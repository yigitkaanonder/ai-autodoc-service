from sqlalchemy.orm import Session
from models import FunctionRegistry, Documentation
from services.ast_parser import extract_functions


def diff_functions(db: Session, repository_id: int, file_path: str, code: str):
    """
    Compare current functions against the registry.
    Returns (new, changed, deleted):
      - new: functions not seen before
      - changed: functions whose hash differs from registry
      - deleted: function names in registry but no longer in the file
    """
    current = extract_functions(code)
    current_by_name = {f["name"]: f for f in current}

    registered = db.query(FunctionRegistry).filter(
        FunctionRegistry.repository_id == repository_id,
        FunctionRegistry.file_path == file_path,
        FunctionRegistry.is_deleted == False
    ).all()
    registered_by_name = {c.function_name: c for c in registered}

    new = []
    changed = []
    for name, func in current_by_name.items():
        registered_func = registered_by_name.get(name)
        if registered_func is None:
            new.append(func)
        elif registered_func.content_hash != func["hash"]:
            changed.append(func)
        # else: unchanged

    deleted = [name for name in registered_by_name if name not in current_by_name]

    return new, changed, deleted


def update_registry(db: Session, repository_id: int, file_path: str, functions: list):
    """
    Update the registry with the latest function hashes.
    Marks the function as not deleted and refreshes its hash.
    """
    from datetime import datetime

    for func in functions:
        existing = db.query(FunctionRegistry).filter(
            FunctionRegistry.repository_id == repository_id,
            FunctionRegistry.file_path == file_path,
            FunctionRegistry.function_name == func["name"]
        ).first()

        if existing:
            existing.content_hash = func["hash"]
            existing.is_deleted = False
            existing.updated_at = datetime.utcnow()
        else:
            new_entry = FunctionRegistry(
                repository_id=repository_id,
                file_path=file_path,
                function_name=func["name"],
                content_hash=func["hash"]
            )
            db.add(new_entry)

    db.commit()


def mark_functions_deleted(db: Session, repository_id: int, file_path: str, function_names: list):
    """
    Soft-delete functions that no longer exist.
    Also marks their documentation entries as deleted.
    """
    for name in function_names:
        entry = db.query(FunctionRegistry).filter(
            FunctionRegistry.repository_id == repository_id,
            FunctionRegistry.file_path == file_path,
            FunctionRegistry.function_name == name
        ).first()
        if entry:
            entry.is_deleted = True
    
    # Mark all documentations for this function
    docs = db.query(Documentation).filter(
        Documentation.repository_id == repository_id,
        Documentation.file_path == file_path,
        Documentation.function_name == name,
        Documentation.is_deleted == False
    ).all()
    for doc in docs:
        doc.is_deleted = True

    db.commit()

def mark_file_deleted(db: Session, repository_id: int, file_path: str):
    """
    Soft-delete all functions in a deleted file.
    Also marks all documentations for that file as deleted.
    """

    entries = db.query(FunctionRegistry).filter(
        FunctionRegistry.repository_id == repository_id,
        FunctionRegistry.file_path == file_path,
        FunctionRegistry.is_deleted == False
    ).all()
    function_names = [entry.function_name for entry in entries]

    if function_names:
        mark_functions_deleted(db, repository_id, file_path, function_names)