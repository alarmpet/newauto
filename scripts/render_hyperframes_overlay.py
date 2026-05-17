import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


def _run(command: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    resolved = list(command)
    tool_path = shutil.which(resolved[0])
    if tool_path:
        resolved[0] = tool_path
    process = subprocess.run(
        resolved,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return process.returncode, process.stdout or "", process.stderr or ""


def validate_overlay_probe(probe: dict[str, Any], *, expected_duration_sec: float) -> dict[str, Any]:
    pix_fmt = str(probe.get("pix_fmt", ""))
    duration_sec = float(probe.get("duration_sec", 0.0))
    if "a" not in pix_fmt:
        return {"ok": False, "error": f"overlay pix_fmt lacks alpha: {pix_fmt}"}
    if abs(duration_sec - expected_duration_sec) > 0.1:
        return {"ok": False, "error": f"overlay duration drift: {duration_sec:.3f}s vs {expected_duration_sec:.3f}s"}
    return {"ok": True, "error": ""}


def _ffprobe_overlay(path: Path) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return {"pix_fmt": "", "duration_sec": 0.0, "error": "ffprobe not found"}
    code, stdout, stderr = _run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=pix_fmt,duration",
            "-of",
            "json",
            str(path),
        ]
    )
    if code != 0:
        return {"pix_fmt": "", "duration_sec": 0.0, "error": stderr.strip()}
    payload = json.loads(stdout or "{}")
    streams = payload.get("streams") if isinstance(payload, dict) else []
    stream = streams[0] if streams else {}
    return {"pix_fmt": str(stream.get("pix_fmt", "")), "duration_sec": float(stream.get("duration") or 0.0)}


def _render_command(format_name: str, output: Path) -> list[str]:
    return ["npx", "hyperframes", "render", "--format", format_name, "--output", str(output.name)]


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _parse_json_text(text: str) -> object:
    try:
        return json.loads(text or "{}")
    except json.JSONDecodeError:
        return {"raw": text}


def render_hyperframes_overlay(overlay_dir: Path, *, expected_duration_sec: float) -> dict[str, Any]:
    webm_output = overlay_dir / "overlay.webm"
    mov_output = overlay_dir / "overlay.mov"
    commands = [
        ["npx", "hyperframes", "lint", "--json"],
        ["npx", "hyperframes", "inspect", "--json", "--samples", "15"],
        _render_command("webm", webm_output),
    ]
    rows = []
    ok = True
    for command in commands:
        code, stdout, stderr = _run(command, cwd=overlay_dir)
        rows.append({"command": command, "returncode": code, "stdout": stdout, "stderr": stderr})
        if "lint" in command:
            _write_json(overlay_dir / "hyperframes_overlay_lint.json", _parse_json_text(stdout))
        if "inspect" in command:
            _write_json(overlay_dir / "hyperframes_overlay_inspect.json", _parse_json_text(stdout))
        ok = ok and code == 0
        if code != 0:
            report = {
                "ok": False,
                "commands": rows,
                "ffprobe": {"pix_fmt": "", "duration_sec": 0.0},
                "validation": {"ok": False, "error": stderr.strip() or stdout.strip()},
                "overlay_path": str(webm_output),
            }
            _write_json(overlay_dir / "overlay_report.json", report)
            return report

    probe = _ffprobe_overlay(webm_output)
    validation = validate_overlay_probe(probe, expected_duration_sec=expected_duration_sec)
    output = webm_output
    if not validation["ok"] and "alpha" in str(validation["error"]):
        mov_command = _render_command("mov", mov_output)
        code, stdout, stderr = _run(mov_command, cwd=overlay_dir)
        rows.append({"command": mov_command, "returncode": code, "stdout": stdout, "stderr": stderr})
        output = mov_output
        probe = _ffprobe_overlay(mov_output)
        validation = validate_overlay_probe(probe, expected_duration_sec=expected_duration_sec)
        ok = ok and code == 0

    ok = ok and bool(validation["ok"])
    report = {"ok": ok, "commands": rows, "ffprobe": probe, "validation": validation, "overlay_path": str(output)}
    _write_json(overlay_dir / "hyperframes_overlay_ffprobe.json", probe)
    _write_json(overlay_dir / "overlay_report.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("overlay_dir")
    parser.add_argument("--duration", type=float, required=True)
    args = parser.parse_args()
    overlay_dir = Path(args.overlay_dir)
    report = render_hyperframes_overlay(overlay_dir, expected_duration_sec=args.duration)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
