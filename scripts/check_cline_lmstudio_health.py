from __future__ import annotations

import argparse
import json
import subprocess
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_MODEL = "qwen/qwen3.5-9b"
DEFAULT_CONTEXT_TARGET = 131_072
CLINE_STORAGE = (
    Path.home()
    / "AppData"
    / "Roaming"
    / "Code"
    / "User"
    / "globalStorage"
    / "saoudrizwan.claude-dev"
)


def _json_get(url: str, timeout: int = 5) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("response root is not a JSON object")
    return payload


def _model_status(model_id: str, context_target: int) -> dict[str, Any]:
    status: dict[str, Any] = {
        "api_ok": False,
        "model_id": model_id,
        "loaded": False,
        "loaded_context_length": 0,
        "max_context_length": 0,
        "context_target": context_target,
        "context_target_met": False,
        "error": "",
    }
    try:
        payload = _json_get("http://127.0.0.1:1234/api/v0/models")
    except Exception as exc:
        status["error"] = f"{type(exc).__name__}: {exc}"
        return status
    status["api_ok"] = True
    for item in payload.get("data", []):
        if not isinstance(item, dict) or item.get("id") != model_id:
            continue
        status["loaded"] = item.get("state") == "loaded"
        status["loaded_context_length"] = int(item.get("loaded_context_length") or 0)
        status["max_context_length"] = int(item.get("max_context_length") or 0)
        status["context_target_met"] = status["loaded_context_length"] >= context_target
        return status
    status["error"] = "model_not_found"
    return status


def _lms_ps() -> str:
    lms = Path.home() / ".lmstudio" / "bin" / "lms.exe"
    if not lms.exists():
        return "lms.exe not found"
    completed = subprocess.run(
        [str(lms), "ps"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
    )
    text = (completed.stdout or completed.stderr).strip()
    return text or f"lms ps exited {completed.returncode}"


def _task_dir_size(path: Path) -> int:
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except OSError:
                continue
    return total


def _large_cline_tasks(limit: int = 8) -> list[dict[str, Any]]:
    tasks_dir = CLINE_STORAGE / "tasks"
    if not tasks_dir.exists():
        return []
    rows: list[dict[str, Any]] = []
    for task_dir in tasks_dir.iterdir():
        if not task_dir.is_dir():
            continue
        size = _task_dir_size(task_dir)
        metadata_path = task_dir / "task_metadata.json"
        tokens_in = 0
        task_excerpt = ""
        if metadata_path.exists():
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                usage = metadata.get("model_usage", [])
                if isinstance(usage, list):
                    tokens_in = sum(int(item.get("tokens_in") or 0) for item in usage if isinstance(item, dict))
                task_excerpt = str(metadata.get("task") or "")[:120]
            except Exception:
                pass
        rows.append(
            {
                "id": task_dir.name,
                "size_mb": round(size / 1024 / 1024, 2),
                "tokens_in": tokens_in,
                "task_excerpt": task_excerpt,
            }
        )
    rows.sort(key=lambda row: (row["size_mb"], row["tokens_in"]), reverse=True)
    return rows[:limit]


def _advice(model: dict[str, Any], large_tasks: list[dict[str, Any]]) -> list[str]:
    tips: list[str] = []
    if not model["api_ok"]:
        tips.append("Start LM Studio server on port 1234, then load the local model.")
    elif not model["loaded"]:
        tips.append("Load qwen/qwen3.5-9b in LM Studio before retrying Cline.")
    elif not model["context_target_met"]:
        tips.append(
            "Reload model: lms unload qwen/qwen3.5-9b; "
            "lms load qwen/qwen3.5-9b --context-length 131072 --parallel 1 --gpu max "
            "--identifier qwen/qwen3.5-9b -y"
        )
    if large_tasks and large_tasks[0]["size_mb"] >= 1:
        tips.append("Do not press Retry on the failed Cline task. Start a fresh compact task or clear/archive the bloated task.")
    tips.append("If a tool result contains base64 screenshots or huge JSON, discard it and switch to DOM/status diagnostics.")
    return tips


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Cline + LM Studio context health.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--context-target", type=int, default=DEFAULT_CONTEXT_TARGET)
    parser.add_argument("--json-output", action="store_true")
    args = parser.parse_args()

    model = _model_status(args.model, args.context_target)
    large_tasks = _large_cline_tasks()
    payload = {
        "ok": bool(model["api_ok"] and model["loaded"] and model["context_target_met"]),
        "model": model,
        "lms_ps": _lms_ps(),
        "large_cline_tasks": large_tasks,
        "advice": _advice(model, large_tasks),
    }
    if args.json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"ok={payload['ok']}")
        print(payload["lms_ps"])
        for tip in payload["advice"]:
            print(f"- {tip}")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
