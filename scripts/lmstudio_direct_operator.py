from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts import lmstudio_openclaw_operator_mcp as operator_core

DEFAULT_BASE_URL = "http://127.0.0.1:1234"
DEFAULT_MODEL = "google/gemma-4-e4b"
MAX_STEPS = 8
AUTO_MODEL_PREFERENCE = (
    "qwen/qwen3.5-9b",
    "google/gemma-4-e4b",
)

SYSTEM_PROMPT = """You are a local Windows operator running through LM Studio.

You can request local tool calls by replying with exactly one JSON object and no markdown.
Use Korean for user-facing final answers.

Available JSON actions:
{"action":"run_powershell","command":"...","cwd":"C:\\\\Users\\\\petbl\\\\newauto","timeout_sec":60,"force_approve":false}
{"action":"read_text_file","path":"...","max_chars":12000}
{"action":"write_text_file","path":"...","content":"...","append":false}
{"action":"list_directory","path":"...","recursive":false,"limit":200}
{"action":"open_target","target":"..."}
{"action":"final","message":"..."}

Rules:
- You are allowed to install programs or set environment variables when the user asks.
- Prefer winget for Windows app installs and PowerShell [Environment]::SetEnvironmentVariable for user env vars.
- After setting a user environment variable, verify it with [Environment]::GetEnvironmentVariable("NAME","User"), not $env:NAME.
- Keep commands scoped and explain what happened.
- Do not reveal or print secrets, tokens, cookies, passwords, or API keys.
- Block payment, purchase, account-password, destructive disk/account operations.
- If a tool result says approval_required, ask the user for explicit approval in a final message.
- For simple verification, use non-destructive commands first.
- Always finish with {"action":"final","message":"..."} after the task is complete.
"""


def _configure_stdout() -> None:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")


def _chat(base_url: str, model: str, messages: list[dict[str, str]], timeout: int = 180) -> str:
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": 2048,
        "stream": False,
    }
    request = urllib.request.Request(
        base_url.rstrip("/") + "/v1/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LM Studio HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"LM Studio request failed: {exc}") from exc

    obj = json.loads(body)
    choices = obj.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError(f"LM Studio response has no choices: {body[:500]}")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str):
        raise RuntimeError(f"LM Studio response has no text content: {body[:500]}")
    return content.strip()


def _loaded_models(base_url: str, timeout: int = 10) -> list[str]:
    request = urllib.request.Request(
        base_url.rstrip("/") + "/v1/models",
        headers={"Content-Type": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return []
    try:
        obj = json.loads(body)
    except json.JSONDecodeError:
        return []
    data = obj.get("data")
    if not isinstance(data, list):
        return []
    models: list[str] = []
    for item in data:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            models.append(item["id"])
    return models


def _resolve_model(base_url: str, requested: str) -> str:
    normalized = requested.strip()
    if normalized and normalized.lower() != "auto":
        return normalized

    loaded = _loaded_models(base_url)
    for preferred in AUTO_MODEL_PREFERENCE:
        if preferred in loaded:
            return preferred
    if loaded:
        return loaded[0]
    return DEFAULT_MODEL


def _extract_json(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    try:
        obj = json.loads(stripped)
    except json.JSONDecodeError as exc:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            try:
                obj = json.loads(stripped[start : end + 1])
            except json.JSONDecodeError:
                raise ValueError(f"Model did not return valid JSON. Raw response:\n{text}") from exc
        else:
            raise ValueError(f"Model did not return valid JSON. Raw response:\n{text}") from exc
    if not isinstance(obj, dict):
        raise ValueError(f"Model JSON must be an object. Raw response:\n{text}")
    return obj


def _tool_result(action: dict[str, Any]) -> str:
    name = str(action.get("action") or "").strip()
    if name == "run_powershell":
        return str(
            operator_core.run_powershell(
                command=str(action.get("command") or ""),
                cwd=str(action.get("cwd") or str(ROOT_DIR)),
                timeout_sec=int(action.get("timeout_sec") or 60),
                force_approve=bool(action.get("force_approve") or False),
            )
        )
    if name == "read_text_file":
        return str(
            operator_core.read_text_file(
                path=str(action.get("path") or ""),
                max_chars=int(action.get("max_chars") or 12000),
                redact_secrets=True,
            )
        )
    if name == "write_text_file":
        return str(
            operator_core.write_text_file(
                path=str(action.get("path") or ""),
                content=str(action.get("content") or ""),
                append=bool(action.get("append") or False),
            )
        )
    if name == "list_directory":
        return str(
            operator_core.list_directory(
                path=str(action.get("path") or str(ROOT_DIR)),
                recursive=bool(action.get("recursive") or False),
                limit=int(action.get("limit") or 200),
            )
        )
    if name == "open_target":
        return str(operator_core.open_target(str(action.get("target") or "")))
    raise ValueError(f"Unknown action: {name}")


def run_task(task: str, *, model: str, base_url: str, max_steps: int = MAX_STEPS, verbose: bool = True) -> str:
    messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task},
    ]
    for step in range(1, max_steps + 1):
        content = _chat(base_url, model, messages)
        if verbose:
            print(f"\n[model step {step}]\n{content}\n")
        try:
            action = _extract_json(content)
        except ValueError:
            if step > 1:
                return content
            raise
        if action.get("action") == "final":
            message = str(action.get("message") or "")
            return message
        result = _tool_result(action)
        if verbose:
            print(f"[tool result]\n{result}\n")
        messages.append({"role": "assistant", "content": content})
        messages.append({"role": "user", "content": "Tool result:\n" + result})
    raise RuntimeError(f"Task did not finish within {max_steps} steps.")


def main() -> int:
    _configure_stdout()
    parser = argparse.ArgumentParser(description="Run a direct LM Studio local operator loop without Cline/MCP client.")
    parser.add_argument("task", nargs="*", help="Task to give to the local LM Studio model.")
    parser.add_argument("--model", default=os.getenv("SCRIPT_LLM_MODEL", DEFAULT_MODEL))
    parser.add_argument("--base-url", default=os.getenv("LMSTUDIO_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--max-steps", type=int, default=MAX_STEPS)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    task = " ".join(args.task).strip()
    if not task:
        print("Enter a task for LM Studio. Ctrl+Z then Enter exits.")
        task = sys.stdin.read().strip()
    if not task:
        print("No task provided.")
        return 2
    model = _resolve_model(args.base_url, args.model)
    if not args.quiet:
        print(f"[lmstudio model] {model}")
    final = run_task(task, model=model, base_url=args.base_url, max_steps=args.max_steps, verbose=not args.quiet)
    print("\n=== final ===")
    print(final)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
