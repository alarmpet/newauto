from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from .. import db
from ..services.image_generation_disabled import disabled_payload, raise_disabled

router = APIRouter(prefix="/api/projects", tags=["image-gen"])


class DisabledPayload(BaseModel):
    model_config = ConfigDict(extra="allow")


def _require_project(pid: str) -> None:
    if db.get_project(pid) is None:
        raise HTTPException(status_code=404, detail="Project not found")


def _disabled_response(pid: str) -> dict[str, object]:
    _require_project(pid)
    return {"disabled": True, **disabled_payload()}


@router.get("/{pid}/comfyui/prompt-suggestion")
def get_comfyui_prompt_suggestion(pid: str, sentence_idx: int = 0) -> dict[str, object]:
    _require_project(pid)
    return {
        "sentence_idx": sentence_idx,
        "template_id": "",
        "positive_prompt": "",
        "negative_prompt": "",
        "disabled": True,
        **disabled_payload(),
    }


@router.get("/{pid}/comfyui/prompt-suggestions")
def get_comfyui_prompt_suggestions(pid: str, start_idx: int = 0, count: int = 3) -> dict[str, object]:
    _require_project(pid)
    return {
        "start_idx": start_idx,
        "count": count,
        "prompts": [],
        "disabled": True,
        **disabled_payload(),
    }


@router.post("/{pid}/media-simple/prompt-manifest")
def create_simple_media_prompt_manifest(pid: str, payload: DisabledPayload) -> dict[str, object]:
    return _disabled_response(pid)


@router.post("/{pid}/media-simple/lmstudio-unload")
def unload_simple_media_lmstudio(pid: str) -> dict[str, object]:
    return _disabled_response(pid)


@router.post("/{pid}/comfyui/workflow/render")
def render_comfyui_workflow(pid: str, payload: DisabledPayload) -> dict[str, object]:
    _require_project(pid)
    raise_disabled()
    return {}


@router.post("/{pid}/comfyui/workflow/submit")
def submit_comfyui_workflow(pid: str, payload: DisabledPayload) -> dict[str, object]:
    _require_project(pid)
    raise_disabled()
    return {}


@router.post("/{pid}/comfyui/job")
def enqueue_comfyui_job(pid: str, payload: DisabledPayload) -> dict[str, object]:
    _require_project(pid)
    db.update_project(
        pid,
        body_image_state="error",
        body_image_progress=0,
        body_image_error=disabled_payload()["error"],
        body_image_phase="disabled",
        body_image_last_log=disabled_payload()["message"],
    )
    raise_disabled()
    return {}


@router.post("/{pid}/comfyui/job/batch-auto")
def enqueue_comfyui_batch_job(pid: str, payload: DisabledPayload) -> dict[str, object]:
    return enqueue_comfyui_job(pid, payload)


@router.post("/{pid}/media-simple/comfyui/job")
def enqueue_simple_media_comfyui_job(pid: str, payload: DisabledPayload) -> dict[str, object]:
    return enqueue_comfyui_job(pid, payload)


@router.post("/{pid}/visual-diagnostics/regenerate")
def regenerate_visual_diagnostics(pid: str) -> dict[str, object]:
    return _disabled_response(pid)


@router.get("/{pid}/comfyui/history/{prompt_id}")
def get_comfyui_history(pid: str, prompt_id: str) -> dict[str, object]:
    _require_project(pid)
    return {"prompt_id": prompt_id, "history": {}, "disabled": True, **disabled_payload()}


@router.post("/{pid}/comfyui/history/import")
def import_comfyui_history_image(pid: str, payload: DisabledPayload) -> dict[str, object]:
    _require_project(pid)
    raise_disabled()
    return {}


@router.post("/{pid}/comfyui/candidates/select")
def select_comfyui_candidate(pid: str, payload: DisabledPayload) -> dict[str, object]:
    return _disabled_response(pid)


@router.get("/{pid}/comfyui/status")
def comfyui_status(pid: str) -> dict[str, object]:
    return _disabled_response(pid)


@router.delete("/{pid}/comfyui/job")
def cancel_comfyui_job(pid: str) -> dict[str, Any]:
    _require_project(pid)
    updated = db.update_project(
        pid,
        body_image_state="idle",
        body_image_progress=0,
        body_image_error="",
        body_image_phase="",
        body_image_last_log="",
        body_image_job_id="",
        body_image_started_at="",
        body_image_heartbeat_at="",
    )
    return {"ok": updated is not None, "disabled": True, **disabled_payload()}
