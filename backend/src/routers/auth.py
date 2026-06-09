import os

from dotenv import load_dotenv
load_dotenv()

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from services.github import (
    get_github_auth_url,
    exchange_code_for_token,
    get_user_repos,
    get_user_info,
    create_webhook,
    delete_webhook
)
from services.user_service import save_user_token, get_user_token
from services.repo_service import save_repository
from models import Documentation, Repository, FunctionRegistry

load_dotenv()

router = APIRouter()

@router.get("/auth/login")
def login():
    # Redirect user to GitHub OAuth page
    github_url = get_github_auth_url()
    return RedirectResponse(url=github_url)

@router.get("/auth/callback")
def callback(code: str, db: Session = Depends(get_db)):
    # Exchange code for access token
    access_token = exchange_code_for_token(code)
    if not access_token:
        return JSONResponse(
            status_code=400,
            content={"error": "Failed to get access token"}
        )

    # Get user info and store token
    user = get_user_info(access_token)
    username = user.get("login")
    save_user_token(db, username, access_token)

    return RedirectResponse(url=f"http://localhost:5173/?username={username}")

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
        return JSONResponse(content={
            "status": "activated",
            "repo": repo_full_name,
            "webhook_id": result["id"]
        })
    
    return JSONResponse(
        status_code=400,
        content={"error": result.get("message", "Failed to create webhook"), "details": result}
    )

@router.get("/repos/{owner}/{name}/docs")
def get_repo_docs(owner: str, name: str, db: Session = Depends(get_db)):
    repo_full_name = f"{owner}/{name}"
    repo = db.query(Repository).filter(Repository.full_name == repo_full_name).first()
    if not repo:
        return JSONResponse(status_code=404, content={"error": "Repository not found"})

    # Get only the latest doc per function (max id = newest)
    latest_ids = db.query(
        func.max(Documentation.id).label('max_id')
    ).filter(
        Documentation.repository_id == repo.id,
        Documentation.is_deleted == False
    ).group_by(Documentation.function_name).subquery()

    docs = db.query(Documentation).filter(
        Documentation.id.in_(db.query(latest_ids.c.max_id))
    ).order_by(Documentation.file_path, Documentation.function_name).all()
    
    return JSONResponse(content={
        "repo": repo_full_name,
        "docs": [
            {
                "id": doc.id,
                "file_path": doc.file_path,
                "function_name": doc.function_name,
                "content": doc.content,
                "score": doc.score,
                "commit_sha": doc.commit_sha,
                "created_at": doc.created_at.isoformat() if doc.created_at else None
            }
            for doc in docs
        ]
    })


@router.get("/repos/{owner}/{name}/docs/{function_name}/history")
def get_function_history(owner: str, name: str, function_name: str, db: Session = Depends(get_db)):
    repo_full_name = f"{owner}/{name}"
    repo = db.query(Repository).filter(Repository.full_name == repo_full_name).first()
    if not repo:
        return JSONResponse(status_code=404, content={"error": "Repository not found"})

    docs = db.query(Documentation).filter(
        Documentation.repository_id == repo.id,
        Documentation.function_name == function_name
    ).order_by(Documentation.created_at.desc()).all()

    return JSONResponse(content={
        "repo": repo_full_name,
        "function_name": function_name,
        "history": [
            {
                "id": doc.id,
                "content": doc.content,
                "score": doc.score,
                "commit_sha": doc.commit_sha,
                "is_deleted": doc.is_deleted,
                "created_at": doc.created_at.isoformat() if doc.created_at else None
            }
            for doc in docs
        ]
    })


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
    db.commit()

    return JSONResponse(content={
        "status": "deleted",
        "repo": repo_full_name,
        "deleted_docs": doc_count,
        "deleted_registry": reg_count
    })