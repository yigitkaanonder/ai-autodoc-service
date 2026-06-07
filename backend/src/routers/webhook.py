from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from database import get_db
from services.github import get_file_content
from services.user_service import get_user_token
from pipeline import process_file

router = APIRouter()

# Which file extensions to document
SUPPORTED_EXTENSIONS = (".py", ".js", ".ts", ".go", ".java", ".cpp")

@router.post("/webhook/github")
async def github_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.json()

    repo_name = payload.get("repository", {}).get("full_name")
    pusher = payload.get("pusher", {}).get("name")
    commits = payload.get("commits", [])
    ref = payload.get("ref", "").replace("refs/heads/", "")

    # Collect changed files
    changed_files = set()
    for commit in commits:
        changed_files.update(commit.get("added", []))
        changed_files.update(commit.get("modified", []))

    # Filter to only supported code files
    code_files = [f for f in changed_files if f.endswith(SUPPORTED_EXTENSIONS)]

    print(f"\n[Webhook] Push received: {repo_name} by {pusher}")
    print(f"[Webhook] Changed files: {list(changed_files)}")
    print(f"[Webhook] Code files to process: {code_files}")

    if not code_files:
        return JSONResponse(content={"status": "no_code_files"})
    # Will be stored in database in real implementation.
    repo_owner = repo_name.split("/")[0]
    access_token = get_user_token(db, repo_owner)
    if not access_token:
        print(f"[Webhook] No token for {repo_owner}, cannot fetch files")
        return JSONResponse(content={"status": "no_token"})


    # Fetch each file's content
    # Right now it fetches the whole file for documentation. 
    # But after adding cache it will check only the changed 
    # files and fetch the contents of those functions/classes.
    processed = []
    for file_path in code_files:
        content = get_file_content(access_token, repo_name, file_path, ref)
        if content:
            print(f"[Webhook] Fetched {file_path} ({len(content)} chars)")
            doc_path = process_file(file_path, content)
            processed.append({"file": file_path, "doc": doc_path})

    return JSONResponse(content={
        "status": "processed",
        "repo": repo_name,
        "processed_count": len(processed)
    })