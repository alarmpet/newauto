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
    }
    mappings = [item for item in project["body_image_mappings"] if item["sentence_idx"] != sentence_idx]
    mappings.append(mapping)
    db.update_project(project["id"], body_image_mappings=sorted(mappings, key=lambda item: item["sentence_idx"]))
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
) -> tuple[str, list[ComfyImageResult]]:
    workflow = load_z_image_workflow(
        positive_prompt=positive_prompt,
        negative_prompt=negative_prompt,
        aspect_ratio=aspect_ratio,
        filename_prefix=filename_prefix,
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
