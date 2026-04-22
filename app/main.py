from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .config import STATIC_DIR
from .routers import projects, render, youtube

app = FastAPI(title="YT Auto (OmniVoice)")


@app.on_event("startup")
def on_startup() -> None:
    db.init_db()


app.include_router(projects.router)
app.include_router(render.router)
app.include_router(youtube.router)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}
