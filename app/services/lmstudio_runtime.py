import json
import subprocess
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from ..config import LMSTUDIO_BASE_URL, SCRIPT_LLM_MODEL


def _lms_exe_path() -> Path:
    return Path.home() / ".lmstudio" / "bin" / "lms.exe"


def loaded_lmstudio_models() -> list[str]:
    lms_exe = _lms_exe_path()
    if lms_exe.is_file():
        try:
            process = subprocess.run(
                [str(lms_exe), "ps"],
                capture_output=True,
                text=True,
                timeout=10,
                stdin=subprocess.DEVNULL,
            )
        except (OSError, subprocess.TimeoutExpired):
            process = None
        if process is not None and process.returncode == 0:
            output = f"{process.stdout}\n{process.stderr}"
            if "No models are currently loaded" in output:
                return []
            models: list[str] = []
            for line in output.splitlines():
                stripped = line.strip()
                if not stripped or stripped.lower().startswith(("loaded", "model", "identifier", "path")):
                    continue
                if stripped.startswith(("To load ", "lms load")):
                    continue
                candidate = stripped.split()[0]
                if "/" in candidate or "\\" in candidate:
                    models.append(candidate)
            if models:
                return models
    request = Request(
        urljoin(LMSTUDIO_BASE_URL.rstrip("/") + "/", "v1/models"),
        headers={"Accept": "application/json"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except (OSError, URLError, json.JSONDecodeError):
        return []
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        return []
    models: list[str] = []
    for item in data:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            models.append(item["id"])
    return models


def unload_lmstudio_model(model: str | None = None) -> dict[str, object]:
    model_name = (model or SCRIPT_LLM_MODEL or "").strip()
    lms_exe = _lms_exe_path()
    if not model_name:
        return {"ok": False, "method": "lms.exe", "error": "LM Studio model name is empty."}
    if not lms_exe.is_file():
        return {"ok": False, "method": "lms.exe", "model": model_name, "error": f"lms.exe not found: {lms_exe}"}
    try:
        process = subprocess.run(
            [str(lms_exe), "unload", model_name],
            capture_output=True,
            text=True,
            timeout=30,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "method": "lms.exe", "model": model_name, "error": str(exc)}
    return {
        "ok": process.returncode == 0,
        "method": "lms.exe",
        "model": model_name,
        "returncode": process.returncode,
        "stdout": process.stdout.strip(),
        "stderr": process.stderr.strip(),
    }
