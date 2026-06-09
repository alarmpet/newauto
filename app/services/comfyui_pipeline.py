from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import TypedDict

from fastapi import HTTPException

from .. import db
from ..config import ALLOWED_IMAGE_EXT, COMFYUI_INSTALL_DIR
from ..types import BodyImageMapping, ProjectRecord
from .comfyui_client import ComfyImageResult, ComfyUIClient
from .comfyui_workflows import PlaceholderMap, render_workflow_template
from .pipeline_manifest import record_image_attempt, text_hash, update_stage_status
from .visual_relevance import sentence_hash
from .z_image_workflow import load_z_image_workflow


class CandidateSelectionDecision(TypedDict):
    selected_path: str
    selected_prompt: str
    selected_prompt_id: str
    selected_index: int
    selected_total: int
    selected_score: float
    selected_score_version: str
    selection_reason: str
    retry_recommended: bool
    retry_reason: str


def _sanitize_filename(filename: str) -> str:
    clean_name = "".join(char if char.isalnum() or char in "._-" else "_" for char in filename).strip("._")
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_IMAGE_EXT:
        suffix = ".png"
    return f"{Path(clean_name).stem or 'image'}{suffix}"


def _unique_media_path(media_dir: Path, filename: str) -> Path:
    target = media_dir / _sanitize_filename(filename)
    counter = 0
    while target.exists():
        counter += 1
        target = media_dir / f"{target.stem}_{counter}{target.suffix}"
    return target


def resolve_comfy_output_path(result: ComfyImageResult, install_dir: Path = COMFYUI_INSTALL_DIR) -> Path:
    base_dir = install_dir / result.type
    candidate = base_dir / result.subfolder / result.filename if result.subfolder else base_dir / result.filename
    if candidate.exists():
        return candidate
    fallback = install_dir / "output" / result.filename
    if fallback.exists():
        return fallback
    raise HTTPException(status_code=404, detail=f"ComfyUI output file not found: {result.filename}")


def import_history_image(
    project: ProjectRecord,
    *,
    result: ComfyImageResult,
    prompt: str,
    prompt_id: str,
    sentence_idx: int = 0,
    selected_reason: str = "manual_import",
    candidate_score: float = 1.0,
    seed: int = 0,
    issue_codes: list[str] | None = None,
    character_descriptor_applied: bool = False,
) -> BodyImageMapping:
    source_path = resolve_comfy_output_path(result)
    media_dir = db.project_dir(project["id"]) / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    target = _unique_media_path(media_dir, source_path.name)
    shutil.copy2(source_path, target)
    mapping: BodyImageMapping = {
        "sentence_idx": sentence_idx,
        "path": target.name,
        "prompt": prompt,
        "sentence_text": project["sentences"][sentence_idx] if sentence_idx < len(project["sentences"]) else "",
        "sentence_hash": sentence_hash(project["sentences"][sentence_idx]) if sentence_idx < len(project["sentences"]) else "",
        "project_id": project["id"],
        "prompt_id": prompt_id,
        "selected_reason": selected_reason,
        "candidate_score": candidate_score,
        "candidate_score_version": "pipeline_manifest_v1",
        "vision_qa_issue_codes": issue_codes or [],
        "character_descriptor_applied": character_descriptor_applied,
    }
    mappings = [item for item in project["body_image_mappings"] if item["sentence_idx"] != sentence_idx]
    mappings.append(mapping)
    prompt_hash = text_hash(prompt)
    pipeline_manifest = record_image_attempt(
        project["pipeline_manifest"],
        sentence_idx=sentence_idx,
        path=target.name,
        prompt_id=prompt_id,
        attempt=1,
        seed=seed,
        prompt_hash=prompt_hash,
        candidate_score=candidate_score,
        issue_codes=issue_codes or [],
        selected=True,
    )
    pipeline_manifest = update_stage_status(
        pipeline_manifest,
        "image",
        state="done",
        input_hash=prompt_hash,
        output_hash=text_hash(target.name),
    )
    db.update_project(
        project["id"],
        body_image_mappings=sorted(mappings, key=lambda item: item["sentence_idx"]),
        pipeline_manifest=pipeline_manifest,
    )
    return mapping


def submit_template(
    client: ComfyUIClient,
    *,
    template_id: str,
    placeholders: PlaceholderMap,
    timeout_sec: int = 180,
) -> tuple[str, list[ComfyImageResult]]:
    workflow = render_workflow_template(template_id, placeholders)
    submission = client.submit_workflow(workflow)
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        history = client.get_history(submission.prompt_id)
        results = client.extract_image_results(history, submission.prompt_id)
        if results:
            return submission.prompt_id, results
        error = client.extract_execution_error(history, submission.prompt_id)
        if error:
            raise HTTPException(status_code=502, detail=error)
        time.sleep(1.0)
    raise HTTPException(status_code=504, detail="ComfyUI workflow timed out.")


def submit_z_image_workflow(
    client: ComfyUIClient,
    *,
    positive_prompt: str,
    negative_prompt: str,
    aspect_ratio: str = "16:9",
    filename_prefix: str = "newauto_z_image",
    timeout_sec: int = 180,
    seed: int = 8,
    character_descriptor: dict[str, object] | None = None,
) -> tuple[str, list[ComfyImageResult]]:
    workflow = load_z_image_workflow(
        positive_prompt=positive_prompt,
        negative_prompt=negative_prompt,
        aspect_ratio=aspect_ratio,
        filename_prefix=filename_prefix,
        seed=seed,
        character_descriptor=character_descriptor,
    )
    submission = client.submit_workflow(workflow)
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        history = client.get_history(submission.prompt_id)
        results = client.extract_image_results(history, submission.prompt_id)
        if results:
            return submission.prompt_id, results
        error = client.extract_execution_error(history, submission.prompt_id)
        if error:
            raise HTTPException(status_code=502, detail=error)
        time.sleep(1.0)
    raise HTTPException(status_code=504, detail="ComfyUI Z-Image workflow timed out.")
