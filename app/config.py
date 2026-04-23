import os
from pathlib import Path

from .tts_profiles import VOICE_PRESET_LABELS, VOICE_PRESETS, VOICE_SAMPLE_TEXT

ROOT_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = ROOT_DIR / "storage"
PROJECTS_DIR = STORAGE_DIR / "projects"
OAUTH_DIR = STORAGE_DIR / "oauth"
DB_PATH = STORAGE_DIR / "app.db"
STATIC_DIR = ROOT_DIR / "app" / "static"
VOICE_SAMPLES_DIR = STORAGE_DIR / "voice_samples"

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

for d in (STORAGE_DIR, PROJECTS_DIR, OAUTH_DIR, VOICE_SAMPLES_DIR):
    d.mkdir(parents=True, exist_ok=True)
STOCK_CACHE_DIR.mkdir(parents=True, exist_ok=True)
