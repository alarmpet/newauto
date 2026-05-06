import csv
import re
import shutil
import time
from io import StringIO
from pathlib import Path
from typing import cast

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from .. import db
from ..config import ALLOWED_IMAGE_EXT, ALLOWED_VIDEO_EXT
from ..services.flow_prompting import (
    FlowPromptManifest,
    attach_flow_asset_to_manifest,
    generate_flow_prompt_manifest,
    load_flow_prompt_manifest,
)
from ..services.visual_relevance import sentence_hash
from ..types import BodyImageMapping, MediaKind, ProjectRecord

router = APIRouter(prefix="/api/flow", tags=["flow"])


class FlowPromptPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    aspect_ratio: str = Field(default="9:16", max_length=8)
    mode: str = Field(default="assisted", max_length=40)


class FlowAssetUploadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project: dict[str, object]
    manifest: FlowPromptManifest
    saved_name: str
    kind: MediaKind


class LocalFlowAssetAttachPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paths: list[str] = Field(default_factory=list, max_length=80)
    start_sentence_number: int = Field(default=1, ge=1)


class RenamedFlowAssetAttachPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paths: list[str] = Field(default_factory=list, max_length=120)
    search_dir: str = Field(default="", max_length=500)
    since_minutes: int = Field(default=240, ge=1, le=10080)


class LocalFlowAssetAttachResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project: dict[str, object]
    manifest: FlowPromptManifest
    attached: list[str]
    skipped: list[str]


class UiVisionPrepareResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest: FlowPromptManifest
    directory: str
    csv_path: str
    prompt_paths: list[str]


RENAMED_FLOW_ASSET_RE = re.compile(r"^flow_s(?P<sentence_number>\d{1,3})[_-].+", re.IGNORECASE)


def _require(pid: str) -> ProjectRecord:
    project = db.get_project(pid)
    if project is None:
        raise HTTPException(404, f"project {pid} not found")
    return project


def _infer_media_kind(filename: str) -> MediaKind | None:
    extension = Path(filename).suffix.lower()
    if extension in ALLOWED_IMAGE_EXT:
        return "image"
    if extension in ALLOWED_VIDEO_EXT:
        return "video"
    return None


def _flow_media_name(sentence_idx: int, original_name: str) -> str:
    extension = Path(original_name).suffix.lower()
    return f"flow_sentence_{sentence_idx + 1:03d}{extension}"


def _uivision_dir(pid: str) -> Path:
    path = db.project_dir(pid) / "uivision"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _mapping_for_asset(
    *,
    project: ProjectRecord,
    sentence_idx: int,
    saved_name: str,
    prompt: str,
) -> BodyImageMapping:
    sentence = project["sentences"][sentence_idx] if sentence_idx < len(project["sentences"]) else ""
    return {
        "sentence_idx": sentence_idx,
        "path": saved_name,
        "prompt": prompt,
        "sentence_text": sentence,
        "sentence_hash": sentence_hash(sentence),
        "project_id": project["id"],
        "selected_reason": "flow_assisted_upload",
    }


def _prompt_for_sentence(manifest: FlowPromptManifest, sentence_idx: int) -> str:
    for entry in manifest["entries"]:
        if entry["sentence_idx"] == sentence_idx:
            return entry["prompt"]
    return ""


def _flow_prompt_csv(manifest: FlowPromptManifest) -> str:
    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["sentence_number", "prompt", "negative_prompt", "section", "narration"],
        lineterminator="\n",
    )
    writer.writeheader()
    for entry in sorted(manifest["entries"], key=lambda item: item["sentence_idx"]):
        writer.writerow(
            {
                "sentence_number": entry["sentence_idx"] + 1,
                "prompt": entry["prompt"],
                "negative_prompt": entry["negative_prompt"],
                "section": entry["section"],
                "narration": entry["narration"],
            }
        )
    return output.getvalue()


def _write_uivision_files(pid: str, manifest: FlowPromptManifest) -> tuple[Path, list[Path]]:
    directory = _uivision_dir(pid)
    csv_path = directory / "flow_prompts.csv"
    csv_path.write_text(_flow_prompt_csv(manifest), encoding="utf-8")
    prompt_paths: list[Path] = []
    for entry in sorted(manifest["entries"], key=lambda item: item["sentence_idx"]):
        prompt_path = directory / f"prompt_{entry['sentence_idx'] + 1:03d}.txt"
        prompt_path.write_text(entry["prompt"], encoding="utf-8")
        prompt_paths.append(prompt_path)
    return csv_path, prompt_paths


def _renamed_sentence_idx(filename: str) -> int | None:
    match = RENAMED_FLOW_ASSET_RE.match(Path(filename).name)
    if match is None:
        return None
    return int(match.group("sentence_number")) - 1


def _renamed_asset_candidates(payload: RenamedFlowAssetAttachPayload) -> list[Path]:
    explicit_paths = [Path(raw_path).expanduser() for raw_path in payload.paths]
    if explicit_paths:
        return explicit_paths
    if not payload.search_dir.strip():
        raise HTTPException(400, "paths or search_dir is required.")
    search_dir = Path(payload.search_dir).expanduser()
    if not search_dir.exists() or not search_dir.is_dir():
        raise HTTPException(400, f"search_dir not found: {search_dir}")
    cutoff = time.time() - payload.since_minutes * 60
    candidates: list[Path] = []
    for path in search_dir.iterdir():
        if not path.is_file() or path.name.endswith(".crdownload"):
            continue
        if _renamed_sentence_idx(path.name) is None:
            continue
        if path.suffix.lower() not in ALLOWED_IMAGE_EXT and path.suffix.lower() not in ALLOWED_VIDEO_EXT:
            continue
        if path.stat().st_mtime >= cutoff:
            candidates.append(path)
    candidates.sort(key=lambda item: (_renamed_sentence_idx(item.name) or -1, item.stat().st_mtime))
    return candidates


def _attach_flow_asset(
    *,
    project: ProjectRecord,
    manifest: FlowPromptManifest,
    mappings: list[BodyImageMapping],
    media_order: list[str],
    source_path: Path,
    sentence_idx: int,
    selected_reason: str,
) -> tuple[FlowPromptManifest, list[BodyImageMapping], list[str], str]:
    media_kind = _infer_media_kind(source_path.name)
    if media_kind is None:
        raise HTTPException(400, f"{source_path}: unsupported file type")
    media_dir = db.project_dir(project["id"]) / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    flow_asset_dir = db.project_dir(project["id"]) / "flow_assets"
    flow_asset_dir.mkdir(parents=True, exist_ok=True)
    saved_name = _flow_media_name(sentence_idx, source_path.name)
    target_path = media_dir / saved_name
    shutil.copy2(source_path, target_path)
    shutil.copy2(target_path, flow_asset_dir / saved_name)
    updated_manifest = attach_flow_asset_to_manifest(project, sentence_idx=sentence_idx, asset_path=saved_name)
    prompt = _prompt_for_sentence(updated_manifest, sentence_idx)
    updated_mappings = [mapping for mapping in mappings if mapping["sentence_idx"] != sentence_idx]
    mapping = _mapping_for_asset(
        project=project,
        sentence_idx=sentence_idx,
        saved_name=saved_name,
        prompt=prompt,
    )
    mapping["selected_reason"] = selected_reason
    updated_mappings.append(mapping)
    updated_media_order = [name for name in media_order if name != saved_name]
    updated_media_order.append(saved_name)
    return updated_manifest, updated_mappings, updated_media_order, saved_name


@router.post("/prompts/{pid}")
def create_flow_prompts(pid: str, payload: FlowPromptPayload) -> FlowPromptManifest:
    project = _require(pid)
    return generate_flow_prompt_manifest(project, aspect_ratio=payload.aspect_ratio, mode=payload.mode)


@router.get("/prompts/{pid}")
def get_flow_prompts(pid: str) -> FlowPromptManifest:
    project = _require(pid)
    manifest = load_flow_prompt_manifest(project)
    if manifest["entries"]:
        return manifest
    return generate_flow_prompt_manifest(project)


@router.get("/prompts/{pid}/csv")
def get_flow_prompts_csv(pid: str) -> Response:
    project = _require(pid)
    manifest = generate_flow_prompt_manifest(project)
    return Response(content=_flow_prompt_csv(manifest), media_type="text/csv; charset=utf-8")


@router.get("/prompts/{pid}/sentence/{sentence_number}")
def get_single_flow_prompt_text(pid: str, sentence_number: int) -> PlainTextResponse:
    if sentence_number < 1:
        raise HTTPException(400, "sentence_number must be 1 or greater.")
    project = _require(pid)
    manifest = generate_flow_prompt_manifest(project)
    sentence_idx = sentence_number - 1
    prompt = _prompt_for_sentence(manifest, sentence_idx)
    if not prompt:
        raise HTTPException(404, f"sentence {sentence_number} has no Flow prompt.")
    return PlainTextResponse(prompt)


@router.post("/prompts/{pid}/uivision/prepare")
def prepare_uivision_flow_files(pid: str) -> UiVisionPrepareResponse:
    project = _require(pid)
    manifest = generate_flow_prompt_manifest(project)
    csv_path, prompt_paths = _write_uivision_files(pid, manifest)
    return cast(
        UiVisionPrepareResponse,
        {
            "manifest": manifest,
            "directory": str(csv_path.parent),
            "csv_path": str(csv_path),
            "prompt_paths": [str(path) for path in prompt_paths],
        },
    )


@router.get("/manifest/{pid}")
def get_flow_manifest(pid: str) -> FlowPromptManifest:
    project = _require(pid)
    return load_flow_prompt_manifest(project)


@router.post("/assets/{pid}/attach-local")
def attach_local_flow_assets(pid: str, payload: LocalFlowAssetAttachPayload) -> LocalFlowAssetAttachResponse:
    project = _require(pid)
    if not payload.paths:
        raise HTTPException(400, "No local Flow asset paths were provided.")

    manifest = load_flow_prompt_manifest(project)
    if not manifest["entries"]:
        manifest = generate_flow_prompt_manifest(project)

    mappings = list(project["body_image_mappings"])
    media_order = list(project["media_order"])
    attached: list[str] = []
    skipped: list[str] = []
    start_idx = payload.start_sentence_number - 1

    for offset, raw_path in enumerate(payload.paths):
        sentence_idx = start_idx + offset
        source_path = Path(raw_path).expanduser()
        if sentence_idx < 0 or sentence_idx >= len(project["sentences"]):
            skipped.append(f"{raw_path}: sentence index out of range")
            continue
        if not source_path.exists() or not source_path.is_file():
            skipped.append(f"{raw_path}: file not found")
            continue
        if _infer_media_kind(source_path.name) is None:
            skipped.append(f"{raw_path}: unsupported file type")
            continue

        manifest, mappings, media_order, saved_name = _attach_flow_asset(
            project=project,
            manifest=manifest,
            mappings=mappings,
            media_order=media_order,
            source_path=source_path,
            sentence_idx=sentence_idx,
            selected_reason="flow_assisted_upload",
        )
        attached.append(saved_name)

    mappings.sort(key=lambda item: item["sentence_idx"])
    updated = db.update_project(
        pid,
        visual_source_mode="flow_assisted",
        body_image_mappings=mappings,
        media_order=media_order,
    )
    if updated is None:
        raise HTTPException(404, f"project {pid} not found")
    return cast(
        LocalFlowAssetAttachResponse,
        {
            "project": dict(updated),
            "manifest": manifest,
            "attached": attached,
            "skipped": skipped,
        },
    )


@router.post("/assets/{pid}/attach-renamed")
def attach_renamed_flow_assets(pid: str, payload: RenamedFlowAssetAttachPayload) -> LocalFlowAssetAttachResponse:
    project = _require(pid)
    candidates = _renamed_asset_candidates(payload)
    if not candidates:
        raise HTTPException(400, "No renamed Flow assets were found.")

    manifest = load_flow_prompt_manifest(project)
    if not manifest["entries"]:
        manifest = generate_flow_prompt_manifest(project)

    mappings = list(project["body_image_mappings"])
    media_order = list(project["media_order"])
    attached: list[str] = []
    skipped: list[str] = []
    used_sentence_indexes: set[int] = set()

    for source_path in candidates:
        sentence_idx = _renamed_sentence_idx(source_path.name)
        if sentence_idx is None:
            skipped.append(f"{source_path}: filename does not match flow_sNNN_ pattern")
            continue
        if sentence_idx in used_sentence_indexes:
            skipped.append(f"{source_path}: duplicate file for sentence {sentence_idx + 1}")
            continue
        if sentence_idx < 0 or sentence_idx >= len(project["sentences"]):
            skipped.append(f"{source_path}: sentence index out of range")
            continue
        if not source_path.exists() or not source_path.is_file():
            skipped.append(f"{source_path}: file not found")
            continue
        if _infer_media_kind(source_path.name) is None:
            skipped.append(f"{source_path}: unsupported file type")
            continue

        manifest, mappings, media_order, saved_name = _attach_flow_asset(
            project=project,
            manifest=manifest,
            mappings=mappings,
            media_order=media_order,
            source_path=source_path,
            sentence_idx=sentence_idx,
            selected_reason="flow_uivision_renamed_download",
        )
        attached.append(saved_name)
        used_sentence_indexes.add(sentence_idx)

    mappings.sort(key=lambda item: item["sentence_idx"])
    updated = db.update_project(
        pid,
        visual_source_mode="flow_assisted",
        body_image_mappings=mappings,
        media_order=media_order,
    )
    if updated is None:
        raise HTTPException(404, f"project {pid} not found")
    return cast(
        LocalFlowAssetAttachResponse,
        {
            "project": dict(updated),
            "manifest": manifest,
            "attached": attached,
            "skipped": skipped,
        },
    )


@router.post("/assets/{pid}/{sentence_idx}")
async def upload_flow_asset(
    pid: str,
    sentence_idx: int,
    file: UploadFile = File(...),
    prompt: str = Form(""),
) -> FlowAssetUploadResponse:
    project = _require(pid)
    if sentence_idx < 0 or sentence_idx >= len(project["sentences"]):
        await file.close()
        raise HTTPException(400, f"sentence index {sentence_idx} is out of range.")
    original_name = Path(file.filename or "").name
    media_kind = _infer_media_kind(original_name)
    if media_kind is None:
        await file.close()
        raise HTTPException(400, "Flow asset must be an image or video file.")

    media_dir = db.project_dir(pid) / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    saved_name = _flow_media_name(sentence_idx, original_name)
    target_path = media_dir / saved_name
    temp_path = media_dir / f"{saved_name}.tmp"

    try:
        with temp_path.open("wb") as output_file:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                output_file.write(chunk)
        temp_path.replace(target_path)
    except Exception as exc:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(500, f"failed to save Flow asset: {exc}") from exc
    finally:
        await file.close()

    flow_asset_dir = db.project_dir(pid) / "flow_assets"
    flow_asset_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target_path, flow_asset_dir / saved_name)

    manifest = attach_flow_asset_to_manifest(project, sentence_idx=sentence_idx, asset_path=saved_name)
    manifest_prompt = prompt.strip()
    if not manifest_prompt:
        manifest_prompt = _prompt_for_sentence(manifest, sentence_idx)

    mappings = [mapping for mapping in project["body_image_mappings"] if mapping["sentence_idx"] != sentence_idx]
    mappings.append(
        _mapping_for_asset(
            project=project,
            sentence_idx=sentence_idx,
            saved_name=saved_name,
            prompt=manifest_prompt,
        )
    )
    mappings.sort(key=lambda item: item["sentence_idx"])
    media_order = [name for name in project["media_order"] if name != saved_name]
    media_order.append(saved_name)
    updated = db.update_project(
        pid,
        visual_source_mode="flow_assisted",
        body_image_mappings=mappings,
        media_order=media_order,
    )
    if updated is None:
        raise HTTPException(404, f"project {pid} not found")
    return cast(
        FlowAssetUploadResponse,
        {
            "project": dict(updated),
            "manifest": manifest,
            "saved_name": saved_name,
            "kind": media_kind,
        },
    )
