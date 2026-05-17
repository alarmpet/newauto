import json
import math
import time
import uuid
from pathlib import Path
from typing import cast

from fastapi import HTTPException

from .. import db
from ..services.image_generation_disabled import IMAGE_GEN_DISABLED_CODE, IMAGE_GEN_DISABLED_MESSAGE
from ..services.preflight import build_preflight_report
from ..services.render_plan import build_render_plan
from ..services.render_report import load_render_report
from ..services.scene_plan import build_scene_plan
from ..services.source_draft import risk_threshold_for_mode
from ..services.source_fetch import analyze_source_url
from ..services.source_research import collect_sources_from_keyword
from ..services.subtitle import normalize_subtitle_style
from ..tts_profiles import normalize_tts_profile
from ..services import gpu_guard
from ..types import PreflightCheck, RenderFormat, TtsProfile
from ..services.script_compile import compile_script, flatten_regional_sentences
from ..config import SCRIPT_LLM_MODEL
from ..types import (
    AutopilotDebugSnapshot,
    AutopilotEvent,
    AutopilotFailureSnapshot,
    AutopilotImageCount,
    AutopilotInputMode,
    AutopilotOptions,
    ProjectRecord,
    QualityMode,
    SourceRegenerateMode,
    VisualSourceMode,
)

MAX_EVENT_LINES = 2000
MAX_RECENT_EVENTS = 10
POLL_WAIT_SEC = 2.0
AUTOPILOT_DEFAULT_VOICE_PRESET = "male-announcer-40s-50s"


def _autopilot_dir(pid: str) -> Path:
    return db.project_dir(pid) / "autopilot"


def _events_path(pid: str) -> Path:
    return _autopilot_dir(pid) / "events.jsonl"


def _events_archive_path(pid: str) -> Path:
    return _autopilot_dir(pid) / "events.1.jsonl"


def _debug_snapshot_path(pid: str) -> Path:
    return _autopilot_dir(pid) / "debug_snapshot.json"


def _last_failure_path(pid: str) -> Path:
    return _autopilot_dir(pid) / "last_failure.json"


def default_options() -> AutopilotOptions:
    return {
        "input_mode": "script",
        "script": "",
        "url": "",
        "keyword": "",
        "tone": "documentary",
        "target_minutes": "auto",
        "regenerate_mode": "",
        "visual_source_mode": "comfyui_auto",
        "image_count": "auto",
        "quality_mode": "fast",
        "render_after_preflight": True,
        "debug_verbose": False,
    }


def _coerce_input_mode(value: object) -> AutopilotInputMode:
    if value in {"script", "url", "keyword"}:
        return cast(AutopilotInputMode, value)
    return "script"


def _coerce_regenerate_mode(value: object) -> SourceRegenerateMode:
    if value in {"", "hook", "point", "story", "lesson"}:
        return cast(SourceRegenerateMode, value)
    return ""


def _coerce_visual_source_mode(value: object) -> VisualSourceMode:
    if value in {"upload_only", "hybrid", "comfyui_auto"}:
        return cast(VisualSourceMode, value)
    return "comfyui_auto"


def _coerce_image_count(value: object) -> AutopilotImageCount:
    if value == "auto":
        return "auto"
    if isinstance(value, int) and not isinstance(value, bool):
        return max(1, min(48, value))
    return "auto"


def _coerce_quality_mode(value: object) -> QualityMode:
    if value in {"fast", "balanced", "exhaustive"}:
        return cast(QualityMode, value)
    return "fast"


def normalize_options(raw: dict[str, object] | AutopilotOptions) -> AutopilotOptions:
    options = default_options()
    options.update(
        {
            "input_mode": _coerce_input_mode(raw.get("input_mode") or options["input_mode"]),
            "script": str(raw.get("script") or ""),
            "url": str(raw.get("url") or ""),
            "keyword": str(raw.get("keyword") or ""),
            "tone": str(raw.get("tone") or options["tone"]),
            "target_minutes": str(raw.get("target_minutes") or options["target_minutes"]),
            "regenerate_mode": _coerce_regenerate_mode(raw.get("regenerate_mode") or options["regenerate_mode"]),
            "visual_source_mode": _coerce_visual_source_mode(raw.get("visual_source_mode") or options["visual_source_mode"]),
            "image_count": _coerce_image_count(raw.get("image_count", options["image_count"])),
            "quality_mode": _coerce_quality_mode(raw.get("quality_mode", options["quality_mode"])),
            "render_after_preflight": bool(raw.get("render_after_preflight", options["render_after_preflight"])),
            "debug_verbose": bool(raw.get("debug_verbose", options["debug_verbose"])),
        }
    )
    return options


def _ensure_dir(pid: str) -> Path:
    target_dir = _autopilot_dir(pid)
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir


def _project_state_map(project: ProjectRecord) -> dict[str, str]:
    return {
        "autopilot_state": project["autopilot_state"],
        "source_draft_state": project["source_draft_state"],
        "tts_state": project["tts_state"],
        "body_image_state": project["body_image_state"],
        "render_state": project["render_state"],
    }


def list_events(pid: str, limit: int = 100) -> list[AutopilotEvent]:
    path = _events_path(pid)
    if not path.exists():
        return []
    events: list[AutopilotEvent] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        events.append(payload)  # type: ignore[arg-type]
    return events[-max(1, min(limit, MAX_EVENT_LINES)) :]


def _rotate_events_if_needed(pid: str) -> None:
    path = _events_path(pid)
    if not path.exists():
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) <= MAX_EVENT_LINES:
        return
    archive = _events_archive_path(pid)
    archive.write_text("\n".join(lines[:-MAX_EVENT_LINES]) + "\n", encoding="utf-8")
    path.write_text("\n".join(lines[-MAX_EVENT_LINES:]) + "\n", encoding="utf-8")


def append_event(
    pid: str,
    *,
    project: ProjectRecord,
    level: str,
    event: str,
    message: str,
    debug: dict[str, object] | None = None,
) -> AutopilotEvent:
    _ensure_dir(pid)
    payload: AutopilotEvent = {
        "ts": db.now_iso(),
        "job_id": project["autopilot_job_id"],
        "phase": project["autopilot_phase"],
        "level": level,
        "event": event,
        "message": message,
        "progress": project["autopilot_progress"],
        "worker_state": project["autopilot_state"],
        "related_state": _project_state_map(project),
        "debug": debug or {},
    }
    with _events_path(pid).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    _rotate_events_if_needed(pid)
    return payload


def _update_runtime(
    pid: str,
    *,
    project: ProjectRecord,
    phase: str | None = None,
    progress: int | None = None,
    last_log: str | None = None,
    debug_summary: str | None = None,
    error: str | None = None,
    error_code: str | None = None,
    state: str | None = None,
    wait_started_at: str | None = None,
    retry_count: int | None = None,
    level: str = "info",
    event: str = "phase_update",
    debug: dict[str, object] | None = None,
) -> ProjectRecord:
    patch: dict[str, object] = {}
    if phase is not None:
        patch["autopilot_phase"] = phase
    if progress is not None:
        patch["autopilot_progress"] = progress
    if last_log is not None:
        patch["autopilot_last_log"] = last_log
    if debug_summary is not None:
        patch["autopilot_debug_summary"] = debug_summary
    if error is not None:
        patch["autopilot_error"] = error
    if error_code is not None:
        patch["autopilot_last_error_code"] = error_code
    if state is not None:
        patch["autopilot_state"] = state
    if wait_started_at is not None:
        patch["autopilot_wait_started_at"] = wait_started_at
    if retry_count is not None:
        patch["autopilot_retry_count"] = retry_count
    patch["autopilot_heartbeat_at"] = db.now_iso()
    updated = db.update_project(pid, **patch)
    if updated is None:
        raise RuntimeError(f"project {pid} not found")
    append_event(
        pid,
        project=updated,
        level=level,
        event=event,
        message=last_log or updated["autopilot_last_log"] or updated["autopilot_debug_summary"],
        debug=debug,
    )
    save_debug_snapshot(pid, updated)
    return updated


def load_last_failure(pid: str) -> AutopilotFailureSnapshot | None:
    path = _last_failure_path(pid)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload  # type: ignore[return-value]


def save_last_failure(
    pid: str,
    *,
    project: ProjectRecord,
    error_code: str,
    message: str,
    action_hint: str,
    recoverable: bool,
) -> AutopilotFailureSnapshot:
    _ensure_dir(pid)
    payload: AutopilotFailureSnapshot = {
        "ts": db.now_iso(),
        "job_id": project["autopilot_job_id"],
        "phase": project["autopilot_phase"],
        "error_code": error_code,
        "message": message,
        "action_hint": action_hint,
        "recoverable": recoverable,
        "project_state": _project_state_map(project),
    }
    _last_failure_path(pid).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def save_debug_snapshot(pid: str, project: ProjectRecord) -> AutopilotDebugSnapshot:
    _ensure_dir(pid)
    snapshot: AutopilotDebugSnapshot = {
        "project_id": pid,
        "state": project["autopilot_state"],
        "phase": project["autopilot_phase"],
        "progress": project["autopilot_progress"],
        "last_log": project["autopilot_last_log"],
        "error": project["autopilot_error"],
        "error_code": project["autopilot_last_error_code"],
        "debug_summary": project["autopilot_debug_summary"],
        "job_id": project["autopilot_job_id"],
        "started_at": project["autopilot_started_at"],
        "heartbeat_at": project["autopilot_heartbeat_at"],
        "wait_started_at": project["autopilot_wait_started_at"],
        "retry_count": project["autopilot_retry_count"],
        "options": normalize_options(project["autopilot_options"]),
        "current_owner": gpu_guard.current_owner(),
        "last_failure": load_last_failure(pid),
        "recent_events": list_events(pid, limit=MAX_RECENT_EVENTS),
    }
    _debug_snapshot_path(pid).write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return snapshot


def load_debug_snapshot(pid: str) -> AutopilotDebugSnapshot:
    project = db.get_project(pid)
    if project is None:
        raise HTTPException(404, f"project {pid} not found")
    path = _debug_snapshot_path(pid)
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            payload["recent_events"] = list_events(pid, limit=MAX_RECENT_EVENTS)
            payload["last_failure"] = load_last_failure(pid)
            return payload  # type: ignore[return-value]
    return save_debug_snapshot(pid, project)


def _require_project(pid: str) -> ProjectRecord:
    project = db.get_project(pid)
    if project is None:
        raise HTTPException(404, f"project {pid} not found")
    return project


def _ensure_startable(project: ProjectRecord) -> None:
    if project["autopilot_state"] in {"queued", "running", "paused"}:
        raise HTTPException(409, "autopilot already active")


def start(pid: str, options: AutopilotOptions) -> ProjectRecord:
    project = _require_project(pid)
    _ensure_startable(project)
    job_id = f"auto_{uuid.uuid4().hex[:12]}"
    updated = db.update_project(
        pid,
        autopilot_state="queued",
        autopilot_progress=0,
        autopilot_phase="prepare_input",
        autopilot_last_log="Autopilot queued.",
        autopilot_error="",
        autopilot_job_id=job_id,
        autopilot_started_at=db.now_iso(),
        autopilot_heartbeat_at="",
        autopilot_options=options,
        autopilot_last_error_code="",
        autopilot_debug_summary=f"Queued for {options['input_mode']} input.",
        autopilot_wait_started_at="",
        autopilot_retry_count=0,
    )
    if updated is None:
        raise HTTPException(404, f"project {pid} not found")
    append_event(
        pid,
        project=updated,
        level="info",
        event="queued",
        message="Autopilot queued.",
        debug={"input_mode": options["input_mode"]},
    )
    save_debug_snapshot(pid, updated)
    return updated


def pause(pid: str) -> ProjectRecord:
    project = _require_project(pid)
    if project["autopilot_state"] not in {"queued", "running"}:
        raise HTTPException(409, "autopilot is not running")
    updated = db.update_project(
        pid,
        autopilot_state="paused",
        autopilot_last_log="Autopilot paused by user.",
        autopilot_debug_summary="Paused by user request.",
    )
    if updated is None:
        raise HTTPException(404, f"project {pid} not found")
    append_event(pid, project=updated, level="pause", event="paused", message="Autopilot paused by user.")
    save_debug_snapshot(pid, updated)
    return updated


def resume(pid: str) -> ProjectRecord:
    project = _require_project(pid)
    if project["autopilot_state"] != "paused":
        raise HTTPException(409, "autopilot is not paused")
    updated = db.update_project(
        pid,
        autopilot_state="queued",
        autopilot_last_log="Autopilot resumed and queued again.",
        autopilot_error="",
        autopilot_debug_summary="Resume requested. Waiting for worker pickup.",
    )
    if updated is None:
        raise HTTPException(404, f"project {pid} not found")
    append_event(pid, project=updated, level="info", event="resumed", message="Autopilot resumed.")
    save_debug_snapshot(pid, updated)
    return updated


def cancel(pid: str) -> ProjectRecord:
    project = _require_project(pid)
    if project["autopilot_state"] in {"idle", "done", "error", "canceled"}:
        raise HTTPException(409, "autopilot is not active")
    updated = db.update_project(
        pid,
        autopilot_state="canceled",
        autopilot_last_log="Autopilot canceled by user.",
        autopilot_error="",
        autopilot_debug_summary="Canceled by user request.",
    )
    if updated is None:
        raise HTTPException(404, f"project {pid} not found")
    append_event(pid, project=updated, level="warn", event="canceled", message="Autopilot canceled by user.")
    save_debug_snapshot(pid, updated)
    return updated


def _preferred_render_format(project: ProjectRecord) -> RenderFormat:
    for render_format in project["render_formats"]:
        if render_format in {"landscape", "shorts"}:
            return render_format
    return "landscape"


def _field_value_as_string(project: ProjectRecord, field: str) -> str:
    if field == "body_image_state":
        return project["body_image_state"]
    if field == "render_state":
        return project["render_state"]
    if field == "tts_state":
        return project["tts_state"]
    if field == "source_draft_state":
        return project["source_draft_state"]
    raise KeyError(field)


def _resolve_image_count(options: AutopilotOptions, sentence_count: int) -> int:
    raw_count = options["image_count"]
    if raw_count != "auto":
        return max(1, min(sentence_count, int(raw_count)))
    return max(1, min(sentence_count, 24))


def _effective_autopilot_tts_profile(project: ProjectRecord) -> tuple[str, TtsProfile, bool]:
    script_text = project["compiled_script"] or project["script"]
    preset, profile = normalize_tts_profile(
        project["tts_profile"],
        project["voice_preset"],
        script_text,
    )
    needs_autopilot_default = (
        preset == "auto"
        or profile["mode"] != "design"
        or not profile["instruct"].strip()
        or profile.get("synthesis_mode", "sentence") != "full_passage"
    )
    if not needs_autopilot_default:
        return preset, profile, False
    autopilot_preset, autopilot_profile = normalize_tts_profile(
        {
            "mode": "design",
            "seed_mode": "fixed",
            "synthesis_mode": "full_passage",
        },
        AUTOPILOT_DEFAULT_VOICE_PRESET,
        script_text,
    )
    return autopilot_preset, autopilot_profile, True


def _wait_for_state(
    pid: str,
    *,
    field: str,
    done_value: str,
    error_value: str = "error",
    phase: str,
    progress: int,
    message: str,
    state_label: str,
) -> ProjectRecord:
    wait_started = db.now_iso()
    project = _require_project(pid)
    project = _update_runtime(
        pid,
        project=project,
        phase=phase,
        progress=progress,
        last_log=message,
        debug_summary=message,
        wait_started_at=wait_started,
        event="wait_start",
        debug={"field": field},
    )
    while True:
        time.sleep(POLL_WAIT_SEC)
        project = _require_project(pid)
        current_value = _field_value_as_string(project, field)
        if project["autopilot_state"] in {"paused", "canceled", "error"}:
            return project
        if current_value == done_value:
            return _update_runtime(
                pid,
                project=project,
                phase=phase,
                progress=progress,
                last_log=f"{state_label} completed.",
                debug_summary=f"{state_label} completed.",
                wait_started_at="",
                event="wait_done",
            )
        if current_value == error_value:
            error_message = ""
            if field == "body_image_state":
                error_message = project["body_image_error"]
            elif field == "source_draft_state":
                error_message = project["source_draft_error"]
            elif field == "tts_state":
                error_message = project["tts_error"]
            raise RuntimeError(f"{state_label} failed: {error_message}")
        _update_runtime(
            pid,
            project=project,
            phase=phase,
            progress=progress,
            last_log=f"{state_label} in progress.",
            debug_summary=f"{state_label} in progress.",
            wait_started_at=wait_started,
            event="wait_tick",
            debug={"field": field, "current_value": current_value},
        )


def _pause_with_failure(
    pid: str,
    *,
    project: ProjectRecord,
    error_code: str,
    message: str,
    action_hint: str,
) -> ProjectRecord:
    updated = _update_runtime(
        pid,
        project=project,
        state="paused",
        last_log=message,
        debug_summary=action_hint,
        error=message,
        error_code=error_code,
        level="pause",
        event="paused",
    )
    save_last_failure(
        pid,
        project=updated,
        error_code=error_code,
        message=message,
        action_hint=action_hint,
        recoverable=True,
    )
    return updated


def _backup_user_script(pid: str, user_script: str) -> None:
    backup_path = _autopilot_dir(pid) / "pre_apply_backup.txt"
    _ensure_dir(pid)
    backup_path.write_text(user_script, encoding="utf-8")


def _queue_source_draft(project: ProjectRecord, options: AutopilotOptions) -> ProjectRecord:
    updated = db.update_project(
        project["id"],
        source_draft_state="queued",
        source_draft_progress=0,
        source_draft_error="",
        source_draft_model=SCRIPT_LLM_MODEL,
        source_draft_regenerate_mode=options["regenerate_mode"],
        source_draft_regenerate_note="",
        source_draft_job_id="",
        source_draft_started_at="",
        source_draft_heartbeat_at="",
        source_draft_phase="queued",
        source_draft_last_log="Queued source draft generation.",
        source_draft_options={
            "tone": options["tone"],
            "target_minutes": "auto" if options["target_minutes"] == "auto" else int(options["target_minutes"]),
            "language": "ko",
        },
    )
    if updated is None:
        raise RuntimeError(f"project {project['id']} not found")
    return updated


def _collect_url_source(pid: str, url: str) -> ProjectRecord:
    extracted = analyze_source_url(url)
    updated = db.update_project(
        pid,
        source_draft_state="done",
        source_draft_progress=100,
        source_draft_error="",
        source_draft_input_mode="url",
        source_draft_query=url.strip(),
        source_draft_sources=[extracted.source],
        source_draft_fact_notes=extracted.fact_notes,
        source_draft_script="",
        source_draft_previous_script="",
        source_draft_warnings=extracted.warnings,
        source_draft_model="",
        source_draft_risk_score=0.0,
    )
    if updated is None:
        raise RuntimeError(f"project {pid} not found")
    return updated


def _collect_keyword_sources(pid: str, keyword: str) -> ProjectRecord:
    search_results, usage = collect_sources_from_keyword(keyword)
    sources = []
    fact_notes = []
    skipped = 0
    for result in search_results:
        try:
            extracted = analyze_source_url(result.url)
        except HTTPException:
            skipped += 1
            continue
        sources.append(extracted.source)
        fact_notes.extend(extracted.fact_notes)
        if len(sources) >= 5:
            break
    if not sources:
        raise HTTPException(404, "검색 결과는 있었지만 분석 가능한 본문을 찾지 못했습니다.")
    warnings = [
        f"Brave 무료 검색 사용량 {usage['used']}/{usage['limit']} | 이번 달 남은 {usage['remaining']}건",
    ]
    cache_value = usage.get("cache")
    if cache_value == "hit":
        warnings.append("같은 키워드 캐시를 사용해 Brave 검색을 다시 호출하지 않았습니다.")
    if skipped:
        warnings.append(f"검색 결과 중 {skipped}개는 본문 추출에 실패해 제외했습니다.")
    updated = db.update_project(
        pid,
        source_draft_state="done",
        source_draft_progress=100,
        source_draft_error="",
        source_draft_input_mode="keyword",
        source_draft_query=keyword.strip(),
        source_draft_sources=sources,
        source_draft_fact_notes=fact_notes,
        source_draft_script="",
        source_draft_previous_script="",
        source_draft_warnings=warnings,
        source_draft_model="",
        source_draft_risk_score=0.0,
    )
    if updated is None:
        raise RuntimeError(f"project {pid} not found")
    return updated


def _apply_source_draft(project: ProjectRecord) -> ProjectRecord:
    draft_script = project["source_draft_script"].strip()
    if not draft_script:
        raise RuntimeError("No source draft script is available for apply.")
    options = normalize_options(project["autopilot_options"])
    compiled_script, regional_sentences = compile_script("standard", draft_script)
    sentences = flatten_regional_sentences(regional_sentences)
    project_dir = db.project_dir(project["id"])
    (project_dir / "script.txt").write_text(draft_script, encoding="utf-8")
    (project_dir / "compiled_script.txt").write_text(compiled_script, encoding="utf-8")
    updated = db.update_project(
        project["id"],
        script=draft_script,
        user_script=draft_script,
        compiled_script=compiled_script,
        regional_sentences=regional_sentences,
        sentences=sentences,
        content_mode="standard",
        visual_source_mode=options["visual_source_mode"],
    )
    if updated is None:
        raise RuntimeError(f"project {project['id']} not found")
    return updated


def _save_script_input(project: ProjectRecord, options: AutopilotOptions) -> ProjectRecord:
    script = options["script"].strip()
    compiled_script, regional_sentences = compile_script(project["content_mode"], script)
    sentences = flatten_regional_sentences(regional_sentences)
    project_dir = db.project_dir(project["id"])
    (project_dir / "script.txt").write_text(script, encoding="utf-8")
    (project_dir / "compiled_script.txt").write_text(compiled_script, encoding="utf-8")
    subtitle_style = normalize_subtitle_style(project["subtitle_style"])
    if subtitle_style["cue_split_mode"] == "sentence":
        subtitle_style["cue_split_mode"] = "readable"
    updated = db.update_project(
        project["id"],
        script=script,
        user_script=script,
        compiled_script=compiled_script,
        regional_sentences=regional_sentences,
        sentences=sentences,
        visual_source_mode=options["visual_source_mode"],
        subtitle_style=subtitle_style,
    )
    if updated is None:
        raise RuntimeError(f"project {project['id']} not found")
    return updated


def _first_preflight_failure(checks: list[PreflightCheck]) -> PreflightCheck | None:
    for check in checks:
        if not check["ok"]:
            return check
    return None


def run_autopilot_job(pid: str) -> None:
    project = _require_project(pid)
    options = normalize_options(project["autopilot_options"])

    try:
        project = _update_runtime(
            pid,
            project=project,
            state="running",
            phase="prepare_input",
            progress=5,
            last_log="Preparing autopilot input.",
            debug_summary="Validating the selected input mode.",
            event="phase_start",
        )
        if options["input_mode"] == "script":
            project = _save_script_input(project, options)
        elif options["input_mode"] == "url":
            project = _update_runtime(
                pid,
                project=project,
                phase="source_collect",
                progress=10,
                last_log="Analyzing source URL.",
                debug_summary="Collecting fact notes from the source URL.",
                event="phase_start",
                debug={"url": options["url"]},
            )
            project = _collect_url_source(pid, options["url"])
            project = _queue_source_draft(project, options)
            project = _update_runtime(
                pid,
                project=project,
                phase="source_generate",
                progress=20,
                last_log="Queued source draft generation.",
                debug_summary="Waiting for source draft worker.",
                event="phase_start",
            )
            project = _wait_for_state(
                pid,
                field="source_draft_state",
                done_value="done",
                phase="source_generate",
                progress=30,
                message="Waiting for source draft worker to complete.",
                state_label="Source draft generation",
            )
        elif options["input_mode"] == "keyword":
            project = _update_runtime(
                pid,
                project=project,
                phase="source_collect",
                progress=10,
                last_log="Collecting sources from keyword.",
                debug_summary="Running Brave keyword research.",
                event="phase_start",
                debug={"keyword": options["keyword"]},
            )
            project = _collect_keyword_sources(pid, options["keyword"])
            project = _queue_source_draft(project, options)
            project = _update_runtime(
                pid,
                project=project,
                phase="source_generate",
                progress=20,
                last_log="Queued source draft generation.",
                debug_summary="Waiting for source draft worker.",
                event="phase_start",
            )
            project = _wait_for_state(
                pid,
                field="source_draft_state",
                done_value="done",
                phase="source_generate",
                progress=30,
                message="Waiting for source draft worker to complete.",
                state_label="Source draft generation",
            )
        else:
            _pause_with_failure(
                pid,
                project=project,
                error_code="INPUT_MODE_NOT_IMPLEMENTED",
                message=f"{options['input_mode']} mode is not implemented yet.",
                action_hint="지원되는 입력 모드로 다시 시작해 주세요.",
            )
            return

        project = _require_project(pid)
        if options["input_mode"] in {"url", "keyword"}:
            threshold = risk_threshold_for_mode(project["source_draft_regenerate_mode"])
            if project["source_draft_risk_score"] >= threshold:
                _pause_with_failure(
                    pid,
                    project=project,
                    error_code="COPY_RISK_HIGH",
                    message=f"Generated source draft risk score is too high ({project['source_draft_risk_score']:.0%}).",
                    action_hint="초안 내용을 검토하고 재생성하거나 직접 수정한 뒤 다시 시작해 주세요.",
                )
                return
            existing_user_script = project["user_script"].strip()
            if existing_user_script and existing_user_script != project["source_draft_script"].strip():
                _backup_user_script(pid, existing_user_script)
                _pause_with_failure(
                    pid,
                    project=project,
                    error_code="COPY_USER_SCRIPT_OVERWRITE",
                    message="Existing user_script would be overwritten by source draft apply.",
                    action_hint="백업 파일을 확인한 뒤 적용 여부를 결정해 주세요.",
                )
                return
            project = _update_runtime(
                pid,
                project=project,
                phase="source_apply",
                progress=35,
                last_log="Applying generated source draft to the script.",
                debug_summary="Applying source draft.",
                event="phase_start",
            )
            project = _apply_source_draft(project)

        autopilot_preset, autopilot_tts_profile, tts_overridden = _effective_autopilot_tts_profile(project)
        project = db.update_project(
            pid,
            voice_preset=autopilot_preset,
            tts_profile=autopilot_tts_profile,
        ) or _require_project(pid)
        tts_debug = {
            "voice_preset": autopilot_preset,
            "mode": autopilot_tts_profile["mode"],
            "seed_mode": autopilot_tts_profile["seed_mode"],
            "instruct": autopilot_tts_profile["instruct"],
            "autopilot_default_applied": tts_overridden,
        }
        project = _update_runtime(
            pid,
            project=project,
            phase="tts_enqueue",
            progress=40,
            last_log="Queued TTS generation.",
            debug_summary="Waiting for TTS worker.",
            event="phase_start",
            debug=tts_debug,
        )
        db.update_project(
            pid,
            tts_state="queued",
            tts_progress=0,
            tts_error="",
            tts_job_id="",
            tts_started_at="",
            tts_heartbeat_at="",
        )
        project = _wait_for_state(
            pid,
            field="tts_state",
            done_value="done",
            phase="tts_wait",
            progress=52,
            message="Waiting for TTS worker to complete.",
            state_label="TTS generation",
        )

        if options["visual_source_mode"] in {"comfyui_auto", "hybrid"}:
            db.update_project(
                pid,
                body_image_state="error",
                body_image_progress=0,
                body_image_error=IMAGE_GEN_DISABLED_CODE,
                body_image_phase="disabled",
                body_image_last_log=IMAGE_GEN_DISABLED_MESSAGE,
                body_image_job_id="",
                body_image_started_at="",
                body_image_heartbeat_at="",
            )
            _pause_with_failure(
                pid,
                project=project,
                error_code=IMAGE_GEN_DISABLED_CODE,
                message=IMAGE_GEN_DISABLED_MESSAGE,
                action_hint="Upload media manually or wait for the D2 Z-Image backend.",
            )
            return
        elif not project["media_order"]:
            _pause_with_failure(
                pid,
                project=project,
                error_code="IMAGE_MEDIA_REQUIRED",
                message="No uploaded media is available and visual mode is upload_only.",
                action_hint="업로드 전용 모드에서는 미디어를 먼저 업로드하거나 comfyui_auto 모드로 시작해 주세요.",
            )
            return

        project = _require_project(pid)
        project = _update_runtime(
            pid,
            project=project,
            phase="plan_refresh",
            progress=78,
            last_log="Refreshing scene and render plans.",
            debug_summary="Building scene and render plans.",
            event="phase_start",
        )
        scene_plan = build_scene_plan(project, render_format=_preferred_render_format(project))
        project = db.update_project(pid, scene_plan=scene_plan) or _require_project(pid)
        render_plan = build_render_plan(project)
        project = db.update_project(pid, render_plan=render_plan) or _require_project(pid)

        project = _update_runtime(
            pid,
            project=project,
            phase="preflight",
            progress=84,
            last_log="Running preflight checks.",
            debug_summary="Checking render readiness.",
            event="phase_start",
        )
        report = build_preflight_report(project)
        if not report["ok"]:
            failed = _first_preflight_failure(report["checks"])
            if failed is None:
                raise RuntimeError("Preflight failed without a detailed check.")
            _pause_with_failure(
                pid,
                project=project,
                error_code=f"PREFLIGHT_{failed['key'].upper()}",
                message=failed["message"],
                action_hint="Step 4 Preflight 결과를 확인하고 필요한 항목을 수정한 뒤 재개해 주세요.",
            )
            return
        if not options["render_after_preflight"]:
            _update_runtime(
                pid,
                project=project,
                state="done",
                phase="done",
                progress=100,
                last_log="Autopilot completed through preflight.",
                debug_summary="Stopped after preflight by option.",
                event="done",
            )
            return

        project = _update_runtime(
            pid,
            project=project,
            phase="render_enqueue",
            progress=88,
            last_log="Queueing render job.",
            debug_summary="Render queued.",
            event="phase_start",
        )
        db.update_project(
            pid,
            render_state="queued",
            render_progress=0,
            render_phase="queued",
            render_phase_pct=0,
            render_progress_detail="",
            render_speed_x=0.0,
            render_eta_sec=0,
            render_job_id="",
            render_started_at="",
            render_heartbeat_at="",
            render_last_log="",
        )
        project = _wait_for_state(
            pid,
            field="render_state",
            done_value="done",
            phase="render_wait",
            progress=96,
            message="Waiting for render worker to complete.",
            state_label="Render",
        )
        render_report = load_render_report(pid)
        report_summary = "Render completed."
        if render_report is not None:
            report_summary = f"Render completed with {len(render_report['outputs'])} output(s)."
        _update_runtime(
            pid,
            project=project,
            state="done",
            phase="done",
            progress=100,
            last_log=report_summary,
            debug_summary=report_summary,
            event="done",
        )
    except HTTPException as exc:
        project = _require_project(pid)
        error_code = "SYSTEM_AUTOPILOT_HTTP_ERROR"
        action_hint = "입력값과 도구 상태를 확인한 뒤 다시 시도해 주세요."
        if exc.status_code == 429:
            error_code = "BRAVE_RATE_LIMIT"
            action_hint = "Brave 무료 검색 한도를 초과했습니다. 다음 달 리셋 후 다시 시도하거나 직접 대본 입력으로 진행해 주세요."
        _pause_with_failure(
            pid,
            project=project,
            error_code=error_code,
            message=str(exc.detail),
            action_hint=action_hint,
        )
    except Exception as exc:
        project = _require_project(pid)
        _pause_with_failure(
            pid,
            project=project,
            error_code="SYSTEM_AUTOPILOT_RUN_FAILED",
            message=str(exc),
            action_hint="오토파일럿 디버그 로그를 확인하고 입력 또는 도구 상태를 점검해 주세요.",
        )
