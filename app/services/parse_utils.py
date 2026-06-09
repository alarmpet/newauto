import json
import re
from typing import cast


_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")


class JsonExtractionError(ValueError):
    pass


def _strip_markdown_fence(text: str) -> str:
    match = _JSON_BLOCK_RE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


def _extract_json_candidate(text: str) -> str:
    stripped = _strip_markdown_fence(text)
    starts = [index for index in (stripped.find("{"), stripped.find("[")) if index >= 0]
    if not starts:
        return stripped
    start = min(starts)
    open_char = stripped[start]
    close_char = "}" if open_char == "{" else "]"
    end = stripped.rfind(close_char)
    if end >= start:
        return stripped[start : end + 1].strip()
    return stripped[start:].strip()


def _balance_brackets(text: str) -> str:
    double_quote_open = False
    escaped = False
    stack: list[str] = []
    for char in text:
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            double_quote_open = not double_quote_open
            continue
        if double_quote_open:
            continue
        if char == "{":
            stack.append("}")
        elif char == "[":
            stack.append("]")
        elif char in {"}", "]"} and stack and stack[-1] == char:
            stack.pop()
    if double_quote_open:
        text += '"'
    if stack:
        text += "".join(reversed(stack))
    return text


def extract_json_from_llm_response(text: str) -> dict[str, object]:
    candidate = _extract_json_candidate(text)
    attempts = [
        candidate,
        _TRAILING_COMMA_RE.sub(r"\1", candidate),
        _balance_brackets(_TRAILING_COMMA_RE.sub(r"\1", candidate)),
    ]
    last_error: Exception | None = None
    for attempt in attempts:
        try:
            payload = json.loads(attempt)
        except json.JSONDecodeError as exc:
            last_error = exc
            continue
        if isinstance(payload, dict):
            return cast(dict[str, object], payload)
        raise JsonExtractionError("LLM JSON response must be an object.")
    detail = str(last_error) if last_error is not None else "no JSON object found"
    raise JsonExtractionError(f"Failed to parse LLM JSON response: {detail}")


def to_int(value: object, default: int) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def to_float(value: object, default: float) -> float:
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def clamp_float(value: object, default: float, *, minimum: float = 0.0, maximum: float = 1.0) -> float:
    parsed = to_float(value, default)
    return max(minimum, min(maximum, parsed))
