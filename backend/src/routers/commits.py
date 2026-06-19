from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from services.github import fetch_repo_branches, fetch_commits_for_ref
from services.user_service import get_user_token
from models import Documentation, Repository

router = APIRouter()

@router.get("/repos/{owner}/{name}/commits")
def get_repo_commit_graph(owner: str, name: str, username: str, db: Session = Depends(get_db)):
    access_token = get_user_token(db, username)
    if not access_token:
        return JSONResponse(status_code=401, content={"error": "Not authenticated"})

    repo_full_name = f"{owner}/{name}"

    # every branch and its head commit
    branches = fetch_repo_branches(access_token, repo_full_name)
    branch_list = [{"name": b["name"], "head_sha": b["commit"]["sha"]} for b in branches]

    # walk each branch head to gather the full directed acyclic graph; dedupe by sha
    commits_by_sha = {}
    for branch in branch_list:
        for raw in fetch_commits_for_ref(access_token, repo_full_name, branch["head_sha"]):
            sha = raw["sha"]
            if sha in commits_by_sha:
                continue
            author_login = (raw.get("author") or {}).get("login")
            commit_author = raw["commit"]["author"]
            parents = [p["sha"] for p in raw.get("parents", [])]
            commits_by_sha[sha] = {
                "sha": sha,
                "short_sha": sha[:7],
                "message": raw["commit"]["message"].split("\n")[0],
                "author": author_login or commit_author.get("name", "unknown"),
                "date": commit_author.get("date"),
                "parents": parents,
                "is_merge": len(parents) > 1,
            }

    # newest first 
    commits = sorted(commits_by_sha.values(), key=lambda c: c["date"] or "", reverse=True)

    repo = db.query(Repository).filter(Repository.full_name == repo_full_name).first()
    return JSONResponse(content={
        "repo": repo_full_name,
        "branches": branch_list,
        "commits": commits,
        "documented_head_sha": repo.documented_head_sha if repo else None,
    })


@router.get("/repos/{owner}/{name}/commits/{sha}/changes")
def get_commit_changes(owner: str, name: str, sha: str, db: Session = Depends(get_db)):
    repo_full_name = f"{owner}/{name}"
    repo = db.query(Repository).filter(Repository.full_name == repo_full_name).first()
    if not repo:
        return JSONResponse(status_code=404, content={"error": "Repository not found"})

    # all documentation events recorded at this commit
    rows = db.query(Documentation).filter(
        Documentation.repository_id == repo.id,
        Documentation.commit_sha == sha
    ).order_by(Documentation.id).all()

    added, changed, deleted = [], [], []
    for row in rows:
        if row.is_deleted:
            deleted.append({"function_name": row.function_name, "file_path": row.file_path})
            continue

        # added vs changed: look at the event immediately before this one
        prev = db.query(Documentation).filter(
            Documentation.repository_id == repo.id,
            Documentation.function_name == row.function_name,
            Documentation.file_path == row.file_path,
            Documentation.id < row.id
        ).order_by(Documentation.id.desc()).first()

        entry = {
            "id": row.id,
            "function_name": row.function_name,
            "file_path": row.file_path,
            "content": row.content,
            "score": row.score,
        }
        if prev is None or prev.is_deleted:
            added.append(entry)      # first time, or re-added after a deletion
        else:
            changed.append(entry)    # had a live doc immediately before

    return JSONResponse(content={
        "repo": repo_full_name,
        "commit_sha": sha,
        "added": added,
        "changed": changed,
        "deleted": deleted,
    })


@router.get("/repos/{owner}/{name}/commits/{sha}/snapshot")
def get_commit_snapshot(owner: str, name: str, sha: str, username: str, db: Session = Depends(get_db)):
    access_token = get_user_token(db, username)
    if not access_token:
        return JSONResponse(status_code=401, content={"error": "Not authenticated"})

    repo_full_name = f"{owner}/{name}"
    repo = db.query(Repository).filter(Repository.full_name == repo_full_name).first()
    if not repo:
        return JSONResponse(status_code=404, content={"error": "Repository not found"})

    # this commit + all its ancestors
    ancestors = fetch_commits_for_ref(access_token, repo_full_name, sha, per_page=100)
    ancestor_shas = [c["sha"] for c in ancestors] or [sha]

    # latest documentation event per function, restricted to those commits
    latest_ids = db.query(
        func.max(Documentation.id).label('max_id')
    ).filter(
        Documentation.repository_id == repo.id,
        Documentation.commit_sha.in_(ancestor_shas)
    ).group_by(Documentation.function_name).subquery()

    # keep only functions whose latest event in this range is NOT a deletion
    docs = db.query(Documentation).filter(
        Documentation.id.in_(db.query(latest_ids.c.max_id)),
        Documentation.is_deleted == False
    ).order_by(Documentation.file_path, Documentation.function_name).all()

    return JSONResponse(content={
        "repo": repo_full_name,
        "commit_sha": sha,
        "docs": [
            {
                "id": d.id,
                "file_path": d.file_path,
                "function_name": d.function_name,
                "content": d.content,
                "score": d.score,
                "commit_sha": d.commit_sha,
            }
            for d in docs
        ]
    })
