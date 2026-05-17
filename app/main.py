import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from collections.abc import Callable
from typing import cast

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .config import STATIC_DIR, STORAGE_DIR
from .routers import autopilot, image_gen, projects, render, stock, system, youtube

app = FastAPI(title="YT Auto (OmniVoice)")

RENDER_WATCHDOG_INTERVAL_SEC = 30.0
RENDER_STALE_AFTER_SEC = 60
RENDER_MAX_RUNTIME_SEC = 7200
SOURCE_DRAFT_STALE_AFTER_SEC = 60
SOURCE_DRAFT_MAX_RUNTIME_SEC = 900
BODY_IMAGE_STALE_AFTER_SEC = 1200
BODY_IMAGE_MAX_RUNTIME_SEC = 7200
TTS_STALE_AFTER_SEC = 60
TTS_MAX_RUNTIME_SEC = 1800
AUTOPILOT_STALE_AFTER_SEC = 60
AUTOPILOT_MAX_RUNTIME_SEC = 7200
DISABLE_BACKGROUND_WORKERS_ENV = "NEWAUTO_DISABLE_BACKGROUND_WORKERS"
WORKER_LOG_DIR = STORAGE_DIR / "logs"
WORKER_ENTRYPOINTS = {
    "render": ("app.workers.render_worker", "render_worker"),
    "source_draft": ("app.workers.source_draft_worker", "source_draft_worker"),
    "image": ("app.workers.image_worker", "image_worker"),
    "autopilot": ("app.workers.autopilot_worker", "autopilot_worker"),
    "tts": ("app.workers.tts_worker", "tts_worker"),
}


def _worker_log_path(name: str) -> Path:
    WORKER_LOG_DIR.mkdir(parents=True, exist_ok=True)
    return WORKER_LOG_DIR / f"{name}.log"


def _worker_command(worker_name: str) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--worker", worker_name]
    return [sys.executable, "-m", "app.main", "--worker", worker_name]


def _spawn_worker(worker_name: str) -> None:
    _, log_name = WORKER_ENTRYPOINTS[worker_name]
    creation_flags = 0
    if os.name == "nt":
        creation_flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    log_handle = _worker_log_path(log_name).open("a", encoding="utf-8")
    subprocess.Popen(
        _worker_command(worker_name),
        stdout=log_handle,
        stderr=log_handle,
        stdin=subprocess.DEVNULL,
        creationflags=creation_flags,
        close_fds=os.name != "nt",
    )
    log_handle.close()


def _start_render_worker() -> None:
    _spawn_worker("render")


def _start_source_draft_worker() -> None:
    _spawn_worker("source_draft")


def _start_image_worker() -> None:
    _spawn_worker("image")


def _start_autopilot_worker() -> None:
    _spawn_worker("autopilot")


def _start_tts_worker() -> None:
    _spawn_worker("tts")


def _load_worker_main(worker_name: str) -> Callable[[], int]:
    import importlib

    module_name, _ = WORKER_ENTRYPOINTS[worker_name]
    module = importlib.import_module(module_name)
    main = getattr(module, "main", None)
    if not callable(main):
        raise RuntimeError(f"Worker {worker_name!r} does not expose a callable main().")
    return cast(Callable[[], int], main)


def run_worker(worker_name: str) -> int:
    if worker_name not in WORKER_ENTRYPOINTS:
        valid = ", ".join(sorted(WORKER_ENTRYPOINTS))
        raise ValueError(f"Unknown worker {worker_name!r}. Valid workers: {valid}.")
    return int(_load_worker_main(worker_name)())


def _open_listen_socket(host: str, port: int) -> socket.socket:
    listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listen_socket.bind((host, port))
    listen_socket.listen(2048)
    return listen_socket


def serve_api(host: str = "127.0.0.1", port: int = 9002) -> int:
    import uvicorn

    listen_socket = _open_listen_socket(host, port)
    actual_port = int(listen_socket.getsockname()[1])
    print(f"NEWAUTO_LISTEN_PORT={actual_port}", flush=True)
    config = uvicorn.Config(app, host=host, port=actual_port, log_level="info")
    server = uvicorn.Server(config)
    server.run(sockets=[listen_socket])
    return 0


def _start_render_watchdog() -> None:
    def watch() -> None:
        while True:
            try:
                db.recover_stale_render_jobs(
                    stale_after_sec=RENDER_STALE_AFTER_SEC,
                    max_runtime_sec=RENDER_MAX_RUNTIME_SEC,
                )
                db.recover_stale_source_draft_jobs(
                    stale_after_sec=SOURCE_DRAFT_STALE_AFTER_SEC,
                    max_runtime_sec=SOURCE_DRAFT_MAX_RUNTIME_SEC,
                )
                db.recover_stale_body_image_jobs(
                    stale_after_sec=BODY_IMAGE_STALE_AFTER_SEC,
                    max_runtime_sec=BODY_IMAGE_MAX_RUNTIME_SEC,
                )
                db.recover_stale_tts_jobs(
                    stale_after_sec=TTS_STALE_AFTER_SEC,
                    max_runtime_sec=TTS_MAX_RUNTIME_SEC,
                )
                db.recover_stale_autopilot_jobs(
                    stale_after_sec=AUTOPILOT_STALE_AFTER_SEC,
                    max_runtime_sec=AUTOPILOT_MAX_RUNTIME_SEC,
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
    _start_source_draft_worker()
    _start_image_worker()
    _start_autopilot_worker()
    _start_tts_worker()
    _start_render_watchdog()


app.include_router(projects.router)
app.include_router(autopilot.router)
app.include_router(image_gen.router)
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


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) == 2 and args[0] == "--worker":
        return run_worker(args[1])
    if args and args[0] == "--serve":
        host = "127.0.0.1"
        port = 9002
        index = 1
        while index < len(args):
            option = args[index]
            if option == "--host" and index + 1 < len(args):
                host = args[index + 1]
                index += 2
                continue
            if option == "--port" and index + 1 < len(args):
                try:
                    port = int(args[index + 1])
                except ValueError:
                    print(f"Invalid --port value: {args[index + 1]}", file=sys.stderr)
                    return 2
                index += 2
                continue
            print("Usage: python -m app.main --serve [--host 127.0.0.1] [--port 9002]", file=sys.stderr)
            return 2
        return serve_api(host=host, port=port)
    if args:
        valid = ", ".join(sorted(WORKER_ENTRYPOINTS))
        print(
            f"Usage: python -m app.main --worker {{{valid}}} OR "
            "python -m app.main --serve [--host 127.0.0.1] [--port 9002]",
            file=sys.stderr,
        )
        return 2
    print("Run the API with: python -m app.main --serve --host 127.0.0.1 --port 9002")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
