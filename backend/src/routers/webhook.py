from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from services.github import get_file_content
from routers.auth import active_tokens

router = APIRouter()

# Which file extensions to document
SUPPORTED_EXTENSIONS = (".py", ".js", ".ts", ".go", ".java", ".cpp")

@router.post("/webhook/github")
async def github_webhook(request: Request):
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
    access_token = active_tokens.get(repo_owner)
    if not access_token:
        print(f"[Webhook] No token for {repo_owner}, cannot fetch files")
        return JSONResponse(content={"status": "no_token"})


    # Fetch each file's content
    # Right now it fetches the whole file for documentation. 
    # But after adding cache it will check only the changed 
    # files and fetch the contents of those functions/classes.
    files_with_content = []
    for file_path in code_files:
        content = get_file_content(access_token, repo_name, file_path, ref)
        if content:
            files_with_content.append({
                "path": file_path,
                "content": content
            })
            print(f"[Webhook] Fetched {file_path} ({len(content)} chars)")

    return JSONResponse(content={
        "status": "files_fetched",
        "repo": repo_name,
        "file_count": len(files_with_content)
    })