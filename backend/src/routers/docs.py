from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from models import Documentation, Repository

router = APIRouter()


@router.get("/repos/{owner}/{name}/docs")
def get_repo_docs(owner: str, name: str, db: Session = Depends(get_db)):
    repo_full_name = f"{owner}/{name}"
    repo = db.query(Repository).filter(Repository.full_name == repo_full_name).first()
    if not repo:
        return JSONResponse(status_code=404, content={"error": "Repository not found"})

   # latest event (row) per function, across ALL rows including tombstones
    latest_ids = db.query(
        func.max(Documentation.id).label('max_id')
    ).filter(
        Documentation.repository_id == repo.id
    ).group_by(Documentation.function_name).subquery()

    # keep only functions whose latest event is NOT a deletion
    docs = db.query(Documentation).filter(
        Documentation.id.in_(db.query(latest_ids.c.max_id)),
        Documentation.is_deleted == False
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
    ).order_by(Documentation.id.desc()).all()

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
