import logging
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from .. import db
from ..config import ALLOWED_AUDIO_EXT, ALLOWED_IMAGE_EXT, ALLOWED_VIDEO_EXT
from ..config import SCRIPT_LLM_MODEL
from ..services.source_fetch import analyze_source_url
from ..services.scene_plan import build_scene_plan
from ..services.render_plan import build_render_plan
from ..services.render_report import load_render_report
from ..services.visual_relevance import attach_visual_relevance
from ..services.source_research import collect_sources_from_keyword, get_brave_usage_status
from ..services.subtitle import normalize_subtitle_style, shorts_subtitle_style
from ..services.script_compile import compile_script, flatten_regional_sentences
from ..types import (
    AcceptedUploadFile,
    MediaKind,
    MediaUploadResponse,
    ProjectCard,
    ProjectCloneResponse,
    ProjectFeatureSettingsResponse,
    ProjectRecord,
    RenderFormat,
    RenderPlan,
    RenderPlanSegment,
    Region,
    ScenePlan,
    ScenePlanScene,
    SkippedUploadFile,
    SubtitleEffect,
    SubtitlePosition,
    SubtitleStyle,
    SubtitleStyleResponse,
    BgmUploadResponse,
    ContentMode,
    SourceRegenerateMode,
    ThumbnailUploadResponse,
    VisualSourceMode,
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
    cue_split_mode: str | None = None
    max_cue_sec: float | None = Field(default=None, ge=1.0, le=6.0)
    max_lines: int | None = Field(default=None, ge=1, le=3)
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
            "cue_split_mode",
            "max_cue_sec",
            "max_lines",
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
    visual_source_mode: VisualSourceMode | None = None
    style_preset: str | None = Field(default=None, max_length=40)
    hyperframes_overlay_enabled: bool | None = None
    hyperframes_overlay_required: bool | None = None

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
        if self.visual_source_mode is not None:
            patch["visual_source_mode"] = self.visual_source_mode
        if self.style_preset is not None:
            normalized = self.style_preset.strip().lower()
            allowed = {"", "k_webtoon", "simple_diagram", "editorial_symbolic"}
            if normalized not in allowed:
                raise HTTPException(400, f"unsupported style_preset: {self.style_preset}")
            patch["style_preset"] = normalized
        if self.hyperframes_overlay_enabled is not None:
            patch["hyperframes_overlay_enabled"] = self.hyperframes_overlay_enabled
        if self.hyperframes_overlay_required is not None:
            patch["hyperframes_overlay_required"] = self.hyperframes_overlay_required
        return patch


class SceneCardPatchPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    locked: bool | None = None
    subtitle_override: SubtitleStylePayload | None = None
    clear_subtitle_override: bool = False
    motion: str | None = Field(default=None, max_length=80)

    def motion_patch(self) -> str | None:
        if self.motion is None:
            return None
        normalized = self.motion.strip()
        if not normalized:
            return None
        allowed = {
            "none",
            "still_locked",
            "slow_zoom_in",
            "slow_zoom_out",
            "micro_motion_locked",
            "micro_motion_locked_out",
            "pan_left",
            "pan_right",
            "pan_up",
            "pan_down",
            "parallax_light",
            "push_in_fade",
            "documentary_hold",
            "beat_cut",
        }
        if normalized not in allowed:
            raise HTTPException(400, f"unsupported motion: {self.motion}")
        return normalized


def _empty_source_draft_patch() -> dict[str, object]:
    return {
        "source_draft_state": "idle",
        "source_draft_progress": 0,
        "source_draft_error": "",
        "source_draft_input_mode": "",
        "source_draft_query": "",
        "source_draft_sources": [],
        "source_draft_fact_notes": [],
        "source_draft_script": "",
        "source_draft_previous_script": "",
        "source_draft_warnings": [],
        "source_draft_model": "",
        "source_draft_risk_score": 0.0,
        "source_draft_regenerate_mode": "",
        "source_draft_regenerate_note": "",
        "source_draft_job_id": "",
        "source_draft_started_at": "",
        "source_draft_heartbeat_at": "",
        "source_draft_phase": "",
        "source_draft_last_log": "",
        "source_draft_options": {},
    }


def _require(pid: str) -> ProjectRecord:
    project = db.get_project(pid)
    if project is None:
        raise HTTPException(404, f"project {pid} not found")
    return project


def _load_json_list_file(path: Path) -> list[object]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return payload if isinstance(payload, list) else []


def _tts_path_by_idx(project: ProjectRecord) -> dict[int, str]:
    manifest_path = db.project_dir(project["id"]) / "tts" / "tts_run_manifest.json"
    entries = []
    if manifest_path.exists():
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        if isinstance(payload, dict) and isinstance(payload.get("entries"), list):
            entries = payload["entries"]
    tts_dir = db.project_dir(project["id"]) / "tts"
    paths: dict[int, str] = {}
    for item in entries:
        if not isinstance(item, dict):
            continue
        idx = item.get("idx")
        path = item.get("path") or item.get("audio_path") or item.get("filename")
        if isinstance(idx, int) and isinstance(path, str) and path.strip():
            paths[idx] = path
    for path in tts_dir.glob("sentence_*.wav"):
        digits = "".join(char for char in path.stem if char.isdigit())
        if not digits:
            continue
        paths.setdefault(int(digits), path.name)
    return paths


def _flow_status_by_idx(project: ProjectRecord) -> dict[int, str]:
    path = db.project_dir(project["id"]) / "flow_prompts.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    entries = payload.get("entries") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return {}
    statuses: dict[int, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        sentence_idx = entry.get("sentence_idx")
        status = entry.get("status")
        if isinstance(sentence_idx, int) and isinstance(status, str):
            statuses[sentence_idx] = status
    return statuses


def _minimal_scene_plan(project: ProjectRecord) -> ScenePlan:
    scenes: list[ScenePlanScene] = []
    cursor = 0.0
    for sentence_idx, sentence in enumerate(project["sentences"]):
        duration_sec = max(2.0, min(8.0, len(sentence) / 12))
        region: Region = "body"
        if sentence_idx < len(project["regional_sentences"]):
            region = project["regional_sentences"][sentence_idx]["region"]
        media_path = project["media_order"][sentence_idx] if sentence_idx < len(project["media_order"]) else ""
        scenes.append(
            {
                "idx": sentence_idx + 1,
                "sentence_idx": sentence_idx,
                "text": sentence,
                "region": region,
                "duration_sec": duration_sec,
                "visual_intent": sentence,
                "prompt": "",
                "style": "uploaded visual sequence",
                "media_path": media_path,
            }
        )
        cursor += duration_sec
    return {
        "version": 2,
        "format": "landscape",
        "total_duration": cursor,
        "scenes": scenes,
    }


def _ensure_scene_plan(project: ProjectRecord) -> ScenePlan:
    scene_plan = project["scene_plan"]
    if scene_plan and scene_plan["scenes"]:
        return scene_plan
    return _minimal_scene_plan(project)


def _ensure_render_plan(project: ProjectRecord) -> RenderPlan:
    render_plan = project["render_plan"]
    if render_plan and render_plan["segments"]:
        return render_plan
    return build_render_plan(project)


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
    return attach_visual_relevance(_require(pid))


@router.get("/{pid}/scene-plan")
def get_scene_plan(pid: str) -> ScenePlan | None:
    project = _require(pid)
    return project["scene_plan"]


@router.post("/{pid}/scene-plan/build")
def build_project_scene_plan(pid: str, render_format: RenderFormat = Query(default="landscape")) -> ScenePlan:
    project = _require(pid)
    scene_plan = build_scene_plan(project, render_format=render_format)
    updated = db.update_project(pid, scene_plan=scene_plan)
    if updated is None:
        raise HTTPException(404, f"project {pid} not found")
    return scene_plan


@router.get("/{pid}/render-plan")
def get_render_plan(pid: str) -> RenderPlan | None:
    project = _require(pid)
    return project["render_plan"]


@router.post("/{pid}/render-plan/build")
def build_project_render_plan(pid: str) -> RenderPlan:
    project = _require(pid)
    render_plan = build_render_plan(project)
    updated = db.update_project(pid, render_plan=render_plan)
    if updated is None:
        raise HTTPException(404, f"project {pid} not found")
    return render_plan


@router.get("/{pid}/scene-cards")
def get_scene_cards(pid: str) -> list[dict[str, object]]:
    project = _require(pid)
    scene_plan = project["scene_plan"]
    scenes_by_sentence = {
        scene["sentence_idx"]: scene
        for scene in (scene_plan["scenes"] if scene_plan else [])
    }
    render_plan = project["render_plan"]
    render_segments_by_sentence = {
        segment["sentence_idx"]: segment
        for segment in (render_plan["segments"] if render_plan else [])
        if "sentence_idx" in segment
    }
    mappings_by_idx = {mapping["sentence_idx"]: mapping for mapping in project["body_image_mappings"]}
    tts_paths = _tts_path_by_idx(project)
    flow_statuses = _flow_status_by_idx(project)
    cards: list[dict[str, object]] = []
    for sentence_idx, sentence in enumerate(project["sentences"]):
        scene = scenes_by_sentence.get(sentence_idx)
        render_segment = render_segments_by_sentence.get(sentence_idx)
        mapping = mappings_by_idx.get(sentence_idx)
        media_path = ""
        prompt = ""
        duration_sec = 0.0
        region = "body"
        subtitle_override: object = None
        locked = False
        if scene is not None:
            media_path = scene["media_path"]
            prompt = scene["prompt"]
            duration_sec = scene["duration_sec"]
            region = scene["region"]
            subtitle_override = scene.get("subtitle_override")
            locked = bool(scene.get("locked", False))
        if mapping is not None:
            media_path = mapping["path"]
            prompt = mapping["prompt"]
        if not media_path and sentence_idx < len(project["media_order"]):
            media_path = project["media_order"][sentence_idx]
        if duration_sec <= 0:
            duration_sec = max(2.0, min(8.0, len(sentence) / 12))
        if sentence_idx < len(project["regional_sentences"]):
            region = project["regional_sentences"][sentence_idx]["region"]
        motion = render_segment["motion"] if render_segment is not None else ""
        cards.append(
            {
                "idx": sentence_idx,
                "scene_id": f"scene-{sentence_idx + 1:03d}",
                "sentence_idx": sentence_idx,
                "text": sentence,
                "region": region,
                "duration_sec": duration_sec,
                "voice_asset_path": tts_paths.get(sentence_idx, ""),
                "visual_asset_path": media_path,
                "prompt": prompt,
                "subtitle_override": subtitle_override,
                "motion": motion,
                "flow_status": flow_statuses.get(sentence_idx, ""),
                "locked": locked,
                "warnings": [
                    warning
                    for warning in (
                        "voice_missing" if sentence_idx not in tts_paths else "",
                        "visual_missing" if not media_path else "",
                    )
                    if warning
                ],
            }
        )
    return cards


@router.patch("/{pid}/scene-cards/{sentence_idx}")
def patch_scene_card(pid: str, sentence_idx: int, payload: SceneCardPatchPayload) -> dict[str, object]:
    project = _require(pid)
    if sentence_idx < 0 or sentence_idx >= len(project["sentences"]):
        raise HTTPException(404, f"scene card {sentence_idx} not found")
    scene_plan = _ensure_scene_plan(project)
    scenes = [dict(scene) for scene in scene_plan["scenes"]]
    scene = next((item for item in scenes if item["sentence_idx"] == sentence_idx), None)
    if scene is None:
        raise HTTPException(404, f"scene card {sentence_idx} not found")
    if payload.locked is not None:
        scene["locked"] = payload.locked
    if payload.clear_subtitle_override:
        scene["subtitle_override"] = None
    elif payload.subtitle_override is not None:
        base = dict(project["subtitle_style"])
        base.update(payload.subtitle_override.to_patch())
        scene["subtitle_override"] = normalize_subtitle_style(base)
    scene_plan = {
        **scene_plan,
        "scenes": cast(list[ScenePlanScene], scenes),
    }

    motion = payload.motion_patch()
    update_fields: dict[str, object] = {"scene_plan": scene_plan}
    if motion is not None:
        render_plan = _ensure_render_plan(project)
        segments = [dict(segment) for segment in render_plan["segments"]]
        segment = next(
            (item for item in segments if item.get("sentence_idx") == sentence_idx),
            segments[sentence_idx] if sentence_idx < len(segments) else None,
        )
        if segment is None:
            raise HTTPException(404, f"render segment {sentence_idx} not found")
        segment["motion"] = motion
        update_fields["render_plan"] = {
            **render_plan,
            "segments": cast(list[RenderPlanSegment], segments),
        }
    updated = db.update_project(pid, **update_fields)
    if updated is None:
        raise HTTPException(404, f"project {pid} not found")
    cards = get_scene_cards(pid)
    return cards[sentence_idx]


@router.delete("/{pid}")
def delete_project(pid: str) -> dict[str, bool]:
    _require(pid)
    project_dir = db.project_dir(pid)
    if project_dir.exists():
        shutil.rmtree(project_dir, ignore_errors=True)
    db.delete_project(pid)
    return {"ok": True}


def _content_mode_from_form(value: str) -> ContentMode:
    return "bible_longform" if value == "bible_longform" else "standard"


def _source_regenerate_mode(value: str) -> SourceRegenerateMode:
    if value == "hook":
        return "hook"
    if value == "point":
        return "point"
    if value == "story":
        return "story"
    if value == "lesson":
        return "lesson"
    return ""


@router.put("/{pid}/script")
def save_script(
    pid: str,
    title: str = Form(...),
    script: str = Form(...),
    content_mode: str = Form("standard"),
) -> ProjectRecord:
    _require(pid)
    normalized_mode = _content_mode_from_form(content_mode)
    compiled_script, regional_sentences = compile_script(normalized_mode, script)
    sentences = flatten_regional_sentences(regional_sentences)
    (db.project_dir(pid) / "script.txt").write_text(script, encoding="utf-8")
    (db.project_dir(pid) / "compiled_script.txt").write_text(compiled_script, encoding="utf-8")
    project = db.update_project(
        pid,
        title=title,
        script=script,
        content_mode=normalized_mode,
        user_script=script,
        compiled_script=compiled_script,
        regional_sentences=regional_sentences,
        sentences=sentences,
    )
    if project is None:
        raise HTTPException(404, f"project {pid} not found")
    return project


@router.get("/{pid}/source/draft")
def get_source_draft(pid: str) -> ProjectRecord:
    return _require(pid)


@router.get("/_/source/brave/status")
def get_brave_source_status() -> dict[str, int | str]:
    return get_brave_usage_status()


@router.delete("/{pid}/source/draft")
def clear_source_draft(pid: str) -> ProjectRecord:
    _require(pid)
    project = db.update_project(pid, **_empty_source_draft_patch())
    if project is None:
        raise HTTPException(404, f"project {pid} not found")
    return project


@router.post("/{pid}/source/url/analyze")
def analyze_source_draft_from_url(
    pid: str,
    url: str = Form(...),
) -> ProjectRecord:
    _require(pid)
    db.update_project(
        pid,
        source_draft_state="running",
        source_draft_progress=10,
        source_draft_error="",
        source_draft_input_mode="url",
        source_draft_query=url.strip(),
    )
    try:
        extracted = analyze_source_url(url)
    except HTTPException as exc:
        db.update_project(
            pid,
            source_draft_state="error",
            source_draft_progress=0,
            source_draft_error=str(exc.detail),
            source_draft_input_mode="url",
            source_draft_query=url.strip(),
            source_draft_sources=[],
            source_draft_fact_notes=[],
            source_draft_script="",
            source_draft_previous_script="",
            source_draft_warnings=[],
            source_draft_model="",
            source_draft_risk_score=0.0,
        )
        raise
    project = db.update_project(
        pid,
        source_draft_state="done",
        source_draft_progress=100,
        source_draft_error="",
        source_draft_input_mode="url",
        source_draft_query=url.strip(),
        source_draft_sources=[extracted.source],
        source_draft_fact_notes=extracted.fact_notes,
        source_draft_script="",
        source_draft_previous_script="",
        source_draft_warnings=extracted.warnings,
        source_draft_model="",
        source_draft_risk_score=0.0,
    )
    if project is None:
        raise HTTPException(404, f"project {pid} not found")
    return project


@router.post("/{pid}/source/keyword/collect")
def collect_source_draft_from_keyword(
    pid: str,
    keyword: str = Form(...),
) -> ProjectRecord:
    _require(pid)
    db.update_project(
        pid,
        source_draft_state="running",
        source_draft_progress=5,
        source_draft_error="",
        source_draft_input_mode="keyword",
        source_draft_query=keyword.strip(),
    )
    try:
        search_results, usage = collect_sources_from_keyword(keyword)
        sources = []
        fact_notes = []
        skipped = 0
        for result in search_results:
            try:
                extracted = analyze_source_url(result.url)
            except HTTPException:
                skipped += 1
                continue
            sources.append(extracted.source)
            fact_notes.extend(extracted.fact_notes)
            if len(sources) >= 5:
                break
        if not sources:
            raise HTTPException(404, "검색 결과는 있었지만 분석 가능한 본문을 찾지 못했습니다.")
        warnings = [
            f"Brave 무료 검색 사용량: {usage['used']}/{usage['limit']} (이번 달 남은 {usage['remaining']}건)",
        ]
        if usage.get("cache") == "hit":
            warnings.append("같은 키워드 캐시를 재사용해서 Brave 검색 호출을 아꼈습니다.")
        if skipped:
            warnings.append(f"검색 결과 중 {skipped}개는 본문 추출에 실패해 제외했습니다.")
        project = db.update_project(
            pid,
            source_draft_state="done",
            source_draft_progress=100,
            source_draft_error="",
            source_draft_input_mode="keyword",
            source_draft_query=keyword.strip(),
            source_draft_sources=sources,
            source_draft_fact_notes=fact_notes,
            source_draft_script="",
            source_draft_warnings=warnings,
            source_draft_model="",
            source_draft_risk_score=0.0,
        )
        if project is None:
            raise HTTPException(404, f"project {pid} not found")
        return project
    except HTTPException as exc:
        db.update_project(
            pid,
            source_draft_state="error",
            source_draft_progress=0,
            source_draft_error=str(exc.detail),
            source_draft_sources=[],
            source_draft_fact_notes=[],
            source_draft_script="",
            source_draft_previous_script="",
            source_draft_warnings=[],
            source_draft_model="",
            source_draft_risk_score=0.0,
        )
        raise


@router.post("/{pid}/source/script/generate")
def generate_source_script(
    pid: str,
    tone: str = Form("설명형"),
    target_minutes: str = Form("auto"),
    language: str = Form("ko"),
    mode: str = Form(""),
    note: str = Form(""),
    script_structure: str = Form("standard"),
) -> ProjectRecord:
    project = _require(pid)
    if project["source_draft_state"] == "running":
        raise HTTPException(409, "이미 다른 source draft 생성 작업이 진행 중입니다.")
    normalized_mode = _source_regenerate_mode(mode)
    normalized_note = note.strip()[:200]
    if target_minutes.strip().lower() in {"", "auto"}:
        normalized_target_minutes: int | str = "auto"
    else:
        try:
            normalized_target_minutes = max(1, min(int(target_minutes), 15))
        except ValueError as exc:
            raise HTTPException(400, "invalid target_minutes") from exc
    normalized_tone = tone.strip() or "설명형"
    normalized_language = language.strip() or "ko"
    options = {
        "tone": normalized_tone,
        "target_minutes": normalized_target_minutes,
        "language": normalized_language,
        "script_structure": "hpsl" if script_structure.strip().lower() == "hpsl" else "standard",
    }
    updated = db.update_project(
        pid,
        source_draft_state="queued",
        source_draft_progress=0,
        source_draft_error="",
        source_draft_model=SCRIPT_LLM_MODEL,
        source_draft_regenerate_mode=normalized_mode,
        source_draft_regenerate_note=normalized_note,
        source_draft_job_id="",
        source_draft_started_at="",
        source_draft_heartbeat_at="",
        source_draft_phase="queued",
        source_draft_last_log="Queued source draft generation.",
        source_draft_options=options,
    )
    if updated is None:
        raise HTTPException(404, f"project {pid} not found")
    return updated


@router.post("/{pid}/source/script/apply")
def apply_source_script(pid: str) -> ProjectRecord:
    project = _require(pid)
    draft_script = project["source_draft_script"].strip()
    if not draft_script:
        raise HTTPException(400, "적용할 대본 초안이 없습니다.")
    compiled_script, regional_sentences = compile_script("standard", draft_script)
    sentences = flatten_regional_sentences(regional_sentences)
    (db.project_dir(pid) / "script.txt").write_text(draft_script, encoding="utf-8")
    (db.project_dir(pid) / "compiled_script.txt").write_text(compiled_script, encoding="utf-8")
    subtitle_style = project["subtitle_style"]
    if "shorts" in project["render_formats"]:
        subtitle_style = shorts_subtitle_style(subtitle_style)
    updated = db.update_project(
        pid,
        script=draft_script,
        user_script=draft_script,
        compiled_script=compiled_script,
        regional_sentences=regional_sentences,
        sentences=sentences,
        content_mode="standard",
        subtitle_style=subtitle_style,
    )
    if updated is None:
        raise HTTPException(404, f"project {pid} not found")
    return updated


@router.post("/{pid}/source/script/restore-previous")
def restore_previous_source_script(pid: str) -> ProjectRecord:
    project = _require(pid)
    previous_script = project["source_draft_previous_script"].strip()
    if not previous_script:
        raise HTTPException(400, "복원할 이전 초안이 없습니다.")
    current_script = project["source_draft_script"]
    updated = db.update_project(
        pid,
        source_draft_script=previous_script,
        source_draft_previous_script=current_script,
    )
    if updated is None:
        raise HTTPException(404, f"project {pid} not found")
    return updated


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
    project = _require(pid)
    patch = payload.to_patch()
    style_preset = patch.pop("style_preset", None)
    hyperframes_overlay_enabled = patch.pop("hyperframes_overlay_enabled", None)
    hyperframes_overlay_required = patch.pop("hyperframes_overlay_required", None)
    update_fields = dict(patch)
    if (
        isinstance(style_preset, str)
        or isinstance(hyperframes_overlay_enabled, bool)
        or isinstance(hyperframes_overlay_required, bool)
    ):
        body_image_options = dict(project["body_image_options"])
        if style_preset:
            body_image_options["style_preset"] = style_preset
        elif isinstance(style_preset, str):
            body_image_options.pop("style_preset", None)
        if isinstance(hyperframes_overlay_enabled, bool):
            body_image_options["hyperframes_overlay_enabled"] = hyperframes_overlay_enabled
            if not hyperframes_overlay_enabled:
                body_image_options["hyperframes_overlay_required"] = False
        if isinstance(hyperframes_overlay_required, bool):
            body_image_options["hyperframes_overlay_required"] = hyperframes_overlay_required
        update_fields["body_image_options"] = body_image_options
    updated_project = db.update_project(pid, **update_fields)
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
        update_fields["content_mode"] = project["content_mode"]
        update_fields["visual_source_mode"] = project["visual_source_mode"]
        update_fields["user_script"] = project["user_script"]
        update_fields["compiled_script"] = project["compiled_script"]
        update_fields["regional_sentences"] = project["regional_sentences"]
        update_fields["bible_query"] = project["bible_query"]
        update_fields["selected_verses"] = project["selected_verses"]
        update_fields["bible_background_file"] = project["bible_background_file"]
        update_fields["body_image_state"] = project["body_image_state"]
        update_fields["body_image_progress"] = project["body_image_progress"]
        update_fields["body_image_error"] = project["body_image_error"]
        update_fields["body_image_mappings"] = project["body_image_mappings"]
        update_fields["scene_plan"] = project["scene_plan"] or {}
        update_fields["render_plan"] = project["render_plan"] or {}
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


def _existing_auto_output(pid: str) -> Path:
    project_dir = db.project_dir(pid)
    report = load_render_report(pid)
    if report is not None:
        for output in report.get("outputs", []):
            if not isinstance(output, dict) or output.get("exists") is not True:
                continue
            raw_path = output.get("path")
            if isinstance(raw_path, str) and raw_path.strip():
                target = Path(raw_path)
                if target.exists():
                    return target
    for name in ("output_shorts.mp4", "output.mp4"):
        target = project_dir / name
        if target.exists():
            return target
    return project_dir / "output.mp4"


@router.get("/{pid}/output")
def get_output(pid: str, format: str = Query(default="auto")) -> FileResponse:
    normalized_format = format.strip().lower()
    if normalized_format == "auto":
        target = _existing_auto_output(pid)
    elif normalized_format in {"shorts", "landscape"}:
        target = db.project_dir(pid) / ("output_shorts.mp4" if normalized_format == "shorts" else "output.mp4")
    else:
        raise HTTPException(422, "format must be auto, landscape, or shorts")
    if not target.exists():
        raise HTTPException(404, "render not complete")
    return FileResponse(target, media_type="video/mp4")
