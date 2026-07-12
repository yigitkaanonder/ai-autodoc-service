import hmac
import os
import secrets
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

from fastapi import APIRouter, Cookie, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from database import get_db
from dependencies import get_current_user
from models import User
from services.github import get_github_auth_url, exchange_code_for_token, get_user_info
from services.user_service import save_user_token, create_session, clear_session

router = APIRouter()

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
SESSION_MAX_AGE = 7 * 24 * 60 * 60  # 7 days
OAUTH_STATE_MAX_AGE = 600           # 10 minutes to complete the OAuth round-trip

def _set_session_cookie(response, token: str):
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=SESSION_MAX_AGE,
        path="/",
    )

@router.get("/auth/login")
def login():
    # Create an anti-CSRF state nonce, remember it in a short-lived cookie, and
    # hand the same value to GitHub. The callback checks that they match.
    state = secrets.token_urlsafe(16)
    github_url = get_github_auth_url(state)
    response = RedirectResponse(url=github_url)
    response.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=OAUTH_STATE_MAX_AGE,
        path="/",
    )
    return response


@router.get("/auth/callback")
def callback(
    code: str,
    state: Optional[str] = None,
    oauth_state: Optional[str] = Cookie(default=None),
    db: Session = Depends(get_db),
    ):
    # Reject the callback unless the state echoed by GitHub matches the nonce we
    # set at /auth/login. This blocks login-CSRF / code-injection.
    if not state or not oauth_state or not hmac.compare_digest(state, oauth_state):
        return JSONResponse(status_code=400, content={"error": "Invalid OAuth state"})
    
    access_token = exchange_code_for_token(code)
    if not access_token:
        return JSONResponse(
            status_code=400,
            content={"error": "Failed to get access token"}
        )

    # Get user info and store token
    user_info = get_user_info(access_token)
    username = user_info.get("login")
    user = save_user_token(db, username, access_token)

    # Issue a server-side session and hand it to the browser as an HttpOnly
    # cookie. The username is no longer passed in the URL — identity now lives
    # in the signed session, not in a client-supplied string.
    session_token = create_session(db, user)
    response = RedirectResponse(url=f"{FRONTEND_URL}/repos")
    _set_session_cookie(response, session_token)
    response.delete_cookie(key="oauth_state", path="/")  # one-time use
    return response


@router.get("/auth/me")
def me(current_user: User = Depends(get_current_user)):
    # Lets the frontend discover who it is without reading the HttpOnly cookie.
    return JSONResponse(content={"username": current_user.username})
 
 
@router.post("/auth/logout")
def logout(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    clear_session(db, current_user)
    response = JSONResponse(content={"status": "logged_out"})
    response.delete_cookie(key="session", path="/")
    return response
