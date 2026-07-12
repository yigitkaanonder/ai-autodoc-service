from sqlalchemy.orm import Session
from models import Repository, User


def save_repository(db: Session, username: str, repo_full_name: str, webhook_id: int) -> Repository:
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None

    repo = db.query(Repository).filter(Repository.full_name == repo_full_name).first()

    if repo:
        # Update existing repo.
        repo.webhook_id = webhook_id
        repo.is_active = True
    else:
        repo = Repository(
            full_name=repo_full_name,
            user_id=user.id,
            webhook_id=webhook_id,
            is_active=True
        )
        db.add(repo)

    db.commit()
    db.refresh(repo)
    return repo


def get_repository(db: Session, repo_full_name: str) -> Repository:
    return db.query(Repository).filter(Repository.full_name == repo_full_name).first()


def get_owned_repository(db: Session, user_id: int, repo_full_name: str) -> Repository:
    """Fetch a repo only if it belongs to this user.
 
    Returns None both when the repo does not exist 
    AND when it exists but is owned by someone else
    """
    
    repo = db.query(Repository).filter(Repository.full_name == repo_full_name).first()
    if not repo or repo.user_id != user_id:
        return None
    return repo
