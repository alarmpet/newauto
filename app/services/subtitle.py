from pathlib import Path
import re

from ..types import SubtitleEffect, SubtitlePosition, SubtitleStyle, TimingEntry

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
    "margin_v": 80,
    "max_line_chars": 40,
    "effect": "none",
}

_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
_POSITION_VALUES: set[SubtitlePosition] = {"top", "middle", "bottom"}
_EFFECT_VALUES: set[SubtitleEffect] = {"none", "fade", "pop"}


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
        "margin_v": _coerce_int(source.get("margin_v"), defaults["margin_v"], 0, 240),
        "max_line_chars": _coerce_int(
            source.get("max_line_chars"),
            defaults["max_line_chars"],
            16,
            80,
        ),
        "effect": _coerce_effect(source.get("effect"), defaults["effect"]),
    }


def _ass_color(hex_color: str, opacity: float = 0.0) -> str:
    normalized = _coerce_color(hex_color, "#FFFFFF").lstrip("#")
    red = normalized[0:2]
    green = normalized[2:4]
    blue = normalized[4:6]
    alpha = round(max(0.0, min(1.0, opacity)) * 255)
    return f"&H{alpha:02X}{blue}{green}{red}"


def _ass_alignment(position: SubtitlePosition) -> int:
    if position == "top":
        return 8
    if position == "middle":
        return 5
    return 2


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


def write_srt(timings: list[TimingEntry], out_path: Path) -> Path:
    lines: list[str] = []
    for index, timing in enumerate(timings, start=1):
        lines.append(str(index))
        lines.append(f"{_fmt_ts(timing['start'])} --> {_fmt_ts(timing['end'])}")
        lines.append(_wrap_long(timing["text"]))
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


def write_ass(timings: list[TimingEntry], out_path: Path, style: SubtitleStyle) -> Path:
    normalized = normalize_subtitle_style(style)
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "PlayResX: 1920",
        "PlayResY: 1080",
        "",
        "[V4+ Styles]",
        (
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
            "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding"
        ),
        (
            "Style: Default,"
            f"{normalized['font_family']},"
            f"{normalized['font_size']},"
            f"{_ass_color(normalized['primary_color'])},"
            "&H00FFFFFF,"
            f"{_ass_color(normalized['outline_color'])},"
            f"{_ass_color(normalized['background_color'], 1.0 - normalized['background_opacity'])},"
            "0,0,0,0,100,100,0,0,1,"
            f"{normalized['outline_width']},"
            f"{normalized['shadow']},"
            f"{_ass_alignment(normalized['position'])},"
            "120,120,"
            f"{normalized['margin_v']},"
            "1"
        ),
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for timing in timings:
        text = _escape_ass_text(_wrap_long(timing["text"], normalized["max_line_chars"]))
        lines.append(
            "Dialogue: 0,"
            f"{_fmt_ass_ts(timing['start'])},"
            f"{_fmt_ass_ts(timing['end'])},"
            "Default,,0,0,0,,"
            f"{_effect_tag(normalized['effect'])}{text}"
        )
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path
