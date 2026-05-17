import logging
import os
import sys
import tempfile
from pathlib import Path

from .tts_profiles import VOICE_PRESET_LABELS, VOICE_PRESETS, VOICE_SAMPLE_TEXT

ROOT_DIR = Path(__file__).resolve().parent.parent


def _default_data_dir() -> Path:
    configured = os.getenv("NEWAUTO_DATA_DIR", "").strip()
    if configured:
        return Path(configured).expanduser()
    if getattr(sys, "frozen", False):
        local_app_data = os.getenv("LOCALAPPDATA", "").strip()
        if local_app_data:
            return Path(local_app_data) / "newauto Studio"
        return Path(tempfile.gettempdir()) / "newauto Studio"
    return ROOT_DIR / "storage"


STORAGE_DIR = _default_data_dir()
USAGE_DIR = STORAGE_DIR / "usage"
PROVIDER_USAGE_PATH = USAGE_DIR / "providers.json"
PROJECTS_DIR = STORAGE_DIR / "projects"
OAUTH_DIR = STORAGE_DIR / "oauth"
DB_PATH = STORAGE_DIR / "app.db"
STATIC_DIR = ROOT_DIR / "app" / "static"
WORKFLOW_TEMPLATES_DIR = ROOT_DIR / "app" / "workflow_templates"
COMFYUI_WORKFLOW_DIR = WORKFLOW_TEMPLATES_DIR / "comfyui"
VOICE_SAMPLES_DIR = STORAGE_DIR / "voice_samples"
SOURCE_CACHE_DIR = STORAGE_DIR / "source_cache"

CLIENT_SECRET_PATH = OAUTH_DIR / "client_secret.json"
TOKEN_PATH = OAUTH_DIR / "token.json"
STOCK_CACHE_DIR = STORAGE_DIR / "stock_cache"

VIDEO_W, VIDEO_H, FPS = 1920, 1080, 30
SHORTS_W, SHORTS_H = 1080, 1920
SAMPLE_RATE = 24000

ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_VIDEO_EXT = {".mp4", ".mov", ".webm"}
ALLOWED_AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac"}
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "")
_LOGGER = logging.getLogger(__name__)


def _normalize_llm_provider(raw: str | None) -> str:
    normalized = (raw or "").strip().lower()
    if normalized == "ollama":
        return "ollama"
    if normalized in {"", "lmstudio"}:
        return "lmstudio"
    _LOGGER.warning("Unsupported LLM_PROVIDER=%r; falling back to 'lmstudio'.", raw)
    return "lmstudio"


_OLLAMA_BASE_URL_ENV = os.getenv("OLLAMA_BASE_URL")
_LMSTUDIO_BASE_URL_ENV = os.getenv("LMSTUDIO_BASE_URL")
LLM_PROVIDER = _normalize_llm_provider(os.getenv("LLM_PROVIDER"))
OLLAMA_BASE_URL = _OLLAMA_BASE_URL_ENV.strip() if _OLLAMA_BASE_URL_ENV and _OLLAMA_BASE_URL_ENV.strip() else "http://127.0.0.1:11434"

if LLM_PROVIDER == "lmstudio":
    if _LMSTUDIO_BASE_URL_ENV and _LMSTUDIO_BASE_URL_ENV.strip():
        LMSTUDIO_BASE_URL = _LMSTUDIO_BASE_URL_ENV.strip()
    elif _OLLAMA_BASE_URL_ENV and _OLLAMA_BASE_URL_ENV.strip():
        _LOGGER.warning(
            "LLM_PROVIDER=lmstudio is set, but LMSTUDIO_BASE_URL is missing. "
            "Falling back to OLLAMA_BASE_URL for compatibility."
        )
        LMSTUDIO_BASE_URL = _OLLAMA_BASE_URL_ENV.strip()
    else:
        LMSTUDIO_BASE_URL = "http://127.0.0.1:1234"
else:
    LMSTUDIO_BASE_URL = _LMSTUDIO_BASE_URL_ENV.strip() if _LMSTUDIO_BASE_URL_ENV and _LMSTUDIO_BASE_URL_ENV.strip() else "http://127.0.0.1:1234"
SCRIPT_LLM_MODEL = (os.getenv("SCRIPT_LLM_MODEL") or "google/gemma-4-e4b").strip() or "google/gemma-4-e4b"
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "")
BRAVE_FREE_MONTHLY_LIMIT = int(os.getenv("BRAVE_FREE_MONTHLY_LIMIT", "1000"))
BRAVE_USAGE_PATH = STORAGE_DIR / "brave_usage.json"
COMFYUI_BASE_URL = os.getenv("COMFYUI_BASE_URL", "http://127.0.0.1:8188")
COMFYUI_ENABLED = os.getenv("COMFYUI_ENABLED", "0") == "1"
COMFYUI_INSTALL_DIR = Path(os.getenv("COMFYUI_INSTALL_DIR", r"C:\Users\petbl\autotube\ComfyUI"))
SOURCE_RESEARCH_CACHE_DIR = STORAGE_DIR / "source_research_cache"
GPU_GUARD_PATH = STORAGE_DIR / "gpu_guard.json"

for d in (
    STORAGE_DIR,
    USAGE_DIR,
    PROJECTS_DIR,
    OAUTH_DIR,
    VOICE_SAMPLES_DIR,
    SOURCE_CACHE_DIR,
    SOURCE_RESEARCH_CACHE_DIR,
    WORKFLOW_TEMPLATES_DIR,
    COMFYUI_WORKFLOW_DIR,
):
    d.mkdir(parents=True, exist_ok=True)
STOCK_CACHE_DIR.mkdir(parents=True, exist_ok=True)
