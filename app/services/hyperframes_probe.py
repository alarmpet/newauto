import re
import shutil
import subprocess
import time
from typing import TypedDict

HYPERFRAMES_PACKAGE = "hyperframes@0.6.12"
_CACHE_TTL_SEC = 300.0
_cache: tuple[float, "HyperFramesRuntimeStatus"] | None = None


class HyperFramesRuntimeStatus(TypedDict):
    node_available: bool
    node_version: str
    node_major: int | None
    npx_available: bool
    npx_version: str
    doctor_ok: bool
    doctor_detail: str
    ffmpeg_alpha_ok: bool
    ffmpeg_alpha_detail: str


def _run_text(command: list[str], timeout_sec: int = 30) -> tuple[int, str, str]:
    process = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=timeout_sec,
    )
    return process.returncode, process.stdout or "", process.stderr or ""


def parse_node_major(output: str) -> int | None:
    match = re.search(r"v?(\d+)\.", output.strip())
    if not match:
        return None
    return int(match.group(1))


def _doctor_passed(returncode: int, output: str) -> bool:
    if returncode != 0:
        return False
    failed_lines = [line.strip() for line in output.splitlines() if "✗" in line]
    if not failed_lines:
        return True
    return all("Docker running" in line for line in failed_lines) and "✓ Chrome" in output


def _empty_status(detail: str) -> HyperFramesRuntimeStatus:
    return {
        "node_available": False,
        "node_version": "",
        "node_major": None,
        "npx_available": False,
        "npx_version": "",
        "doctor_ok": False,
        "doctor_detail": detail,
        "ffmpeg_alpha_ok": False,
        "ffmpeg_alpha_detail": "",
    }


def probe_hyperframes_runtime(*, refresh: bool = False) -> HyperFramesRuntimeStatus:
    global _cache
    now = time.monotonic()
    if _cache is not None and not refresh and now - _cache[0] <= _CACHE_TTL_SEC:
        return dict(_cache[1])

    node_path = shutil.which("node")
    if node_path is None:
        return _empty_status("node not found on PATH")
    npx_path = shutil.which("npx")
    if npx_path is None:
        status = _empty_status("npx not found on PATH")
        status["node_available"] = True
        _cache = (now, status)
        return dict(status)

    node_code, node_out, node_err = _run_text([node_path, "--version"])
    npx_code, npx_out, npx_err = _run_text([npx_path, "--version"])
    node_major = parse_node_major(node_out)
    doctor_code, doctor_out, doctor_err = _run_text([npx_path, "-y", HYPERFRAMES_PACKAGE, "doctor"], timeout_sec=90)
    doctor_text = (doctor_out or doctor_err).strip()
    ffmpeg_path = shutil.which("ffmpeg") or "ffmpeg"
    enc_code, enc_out, enc_err = _run_text([ffmpeg_path, "-hide_banner", "-encoders"], timeout_sec=30)
    enc_text = enc_out + enc_err
    alpha_ok = enc_code == 0 and "libvpx-vp9" in enc_text and "prores_ks" in enc_text

    status: HyperFramesRuntimeStatus = {
        "node_available": node_code == 0 and node_major is not None and node_major >= 22,
        "node_version": (node_out or node_err).strip(),
        "node_major": node_major,
        "npx_available": npx_code == 0,
        "npx_version": (npx_out or npx_err).strip(),
        "doctor_ok": _doctor_passed(doctor_code, doctor_text),
        "doctor_detail": doctor_text,
        "ffmpeg_alpha_ok": alpha_ok,
        "ffmpeg_alpha_detail": enc_text.strip(),
    }
    _cache = (now, status)
    return dict(status)
