import re

from .pipeline_manifest import text_hash
from .text_health import looks_mojibake
from ..text import split_sentences
from ..types import ContentMode, Region, RegionalSentence, SelectedVerse

_REGION_MARKER_RE = re.compile(r"^\s*<<\s*(intro|body|bible)\s*>>\s*$", re.IGNORECASE)


def _normalize_region(value: str) -> Region:
    normalized = value.strip().lower()
    if normalized == "intro":
        return "intro"
    if normalized == "bible":
        return "bible"
    return "body"


def _regionalize(script: str, default_region: Region = "body") -> list[RegionalSentence]:
    region = default_region
    sentences: list[RegionalSentence] = []
    pending_lines: list[str] = []

    def flush() -> None:
        nonlocal pending_lines
        chunk = "\n".join(pending_lines).strip()
        pending_lines = []
        if not chunk:
            return
        for text in split_sentences(chunk):
            normalized_text = text.strip()
            sentences.append(
                {
                    "idx": len(sentences),
                    "text": normalized_text,
                    "region": region,
                    "original_text": text,
                    "normalized_text": normalized_text,
                    "text_hash": text_hash(normalized_text),
                    "source_marker": region,
                }
            )

    if looks_mojibake(script or ""):
        raise ValueError("script contains mojibake text")
    for line in (script or "").splitlines():
        marker = _REGION_MARKER_RE.match(line)
        if marker is None:
            pending_lines.append(line)
            continue
        flush()
        region = _normalize_region(marker.group(1))
    flush()
    return sentences


def flatten_regional_sentences(regional_sentences: list[RegionalSentence]) -> list[str]:
    return [sentence["text"] for sentence in regional_sentences]


def compile_standard_script(script: str) -> tuple[str, list[RegionalSentence]]:
    compiled_script = script or ""
    return compiled_script, _regionalize(compiled_script, default_region="body")


def format_selected_verses(selected_verses: list[SelectedVerse]) -> str:
    lines: list[str] = []
    for verse in selected_verses:
        reference = verse["reference"].strip()
        text = verse["text"].strip()
        if not text:
            continue
        lines.append(f"{reference} {text}".strip())
    return "\n".join(lines)


def compile_bible_longform_script(
    user_script: str,
    selected_verses: list[SelectedVerse] | None = None,
) -> tuple[str, list[RegionalSentence]]:
    verses_text = format_selected_verses(selected_verses or [])
    source = user_script or ""
    has_bible_marker = False
    for line in source.splitlines():
        marker = _REGION_MARKER_RE.match(line)
        if marker is not None and _normalize_region(marker.group(1)) == "bible":
            has_bible_marker = True
            break
    if verses_text and not has_bible_marker:
        source = f"{source.rstrip()}\n\n<<bible>>\n{verses_text}\n"
    compiled_script = source
    return compiled_script, _regionalize(compiled_script, default_region="body")


def compile_script(
    content_mode: ContentMode,
    user_script: str,
    selected_verses: list[SelectedVerse] | None = None,
) -> tuple[str, list[RegionalSentence]]:
    if content_mode == "bible_longform":
        return compile_bible_longform_script(user_script, selected_verses)
    return compile_standard_script(user_script)
