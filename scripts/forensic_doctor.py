"""Forensic diagnostic tool for the newauto pipeline.

Designed to be called by Cline + LM Studio (or any small LLM) when a tool
returns a timeout / error / vague failure. Replaces the LLM's role of
"figure out what's wrong" with deterministic checks. The LLM's job
becomes: read `critical_findings`, pick one of `recommended_actions`.

Usage:
    python scripts/forensic_doctor.py --json
    python scripts/forensic_doctor.py --project-id 63243581a058 --json
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SERVER_BASE = os.environ.get(
    "NEWAUTO_BASE",
    os.environ.get("NEWAUTO_BASE_URL", "http://127.0.0.1:9002"),
)
LMSTUDIO_BASE = os.environ.get("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234")
COMFYUI_BASE = os.environ.get("COMFYUI_BASE_URL", "http://127.0.0.1:8188")
OPERATOR_LOG_DIR = ROOT / "storage" / "operator_logs"
LOG_DIR = ROOT / "storage" / "logs"
PROJECTS_DIR = ROOT / "storage" / "projects"
DB_PATH = ROOT / "storage" / "app.db"

VENVS: dict[str, Path] = {
    "omnivoice_env": ROOT / "omnivoice_env" / "Scripts" / "python.exe",
    "local-rag": Path.home() / "local-rag" / ".venv" / "Scripts" / "python.exe",
}
REQUIRED_MODULES: dict[str, list[str]] = {
    "omnivoice_env": ["fastapi", "uvicorn", "requests"],
    "local-rag": ["pyautogui", "pygetwindow", "pyscreeze", "PIL", "playwright"],
}


def _http_alive(url: str, timeout: float = 3.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            r.read(64)
            return True
    except Exception:
        return False


def check_servers() -> dict[str, bool]:
    return {
        "newauto_api": _http_alive(f"{SERVER_BASE}/health"),
        "lmstudio_1234": _http_alive(f"{LMSTUDIO_BASE}/v1/models"),
        "comfyui_8188": _http_alive(f"{COMFYUI_BASE}/system_stats"),
    }


def check_venv(name: str, python_path: Path, modules: list[str]) -> dict[str, Any]:
    if not python_path.exists():
        return {"exists": False, "missing": modules, "python": ""}
    code = (
        "import importlib.util,sys,json;"
        f"mods={modules!r};"
        "missing=[m for m in mods if importlib.util.find_spec(m) is None];"
        "print(json.dumps({'python':sys.version.split()[0],'missing':missing}))"
    )
    try:
        out = subprocess.run(
            [str(python_path), "-c", code],
            capture_output=True, text=True, timeout=10,
            encoding="utf-8", errors="replace",
        )
        line = (out.stdout or "").strip().splitlines()
        if not line:
            return {"exists": True, "error": (out.stderr or "")[:200]}
        return {"exists": True, **json.loads(line[-1])}
    except Exception as exc:
        return {"exists": True, "error": str(exc)[:200]}


def check_processes() -> dict[str, Any]:
    cmd = (
        "Get-Process | Select-Object ProcessName, Id, MainWindowTitle | "
        "ConvertTo-Json -Compress -Depth 2"
    )
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "$OutputEncoding=[System.Text.Encoding]::UTF8; "
             "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; " + cmd],
            capture_output=True, text=True, timeout=10,
            encoding="utf-8", errors="replace",
        )
        if not (out.stdout or "").strip():
            return {"error": "powershell returned empty"}
        procs = json.loads(out.stdout)
        if isinstance(procs, dict):
            procs = [procs]
        names = [p.get("ProcessName", "").lower() for p in procs]
        return {
            "chrome_count": sum(1 for n in names if n == "chrome"),
            "msedgewebview2_count": sum(1 for n in names if n == "msedgewebview2"),
        }
    except Exception as exc:
        return {"error": str(exc)[:200]}


def _process_command_lines() -> list[dict[str, Any]]:
    script = (
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.Name -match 'python|uvicorn' -or $_.CommandLine -match 'uvicorn|newauto|run_tts_job|tts_worker' } | "
        "Select-Object ProcessId,Name,ExecutablePath,CommandLine | "
        "ConvertTo-Json -Compress -Depth 3"
    )
    try:
        out = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "$OutputEncoding=[System.Text.Encoding]::UTF8; "
                "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
                + script,
            ],
            capture_output=True,
            text=True,
            timeout=10,
            encoding="utf-8",
            errors="replace",
        )
        if not (out.stdout or "").strip():
            return []
        payload = json.loads(out.stdout)
        if isinstance(payload, dict):
            payload = [payload]
        if not isinstance(payload, list):
            return []
        return [
            {
                "pid": item.get("ProcessId"),
                "name": item.get("Name"),
                "exe": item.get("ExecutablePath"),
                "cmd": item.get("CommandLine") or "",
            }
            for item in payload
            if isinstance(item, dict)
        ]
    except Exception:
        return []


def _port_listen_owners(port: int) -> list[int]:
    script = (
        f"Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue | "
        "Select-Object -ExpandProperty OwningProcess | ConvertTo-Json -Compress"
    )
    try:
        out = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "$OutputEncoding=[System.Text.Encoding]::UTF8; "
                "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
                + script,
            ],
            capture_output=True,
            text=True,
            timeout=10,
            encoding="utf-8",
            errors="replace",
        )
        raw = (out.stdout or "").strip()
        if not raw:
            return []
        payload = json.loads(raw)
        if isinstance(payload, int):
            return [payload]
        if isinstance(payload, list):
            return [int(item) for item in payload if str(item).isdigit()]
    except Exception:
        return []
    return []


def _parse_iso(value: str) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _mtime_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False}
    stat = path.stat()
    return {
        "exists": True,
        "size": stat.st_size,
        "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(timespec="seconds"),
    }


def _tts_artifacts(pid: str) -> dict[str, Any]:
    tts_dir = PROJECTS_DIR / pid / "tts"
    audio_files = sorted(tts_dir.glob("*.wav")) if tts_dir.exists() else []
    latest_mtime = 0.0
    for path in audio_files:
        latest_mtime = max(latest_mtime, path.stat().st_mtime)
    return {
        "dir_exists": tts_dir.exists(),
        "timings_json": _mtime_payload(tts_dir / "timings.json"),
        "tts_run_manifest_json": _mtime_payload(tts_dir / "tts_run_manifest.json"),
        "runtime_probe_json": _mtime_payload(tts_dir / "omnivoice_runtime_probe.json"),
        "tts_error_json": _mtime_payload(tts_dir / "tts_error.json"),
        "audio_count": len(audio_files),
        "audio_nonzero_count": sum(1 for path in audio_files if path.stat().st_size > 0),
        "latest_audio_mtime": (
            datetime.fromtimestamp(latest_mtime, timezone.utc).isoformat(timespec="seconds")
            if latest_mtime
            else ""
        ),
    }


def _tts_db_state(pid: str) -> dict[str, Any]:
    if not DB_PATH.exists():
        return {"exists": False, "error": f"database missing: {DB_PATH}"}
    con: sqlite3.Connection | None = None
    try:
        con = sqlite3.connect(DB_PATH)
        con.row_factory = sqlite3.Row
        row = con.execute(
            """
            SELECT id,title,tts_state,tts_progress,tts_error,tts_job_id,tts_started_at,tts_heartbeat_at,updated_at
            FROM projects
            WHERE id=?
            """,
            (pid,),
        ).fetchone()
    except Exception as exc:
        return {"exists": False, "error": f"{type(exc).__name__}: {exc}"}
    finally:
        if con is not None:
            con.close()
    if row is None:
        return {"exists": False, "error": f"project not found: {pid}"}
    payload = dict(row)
    heartbeat_at = _parse_iso(str(payload.get("tts_heartbeat_at") or ""))
    started_at = _parse_iso(str(payload.get("tts_started_at") or ""))
    now = datetime.now(timezone.utc)
    payload["exists"] = True
    payload["tts_progress"] = int(payload.get("tts_progress") or 0)
    payload["heartbeat_age_sec"] = round((now - heartbeat_at).total_seconds(), 1) if heartbeat_at else None
    payload["runtime_age_sec"] = round((now - started_at).total_seconds(), 1) if started_at else None
    return payload


def check_tts_pipeline(pid: str) -> dict[str, Any]:
    if not pid:
        return {}
    processes = _process_command_lines()
    tts_worker = [
        proc for proc in processes
        if "app.workers.tts_worker" in str(proc.get("cmd") or "")
    ]
    run_tts = [
        proc for proc in processes
        if "run_tts_job.py" in str(proc.get("cmd") or "")
        and (pid in str(proc.get("cmd") or ""))
    ]
    api_servers = [
        proc for proc in processes
        if "uvicorn" in str(proc.get("cmd") or "")
        and "app.main:app" in str(proc.get("cmd") or "")
    ]
    api_port_owners = _port_listen_owners(9002)
    return {
        "db": _tts_db_state(pid),
        "artifacts": _tts_artifacts(pid),
        "processes": {
            "tts_worker": tts_worker,
            "run_tts_job": run_tts,
            "api_servers": api_servers,
            "api_port_listen_owners": api_port_owners,
            "tts_worker_live": bool(tts_worker),
            "run_tts_job_live": bool(run_tts),
            "duplicate_api_server": len(set(api_port_owners)) > 1,
        },
    }


def parse_operator_log(hours: int = 6, limit: int = 10) -> list[dict[str, Any]]:
    today = OPERATOR_LOG_DIR / f"operator-{datetime.now():%Y-%m-%d}.jsonl"
    if not today.exists():
        return []
    cutoff = datetime.now() - timedelta(hours=hours)
    failures: list[dict[str, Any]] = []
    try:
        for line in today.read_text(encoding="utf-8").splitlines():
            try:
                entry = json.loads(line)
            except Exception:
                continue
            ts = entry.get("timestamp", "")
            try:
                t = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S")
                if t < cutoff:
                    continue
            except Exception:
                pass
            exit_code = entry.get("exit_code")
            stderr_chars = entry.get("stderr_chars") or 0
            if exit_code not in (0, None) or stderr_chars > 0:
                failures.append({
                    "timestamp": ts,
                    "command": (entry.get("command") or "")[:200],
                    "exit_code": exit_code,
                    "stderr_chars": stderr_chars,
                    "elapsed_sec": entry.get("elapsed_sec"),
                })
    except Exception:
        pass
    return failures[-limit:]


def project_state(pid: str) -> dict[str, Any]:
    pdir = PROJECTS_DIR / pid
    if not pdir.exists():
        return {"exists": False}
    files = {
        p.name: p.stat().st_size
        for p in pdir.iterdir() if p.is_file()
    }
    media = pdir / "media"
    media_count = (
        sum(1 for p in media.iterdir() if p.is_file()) if media.exists() else 0
    )
    flow_status: dict[str, Any] = {}
    flow_json = pdir / "flow_prompts.json"
    if flow_json.exists():
        try:
            data = json.loads(flow_json.read_text(encoding="utf-8"))
            entries = data.get("entries", []) or []
            statuses = Counter(e.get("status") for e in entries)
            flow_status = {
                "total_prompts": len(entries),
                "by_status": dict(statuses),
                "with_asset": sum(1 for e in entries if e.get("asset_path")),
            }
        except Exception:
            flow_status = {"error": "parse_failed"}
    return {
        "exists": True,
        "files": files,
        "media_count": media_count,
        "flow_prompts": flow_status,
        "flow_prompt_files_dir_exists": (pdir / "flow_prompts").exists(),
    }


def synthesize(report: dict[str, Any]) -> tuple[list[str], list[str]]:
    findings: list[str] = []
    actions: list[str] = []

    s = report["servers"]
    if not s["newauto_api"]:
        findings.append(f"CRITICAL: newauto API가 {SERVER_BASE}에서 응답 없음")
        actions.append("작업 폴더에서 .\\run-newauto-9001.cmd 실행")
    if not s["lmstudio_1234"]:
        findings.append("CRITICAL: LM Studio :1234 가 응답 없음")
        actions.append("lms server start 그리고 lms load qwen/qwen3.5-9b --context-length 65536 --parallel 1 --gpu max")

    for name, vh in report["venvs"].items():
        if not vh.get("exists"):
            findings.append(f"venv 없음: {name} (경로 자체 부재)")
            continue
        missing = vh.get("missing") or []
        if missing:
            mods = " ".join(missing)
            findings.append(
                f"{name} (Python {vh.get('python','?')}) 모듈 없음: {','.join(missing)}"
            )
            python_path = VENVS[name]
            actions.append(f"& '{python_path}' -m pip install --upgrade {mods}")

    proj = report.get("project")
    if isinstance(proj, dict) and proj.get("exists"):
        fp = proj.get("flow_prompts") or {}
        total = fp.get("total_prompts", 0)
        with_asset = fp.get("with_asset", 0)
        media_count = proj.get("media_count", 0)
        if total > 0 and with_asset == 0 and media_count == 0:
            findings.append(
                f"Flow 프롬프트 {total}개 생성됐지만 asset 0개, media/ 비어있음"
            )
            actions.append("Run Playwright Flow generation or attach downloaded Flow assets.")
        elif with_asset < total:
            findings.append(f"Flow asset 미완성: {with_asset}/{total}")

    tts = report.get("tts")
    if isinstance(tts, dict) and tts:
        tts_db = tts.get("db") if isinstance(tts.get("db"), dict) else {}
        tts_artifacts = tts.get("artifacts") if isinstance(tts.get("artifacts"), dict) else {}
        tts_processes = tts.get("processes") if isinstance(tts.get("processes"), dict) else {}
        tts_state = str(tts_db.get("tts_state") or "")
        tts_progress = int(tts_db.get("tts_progress") or 0)
        heartbeat_age = tts_db.get("heartbeat_age_sec")
        heartbeat_expired = isinstance(heartbeat_age, (int, float)) and float(heartbeat_age) > 60
        timings_exists = bool((tts_artifacts.get("timings_json") or {}).get("exists"))
        manifest_exists = bool((tts_artifacts.get("tts_run_manifest_json") or {}).get("exists"))
        audio_count = int(tts_artifacts.get("audio_nonzero_count") or 0)
        worker_live = bool(tts_processes.get("tts_worker_live"))
        subprocess_live = bool(tts_processes.get("run_tts_job_live"))
        tts_error = str(tts_db.get("tts_error") or "")

        if tts_processes.get("duplicate_api_server"):
            findings.append("DUPLICATE_API_SERVER: multiple uvicorn app.main:app processes are visible")
            actions.append("Keep only the process owning port 9002, then restart background workers.")

        if tts_state in {"queued", "running"} and not worker_live:
            findings.append("TTS_WORKER_MISSING: tts job is queued/running but app.workers.tts_worker is not live")
            actions.append("Run repair_tts or restart app.workers.tts_worker.")

        if tts_state == "running" and heartbeat_expired:
            findings.append(
                f"TTS_HEARTBEAT_EXPIRED: heartbeat age={heartbeat_age}s progress={tts_progress}%"
            )
            actions.append("Run repair_tts: reset abandoned TTS job to queued and restart tts_worker.")

        if tts_state == "error" and "heartbeat expired" in tts_error.lower():
            findings.append(f"TTS_ERROR_HEARTBEAT_EXPIRED: {tts_error[:200]}")
            actions.append("Run repair_tts: previous TTS worker heartbeat expired and no completed output is expected.")

        if tts_state == "running" and not subprocess_live and not timings_exists:
            findings.append("TTS_SUBPROCESS_MISSING: tts_state=running but run_tts_job.py is not live")
            actions.append("Run repair_tts after confirming no valid TTS artifacts exist.")

        if tts_state in {"running", "error"} and not timings_exists and audio_count == 0:
            findings.append("TTS_OUTPUT_MISSING: no timings.json or nonzero wav output exists")
            actions.append("Run repair_tts if no active run_tts_job.py process exists for this project.")

        if tts_state == "done" and not (timings_exists and manifest_exists and audio_count > 0):
            findings.append(
                "TTS_DONE_OUTPUT_INCOMPLETE: DB says done but timings/manifest/audio artifacts are incomplete"
            )
            actions.append("Reset TTS to queued with repair_tts after preserving any useful logs.")

        probe = tts_artifacts.get("runtime_probe_json") or {}
        if probe.get("exists") and tts_state in {"running", "error"} and not subprocess_live and not timings_exists:
            findings.append("OMNIVOICE_RUNTIME_OK_BUT_JOB_ABORTED: runtime probe exists but TTS output is missing")
            actions.append("Run repair_tts: OmniVoice was resolved, but the local TTS job was abandoned before output.")

    last_fails = report.get("recent_failures") or []
    if last_fails:
        last = last_fails[-1]
        findings.append(
            f"최근 도구 실패: exit={last['exit_code']} "
            f"elapsed={last.get('elapsed_sec')}s "
            f"stderr_chars={last.get('stderr_chars')} "
            f"cmd={last['command'][:120]}"
        )
        if last.get("elapsed_sec", 999) < 2 and last.get("stderr_chars", 0) > 0:
            findings.append(
                "  → 빠른 실패 + stderr 존재. timeout 아니라 import/argument 에러일 가능성 매우 높음"
            )
            actions.append(
                "위 명령을 직접 실행해 stderr 전문을 확인 (subprocess capture)"
            )

    if not findings:
        findings.append("뚜렷한 이상 없음. 작업 진행 가능.")
    return findings, actions


def run_full_diagnosis(project_id: str = "") -> dict[str, Any]:
    report: dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "servers": check_servers(),
        "venvs": {
            name: check_venv(name, path, REQUIRED_MODULES[name])
            for name, path in VENVS.items()
        },
        "processes": check_processes(),
        "recent_failures": parse_operator_log(),
    }
    if project_id:
        report["project_id"] = project_id
        report["project"] = project_state(project_id)
        report["tts"] = check_tts_pipeline(project_id)

    findings, actions = synthesize(report)
    report["critical_findings"] = findings
    report["recommended_actions"] = actions
    report["status"] = (
        "broken" if any("CRITICAL" in f for f in findings)
        else "degraded" if len(findings) > 1
        else "healthy"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Newauto forensic diagnostic")
    parser.add_argument("--project-id", default="", help="optional project to inspect")
    parser.add_argument("--json", action="store_true", help="emit JSON only")
    args = parser.parse_args()

    report = run_full_diagnosis(args.project_id)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    print("=" * 70)
    print(f"Forensic report  {report['timestamp']}  status={report['status']}")
    print("=" * 70)
    print("\n[Critical findings]")
    for f in report["critical_findings"]:
        print(f"  - {f}")
    print("\n[Recommended actions]")
    for i, a in enumerate(report["recommended_actions"], 1):
        print(f"  {i}. {a}")
    print("\n[Servers]", report["servers"])
    print("\n[Venvs]")
    for name, vh in report["venvs"].items():
        print(f"  {name}: {vh}")
    print("\n[Processes]", report["processes"])
    if "project" in report:
        print("\n[Project]", json.dumps(report["project"], ensure_ascii=False))
    if report["recent_failures"]:
        print("\n[Recent failures]")
        for f in report["recent_failures"][-5:]:
            print(f"  {f['timestamp']} exit={f['exit_code']} {f['command'][:120]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
