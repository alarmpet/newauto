import json
import os
import ctypes
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..config import GPU_GUARD_PATH
from ..types import GpuStatus


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _empty_status() -> GpuStatus:
    return {
        "locked": False,
        "owner": "",
        "resource": "",
        "expires_at": "",
        "owner_pid": 0,
        "owner_project_id": "",
        "owner_job_type": "",
        "stale": False,
    }


def _pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x00100000, False, pid)
        if not handle:
            return False
        kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
    except (OSError, SystemError):
        return False
    return True


def _parse_owner_metadata(owner: str) -> tuple[str, str]:
    normalized = owner.strip()
    if ":" not in normalized:
        return normalized, ""
    job_type, project_id = normalized.split(":", 1)
    return job_type.strip(), project_id.strip()


def _read_status(path: Path = GPU_GUARD_PATH, *, preserve_stale: bool = False) -> GpuStatus:
    if not path.exists():
        return _empty_status()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_status()
    if not isinstance(payload, dict):
        return _empty_status()
    locked = payload.get("locked")
    owner = payload.get("owner")
    resource = payload.get("resource")
    expires_at = payload.get("expires_at")
    owner_pid = payload.get("owner_pid", 0)
    owner_project_id = payload.get("owner_project_id", "")
    owner_job_type = payload.get("owner_job_type", "")
    if (
        not isinstance(locked, bool)
        or not isinstance(owner, str)
        or not isinstance(resource, str)
        or not isinstance(expires_at, str)
        or not isinstance(owner_pid, int)
        or not isinstance(owner_project_id, str)
        or not isinstance(owner_job_type, str)
    ):
        return _empty_status()
    if not locked or not expires_at:
        return _empty_status()
    try:
        expires_dt = datetime.fromisoformat(expires_at)
    except ValueError:
        return _empty_status()
    expires_dt = expires_dt.astimezone(timezone.utc)
    if expires_dt <= _now():
        return _empty_status()
    parsed_job_type, parsed_project_id = _parse_owner_metadata(owner)
    normalized_job_type = owner_job_type or parsed_job_type
    normalized_project_id = owner_project_id or parsed_project_id
    stale = owner_pid > 0 and not _pid_exists(owner_pid)
    if stale and not preserve_stale:
        with suppress(OSError):
            path.unlink(missing_ok=True)
        return _empty_status()
    return {
        "locked": True,
        "owner": owner,
        "resource": resource,
        "expires_at": expires_dt.isoformat(timespec="seconds"),
        "owner_pid": owner_pid,
        "owner_project_id": normalized_project_id,
        "owner_job_type": normalized_job_type,
        "stale": stale,
    }


def _write_status(status: GpuStatus, path: Path = GPU_GUARD_PATH) -> None:
    if not status["locked"]:
        if path.exists():
            path.unlink()
        return
    path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")


def acquire(resource: str, owner: str, timeout_sec: int = 900, path: Path = GPU_GUARD_PATH) -> bool:
    status = _read_status(path)
    if status["locked"] and status["owner"] != owner:
        return False
    owner_job_type, owner_project_id = _parse_owner_metadata(owner)
    expires_at = (_now() + timedelta(seconds=max(timeout_sec, 1))).isoformat(timespec="seconds")
    _write_status(
        {
            "locked": True,
            "owner": owner,
            "resource": resource,
            "expires_at": expires_at,
            "owner_pid": os.getpid(),
            "owner_project_id": owner_project_id,
            "owner_job_type": owner_job_type,
            "stale": False,
        },
        path,
    )
    return True


def release(owner: str, path: Path = GPU_GUARD_PATH) -> bool:
    status = _read_status(path)
    if not status["locked"]:
        return True
    if status["owner"] != owner:
        return False
    _write_status(_empty_status(), path)
    return True


def current_owner(path: Path = GPU_GUARD_PATH) -> str:
    return _read_status(path)["owner"]


def get_status(path: Path = GPU_GUARD_PATH) -> GpuStatus:
    return _read_status(path, preserve_stale=True)
