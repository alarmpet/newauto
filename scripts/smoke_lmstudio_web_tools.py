from __future__ import annotations

import json
import sys
import traceback
import urllib.request
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LMSTUDIO_BASE_URL = "http://127.0.0.1:1234"
MODEL = "google/gemma-4-e4b"
CONNECT_TIMEOUT_SEC = 10
MODEL_TIMEOUT_SEC = 180

sys.path.insert(0, str(PROJECT_ROOT))

from app.services.web_read import format_read_url_or_search  # noqa: E402
from app.services.web_read import read_url_or_search  # noqa: E402
from app.services.web_search import format_search_response  # noqa: E402
from app.services.web_search import search_web  # noqa: E402


def _post_json(path: str, payload: dict[str, Any], *, timeout_sec: int) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{LMSTUDIO_BASE_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_sec) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_json(path: str, *, timeout_sec: int) -> dict[str, Any]:
    with urllib.request.urlopen(f"{LMSTUDIO_BASE_URL}{path}", timeout=timeout_sec) as response:
        return json.loads(response.read().decode("utf-8"))


def check_lmstudio_models() -> None:
    payload = _get_json("/v1/models", timeout_sec=CONNECT_TIMEOUT_SEC)
    model_ids = [item.get("id") for item in payload.get("data", [])]
    print("LM Studio models:", ", ".join(str(item) for item in model_ids))
    if MODEL not in model_ids:
        raise RuntimeError(f"Expected loaded model not found: {MODEL}")


def check_tool_choice() -> None:
    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Use search_web for current/latest news search requests. "
                    "Do not use browser_navigate unless visual browser interaction is needed."
                ),
            },
            {"role": "user", "content": "구글에서 최신 AI 뉴스 3개 검색해서 제목이랑 요약해줘"},
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "search_web",
                    "description": "Search the public web for current/latest news results.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "max_results": {"type": "integer"},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_navigate",
                    "description": "Open a visual browser only for interactive browsing.",
                    "parameters": {
                        "type": "object",
                        "properties": {"url": {"type": "string"}},
                        "required": ["url"],
                    },
                },
            },
        ],
        "tool_choice": "auto",
        "temperature": 0,
        "max_tokens": 512,
    }
    response = _post_json("/v1/chat/completions", payload, timeout_sec=MODEL_TIMEOUT_SEC)
    message = response["choices"][0]["message"]
    tool_calls = message.get("tool_calls") or []
    selected = [call["function"]["name"] for call in tool_calls]
    print("Selected tools:", selected)
    if selected[:1] != ["search_web"]:
        raise RuntimeError(f"Expected first tool to be search_web, got: {selected or message.get('content')}")


def check_search_web() -> None:
    response = search_web("최신 AI 뉴스", max_results=3, timeout_sec=20)
    print(format_search_response(response, snippet_limit=160))
    if not response.ok or len(response.results) < 3:
        raise RuntimeError(f"search_web failed: {response.failure_class} {response.message}")


def check_naver_read() -> None:
    payload = read_url_or_search("네이버뉴스 최신뉴스 3개", count=3)
    print(format_read_url_or_search(payload)[:2500])
    items = payload.get("articles") or payload.get("items") or payload.get("results") or []
    if not payload.get("ok") or len(items) < 3:
        raise RuntimeError(f"read_url_or_search failed: {payload.get('failure_class')} {payload.get('message')}")


def main() -> int:
    checks = [
        ("lmstudio_models", check_lmstudio_models),
        ("tool_choice", check_tool_choice),
        ("search_web", check_search_web),
        ("naver_read", check_naver_read),
    ]
    for name, check in checks:
        print(f"\n== {name} ==")
        try:
            check()
        except Exception as exc:
            print(f"FAILED: {name}")
            print(f"failure_class: {type(exc).__name__}")
            print(f"message: {exc}")
            print("next_action: start LM Studio local server and rerun this smoke test")
            if "--debug" in sys.argv:
                traceback.print_exc()
            return 1
    print("\nSmoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
