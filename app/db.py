import json
import os
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import cast

from .config import DB_PATH, PROJECTS_DIR
from .services.subtitle import normalize_subtitle_style
from .tts_profiles import normalize_tts_profile
from .types import (
    AutopilotState,
    BodyImageMapping,
    ContentMode,
    MediaKind,
    ProjectCard,
    ProjectRecord,
    Region,
    RegionalSentence,
    RenderFormat,
    RenderPlan,
    RenderPlanSegment,
    RenderPlanSegmentMedia,
    ScenePlan,
    ScenePlanScene,
    SelectedVerse,
    SourceDraftFactNote,
    SourceDraftInputMode,
    SourceRegenerateMode,
    SourceDraftSource,
    TaskState,
    VisualSourceMode,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id           TEXT PRIMARY KEY,
    title        TEXT NOT NULL DEFAULT '',
    script       TEXT NOT NULL DEFAULT '',
    content_mode TEXT NOT NULL DEFAULT 'standard',
    visual_source_mode TEXT NOT NULL DEFAULT 'upload_only',
    user_script TEXT NOT NULL DEFAULT '',
    compiled_script TEXT NOT NULL DEFAULT '',
    regional_sentences TEXT NOT NULL DEFAULT '[]',
    bible_query TEXT NOT NULL DEFAULT '',
    selected_verses TEXT NOT NULL DEFAULT '[]',
    bible_background_file TEXT NOT NULL DEFAULT '',
    body_image_state TEXT NOT NULL DEFAULT 'idle',
    body_image_progress INTEGER NOT NULL DEFAULT 0,
    body_image_error TEXT NOT NULL DEFAULT '',
    body_image_mappings TEXT NOT NULL DEFAULT '[]',
    body_image_job_id TEXT NOT NULL DEFAULT '',
    body_image_started_at TEXT NOT NULL DEFAULT '',
    body_image_heartbeat_at TEXT NOT NULL DEFAULT '',
    body_image_phase TEXT NOT NULL DEFAULT '',
    body_image_last_log TEXT NOT NULL DEFAULT '',
    body_image_options TEXT NOT NULL DEFAULT '{}',
    source_draft_state TEXT NOT NULL DEFAULT 'idle',
    source_draft_progress INTEGER NOT NULL DEFAULT 0,
    source_draft_error TEXT NOT NULL DEFAULT '',
    source_draft_input_mode TEXT NOT NULL DEFAULT '',
    source_draft_query TEXT NOT NULL DEFAULT '',
    source_draft_sources TEXT NOT NULL DEFAULT '[]',
    source_draft_fact_notes TEXT NOT NULL DEFAULT '[]',
    source_draft_script TEXT NOT NULL DEFAULT '',
    source_draft_previous_script TEXT NOT NULL DEFAULT '',
    source_draft_warnings TEXT NOT NULL DEFAULT '[]',
    source_draft_model TEXT NOT NULL DEFAULT '',
    source_draft_risk_score REAL NOT NULL DEFAULT 0,
    source_draft_regenerate_mode TEXT NOT NULL DEFAULT '',
    source_draft_regenerate_note TEXT NOT NULL DEFAULT '',
    source_draft_job_id TEXT NOT NULL DEFAULT '',
    source_draft_started_at TEXT NOT NULL DEFAULT '',
    source_draft_heartbeat_at TEXT NOT NULL DEFAULT '',
    source_draft_phase TEXT NOT NULL DEFAULT '',
    source_draft_last_log TEXT NOT NULL DEFAULT '',
    source_draft_options TEXT NOT NULL DEFAULT '{}',
    autopilot_state TEXT NOT NULL DEFAULT 'idle',
    autopilot_progress INTEGER NOT NULL DEFAULT 0,
    autopilot_phase TEXT NOT NULL DEFAULT '',
    autopilot_last_log TEXT NOT NULL DEFAULT '',
    autopilot_error TEXT NOT NULL DEFAULT '',
    autopilot_job_id TEXT NOT NULL DEFAULT '',
    autopilot_started_at TEXT NOT NULL DEFAULT '',
    autopilot_heartbeat_at TEXT NOT NULL DEFAULT '',
    autopilot_options TEXT NOT NULL DEFAULT '{}',
    autopilot_last_error_code TEXT NOT NULL DEFAULT '',
    autopilot_debug_summary TEXT NOT NULL DEFAULT '',
    autopilot_wait_started_at TEXT NOT NULL DEFAULT '',
    autopilot_retry_count INTEGER NOT NULL DEFAULT 0,
    scene_plan TEXT NOT NULL DEFAULT '{}',
    render_plan TEXT NOT NULL DEFAULT '{}',
    sentences    TEXT NOT NULL DEFAULT '[]',
    media_order  TEXT NOT NULL DEFAULT '[]',
    thumbnail_file TEXT NOT NULL DEFAULT '',
    subtitle_style TEXT NOT NULL DEFAULT '{}',
    voice_preset TEXT NOT NULL DEFAULT 'auto',
    tts_profile TEXT NOT NULL DEFAULT '{}',
    kenburns_enabled INTEGER NOT NULL DEFAULT 0,
    bgm_file TEXT NOT NULL DEFAULT '',
    bgm_volume_db INTEGER NOT NULL DEFAULT -20,
    bgm_ducking_enabled INTEGER NOT NULL DEFAULT 1,
    render_formats TEXT NOT NULL DEFAULT '["landscape"]',
    youtube_schedule_at TEXT NOT NULL DEFAULT '',
    tts_state    TEXT NOT NULL DEFAULT 'idle',
    tts_progress INTEGER NOT NULL DEFAULT 0,
    tts_error TEXT NOT NULL DEFAULT '',
    tts_job_id TEXT NOT NULL DEFAULT '',
    tts_started_at TEXT NOT NULL DEFAULT '',
    tts_heartbeat_at TEXT NOT NULL DEFAULT '',
    render_state TEXT NOT NULL DEFAULT 'idle',
    render_progress INTEGER NOT NULL DEFAULT 0,
    render_phase TEXT NOT NULL DEFAULT '',
    render_phase_pct INTEGER NOT NULL DEFAULT 0,
    render_progress_detail TEXT NOT NULL DEFAULT '',
    render_speed_x REAL NOT NULL DEFAULT 0,
    render_eta_sec INTEGER NOT NULL DEFAULT 0,
    render_job_id TEXT NOT NULL DEFAULT '',
    render_started_at TEXT NOT NULL DEFAULT '',
    render_heartbeat_at TEXT NOT NULL DEFAULT '',
    render_last_log TEXT NOT NULL DEFAULT '',
    upload_state TEXT NOT NULL DEFAULT 'idle',
    upload_progress INTEGER NOT NULL DEFAULT 0,
    media_upload_state TEXT NOT NULL DEFAULT 'idle',
    media_upload_progress INTEGER NOT NULL DEFAULT 0,
    media_upload_completed INTEGER NOT NULL DEFAULT 0,
    media_upload_total INTEGER NOT NULL DEFAULT 0,
    media_upload_error TEXT NOT NULL DEFAULT '',
    youtube_id   TEXT,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
"""

MIGRATION_COLUMNS: dict[str, str] = {
    "media_upload_state": "TEXT NOT NULL DEFAULT 'idle'",
    "media_upload_progress": "INTEGER NOT NULL DEFAULT 0",
    "media_upload_completed": "INTEGER NOT NULL DEFAULT 0",
    "media_upload_total": "INTEGER NOT NULL DEFAULT 0",
    "media_upload_error": "TEXT NOT NULL DEFAULT ''",
    "content_mode": "TEXT NOT NULL DEFAULT 'standard'",
    "visual_source_mode": "TEXT NOT NULL DEFAULT 'upload_only'",
    "user_script": "TEXT NOT NULL DEFAULT ''",
    "compiled_script": "TEXT NOT NULL DEFAULT ''",
    "regional_sentences": "TEXT NOT NULL DEFAULT '[]'",
    "bible_query": "TEXT NOT NULL DEFAULT ''",
    "selected_verses": "TEXT NOT NULL DEFAULT '[]'",
    "bible_background_file": "TEXT NOT NULL DEFAULT ''",
    "body_image_state": "TEXT NOT NULL DEFAULT 'idle'",
    "body_image_progress": "INTEGER NOT NULL DEFAULT 0",
    "body_image_error": "TEXT NOT NULL DEFAULT ''",
    "body_image_mappings": "TEXT NOT NULL DEFAULT '[]'",
    "body_image_job_id": "TEXT NOT NULL DEFAULT ''",
    "body_image_started_at": "TEXT NOT NULL DEFAULT ''",
    "body_image_heartbeat_at": "TEXT NOT NULL DEFAULT ''",
    "body_image_phase": "TEXT NOT NULL DEFAULT ''",
    "body_image_last_log": "TEXT NOT NULL DEFAULT ''",
    "body_image_options": "TEXT NOT NULL DEFAULT '{}'",
    "source_draft_state": "TEXT NOT NULL DEFAULT 'idle'",
    "source_draft_progress": "INTEGER NOT NULL DEFAULT 0",
    "source_draft_error": "TEXT NOT NULL DEFAULT ''",
    "source_draft_input_mode": "TEXT NOT NULL DEFAULT ''",
    "source_draft_query": "TEXT NOT NULL DEFAULT ''",
    "source_draft_sources": "TEXT NOT NULL DEFAULT '[]'",
    "source_draft_fact_notes": "TEXT NOT NULL DEFAULT '[]'",
    "source_draft_script": "TEXT NOT NULL DEFAULT ''",
    "source_draft_previous_script": "TEXT NOT NULL DEFAULT ''",
    "source_draft_warnings": "TEXT NOT NULL DEFAULT '[]'",
    "source_draft_model": "TEXT NOT NULL DEFAULT ''",
    "source_draft_risk_score": "REAL NOT NULL DEFAULT 0",
    "source_draft_regenerate_mode": "TEXT NOT NULL DEFAULT ''",
    "source_draft_regenerate_note": "TEXT NOT NULL DEFAULT ''",
    "source_draft_job_id": "TEXT NOT NULL DEFAULT ''",
    "source_draft_started_at": "TEXT NOT NULL DEFAULT ''",
    "source_draft_heartbeat_at": "TEXT NOT NULL DEFAULT ''",
    "source_draft_phase": "TEXT NOT NULL DEFAULT ''",
    "source_draft_last_log": "TEXT NOT NULL DEFAULT ''",
    "source_draft_options": "TEXT NOT NULL DEFAULT '{}'",
    "autopilot_state": "TEXT NOT NULL DEFAULT 'idle'",
    "autopilot_progress": "INTEGER NOT NULL DEFAULT 0",
    "autopilot_phase": "TEXT NOT NULL DEFAULT ''",
    "autopilot_last_log": "TEXT NOT NULL DEFAULT ''",
    "autopilot_error": "TEXT NOT NULL DEFAULT ''",
    "autopilot_job_id": "TEXT NOT NULL DEFAULT ''",
    "autopilot_started_at": "TEXT NOT NULL DEFAULT ''",
    "autopilot_heartbeat_at": "TEXT NOT NULL DEFAULT ''",
    "autopilot_options": "TEXT NOT NULL DEFAULT '{}'",
    "autopilot_last_error_code": "TEXT NOT NULL DEFAULT ''",
    "autopilot_debug_summary": "TEXT NOT NULL DEFAULT ''",
    "autopilot_wait_started_at": "TEXT NOT NULL DEFAULT ''",
    "autopilot_retry_count": "INTEGER NOT NULL DEFAULT 0",
    "scene_plan": "TEXT NOT NULL DEFAULT '{}'",
    "render_plan": "TEXT NOT NULL DEFAULT '{}'",
    "thumbnail_file": "TEXT NOT NULL DEFAULT ''",
    "subtitle_style": "TEXT NOT NULL DEFAULT '{}'",
    "tts_profile": "TEXT NOT NULL DEFAULT '{}'",
    "kenburns_enabled": "INTEGER NOT NULL DEFAULT 0",
    "bgm_file": "TEXT NOT NULL DEFAULT ''",
    "bgm_volume_db": "INTEGER NOT NULL DEFAULT -20",
    "bgm_ducking_enabled": "INTEGER NOT NULL DEFAULT 1",
    "render_formats": "TEXT NOT NULL DEFAULT '[\"landscape\"]'",
    "youtube_schedule_at": "TEXT NOT NULL DEFAULT ''",
    "render_phase": "TEXT NOT NULL DEFAULT ''",
    "render_phase_pct": "INTEGER NOT NULL DEFAULT 0",
    "render_progress_detail": "TEXT NOT NULL DEFAULT ''",
    "render_speed_x": "REAL NOT NULL DEFAULT 0",
    "render_eta_sec": "INTEGER NOT NULL DEFAULT 0",
    "render_job_id": "TEXT NOT NULL DEFAULT ''",
    "render_started_at": "TEXT NOT NULL DEFAULT ''",
    "render_heartbeat_at": "TEXT NOT NULL DEFAULT ''",
    "render_last_log": "TEXT NOT NULL DEFAULT ''",
    "tts_error": "TEXT NOT NULL DEFAULT ''",
    "tts_job_id": "TEXT NOT NULL DEFAULT ''",
    "tts_started_at": "TEXT NOT NULL DEFAULT ''",
    "tts_heartbeat_at": "TEXT NOT NULL DEFAULT ''",
}


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.execute("PRAGMA busy_timeout=5000")
    return connection


def init_db() -> None:
    with _connect() as connection:
        connection.executescript(SCHEMA)
        existing_columns = {
            str(row["name"])
            for row in connection.execute("PRAGMA table_info(projects)").fetchall()
        }
        for column, ddl in MIGRATION_COLUMNS.items():
            if column not in existing_columns:
                connection.execute(f"ALTER TABLE projects ADD COLUMN {column} {ddl}")
        connection.execute(
            """
            UPDATE projects
            SET
                user_script=CASE WHEN user_script='' THEN script ELSE user_script END,
                compiled_script=CASE WHEN compiled_script='' THEN script ELSE compiled_script END
            WHERE user_script='' OR compiled_script=''
            """
        )


def recover_interrupted_tasks() -> dict[str, int]:
    with tx() as connection:
        tts_count = connection.execute(
            """
            UPDATE projects
            SET
                tts_state='error',
                tts_progress=0,
                tts_error=?,
                tts_job_id='',
                tts_started_at='',
                tts_heartbeat_at='',
                updated_at=?
            WHERE tts_state IN ('queued', 'running')
            """,
            ("Previous TTS job was interrupted when the server restarted. Start TTS again.", _now()),
        ).rowcount
        body_image_count = connection.execute(
            """
            UPDATE projects
            SET
                body_image_state='error',
                body_image_progress=0,
                body_image_error=?,
                body_image_phase='',
                body_image_last_log='',
                body_image_job_id='',
                body_image_started_at='',
                body_image_heartbeat_at='',
                updated_at=?
            WHERE body_image_state IN ('queued', 'running')
            """,
            ("Previous image job was interrupted when the server restarted. Start generation again.", _now()),
        ).rowcount
        render_count = connection.execute(
            """
            UPDATE projects
            SET
                render_state='error',
                render_progress=0,
                render_phase='',
                render_phase_pct=0,
                render_progress_detail='',
                render_speed_x=0,
                render_eta_sec=0,
                render_job_id='',
                render_started_at='',
                render_heartbeat_at='',
                render_last_log=?,
                updated_at=?
            WHERE render_state='running'
            """,
            ("Previous render was interrupted when the server restarted. Start render again.", _now()),
        ).rowcount
        upload_count = connection.execute(
            "UPDATE projects SET upload_state='error', upload_progress=0, updated_at=? WHERE upload_state='running'",
            (_now(),),
        ).rowcount
        media_upload_count = connection.execute(
            """
            UPDATE projects
            SET
                media_upload_state='error',
                media_upload_error=?,
                updated_at=?
            WHERE media_upload_state='running'
            """,
            ("Previous media upload was interrupted when the server restarted. Upload the files again.", _now()),
        ).rowcount
        source_draft_count = connection.execute(
            """
            UPDATE projects
            SET
                source_draft_state='error',
                source_draft_progress=0,
                source_draft_error=?,
                source_draft_phase='',
                source_draft_last_log='',
                source_draft_job_id='',
                source_draft_started_at='',
                source_draft_heartbeat_at='',
                updated_at=?
            WHERE source_draft_state IN ('queued', 'running')
            """,
            ("Previous source draft job was interrupted when the server restarted. Start generation again.", _now()),
        ).rowcount
        autopilot_count = connection.execute(
            """
            UPDATE projects
            SET
                autopilot_state='error',
                autopilot_progress=0,
                autopilot_phase='',
                autopilot_last_log=?,
                autopilot_error=?,
                autopilot_job_id='',
                autopilot_started_at='',
                autopilot_heartbeat_at='',
                autopilot_last_error_code='SYSTEM_RESTART_INTERRUPTED',
                autopilot_debug_summary=?,
                autopilot_wait_started_at='',
                autopilot_retry_count=0,
                updated_at=?
            WHERE autopilot_state='running'
            """,
            (
                "Previous autopilot job was interrupted when the server restarted.",
                "Previous autopilot job was interrupted when the server restarted. Start autopilot again.",
                "Server restart interrupted the autopilot run.",
                _now(),
            ),
        ).rowcount
    return {
        "tts": tts_count,
        "body_image": body_image_count,
        "render": render_count,
        "upload": upload_count,
        "media_upload": media_upload_count,
        "source_draft": source_draft_count,
        "autopilot": autopilot_count,
    }


@contextmanager
def tx() -> Iterator[sqlite3.Connection]:
    connection = _connect()
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _now() -> str:
    return now_iso()


def _parse_iso_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _load_json_list(value: object) -> list[object]:
    try:
        payload = json.loads(str(value or "[]"))
    except json.JSONDecodeError:
        return []
    return payload if isinstance(payload, list) else []


def _load_string_list(value: object) -> list[str]:
    return [item for item in _load_json_list(value) if isinstance(item, str)]


def _load_regional_sentences(value: object) -> list[RegionalSentence]:
    regional_sentences: list[RegionalSentence] = []
    for item in _load_json_list(value):
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        region = item.get("region")
        if not isinstance(text, str) or region not in {"intro", "body", "bible"}:
            continue
        regional_sentences.append(
            {
                "idx": len(regional_sentences),
                "text": text,
                "region": cast(Region, region),
            }
        )
    return regional_sentences


def _load_selected_verses(value: object) -> list[SelectedVerse]:
    selected_verses: list[SelectedVerse] = []
    for item in _load_json_list(value):
        if not isinstance(item, dict):
            continue
        reference = item.get("reference")
        text = item.get("text")
        if isinstance(reference, str) and isinstance(text, str):
            selected_verses.append({"reference": reference, "text": text})
    return selected_verses


def _load_body_image_mappings(value: object) -> list[BodyImageMapping]:
    mappings: list[BodyImageMapping] = []
    for item in _load_json_list(value):
        if not isinstance(item, dict):
            continue
        sentence_idx = item.get("sentence_idx")
        path = item.get("path")
        prompt = item.get("prompt")
        if isinstance(sentence_idx, int) and isinstance(path, str) and isinstance(prompt, str):
            mapping: BodyImageMapping = {"sentence_idx": sentence_idx, "path": path, "prompt": prompt}
            sentence_text = item.get("sentence_text")
            sentence_hash = item.get("sentence_hash")
            project_id = item.get("project_id")
            prompt_id = item.get("prompt_id")
            manifest_sentence_hash = item.get("manifest_sentence_hash")
            selected_reason = item.get("selected_reason")
            candidate_index = item.get("candidate_index")
            candidate_total = item.get("candidate_total")
            candidate_score = item.get("candidate_score")
            candidate_score_version = item.get("candidate_score_version")
            vision_qa_issue_codes = item.get("vision_qa_issue_codes")
            if isinstance(sentence_text, str):
                mapping["sentence_text"] = sentence_text
            if isinstance(sentence_hash, str):
                mapping["sentence_hash"] = sentence_hash
            if isinstance(project_id, str):
                mapping["project_id"] = project_id
            if isinstance(prompt_id, str):
                mapping["prompt_id"] = prompt_id
            if isinstance(manifest_sentence_hash, str):
                mapping["manifest_sentence_hash"] = manifest_sentence_hash
            if isinstance(selected_reason, str):
                mapping["selected_reason"] = selected_reason
            if isinstance(candidate_index, int):
                mapping["candidate_index"] = candidate_index
            if isinstance(candidate_total, int):
                mapping["candidate_total"] = candidate_total
            if isinstance(candidate_score, (int, float)):
                mapping["candidate_score"] = float(candidate_score)
            if isinstance(candidate_score_version, str):
                mapping["candidate_score_version"] = candidate_score_version
            if isinstance(vision_qa_issue_codes, list):
                mapping["vision_qa_issue_codes"] = [
                    code for code in vision_qa_issue_codes if isinstance(code, str)
                ]
            mappings.append(mapping)
    return mappings


def _load_source_items(value: object) -> list[SourceDraftSource]:
    items: list[SourceDraftSource] = []
    for item in _load_json_list(value):
        if not isinstance(item, dict):
            continue
        payload = {
            "id": item.get("id"),
            "url": item.get("url"),
            "final_url": item.get("final_url"),
            "title": item.get("title"),
            "domain": item.get("domain"),
            "author": item.get("author"),
            "published_at": item.get("published_at"),
            "language": item.get("language"),
            "excerpt": item.get("excerpt"),
            "fetched_at": item.get("fetched_at"),
            "word_count": item.get("word_count"),
        }
        if not all(isinstance(payload[key], str) for key in payload if key != "word_count"):
            continue
        if not isinstance(payload["word_count"], int):
            continue
        items.append(cast(SourceDraftSource, payload))
    return items


def _load_source_fact_notes(value: object) -> list[SourceDraftFactNote]:
    notes: list[SourceDraftFactNote] = []
    for item in _load_json_list(value):
        if not isinstance(item, dict):
            continue
        source_id = item.get("source_id")
        note = item.get("note")
        if isinstance(source_id, str) and isinstance(note, str):
            notes.append({"source_id": source_id, "note": note})
    return notes


def _load_render_plan(value: object) -> RenderPlan | None:
    try:
        payload = json.loads(str(value or "{}"))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict) or not payload:
        return None
    version = payload.get("version")
    total_duration = payload.get("total_duration")
    segments = payload.get("segments")
    if not isinstance(version, int) or not isinstance(total_duration, (int, float)) or not isinstance(segments, list):
        return None
    normalized_segments: list[RenderPlanSegment] = []
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        region = segment.get("region")
        start = segment.get("start")
        end = segment.get("end")
        media = segment.get("media")
        sentence_idx = segment.get("sentence_idx")
        motion = segment.get("motion")
        effect = segment.get("effect")
        caption_style = segment.get("caption_style")
        if region not in {"intro", "body", "bible"} or not isinstance(start, (int, float)) or not isinstance(end, (int, float)) or not isinstance(media, list):
            continue
        normalized_media: list[RenderPlanSegmentMedia] = []
        for media_item in media:
            if not isinstance(media_item, dict):
                continue
            path = media_item.get("path")
            kind = media_item.get("kind")
            if isinstance(path, str) and kind in {"image", "video"}:
                normalized_media.append({"path": path, "kind": cast(MediaKind, kind)})
        normalized_segment: RenderPlanSegment = {
            "region": cast(Region, region),
            "start": float(start),
            "end": float(end),
            "media": normalized_media,
            "motion": motion if isinstance(motion, str) else "none",
            "effect": effect if isinstance(effect, str) else "none",
            "caption_style": caption_style if isinstance(caption_style, str) else "plain",
        }
        if isinstance(sentence_idx, int):
            normalized_segment["sentence_idx"] = sentence_idx
        normalized_segments.append(normalized_segment)
    return {
        "version": version,
        "total_duration": float(total_duration),
        "segments": normalized_segments,
    }


def _load_scene_plan(value: object) -> ScenePlan | None:
    try:
        payload = json.loads(str(value or "{}"))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict) or not payload:
        return None
    version = payload.get("version")
    plan_format = payload.get("format")
    total_duration = payload.get("total_duration")
    scenes = payload.get("scenes")
    if (
        not isinstance(version, int)
        or plan_format not in {"landscape", "shorts"}
        or not isinstance(total_duration, (int, float))
        or not isinstance(scenes, list)
    ):
        return None
    normalized_scenes: list[ScenePlanScene] = []
    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        region = scene.get("region")
        if region not in {"intro", "body", "bible"}:
            continue
        idx = scene.get("idx")
        sentence_idx = scene.get("sentence_idx")
        text = scene.get("text")
        duration_sec = scene.get("duration_sec")
        visual_intent = scene.get("visual_intent")
        prompt = scene.get("prompt")
        style = scene.get("style")
        media_path = scene.get("media_path")
        if not isinstance(idx, int) or not isinstance(sentence_idx, int):
            continue
        if not isinstance(text, str) or not isinstance(visual_intent, str) or not isinstance(prompt, str):
            continue
        if not isinstance(style, str) or not isinstance(media_path, str) or not isinstance(duration_sec, (int, float)):
            continue
        normalized_scenes.append(
            {
                "idx": idx,
                "sentence_idx": sentence_idx,
                "text": text,
                "region": cast(Region, region),
                "duration_sec": float(duration_sec),
                "visual_intent": visual_intent,
                "prompt": prompt,
                "style": style,
                "media_path": media_path,
            }
        )
        normalized_scene = normalized_scenes[-1]
        key_concept = scene.get("key_concept")
        visual_metaphor = scene.get("visual_metaphor")
        subject = scene.get("subject")
        props = scene.get("props")
        background = scene.get("background")
        avoid = scene.get("avoid")
        core_meaning = scene.get("core_meaning")
        primary_keywords = scene.get("primary_keywords")
        secondary_keywords = scene.get("secondary_keywords")
        subject_modes = scene.get("subject_modes")
        must_show = scene.get("must_show")
        may_show = scene.get("may_show")
        prompt_hint = scene.get("prompt_hint")
        vocab_refs = scene.get("vocab_refs")
        domain = scene.get("domain")
        locked = scene.get("locked")
        subtitle_override = scene.get("subtitle_override")
        if isinstance(key_concept, str):
            normalized_scene["key_concept"] = key_concept
        if isinstance(visual_metaphor, str):
            normalized_scene["visual_metaphor"] = visual_metaphor
        if isinstance(subject, str):
            normalized_scene["subject"] = subject
        if isinstance(props, list):
            normalized_props = [item for item in props if isinstance(item, str)]
            if normalized_props:
                normalized_scene["props"] = normalized_props
        if isinstance(background, str):
            normalized_scene["background"] = background
        if isinstance(avoid, list):
            normalized_avoid = [item for item in avoid if isinstance(item, str)]
            if normalized_avoid:
                normalized_scene["avoid"] = normalized_avoid
        if isinstance(core_meaning, str):
            normalized_scene["core_meaning"] = core_meaning
        if isinstance(primary_keywords, list):
            normalized_primary_keywords = [item for item in primary_keywords if isinstance(item, str)]
            if normalized_primary_keywords:
                normalized_scene["primary_keywords"] = normalized_primary_keywords
        if isinstance(secondary_keywords, list):
            normalized_secondary_keywords = [item for item in secondary_keywords if isinstance(item, str)]
            if normalized_secondary_keywords:
                normalized_scene["secondary_keywords"] = normalized_secondary_keywords
        if isinstance(subject_modes, list):
            normalized_subject_modes = [
                item
                for item in subject_modes
                if item in {"person", "environment", "object_metaphor", "symbolic"}
            ]
            if normalized_subject_modes:
                normalized_scene["subject_modes"] = normalized_subject_modes
        if isinstance(must_show, list):
            normalized_must_show = [item for item in must_show if isinstance(item, str)]
            if normalized_must_show:
                normalized_scene["must_show"] = normalized_must_show
        if isinstance(may_show, list):
            normalized_may_show = [item for item in may_show if isinstance(item, str)]
            if normalized_may_show:
                normalized_scene["may_show"] = normalized_may_show
        if isinstance(prompt_hint, str):
            normalized_scene["prompt_hint"] = prompt_hint
        if isinstance(vocab_refs, list):
            normalized_vocab_refs = [item for item in vocab_refs if isinstance(item, str)]
            if normalized_vocab_refs:
                normalized_scene["vocab_refs"] = normalized_vocab_refs
        if isinstance(domain, str):
            normalized_scene["domain"] = domain
        if isinstance(locked, bool):
            normalized_scene["locked"] = locked
        if subtitle_override is None:
            normalized_scene["subtitle_override"] = None
        elif isinstance(subtitle_override, dict):
            normalized_scene["subtitle_override"] = normalize_subtitle_style(subtitle_override)
    return {
        "version": version,
        "format": cast(RenderFormat, plan_format),
        "total_duration": float(total_duration),
        "scenes": normalized_scenes,
    }


def _load_json_dict(value: object) -> dict[str, object]:
    try:
        payload = json.loads(str(value or "{}"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _content_mode(value: object) -> ContentMode:
    return "bible_longform" if value == "bible_longform" else "standard"


def _visual_source_mode(value: object) -> VisualSourceMode:
    if value in {"hybrid", "comfyui_auto"}:
        return cast(VisualSourceMode, value)
    return "upload_only"


def _source_draft_input_mode(value: object) -> SourceDraftInputMode:
    if value == "url":
        return "url"
    if value == "keyword":
        return "keyword"
    return ""


def _source_regenerate_mode(value: object) -> SourceRegenerateMode:
    if value == "hook":
        return "hook"
    if value == "point":
        return "point"
    if value == "story":
        return "story"
    if value == "lesson":
        return "lesson"
    return ""


def _row_to_project(row: sqlite3.Row) -> ProjectRecord:
    script = str(row["script"])
    user_script = str(row["user_script"] or script)
    compiled_script = str(row["compiled_script"] or script)
    sentences = _load_string_list(row["sentences"])
    media_order = _load_string_list(row["media_order"])
    render_formats = _load_string_list(row["render_formats"] or '["landscape"]')
    subtitle_style_payload = json.loads(str(row["subtitle_style"] or "{}"))
    tts_profile_payload = json.loads(str(row["tts_profile"] or "{}"))
    subtitle_style = normalize_subtitle_style(
        subtitle_style_payload if isinstance(subtitle_style_payload, dict) else {}
    )
    voice_preset, tts_profile = normalize_tts_profile(
        tts_profile_payload if isinstance(tts_profile_payload, dict) else {},
        str(row["voice_preset"]),
        compiled_script or script,
    )
    return {
        "id": str(row["id"]),
        "title": str(row["title"]),
        "script": script,
        "content_mode": _content_mode(row["content_mode"]),
        "visual_source_mode": _visual_source_mode(row["visual_source_mode"]),
        "user_script": user_script,
        "compiled_script": compiled_script,
        "regional_sentences": _load_regional_sentences(row["regional_sentences"]),
        "bible_query": str(row["bible_query"] or ""),
        "selected_verses": _load_selected_verses(row["selected_verses"]),
        "bible_background_file": str(row["bible_background_file"] or ""),
        "body_image_state": cast(TaskState, row["body_image_state"]),
        "body_image_progress": int(row["body_image_progress"] or 0),
        "body_image_error": str(row["body_image_error"] or ""),
        "body_image_mappings": _load_body_image_mappings(row["body_image_mappings"]),
        "body_image_job_id": str(row["body_image_job_id"] or ""),
        "body_image_started_at": str(row["body_image_started_at"] or ""),
        "body_image_heartbeat_at": str(row["body_image_heartbeat_at"] or ""),
        "body_image_phase": str(row["body_image_phase"] or ""),
        "body_image_last_log": str(row["body_image_last_log"] or ""),
        "body_image_options": _load_json_dict(row["body_image_options"]),
        "source_draft_state": cast(TaskState, row["source_draft_state"]),
        "source_draft_progress": int(row["source_draft_progress"] or 0),
        "source_draft_error": str(row["source_draft_error"] or ""),
        "source_draft_input_mode": _source_draft_input_mode(row["source_draft_input_mode"]),
        "source_draft_query": str(row["source_draft_query"] or ""),
        "source_draft_sources": _load_source_items(row["source_draft_sources"]),
        "source_draft_fact_notes": _load_source_fact_notes(row["source_draft_fact_notes"]),
        "source_draft_script": str(row["source_draft_script"] or ""),
        "source_draft_previous_script": str(row["source_draft_previous_script"] or ""),
        "source_draft_warnings": _load_string_list(row["source_draft_warnings"]),
        "source_draft_model": str(row["source_draft_model"] or ""),
        "source_draft_risk_score": float(row["source_draft_risk_score"] or 0.0),
        "source_draft_regenerate_mode": _source_regenerate_mode(row["source_draft_regenerate_mode"]),
        "source_draft_regenerate_note": str(row["source_draft_regenerate_note"] or ""),
        "source_draft_job_id": str(row["source_draft_job_id"] or ""),
        "source_draft_started_at": str(row["source_draft_started_at"] or ""),
        "source_draft_heartbeat_at": str(row["source_draft_heartbeat_at"] or ""),
        "source_draft_phase": str(row["source_draft_phase"] or ""),
        "source_draft_last_log": str(row["source_draft_last_log"] or ""),
        "source_draft_options": _load_json_dict(row["source_draft_options"]),
        "autopilot_state": cast(AutopilotState, row["autopilot_state"]),
        "autopilot_progress": int(row["autopilot_progress"] or 0),
        "autopilot_phase": str(row["autopilot_phase"] or ""),
        "autopilot_last_log": str(row["autopilot_last_log"] or ""),
        "autopilot_error": str(row["autopilot_error"] or ""),
        "autopilot_job_id": str(row["autopilot_job_id"] or ""),
        "autopilot_started_at": str(row["autopilot_started_at"] or ""),
        "autopilot_heartbeat_at": str(row["autopilot_heartbeat_at"] or ""),
        "autopilot_options": _load_json_dict(row["autopilot_options"]),
        "autopilot_last_error_code": str(row["autopilot_last_error_code"] or ""),
        "autopilot_debug_summary": str(row["autopilot_debug_summary"] or ""),
        "autopilot_wait_started_at": str(row["autopilot_wait_started_at"] or ""),
        "autopilot_retry_count": int(row["autopilot_retry_count"] or 0),
        "scene_plan": _load_scene_plan(row["scene_plan"]),
        "render_plan": _load_render_plan(row["render_plan"]),
        "sentences": sentences,
        "media_order": media_order,
        "thumbnail_file": str(row["thumbnail_file"] or ""),
        "subtitle_style": subtitle_style,
        "voice_preset": voice_preset,
        "tts_profile": tts_profile,
        "kenburns_enabled": bool(int(row["kenburns_enabled"])),
        "bgm_file": str(row["bgm_file"] or ""),
        "bgm_volume_db": int(row["bgm_volume_db"]),
        "bgm_ducking_enabled": bool(int(row["bgm_ducking_enabled"])),
        "render_formats": cast(list[RenderFormat], [fmt for fmt in render_formats if fmt in {"landscape", "shorts"}] or ["landscape"]),
        "youtube_schedule_at": str(row["youtube_schedule_at"] or ""),
        "tts_state": cast(TaskState, row["tts_state"]),
        "tts_progress": int(row["tts_progress"]),
        "tts_error": str(row["tts_error"] or ""),
        "tts_job_id": str(row["tts_job_id"] or ""),
        "tts_started_at": str(row["tts_started_at"] or ""),
        "tts_heartbeat_at": str(row["tts_heartbeat_at"] or ""),
        "render_state": cast(TaskState, row["render_state"]),
        "render_progress": int(row["render_progress"]),
        "render_phase": str(row["render_phase"] or ""),
        "render_phase_pct": int(row["render_phase_pct"] or 0),
        "render_progress_detail": str(row["render_progress_detail"] or ""),
        "render_speed_x": float(row["render_speed_x"] or 0.0),
        "render_eta_sec": int(row["render_eta_sec"] or 0),
        "render_job_id": str(row["render_job_id"] or ""),
        "render_started_at": str(row["render_started_at"] or ""),
        "render_heartbeat_at": str(row["render_heartbeat_at"] or ""),
        "render_last_log": str(row["render_last_log"] or ""),
        "upload_state": cast(TaskState, row["upload_state"]),
        "upload_progress": int(row["upload_progress"]),
        "media_upload_state": cast(TaskState, row["media_upload_state"]),
        "media_upload_progress": int(row["media_upload_progress"]),
        "media_upload_completed": int(row["media_upload_completed"]),
        "media_upload_total": int(row["media_upload_total"]),
        "media_upload_error": str(row["media_upload_error"]),
        "youtube_id": cast(str | None, row["youtube_id"]),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }


def create_project(title: str = "") -> ProjectRecord:
    project_id = uuid.uuid4().hex[:12]
    (PROJECTS_DIR / project_id / "media").mkdir(parents=True, exist_ok=True)
    (PROJECTS_DIR / project_id / "tts").mkdir(parents=True, exist_ok=True)
    now = _now()
    with tx() as connection:
        connection.execute(
            "INSERT INTO projects (id, title, created_at, updated_at) VALUES (?,?,?,?)",
            (project_id, title, now, now),
        )
    project = get_project(project_id)
    if project is None:
        raise RuntimeError(f"project {project_id} was not created")
    return project


def list_projects() -> list[ProjectCard]:
    with tx() as connection:
        rows = connection.execute(
            "SELECT id, title, updated_at, tts_state, render_state, upload_state, youtube_id "
            "FROM projects ORDER BY updated_at DESC"
        ).fetchall()
    return [
        {
            "id": str(row["id"]),
            "title": str(row["title"]),
            "updated_at": str(row["updated_at"]),
            "tts_state": cast(TaskState, row["tts_state"]),
            "render_state": cast(TaskState, row["render_state"]),
            "upload_state": cast(TaskState, row["upload_state"]),
            "youtube_id": cast(str | None, row["youtube_id"]),
        }
        for row in rows
    ]


def get_project(pid: str) -> ProjectRecord | None:
    with tx() as connection:
        row = connection.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    return _row_to_project(row) if row else None


def update_project(pid: str, **fields: object) -> ProjectRecord | None:
    if not fields:
        return get_project(pid)
    for key in (
        "sentences",
        "media_order",
        "subtitle_style",
        "render_formats",
        "tts_profile",
        "regional_sentences",
        "selected_verses",
        "body_image_mappings",
        "body_image_options",
        "source_draft_sources",
        "source_draft_fact_notes",
        "source_draft_warnings",
        "source_draft_options",
        "autopilot_options",
        "scene_plan",
        "render_plan",
    ):
        if key in fields and not isinstance(fields[key], str):
            fields[key] = json.dumps(fields[key], ensure_ascii=False)
    for key in ("kenburns_enabled", "bgm_ducking_enabled"):
        if key in fields:
            fields[key] = 1 if bool(fields[key]) else 0
    fields["updated_at"] = _now()
    columns = ", ".join(f"{key}=?" for key in fields)
    with tx() as connection:
        connection.execute(f"UPDATE projects SET {columns} WHERE id=?", (*fields.values(), pid))
    return get_project(pid)


def delete_project(pid: str) -> None:
    with tx() as connection:
        connection.execute("DELETE FROM projects WHERE id=?", (pid,))


def project_dir(pid: str) -> Path:
    return PROJECTS_DIR / pid


def claim_next_queued_source_draft() -> str | None:
    with tx() as connection:
        row = connection.execute(
            "SELECT id FROM projects WHERE source_draft_state='queued' ORDER BY updated_at LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        pid = str(row["id"])
        job_id = uuid.uuid4().hex
        now = _now()
        cursor = connection.execute(
            """
            UPDATE projects
            SET
                source_draft_state='running',
                source_draft_job_id=?,
                source_draft_started_at=?,
                source_draft_heartbeat_at=?,
                updated_at=?
            WHERE id=? AND source_draft_state='queued'
            """,
            (job_id, now, now, now, pid),
        )
        if cursor.rowcount == 0:
            return None
    return pid


def claim_next_queued_body_image() -> str | None:
    with tx() as connection:
        row = connection.execute(
            "SELECT id FROM projects WHERE body_image_state='queued' ORDER BY updated_at LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        pid = str(row["id"])
        job_id = uuid.uuid4().hex
        now = _now()
        cursor = connection.execute(
            """
            UPDATE projects
            SET
                body_image_state='running',
                body_image_job_id=?,
                body_image_started_at=?,
                body_image_heartbeat_at=?,
                updated_at=?
            WHERE id=? AND body_image_state='queued'
            """,
            (job_id, now, now, now, pid),
        )
        if cursor.rowcount == 0:
            return None
    return pid


def touch_body_image_heartbeat(pid: str) -> None:
    update_project(pid, body_image_heartbeat_at=_now())


def touch_source_draft_heartbeat(pid: str) -> None:
    update_project(pid, source_draft_heartbeat_at=_now())


def claim_next_queued_autopilot() -> str | None:
    with tx() as connection:
        row = connection.execute(
            "SELECT id FROM projects WHERE autopilot_state='queued' ORDER BY updated_at LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        pid = str(row["id"])
        now = _now()
        cursor = connection.execute(
            """
            UPDATE projects
            SET
                autopilot_state='running',
                autopilot_started_at=CASE WHEN autopilot_started_at='' THEN ? ELSE autopilot_started_at END,
                autopilot_heartbeat_at=?,
                updated_at=?
            WHERE id=? AND autopilot_state='queued'
            """,
            (now, now, now, pid),
        )
        if cursor.rowcount == 0:
            return None
    return pid


def touch_autopilot_heartbeat(pid: str) -> None:
    update_project(pid, autopilot_heartbeat_at=_now())


def claim_next_queued_tts() -> str | None:
    with tx() as connection:
        row = connection.execute(
            "SELECT id FROM projects WHERE tts_state='queued' ORDER BY updated_at LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        pid = str(row["id"])
        job_id = uuid.uuid4().hex
        now = _now()
        cursor = connection.execute(
            """
            UPDATE projects
            SET
                tts_state='running',
                tts_job_id=?,
                tts_started_at=?,
                tts_heartbeat_at=?,
                updated_at=?
            WHERE id=? AND tts_state='queued'
            """,
            (job_id, now, now, now, pid),
        )
        if cursor.rowcount == 0:
            return None
    return pid


def touch_tts_heartbeat(pid: str) -> None:
    update_project(pid, tts_heartbeat_at=_now())


def claim_next_queued_render() -> str | None:
    with tx() as connection:
        row = connection.execute(
            "SELECT id FROM projects WHERE render_state='queued' ORDER BY updated_at LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        pid = str(row["id"])
        job_id = uuid.uuid4().hex
        now = _now()
        cursor = connection.execute(
            """
            UPDATE projects
            SET
                render_state='running',
                render_job_id=?,
                render_started_at=?,
                render_heartbeat_at=?,
                updated_at=?
            WHERE id=? AND render_state='queued'
            """,
            (job_id, now, now, now, pid),
        )
        if cursor.rowcount == 0:
            return None
    return pid


def touch_render_heartbeat(pid: str) -> None:
    update_project(pid, render_heartbeat_at=_now())


def recover_stale_autopilot_jobs(
    *,
    stale_after_sec: int,
    max_runtime_sec: int,
) -> int:
    now = datetime.now(timezone.utc)
    recovered = 0
    with tx() as connection:
        rows = connection.execute(
            """
            SELECT id, autopilot_started_at, autopilot_heartbeat_at
            FROM projects
            WHERE autopilot_state='running'
            """
        ).fetchall()
        for row in rows:
            pid = str(row["id"])
            started_at = _parse_iso_datetime(str(row["autopilot_started_at"] or ""))
            heartbeat_at = _parse_iso_datetime(str(row["autopilot_heartbeat_at"] or ""))
            heartbeat_dead = heartbeat_at is None or now - heartbeat_at > timedelta(seconds=stale_after_sec)
            runtime_dead = started_at is not None and now - started_at > timedelta(seconds=max_runtime_sec)
            if not heartbeat_dead and not runtime_dead:
                continue
            connection.execute(
                """
                UPDATE projects
                SET
                    autopilot_state='error',
                    autopilot_progress=0,
                    autopilot_phase='',
                    autopilot_last_log=?,
                    autopilot_error=?,
                    autopilot_last_error_code='SYSTEM_HEARTBEAT_EXPIRED',
                    autopilot_debug_summary=?,
                    autopilot_job_id='',
                    autopilot_started_at='',
                    autopilot_heartbeat_at='',
                    autopilot_wait_started_at='',
                    autopilot_retry_count=0,
                    updated_at=?
                WHERE id=?
                """,
                (
                    "Autopilot worker heartbeat expired.",
                    "Autopilot worker heartbeat expired. Start autopilot again.",
                    "Autopilot worker heartbeat expired.",
                    _now(),
                    pid,
                ),
            )
            recovered += 1
    return recovered


def recover_stale_render_jobs(
    *,
    stale_after_sec: int,
    max_runtime_sec: int,
) -> int:
    now = datetime.now(timezone.utc)
    recovered = 0
    with tx() as connection:
        rows = connection.execute(
            """
            SELECT id, render_started_at, render_heartbeat_at
            FROM projects
            WHERE render_state='running'
            """
        ).fetchall()
        for row in rows:
            pid = str(row["id"])
            started_at = _parse_iso_datetime(str(row["render_started_at"] or ""))
            heartbeat_at = _parse_iso_datetime(str(row["render_heartbeat_at"] or ""))
            heartbeat_dead = heartbeat_at is None or now - heartbeat_at > timedelta(seconds=stale_after_sec)
            runtime_dead = started_at is not None and now - started_at > timedelta(seconds=max_runtime_sec)
            if not heartbeat_dead and not runtime_dead:
                continue
            connection.execute(
                """
                UPDATE projects
                SET
                    render_state='error',
                    render_progress=0,
                    render_phase='',
                    render_phase_pct=0,
                    render_progress_detail='',
                    render_speed_x=0,
                    render_eta_sec=0,
                    render_job_id='',
                    render_started_at='',
                    render_heartbeat_at='',
                    render_last_log=?,
                    updated_at=?
                WHERE id=?
                """,
                ("Render worker heartbeat expired. Start render again.", _now(), pid),
            )
            recovered += 1
    return recovered


def recover_stale_tts_jobs(
    *,
    stale_after_sec: int,
    max_runtime_sec: int,
) -> int:
    now = datetime.now(timezone.utc)
    recovered = 0
    with tx() as connection:
        rows = connection.execute(
            """
            SELECT id, tts_started_at, tts_heartbeat_at
            FROM projects
            WHERE tts_state='running'
            """
        ).fetchall()
        for row in rows:
            pid = str(row["id"])
            started_at = _parse_iso_datetime(str(row["tts_started_at"] or ""))
            heartbeat_at = _parse_iso_datetime(str(row["tts_heartbeat_at"] or ""))
            heartbeat_dead = heartbeat_at is None or now - heartbeat_at > timedelta(seconds=stale_after_sec)
            runtime_dead = started_at is not None and now - started_at > timedelta(seconds=max_runtime_sec)
            if not heartbeat_dead and not runtime_dead:
                continue
            connection.execute(
                """
                UPDATE projects
                SET
                    tts_state='error',
                    tts_progress=0,
                    tts_error=?,
                    tts_job_id='',
                    tts_started_at='',
                    tts_heartbeat_at='',
                    updated_at=?
                WHERE id=?
                """,
                ("TTS worker heartbeat expired. Start TTS again.", _now(), pid),
            )
            recovered += 1
    return recovered


def recover_stale_source_draft_jobs(
    *,
    stale_after_sec: int,
    max_runtime_sec: int,
) -> int:
    now = datetime.now(timezone.utc)
    recovered = 0
    with tx() as connection:
        rows = connection.execute(
            """
            SELECT id, source_draft_started_at, source_draft_heartbeat_at
            FROM projects
            WHERE source_draft_state='running'
            """
        ).fetchall()
        for row in rows:
            pid = str(row["id"])
            started_at = _parse_iso_datetime(str(row["source_draft_started_at"] or ""))
            heartbeat_at = _parse_iso_datetime(str(row["source_draft_heartbeat_at"] or ""))
            heartbeat_dead = heartbeat_at is None or now - heartbeat_at > timedelta(seconds=stale_after_sec)
            runtime_dead = started_at is not None and now - started_at > timedelta(seconds=max_runtime_sec)
            if not heartbeat_dead and not runtime_dead:
                continue
            connection.execute(
                """
                UPDATE projects
                SET
                    source_draft_state='error',
                    source_draft_progress=0,
                    source_draft_error=?,
                    source_draft_phase='',
                    source_draft_last_log=?,
                    source_draft_job_id='',
                    source_draft_started_at='',
                    source_draft_heartbeat_at='',
                    updated_at=?
                WHERE id=?
                """,
                (
                    "Source draft worker heartbeat expired. Start generation again.",
                    "Source draft worker heartbeat expired.",
                    _now(),
                    pid,
                ),
            )
            recovered += 1
    return recovered


def recover_stale_body_image_jobs(
    *,
    stale_after_sec: int,
    max_runtime_sec: int,
) -> int:
    now = datetime.now(timezone.utc)
    recovered = 0
    with tx() as connection:
        rows = connection.execute(
            """
            SELECT id, body_image_started_at, body_image_heartbeat_at
            FROM projects
            WHERE body_image_state='running'
            """
        ).fetchall()
        for row in rows:
            pid = str(row["id"])
            started_at = _parse_iso_datetime(str(row["body_image_started_at"] or ""))
            heartbeat_at = _parse_iso_datetime(str(row["body_image_heartbeat_at"] or ""))
            heartbeat_dead = heartbeat_at is None or now - heartbeat_at > timedelta(seconds=stale_after_sec)
            runtime_dead = started_at is not None and now - started_at > timedelta(seconds=max_runtime_sec)
            if not heartbeat_dead and not runtime_dead:
                continue
            connection.execute(
                """
                UPDATE projects
                SET
                    body_image_state='error',
                    body_image_progress=0,
                    body_image_error=?,
                    body_image_phase='',
                    body_image_last_log=?,
                    body_image_job_id='',
                    body_image_started_at='',
                    body_image_heartbeat_at='',
                    updated_at=?
                WHERE id=?
                """,
                (
                    "Image worker heartbeat expired. Start image generation again.",
                    "Image worker heartbeat expired.",
                    _now(),
                    pid,
                ),
            )
            recovered += 1
    return recovered
