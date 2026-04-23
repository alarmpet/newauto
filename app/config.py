from pathlib import Path
import os

from .types import VoicePresetArg

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

VOICE_SAMPLE_TEXT = (
    "안녕하세요. 지금 들으시는 음성은 OmniVoice 남성 프리셋 비교용 샘플입니다. "
    "발음, 톤, 속도, 안정감을 함께 확인해 주세요."
)

VOICE_PRESETS: dict[str, dict[str, VoicePresetArg]] = {
    "auto": {},
    "male-calm": {"gender": "male", "age": "adult", "pitch": "low"},
    "female-bright": {"gender": "female", "age": "adult", "pitch": "high"},
    "narrator": {"gender": "male", "age": "adult", "pitch": "medium"},
    "male-30s-40s-lowmid": {
        "gender": "male",
        "age": "adult",
        "pitch": "low",
        "instruct": "male, young adult, low pitch, korean accent",
    },
    "male-40s-50s-lowmid": {
        "gender": "male",
        "age": "adult",
        "pitch": "low",
        "instruct": "male, middle-aged, low pitch, korean accent",
    },
    "male-announcer-30s-40s": {
        "gender": "male",
        "age": "adult",
        "pitch": "medium",
        "speed": 1.02,
        "instruct": "male, young adult, moderate pitch, korean accent",
    },
    "male-low-30s-40s": {
        "gender": "male",
        "age": "adult",
        "pitch": "low",
        "speed": 0.97,
        "instruct": "male, young adult, very low pitch, korean accent",
    },
    "male-pastor-30s-40s": {
        "gender": "male",
        "age": "adult",
        "pitch": "low",
        "speed": 0.94,
        "instruct": "male, middle-aged, low pitch, korean accent",
    },
}

VOICE_PRESET_LABELS: dict[str, str] = {
    "auto": "Auto",
    "male-calm": "기본 남성 차분한 음성",
    "female-bright": "기본 여성 밝은 음성",
    "narrator": "기본 남성 내레이터",
    "male-30s-40s-lowmid": "30~40대 중저음 남성",
    "male-40s-50s-lowmid": "40~50대 중저음 남성",
    "male-announcer-30s-40s": "30~40대 남성 아나운서",
    "male-low-30s-40s": "30~40대 남성 저음",
    "male-pastor-30s-40s": "30~40대 남성 목사님",
}

for d in (STORAGE_DIR, PROJECTS_DIR, OAUTH_DIR, VOICE_SAMPLES_DIR):
    d.mkdir(parents=True, exist_ok=True)
STOCK_CACHE_DIR.mkdir(parents=True, exist_ok=True)
