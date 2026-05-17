from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from .. import db
from ..config import VOICE_SAMPLE_TEXT
from ..services import preflight as preflight_svc
from ..services.operator_summary import build_operator_summary
from ..services.render_report import load_render_report
from ..services import tts as tts_svc
from ..services.visual_relevance import attach_visual_relevance, load_final_scene_review
from ..tts_profiles import build_tts_preset_catalog, canonical_voice_preset, normalize_tts_profile
from ..types import (
    FinalSceneReview,
    PreflightReport,
    ProjectRecord,
    ProjectStatus,
    RenderReport,
    TtsMode,
    TtsPresetCatalogResponse,
    TtsPreviewResponse,
    TtsSeedMode,
    TtsSynthesisMode,
)

router = APIRouter(prefix="/api/projects", tags=["render"])
meta_router = APIRouter(prefix="/api/tts", tags=["tts"])


class TtsProfilePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: TtsMode | None = None
    synthesis_mode: TtsSynthesisMode | None = None
    seed_mode: TtsSeedMode | None = None
    language: str | None = Field(default=None, pattern=r"^(auto|ko|en)$")
    instruct: str | None = Field(default=None, max_length=200)
    speed: float | None = Field(default=None, ge=0.75, le=1.25)
    duration: float | None = Field(default=None, ge=0.0, le=30.0)
    num_step: int | None = Field(default=None, ge=16, le=64)
    guidance_scale: float | None = Field(default=None, ge=1.0, le=5.0)
    denoise: bool | None = None
    postprocess_output: bool | None = None
    seed: int | None = Field(default=None, ge=0, le=2147483647)

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {}
        for key in (
            "mode",
            "synthesis_mode",
            "seed_mode",
            "language",
            "instruct",
            "speed",
            "duration",
            "num_step",
            "guidance_scale",
            "denoise",
            "postprocess_output",
            "seed",
        ):
            value = getattr(self, key)
            if value is not None:
                payload[key] = value
        return payload


class TtsPreviewLockPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    voice_preset: str
    signature: str = Field(min_length=64, max_length=64)
    tts_profile: TtsProfilePayload

    def to_payload(self) -> dict[str, object]:
        return {
            "voice_preset": self.voice_preset,
            "signature": self.signature,
            "tts_profile": self.tts_profile.to_payload(),
        }


class TtsRunPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    voice_preset: str = "auto"
    tts_profile: TtsProfilePayload | None = None
    preview_lock: TtsPreviewLockPayload | None = None


class TtsPreviewPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    voice_preset: str = "auto"
    sample_text: str | None = Field(default=None, max_length=200)
    tts_profile: TtsProfilePayload | None = None


def _require(pid: str) -> ProjectRecord:
    project = db.get_project(pid)
    if project is None:
        raise HTTPException(404, f"project {pid} not found")
    return project


@meta_router.get("/presets")
def get_tts_presets() -> TtsPresetCatalogResponse:
    return build_tts_preset_catalog()


@router.post("/{pid}/tts")
def start_tts(pid: str, payload: TtsRunPayload) -> dict[str, bool]:
    project = _require(pid)
    if not project["sentences"]:
        raise HTTPException(400, "script is empty - save title and script first")
    if project["tts_state"] in {"queued", "running"}:
        raise HTTPException(409, "TTS already running")

    voice_preset, tts_profile = normalize_tts_profile(
        payload.tts_profile.to_payload() if payload.tts_profile is not None else {},
        payload.voice_preset,
        project["compiled_script"] or project["script"],
    )
    try:
        if payload.preview_lock is not None:
            preview_lock = tts_svc.validate_preview_lock(
                payload.preview_lock.to_payload(),
                voice_preset,
                tts_svc.ensure_seed(tts_profile, forced_seed=payload.preview_lock.tts_profile.seed),
            )
            tts_profile = preview_lock["tts_profile"]
        else:
            tts_profile = tts_svc.ensure_seed(tts_profile)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    db.update_project(
        pid,
        voice_preset=voice_preset,
        tts_profile=tts_profile,
        tts_state="queued",
        tts_progress=0,
        tts_error="",
        tts_job_id="",
        tts_started_at="",
        tts_heartbeat_at="",
    )
    return {"ok": True}


@router.post("/{pid}/tts/preview")
def generate_tts_preview(pid: str, payload: TtsPreviewPayload) -> TtsPreviewResponse:
    _require(pid)
    sample_text = (payload.sample_text or "").strip()[:200] or VOICE_SAMPLE_TEXT
    preview_path = db.project_dir(pid) / "tts_preview.wav"
    canonical_preset = canonical_voice_preset(payload.voice_preset)
    try:
        voice_preset, tts_profile, preview_lock, audio = tts_svc.synthesize_preview_with_profile(
            sample_text,
            canonical_preset,
            payload.tts_profile.to_payload() if payload.tts_profile is not None else {},
            owner=f"tts-preview:{pid}",
        )
        tts_svc.save_audio_file(audio, preview_path)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {
        "preview_url": f"/api/projects/{pid}/tts-preview",
        "sample_text": sample_text,
        "voice_preset": voice_preset,
        "tts_profile": tts_profile,
        "preview_lock": preview_lock,
    }


@router.get("/{pid}/tts-preview")
def get_tts_preview(pid: str) -> FileResponse:
    _require(pid)
    target = db.project_dir(pid) / "tts_preview.wav"
    if not target.exists():
        raise HTTPException(404, "TTS preview not found")
    return FileResponse(target, media_type="audio/wav", filename="tts_preview.wav")


@router.post("/{pid}/render")
def start_render(pid: str) -> dict[str, bool]:
    project = _require(pid)
    if project["tts_state"] != "done":
        raise HTTPException(400, "run TTS first")
    if not project["media_order"]:
        raise HTTPException(400, "upload at least one media file")
    if project["media_upload_state"] == "running":
        raise HTTPException(409, "wait for media upload to finish")
    if project["render_state"] in {"queued", "running"}:
        raise HTTPException(409, "render already running")

    db.update_project(
        pid,
        render_state="queued",
        render_progress=0,
        render_phase="queued",
        render_phase_pct=0,
        render_progress_detail="",
        render_speed_x=0.0,
        render_eta_sec=0,
        render_job_id="",
        render_started_at="",
        render_heartbeat_at="",
        render_last_log="",
    )
    return {"ok": True}


@router.get("/{pid}/preflight")
def preflight(pid: str) -> PreflightReport:
    project = _require(pid)
    return preflight_svc.build_preflight_report(project)


@router.get("/{pid}/render-report")
def get_render_report(pid: str) -> RenderReport:
    _require(pid)
    report = load_render_report(pid)
    if report is None:
        raise HTTPException(404, "render report not found")
    return report


@router.get("/{pid}/operator-summary")
def get_operator_summary(pid: str) -> dict[str, object]:
    project = _require(pid)
    return build_operator_summary(project)


@router.get("/{pid}/final-scene-review")
def get_final_scene_review(pid: str) -> FinalSceneReview:
    _require(pid)
    review = load_final_scene_review(pid)
    if review is None:
        raise HTTPException(404, "final scene review not found")
    return review


@router.get("/{pid}/status")
def status(pid: str) -> ProjectStatus:
    project = attach_visual_relevance(_require(pid))
    return {
        "id": project["id"],
        "tts_state": project["tts_state"],
        "tts_progress": project["tts_progress"],
        "tts_error": project["tts_error"],
        "tts_job_id": project["tts_job_id"],
        "tts_started_at": project["tts_started_at"],
        "tts_heartbeat_at": project["tts_heartbeat_at"],
        "body_image_state": project["body_image_state"],
        "body_image_progress": project["body_image_progress"],
        "body_image_phase": project["body_image_phase"],
        "body_image_last_log": project["body_image_last_log"],
        "body_image_started_at": project["body_image_started_at"],
        "body_image_heartbeat_at": project["body_image_heartbeat_at"],
        "body_image_error": project["body_image_error"],
        "source_draft_state": project["source_draft_state"],
        "source_draft_progress": project["source_draft_progress"],
        "source_draft_phase": project["source_draft_phase"],
        "source_draft_last_log": project["source_draft_last_log"],
        "source_draft_started_at": project["source_draft_started_at"],
        "source_draft_heartbeat_at": project["source_draft_heartbeat_at"],
        "source_draft_error": project["source_draft_error"],
        "autopilot_state": project["autopilot_state"],
        "autopilot_progress": project["autopilot_progress"],
        "autopilot_phase": project["autopilot_phase"],
        "autopilot_last_log": project["autopilot_last_log"],
        "autopilot_error": project["autopilot_error"],
        "autopilot_job_id": project["autopilot_job_id"],
        "autopilot_started_at": project["autopilot_started_at"],
        "autopilot_heartbeat_at": project["autopilot_heartbeat_at"],
        "autopilot_last_error_code": project["autopilot_last_error_code"],
        "autopilot_debug_summary": project["autopilot_debug_summary"],
        "autopilot_wait_started_at": project["autopilot_wait_started_at"],
        "autopilot_retry_count": project["autopilot_retry_count"],
        "scene_plan": project["scene_plan"],
        "render_state": project["render_state"],
        "render_progress": project["render_progress"],
        "render_phase": project["render_phase"],
        "render_phase_pct": project["render_phase_pct"],
        "render_progress_detail": project["render_progress_detail"],
        "render_speed_x": project["render_speed_x"],
        "render_eta_sec": project["render_eta_sec"],
        "render_job_id": project["render_job_id"],
        "render_started_at": project["render_started_at"],
        "render_heartbeat_at": project["render_heartbeat_at"],
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
        "visual_relevance_rows": project["visual_relevance_rows"],
        "visual_relevance_summary": project["visual_relevance_summary"],
    }
