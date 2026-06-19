import asyncio

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session
from database import get_db
from services.github import fetch_commits_for_ref
from services.user_service import get_user_token
from services.events import event_hub
from models import Documentation, Repository, FunctionRegistry

router = APIRouter()


@router.get("/repos/{owner}/{name}/events")
async def repo_events(owner: str, name: str, request: Request):
    repo_full_name = f"{owner}/{name}"
    queue = await event_hub.subscribe(repo_full_name)

    async def event_stream():
        try:
            yield ": connected\n\n"  # open the stream
            while True:
                if await request.is_disconnected():
                    break
                try:
                    # wait for a push, but wake every 5s for a heartbeat
                    message = await asyncio.wait_for(queue.get(), timeout=5.0)
                    yield f"event: push\ndata: {message}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            event_hub.unsubscribe(repo_full_name, queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/repos/{owner}/{name}/backfill")
def backfill_repo(owner: str, name: str, username: str, db: Session = Depends(get_db)):
    access_token = get_user_token(db, username)
    if not access_token:
        return JSONResponse(status_code=401, content={"error": "Not authenticated"})

    repo_full_name = f"{owner}/{name}"
    repo = db.query(Repository).filter(Repository.full_name == repo_full_name).first()
    if not repo:
        return JSONResponse(status_code=404, content={"error": "Repository not found"})

    db.query(Documentation).filter(Documentation.repository_id == repo.id).delete()
    db.query(FunctionRegistry).filter(FunctionRegistry.repository_id == repo.id).delete()
    repo.documented_head_sha = None
    db.commit()

    from services.backfill_service import backfill_repository
    result = backfill_repository(db, access_token, repo_full_name, repo)

    return JSONResponse(content={"repo": repo_full_name, **result})
