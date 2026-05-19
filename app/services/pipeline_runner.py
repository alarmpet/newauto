from __future__ import annotations

from typing import Literal, TypedDict, cast

from .. import db
from ..types import PipelineManifest, ProjectRecord
from .pipeline_manifest import text_hash, update_stage_status

AutopilotStage = Literal[
    "prepare_input",
    "script_compile",
    "visual_plan",
    "tts",
    "image",
    "render_plan",
    "preflight",
    "render",
]


class StageResult(TypedDict):
    stage: AutopilotStage
    state: str
    input_hash: str
    output_hash: str
    error_code: str
    recovery_hint: str

AUTOPILOT_STAGES = [
    "prepare_input",
    "script_compile",
    "visual_plan",
    "tts",
    "image",
    "render_plan",
    "preflight",
    "render",
]

AUTOPILOT_PHASE_STAGE_MAP: dict[str, AutopilotStage] = {
    "prepare_input": "prepare_input",
    "source_collect": "prepare_input",
    "source_generate": "script_compile",
    "source_apply": "script_compile",
    "tts_enqueue": "tts",
    "tts_wait": "tts",
    "image_enqueue": "image",
    "image_wait": "image",
    "plan_refresh": "render_plan",
    "preflight": "preflight",
    "render_enqueue": "render",
    "render_wait": "render",
}


def _require_project(pid: str) -> ProjectRecord:
    project = db.get_project(pid)
    if project is None:
        raise RuntimeError(f"project {pid} not found")
    return project


def _require_stage(stage: str) -> AutopilotStage:
    if stage not in AUTOPILOT_STAGES:
        raise ValueError(f"unknown autopilot stage: {stage}")
    return cast(AutopilotStage, stage)


def _empty_stage_status(state: str = "idle") -> dict[str, str]:
    return {
        "state": state,
        "error_code": "",
        "recovery_hint": "",
        "input_hash": "",
        "output_hash": "",
    }


def initialize_autopilot_stage_status(pid: str, *, input_text: str = "") -> dict[str, object]:
    project = _require_project(pid)
    manifest = dict(project["pipeline_manifest"])
    stage_status = dict(manifest.get("stage_status") or {})
    for stage in AUTOPILOT_STAGES:
        stage_status[stage] = _empty_stage_status("idle")
    stage_status["prepare_input"] = {
        "state": "queued",
        "error_code": "",
        "recovery_hint": "",
        "input_hash": text_hash(input_text),
        "output_hash": "",
    }
    manifest["stage_status"] = stage_status
    updated = db.update_project(pid, pipeline_manifest=manifest)
    if updated is None:
        raise RuntimeError(f"project {pid} not found")
    return dict(updated["pipeline_manifest"])


def _write_stage_status(
    pid: str,
    stage: str,
    *,
    state: str,
    input_text: str = "",
    output_text: str = "",
    error_code: str = "",
    recovery_hint: str = "",
) -> PipelineManifest:
    project = _require_project(pid)
    checked_stage = _require_stage(stage)
    manifest = cast(PipelineManifest, project["pipeline_manifest"])
    updated_manifest = update_stage_status(
        manifest,
        checked_stage,
        state=state,
        error_code=error_code,
        recovery_hint=recovery_hint,
        input_hash=text_hash(input_text) if input_text else "",
        output_hash=text_hash(output_text) if output_text else "",
    )
    updated = db.update_project(pid, pipeline_manifest=updated_manifest)
    if updated is None:
        raise RuntimeError(f"project {pid} not found")
    return cast(PipelineManifest, updated["pipeline_manifest"])


def mark_stage_running(pid: str, stage: str, *, input_text: str = "") -> PipelineManifest:
    return _write_stage_status(pid, stage, state="running", input_text=input_text)


def mark_stage_done(pid: str, stage: str, *, output_text: str = "") -> PipelineManifest:
    return _write_stage_status(pid, stage, state="done", output_text=output_text)


def mark_stage_error(
    pid: str,
    stage: str,
    *,
    error_code: str,
    recovery_hint: str,
) -> PipelineManifest:
    return _write_stage_status(
        pid,
        stage,
        state="error",
        error_code=error_code,
        recovery_hint=recovery_hint,
    )


def first_incomplete_stage(project: ProjectRecord) -> AutopilotStage | None:
    manifest = project["pipeline_manifest"]
    if not isinstance(manifest, dict):
        return "prepare_input"
    stage_status = manifest.get("stage_status")
    if not isinstance(stage_status, dict):
        return "prepare_input"
    for stage in AUTOPILOT_STAGES:
        status = stage_status.get(stage)
        if not isinstance(status, dict) or status.get("state") != "done":
            return cast(AutopilotStage, stage)
    return None


def stage_for_autopilot_phase(phase: str) -> AutopilotStage | None:
    return AUTOPILOT_PHASE_STAGE_MAP.get(phase)
