from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

MCP_PYTHON = Path.home() / "local-rag" / ".venv" / "Scripts" / "python.exe"
try:
    import mcp  # noqa: F401
except ModuleNotFoundError:
    current = Path(sys.executable).resolve()
    if MCP_PYTHON.exists() and current != MCP_PYTHON.resolve():
        os.execv(str(MCP_PYTHON), [str(MCP_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]])
    raise

from scripts import newauto_stepwise_mcp as stepwise


EVAL_DIR = ROOT_DIR / "storage" / "agent_evals"
MEMORY_DIR = ROOT_DIR / "storage" / "agent_memory"
LESSONS_PATH = MEMORY_DIR / "lessons.jsonl"
CLINE_MCP_SETTINGS = (
    Path(os.environ.get("APPDATA", ""))
    / "Code"
    / "User"
    / "globalStorage"
    / "saoudrizwan.claude-dev"
    / "settings"
    / "cline_mcp_settings.json"
)
OPERATOR_LOG_DIR = ROOT_DIR / "storage" / "operator_logs"
API_PORT = int(os.environ.get("NEWAUTO_API_PORT", "9002"))
SECRET_RE = re.compile(
    r"(?i)(token|password|passwd|secret|api[_-]?key|authorization|bearer|cookie)\s*[:=]\s*[^,\s\"']+"
)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _check(name: str, func: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    start = time.time()
    try:
        payload = func()
        ok = bool(payload.pop("ok", True))
        return {
            "name": name,
            "ok": ok,
            "elapsed_sec": round(time.time() - start, 3),
            **payload,
        }
    except Exception as exc:
        return {
            "name": name,
            "ok": False,
            "elapsed_sec": round(time.time() - start, 3),
            "error": f"{type(exc).__name__}: {exc}",
        }


def _redact(value: object) -> object:
    if isinstance(value, str):
        return SECRET_RE.sub(lambda match: f"{match.group(1)}=[REDACTED]", value)
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _redact(item) for key, item in value.items()}
    return value


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _run_text(command: list[str], timeout_sec: int = 10) -> tuple[int | None, str, str]:
    try:
        completed = subprocess.run(
            command,
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
        )
    except Exception as exc:
        return None, "", f"{type(exc).__name__}: {exc}"
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def _metadata_check(project_id: str) -> dict[str, Any]:
    metadata = stepwise._agentic_metadata(project_id)
    required_tools = {
        "diagnose_runtime",
        "forensic_diagnose",
        "start_video_workflow",
        "continue_video_workflow",
        "check_assets",
        "generate_one_image",
        "repair_runtime",
        "search_web",
        "operator_status",
        "ask_openrouter_subagent",
        "run_powershell",
    }
    visible_tools = set(str(item) for item in metadata.get("visible_tools", []))
    missing = sorted(required_tools - visible_tools)
    return {
        "ok": not missing and metadata.get("agentic_mode") == "enabled",
        "missing_tools": missing,
        "context_target": metadata.get("context_target"),
        "loaded_model": metadata.get("loaded_model", ""),
        "loaded_context_length": metadata.get("loaded_context_length", 0),
        "loaded_models": metadata.get("loaded_models", []),
        "lmstudio_api_ok": metadata.get("lmstudio_api_ok", False),
        "context_target_met": metadata.get("context_target_met", False),
        "flow_window_ready": metadata.get("flow_window_ready"),
        "desktop_locked": metadata.get("desktop_locked"),
        "recommended_next_tool": metadata.get("recommended_next_tool"),
    }


def _lmstudio_version_check() -> dict[str, Any]:
    rc, stdout, stderr = _run_text(["lms", "--version"], timeout_sec=10)
    if rc is None or rc != 0:
        rc, stdout, stderr = _run_text([str(Path.home() / ".lmstudio" / "bin" / "lms.exe"), "--version"], timeout_sec=10)
    metadata = stepwise._agentic_metadata("")
    loaded_models = metadata.get("loaded_models", [])
    primary = loaded_models[0] if isinstance(loaded_models, list) and loaded_models else {}
    return {
        "ok": bool(metadata.get("lmstudio_api_ok")),
        "lms_cli_exit_code": rc,
        "lms_cli_version": stdout[:300],
        "lms_cli_error": stderr[:300],
        "loaded_model": metadata.get("loaded_model", ""),
        "loaded_context_length": metadata.get("loaded_context_length", 0),
        "quantization": primary.get("quantization", "") if isinstance(primary, dict) else "",
        "capabilities": primary.get("capabilities", []) if isinstance(primary, dict) else [],
        "python_executable": sys.executable,
        "python_version": sys.version,
    }


def _diagnose_check(project_id: str) -> dict[str, Any]:
    text = stepwise.diagnose_runtime(project_id)
    return {
        "ok": "=== agentic_metadata_json ===" in text and "=== newauto MCP Runtime Diagnosis ===" in text,
        "chars": len(text),
        "has_agentic_metadata_json": "=== agentic_metadata_json ===" in text,
        "has_runtime_diagnosis": "=== newauto MCP Runtime Diagnosis ===" in text,
    }


def _cline_config_check() -> dict[str, Any]:
    payload = _load_json(CLINE_MCP_SETTINGS)
    servers = payload.get("mcpServers", {})
    if not isinstance(servers, dict):
        servers = {}
    required = {
        "newauto-stepwise",
        "playwright",
        "browser-use",
        "computer-use",
        "sequential-thinking",
        "memory",
        "context7",
    }
    missing = sorted(required - set(servers))
    key_summary: dict[str, dict[str, object]] = {}
    for name, config in servers.items():
        if not isinstance(config, dict):
            continue
        key_summary[str(name)] = {
            "has_autoApprove": "autoApprove" in config,
            "has_alwaysAllow": "alwaysAllow" in config,
            "disabled": config.get("disabled", False),
            "timeoutInSeconds": config.get("timeoutInSeconds", None),
            "transportType": config.get("transportType", "stdio"),
        }
    return {
        "ok": not missing and bool(key_summary),
        "settings_path": str(CLINE_MCP_SETTINGS),
        "missing_servers": missing,
        "server_count": len(servers),
        "key_summary": key_summary,
        "canonical_key_observed": "autoApprove"
        if any(item.get("has_autoApprove") for item in key_summary.values())
        else "alwaysAllow"
        if any(item.get("has_alwaysAllow") for item in key_summary.values())
        else "none",
    }


def _search_check() -> dict[str, Any]:
    text = stepwise.search_web("Playwright official docs browser automation", 3)
    lower = text.lower()
    return {
        "ok": "playwright" in lower,
        "chars": len(text),
        "preview": text[:500],
    }


def _powershell_check() -> dict[str, Any]:
    safe_text = stepwise.run_powershell("Write-Output 'operator-smoke-ok'", "", 30, False)
    blocked_text = stepwise.run_powershell("Remove-Item .\\definitely-do-not-delete.tmp", "", 30, False)
    return {
        "ok": "operator-smoke-ok" in safe_text and "approval_required" in blocked_text,
        "safe_command_ok": "operator-smoke-ok" in safe_text,
        "destructive_policy_ok": "approval_required" in blocked_text,
    }


def _flow_readiness_check(project_id: str) -> dict[str, Any]:
    metadata = stepwise._agentic_metadata(project_id)
    return {
        "ok": metadata.get("desktop_locked") is not True,
        "desktop_locked": metadata.get("desktop_locked"),
        "flow_window_ready": metadata.get("flow_window_ready"),
        "foreground_hwnd": metadata.get("foreground_hwnd"),
    }


def _stdin_guard_check() -> dict[str, Any]:
    risky: list[str] = []
    for rel_path in ("scripts/newauto_mcp.py", "scripts/newauto_stepwise_mcp.py"):
        path = ROOT_DIR / rel_path
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            if "subprocess.run(" not in line and "subprocess.Popen(" not in line:
                continue
            window = "\n".join(lines[index:index + 16])
            if "stdin=" not in window and "input=" not in window:
                risky.append(f"{rel_path}:{index + 1}")
    return {
        "ok": not risky,
        "missing_stdin_locations": risky,
    }


def _resolve_omnivoice_python() -> str:
    script = ROOT_DIR / "scripts" / "resolve_omnivoice_python.ps1"
    rc, stdout, _stderr = _run_text(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        timeout_sec=20,
    )
    return stdout.strip() if rc == 0 else ""


def _api_port_process() -> dict[str, object]:
    command = (
        "$ownerPid=(Get-NetTCPConnection "
        f"-LocalPort {API_PORT} -State Listen -ErrorAction SilentlyContinue | "
        "Select-Object -First 1 -ExpandProperty OwningProcess); "
        "if ($ownerPid) { "
        "$p=Get-CimInstance Win32_Process -Filter \"ProcessId=$ownerPid\"; "
        "$parent=Get-CimInstance Win32_Process -Filter \"ProcessId=$($p.ParentProcessId)\" -ErrorAction SilentlyContinue; "
        "[pscustomobject]@{"
        "ProcessId=$p.ProcessId;"
        "ExecutablePath=$p.ExecutablePath;"
        "CommandLine=$p.CommandLine;"
        "ParentProcessId=$p.ParentProcessId;"
        "ParentExecutablePath=$parent.ExecutablePath;"
        "ParentCommandLine=$parent.CommandLine"
        "} | ConvertTo-Json -Compress "
        "}"
    )
    rc, stdout, _stderr = _run_text(["powershell", "-NoProfile", "-Command", command], timeout_sec=20)
    if rc != 0 or not stdout:
        return {}
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _runtime_mismatch_check() -> dict[str, Any]:
    expected_python = _resolve_omnivoice_python()
    process = _api_port_process()
    executable = str(process.get("ExecutablePath") or "")
    command_line = str(process.get("CommandLine") or "")
    parent_executable = str(process.get("ParentExecutablePath") or "")
    parent_command_line = str(process.get("ParentCommandLine") or "")
    expected_norm = expected_python.lower().replace("/", "\\")
    actual_norm = executable.lower().replace("/", "\\")
    command_norm = command_line.lower().replace("/", "\\")
    parent_actual_norm = parent_executable.lower().replace("/", "\\")
    parent_command_norm = parent_command_line.lower().replace("/", "\\")
    listener_present = bool(process)
    matches = bool(expected_norm) and (
        actual_norm == expected_norm or expected_norm in command_norm
        or parent_actual_norm == expected_norm or expected_norm in parent_command_norm
    )
    return {
        "ok": True,
        "api_port": API_PORT,
        "listener_present": listener_present,
        "runtime_matches_expected": matches if listener_present else None,
        "warning": "" if (not listener_present or matches) else f"port_{API_PORT}_runtime_mismatch",
        "expected_python": expected_python,
        "process": process,
    }


def _recent_operator_entries(limit: int = 200) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    files = sorted(OPERATOR_LOG_DIR.glob("operator-*.jsonl"), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in files[:3]:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines[-limit:]:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                entries.append(payload)
    return entries[-limit:]


def _repeated_call_check() -> dict[str, Any]:
    entries = _recent_operator_entries()
    counts: dict[str, int] = {}
    ignored_commands = {"Write-Output 'operator-smoke-ok'", "Remove-Item .\\definitely-do-not-delete.tmp"}
    for entry in entries:
        tool = str(entry.get("tool") or "")
        command = str(entry.get("command") or "")
        if command in ignored_commands:
            continue
        key = json.dumps(
            {
                "tool": tool,
                "command": command,
                "cwd": str(entry.get("cwd") or ""),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        counts[key] = counts.get(key, 0) + 1
    repeated = [
        {"key": key, "count": count}
        for key, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)
        if count >= 3
    ]
    return {
        "ok": True,
        "repeated_call_warnings": repeated[:10],
        "entries_scanned": len(entries),
    }


def _openrouter_smoke_check(live: bool = False) -> dict[str, Any]:
    from scripts import openrouter_subagent_harness as openrouter

    result = openrouter.run_harness(
        mode="review",
        task="Smoke redaction check: api_key=abc123 token=secret123. Return a compact diagnosis.",
        files=["openrouter.txt"],
        dry_run=True,
        max_input_chars=6000,
    )
    packed = result.packed_context or {}
    serialized = json.dumps(packed, ensure_ascii=False, sort_keys=True)
    redaction_ok = "abc123" not in serialized and "secret123" not in serialized
    denied_path_ok = any(
        isinstance(item, dict) and item.get("blocked") and item.get("reason") == "denied_path"
        for item in packed.get("files", [])
    )
    payload: dict[str, Any] = {
        "ok": redaction_ok and denied_path_ok,
        "dry_run_ok": bool(result.ok),
        "redaction_ok": redaction_ok,
        "denied_path_ok": denied_path_ok,
        "budget": openrouter.budget_status(),
        "live_requested": live,
        "live_skipped": True,
    }
    if not live:
        return payload

    configured_model = (
        os.environ.get("OPENROUTER_MODEL_REVIEWER")
        or os.environ.get("OPENROUTER_MODEL")
        or ""
    ).strip()
    api_key, key_source = openrouter.load_api_key()
    payload["key_source"] = key_source
    if not api_key:
        payload["live_skip_reason"] = "missing_api_key"
        return payload
    if not configured_model:
        payload["live_skip_reason"] = "missing_model"
        return payload
    live_result = openrouter.run_harness(
        mode="review",
        task="Return JSON only: diagnose a fake pytest import error and suggest one verification command.",
        model=configured_model,
        essential=False,
        timeout_sec=45,
    )
    payload["live_skipped"] = bool(live_result.skipped)
    payload["live_ok"] = bool(live_result.ok and live_result.response)
    payload["live_model"] = live_result.model
    payload["live_usage"] = live_result.usage
    payload["ok"] = bool(payload["ok"] and payload["live_ok"])
    return payload


def _latest_prior_report() -> dict[str, Any]:
    paths = sorted(
        [Path(path) for path in glob.glob(str(EVAL_DIR / "agent-smoke-*.json"))],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in paths:
        payload = _load_json(path)
        if payload:
            payload["_path"] = str(path)
            return payload
    return {}


def _regression_diff(current: dict[str, Any], prior: dict[str, Any]) -> dict[str, Any]:
    if not prior:
        return {"prior_report": "", "new_failed_checks": [], "changed_fields": {}}
    current_checks = {str(item.get("name")): bool(item.get("ok")) for item in current.get("checks", [])}
    prior_checks = {str(item.get("name")): bool(item.get("ok")) for item in prior.get("checks", [])}
    new_failed = [
        name for name, ok in current_checks.items()
        if not ok and prior_checks.get(name, True)
    ]
    changed_fields: dict[str, object] = {}
    for key in ("model", "loaded_context_length"):
        if current.get(key) != prior.get(key):
            changed_fields[key] = {"prior": prior.get(key), "current": current.get(key)}
    return {
        "prior_report": prior.get("_path", ""),
        "new_failed_checks": new_failed,
        "changed_fields": changed_fields,
    }


def _write_report(report: dict[str, Any]) -> Path:
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    path = EVAL_DIR / f"agent-smoke-{time.strftime('%Y%m%d-%H%M%S')}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _append_lesson(report: dict[str, Any]) -> None:
    failed = [item for item in report["checks"] if not item.get("ok")]
    regression = report.get("regression_diff", {})
    warnings = [
        item for item in report["checks"]
        if item.get("warning") or item.get("repeated_call_warnings")
    ]
    if not failed and not regression.get("new_failed_checks") and not warnings:
        return
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    lesson = {
        "timestamp": report["timestamp"],
        "task": "agent_eval_smoke",
        "model": report.get("model", "local"),
        "context_length": report.get("loaded_context_length", 0),
        "tools_used": ["diagnose_runtime", "search_web", "run_powershell"],
        "symptom": "; ".join(str(item["name"]) for item in [*failed, *warnings]) or "regression_diff",
        "verified_cause": "see failed checks, warnings, and regression_diff in report",
        "fix_applied": "",
        "verification": str(report.get("report_path", "")),
        "reusable_lesson": "Treat new smoke failures or transport/runtime warnings as regressions until verified.",
        "secrets_redacted": True,
    }
    signature_keys = ("task", "model", "symptom", "verified_cause", "reusable_lesson")
    signature = {key: lesson.get(key) for key in signature_keys}
    if LESSONS_PATH.exists():
        try:
            last_line = next((line for line in reversed(LESSONS_PATH.read_text(encoding="utf-8").splitlines()) if line.strip()), "")
            if last_line:
                prior = json.loads(last_line)
                prior_signature = {key: prior.get(key) for key in signature_keys}
                if prior_signature == signature:
                    return
        except Exception:
            pass
    with LESSONS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_redact(lesson), ensure_ascii=False, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run agentic MCP smoke checks and persist eval output.")
    parser.add_argument("--project-id", default="", help="Optional newauto project id.")
    parser.add_argument("--skip-web", action="store_true", help="Skip DuckDuckGo-backed search_web smoke.")
    parser.add_argument("--skip-shell", action="store_true", help="Skip run_powershell smoke.")
    parser.add_argument("--skip-openrouter", action="store_true", help="Skip OpenRouter subagent dry-run smoke.")
    parser.add_argument("--openrouter-live", action="store_true", help="Spend one OpenRouter :free request for live smoke when model/key are configured.")
    args = parser.parse_args()

    checks: list[dict[str, Any]] = [
        _check("agentic_metadata", lambda: _metadata_check(args.project_id)),
        _check("lmstudio_version_runtime", _lmstudio_version_check),
        _check("cline_mcp_config", _cline_config_check),
        _check("diagnose_runtime", lambda: _diagnose_check(args.project_id)),
        _check("flow_readiness", lambda: _flow_readiness_check(args.project_id)),
        _check("stdin_guard", _stdin_guard_check),
        _check("runtime_mismatch", _runtime_mismatch_check),
        _check("repeated_call_detector", _repeated_call_check),
    ]
    if not args.skip_web:
        checks.append(_check("search_web", _search_check))
    if not args.skip_shell:
        checks.append(_check("powershell_policy", _powershell_check))
    if not args.skip_openrouter:
        checks.append(_check("openrouter_subagent", lambda: _openrouter_smoke_check(args.openrouter_live)))

    metadata = stepwise._agentic_metadata(args.project_id)
    prior_report = _latest_prior_report()
    report: dict[str, Any] = {
        "timestamp": _now(),
        "project_id": args.project_id,
        "model": metadata.get("loaded_model", ""),
        "loaded_context_length": metadata.get("loaded_context_length", 0),
        "checks": checks,
        "ok": all(item.get("ok") for item in checks),
    }
    report["regression_diff"] = _regression_diff(report, prior_report)
    report_path = _write_report(report)
    report["report_path"] = str(report_path)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    _append_lesson(report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
