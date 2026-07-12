import os
from dotenv import load_dotenv
load_dotenv()

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from database import get_db
from dependencies import get_current_user
from models import Documentation, Repository, FunctionRegistry, User
from services.github import get_user_repos, create_webhook, delete_webhook
from services.repo_service import save_repository, get_owned_repository
from models import Documentation, Repository, FunctionRegistry
from limiter import limiter

router = APIRouter()


@router.get("/repos")
def list_repos(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    repos = get_user_repos(current_user.access_token)

    active_repos = db.query(Repository).filter(
        Repository.is_active == True,
        Repository.user_id == current_user.id,
    ).all()
    active_names = {r.full_name for r in active_repos}

    repo_list = [
        {
            "name": repo["name"],
            "full_name": repo["full_name"],
            "private": repo["private"],
            "url": repo["html_url"],
            "is_active": repo["full_name"] in active_names
        }
        for repo in repos
    ]

    return JSONResponse(content={"username": current_user.username, "repos": repo_list})


@router.post("/repos/activate")
@limiter.limit("10/minute")
def activate_repo(request: Request, repo_full_name: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ngrok_url = os.getenv("NGROK_URL")
    if not ngrok_url:
        return JSONResponse(
            status_code=500,
            content={"error": "NGROK_URL not configured"}
        )

    webhook_url = f"{ngrok_url}/webhook/github"
    result = create_webhook(current_user.access_token, repo_full_name, webhook_url)

    if "id" in result:
        save_repository(db, current_user.username, repo_full_name, result["id"])
        repo = db.query(Repository).filter(Repository.full_name == repo_full_name).first()

        # document history: root -> HEAD on first activation, or fill the gap on reactivation
        from services.backfill_service import backfill_repository
        backfill_repository(db, current_user.access_token, repo_full_name, repo)

        return JSONResponse(content={
            "status": "activated",
            "repo": repo_full_name,
            "webhook_id": result["id"]
        })
    
    # Don't leak GitHub's raw API response to the client: keep the full detail
    # in the server log, return only a short reason.
    print(f"[activate] webhook creation failed for {repo_full_name}: {result}")
    
    return JSONResponse(
        status_code=400,
        content={"error": result.get("message", "Failed to create webhook")}
    )


@router.post("/repos/deactivate")
def deactivate_repo(repo_full_name: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    repo = get_owned_repository(db, current_user.id, repo_full_name)
    if not repo:
        return JSONResponse(status_code=404, content={"error": "Repository not found"})

    # Delete webhook from GitHub
    if repo.webhook_id:
        delete_webhook(current_user.access_token, repo_full_name, repo.webhook_id)

    # Just deactivate, keep data
    repo.is_active = False
    repo.webhook_id = None
    db.commit()

    return JSONResponse(content={"status": "deactivated", "repo": repo_full_name})


@router.post("/repos/delete-data")
def delete_repo_data(repo_full_name: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    repo = get_owned_repository(db, current_user.id, repo_full_name)
    if not repo:
        return JSONResponse(status_code=404, content={"error": "Repository not found"})

    doc_count = db.query(Documentation).filter(Documentation.repository_id == repo.id).delete()
    reg_count = db.query(FunctionRegistry).filter(FunctionRegistry.repository_id == repo.id).delete()
    repo.documented_head_sha = None
    db.commit()

    return JSONResponse(content={
        "status": "deleted",
        "repo": repo_full_name,
        "deleted_docs": doc_count,
        "deleted_registry": reg_count
    })
