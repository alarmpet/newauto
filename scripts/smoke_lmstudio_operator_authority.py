from __future__ import annotations

import json
import os
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
COMFYUI_PATH = r"C:\Users\petbl\autotube\ComfyUI"

sys.path.insert(0, str(PROJECT_ROOT))

try:
    from scripts import lmstudio_openclaw_operator_mcp as operator_core  # noqa: E402
except ModuleNotFoundError as exc:
    if exc.name == "mcp":
        print("FAILED: import_operator_core")
        print("failure_class: missing_mcp_package")
        print("message: This smoke test must run with the LM Studio/newauto MCP Python environment.")
        print(r"next_action: C:\Users\petbl\local-rag\.venv\Scripts\python.exe scripts\smoke_lmstudio_operator_authority.py")
        raise SystemExit(1) from exc
    raise


def _get_json(path: str, *, timeout_sec: int) -> dict[str, Any]:
    with urllib.request.urlopen(f"{LMSTUDIO_BASE_URL}{path}", timeout=timeout_sec) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_json(path: str, payload: dict[str, Any], *, timeout_sec: int) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{LMSTUDIO_BASE_URL}{path}",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_sec) as response:
        return json.loads(response.read().decode("utf-8"))


def check_lmstudio_models() -> None:
    payload = _get_json("/v1/models", timeout_sec=CONNECT_TIMEOUT_SEC)
    model_ids = [item.get("id") for item in payload.get("data", [])]
    print("LM Studio models:", ", ".join(str(item) for item in model_ids))
    if MODEL not in model_ids:
        raise RuntimeError(f"Expected loaded model not found: {MODEL}")


def check_gemma_operator_tool_choice() -> None:
    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a local Windows operator. If the user asks to inspect local paths, "
                    "configure environment variables, create files, install normal tools, or verify "
                    "local state, use run_powershell. Do not say you cannot execute code."
                ),
            },
            {"role": "user", "content": rf"{COMFYUI_PATH} 경로가 존재하는지 확인해줘"},
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "run_powershell",
                    "description": "Run a local PowerShell command for safe local inspection and setup.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string"},
                            "cwd": {"type": "string"},
                            "timeout_sec": {"type": "integer"},
                            "force_approve": {"type": "boolean"},
                        },
                        "required": ["command"],
                    },
                },
            }
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
    if selected[:1] != ["run_powershell"]:
        raise RuntimeError(f"Expected run_powershell tool call, got: {selected or message.get('content')}")


def check_direct_operator_path() -> None:
    command = rf"Test-Path -LiteralPath '{COMFYUI_PATH}'"
    result = operator_core.run_powershell(command=command, cwd=str(PROJECT_ROOT), timeout_sec=20)
    print(result)
    if "exit_code: 0" not in result:
        raise RuntimeError("ComfyUI Test-Path command did not complete successfully.")


def check_user_env_write() -> None:
    name = "NEWAUTO_OPERATOR_SMOKE"
    value = "ok"
    command = (
        f"[Environment]::SetEnvironmentVariable('{name}','{value}','User'); "
        f"[Environment]::GetEnvironmentVariable('{name}','User')"
    )
    result = operator_core.run_powershell(command=command, cwd=str(PROJECT_ROOT), timeout_sec=20)
    print(result)
    if value not in result:
        raise RuntimeError("User environment variable write/read smoke failed.")


def check_destructive_guardrail() -> None:
    target = PROJECT_ROOT / "storage" / "operator_smoke_delete_guard"
    command = f"Remove-Item -LiteralPath '{target}' -Recurse -Force"
    result = operator_core.run_powershell(command=command, cwd=str(PROJECT_ROOT), timeout_sec=20, force_approve=False)
    print(result)
    if "approval_required" not in result:
        raise RuntimeError("Destructive command was not blocked with approval_required.")


def main() -> int:
    checks = [
        ("lmstudio_models", check_lmstudio_models),
        ("gemma_operator_tool_choice", check_gemma_operator_tool_choice),
        ("direct_operator_path", check_direct_operator_path),
        ("user_env_write", check_user_env_write),
        ("destructive_guardrail", check_destructive_guardrail),
    ]
    for name, check in checks:
        print(f"\n== {name} ==")
        try:
            check()
        except Exception as exc:
            print(f"FAILED: {name}")
            print(f"failure_class: {type(exc).__name__}")
            print(f"message: {exc}")
            if name.startswith("lmstudio") or name.startswith("gemma"):
                print("next_action: start LM Studio local server, load google/gemma-4-e4b, and rerun.")
            if "--debug" in sys.argv:
                traceback.print_exc()
            return 1
    print("\nOperator authority smoke test passed.")
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    raise SystemExit(main())
