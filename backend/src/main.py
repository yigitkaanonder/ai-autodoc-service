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

from routers.auth import router as auth_router
from routers.commits import router as commits_router
from routers.docs import router as docs_router
from routers.events import router as events_router
from routers.repos import router as repos_router
from routers.webhook import router as webhook_router

app = FastAPI(title="AI Autodoc Service")
app.mount("/static", StaticFiles(directory="../frontend"), name="static")

# Register routers
app.include_router(auth_router)
app.include_router(commits_router)
app.include_router(docs_router)
app.include_router(events_router)
app.include_router(repos_router)
app.include_router(webhook_router)

@app.get("/")
def root():
    return FileResponse("../frontend/index.html")


if __name__ == "__main__":
    import uvicorn

    def open_browser():
        import time
        time.sleep(1)
        webbrowser.open("http://localhost:8000")

    threading.Thread(target=open_browser).start()
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
