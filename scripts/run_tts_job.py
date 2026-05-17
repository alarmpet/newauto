from __future__ import annotations

import argparse
import os
import subprocess
import sys
import traceback
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import db
from app.services.python_runtime import resolve_omnivoice_python
from app.services.tts import run_tts_job, write_tts_error


def _same_executable(left: str, right: str) -> bool:
    try:
        return Path(left).resolve() == Path(right).resolve()
    except OSError:
        return left.lower() == right.lower()


def _tts_outputs_complete(pid: str) -> bool:
    project = db.get_project(pid)
    output_dir = db.project_dir(pid) / "tts"
    return bool(
        project is not None
        and project["tts_state"] == "done"
        and int(project["tts_progress"]) == 100
        and (output_dir / "tts_run_manifest.json").exists()
        and (output_dir / "timings.json").exists()
        and any(output_dir.glob("*.wav"))
    )


def _delegate_to_omnivoice_python_if_needed(pid: str) -> int | None:
    if os.environ.get("NEWAUTO_TTS_BOOTSTRAPPED") == "1":
        return None
    try:
        python_exe = resolve_omnivoice_python()
    except Exception:
        return None
    if _same_executable(sys.executable, python_exe):
        return None
    try:
        completed = subprocess.run(
            [python_exe, str(Path(__file__).resolve()), *sys.argv[1:]],
            env={
                **os.environ,
                "NEWAUTO_TTS_BOOTSTRAPPED": "1",
                "PYTHONIOENCODING": "utf-8",
                "PYTHONUNBUFFERED": "1",
            },
            check=False,
        )
    except KeyboardInterrupt:
        if _tts_outputs_complete(pid):
            return 0
        raise
    if completed.returncode != 0 and _tts_outputs_complete(pid):
        return 0
    return int(completed.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a TTS job for a project.")
    parser.add_argument("--project-id", required=True)
    args = parser.parse_args()
    pid = str(args.project_id)
    db.init_db()
    if _tts_outputs_complete(pid):
        return 0
    delegated_returncode = _delegate_to_omnivoice_python_if_needed(pid)
    if delegated_returncode is not None:
        return delegated_returncode
    try:
        run_tts_job(pid)
        project = db.get_project(pid)
        if project is None:
            return 1
        if project["tts_state"] != "done":
            message = project["tts_error"] or "TTS job did not complete successfully."
            write_tts_error(pid, message)
            return 1
        return 0
    except Exception as exc:
        traceback_text = traceback.format_exc()
        print(traceback_text)
        write_tts_error(pid, str(exc), traceback_text)
        db.update_project(
            pid,
            tts_state="error",
            tts_progress=0,
            tts_error=str(exc),
            render_last_log=str(exc),
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
