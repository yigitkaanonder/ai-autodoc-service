import hmac
import hashlib
import json
import os
from typing import Optional

from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from database import get_db, SessionLocal
from models import Documentation
from services.github import get_file_content
from services.user_service import get_user_token
from services.repo_service import get_repository
from services.registry_service import diff_functions, mark_file_deleted, update_registry, mark_functions_deleted
from services.code_parser import extract_functions
from services.events import event_hub
from services.doc_service import get_latest_documentation
from services.changeset_service import ChangedFunction, run_repo_changeset_async
from limiter import limiter

router = APIRouter()

# Which file extensions to document
SUPPORTED_EXTENSIONS = (".py", ".js", ".ts", ".go", ".java", ".cpp", ".cc", ".cxx", ".h", ".hpp")


WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")

def verify_signature(raw_body: bytes, signature_header: Optional[str]) -> bool:
    """Verify GitHub's X-Hub-Signature-256 HMAC over the exact raw request body.
 
    GitHub signs the raw bytes it sends using the shared webhook secret. We
    recompute that HMAC and compare in constant time. Any payload not signed
    with our secret (i.e. a forged push) fails here and never reaches the
    processing logic below.
    """
    # Fail closed: if no secret is configured, reject everything rather than
    # silently accepting unsigned (forgeable) payloads.
    if not WEBHOOK_SECRET:
        return False
    if not signature_header or not signature_header.startswith("sha256="):
        return False
 
    expected = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode(),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
 
    # constant-time compare to avoid timing side-channels
    return hmac.compare_digest(expected, signature_header)


@router.post("/webhook/github")
@limiter.limit("60/minute")
async def github_webhook(request: Request, db: Session = Depends(get_db)):
    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    if not verify_signature(raw_body, signature):
        return JSONResponse(status_code=401, content={"error": "Invalid or missing signature"})
 
    payload = json.loads(raw_body)

    repo_name = payload.get("repository", {}).get("full_name")
    pusher = payload.get("pusher", {}).get("name")
    commits = payload.get("commits", [])
    ref = payload.get("ref", "").replace("refs/heads/", "")
    after_sha = payload.get("after")

    # Collect changed files
    added_files = set()
    modified_files = set()
    deleted_files = set()
    for commit in commits:
        added_files.update(commit.get("added", []))
        modified_files.update(commit.get("modified", []))
        deleted_files.update(commit.get("removed", []))

    # Filter to only supported code files
    added_code_files = [f for f in added_files if f.endswith(SUPPORTED_EXTENSIONS)]
    modified_code_files = [f for f in modified_files if f.endswith(SUPPORTED_EXTENSIONS)]
    deleted_code_files = [f for f in deleted_files if f.endswith(SUPPORTED_EXTENSIONS)]

    print(f"\n[Webhook] Push received: {repo_name} by {pusher}")
    event_hub.publish(repo_name)
    print(f"[Webhook] Added: {added_code_files}")
    print(f"[Webhook] Modified: {modified_code_files}")
    print(f"[Webhook] Deleted: {deleted_code_files}")

    # Every processed push extends coverage up to its HEAD commit, even
    # pushes that changed no code (docs are still current there).
    repository = get_repository(db, repo_name)
    if repository and not repository.is_active:
        print(f"[Webhook] {repo_name} is deactivated, ignoring push")
        return JSONResponse(content={"status": "inactive"})

    prev_head = repository.documented_head_sha if repository else None
    if repository and after_sha:
        repository.documented_head_sha = after_sha
        db.commit()

    if not added_code_files and not modified_code_files and not deleted_code_files:
        return JSONResponse(content={"status": "no_code_files"})
    
    repo_owner = repo_name.split("/")[0]
    access_token = get_user_token(db, repo_owner)
    if not access_token:
        print(f"[Webhook] No token for {repo_owner}, cannot fetch files")
        return JSONResponse(content={"status": "no_token"})
    

    if not repository:
        print(f"[Webhook] Repository {repo_name} not in DB (not activated?)")
        return JSONResponse(content={"status": "repo_not_found"})
    
    processed = []
    skipped = []

    changeset = []
    registry_updates = {}
    
    # --- Handle deleted files ---
    for file_path in deleted_code_files:
        mark_file_deleted(db, repository.id, file_path, after_sha)
        print(f"[Webhook] File deleted: {file_path}")

    # --- Handle added files (all functions are new, skip diff) ---
    for file_path in added_code_files:
        content = get_file_content(access_token, repo_name, file_path, ref)
        if not content:
            continue

        print(f"[Webhook] New file: {file_path} ({len(content)} chars)")
        functions = extract_functions(content, file_path)

        for func in functions:
            changeset.append(ChangedFunction(func=func, mode="added"))
        processed.append(file_path)

    # --- Handle modified files (compare with registry) ---
    for file_path in modified_code_files:
        content = get_file_content(access_token, repo_name, file_path, ref)
        if not content:
            continue

        print(f"[Webhook] Modified file: {file_path} ({len(content)} chars)")
        
        by_name = {f["name"]: f for f in extract_functions(content, file_path)}
        new, changed, deleted = diff_functions(db, repository.id, file_path, content)

        if not new and not changed and not deleted:
            print(f"[Webhook] {file_path}: no function changes, skipping")
            skipped.append(file_path)
            continue

        print(f"[Webhook] {file_path}: {len(new)} new, {len(changed)} changed, {len(deleted)} deleted")

        # New functions: generate from scratch
        for func in new:
            changeset.append(ChangedFunction(func=by_name.get(func["name"], func), mode="added"))

        # Changed functions: ask critic #1. keep or generate.
        for func in changed:
            existing = get_latest_documentation(db, repository.id, file_path, func["name"])
            changeset.append(ChangedFunction(
                func=by_name.get(func["name"], func),
                mode="modified",
                existing_documentation=existing.content if existing else "",
            ))

        if deleted:
            mark_functions_deleted(db, repository.id, file_path, deleted, after_sha)

        registry_updates[file_path] = new + changed
        processed.append(file_path)

    result = None
    if changeset:
        result = await run_repo_changeset_async(db, SessionLocal, repository.id, after_sha, changeset)

    if result is not None and result.cancelled:
        db.query(Documentation).filter(
            Documentation.repository_id == repository.id,
            Documentation.commit_sha == after_sha,
        ).delete()
        repository.documented_head_sha = prev_head
        db.commit()
        print(f"[Webhook] {repo_name}: cancelled, rolled back push")
        return JSONResponse(content={"status": "cancelled", "repo": repo_name})

    for file_path, functions in registry_updates.items():
        update_registry(db, repository.id, file_path, functions)

    return JSONResponse(content={
        "status": "processed",
        "repo": repo_name,
        "processed": processed,
        "skipped": skipped
    })