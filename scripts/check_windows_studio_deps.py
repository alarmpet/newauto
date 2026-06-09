from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]


def _run(command: list[str], timeout_sec: int = 15) -> tuple[int | None, str]:
    try:
        completed = subprocess.run(
            command,
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_sec,
            stdin=subprocess.DEVNULL,
            check=False,
        )
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"
    output = "\n".join(part for part in (completed.stdout.strip(), completed.stderr.strip()) if part)
    return completed.returncode, output[:1200]


def _tool_check(name: str, command: list[str], *, required: bool = True) -> dict[str, Any]:
    executable = shutil.which(command[0])
    if executable is None:
        return {
            "name": name,
            "ok": not required,
            "required": required,
            "found": False,
            "command": command,
            "message": f"{command[0]} not found on PATH.",
        }
    resolved_command = [executable, *command[1:]]
    rc, output = _run(resolved_command)
    return {
        "name": name,
        "ok": rc == 0,
        "required": required,
        "found": True,
        "path": executable,
        "command": resolved_command,
        "exit_code": rc,
        "output": output,
    }


def _python_module_check(module: str, *, required: bool = True) -> dict[str, Any]:
    rc, output = _run([sys.executable, "-c", f"import {module}; print({module!r})"])
    return {
        "name": f"python:{module}",
        "ok": rc == 0,
        "required": required,
        "command": [sys.executable, "-c", f"import {module}"],
        "exit_code": rc,
        "output": output,
    }


def build_report() -> dict[str, Any]:
    checks = [
        _tool_check("python", [sys.executable, "--version"]),
        _tool_check("node", ["node", "--version"]),
        _tool_check("npm", ["npm", "--version"]),
        _tool_check("tauri_cli", ["npx", "tauri", "--version"]),
        _tool_check("cargo", ["cargo", "--version"]),
        _tool_check("rustc", ["rustc", "--version"]),
        _tool_check("ffmpeg", ["ffmpeg", "-version"], required=False),
        _python_module_check("fastapi"),
        _python_module_check("uvicorn"),
        _python_module_check("PyInstaller", required=False),
    ]
    missing_required = [item["name"] for item in checks if item["required"] and not item["ok"]]
    return {
        "ok": not missing_required,
        "root": str(ROOT_DIR),
        "missing_required": missing_required,
        "checks": checks,
        "next_actions": _next_actions(missing_required),
    }


def _next_actions(missing_required: list[str]) -> list[str]:
    actions: list[str] = []
    if "cargo" in missing_required or "rustc" in missing_required:
        actions.append("Install Rust from https://rustup.rs or winget install Rustlang.Rustup.")
    if "tauri_cli" in missing_required:
        actions.append("Run npm install in the repository root.")
    if "python:fastapi" in missing_required or "python:uvicorn" in missing_required:
        actions.append("Install Python dependencies from requirements.txt.")
    return actions


def main() -> int:
    report = build_report()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
