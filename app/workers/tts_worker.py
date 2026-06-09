import threading
import time
import hashlib
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import os
import json

from .. import db
from ..config import STORAGE_DIR
from ..services.python_runtime import OmniVoicePythonStatus, resolve_omnivoice_python_with_probes
from ..types import ProjectRecord
from .worker_lock import single_instance_lock

POLL_INTERVAL_SEC = 3.0
HEARTBEAT_INTERVAL_SEC = 10.0
WORKER_LOCK_PATH = STORAGE_DIR / "locks" / "tts_worker.lock"
SUBPROCESS_NOISE_PREFIXES = (
    "Loading weights:",
    "Fetching ",
    "Warning: You are sending unauthenticated requests to the HF Hub.",
)


def _empty_runtime_status(error: str) -> OmniVoicePythonStatus:
    return {
        "resolved": False,
        "python_path": "",
        "omnivoice_import_ok": False,
        "torch_import_ok": False,
        "cuda_available": False,
        "error": error,
    }


def _write_omnivoice_runtime_probe(
    pid: str,
    selected: OmniVoicePythonStatus,
    candidates: list[OmniVoicePythonStatus],
    *,
    final_error: str = "",
) -> None:
    output_dir = db.project_dir(pid) / "tts"
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "project_id": pid,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "selected": selected,
        "selected_python_path": selected["python_path"],
        "final_error": final_error,
        "candidates": candidates,
        "success": final_error == "",
    }
    (output_dir / "omnivoice_runtime_probe.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _clean_subprocess_text(*chunks: str) -> str:
    lines: list[str] = []
    for chunk in chunks:
        for raw_line in str(chunk or "").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if any(line.startswith(prefix) for prefix in SUBPROCESS_NOISE_PREFIXES):
                continue
            lines.append(line)
    return "\n".join(lines).strip()


def _retry_with_sentence_mode(project: ProjectRecord) -> bool:
    profile = project.get("tts_profile")
    if not isinstance(profile, dict):
        return False
    if profile.get("synthesis_mode") != "full_passage":
        return False
    fallback_profile = dict(profile)
    fallback_profile["synthesis_mode"] = "sentence"
    fallback_profile["seed_mode"] = "fixed"
    if not isinstance(fallback_profile.get("seed"), int):
        digest = hashlib.sha256(str(project["id"]).encode("utf-8")).hexdigest()
        fallback_profile["seed"] = int(digest[:8], 16) % 2_147_483_647 or 1
    db.update_project(
        str(project["id"]),
        tts_profile=fallback_profile,
        tts_state="running",
        tts_progress=0,
        tts_error="",
        render_last_log="Retrying TTS with sentence synthesis after full_passage subprocess abort.",
    )
    return True


def _tts_consistency_failed(pid: str) -> bool:
    report_path = db.project_dir(pid) / "tts" / "tts_consistency_report.json"
    if not report_path.exists():
        return False
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        payload.get("audio_consistency_checked") is True
        and payload.get("audio_consistency_passed") is False
    )


def _retry_with_full_passage_after_consistency_failure(project: ProjectRecord) -> bool:
    profile = project.get("tts_profile")
    if not isinstance(profile, dict):
        return False
    if profile.get("synthesis_mode", "sentence") != "sentence":
        return False
    if profile.get("_consistency_retry_attempted") is True:
        return False
    if not _tts_consistency_failed(str(project["id"])):
        return False
    fallback_profile = dict(profile)
    fallback_profile["synthesis_mode"] = "full_passage"
    fallback_profile["seed_mode"] = "fixed"
    fallback_profile["_consistency_retry_attempted"] = True
    db.update_project(
        str(project["id"]),
        tts_profile=fallback_profile,
        tts_state="running",
        tts_progress=0,
        tts_error="",
        render_last_log="Retrying TTS with full_passage synthesis after audio consistency failure.",
    )
    return True


def _run_tts_subprocess(python_exe: str, script_path: Path, pid: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [python_exe, str(script_path), "--project-id", pid],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={
            **os.environ,
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUNBUFFERED": "1",
        },
        check=False,
    )


def _run_job_with_heartbeat(pid: str) -> None:
    stop_event = threading.Event()

    def heartbeat() -> None:
        while not stop_event.wait(HEARTBEAT_INTERVAL_SEC):
            with suppress(Exception):
                db.touch_tts_heartbeat(pid)

    heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
    heartbeat_thread.start()
    selected_runtime = _empty_runtime_status("No usable OmniVoice Python environment found.")
    candidate_statuses: list[OmniVoicePythonStatus] = []
    try:
        try:
            selected_runtime, candidate_statuses = resolve_omnivoice_python_with_probes()
            _write_omnivoice_runtime_probe(pid, selected_runtime, candidate_statuses)
            if not selected_runtime["resolved"] or not selected_runtime["python_path"]:
                raise RuntimeError(selected_runtime["error"] or "No usable OmniVoice Python environment found.")
            python_exe = selected_runtime["python_path"]
        except Exception as exc:
            message = str(exc)
            _write_omnivoice_runtime_probe(pid, selected_runtime, candidate_statuses, final_error=message)
            db.update_project(
                pid,
                tts_state="error",
                tts_progress=0,
                tts_error=message,
                render_last_log=message,
            )
            return
        script_path = Path(__file__).resolve().parents[2] / "scripts" / "run_tts_job.py"
        completed = _run_tts_subprocess(python_exe, script_path, pid)
        project = db.get_project(pid)
        if project is not None and project["tts_state"] != "done" and _retry_with_sentence_mode(project):
            completed = _run_tts_subprocess(python_exe, script_path, pid)
        project = db.get_project(pid)
        if (
            completed.returncode == 0
            and project is not None
            and _retry_with_full_passage_after_consistency_failure(project)
        ):
            completed = _run_tts_subprocess(python_exe, script_path, pid)
        if completed.returncode != 0:
            project = db.get_project(pid)
            if project is not None and project["tts_state"] != "done":
                detail = _clean_subprocess_text(
                    project["tts_error"],
                    completed.stderr,
                    completed.stdout,
                )
                message = detail or f"TTS subprocess failed with return code {completed.returncode}."
                _write_omnivoice_runtime_probe(pid, selected_runtime, candidate_statuses, final_error=message)
                db.update_project(
                    pid,
                    tts_state="error",
                    tts_progress=0,
                    tts_error=message,
                    render_last_log=message,
                )
        else:
            project = db.get_project(pid)
            if project is not None and project["tts_state"] != "done":
                message = "TTS subprocess exited successfully but did not mark the project done."
                _write_omnivoice_runtime_probe(pid, selected_runtime, candidate_statuses, final_error=message)
                db.update_project(
                    pid,
                    tts_state="error",
                    tts_progress=0,
                    tts_error=message,
                    render_last_log=message,
                )
    finally:
        stop_event.set()
        heartbeat_thread.join(timeout=1.0)


def main() -> int:
    db.init_db()
    with single_instance_lock(WORKER_LOCK_PATH) as acquired:
        if not acquired:
            return 0
        while True:
            pid = db.claim_next_queued_tts()
            if pid is None:
                time.sleep(POLL_INTERVAL_SEC)
                continue
            _run_job_with_heartbeat(pid)


if __name__ == "__main__":
    raise SystemExit(main())
