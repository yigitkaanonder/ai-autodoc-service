import os
from fastapi import APIRouter
from fastapi.responses import RedirectResponse, JSONResponse
from services.github import (
    get_github_auth_url,
    exchange_code_for_token,
    get_user_repos,
    get_user_info
)

router = APIRouter()

# Temporary in-memory token storage
# In production this would be a database or session
active_tokens = {}

@router.get("/auth/login")
def login():
    # Redirect user to GitHub OAuth page
    github_url = get_github_auth_url()
    return RedirectResponse(url=github_url)

@router.get("/auth/callback")
def callback(code: str):
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
    active_tokens[username] = access_token

    return RedirectResponse(url=f"/?username={username}")

@router.get("/repos")
def list_repos(username: str):
    # Get token for this user
    access_token = active_tokens.get(username)
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