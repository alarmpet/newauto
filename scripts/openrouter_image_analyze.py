from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
OPENROUTER_KEY_FILE = ROOT_DIR / "openrouter.txt"
API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "google/gemma-4-26b-a4b-it:free"
DEFAULT_FALLBACK_MODEL = "google/gemma-4-31b-it:free"
REDACT_MARKERS = ("api_key", "authorization", "bearer", "token", "cookie")
USER_ID_RE = re.compile(r"user_[A-Za-z0-9_-]+")


def load_api_key() -> tuple[str, str]:
    env_key = os.environ.get("OPENROUTER_API_KEY", "").strip().lstrip("\ufeff")
    if env_key:
        return env_key, "env"
    if OPENROUTER_KEY_FILE.exists():
        for raw_line in OPENROUTER_KEY_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw_line.strip().lstrip("\ufeff")
            if line and not line.startswith("#"):
                return line, "openrouter.txt:first-line"
    return "", "missing"


def image_data_url(path: Path) -> str:
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(str(path))
    mime_type = mimetypes.guess_type(str(path))[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def redact_detail(value: str) -> str:
    text = USER_ID_RE.sub("user_[REDACTED]", value)
    for marker in REDACT_MARKERS:
        text = text.replace(marker, f"{marker}_redacted")
    return text[:1000]


def model_chain(primary: str, fallback: str) -> list[str]:
    chain: list[str] = []
    for model in (primary, fallback):
        cleaned = model.strip()
        if cleaned and cleaned not in chain:
            if not cleaned.endswith(":free"):
                raise ValueError(f"refusing_non_free_model:{cleaned}")
            chain.append(cleaned)
    return chain


def call_openrouter(
    *,
    api_key: str,
    model: str,
    image_path: Path,
    prompt: str,
    max_tokens: int,
    timeout_sec: int,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You analyze images for a local coding/video automation assistant. "
                    "Answer in Korean. Separate visible observations from guesses. "
                    "Do not ask for secrets or credentials."
                ),
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_data_url(image_path)}},
                ],
            },
        ],
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://local.newauto",
        "X-Title": "newauto-openrouter-image-analysis",
    }
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_sec) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def extract_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices", [])
    if not choices or not isinstance(choices[0], dict):
        return ""
    message = choices[0].get("message", {})
    if not isinstance(message, dict):
        return ""
    content = message.get("content", "")
    return content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze one image with OpenRouter Gemma 4 free model.")
    parser.add_argument("image", help="Path to an image file.")
    parser.add_argument("--prompt", default="이 이미지를 자세히 분석해줘.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--fallback-model", default=DEFAULT_FALLBACK_MODEL)
    parser.add_argument("--max-tokens", type=int, default=1200)
    parser.add_argument("--timeout-sec", type=int, default=60)
    parser.add_argument("--json-output", action="store_true")
    args = parser.parse_args()

    try:
        models = model_chain(args.model, args.fallback_model)
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2

    api_key, key_source = load_api_key()
    if not api_key:
        print(json.dumps({"ok": False, "error": "missing_api_key", "key_source": key_source}, ensure_ascii=False))
        return 1

    image_path = Path(args.image)
    if not image_path.is_absolute():
        image_path = (Path.cwd() / image_path).resolve()

    attempts: list[dict[str, Any]] = []
    payload: dict[str, Any] | None = None
    resolved_model = models[0]
    for index, candidate in enumerate(models):
        try:
            payload = call_openrouter(
                api_key=api_key,
                model=candidate,
                image_path=image_path,
                prompt=args.prompt,
                max_tokens=args.max_tokens,
                timeout_sec=args.timeout_sec,
            )
            resolved_model = candidate
            attempts.append({"model": candidate, "ok": True})
            break
        except urllib.error.HTTPError as exc:
            detail = redact_detail(exc.read().decode("utf-8", errors="replace"))
            attempts.append({"model": candidate, "ok": False, "error": f"openrouter_http_{exc.code}", "detail": detail})
            if exc.code not in {408, 409, 429} and exc.code < 500:
                break
            if index >= len(models) - 1:
                break
        except Exception as exc:
            attempts.append({"model": candidate, "ok": False, "error": type(exc).__name__, "detail": redact_detail(str(exc))})
            if index >= len(models) - 1:
                break

    if payload is None:
        print(json.dumps({"ok": False, "error": "all_models_failed", "attempts": attempts}, ensure_ascii=False))
        return 1

    text = extract_text(payload)
    result = {
        "ok": bool(text.strip()),
        "model": resolved_model,
        "model_chain": models,
        "attempts": attempts,
        "key_source": key_source,
        "image": str(image_path),
        "analysis": text,
        "usage": payload.get("usage", {}),
        "finish_reason": (
            payload.get("choices", [{}])[0].get("finish_reason", "")
            if isinstance(payload.get("choices", [{}])[0], dict)
            else ""
        ),
    }
    if args.json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(text)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
