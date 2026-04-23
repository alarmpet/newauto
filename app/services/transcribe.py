import json
from pathlib import Path

from ..types import TimingEntry, WordTimingEntry


def _load_model() -> object:
    from faster_whisper import WhisperModel  # noqa: WPS433

    return WhisperModel("small", device="auto", compute_type="int8")


def _split_word_entries(
    cue_idx: int,
    cue_start: float,
    cue_end: float,
    text: str,
) -> list[WordTimingEntry]:
    words = [word for word in text.split() if word]
    if not words:
        return []
    duration = max(0.01, cue_end - cue_start)
    per_word = duration / len(words)
    entries: list[WordTimingEntry] = []
    cursor = cue_start
    for index, word in enumerate(words):
        end = cue_end if index == len(words) - 1 else round(cursor + per_word, 3)
        entries.append(
            {
                "cue_idx": cue_idx,
                "word": word,
                "start": round(cursor, 3),
                "end": round(end, 3),
            }
        )
        cursor = end
    return entries


def build_word_timings(timings: list[TimingEntry]) -> list[WordTimingEntry]:
    try:
        _load_model()
    except Exception:
        word_timings: list[WordTimingEntry] = []
        for timing in timings:
            word_timings.extend(
                _split_word_entries(
                    timing["idx"],
                    timing["start"],
                    timing["end"],
                    timing["text"],
                )
            )
        return word_timings

    word_timings = []
    for timing in timings:
        word_timings.extend(
            _split_word_entries(
                timing["idx"],
                timing["start"],
                timing["end"],
                timing["text"],
            )
        )
    return word_timings


def save_word_timings(output_path: Path, timings: list[TimingEntry]) -> list[WordTimingEntry]:
    word_timings = build_word_timings(timings)
    output_path.write_text(
        json.dumps(word_timings, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return word_timings
