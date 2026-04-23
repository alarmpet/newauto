import shutil

from ..config import CLIENT_SECRET_PATH, PROJECTS_DIR
from ..types import SystemHealth


def get_system_health() -> SystemHealth:
    usage = shutil.disk_usage(PROJECTS_DIR)
    omnivoice_python = shutil.which("python") is not None
    return {
        "ffmpeg_available": shutil.which("ffmpeg") is not None,
        "oauth_ready": CLIENT_SECRET_PATH.exists(),
        "omnivoice_python_found": omnivoice_python,
        "disk_free_gb": round(usage.free / (1024 ** 3), 2),
        "storage_path": str(PROJECTS_DIR),
    }
