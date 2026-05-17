import threading
import time
from contextlib import suppress
from pathlib import Path
from typing import cast

from .. import db
from ..config import STORAGE_DIR
from ..services import gpu_guard
from ..services.hpsl_script import generate_hpsl_draft, save_hpsl_payload
from ..services.source_draft import generate_script_draft
from .worker_lock import single_instance_lock

POLL_INTERVAL_SEC = 3.0
HEARTBEAT_INTERVAL_SEC = 10.0
WORKER_LOCK_PATH = STORAGE_DIR / "locks" / "source_draft_worker.lock"
LLM_RESOURCE = "lmstudio"


def _parse_target_minutes(value: object) -> int | None:
    if value in {None, "", "auto"}:
        return None
    try:
        parsed = int(cast(str | bytes | bytearray, value))
    except (TypeError, ValueError):
        return None
    return max(1, min(parsed, 15))


def _run_job_with_heartbeat(pid: str) -> None:
    stop_event = threading.Event()
    gpu_owner = f"source-draft:{pid}"

    def heartbeat() -> None:
        while not stop_event.wait(HEARTBEAT_INTERVAL_SEC):
            with suppress(Exception):
                db.touch_source_draft_heartbeat(pid)

    heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
    heartbeat_thread.start()

    def _release_stale_legacy_source_lock() -> bool:
        status = gpu_guard.get_status()
        if not status["locked"] or status["resource"] != "ollama":
            return True
        owner = status["owner"]
        if not owner.startswith("source-draft:"):
            return True
        if status["stale"]:
            gpu_guard.release(owner)
            return True
        return False

    try:
        project = db.get_project(pid)
        if project is None:
            return
        options = project["source_draft_options"]
        tone = str(options.get("tone") or "설명형")
        target_minutes = _parse_target_minutes(options.get("target_minutes", "auto"))
        language = str(options.get("language") or "ko")
        script_structure = str(options.get("script_structure") or "standard").strip().lower()
        while True:
            if not _release_stale_legacy_source_lock():
                owner = gpu_guard.current_owner()
                db.update_project(
                    pid,
                    source_draft_phase="wait_gpu",
                    source_draft_progress=15,
                    source_draft_last_log=(
                        f"Waiting for legacy source-draft GPU guard lock release ({owner or 'unknown owner'})."
                    ),
                )
                if stop_event.wait(2.0):
                    return
                continue
            if gpu_guard.acquire(LLM_RESOURCE, gpu_owner, timeout_sec=900):
                break
            owner = gpu_guard.current_owner()
            db.update_project(
                pid,
                source_draft_phase="wait_gpu",
                source_draft_progress=15,
                source_draft_last_log=(
                    f"Waiting for GPU to become available ({owner or 'unknown owner'})."
                ),
            )
            if stop_event.wait(2.0):
                return
        db.update_project(
            pid,
            source_draft_phase="generate",
            source_draft_progress=40,
            source_draft_last_log="Generating source draft with LLM provider...",
        )
        if script_structure == "hpsl":
            hpsl_generated = generate_hpsl_draft(
                project,
                tone=tone,
                target_minutes=target_minutes,
                language=language,
            )
            save_hpsl_payload(pid, hpsl_generated.payload)
            script = hpsl_generated.script
            previous_script = hpsl_generated.previous_script
            warnings = hpsl_generated.warnings
            model = hpsl_generated.model
            risk_score = hpsl_generated.risk_score
        else:
            source_generated = generate_script_draft(
                project,
                tone=tone,
                target_minutes=target_minutes,
                language=language,
                mode=project["source_draft_regenerate_mode"],
                note=project["source_draft_regenerate_note"],
            )
            script = source_generated.script
            previous_script = source_generated.previous_script
            warnings = source_generated.warnings
            model = source_generated.model
            risk_score = source_generated.risk_score
        db.update_project(
            pid,
            source_draft_state="done",
            source_draft_progress=100,
            source_draft_error="",
            source_draft_script=script,
            source_draft_previous_script=previous_script,
            source_draft_warnings=warnings,
            source_draft_model=model,
            source_draft_risk_score=risk_score,
            source_draft_regenerate_mode=project["source_draft_regenerate_mode"],
            source_draft_phase="done",
            source_draft_last_log="",
        )
    except Exception as exc:
        db.update_project(
            pid,
            source_draft_state="error",
            source_draft_progress=0,
            source_draft_error=str(exc),
            source_draft_phase="",
            source_draft_last_log=str(exc)[:500],
        )
    finally:
        gpu_guard.release(gpu_owner)
        stop_event.set()
        heartbeat_thread.join(timeout=1.0)


def main() -> int:
    db.init_db()
    with single_instance_lock(WORKER_LOCK_PATH) as acquired:
        if not acquired:
            return 0
        while True:
            pid = db.claim_next_queued_source_draft()
            if pid is None:
                time.sleep(POLL_INTERVAL_SEC)
                continue
            _run_job_with_heartbeat(pid)


if __name__ == "__main__":
    raise SystemExit(main())
