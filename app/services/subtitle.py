from pathlib import Path
import re
from typing import cast

from ..types import SubtitleCueSplitMode, SubtitleEffect, SubtitlePosition, SubtitleStyle, TimingEntry, WordTimingEntry

DEFAULT_SUBTITLE_STYLE: SubtitleStyle = {
    "font_family": "Malgun Gothic",
    "font_size": 48,
    "primary_color": "#FFFFFF",
    "outline_color": "#000000",
    "background_color": "#000000",
    "background_opacity": 0.0,
    "outline_width": 2,
    "shadow": 1,
    "position": "bottom",
    "margin_h": 120,
    "margin_v": 80,
    "max_line_chars": 26,
    "min_display_sec": 1.0,
    "cue_split_mode": "sentence",
    "max_cue_sec": 3.5,
    "max_lines": 2,
    "effect": "none",
}

SHORTS_SUBTITLE_OVERRIDES: dict[str, object] = {
    "font_size": 52,
    "position": "bottom",
    "margin_h": 72,
    "margin_v": 116,
    "max_line_chars": 16,
    "min_display_sec": 0.5,
    "cue_split_mode": "readable",
    "max_cue_sec": 2.6,
    "max_lines": 1,
    "outline_width": 3,
    "shadow": 1,
}

_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
_POSITION_VALUES: set[SubtitlePosition] = {"top", "upper", "middle", "lower", "bottom"}
_EFFECT_VALUES: set[SubtitleEffect] = {"none", "fade", "pop", "karaoke"}
PLAY_RES_X = 1920
PLAY_RES_Y = 1080
READABLE_MIN_DISPLAY_SEC = 0.3
READABLE_PUNCTUATION = set(".,!?;:")
WORD_TEXT_SANITIZE_RE = re.compile(r"[\W_]+", flags=re.UNICODE)
POSITION_CENTER_RATIO: dict[SubtitlePosition, float] = {
    "top": 0.12,
    "upper": 0.30,
    "middle": 0.50,
    "lower": 0.78,
    "bottom": 0.88,
}


def _fmt_ts(sec: float) -> str:
    hours = int(sec // 3600)
    minutes = int((sec % 3600) // 60)
    seconds = int(sec % 60)
    milliseconds = int(round((sec - int(sec)) * 1000))
    if milliseconds == 1000:
        milliseconds, seconds = 0, seconds + 1
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def _find_break_backward(text: str, max_len: int) -> int:
    if len(text) <= max_len:
        return len(text)
    upper = min(max_len, len(text) - 1)
    for chars in (".!?", ",;:", " "):
        for index in range(upper, 0, -1):
            if text[index - 1] in chars:
                return index
    return upper


def _smart_wrap(text: str, max_len: int = 26) -> str:
    normalized = " ".join(text.strip().split())
    if len(normalized) <= max_len:
        return normalized
    first_split = _find_break_backward(normalized, max_len)
    first_line = normalized[:first_split].rstrip()
    remainder = normalized[first_split:].lstrip(" ,;:")
    if not first_line or not remainder:
        midpoint = min(max_len, max(1, len(normalized) // 2))
        first_line = normalized[:midpoint].rstrip()
        remainder = normalized[midpoint:].lstrip()
    if len(remainder) <= max_len:
        return f"{first_line}\n{remainder}"

    second_split = _find_break_backward(remainder, max_len)
    second_left = remainder[:second_split].rstrip()
    second_right = remainder[second_split:].lstrip(" ,;:")
    merged_second_line = f"{second_left} {second_right}".strip() if second_right else second_left
    if not merged_second_line:
        merged_second_line = remainder
    return f"{first_line}\n{merged_second_line}"


def _coerce_int(value: object, default: int, min_value: int, max_value: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return max(min_value, min(max_value, int(value)))
    if isinstance(value, str):
        try:
            return max(min_value, min(max_value, int(value)))
        except ValueError:
            return default
    return default


def _coerce_float(value: object, default: float, min_value: float, max_value: float) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return max(min_value, min(max_value, float(value)))
    if isinstance(value, str):
        try:
            return max(min_value, min(max_value, float(value)))
        except ValueError:
            return default
    return default


def _coerce_color(value: object, default: str) -> str:
    if isinstance(value, str) and _HEX_COLOR_RE.fullmatch(value):
        return value.upper()
    return default


def _coerce_position(value: object, default: SubtitlePosition) -> SubtitlePosition:
    if isinstance(value, str) and value in _POSITION_VALUES:
        return value
    return default


def _coerce_effect(value: object, default: SubtitleEffect) -> SubtitleEffect:
    if isinstance(value, str) and value in _EFFECT_VALUES:
        return value
    return default


def _coerce_cue_split_mode(value: object, default: SubtitleCueSplitMode) -> SubtitleCueSplitMode:
    if isinstance(value, str) and value in {"off", "sentence", "readable"}:
        return cast(SubtitleCueSplitMode, value)
    return default


def normalize_subtitle_style(style: dict[str, object] | SubtitleStyle | None) -> SubtitleStyle:
    source: dict[str, object] = dict(style or {})
    defaults = DEFAULT_SUBTITLE_STYLE
    return {
        "font_family": str(source.get("font_family") or defaults["font_family"])[:80],
        "font_size": _coerce_int(source.get("font_size"), defaults["font_size"], 24, 96),
        "primary_color": _coerce_color(source.get("primary_color"), defaults["primary_color"]),
        "outline_color": _coerce_color(source.get("outline_color"), defaults["outline_color"]),
        "background_color": _coerce_color(source.get("background_color"), defaults["background_color"]),
        "background_opacity": _coerce_float(
            source.get("background_opacity"),
            defaults["background_opacity"],
            0.0,
            1.0,
        ),
        "outline_width": _coerce_int(source.get("outline_width"), defaults["outline_width"], 0, 8),
        "shadow": _coerce_int(source.get("shadow"), defaults["shadow"], 0, 8),
        "position": _coerce_position(source.get("position"), defaults["position"]),
        "margin_h": _coerce_int(source.get("margin_h"), defaults["margin_h"], 0, 400),
        "margin_v": _coerce_int(source.get("margin_v"), defaults["margin_v"], 0, 240),
        "max_line_chars": _coerce_int(
            source.get("max_line_chars"),
            defaults["max_line_chars"],
            16,
            40,
        ),
        "min_display_sec": _coerce_float(
            source.get("min_display_sec"),
            defaults["min_display_sec"],
            0.3,
            3.0,
        ),
        "cue_split_mode": _coerce_cue_split_mode(source.get("cue_split_mode"), defaults["cue_split_mode"]),
        "max_cue_sec": _coerce_float(
            source.get("max_cue_sec"),
            defaults["max_cue_sec"],
            1.0,
            6.0,
        ),
        "max_lines": _coerce_int(source.get("max_lines"), defaults["max_lines"], 1, 3),
        "effect": _coerce_effect(source.get("effect"), defaults["effect"]),
    }


def shorts_subtitle_style(style: dict[str, object] | SubtitleStyle | None = None) -> SubtitleStyle:
    source: dict[str, object] = dict(style or {})
    source.update(SHORTS_SUBTITLE_OVERRIDES)
    return normalize_subtitle_style(source)


def _ass_color(hex_color: str, opacity: float = 0.0) -> str:
    normalized = _coerce_color(hex_color, "#FFFFFF").lstrip("#")
    red = normalized[0:2]
    green = normalized[2:4]
    blue = normalized[4:6]
    alpha = round(max(0.0, min(1.0, opacity)) * 255)
    return f"&H{alpha:02X}{blue}{green}{red}"


def _ass_alignment(position: SubtitlePosition) -> int:
    if position == "middle":
        return 5
    return 2


def _estimate_block_height_px(font_size: int, line_count: int, outline: int) -> int:
    return int(font_size * 1.4) * max(1, line_count) + (outline * 2)


def _ass_margin_v(
    position: SubtitlePosition,
    user_margin_v: int,
    font_size: int,
    line_count: int,
    outline: int,
) -> int:
    if position == "middle":
        return 0
    block_height = _estimate_block_height_px(font_size, line_count, outline)
    target_center_y = int(PLAY_RES_Y * POSITION_CENTER_RATIO[position])
    margin = PLAY_RES_Y - target_center_y - (block_height // 2)
    if position == "top":
        margin -= user_margin_v
    elif position == "bottom":
        margin += user_margin_v
    return max(8, margin)


def _effective_max_line_chars(style: SubtitleStyle) -> int:
    available_width = max(480, PLAY_RES_X - (style["margin_h"] * 2))
    estimated_char_width = max(20.0, style["font_size"] * 1.05)
    safe_chars = int(available_width / estimated_char_width)
    floor = max(6, 24 // max(1, style["font_size"] // 24))
    return max(floor, min(style["max_line_chars"], safe_chars, 40))


def _escape_ass_text(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace("{", r"\{")
        .replace("}", r"\}")
        .replace("\n", r"\N")
    )


def _effect_tag(effect: SubtitleEffect) -> str:
    if effect == "fade":
        return r"{\fad(120,120)}"
    if effect == "pop":
        return r"{\fscx105\fscy105}"
    return ""


def _style_name_for_variant(variant: str) -> str:
    if variant == "quote":
        return "Quote"
    if variant == "emphasis":
        return "Emphasis"
    return "Default"


def _variant_style(base: SubtitleStyle, variant: str) -> SubtitleStyle:
    if variant == "quote":
        return normalize_subtitle_style(
            {
                **base,
                "primary_color": "#FFE6A3",
                "position": "lower",
                "effect": "fade" if base["effect"] != "karaoke" else "karaoke",
                "min_display_sec": max(base["min_display_sec"], 1.3),
                "background_opacity": max(base["background_opacity"], 0.15),
            }
        )
    if variant == "emphasis":
        return normalize_subtitle_style(
            {
                **base,
                "font_size": min(96, base["font_size"] + 8),
                "primary_color": "#FFF07A",
                "position": "upper",
                "effect": "pop" if base["effect"] != "karaoke" else "karaoke",
                "outline_width": max(base["outline_width"], 3),
                "background_opacity": max(base["background_opacity"], 0.2),
            }
        )
    return normalize_subtitle_style(base)


def _karaoke_text(
    timing: TimingEntry,
    word_timings: list[WordTimingEntry],
    max_line_chars: int,
) -> str:
    cue_words = [word for word in word_timings if word["cue_idx"] == timing["idx"]]
    if not cue_words:
        return _escape_ass_text(_smart_wrap(timing["text"], max_line_chars))

    karaoke_parts: list[str] = []
    for word in cue_words:
        duration_cs = max(1, int(round((word["end"] - word["start"]) * 100)))
        karaoke_parts.append(rf"{{\k{duration_cs}}}{_escape_ass_text(word['word'])}")
    return " ".join(karaoke_parts)


def _apply_min_display_time(
    timings: list[TimingEntry],
    min_display_sec: float,
    *,
    allow_extension: bool = True,
) -> list[TimingEntry]:
    if not allow_extension:
        return [{**timing, "dur": max(0.0, timing["end"] - timing["start"])} for timing in timings]
    adjusted: list[TimingEntry] = []
    total = len(timings)
    for index, timing in enumerate(timings):
        next_start = timings[index + 1]["start"] if index + 1 < total else None
        end = timing["end"]
        desired_end = max(end, timing["start"] + min_display_sec)
        if next_start is not None:
            desired_end = min(desired_end, max(end, next_start - 0.05))
        adjusted.append(
            {
                **timing,
                "end": desired_end,
                "dur": max(0.0, desired_end - timing["start"]),
            }
        )
    return adjusted


def _timing_source_idx(timing: TimingEntry) -> int:
    source_idx = timing.get("source_idx")
    if isinstance(source_idx, int):
        return source_idx
    return timing["idx"]


def _join_words(words: list[WordTimingEntry]) -> str:
    return " ".join(word["word"].strip() for word in words if word["word"].strip()).strip()


def _normalize_word_match_text(text: str) -> str:
    return WORD_TEXT_SANITIZE_RE.sub("", text).casefold()


def _word_timings_are_usable(
    timings: list[TimingEntry],
    word_timings: list[WordTimingEntry],
) -> bool:
    if not timings or not word_timings:
        return False
    cue_words_by_idx: dict[int, list[WordTimingEntry]] = {}
    for word in word_timings:
        cue_words_by_idx.setdefault(word["cue_idx"], []).append(word)
    matched = 0
    with_words = 0
    for timing in timings:
        source_words = cue_words_by_idx.get(timing["idx"], [])
        if not source_words:
            continue
        with_words += 1
        joined = _normalize_word_match_text(_join_words(source_words))
        expected = _normalize_word_match_text(timing["text"])
        if joined and expected and joined == expected:
            matched += 1
    if with_words == 0:
        return False
    return (matched / with_words) >= 0.8


def _split_text_parts(text: str, budget: int) -> list[str]:
    normalized = " ".join(text.strip().split())
    if not normalized:
        return []
    if len(normalized) <= budget:
        return [normalized]
    parts: list[str] = []
    remaining = normalized
    while remaining:
        if len(remaining) <= budget:
            parts.append(remaining)
            break
        split_at = _find_break_backward(remaining, budget)
        if split_at <= 0:
            split_at = budget
        head = remaining[:split_at].rstrip()
        tail = remaining[split_at:].lstrip(" ,;:")
        if not head:
            head = remaining[:budget].rstrip()
            tail = remaining[budget:].lstrip()
        parts.append(head)
        remaining = tail
    return [part for part in parts if part]


def _split_readable_text_cues(
    timings: list[TimingEntry],
    *,
    max_chars_per_cue: int,
) -> list[TimingEntry]:
    cues: list[TimingEntry] = []
    next_idx = 0
    for timing in timings:
        parts = _split_text_parts(timing["text"], max_chars_per_cue)
        if not parts:
            continue
        total_units = max(1, sum(max(1, len(part.replace(" ", ""))) for part in parts))
        consumed_units = 0
        for part_index, part in enumerate(parts):
            part_units = max(1, len(part.replace(" ", "")))
            start = timing["start"] + (timing["dur"] * consumed_units / total_units)
            if part_index == len(parts) - 1:
                end = timing["end"]
            else:
                end = timing["start"] + (timing["dur"] * (consumed_units + part_units) / total_units)
            cues.append(
                {
                    "idx": next_idx,
                    "source_idx": timing["idx"],
                    "text": part,
                    "start": round(start, 3),
                    "end": round(max(start, end), 3),
                    "dur": round(max(0.0, end - start), 3),
                }
            )
            next_idx += 1
            consumed_units += part_units
    return cues


def _split_readable_word_cues(
    timings: list[TimingEntry],
    word_timings: list[WordTimingEntry],
    *,
    max_chars_per_cue: int,
    max_cue_sec: float,
) -> tuple[list[TimingEntry], list[WordTimingEntry]]:
    cue_words_by_idx: dict[int, list[WordTimingEntry]] = {}
    for word in word_timings:
        cue_words_by_idx.setdefault(word["cue_idx"], []).append(word)

    cues: list[TimingEntry] = []
    split_words: list[WordTimingEntry] = []
    next_idx = 0
    for timing in timings:
        source_words = cue_words_by_idx.get(timing["idx"], [])
        if not source_words:
            fallback_cues = _split_readable_text_cues([timing], max_chars_per_cue=max_chars_per_cue)
            for fallback in fallback_cues:
                fallback["idx"] = next_idx
                fallback["source_idx"] = timing["idx"]
                cues.append(fallback)
                next_idx += 1
            continue

        current_words: list[WordTimingEntry] = []

        def flush_current() -> None:
            nonlocal current_words, next_idx
            if not current_words:
                return
            cue_text = _join_words(current_words)
            start = current_words[0]["start"]
            end = current_words[-1]["end"]
            cues.append(
                {
                    "idx": next_idx,
                    "source_idx": timing["idx"],
                    "text": cue_text,
                    "start": round(start, 3),
                    "end": round(end, 3),
                    "dur": round(max(0.0, end - start), 3),
                }
            )
            for word in current_words:
                split_words.append(
                    {
                        "cue_idx": next_idx,
                        "word": word["word"],
                        "start": word["start"],
                        "end": word["end"],
                    }
                )
            next_idx += 1
            current_words = []

        for word_index, word in enumerate(source_words):
            if current_words:
                prospective_words = [*current_words, word]
                prospective_text = _join_words(prospective_words)
                prospective_duration = word["end"] - current_words[0]["start"]
                if len(prospective_text) > max_chars_per_cue or prospective_duration > max_cue_sec:
                    flush_current()
            current_words.append(word)
            current_duration = current_words[-1]["end"] - current_words[0]["start"]
            should_break = (
                word["word"].strip().endswith(tuple(READABLE_PUNCTUATION))
                and current_duration >= READABLE_MIN_DISPLAY_SEC
                and word_index < len(source_words) - 1
            )
            if should_break:
                flush_current()
        flush_current()
    return cues, split_words


def _prepare_display_timings(
    timings: list[TimingEntry],
    style: SubtitleStyle,
    word_timings: list[WordTimingEntry] | None = None,
) -> tuple[list[TimingEntry], list[WordTimingEntry] | None, bool]:
    normalized = normalize_subtitle_style(style)
    if normalized["cue_split_mode"] != "readable":
        adjusted = _apply_min_display_time(timings, normalized["min_display_sec"])
        return adjusted, word_timings, False

    max_line_chars = _effective_max_line_chars(normalized)
    max_chars_per_cue = max_line_chars * max(1, normalized["max_lines"])
    if word_timings and _word_timings_are_usable(timings, word_timings):
        split_timings, split_words = _split_readable_word_cues(
            timings,
            word_timings,
            max_chars_per_cue=max_chars_per_cue,
            max_cue_sec=normalized["max_cue_sec"],
        )
        adjusted = _apply_min_display_time(split_timings, READABLE_MIN_DISPLAY_SEC, allow_extension=False)
        return adjusted, split_words, True

    split_timings = _split_readable_text_cues(timings, max_chars_per_cue=max_chars_per_cue)
    adjusted = _apply_min_display_time(split_timings, READABLE_MIN_DISPLAY_SEC, allow_extension=False)
    return adjusted, None, True


def count_display_cues(
    timings: list[TimingEntry],
    style: SubtitleStyle,
    word_timings: list[WordTimingEntry] | None = None,
) -> int:
    display_timings, _, _ = _prepare_display_timings(timings, style, word_timings)
    return len(display_timings)


def subtitle_display_qa(
    timings: list[TimingEntry],
    style: SubtitleStyle,
    word_timings: list[WordTimingEntry] | None = None,
    *,
    render_format: str = "landscape",
) -> dict[str, object]:
    normalized = normalize_subtitle_style(style)
    adjusted_timings, _, _ = _prepare_display_timings(timings, normalized, word_timings)
    max_line_chars = _effective_max_line_chars(normalized)
    max_lines = max(1, int(normalized.get("max_lines", 2)))
    max_cue_sec = float(normalized.get("max_cue_sec", DEFAULT_SUBTITLE_STYLE["max_cue_sec"]))
    issues: list[dict[str, object]] = []
    for timing in adjusted_timings:
        wrapped = _smart_wrap(timing["text"], max_line_chars)
        lines = wrapped.splitlines() or [""]
        longest_line = max((len(line) for line in lines), default=0)
        duration = float(timing["end"] - timing["start"])
        cue_issues: list[str] = []
        if len(lines) > max_lines:
            cue_issues.append(f"{len(lines)} lines")
        if longest_line > max_line_chars:
            cue_issues.append(f"{longest_line} chars on one line")
        if render_format == "shorts" and duration > max_cue_sec + 0.15:
            cue_issues.append(f"{duration:.1f}s cue")
        if cue_issues:
            issues.append(
                {
                    "idx": timing["idx"],
                    "text": timing["text"][:80],
                    "issues": cue_issues,
                }
            )
    if render_format == "shorts" and normalized["cue_split_mode"] != "readable":
        issues.insert(
            0,
            {
                "idx": -1,
                "text": "",
                "issues": ["shorts subtitles require readable cue splitting"],
            },
        )
    return {
        "ok": not issues,
        "cue_count": len(adjusted_timings),
        "max_line_chars": max_line_chars,
        "max_lines": max_lines,
        "max_cue_sec": max_cue_sec,
        "issues": issues[:5],
    }


def write_srt(timings: list[TimingEntry], out_path: Path) -> Path:
    lines: list[str] = []
    adjusted_timings, _, _ = _prepare_display_timings(timings, DEFAULT_SUBTITLE_STYLE, None)
    max_line_chars = _effective_max_line_chars(DEFAULT_SUBTITLE_STYLE)
    for index, timing in enumerate(adjusted_timings, start=1):
        lines.append(str(index))
        lines.append(f"{_fmt_ts(timing['start'])} --> {_fmt_ts(timing['end'])}")
        lines.append(_smart_wrap(timing["text"], max_line_chars))
        lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def _fmt_ass_ts(sec: float) -> str:
    hours = int(sec // 3600)
    minutes = int((sec % 3600) // 60)
    seconds = int(sec % 60)
    centiseconds = int(round((sec - int(sec)) * 100))
    if centiseconds == 100:
        centiseconds, seconds = 0, seconds + 1
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"


def write_ass(
    timings: list[TimingEntry],
    out_path: Path,
    style: SubtitleStyle,
    word_timings: list[WordTimingEntry] | None = None,
    cue_style_map: dict[int, str] | None = None,
) -> Path:
    normalized = normalize_subtitle_style(style)
    variant_keys = {"plain"}
    if cue_style_map:
        variant_keys.update(str(value or "plain") for value in cue_style_map.values())
    variant_styles = {
        variant: _variant_style(normalized, variant)
        for variant in sorted(variant_keys)
    }
    default_variant = variant_styles.get("plain", normalized)
    adjusted_timings, display_word_timings, is_readable_split = _prepare_display_timings(
        timings,
        normalized,
        word_timings,
    )
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        f"PlayResX: {PLAY_RES_X}",
        f"PlayResY: {PLAY_RES_Y}",
        "",
        "[V4+ Styles]",
        (
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
            "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding"
        ),
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for variant, variant_style in variant_styles.items():
        lines.insert(
            -3,
            (
                f"Style: {_style_name_for_variant(variant)},"
                f"{variant_style['font_family']},"
                f"{variant_style['font_size']},"
                f"{_ass_color(variant_style['primary_color'])},"
                "&H00FFFFFF,"
                f"{_ass_color(variant_style['outline_color'])},"
                f"{_ass_color(variant_style['background_color'], 1.0 - variant_style['background_opacity'])},"
                "0,0,0,0,100,100,0,0,1,"
                f"{variant_style['outline_width']},"
                f"{variant_style['shadow']},"
                f"{_ass_alignment(variant_style['position'])},"
                f"{variant_style['margin_h']},{variant_style['margin_h']},"
                f"{variant_style['margin_v']},"
                "1"
            ),
        )
    for timing in adjusted_timings:
        style_lookup_idx = _timing_source_idx(timing) if is_readable_split else timing["idx"]
        variant = str(cue_style_map.get(style_lookup_idx, "plain")) if cue_style_map else "plain"
        variant_style = variant_styles.get(variant, default_variant)
        max_line_chars = _effective_max_line_chars(variant_style)
        plain_wrapped = _smart_wrap(timing["text"], max_line_chars)
        line_count = plain_wrapped.count("\n") + 1
        event_margin_v = _ass_margin_v(
            variant_style["position"],
            variant_style["margin_v"],
            variant_style["font_size"],
            line_count,
            variant_style["outline_width"],
        )
        text = (
            _karaoke_text(timing, display_word_timings or [], max_line_chars)
            if variant_style["effect"] == "karaoke"
            else _escape_ass_text(plain_wrapped)
        )
        lines.append(
            "Dialogue: 0,"
            f"{_fmt_ass_ts(timing['start'])},"
            f"{_fmt_ass_ts(timing['end'])},"
            f"{_style_name_for_variant(variant)},,0,0,{event_margin_v},,"
            f"{_effect_tag(variant_style['effect'])}{text}"
        )
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path
