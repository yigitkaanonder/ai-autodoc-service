from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from database import get_db
from services.github import get_file_content
from services.user_service import get_user_token
from pipeline import process_function
from services.repo_service import get_repository
from services.registry_service import diff_functions, mark_file_deleted, update_registry, mark_functions_deleted
from services.code_parser import extract_functions
from services.events import event_hub

router = APIRouter()

# Which file extensions to document
SUPPORTED_EXTENSIONS = (".py", ".js", ".ts", ".go", ".java", ".cpp", ".cc", ".cxx", ".h", ".hpp")

@router.post("/webhook/github")
async def github_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.json()

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
    

    repository = get_repository(db, repo_name)
    if not repository:
        print(f"[Webhook] Repository {repo_name} not in DB (not activated?)")
        return JSONResponse(content={"status": "repo_not_found"})
    
    processed = []
    skipped = []
    
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
            process_function(db, repository.id, file_path, func["name"], func["source"], after_sha)

        update_registry(db, repository.id, file_path, functions)
        processed.append(file_path)

    # --- Handle modified files (compare with registry) ---
    for file_path in modified_code_files:
        content = get_file_content(access_token, repo_name, file_path, ref)
        if not content:
            continue

        print(f"[Webhook] Modified file: {file_path} ({len(content)} chars)")
        new, changed, deleted = diff_functions(db, repository.id, file_path, content)

        if not new and not changed and not deleted:
            print(f"[Webhook] {file_path}: no function changes, skipping")
            skipped.append(file_path)
            continue

        print(f"[Webhook] {file_path}: {len(new)} new, {len(changed)} changed, {len(deleted)} deleted")

        # New functions: generate from scratch
        for func in new:
            process_function(db, repository.id, file_path, func["name"], func["source"], after_sha)

        # Changed functions: for now same as new, later will use router agent
        # TODO: implement router agent to only update changed parts of documentation
        for func in changed:
            process_function(db, repository.id, file_path, func["name"], func["source"], after_sha)

        if deleted:
            mark_functions_deleted(db, repository.id, file_path, deleted, after_sha)

        update_registry(db, repository.id, file_path, new + changed)
        processed.append(file_path)

    return JSONResponse(content={
        "status": "processed",
        "repo": repo_name,
        "processed": processed,
        "skipped": skipped
    })