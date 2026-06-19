import os
from dotenv import load_dotenv
load_dotenv()

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from database import get_db
from services.github import get_user_repos, create_webhook, delete_webhook
from services.user_service import get_user_token
from services.repo_service import save_repository
from models import Documentation, Repository, FunctionRegistry

router = APIRouter()


@router.get("/repos")
def list_repos(username: str, db: Session = Depends(get_db)):
    access_token = get_user_token(db, username)
    if not access_token:
        return JSONResponse(
            status_code=401,
            content={"error": "Not authenticated"}
        )

    repos = get_user_repos(access_token)

    # Get active repos from database
    active_repos = db.query(Repository).filter(Repository.is_active == True).all()
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

    return JSONResponse(content={"username": username, "repos": repo_list})


@router.post("/repos/activate")
def activate_repo(username: str, repo_full_name: str, db: Session = Depends(get_db)):
    access_token = get_user_token(db, username)
    if not access_token:
        return JSONResponse(
            status_code=401,
            content={"error": "Not authenticated"}
        )

    ngrok_url = os.getenv("NGROK_URL")
    if not ngrok_url:
        return JSONResponse(
            status_code=500,
            content={"error": "NGROK_URL not configured"}
        )

    webhook_url = f"{ngrok_url}/webhook/github"
    result = create_webhook(access_token, repo_full_name, webhook_url)

    if "id" in result:
        save_repository(db, username, repo_full_name, result["id"])
        repo = db.query(Repository).filter(Repository.full_name == repo_full_name).first()

        # document history: root -> HEAD on first activation, or fill the gap on reactivation
        from services.backfill_service import backfill_repository
        backfill_repository(db, access_token, repo_full_name, repo)

        return JSONResponse(content={
            "status": "activated",
            "repo": repo_full_name,
            "webhook_id": result["id"]
        })
    
    return JSONResponse(
        status_code=400,
        content={"error": result.get("message", "Failed to create webhook"), "details": result}
    )


@router.post("/repos/deactivate")
def deactivate_repo(username: str, repo_full_name: str, db: Session = Depends(get_db)):
    access_token = get_user_token(db, username)
    if not access_token:
        return JSONResponse(status_code=401, content={"error": "Not authenticated"})

    repo = db.query(Repository).filter(Repository.full_name == repo_full_name).first()
    if not repo:
        return JSONResponse(status_code=404, content={"error": "Repository not found"})

    # Delete webhook from GitHub
    if repo.webhook_id:
        delete_webhook(access_token, repo_full_name, repo.webhook_id)

    # Just deactivate, keep data
    repo.is_active = False
    repo.webhook_id = None
    db.commit()

    return JSONResponse(content={"status": "deactivated", "repo": repo_full_name})


@router.post("/repos/delete-data")
def delete_repo_data(username: str, repo_full_name: str, db: Session = Depends(get_db)):
    access_token = get_user_token(db, username)
    if not access_token:
        return JSONResponse(status_code=401, content={"error": "Not authenticated"})

    repo = db.query(Repository).filter(Repository.full_name == repo_full_name).first()
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
