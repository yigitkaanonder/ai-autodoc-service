import os
import sys
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from datetime import datetime

import webbrowser
import threading
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

load_dotenv()

# Add src to path so imports work
sys.path.append(os.path.dirname(__file__))

from routers.auth import router as auth_router
from routers.webhook import router as webhook_router
from agents.generator import generate_documentation
from graph import build_graph

app = FastAPI(title="AI Autodoc Service")
app.mount("/static", StaticFiles(directory="../frontend"), name="static")

# Register routers
app.include_router(auth_router)
app.include_router(webhook_router)

@app.get("/")
def root():
    return FileResponse("../frontend/index.html")


def save_documentation(content: str, filename: str = "documentation") -> str:
    docs_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "docs")
    )
    os.makedirs(docs_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(docs_dir, f"{filename}_{timestamp}.md")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("# Documentation\n\n")
        f.write(f"**Generated at:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("---\n\n")
        f.write(content)

    print(f"Documentation saved: {filepath}")
    return filepath


if __name__ == "__main__":
    import uvicorn

    def open_browser():
        import time
        time.sleep(1)
        webbrowser.open("http://localhost:8000")

    threading.Thread(target=open_browser).start()
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)