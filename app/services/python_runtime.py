from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import TypedDict


class OmniVoicePythonStatus(TypedDict):
    resolved: bool
    python_path: str
    omnivoice_import_ok: bool
    torch_import_ok: bool
    cuda_available: bool
    error: str


def _candidate_paths() -> list[str]:
    root_dir = Path(__file__).resolve().parents[2]
    candidates: list[str] = []
    env_python = os.environ.get("OMNIVOICE_PYTHON", "").strip()
    env_dir = os.environ.get("OMNIVOICE_ENV_DIR", "").strip()
    if env_python:
        candidates.append(env_python)
    if env_dir:
        candidates.append(str(Path(env_dir) / "Scripts" / "python.exe"))
    candidates.extend(
        [
            str(root_dir / "omnivoice_env" / "Scripts" / "python.exe"),
            r"C:\Users\petbl\music-auto\.venv_omnivoice\Scripts\python.exe",
            sys.executable,
        ]
    )
    seen: set[str] = set()
    unique: list[str] = []
    for candidate in candidates:
        normalized = candidate.strip()
        if not normalized:
            continue
        lowered = normalized.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        unique.append(normalized)
    return unique


def _unresolved_runtime_status(error: str) -> OmniVoicePythonStatus:
    return {
        "resolved": False,
        "python_path": "",
        "omnivoice_import_ok": False,
        "torch_import_ok": False,
        "cuda_available": False,
        "error": error,
    }


def _select_first_resolved_candidate(candidates: list[OmniVoicePythonStatus]) -> OmniVoicePythonStatus:
    if not candidates:
        return _unresolved_runtime_status("no candidates checked")
    for status in candidates:
        if status["resolved"]:
            return status
    return candidates[-1]


def probe_omnivoice_python(python_path: str) -> OmniVoicePythonStatus:
    candidate = Path(python_path)
    if not candidate.exists():
        return {
            "resolved": False,
            "python_path": python_path,
            "omnivoice_import_ok": False,
            "torch_import_ok": False,
            "cuda_available": False,
            "error": "python executable not found",
        }
    probe_code = (
        "import json\n"
        "payload={'omnivoice_import_ok': False, 'torch_import_ok': False, 'cuda_available': False, 'error': ''}\n"
        "try:\n"
        "    import omnivoice\n"
        "    payload['omnivoice_import_ok']=True\n"
        "except Exception as exc:\n"
        "    payload['error']=f'omnivoice import failed: {exc}'\n"
        "try:\n"
        "    import torch\n"
        "    payload['torch_import_ok']=True\n"
        "    payload['cuda_available']=bool(torch.cuda.is_available())\n"
        "except Exception as exc:\n"
        "    payload['error']=payload['error'] or f'torch import failed: {exc}'\n"
        "print(json.dumps(payload, ensure_ascii=False))\n"
    )
    try:
        completed = subprocess.run(
            [python_path, "-c", probe_code],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            check=False,
        )
    except Exception as exc:
        return {
            "resolved": False,
            "python_path": python_path,
            "omnivoice_import_ok": False,
            "torch_import_ok": False,
            "cuda_available": False,
            "error": str(exc),
        }
    stdout = completed.stdout.strip()
    if completed.returncode != 0 or not stdout:
        return {
            "resolved": False,
            "python_path": python_path,
            "omnivoice_import_ok": False,
            "torch_import_ok": False,
            "cuda_available": False,
            "error": completed.stderr.strip() or "probe returned no output",
        }
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return {
            "resolved": False,
            "python_path": python_path,
            "omnivoice_import_ok": False,
            "torch_import_ok": False,
            "cuda_available": False,
            "error": f"invalid probe output: {stdout[:200]}",
        }
    if not isinstance(payload, dict):
        return {
            "resolved": False,
            "python_path": python_path,
            "omnivoice_import_ok": False,
            "torch_import_ok": False,
            "cuda_available": False,
            "error": "invalid probe payload",
        }
    omnivoice_import_ok = bool(payload.get("omnivoice_import_ok"))
    torch_import_ok = bool(payload.get("torch_import_ok"))
    error = str(payload.get("error") or "")
    return {
        "resolved": omnivoice_import_ok,
        "python_path": python_path,
        "omnivoice_import_ok": omnivoice_import_ok,
        "torch_import_ok": torch_import_ok,
        "cuda_available": bool(payload.get("cuda_available")),
        "error": error,
    }


def probe_omnivoice_python_candidates() -> list[OmniVoicePythonStatus]:
    return [probe_omnivoice_python(candidate) for candidate in _candidate_paths()]


def get_omnivoice_runtime_status() -> OmniVoicePythonStatus:
    candidates = probe_omnivoice_python_candidates()
    return _select_first_resolved_candidate(candidates)


def resolve_omnivoice_python_with_probes() -> tuple[OmniVoicePythonStatus, list[OmniVoicePythonStatus]]:
    candidates = probe_omnivoice_python_candidates()
    return _select_first_resolved_candidate(candidates), candidates


def resolve_omnivoice_python() -> str:
    status, _ = resolve_omnivoice_python_with_probes()
    if not status["resolved"] or not status["python_path"]:
        raise RuntimeError(status["error"] or "No usable OmniVoice Python environment found.")
    return status["python_path"]
