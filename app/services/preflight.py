import shutil
from pathlib import Path

from .. import db
from ..config import CLIENT_SECRET_PATH, PROJECTS_DIR
from ..types import PreflightCheck, PreflightReport, ProjectRecord


def _check(key: str, ok: bool, message: str) -> PreflightCheck:
    return {
        "key": key,
        "ok": ok,
        "message": message,
    }


def _existing_media_count(project: ProjectRecord) -> int:
    media_dir = db.project_dir(project["id"]) / "media"
    return sum(1 for name in project["media_order"] if (media_dir / name).exists())


def build_preflight_report(project: ProjectRecord) -> PreflightReport:
    project_dir = db.project_dir(project["id"])
    timings_path = project_dir / "tts" / "timings.json"
    output_parent = project_dir.parent
    usage = shutil.disk_usage(output_parent if output_parent.exists() else PROJECTS_DIR)
    checks: list[PreflightCheck] = [
        _check(
            "script",
            bool(project["sentences"]),
            "Script has at least one readable sentence." if project["sentences"] else "Save a script with at least one readable sentence first.",
        ),
        _check(
            "tts_state",
            project["tts_state"] == "done",
            "TTS is complete." if project["tts_state"] == "done" else "Run TTS before rendering.",
        ),
        _check(
            "timings",
            timings_path.exists(),
            "timings.json is present." if timings_path.exists() else "timings.json is missing. Re-run TTS.",
        ),
        _check(
            "media",
            bool(project["media_order"]),
            "Media order is populated." if project["media_order"] else "Upload at least one media file.",
        ),
        _check(
            "media_files",
            _existing_media_count(project) == len(project["media_order"]) and bool(project["media_order"]),
            "All referenced media files exist." if _existing_media_count(project) == len(project["media_order"]) and project["media_order"] else "Some media files are missing on disk.",
        ),
        _check(
            "ffmpeg",
            shutil.which("ffmpeg") is not None,
            "FFmpeg is available on PATH." if shutil.which("ffmpeg") is not None else "FFmpeg is missing from PATH.",
        ),
        _check(
            "disk_space",
            usage.free >= 500 * 1024 * 1024,
            f"Free disk space is {usage.free / (1024 ** 3):.1f} GB." if usage.free >= 500 * 1024 * 1024 else "At least 0.5 GB of free disk space is recommended.",
        ),
        _check(
            "oauth",
            CLIENT_SECRET_PATH.exists(),
            "OAuth client secret is present." if CLIENT_SECRET_PATH.exists() else "OAuth client secret is missing.",
        ),
    ]
    return {
        "ok": all(check["ok"] for check in checks),
        "checks": checks,
    }
