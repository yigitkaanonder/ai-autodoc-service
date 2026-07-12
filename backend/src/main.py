import os
import sys
from fastapi import FastAPI
from dotenv import load_dotenv

import webbrowser
import threading
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

load_dotenv()

# Add src to path so imports work
sys.path.append(os.path.dirname(__file__))

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
 
from limiter import limiter
from routers.auth import router as auth_router
from routers.commits import router as commits_router
from routers.docs import router as docs_router
from routers.events import router as events_router
from routers.repos import router as repos_router
from routers.webhook import router as webhook_router

app = FastAPI(title="AI Autodoc Service")

# Rate limiting: register the shared limiter and the 429 handler. Individual
# heavy/public endpoints opt in with @limiter.limit(...).
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Register routers
app.include_router(auth_router)
app.include_router(commits_router)
app.include_router(docs_router)
app.include_router(events_router)
app.include_router(repos_router)
app.include_router(webhook_router)


if __name__ == "__main__":
    import uvicorn

    def open_browser():
        import time
        time.sleep(1)
        webbrowser.open("http://localhost:8000")

    if os.getenv("AUTODOC_OPEN_BROWSER", "false").lower() == "true":
        threading.Thread(target=open_browser, daemon=True).start()
 
    host = os.getenv("HOST", "127.0.0.1")
    reload = os.getenv("AUTODOC_RELOAD", "false").lower() == "true"
    uvicorn.run("main:app", host=host, port=8000, reload=reload)
