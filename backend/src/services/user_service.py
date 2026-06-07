from sqlalchemy.orm import Session
from models import User
from typing import Optional

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