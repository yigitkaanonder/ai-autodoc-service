from services.celery_app import celery_app
from database import SessionLocal
from services.github import get_file_content
from services.user_service import get_user_token
from services.repo_service import get_repository
from services.registry_service import (
    diff_functions, update_registry, mark_functions_deleted, mark_file_deleted,
)
from services.code_parser import extract_functions
from services.doc_service import get_latest_documentation
from services.changeset_service import ChangedFunction, run_repo_changeset

SUPPORTED_EXTENSIONS = (".py", ".js", ".ts", ".go", ".java", ".cpp", ".cc", ".cxx", ".h", ".hpp")


@celery_app.task(name="autodoc.document_push", bind=True, max_retries=2, default_retry_delay=15)
def document_push(self, payload):
    """Enqueued by the webhook for each push. Documents the push synchronously."""
    db = SessionLocal()
    try:
        return _run_push(db, payload)
    except Exception as exc:
        db.rollback()
        # transient failures (GitHub/DB hiccup): retry with backoff
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(name="autodoc.backfill_repo", bind=True)
def backfill_repo(self, repo_full_name):
    """Enqueued on (re)activation. Walks the default branch and documents the gap."""
    from services.backfill_service import backfill_repository
    db = SessionLocal()
    try:
        repo_owner = repo_full_name.split("/")[0]
        access_token = get_user_token(db, repo_owner)
        repository = get_repository(db, repo_full_name)
        if not access_token or not repository:
            return {"status": "not_ready", "repo": repo_full_name}
        return backfill_repository(db, access_token, repo_full_name, repository)
    finally:
        db.close()

# -------------------------------------------------------------------
# Synced core for the push job. Separated from Celery to allow 
# testing; the worker task just manages the session and calls this.
# -------------------------------------------------------------------
def _run_push(db, payload):
    repo_name = payload.get("repository", {}).get("full_name")
    commits = payload.get("commits", [])
    ref = payload.get("ref", "").replace("refs/heads/", "")
    after_sha = payload.get("after")

    added_files, modified_files, deleted_files = set(), set(), set()
    for commit in commits:
        added_files.update(commit.get("added", []))
        modified_files.update(commit.get("modified", []))
        deleted_files.update(commit.get("removed", []))

    added_code_files = [f for f in added_files if f.endswith(SUPPORTED_EXTENSIONS)]
    modified_code_files = [f for f in modified_files if f.endswith(SUPPORTED_EXTENSIONS)]
    deleted_code_files = [f for f in deleted_files if f.endswith(SUPPORTED_EXTENSIONS)]

    print(f"\n[Task] document_push: {repo_name} ref={ref} after={after_sha}")

    # Advance the coverage HEAD (even pushes with no code changes will consider the documentation up to date).
    repository = get_repository(db, repo_name)
    if repository and after_sha:
        repository.documented_head_sha = after_sha
        db.commit()

    if not added_code_files and not modified_code_files and not deleted_code_files:
        return {"status": "no_code_files", "repo": repo_name}

    repo_owner = repo_name.split("/")[0]
    access_token = get_user_token(db, repo_owner)
    if not access_token:
        print(f"[Task] No token for {repo_owner}")
        return {"status": "no_token", "repo": repo_name}

    repository = get_repository(db, repo_name)
    if not repository:
        print(f"[Task] Repository {repo_name} not activated")
        return {"status": "repo_not_found", "repo": repo_name}

    processed, skipped = [], []
    changeset = []
    registry_updates = {}

    # deleted files
    for file_path in deleted_code_files:
        mark_file_deleted(db, repository.id, file_path, after_sha)
        print(f"[Task] File deleted: {file_path}")

    # added files
    for file_path in added_code_files:
        content = get_file_content(access_token, repo_name, file_path, ref)
        if not content:
            continue
        functions = extract_functions(content, file_path)
        registry_updates[file_path] = functions
        for func in functions:
            changeset.append(ChangedFunction(func=func, mode="added"))
        processed.append(file_path)

    # modified files
    for file_path in modified_code_files:
        content = get_file_content(access_token, repo_name, file_path, ref)
        if not content:
            continue
        by_name = {f["name"]: f for f in extract_functions(content, file_path)}
        new, changed, deleted = diff_functions(db, repository.id, file_path, content)

        if not new and not changed and not deleted:
            skipped.append(file_path)
            continue

        for func in new:
            changeset.append(ChangedFunction(func=by_name.get(func["name"], func), mode="added"))
        for func in changed:
            existing = get_latest_documentation(db, repository.id, file_path, func["name"])
            changeset.append(ChangedFunction(
                func=by_name.get(func["name"], func), mode="modified",
                existing_documentation=existing.content if existing else "",
            ))
        if deleted:
            mark_functions_deleted(db, repository.id, file_path, deleted, after_sha)
        registry_updates[file_path] = new + changed
        processed.append(file_path)

    # documantate entire push as a single changeset
    if changeset:
        run_repo_changeset(db, SessionLocal, repository.id, after_sha, changeset)

    # update registry after documentation is done.
    for file_path, functions in registry_updates.items():
        update_registry(db, repository.id, file_path, functions)

    return {"status": "processed", "repo": repo_name, "processed": processed, "skipped": skipped}