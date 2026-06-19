from sqlalchemy.orm import Session
from models import Documentation

def save_documentation_to_db(
    db: Session,
    repository_id: int,
    file_path: str,
    content: str,
    function_name: str = None,
    score: int = None,
    commit_sha: str = None
) -> Documentation:
    doc = Documentation(
        repository_id=repository_id,
        file_path=file_path,
        function_name=function_name,
        content=content,
        score=score,
        commit_sha=commit_sha
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc

def get_latest_documentation(db, repository_id, file_path, function_name):
    return (
        db.query(Documentation)
        .filter(
            Documentation.repository_id == repository_id,
            Documentation.file_path == file_path,
            Documentation.function_name == function_name,
            Documentation.is_deleted == False,
        )
        .order_by(Documentation.id.desc())
        .first()
    )
