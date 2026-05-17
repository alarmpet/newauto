import json
import shutil
from pathlib import Path

from .. import db
from ..config import CLIENT_SECRET_PATH, PROJECTS_DIR
from .hyperframes_overlay import resolve_korean_font_source
from .hyperframes_probe import probe_hyperframes_runtime
from .render import find_invalid_media_files, probe_media_dimensions
from .subtitle import subtitle_display_qa
from .text_health import looks_mojibake
from .visual_relevance import validate_generated_image_mappings, write_final_scene_review, write_visual_mismatch_report
from ..types import PreflightCheck, PreflightReport, ProjectRecord


def _check(key: str, ok: bool, message: str) -> PreflightCheck:
    return {
        "key": key,
        "ok": ok,
        "message": message,
    }


def _existing_media_count(project: ProjectRecord) -> int:
    media_dir = db.project_dir(project["id"]) / "media"
    return sum(1 for name in project["media_order"] if (media_dir / name).exists())


def _existing_media_paths(project: ProjectRecord) -> list[Path]:
    media_dir = db.project_dir(project["id"]) / "media"
    return [
        media_dir / name
        for name in project["media_order"]
        if (media_dir / name).exists()
    ]


def _load_timings_count(project: ProjectRecord) -> int:
    return len(_load_timings(project))


def _load_timings(project: ProjectRecord) -> list[dict[str, object]]:
    timings_path = db.project_dir(project["id"]) / "tts" / "timings.json"
    if not timings_path.exists():
        return []
    try:
        payload = json.loads(timings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return payload if isinstance(payload, list) else []


def _render_plan_media_summary(project: ProjectRecord) -> tuple[int, int]:
    render_plan = project["render_plan"]
    if not render_plan:
        return (0, 0)
    media_dir = db.project_dir(project["id"]) / "media"
    total = 0
    missing = 0
    for segment in render_plan["segments"]:
        if not segment["media"]:
            continue
        total += 1
        if not any((media_dir / media["path"]).exists() for media in segment["media"]):
            missing += 1
    return (total, missing)


def _tts_consistency_summary(project: ProjectRecord) -> tuple[bool, str]:
    report_path = db.project_dir(project["id"]) / "tts" / "tts_consistency_report.json"
    if not report_path.exists():
        return (True, "TTS consistency report is not available yet.")
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return (False, "TTS consistency report is unreadable. Re-run TTS.")
    metadata_ok = payload.get("metadata_consistent") is True
    audio_checked = payload.get("audio_consistency_checked") is True
    audio_ok = payload.get("audio_consistency_passed") is True
    if metadata_ok and (not audio_checked or audio_ok):
        return (True, "TTS voice settings and audio consistency look stable.")
    pitch_drift = payload.get("max_estimated_pitch_relative_drift")
    centroid_drift = payload.get("max_spectral_centroid_relative_drift")
    recommended = str(payload.get("recommended_tts_mode") or "full_passage_or_reference_voice")
    details: list[str] = []
    if isinstance(pitch_drift, (int, float)):
        details.append(f"pitch drift {float(pitch_drift):.2f}")
    if isinstance(centroid_drift, (int, float)):
        details.append(f"spectral drift {float(centroid_drift):.2f}")
    detail_text = ", ".join(details) if details else "audio drift detected"
    return (
        False,
        f"TTS voice consistency failed ({detail_text}). Recommended mode: {recommended}.",
    )


def _tts_manifest_text_summary(project: ProjectRecord) -> tuple[bool, str]:
    manifest_path = db.project_dir(project["id"]) / "tts" / "tts_run_manifest.json"
    if not manifest_path.exists():
        return (False, "TTS run manifest is missing. Re-run TTS.")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return (False, "TTS run manifest is unreadable. Re-run TTS.")
    raw_sentences = payload.get("sentences")
    if not isinstance(raw_sentences, list) or not raw_sentences:
        return (False, "TTS run manifest has no synthesized sentences. Re-run TTS.")
    tts_sentences: list[str] = []
    for item in raw_sentences:
        if not isinstance(item, dict):
            return (False, "TTS run manifest has invalid sentence entries. Re-run TTS.")
        text = item.get("text")
        if not isinstance(text, str) or not text.strip():
            return (False, "TTS run manifest has blank sentence text. Re-run TTS.")
        tts_sentences.append(text.strip())
    mojibake_indexes = [
        index
        for index, text in enumerate(tts_sentences)
        if looks_mojibake(text)
    ]
    if mojibake_indexes:
        joined = ", ".join(str(index) for index in mojibake_indexes[:5])
        return (
            False,
            f"TTS synthesized text contains mojibake at sentence {joined}. Re-run TTS from the current script.",
        )
    current_sentences = [sentence.strip() for sentence in project["sentences"] if sentence.strip()]
    if tts_sentences != current_sentences:
        return (
            False,
            "TTS synthesized text does not match the current script. Re-run TTS before rendering.",
        )
    return (True, "TTS synthesized text matches the current script.")


def _subtitle_layout_summary(project: ProjectRecord) -> tuple[bool, str]:
    timings = _load_timings(project)
    if not timings:
        return (False, "Subtitle timings are missing. Re-run TTS before rendering.")
    render_format = "shorts" if "shorts" in project["render_formats"] else "landscape"
    qa = subtitle_display_qa(
        timings,  # type: ignore[arg-type]
        project["subtitle_style"],
        None,
        render_format=render_format,
    )
    if qa["ok"] is True:
        return (True, f"Subtitle layout is readable for {render_format} ({qa['cue_count']} display cues).")
    issues = qa.get("issues")
    first_issue = ""
    if isinstance(issues, list) and issues and isinstance(issues[0], dict):
        raw_issues = issues[0].get("issues")
        if isinstance(raw_issues, list):
            first_issue = ", ".join(str(issue) for issue in raw_issues)
    detail = first_issue or "cue layout exceeds readable limits"
    return (
        False,
        f"Subtitle layout failed for {render_format}: {detail}. Use readable cue splitting before rendering.",
    )


def _media_aspect_summary(project: ProjectRecord, media_paths: list[Path]) -> tuple[bool, str]:
    if not media_paths:
        return (False, "Upload at least one readable media file.")
    dimensions: list[tuple[str, int, int]] = []
    for path in media_paths:
        width, height = probe_media_dimensions(path)
        if width > 0 and height > 0:
            dimensions.append((path.name, width, height))
    if not dimensions:
        return (False, "Media dimensions are unavailable. Re-upload or regenerate media.")
    vertical_count = sum(1 for _, width, height in dimensions if height > width * 1.2)
    landscape_count = sum(1 for _, width, height in dimensions if width > height * 1.2)
    render_formats = project["render_formats"] or ["landscape"]
    if "shorts" not in render_formats and vertical_count == len(dimensions):
        sample = dimensions[0]
        return (
            False,
            f"All media are vertical ({sample[1]}x{sample[2]}) but render_formats is {render_formats}. Enable shorts before rendering.",
        )
    if render_formats == ["landscape"] and vertical_count > landscape_count:
        sample = dimensions[0]
        return (
            False,
            f"Most media are vertical ({sample[1]}x{sample[2]}) but only landscape output is selected. Enable shorts or regenerate 16:9 media.",
        )
    return (
        True,
        f"Media aspect ratios match selected formats ({vertical_count} vertical, {landscape_count} landscape).",
    )


def _operator_intervention_summary(project: ProjectRecord) -> tuple[bool, str]:
    review_path = write_final_scene_review(project)
    try:
        payload = json.loads(review_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return (True, "No operator visual review blocks were found.")
    entries = payload.get("entries") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return (True, "No operator visual review blocks were found.")
    blocking_entries = [
        entry
        for entry in entries
        if isinstance(entry, dict) and entry.get("operator_intervention_required") is True
    ]
    if not blocking_entries:
        return (True, "No operator visual review blocks were found.")
    if project["body_image_options"].get("allow_visual_relevance_warnings_for_render"):
        return (
            True,
            f"Operator visual review override is enabled for {len(blocking_entries)} scene(s).",
        )
    first = blocking_entries[0]
    sentence_idx = first.get("sentence_idx")
    reason = str(first.get("operator_intervention_reason") or first.get("retry_reason") or "visual review required")
    return (
        False,
        f"Operator visual review is required for sentence {sentence_idx}: {reason}",
    )


def build_preflight_report(project: ProjectRecord) -> PreflightReport:
    project_dir = db.project_dir(project["id"])
    timings_path = project_dir / "tts" / "timings.json"
    output_parent = project_dir.parent
    usage = shutil.disk_usage(output_parent if output_parent.exists() else PROJECTS_DIR)
    media_paths = _existing_media_paths(project)
    invalid_media = find_invalid_media_files(media_paths) if media_paths else []
    timing_count = _load_timings_count(project)
    subtitle_layout_ok, subtitle_layout_message = _subtitle_layout_summary(project)
    media_aspect_ok, media_aspect_message = _media_aspect_summary(project, media_paths)
    render_plan_media_total, render_plan_media_missing = _render_plan_media_summary(project)
    visual_relevance_issues = validate_generated_image_mappings(project)
    if project["body_image_options"].get("allow_visual_relevance_warnings_for_render"):
        visual_relevance_issues = []
    operator_intervention_ok, operator_intervention_message = _operator_intervention_summary(project)
    tts_consistency_ok, tts_consistency_message = _tts_consistency_summary(project)
    tts_manifest_text_ok, tts_manifest_text_message = _tts_manifest_text_summary(project)
    write_visual_mismatch_report(project)
    scene_plan = project["scene_plan"]
    render_plan = project["render_plan"]
    hyperframes_enabled = bool(project["body_image_options"].get("hyperframes_overlay_enabled"))
    hyperframes_check: PreflightCheck | None = None
    if hyperframes_enabled:
        hyperframes_status = probe_hyperframes_runtime(refresh=False)
        hyperframes_runtime_ready = bool(
            hyperframes_status["node_available"]
            and hyperframes_status["npx_available"]
            and hyperframes_status["doctor_ok"]
            and hyperframes_status["ffmpeg_alpha_ok"]
        )
        try:
            font_path = resolve_korean_font_source()
            font_ready = True
            font_detail = f"Korean font available: {font_path}"
        except FileNotFoundError as exc:
            font_ready = False
            font_detail = str(exc)
        hyperframes_ready = hyperframes_runtime_ready and font_ready
        hyperframes_detail = (
            "HyperFrames overlay runtime is ready."
            if hyperframes_runtime_ready and font_ready
            else str(hyperframes_status["doctor_detail"] or hyperframes_status["ffmpeg_alpha_detail"])
            if not hyperframes_runtime_ready
            else font_detail
        )
        hyperframes_check = _check(
            "hyperframes_overlay",
            hyperframes_ready,
            hyperframes_detail,
        )
    checks: list[PreflightCheck] = [
        _check(
            "script",
            bool(project["sentences"]),
            "Script has at least one readable sentence." if project["sentences"] else "Save a script with at least one readable sentence first.",
        ),
        _check(
            "tts_state",
            project["tts_state"] == "done",
            "TTS is complete." if project["tts_state"] == "done" else "Run TTS before rendering.",
        ),
        _check(
            "timings",
            timings_path.exists(),
            "timings.json is present." if timings_path.exists() else "timings.json is missing. Re-run TTS.",
        ),
        _check(
            "subtitle_cues",
            timing_count > 0,
            f"{timing_count} subtitle cues are available." if timing_count > 0 else "No subtitle cues were found. Re-run TTS before rendering.",
        ),
        _check(
            "subtitle_layout",
            subtitle_layout_ok,
            subtitle_layout_message,
        ),
        _check(
            "tts_consistency",
            tts_consistency_ok,
            tts_consistency_message,
        ),
        _check(
            "tts_manifest_text",
            tts_manifest_text_ok,
            tts_manifest_text_message,
        ),
        _check(
            "media",
            bool(project["media_order"]),
            "Media order is populated." if project["media_order"] else "Upload at least one media file.",
        ),
        _check(
            "media_files",
            _existing_media_count(project) == len(project["media_order"]) and bool(project["media_order"]),
            "All referenced media files exist." if _existing_media_count(project) == len(project["media_order"]) and project["media_order"] else "Some media files are missing on disk.",
        ),
        _check(
            "media_metadata",
            not invalid_media if media_paths else False,
            "All media files expose readable video dimensions."
            if media_paths and not invalid_media
            else "Some media files are unreadable or missing video dimensions: " + ", ".join(invalid_media)
            if invalid_media
            else "Upload at least one readable media file.",
        ),
        _check(
            "media_aspect",
            media_aspect_ok,
            media_aspect_message,
        ),
        _check(
            "plan_sync",
            (
                not project["sentences"]
                or (
                    scene_plan is not None
                    and len(scene_plan["scenes"]) == len(project["sentences"])
                    and (
                        render_plan is None
                        or len(render_plan["segments"]) == len(scene_plan["scenes"])
                    )
                )
            ),
            "Scene/render plans match the current sentence count."
            if (
                not project["sentences"]
                or (
                    scene_plan is not None
                    and len(scene_plan["scenes"]) == len(project["sentences"])
                    and (
                        render_plan is None
                        or len(render_plan["segments"]) == len(scene_plan["scenes"])
                    )
                )
            )
            else "Scene or render plans look stale. Rebuild the plans before rendering.",
        ),
        _check(
            "render_plan_media",
            render_plan_media_total == 0 or render_plan_media_missing == 0,
            "All render-plan segments have available media."
            if render_plan_media_total == 0 or render_plan_media_missing == 0
            else f"{render_plan_media_missing} render-plan segments are missing media files.",
        ),
        _check(
            "visual_relevance",
            not visual_relevance_issues,
            "Generated image mappings match the current script."
            if not visual_relevance_issues
            else visual_relevance_issues[0]["message"],
        ),
        _check(
            "operator_visual_review",
            operator_intervention_ok,
            operator_intervention_message,
        ),
        _check(
            "ffmpeg",
            shutil.which("ffmpeg") is not None,
            "FFmpeg is available on PATH." if shutil.which("ffmpeg") is not None else "FFmpeg is missing from PATH.",
        ),
        _check(
            "disk_space",
            usage.free >= 500 * 1024 * 1024,
            f"Free disk space is {usage.free / (1024 ** 3):.1f} GB." if usage.free >= 500 * 1024 * 1024 else "At least 0.5 GB of free disk space is recommended.",
        ),
        _check(
            "oauth",
            CLIENT_SECRET_PATH.exists(),
            "OAuth client secret is present." if CLIENT_SECRET_PATH.exists() else "OAuth client secret is missing.",
        ),
    ]
    if hyperframes_check is not None:
        checks.append(hyperframes_check)
    return {
        "ok": all(check["ok"] for check in checks),
        "checks": checks,
    }
