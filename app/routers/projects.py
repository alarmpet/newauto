import logging
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from .. import db
from ..config import ALLOWED_AUDIO_EXT, ALLOWED_IMAGE_EXT, ALLOWED_VIDEO_EXT
from ..services.subtitle import normalize_subtitle_style
from ..text import split_sentences
from ..types import (
    AcceptedUploadFile,
    MediaKind,
    MediaUploadResponse,
    ProjectCard,
    ProjectCloneResponse,
    ProjectFeatureSettingsResponse,
    ProjectRecord,
    RenderFormat,
    SkippedUploadFile,
    SubtitleEffect,
    SubtitlePosition,
    SubtitleStyle,
    SubtitleStyleResponse,
    BgmUploadResponse,
    ThumbnailUploadResponse,
)

router = APIRouter(prefix="/api/projects", tags=["projects"])
logger = logging.getLogger(__name__)
THUMBNAIL_MAX_BYTES = 10 * 1024 * 1024
BGM_MAX_BYTES = 50 * 1024 * 1024


@dataclass(frozen=True)
class PreparedUpload:
    file: UploadFile
    original_name: str
    sanitized_name: str
    kind: MediaKind


class SubtitleStylePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    font_family: str | None = Field(default=None, min_length=1, max_length=80)
    font_size: int | None = Field(default=None, ge=24, le=96)
    primary_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    outline_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    background_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    background_opacity: float | None = Field(default=None, ge=0.0, le=1.0)
    outline_width: int | None = Field(default=None, ge=0, le=8)
    shadow: int | None = Field(default=None, ge=0, le=8)
    position: SubtitlePosition | None = None
    margin_h: int | None = Field(default=None, ge=0, le=400)
    margin_v: int | None = Field(default=None, ge=0, le=240)
    max_line_chars: int | None = Field(default=None, ge=16, le=40)
    min_display_sec: float | None = Field(default=None, ge=0.5, le=3.0)
    effect: SubtitleEffect | None = None

    def to_patch(self) -> dict[str, object]:
        patch: dict[str, object] = {}
        for key in (
            "font_family",
            "font_size",
            "primary_color",
            "outline_color",
            "background_color",
            "background_opacity",
            "outline_width",
            "shadow",
            "position",
            "margin_h",
            "margin_v",
            "max_line_chars",
            "min_display_sec",
            "effect",
        ):
            value = getattr(self, key)
            if value is not None:
                patch[key] = value
        return patch


class ProjectFeaturePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kenburns_enabled: bool | None = None
    bgm_volume_db: int | None = Field(default=None, ge=-40, le=6)
    bgm_ducking_enabled: bool | None = None
    render_formats: list[RenderFormat] | None = None

    def to_patch(self) -> dict[str, object]:
        patch: dict[str, object] = {}
        if self.kenburns_enabled is not None:
            patch["kenburns_enabled"] = self.kenburns_enabled
        if self.bgm_volume_db is not None:
            patch["bgm_volume_db"] = self.bgm_volume_db
        if self.bgm_ducking_enabled is not None:
            patch["bgm_ducking_enabled"] = self.bgm_ducking_enabled
        if self.render_formats is not None:
            patch["render_formats"] = self.render_formats or ["landscape"]
        return patch


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


def _sanitize_filename(filename: str) -> str:
    clean_name = re.sub(r"[^\w\-.]+", "_", filename).strip("._")
    suffix = Path(filename).suffix.lower()
    if clean_name:
        return clean_name
    return f"media{suffix}" if suffix else "media"


def _unique_media_path(media_dir: Path, filename: str) -> Path:
    base_name = _sanitize_filename(filename)
    target = media_dir / base_name
    counter = 0
    while target.exists():
        counter += 1
        target = media_dir / f"{target.stem}_{counter}{target.suffix}"
    return target


def _thumbnail_dir(pid: str) -> Path:
    return db.project_dir(pid) / "thumbnail"


def _bgm_dir(pid: str) -> Path:
    return db.project_dir(pid) / "bgm"


def _clear_thumbnail_dir(thumbnail_dir: Path, keep_path: Path | None = None) -> None:
    if not thumbnail_dir.exists():
        return
    for path in thumbnail_dir.iterdir():
        if keep_path is not None and path == keep_path:
            continue
        if path.is_file():
            path.unlink()


def _thumbnail_path(project: ProjectRecord) -> Path:
    return _thumbnail_dir(project["id"]) / project["thumbnail_file"]


def _clear_dir(target_dir: Path, keep_path: Path | None = None) -> None:
    if not target_dir.exists():
        return
    for path in target_dir.iterdir():
        if keep_path is not None and path == keep_path:
            continue
        if path.is_file():
            path.unlink()


@router.get("")
def list_projects() -> list[ProjectCard]:
    return db.list_projects()


@router.post("")
def create_project(title: str = Form("")) -> ProjectRecord:
    return db.create_project(title=title)


@router.get("/{pid}")
def get_project(pid: str) -> ProjectRecord:
    return _require(pid)


@router.delete("/{pid}")
def delete_project(pid: str) -> dict[str, bool]:
    _require(pid)
    project_dir = db.project_dir(pid)
    if project_dir.exists():
        shutil.rmtree(project_dir, ignore_errors=True)
    db.delete_project(pid)
    return {"ok": True}


@router.put("/{pid}/script")
def save_script(pid: str, title: str = Form(...), script: str = Form(...)) -> ProjectRecord:
    _require(pid)
    sentences = split_sentences(script)
    (db.project_dir(pid) / "script.txt").write_text(script, encoding="utf-8")
    project = db.update_project(pid, title=title, script=script, sentences=sentences)
    if project is None:
        raise HTTPException(404, f"project {pid} not found")
    return project


@router.post("/{pid}/media")
async def upload_media(pid: str, files: list[UploadFile] = File(...)) -> MediaUploadResponse:
    project = _require(pid)
    media_dir = db.project_dir(pid) / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    prepared_uploads: list[PreparedUpload] = []
    skipped_files: list[SkippedUploadFile] = []
    for upload_file in files:
        original_name = Path(upload_file.filename or "").name or "media"
        media_kind = _infer_media_kind(original_name)
        if media_kind is None:
            skipped_files.append(
                {
                    "name": original_name,
                    "reason": "unsupported file type",
                }
            )
            await upload_file.close()
            continue
        prepared_uploads.append(
            PreparedUpload(
                file=upload_file,
                original_name=original_name,
                sanitized_name=_sanitize_filename(original_name),
                kind=media_kind,
            )
        )

    total_files = len(prepared_uploads)
    if total_files == 0:
        db.update_project(
            pid,
            media_upload_state="error",
            media_upload_progress=0,
            media_upload_completed=0,
            media_upload_total=0,
            media_upload_error="no supported media files selected",
        )
        raise HTTPException(400, "no supported media files selected")

    logger.info(
        "starting media upload pid=%s valid=%s skipped=%s",
        pid,
        total_files,
        len(skipped_files),
    )
    db.update_project(
        pid,
        media_upload_state="running",
        media_upload_progress=0,
        media_upload_completed=0,
        media_upload_total=total_files,
        media_upload_error="",
    )

    media_order = list(project["media_order"])
    accepted_files: list[AcceptedUploadFile] = []

    try:
        for index, prepared_upload in enumerate(prepared_uploads, start=1):
            target_path = _unique_media_path(media_dir, prepared_upload.sanitized_name)
            with target_path.open("wb") as output_file:
                shutil.copyfileobj(prepared_upload.file.file, output_file, length=1024 * 1024)

            media_order.append(target_path.name)
            accepted_files.append(
                {
                    "original_name": prepared_upload.original_name,
                    "saved_name": target_path.name,
                    "kind": prepared_upload.kind,
                }
            )
            db.update_project(
                pid,
                media_upload_progress=int(index / total_files * 100),
                media_upload_completed=index,
                media_upload_total=total_files,
            )
            await prepared_upload.file.close()

        updated_project = db.update_project(
            pid,
            media_order=media_order,
            media_upload_state="done",
            media_upload_progress=100,
            media_upload_completed=total_files,
            media_upload_total=total_files,
            media_upload_error="",
        )
        if updated_project is None:
            raise RuntimeError(f"project {pid} disappeared during media upload")
        logger.info(
            "completed media upload pid=%s saved=%s skipped=%s",
            pid,
            len(accepted_files),
            len(skipped_files),
        )
        return {
            "project": updated_project,
            "accepted_files": accepted_files,
            "skipped_files": skipped_files,
        }
    except Exception as exc:
        logger.exception("media upload failed pid=%s", pid)
        db.update_project(
            pid,
            media_upload_state="error",
            media_upload_error=str(exc),
        )
        raise HTTPException(500, f"media upload failed: {exc}") from exc


@router.post("/{pid}/thumbnail")
async def upload_thumbnail(pid: str, file: UploadFile = File(...)) -> ThumbnailUploadResponse:
    _require(pid)
    original_name = Path(file.filename or "").name
    extension = Path(original_name).suffix.lower()
    if extension not in ALLOWED_IMAGE_EXT:
        await file.close()
        raise HTTPException(400, "thumbnail must be an image file")

    thumbnail_dir = _thumbnail_dir(pid)
    thumbnail_dir.mkdir(parents=True, exist_ok=True)
    target_name = f"thumbnail{extension}"
    target_path = thumbnail_dir / target_name
    temp_path = thumbnail_dir / f"{target_name}.tmp"
    total_bytes = 0

    try:
        try:
            with temp_path.open("wb") as output_file:
                while True:
                    chunk = await file.read(1024 * 1024)
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    if total_bytes > THUMBNAIL_MAX_BYTES:
                        raise HTTPException(400, "thumbnail file is too large")
                    output_file.write(chunk)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise
    finally:
        await file.close()

    _clear_thumbnail_dir(thumbnail_dir, keep_path=temp_path)
    temp_path.replace(target_path)
    project = db.update_project(pid, thumbnail_file=target_name)
    if project is None:
        raise HTTPException(404, f"project {pid} not found")
    return {
        "project": project,
        "thumbnail_url": f"/api/projects/{pid}/thumbnail",
    }


@router.get("/{pid}/thumbnail")
def get_thumbnail(pid: str) -> FileResponse:
    project = _require(pid)
    if not project["thumbnail_file"]:
        raise HTTPException(404, "thumbnail not found")
    target = _thumbnail_path(project)
    if not target.exists():
        raise HTTPException(404, "thumbnail not found")
    return FileResponse(target)


@router.delete("/{pid}/thumbnail")
def delete_thumbnail(pid: str) -> ProjectRecord:
    _require(pid)
    _clear_thumbnail_dir(_thumbnail_dir(pid))
    project = db.update_project(pid, thumbnail_file="")
    if project is None:
        raise HTTPException(404, f"project {pid} not found")
    return project


@router.get("/{pid}/subtitle-style")
def get_subtitle_style(pid: str) -> SubtitleStyle:
    project = _require(pid)
    return project["subtitle_style"]


@router.put("/{pid}/subtitle-style")
def save_subtitle_style(pid: str, payload: SubtitleStylePayload) -> SubtitleStyleResponse:
    project = _require(pid)
    style_input: dict[str, object] = dict(project["subtitle_style"])
    style_input.update(payload.to_patch())
    style = normalize_subtitle_style(style_input)
    updated_project = db.update_project(pid, subtitle_style=style)
    if updated_project is None:
        raise HTTPException(404, f"project {pid} not found")
    return {
        "project": updated_project,
        "effective_style": style,
    }


@router.put("/{pid}/features")
def save_project_features(pid: str, payload: ProjectFeaturePayload) -> ProjectFeatureSettingsResponse:
    _require(pid)
    updated_project = db.update_project(pid, **payload.to_patch())
    if updated_project is None:
        raise HTTPException(404, f"project {pid} not found")
    return {
        "project": updated_project,
    }


@router.post("/{pid}/bgm")
async def upload_bgm(pid: str, file: UploadFile = File(...)) -> BgmUploadResponse:
    _require(pid)
    original_name = Path(file.filename or "").name
    extension = Path(original_name).suffix.lower()
    if extension not in ALLOWED_AUDIO_EXT:
        await file.close()
        raise HTTPException(400, "bgm must be an audio file")

    bgm_dir = _bgm_dir(pid)
    bgm_dir.mkdir(parents=True, exist_ok=True)
    target_name = f"bgm{extension}"
    target_path = bgm_dir / target_name
    temp_path = bgm_dir / f"{target_name}.tmp"
    total_bytes = 0

    try:
        try:
            with temp_path.open("wb") as output_file:
                while True:
                    chunk = await file.read(1024 * 1024)
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    if total_bytes > BGM_MAX_BYTES:
                        raise HTTPException(400, "bgm file is too large")
                    output_file.write(chunk)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise
    finally:
        await file.close()

    _clear_dir(bgm_dir, keep_path=temp_path)
    temp_path.replace(target_path)
    project = db.update_project(pid, bgm_file=target_name)
    if project is None:
        raise HTTPException(404, f"project {pid} not found")
    return {
        "project": project,
        "bgm_url": f"/api/projects/{pid}/bgm",
    }


@router.get("/{pid}/bgm")
def get_bgm(pid: str) -> FileResponse:
    project = _require(pid)
    if not project["bgm_file"]:
        raise HTTPException(404, "bgm not found")
    target = _bgm_dir(pid) / project["bgm_file"]
    if not target.exists():
        raise HTTPException(404, "bgm not found")
    return FileResponse(target)


@router.delete("/{pid}/bgm")
def delete_bgm(pid: str) -> ProjectRecord:
    _require(pid)
    _clear_dir(_bgm_dir(pid))
    project = db.update_project(pid, bgm_file="")
    if project is None:
        raise HTTPException(404, f"project {pid} not found")
    return project


@router.post("/{pid}/clone")
def clone_project(
    pid: str,
    include_script: bool = Query(default=True),
    include_media: bool = Query(default=False),
    include_thumbnail: bool = Query(default=False),
    include_bgm: bool = Query(default=False),
) -> ProjectCloneResponse:
    project = _require(pid)
    cloned = db.create_project(title=f"{project['title']} Copy".strip())
    update_fields: dict[str, object] = {
        "voice_preset": project["voice_preset"],
        "tts_profile": project["tts_profile"],
        "subtitle_style": project["subtitle_style"],
        "kenburns_enabled": project["kenburns_enabled"],
        "bgm_volume_db": project["bgm_volume_db"],
        "bgm_ducking_enabled": project["bgm_ducking_enabled"],
        "render_formats": project["render_formats"],
        "youtube_schedule_at": project["youtube_schedule_at"],
    }
    if include_script:
        update_fields["script"] = project["script"]
        update_fields["sentences"] = project["sentences"]
    cloned_project = db.update_project(cloned["id"], **update_fields)
    if cloned_project is None:
        raise HTTPException(500, "failed to clone project settings")

    source_dir = db.project_dir(pid)
    target_dir = db.project_dir(cloned["id"])
    if include_media:
        media_dir = source_dir / "media"
        target_media_dir = target_dir / "media"
        target_media_dir.mkdir(parents=True, exist_ok=True)
        for name in project["media_order"]:
            source_path = media_dir / name
            if source_path.exists():
                shutil.copy2(source_path, target_media_dir / name)
        cloned_project = db.update_project(cloned["id"], media_order=project["media_order"]) or cloned_project
    if include_thumbnail and project["thumbnail_file"]:
        source_thumb = _thumbnail_dir(pid) / project["thumbnail_file"]
        if source_thumb.exists():
            target_thumb_dir = _thumbnail_dir(cloned["id"])
            target_thumb_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_thumb, target_thumb_dir / project["thumbnail_file"])
            cloned_project = db.update_project(cloned["id"], thumbnail_file=project["thumbnail_file"]) or cloned_project
    if include_bgm and project["bgm_file"]:
        source_bgm = _bgm_dir(pid) / project["bgm_file"]
        if source_bgm.exists():
            target_bgm_dir = _bgm_dir(cloned["id"])
            target_bgm_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_bgm, target_bgm_dir / project["bgm_file"])
            cloned_project = db.update_project(cloned["id"], bgm_file=project["bgm_file"]) or cloned_project
    return {
        "project": cloned_project,
        "source_project_id": pid,
    }


@router.put("/{pid}/media/order")
def reorder_media(pid: str, order: list[str]) -> ProjectRecord:
    project = _require(pid)
    media_dir = db.project_dir(pid) / "media"
    existing = {path.name for path in media_dir.iterdir()} if media_dir.exists() else set()
    cleaned_order: list[str] = []
    seen: set[str] = set()

    for name in order:
        if name in existing and name not in seen:
            cleaned_order.append(name)
            seen.add(name)

    for name in project["media_order"]:
        if name in existing and name not in seen:
            cleaned_order.append(name)
            seen.add(name)

    for name in sorted(existing):
        if name not in seen:
            cleaned_order.append(name)
            seen.add(name)

    updated_project = db.update_project(pid, media_order=cleaned_order)
    if updated_project is None:
        raise HTTPException(404, f"project {pid} not found")
    return updated_project


@router.delete("/{pid}/media/{name}")
def delete_media(pid: str, name: str) -> ProjectRecord:
    project = _require(pid)
    target = db.project_dir(pid) / "media" / name
    if target.exists():
        target.unlink()
    media_order = [media_name for media_name in project["media_order"] if media_name != name]
    updated_project = db.update_project(pid, media_order=media_order)
    if updated_project is None:
        raise HTTPException(404, f"project {pid} not found")
    return updated_project


@router.get("/{pid}/media/{name}")
def get_media(pid: str, name: str) -> FileResponse:
    target = db.project_dir(pid) / "media" / name
    if not target.exists():
        raise HTTPException(404, "media not found")
    return FileResponse(target)


@router.get("/{pid}/tts/{name}")
def get_tts(pid: str, name: str) -> FileResponse:
    target = db.project_dir(pid) / "tts" / name
    if not target.exists():
        raise HTTPException(404, "audio not found")
    return FileResponse(target)


@router.get("/{pid}/output")
def get_output(pid: str, format: RenderFormat = Query(default="landscape")) -> FileResponse:
    target = db.project_dir(pid) / ("output_shorts.mp4" if format == "shorts" else "output.mp4")
    if not target.exists():
        raise HTTPException(404, "render not complete")
    return FileResponse(target, media_type="video/mp4")
