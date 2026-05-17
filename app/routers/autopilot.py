from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .. import db
from ..services import autopilot as autopilot_svc
from ..types import (
    AutopilotDebugSnapshot,
    AutopilotEvent,
    AutopilotImageCount,
    AutopilotInputMode,
    AutopilotOptions,
    SourceRegenerateMode,
    VisualSourceMode,
)

router = APIRouter(prefix="/api/projects", tags=["autopilot"])


class AutopilotStartPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_mode: AutopilotInputMode = "script"
    script: str = ""
    url: str = ""
    keyword: str = ""
    tone: str = Field(default="documentary", min_length=1, max_length=60)
    target_minutes: int | Literal["auto"] = "auto"
    regenerate_mode: SourceRegenerateMode = ""
    visual_source_mode: VisualSourceMode = "comfyui_auto"
    image_count: AutopilotImageCount = "auto"
    render_after_preflight: bool = True
    debug_verbose: bool = False

    @field_validator("script", "url", "keyword", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> str:
        return str(value or "").strip()

    @field_validator("target_minutes", mode="before")
    @classmethod
    def normalize_target_minutes(cls, value: object) -> int | Literal["auto"]:
        if value in {"", None, "auto"}:
            return "auto"
        if isinstance(value, int):
            return max(1, min(15, value))
        if isinstance(value, str):
            parsed = int(value)
            return max(1, min(15, parsed))
        raise ValueError("invalid target_minutes")

    @field_validator("image_count", mode="before")
    @classmethod
    def normalize_image_count(cls, value: object) -> AutopilotImageCount:
        if value in {"", None, "auto"}:
            return "auto"
        if isinstance(value, bool):
            raise ValueError("invalid image_count")
        if isinstance(value, int):
            return max(1, min(48, value))
        if isinstance(value, str):
            parsed = int(value)
            return max(1, min(48, parsed))
        raise ValueError("invalid image_count")

    def to_options(self) -> AutopilotOptions:
        return {
            "input_mode": self.input_mode,
            "script": self.script,
            "url": self.url,
            "keyword": self.keyword,
            "tone": self.tone.strip(),
            "target_minutes": str(self.target_minutes),
            "regenerate_mode": self.regenerate_mode,
            "visual_source_mode": self.visual_source_mode,
            "image_count": self.image_count,
            "render_after_preflight": self.render_after_preflight,
            "debug_verbose": self.debug_verbose,
        }


def _require(pid: str) -> None:
    if db.get_project(pid) is None:
        raise HTTPException(404, f"project {pid} not found")


def _validate_start_payload(payload: AutopilotStartPayload) -> None:
    if payload.input_mode == "script" and not payload.script:
        raise HTTPException(400, "script input is required")
    if payload.input_mode == "url" and not payload.url:
        raise HTTPException(400, "url input is required")
    if payload.input_mode == "keyword" and not payload.keyword:
        raise HTTPException(400, "keyword input is required")


@router.post("/{pid}/autopilot/start")
def start_autopilot(pid: str, payload: AutopilotStartPayload) -> dict[str, object]:
    _require(pid)
    _validate_start_payload(payload)
    project = autopilot_svc.start(pid, payload.to_options())
    return {
        "project": project,
        "status": {
            "state": project["autopilot_state"],
            "progress": project["autopilot_progress"],
            "phase": project["autopilot_phase"],
        },
    }


@router.get("/{pid}/autopilot/status")
def get_autopilot_status(pid: str) -> dict[str, object]:
    _require(pid)
    project = db.get_project(pid)
    if project is None:
        raise HTTPException(404, f"project {pid} not found")
    return {
        "state": project["autopilot_state"],
        "progress": project["autopilot_progress"],
        "phase": project["autopilot_phase"],
        "last_log": project["autopilot_last_log"],
        "error": project["autopilot_error"],
        "job_id": project["autopilot_job_id"],
        "started_at": project["autopilot_started_at"],
        "heartbeat_at": project["autopilot_heartbeat_at"],
        "last_error_code": project["autopilot_last_error_code"],
        "debug_summary": project["autopilot_debug_summary"],
        "wait_started_at": project["autopilot_wait_started_at"],
        "retry_count": project["autopilot_retry_count"],
        "options": project["autopilot_options"],
    }


@router.get("/{pid}/autopilot/events")
def get_autopilot_events(pid: str, limit: int = 100) -> list[AutopilotEvent]:
    _require(pid)
    return autopilot_svc.list_events(pid, limit=limit)


@router.get("/{pid}/autopilot/debug")
def get_autopilot_debug(pid: str) -> AutopilotDebugSnapshot:
    _require(pid)
    return autopilot_svc.load_debug_snapshot(pid)


@router.post("/{pid}/autopilot/pause")
def pause_autopilot(pid: str) -> dict[str, object]:
    _require(pid)
    project = autopilot_svc.pause(pid)
    return {"project": project}


@router.post("/{pid}/autopilot/resume")
def resume_autopilot(pid: str) -> dict[str, object]:
    _require(pid)
    project = autopilot_svc.resume(pid)
    return {"project": project}


@router.post("/{pid}/autopilot/cancel")
def cancel_autopilot(pid: str) -> dict[str, object]:
    _require(pid)
    project = autopilot_svc.cancel(pid)
    return {"project": project}
