import hashlib
import secrets
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from models import User
from typing import Optional

SESSION_TTL_DAYS = 7


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def save_user_token(db: Session, username: str, access_token: str) -> User:
    # Check if user already exists
    user = db.query(User).filter(User.username == username).first()

    if user:
        user.access_token = access_token
    else:
        user = User(username=username, access_token=access_token)
        db.add(user)

    db.commit()
    db.refresh(user)
    return user


def get_user_token(db: Session, username: str) -> Optional[str]:
    user = db.query(User).filter(User.username == username).first()
    return user.access_token if user else None


def create_session(db: Session, user: User) -> str:
    """Issue a fresh opaque session token for the user and store only its hash.
 
    Returns the RAW token, which the caller sets as an HttpOnly cookie. The raw
    value never touches the database.
    """
    raw_token = secrets.token_urlsafe(32)
    user.session_token_hash = _hash_token(raw_token)
    user.session_expires_at = datetime.utcnow() + timedelta(days=SESSION_TTL_DAYS)
    db.commit()
    return raw_token
 
 
def get_user_by_session(db: Session, raw_token: str) -> Optional[User]:
    """Resolve a raw session token back to its user, or None if invalid/expired."""
    if not raw_token:
        return None
    user = db.query(User).filter(
        User.session_token_hash == _hash_token(raw_token)
    ).first()
    if not user:
        return None
    if not user.session_expires_at or user.session_expires_at < datetime.utcnow():
        return None
    return user
 
 
def clear_session(db: Session, user: User) -> None:
    user.session_token_hash = None
    user.session_expires_at = None
    db.commit()
