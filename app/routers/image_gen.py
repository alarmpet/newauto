from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from .. import db
from ..services.comfyui_client import ComfyUIClient
from ..services.comfyui_pipeline import import_history_image, submit_z_image_workflow
from ..services.image_prompt import build_z_image_prompt
from ..services.z_image_workflow import Z_IMAGE_TEMPLATE_ID, load_z_image_workflow
from ..types import ProjectRecord

router = APIRouter(prefix="/api/projects", tags=["image-gen"])


class ImageGenPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    sentence_idx: int = 0
    aspect_ratio: str = "16:9"
    negative_prompt_override: str = ""
    timeout_sec: int = 180


def _require_project(pid: str) -> None:
    if db.get_project(pid) is None:
        raise HTTPException(status_code=404, detail="Project not found")


def _project_or_404(pid: str) -> ProjectRecord:
    project = db.get_project(pid)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _sentence_at(project: ProjectRecord, sentence_idx: int) -> str:
    if sentence_idx < 0 or sentence_idx >= len(project["sentences"]):
        raise HTTPException(status_code=400, detail="sentence_idx is out of range")
    return project["sentences"][sentence_idx]


def _project_image_options(project: ProjectRecord, payload: ImageGenPayload) -> dict[str, object]:
    options = dict(project["body_image_options"])
    aspect_ratio = payload.aspect_ratio or str(options.get("aspect_ratio") or "16:9")
    negative_override = payload.negative_prompt_override or str(options.get("negative_prompt_override") or "")
    return {
        "image_backend_version": "v1",
        "aspect_ratio": aspect_ratio,
        "negative_prompt_override": negative_override,
        "image_count_per_sentence": int(options.get("image_count_per_sentence") or 1),
    }


def _prompt_for(project: ProjectRecord, payload: ImageGenPayload) -> tuple[str, str, dict[str, object]]:
    options = _project_image_options(project, payload)
    prompt = build_z_image_prompt(
        _sentence_at(project, payload.sentence_idx),
        negative_prompt_override=str(options["negative_prompt_override"]),
    )
    return prompt.positive, prompt.negative, options


@router.get("/{pid}/comfyui/prompt-suggestion")
def get_comfyui_prompt_suggestion(pid: str, sentence_idx: int = 0) -> dict[str, object]:
    project = _project_or_404(pid)
    payload = ImageGenPayload(sentence_idx=sentence_idx)
    positive, negative, _ = _prompt_for(project, payload)
    return {
        "sentence_idx": sentence_idx,
        "template_id": Z_IMAGE_TEMPLATE_ID,
        "positive_prompt": positive,
        "negative_prompt": negative,
        "backend": "z_image_turbo_korean",
    }


@router.get("/{pid}/comfyui/prompt-suggestions")
def get_comfyui_prompt_suggestions(pid: str, start_idx: int = 0, count: int = 3) -> dict[str, object]:
    project = _project_or_404(pid)
    prompts = []
    for sentence_idx in range(max(0, start_idx), min(len(project["sentences"]), start_idx + max(1, count))):
        positive, negative, _ = _prompt_for(project, ImageGenPayload(sentence_idx=sentence_idx))
        prompts.append({"sentence_idx": sentence_idx, "positive_prompt": positive, "negative_prompt": negative})
    return {
        "start_idx": start_idx,
        "count": count,
        "prompts": prompts,
        "template_id": Z_IMAGE_TEMPLATE_ID,
        "backend": "z_image_turbo_korean",
    }


@router.post("/{pid}/media-simple/prompt-manifest")
def create_simple_media_prompt_manifest(pid: str, payload: ImageGenPayload) -> dict[str, object]:
    project = _project_or_404(pid)
    prompts = []
    for sentence_idx, _sentence in enumerate(project["sentences"]):
        positive, negative, _ = _prompt_for(project, ImageGenPayload(sentence_idx=sentence_idx))
        prompts.append({"sentence_idx": sentence_idx, "positive_prompt": positive, "negative_prompt": negative})
    return {"ok": True, "prompts": prompts, "template_id": Z_IMAGE_TEMPLATE_ID}


@router.post("/{pid}/media-simple/lmstudio-unload")
def unload_simple_media_lmstudio(pid: str) -> dict[str, object]:
    _require_project(pid)
    return {"ok": True, "message": "Z-Image prompt building does not require LM Studio unload."}


@router.post("/{pid}/comfyui/workflow/render")
def render_comfyui_workflow(pid: str, payload: ImageGenPayload) -> dict[str, object]:
    project = _project_or_404(pid)
    positive, negative, options = _prompt_for(project, payload)
    workflow = load_z_image_workflow(
        positive_prompt=positive,
        negative_prompt=negative,
        aspect_ratio=str(options["aspect_ratio"]),
        filename_prefix=f"newauto_{pid}_{payload.sentence_idx}",
    )
    return {"template_id": Z_IMAGE_TEMPLATE_ID, "workflow": workflow, "positive_prompt": positive, "negative_prompt": negative}


@router.post("/{pid}/comfyui/workflow/submit")
def submit_comfyui_workflow(pid: str, payload: ImageGenPayload) -> dict[str, object]:
    project = _project_or_404(pid)
    positive, negative, options = _prompt_for(project, payload)
    prompt_id, results = submit_z_image_workflow(
        ComfyUIClient(timeout_sec=min(max(payload.timeout_sec, 1), 600)),
        positive_prompt=positive,
        negative_prompt=negative,
        aspect_ratio=str(options["aspect_ratio"]),
        filename_prefix=f"newauto_{pid}_{payload.sentence_idx}",
        timeout_sec=min(max(payload.timeout_sec, 1), 600),
    )
    mapping = import_history_image(
        project,
        result=results[0],
        prompt=positive,
        prompt_id=prompt_id,
        sentence_idx=payload.sentence_idx,
        selected_reason="z_image_turbo_korean",
    )
    return {"ok": True, "prompt_id": prompt_id, "mapping": mapping}


@router.post("/{pid}/comfyui/job")
def enqueue_comfyui_job(pid: str, payload: ImageGenPayload) -> dict[str, object]:
    project = _project_or_404(pid)
    _positive, _negative, options = _prompt_for(project, payload)
    db.update_project(
        pid,
        body_image_state="queued",
        body_image_progress=0,
        body_image_error="",
        body_image_phase="queued",
        body_image_last_log="Z-Image Turbo image job queued.",
        body_image_options={**options, "queued_sentence_idx": payload.sentence_idx},
    )
    return {"ok": True, "state": "queued", "backend": "z_image_turbo_korean"}


@router.post("/{pid}/comfyui/job/batch-auto")
def enqueue_comfyui_batch_job(pid: str, payload: ImageGenPayload) -> dict[str, object]:
    project = _project_or_404(pid)
    options = _project_image_options(project, payload)
    db.update_project(
        pid,
        body_image_state="queued",
        body_image_progress=0,
        body_image_error="",
        body_image_phase="queued",
        body_image_last_log="Z-Image Turbo batch image job queued.",
        body_image_options=options,
    )
    return {"ok": True, "state": "queued", "backend": "z_image_turbo_korean", "count": len(project["sentences"])}


@router.post("/{pid}/media-simple/comfyui/job")
def enqueue_simple_media_comfyui_job(pid: str, payload: ImageGenPayload) -> dict[str, object]:
    return enqueue_comfyui_job(pid, payload)


@router.post("/{pid}/visual-diagnostics/regenerate")
def regenerate_visual_diagnostics(pid: str) -> dict[str, object]:
    _require_project(pid)
    return {"ok": True, "message": "Visual diagnostics can be regenerated after Z-Image mappings exist."}


@router.get("/{pid}/comfyui/history/{prompt_id}")
def get_comfyui_history(pid: str, prompt_id: str) -> dict[str, object]:
    _require_project(pid)
    return {"prompt_id": prompt_id, "history": ComfyUIClient().get_history(prompt_id)}


@router.post("/{pid}/comfyui/history/import")
def import_comfyui_history_image(pid: str, payload: ImageGenPayload) -> dict[str, object]:
    _require_project(pid)
    raise HTTPException(400, "Import by history id is not wired for D2 yet; submit through the Z-Image endpoint.")


@router.post("/{pid}/comfyui/candidates/select")
def select_comfyui_candidate(pid: str, payload: ImageGenPayload) -> dict[str, object]:
    _require_project(pid)
    return {"ok": True, "message": "Z-Image D2 stores the first returned image as the selected mapping."}


@router.get("/{pid}/comfyui/status")
def comfyui_status(pid: str) -> dict[str, object]:
    project = _project_or_404(pid)
    return {
        "ok": True,
        "backend": "z_image_turbo_korean",
        "state": project["body_image_state"],
        "progress": project["body_image_progress"],
        "phase": project["body_image_phase"],
        "last_log": project["body_image_last_log"],
    }


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
    return {"ok": updated is not None}
