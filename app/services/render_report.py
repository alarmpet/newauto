import json
import re
import shutil
import subprocess
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

from .. import db
from ..types import ProjectRecord, RenderFormat, RenderReport, RenderReportOutput, RenderReportSegment

FINAL_AUDIO_SAMPLE_RATE = 48000
FINAL_AUDIO_CHANNELS = 2
MIN_AUDIBLE_MEAN_VOLUME_DB = -45.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _report_path(pid: str) -> Path:
    return db.project_dir(pid) / "render_report.json"


def _final_scene_review_path(pid: str) -> Path:
    return db.project_dir(pid) / "final_scene_review.json"


def _probe_duration(media_path: Path) -> float:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return 0.0
    process = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(media_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if process.returncode != 0:
        return 0.0
    try:
        return float((process.stdout or "").strip())
    except ValueError:
        return 0.0


def _probe_audio_stream(media_path: Path) -> dict[str, object]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return {}
    process = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=codec_name,sample_rate,channels,bit_rate",
            "-of",
            "json",
            str(media_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if process.returncode != 0:
        return {}
    try:
        payload = json.loads(process.stdout or "{}")
    except json.JSONDecodeError:
        return {}
    streams = payload.get("streams")
    if not isinstance(streams, list) or not streams:
        return {}
    stream = streams[0]
    if not isinstance(stream, dict):
        return {}

    def _int_value(value: object) -> int:
        try:
            return int(str(value))
        except (TypeError, ValueError):
            return 0

    sample_rate = _int_value(stream.get("sample_rate"))
    channels = _int_value(stream.get("channels"))
    bitrate = _int_value(stream.get("bit_rate"))
    return {
        "audio_codec": str(stream.get("codec_name") or ""),
        "audio_sample_rate": sample_rate,
        "audio_channels": channels,
        "audio_bitrate": bitrate,
        "audio_profile_ok": sample_rate == FINAL_AUDIO_SAMPLE_RATE and channels == FINAL_AUDIO_CHANNELS,
    }


def _probe_audio_volume(media_path: Path) -> dict[str, object]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return {}
    process = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-nostats",
            "-i",
            str(media_path),
            "-af",
            "volumedetect",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    stderr = process.stderr or ""
    mean_match = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?)\s*dB", stderr)
    max_match = re.search(r"max_volume:\s*(-?\d+(?:\.\d+)?)\s*dB", stderr)
    metrics: dict[str, object] = {}
    if mean_match:
        mean_volume = float(mean_match.group(1))
        metrics["audio_mean_volume_db"] = mean_volume
        metrics["audio_audibility_ok"] = mean_volume >= MIN_AUDIBLE_MEAN_VOLUME_DB
    if max_match:
        metrics["audio_max_volume_db"] = float(max_match.group(1))
    return metrics


def _autopilot_input_mode(project: ProjectRecord) -> str:
    options = project["autopilot_options"]
    if isinstance(options, dict):
        value = options.get("input_mode", "")
        if isinstance(value, str):
            return value
    return ""


def _hyperframes_overlay_output_fields(project: ProjectRecord, project_dir: Path) -> dict[str, object]:
    options = project["body_image_options"]
    if options.get("hyperframes_overlay_enabled") is not True:
        return {}
    status = str(options.get("hyperframes_overlay_status") or "not_run")
    report_path = str(options.get("hyperframes_overlay_report_path") or "")
    fields: dict[str, object] = {
        "hyperframes_overlay_status": status,
        "hyperframes_overlay_report_path": report_path,
    }
    path = Path(report_path) if report_path else project_dir / "hyperframes_overlay" / "overlay_report.json"
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        if isinstance(payload, dict):
            raw_overlay_path = payload.get("overlay_path")
            if isinstance(raw_overlay_path, str):
                fields["hyperframes_overlay_path"] = raw_overlay_path
            ffprobe = payload.get("ffprobe")
            if isinstance(ffprobe, dict):
                pix_fmt = ffprobe.get("pix_fmt")
                if isinstance(pix_fmt, str):
                    fields["hyperframes_overlay_pix_fmt"] = pix_fmt
    return fields


def build_render_report(
    project: ProjectRecord,
    *,
    status: str,
    audio_duration_sec: float,
    audio_raw_duration_sec: float = 0.0,
    audio_normalized_duration_sec: float = 0.0,
    output_duration_sec: float = 0.0,
    duration_drift_sec: float = 0.0,
    duration_guard_passed: bool = False,
    subtitle_cue_count: int,
    fallback_used: bool,
    ffmpeg_log_tail: str,
    error: str = "",
    segment_frame_data: Sequence[object] | None = None,
) -> RenderReport:
    project_dir = db.project_dir(project["id"])
    render_plan = project["render_plan"]
    segments: list[RenderReportSegment] = []
    missing_render_plan_media_count = 0
    if render_plan:
        media_dir = project_dir / "media"
        for segment in render_plan["segments"]:
            media_path = next((media["path"] for media in segment["media"]), "")
            media_missing = bool(media_path) and not (media_dir / media_path).exists()
            if media_missing:
                missing_render_plan_media_count += 1
            report_segment: RenderReportSegment = {
                "region": segment["region"],
                "start": segment["start"],
                "end": segment["end"],
                "media_path": media_path,
                "media_missing": media_missing,
                "motion": segment["motion"],
                "effect": segment["effect"],
                "caption_style": segment["caption_style"],
            }
            sentence_idx = segment.get("sentence_idx")
            if isinstance(sentence_idx, int):
                report_segment["sentence_idx"] = sentence_idx
            if segment_frame_data and len(segment_frame_data) > len(segments):
                frame_data = segment_frame_data[len(segments)]
                if hasattr(frame_data, "frame_count"):
                    report_segment["frame_count"] = int(getattr(frame_data, "frame_count"))
                if hasattr(frame_data, "target_frame_count"):
                    report_segment["target_frame_count"] = int(getattr(frame_data, "target_frame_count"))
                if hasattr(frame_data, "frame_duration_sec"):
                    report_segment["frame_duration_sec"] = float(getattr(frame_data, "frame_duration_sec"))
                if hasattr(frame_data, "drift_frames"):
                    report_segment["drift_frames"] = int(getattr(frame_data, "drift_frames"))
            segments.append(report_segment)

    outputs: list[RenderReportOutput] = []
    overlay_fields = _hyperframes_overlay_output_fields(project, project_dir)
    for render_format in project["render_formats"] or ["landscape"]:
        output_path = project_dir / ("output_shorts.mp4" if render_format == "shorts" else "output.mp4")
        exists = output_path.exists()
        output: RenderReportOutput = {
            "format": render_format,
            "path": str(output_path),
            "exists": exists,
            "size_bytes": output_path.stat().st_size if exists else 0,
            "duration_sec": _probe_duration(output_path) if exists else 0.0,
        }
        if exists:
            output.update(_probe_audio_stream(output_path))  # type: ignore[arg-type]
            output.update(_probe_audio_volume(output_path))  # type: ignore[arg-type]
        output.update(overlay_fields)  # type: ignore[arg-type]
        outputs.append(output)
    final_scene_review_path = _final_scene_review_path(project["id"])

    return {
        "project_id": project["id"],
        "title": project["title"],
        "status": status,
        "created_at": _now_iso(),
        "autopilot_job_id": project["autopilot_job_id"],
        "autopilot_input_mode": _autopilot_input_mode(project),
        "autopilot_state": project["autopilot_state"],
        "autopilot_phase": project["autopilot_phase"],
        "render_started_at": project["render_started_at"],
        "render_finished_at": _now_iso(),
        "audio_duration_sec": audio_duration_sec,
        "audio_raw_duration_sec": audio_raw_duration_sec,
        "audio_normalized_duration_sec": audio_normalized_duration_sec,
        "output_duration_sec": output_duration_sec,
        "duration_drift_sec": duration_drift_sec,
        "duration_guard_passed": duration_guard_passed,
        "subtitle_cue_count": subtitle_cue_count,
        "render_plan_segment_count": len(render_plan["segments"]) if render_plan else 0,
        "missing_render_plan_media_count": missing_render_plan_media_count,
        "fallback_used": fallback_used,
        "outputs": outputs,
        "segments": segments,
        "final_scene_review_path": str(final_scene_review_path),
        "final_scene_review_exists": final_scene_review_path.exists(),
        "ffmpeg_log_tail": ffmpeg_log_tail,
        "error": error,
    }


def save_render_report(report: RenderReport) -> Path:
    path = _report_path(report["project_id"])
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_render_report(pid: str) -> RenderReport | None:
    path = _report_path(pid)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload  # type: ignore[return-value]


def summarize_recent_render_reports(limit: int = 20) -> dict[str, int]:
    reports: list[RenderReport] = []
    for project_dir in db.PROJECTS_DIR.iterdir():
        if not project_dir.is_dir():
            continue
        report_path = project_dir / "render_report.json"
        if not report_path.exists():
            continue
        try:
            payload = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            reports.append(payload)  # type: ignore[arg-type]
    reports.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
    selected = reports[: max(1, limit)]
    total = len(selected)
    success = sum(1 for item in selected if item.get("status") == "done")
    error = sum(1 for item in selected if item.get("status") == "error")
    fallback = sum(1 for item in selected if bool(item.get("fallback_used")))
    missing_media = sum(int(item.get("missing_render_plan_media_count", 0) or 0) for item in selected)
    return {
        "total": total,
        "success": success,
        "error": error,
        "fallback": fallback,
        "missing_media": missing_media,
    }
