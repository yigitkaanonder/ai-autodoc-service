from typing import Optional

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import User
from services.user_service import get_user_by_session


def get_current_user(
    session: Optional[str] = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    """
    Resolve the caller's identity from the HttpOnly `session` cookie.
 
    This is the single source of truth for "who is making this request". No
    endpoint should ever trust a username coming from the query string, body,
    or headers — only this dependency, which validates a server-issued token.
    """
    
    user = get_user_by_session(db, session)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
