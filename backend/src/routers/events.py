import asyncio

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session
from database import get_db
from dependencies import get_current_user
from models import Documentation, FunctionRegistry, User
from services.events import event_hub
from services.repo_service import get_owned_repository
from limiter import limiter

router = APIRouter()


@router.get("/repos/{owner}/{name}/events")
async def repo_events(owner: str, name: str, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    repo_full_name = f"{owner}/{name}"

    repo = get_owned_repository(db, current_user.id, repo_full_name)
    if not repo:
        return JSONResponse(status_code=404, content={"error": "Repository not found"})
    
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
@limiter.limit("10/minute")
def backfill_repo(request: Request, owner: str, name: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    repo_full_name = f"{owner}/{name}"
    repo = get_owned_repository(db, current_user.id, repo_full_name)
    if not repo:
        return JSONResponse(status_code=404, content={"error": "Repository not found"})

    db.query(Documentation).filter(Documentation.repository_id == repo.id).delete()
    db.query(FunctionRegistry).filter(FunctionRegistry.repository_id == repo.id).delete()
    repo.documented_head_sha = None
    db.commit()

    from services.backfill_service import backfill_repository
    result = backfill_repository(db, current_user.access_token, repo_full_name, repo)

    return JSONResponse(content={"repo": repo_full_name, **result})
