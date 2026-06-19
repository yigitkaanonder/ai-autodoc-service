from dotenv import load_dotenv
load_dotenv()

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from database import get_db
from services.github import get_github_auth_url, exchange_code_for_token, get_user_info
from services.user_service import save_user_token

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
