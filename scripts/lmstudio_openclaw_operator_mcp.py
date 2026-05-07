from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CWD = ROOT_DIR
LOG_DIR = ROOT_DIR / "storage" / "operator_logs"
MAX_OUTPUT_CHARS = 24000
MAX_READ_CHARS = 120000

INSTRUCTIONS = """
You are the OpenClaw-style local operator MCP for LM Studio + Gemma4.

This server intentionally grants broad local authority similar to the user's
OpenClaw sandbox=off/tools=full setup. Use it only when the user explicitly
asks you to inspect, run, repair, edit, start, or diagnose local resources.

Available authority:
- Run PowerShell commands on the local Windows machine.
- Read and write local text files.
- List directories.
- Open URLs or local paths through the OS shell.
- Inspect recent operator command logs.

Rules:
- Prefer purpose-built workflow tools first when they exist.
- Use this operator when the workflow MCP is broken, missing, or needs local repair.
- Keep commands scoped and explain the result in Korean.
- Do not print secret values such as tokens, cookies, API keys, or credentials.
- If you read a config file that contains secrets, summarize the structure only.
- Destructive operations require a direct user request naming the target.
"""

mcp = FastMCP(
    name="openclaw-operator",
    log_level="ERROR",
    instructions=INSTRUCTIONS,
)


def _configure_stdout() -> None:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")


def _clamp_timeout(timeout_sec: int) -> int:
    if timeout_sec < 1:
        return 1
    if timeout_sec > 600:
        return 600
    return timeout_sec


def _resolve_cwd(cwd: str) -> Path:
    if cwd.strip():
        return Path(cwd).expanduser().resolve()
    return DEFAULT_CWD


def _truncate(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    if len(text) <= limit:
        return text
    omitted = len(text) - limit
    return text[:limit] + f"\n\n[truncated {omitted} chars]"


def _redact(text: str) -> str:
    redacted_lines: list[str] = []
    secret_markers = (
        "token",
        "apikey",
        "api_key",
        "secret",
        "password",
        "cookie",
        "authorization",
        "botToken",
        "bearer",
    )
    for line in text.splitlines():
        lower = line.lower()
        if any(marker.lower() in lower for marker in secret_markers):
            redacted_lines.append("[redacted secret-like line]")
        else:
            redacted_lines.append(line)
    return "\n".join(redacted_lines)


def _append_log(entry: dict[str, object]) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / f"operator-{time.strftime('%Y-%m-%d')}.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    return path


def _run(command: str, cwd: str, timeout_sec: int) -> tuple[int | None, str, str, Path]:
    resolved_cwd = _resolve_cwd(cwd)
    start = time.time()
    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                command,
            ],
            cwd=str(resolved_cwd),
            capture_output=True,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=_clamp_timeout(timeout_sec),
            encoding="utf-8",
            errors="replace",
        )
        exit_code: int | None = completed.returncode
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
    except subprocess.TimeoutExpired as exc:
        exit_code = None
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = f"timeout after {_clamp_timeout(timeout_sec)}s"
    except OSError as exc:
        exit_code = None
        stdout = ""
        stderr = f"{type(exc).__name__}: {exc}"

    log_path = _append_log(
        {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "tool": "run_powershell",
            "cwd": str(resolved_cwd),
            "command": command,
            "timeout_sec": _clamp_timeout(timeout_sec),
            "elapsed_sec": round(time.time() - start, 3),
            "exit_code": exit_code,
            "stdout_chars": len(stdout),
            "stderr_chars": len(stderr),
        }
    )
    return exit_code, stdout, stderr, log_path


@mcp.tool()
def operator_status() -> str:
    """Show the local operator authority surface and current runtime identity."""
    _configure_stdout()
    return (
        "=== openclaw-operator status ===\n"
        f"script: {Path(__file__).resolve()}\n"
        f"cwd: {ROOT_DIR}\n"
        f"python: {sys.executable}\n"
        f"pid: {os.getpid()}\n"
        "authority: OpenClaw-style local full operator via MCP\n"
        "tools: run_powershell, read_text_file, write_text_file, list_directory, open_target, recent_operator_logs\n"
        "secret_policy: secret-like lines are redacted in read_text_file and recent logs"
    )


@mcp.tool()
def run_powershell(command: str, cwd: str = "", timeout_sec: int = 60) -> str:
    """Run a local PowerShell command with broad OpenClaw-style authority."""
    _configure_stdout()
    exit_code, stdout, stderr, log_path = _run(command, cwd, timeout_sec)
    output = _truncate(stdout)
    error = _truncate(stderr)
    return (
        "=== run_powershell result ===\n"
        f"exit_code: {exit_code if exit_code is not None else 'timeout/error'}\n"
        f"log: {log_path}\n"
        "\n--- stdout ---\n"
        f"{output if output.strip() else '(empty)'}\n"
        "\n--- stderr ---\n"
        f"{error if error.strip() else '(empty)'}"
    )


@mcp.tool()
def read_text_file(path: str, max_chars: int = MAX_READ_CHARS, redact_secrets: bool = True) -> str:
    """Read a local UTF-8 text file, optionally redacting secret-like lines."""
    _configure_stdout()
    file_path = Path(path).expanduser().resolve()
    if max_chars < 1:
        max_chars = 1
    if max_chars > MAX_READ_CHARS:
        max_chars = MAX_READ_CHARS
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"read_text_file error: {type(exc).__name__}: {exc}"
    if redact_secrets:
        text = _redact(text)
    return (
        "=== read_text_file ===\n"
        f"path: {file_path}\n"
        f"chars_total: {len(text)}\n"
        f"redacted: {redact_secrets}\n\n"
        f"{_truncate(text, max_chars)}"
    )


@mcp.tool()
def write_text_file(path: str, content: str, append: bool = False) -> str:
    """Write or append UTF-8 text to a local file."""
    _configure_stdout()
    file_path = Path(path).expanduser().resolve()
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        if append:
            with file_path.open("a", encoding="utf-8", newline="") as handle:
                handle.write(content)
        else:
            file_path.write_text(content, encoding="utf-8", newline="")
    except OSError as exc:
        return f"write_text_file error: {type(exc).__name__}: {exc}"
    _append_log(
        {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "tool": "write_text_file",
            "path": str(file_path),
            "append": append,
            "chars": len(content),
        }
    )
    return f"write_text_file ok: {file_path} ({len(content)} chars, append={append})"


@mcp.tool()
def list_directory(path: str = "", recursive: bool = False, limit: int = 200) -> str:
    """List files and directories under a local path."""
    _configure_stdout()
    root = _resolve_cwd(path)
    if limit < 1:
        limit = 1
    if limit > 1000:
        limit = 1000
    try:
        iterator = root.rglob("*") if recursive else root.iterdir()
        lines: list[str] = []
        for index, item in enumerate(iterator):
            if index >= limit:
                lines.append(f"... truncated at {limit} entries")
                break
            kind = "dir" if item.is_dir() else "file"
            try:
                size = item.stat().st_size if item.is_file() else 0
            except OSError:
                size = 0
            lines.append(f"{kind}\t{size}\t{item}")
    except OSError as exc:
        return f"list_directory error: {type(exc).__name__}: {exc}"
    return "=== list_directory ===\n" + "\n".join(lines)


@mcp.tool()
def open_target(target: str) -> str:
    """Open a URL or local path with the Windows shell."""
    _configure_stdout()
    command = f"Start-Process -FilePath {json.dumps(target)}"
    exit_code, stdout, stderr, log_path = _run(command, str(ROOT_DIR), 30)
    return (
        "=== open_target ===\n"
        f"target: {target}\n"
        f"exit_code: {exit_code if exit_code is not None else 'timeout/error'}\n"
        f"log: {log_path}\n"
        f"stdout: {_truncate(stdout, 2000) if stdout.strip() else '(empty)'}\n"
        f"stderr: {_truncate(stderr, 2000) if stderr.strip() else '(empty)'}"
    )


@mcp.tool()
def recent_operator_logs(max_lines: int = 40) -> str:
    """Read recent operator logs with secret-like lines redacted."""
    _configure_stdout()
    if max_lines < 1:
        max_lines = 1
    if max_lines > 200:
        max_lines = 200
    if not LOG_DIR.exists():
        return "No operator logs yet."
    files = sorted(LOG_DIR.glob("operator-*.jsonl"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not files:
        return "No operator logs yet."
    lines = files[0].read_text(encoding="utf-8", errors="replace").splitlines()[-max_lines:]
    return "=== recent_operator_logs ===\n" + _redact("\n".join(lines))


def main() -> None:
    _configure_stdout()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
