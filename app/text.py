import re
from collections.abc import Iterable

_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_READABLE_TEXT_RE = re.compile(r"[^\W_]", re.UNICODE)
_KOREAN_THEN_LATIN_PAREN_RE = re.compile(
    r"(?<=[가-힣])\s*\(([A-Za-z][A-Za-z0-9 .,&+\-'/]*)\)"
)


def is_tts_readable_text(text: str) -> bool:
    stripped = text.strip()
    return bool(stripped) and _READABLE_TEXT_RE.search(stripped) is not None


def filter_tts_segments(parts: Iterable[str]) -> list[str]:
    cleaned: list[str] = []
    for part in parts:
        stripped = part.strip()
        if is_tts_readable_text(stripped):
            cleaned.append(stripped)
    return cleaned


def normalize_tts_reading_text(text: str) -> str:
    """Remove English aliases in parentheses after Korean words for cleaner Korean TTS."""
    cleaned = _KOREAN_THEN_LATIN_PAREN_RE.sub("", text or "")
    return re.sub(r"\s{2,}", " ", cleaned).strip()


def split_sentences(script: str) -> list[str]:
    return filter_tts_segments(_SPLIT_RE.split(script or ""))
