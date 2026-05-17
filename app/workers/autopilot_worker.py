import threading
import time
from contextlib import suppress
from pathlib import Path

from .. import db
from ..config import STORAGE_DIR
from ..services.autopilot import run_autopilot_job
from .worker_lock import single_instance_lock

POLL_INTERVAL_SEC = 3.0
HEARTBEAT_INTERVAL_SEC = 10.0
WORKER_LOCK_PATH = STORAGE_DIR / "locks" / "autopilot_worker.lock"


def _run_job_with_heartbeat(pid: str) -> None:
    stop_event = threading.Event()

    def heartbeat() -> None:
        while not stop_event.wait(HEARTBEAT_INTERVAL_SEC):
            with suppress(Exception):
                db.touch_autopilot_heartbeat(pid)

    heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
    heartbeat_thread.start()
    try:
        run_autopilot_job(pid)
    finally:
        stop_event.set()
        heartbeat_thread.join(timeout=1.0)


def main() -> int:
    db.init_db()
    with single_instance_lock(WORKER_LOCK_PATH) as acquired:
        if not acquired:
            return 0
        while True:
            pid = db.claim_next_queued_autopilot()
            if pid is None:
                time.sleep(POLL_INTERVAL_SEC)
                continue
            _run_job_with_heartbeat(pid)


if __name__ == "__main__":
    raise SystemExit(main())
