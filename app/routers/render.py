from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .. import db
from ..services import preflight as preflight_svc
from ..services import render as render_svc
from ..services import tts as tts_svc
from ..tts_profiles import normalize_tts_profile
from ..types import PreflightReport, ProjectRecord, ProjectStatus, TtsMode

router = APIRouter(prefix="/api/projects", tags=["render"])


class TtsProfilePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: TtsMode | None = None
    language: str | None = Field(default=None, pattern=r"^(auto|ko|en)$")
    instruct: str | None = Field(default=None, max_length=200)
    speed: float | None = Field(default=None, ge=0.75, le=1.25)
    duration: float | None = Field(default=None, ge=0.0, le=30.0)
    num_step: int | None = Field(default=None, ge=16, le=64)
    guidance_scale: float | None = Field(default=None, ge=1.0, le=5.0)
    denoise: bool | None = None
    postprocess_output: bool | None = None

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {}
        for key in (
            "mode",
            "language",
            "instruct",
            "speed",
            "duration",
            "num_step",
            "guidance_scale",
            "denoise",
            "postprocess_output",
        ):
            value = getattr(self, key)
            if value is not None:
                payload[key] = value
        return payload


class TtsRunPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    voice_preset: str = "auto"
    tts_profile: TtsProfilePayload | None = None


def _require(pid: str) -> ProjectRecord:
    project = db.get_project(pid)
    if project is None:
        raise HTTPException(404, f"project {pid} not found")
    return project


@router.post("/{pid}/tts")
def start_tts(pid: str, bg: BackgroundTasks, payload: TtsRunPayload) -> dict[str, bool]:
    project = _require(pid)
    if not project["sentences"]:
        raise HTTPException(400, "script is empty - save title and script first")
    if project["tts_state"] == "running":
        raise HTTPException(409, "TTS already running")

    voice_preset, tts_profile = normalize_tts_profile(
        payload.tts_profile.to_payload() if payload.tts_profile is not None else {},
        payload.voice_preset,
        project["script"],
    )
    db.update_project(
        pid,
        voice_preset=voice_preset,
        tts_profile=tts_profile,
        tts_state="running",
        tts_progress=0,
    )
    bg.add_task(tts_svc.run_tts_job, pid)
    return {"ok": True}


@router.post("/{pid}/render")
def start_render(pid: str, bg: BackgroundTasks) -> dict[str, bool]:
    project = _require(pid)
    if project["tts_state"] != "done":
        raise HTTPException(400, "run TTS first")
    if not project["media_order"]:
        raise HTTPException(400, "upload at least one media file")
    if project["media_upload_state"] == "running":
        raise HTTPException(409, "wait for media upload to finish")
    if project["render_state"] == "running":
        raise HTTPException(409, "render already running")

    db.update_project(
        pid,
        render_state="running",
        render_progress=0,
        render_phase="queued",
        render_last_log="",
    )
    bg.add_task(render_svc.run_render_job, pid)
    return {"ok": True}


@router.get("/{pid}/preflight")
def preflight(pid: str) -> PreflightReport:
    project = _require(pid)
    return preflight_svc.build_preflight_report(project)


@router.get("/{pid}/status")
def status(pid: str) -> ProjectStatus:
    project = _require(pid)
    return {
        "id": project["id"],
        "tts_state": project["tts_state"],
        "tts_progress": project["tts_progress"],
        "render_state": project["render_state"],
        "render_progress": project["render_progress"],
        "render_phase": project["render_phase"],
        "render_last_log": project["render_last_log"],
        "upload_state": project["upload_state"],
        "upload_progress": project["upload_progress"],
        "media_upload_state": project["media_upload_state"],
        "media_upload_progress": project["media_upload_progress"],
        "media_upload_completed": project["media_upload_completed"],
        "media_upload_total": project["media_upload_total"],
        "media_upload_error": project["media_upload_error"],
        "thumbnail_file": project["thumbnail_file"],
        "subtitle_style": project["subtitle_style"],
        "kenburns_enabled": project["kenburns_enabled"],
        "bgm_file": project["bgm_file"],
        "bgm_volume_db": project["bgm_volume_db"],
        "bgm_ducking_enabled": project["bgm_ducking_enabled"],
        "render_formats": project["render_formats"],
        "youtube_schedule_at": project["youtube_schedule_at"],
        "youtube_id": project["youtube_id"],
    }
