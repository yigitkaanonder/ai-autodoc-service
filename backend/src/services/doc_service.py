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