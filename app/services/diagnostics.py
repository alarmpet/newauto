import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .. import db
from .operator_summary import build_operator_summary
from .preflight import build_preflight_report
from .visual_relevance import write_final_scene_review, write_visual_contact_sheet, write_visual_mismatch_report


def _run_text(command: list[str]) -> tuple[int, str, str]:
    process = subprocess.run(command, capture_output=True, text=True, check=False)
    return (process.returncode, process.stdout or "", process.stderr or "")


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _copy_if_exists(source: Path, target: Path) -> bool:
    if not source.exists():
        return False
    shutil.copy2(source, target)
    return True


def _project_outputs(project_dir: Path) -> list[Path]:
    return [path for path in (project_dir / "output.mp4", project_dir / "output_shorts.mp4") if path.exists()]


def _collect_ffprobe(outputs: list[Path]) -> dict[str, object]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return {"available": False, "outputs": []}
    rows: list[dict[str, object]] = []
    for output in outputs:
        code, stdout, stderr = _run_text(
            [
                ffprobe,
                "-v",
                "error",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(output),
            ]
        )
        parsed: object
        try:
            parsed = json.loads(stdout or "{}")
        except json.JSONDecodeError:
            parsed = {}
        rows.append(
            {
                "path": str(output),
                "returncode": code,
                "stderr": stderr,
                "probe": parsed,
            }
        )
    return {"available": True, "outputs": rows}


def _collect_volumedetect(outputs: list[Path]) -> str:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return "ffmpeg unavailable on PATH\n"
    chunks: list[str] = []
    for output in outputs:
        code, stdout, stderr = _run_text(
            [
                ffmpeg,
                "-hide_banner",
                "-nostats",
                "-i",
                str(output),
                "-af",
                "volumedetect",
                "-f",
                "null",
                "-",
            ]
        )
        chunks.extend(
            [
                f"=== {output} ===",
                f"returncode: {code}",
                stdout.strip(),
                stderr.strip(),
                "",
            ]
        )
    return "\n".join(chunks).strip() + "\n"


def _tts_manifest_excerpt(project_dir: Path) -> dict[str, object]:
    path = project_dir / "tts" / "tts_run_manifest.json"
    if not path.exists():
        return {"exists": False, "path": str(path), "sentences": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"exists": True, "path": str(path), "error": f"{type(exc).__name__}: {exc}", "sentences": []}
    sentences = payload.get("sentences") if isinstance(payload, dict) else []
    excerpt: list[object] = sentences[:5] if isinstance(sentences, list) else []
    return {
        "exists": True,
        "path": str(path),
        "voice_preset": payload.get("voice_preset", "") if isinstance(payload, dict) else "",
        "sentence_count": len(sentences) if isinstance(sentences, list) else 0,
        "sentences": excerpt,
    }


def _copy_hyperframes_overlay(project_dir: Path, bundle_dir: Path) -> list[str]:
    source_dir = project_dir / "hyperframes_overlay"
    if not source_dir.exists():
        return []
    target_dir = bundle_dir / "hyperframes_overlay"
    target_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for name in (
        "index.html",
        "overlay_plan.json",
        "overlay_report.json",
        "overlay.webm",
        "overlay.mov",
        "hyperframes_overlay_lint.json",
        "hyperframes_overlay_inspect.json",
        "hyperframes_overlay_ffprobe.json",
    ):
        if _copy_if_exists(source_dir / name, target_dir / name):
            copied.append(f"hyperframes_overlay/{name}")
    return copied


def collect_project_diagnostics(project_id: str) -> dict[str, Any]:
    project = db.get_project(project_id)
    if project is None:
        raise ValueError(f"Project not found: {project_id}")

    project_dir = db.project_dir(project_id)
    bundle_dir = project_dir / "diagnostics_bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    outputs = _project_outputs(project_dir)
    _write_json(bundle_dir / "ffprobe_output.json", _collect_ffprobe(outputs))
    (bundle_dir / "audio_volumedetect.txt").write_text(_collect_volumedetect(outputs), encoding="utf-8")

    preflight_report = build_preflight_report(project)
    _write_json(bundle_dir / "preflight_report.json", preflight_report)
    _write_json(bundle_dir / "tts_manifest_excerpt.json", _tts_manifest_excerpt(project_dir))

    visual_json_path, visual_md_path = write_visual_mismatch_report(project)
    final_scene_review_path = write_final_scene_review(project)
    contact_sheet_path = write_visual_contact_sheet(project)
    operator_summary = build_operator_summary(project)

    copied: dict[str, bool] = {
        "render_report.json": _copy_if_exists(project_dir / "render_report.json", bundle_dir / "render_report.json"),
        "visual_mismatch_report.md": _copy_if_exists(visual_md_path, bundle_dir / "visual_mismatch_report.md"),
        "visual_mismatch_report.json": _copy_if_exists(visual_json_path, bundle_dir / "visual_mismatch_report.json"),
        "final_scene_review.json": _copy_if_exists(final_scene_review_path, bundle_dir / "final_scene_review.json"),
        "diagnostic_contact_sheet.jpg": _copy_if_exists(contact_sheet_path, bundle_dir / "diagnostic_contact_sheet.jpg"),
    }
    hyperframes_overlay_files = _copy_hyperframes_overlay(project_dir, bundle_dir)
    _write_json(bundle_dir / "operator_summary.json", operator_summary)

    manifest: dict[str, Any] = {
        "project_id": project_id,
        "bundle_dir": str(bundle_dir),
        "outputs": [str(path) for path in outputs],
        "files": [],
        "copied": copied,
        "hyperframes_overlay_files": hyperframes_overlay_files,
    }
    _write_json(bundle_dir / "diagnostics_manifest.json", manifest)
    manifest["files"] = sorted(path.name for path in bundle_dir.iterdir() if path.is_file())
    _write_json(bundle_dir / "diagnostics_manifest.json", manifest)
    return manifest
