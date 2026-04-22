import re
from collections.abc import Iterable

_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_READABLE_TEXT_RE = re.compile(r"[^\W_]", re.UNICODE)


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


def split_sentences(script: str) -> list[str]:
    return filter_tts_segments(_SPLIT_RE.split(script or ""))
