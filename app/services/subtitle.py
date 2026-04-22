from pathlib import Path

from ..types import TimingEntry


def _fmt_ts(sec: float) -> str:
    hours = int(sec // 3600)
    minutes = int((sec % 3600) // 60)
    seconds = int(sec % 60)
    milliseconds = int(round((sec - int(sec)) * 1000))
    if milliseconds == 1000:
        milliseconds, seconds = 0, seconds + 1
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def _wrap_long(text: str, max_len: int = 40) -> str:
    if len(text) <= max_len:
        return text
    punctuation_positions = [index for index, char in enumerate(text) if char in ",.?!"]
    if punctuation_positions:
        midpoint = len(text) // 2
        split_index = min(punctuation_positions, key=lambda index: abs(index - midpoint))
        return text[: split_index + 1].strip() + "\n" + text[split_index + 1 :].strip()
    midpoint = len(text) // 2
    return text[:midpoint].strip() + "\n" + text[midpoint:].strip()


def write_srt(timings: list[TimingEntry], out_path: Path) -> Path:
    lines: list[str] = []
    for index, timing in enumerate(timings, start=1):
        lines.append(str(index))
        lines.append(f"{_fmt_ts(timing['start'])} --> {_fmt_ts(timing['end'])}")
        lines.append(_wrap_long(timing["text"]))
        lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path
