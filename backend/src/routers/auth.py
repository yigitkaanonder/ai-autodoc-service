import os

from dotenv import load_dotenv
load_dotenv()

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from database import get_db
from services.github import (
    get_github_auth_url,
    exchange_code_for_token,
    get_user_repos,
    get_user_info,
    create_webhook
)
from services.user_service import save_user_token, get_user_token
from services.repo_service import save_repository

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

    return RedirectResponse(url=f"/?username={username}")

@router.get("/repos")
def list_repos(username: str, db: Session = Depends(get_db)):
    # Get token for this user
    access_token = get_user_token(db, username)
    if not access_token:
        return JSONResponse(
            status_code=401,
            content={"error": "Not authenticated"}
        )

    # Fetch and return repos
    repos = get_user_repos(access_token)
    repo_list = [
        {
            "name": repo["name"],
            "full_name": repo["full_name"],
            "private": repo["private"],
            "url": repo["html_url"]
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