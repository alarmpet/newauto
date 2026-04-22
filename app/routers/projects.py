import logging
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from .. import db
from ..config import ALLOWED_IMAGE_EXT, ALLOWED_VIDEO_EXT
from ..text import split_sentences
from ..types import (
    AcceptedUploadFile,
    MediaKind,
    MediaUploadResponse,
    ProjectCard,
    ProjectRecord,
    SkippedUploadFile,
)

router = APIRouter(prefix="/api/projects", tags=["projects"])
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PreparedUpload:
    file: UploadFile
    original_name: str
    sanitized_name: str
    kind: MediaKind
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
def get_output(pid: str) -> FileResponse:
    target = db.project_dir(pid) / "output.mp4"
    if not target.exists():
        raise HTTPException(404, "render not complete")
    return FileResponse(target, media_type="video/mp4")
