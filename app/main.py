import os
import subprocess
import sys
import threading
import time

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .config import STATIC_DIR
from .routers import projects, render, stock, system, youtube

app = FastAPI(title="YT Auto (OmniVoice)")

RENDER_WATCHDOG_INTERVAL_SEC = 30.0
RENDER_STALE_AFTER_SEC = 60
RENDER_MAX_RUNTIME_SEC = 7200
DISABLE_BACKGROUND_WORKERS_ENV = "NEWAUTO_DISABLE_BACKGROUND_WORKERS"


def _start_render_worker() -> None:
    creation_flags = 0
    if os.name == "nt":
        creation_flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(
        [sys.executable, "-m", "app.workers.render_worker"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=creation_flags,
        close_fds=os.name != "nt",
    )


def _start_render_watchdog() -> None:
    def watch() -> None:
        while True:
            try:
                db.recover_stale_render_jobs(
                    stale_after_sec=RENDER_STALE_AFTER_SEC,
                    max_runtime_sec=RENDER_MAX_RUNTIME_SEC,
                )
            except Exception:
                pass
            time.sleep(RENDER_WATCHDOG_INTERVAL_SEC)

    threading.Thread(target=watch, daemon=True).start()


@app.on_event("startup")
def on_startup() -> None:
    db.init_db()
    db.recover_interrupted_tasks()
    if os.environ.get(DISABLE_BACKGROUND_WORKERS_ENV) == "1":
        return
    _start_render_worker()
    _start_render_watchdog()


app.include_router(projects.router)
app.include_router(render.router)
app.include_router(render.meta_router)
app.include_router(system.router)
app.include_router(stock.router)
app.include_router(youtube.router)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}
