from __future__ import annotations

import time

from .. import db
from ..config import STORAGE_DIR
from ..services.image_generation_disabled import IMAGE_GEN_DISABLED_CODE, IMAGE_GEN_DISABLED_MESSAGE
from .worker_lock import single_instance_lock

POLL_INTERVAL_SEC = 3.0
WORKER_LOCK_PATH = STORAGE_DIR / "locks" / "image_worker.lock"


def _mark_disabled(pid: str) -> None:
    db.update_project(
        pid,
        body_image_state="error",
        body_image_progress=0,
        body_image_error=IMAGE_GEN_DISABLED_CODE,
        body_image_phase="disabled",
        body_image_last_log=IMAGE_GEN_DISABLED_MESSAGE,
        body_image_job_id="",
        body_image_started_at="",
        body_image_heartbeat_at="",
    )


def _mark_stale_jobs_disabled() -> None:
    for project in db.list_projects():
        if project["body_image_state"] in {"queued", "running"}:
            _mark_disabled(project["id"])


def main() -> int:
    db.init_db()
    with single_instance_lock(WORKER_LOCK_PATH) as acquired:
        if not acquired:
            return 0
        _mark_stale_jobs_disabled()
        while True:
            pid = db.claim_next_queued_body_image()
            if pid is None:
                time.sleep(POLL_INTERVAL_SEC)
                continue
            _mark_disabled(pid)
