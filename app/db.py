import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from .config import DB_PATH, PROJECTS_DIR
from .services.subtitle import normalize_subtitle_style
from .types import ProjectCard, ProjectRecord, RenderFormat, TaskState

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id           TEXT PRIMARY KEY,
    title        TEXT NOT NULL DEFAULT '',
    script       TEXT NOT NULL DEFAULT '',
    sentences    TEXT NOT NULL DEFAULT '[]',
    media_order  TEXT NOT NULL DEFAULT '[]',
    thumbnail_file TEXT NOT NULL DEFAULT '',
    subtitle_style TEXT NOT NULL DEFAULT '{}',
    voice_preset TEXT NOT NULL DEFAULT 'auto',
    kenburns_enabled INTEGER NOT NULL DEFAULT 0,
    bgm_file TEXT NOT NULL DEFAULT '',
    bgm_volume_db INTEGER NOT NULL DEFAULT -20,
    bgm_ducking_enabled INTEGER NOT NULL DEFAULT 1,
    render_formats TEXT NOT NULL DEFAULT '["landscape"]',
    youtube_schedule_at TEXT NOT NULL DEFAULT '',
    tts_state    TEXT NOT NULL DEFAULT 'idle',
    tts_progress INTEGER NOT NULL DEFAULT 0,
    render_state TEXT NOT NULL DEFAULT 'idle',
    render_progress INTEGER NOT NULL DEFAULT 0,
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
    "thumbnail_file": "TEXT NOT NULL DEFAULT ''",
    "subtitle_style": "TEXT NOT NULL DEFAULT '{}'",
    "kenburns_enabled": "INTEGER NOT NULL DEFAULT 0",
    "bgm_file": "TEXT NOT NULL DEFAULT ''",
    "bgm_volume_db": "INTEGER NOT NULL DEFAULT -20",
    "bgm_ducking_enabled": "INTEGER NOT NULL DEFAULT 1",
    "render_formats": "TEXT NOT NULL DEFAULT '[\"landscape\"]'",
    "youtube_schedule_at": "TEXT NOT NULL DEFAULT ''",
}


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
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


@contextmanager
def tx() -> Iterator[sqlite3.Connection]:
    connection = _connect()
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _row_to_project(row: sqlite3.Row) -> ProjectRecord:
    sentences = cast(list[str], json.loads(str(row["sentences"] or "[]")))
    media_order = cast(list[str], json.loads(str(row["media_order"] or "[]")))
    render_formats = cast(list[str], json.loads(str(row["render_formats"] or '["landscape"]')))
    subtitle_style_payload = json.loads(str(row["subtitle_style"] or "{}"))
    subtitle_style = normalize_subtitle_style(
        subtitle_style_payload if isinstance(subtitle_style_payload, dict) else {}
    )
    return {
        "id": str(row["id"]),
        "title": str(row["title"]),
        "script": str(row["script"]),
        "sentences": sentences,
        "media_order": media_order,
        "thumbnail_file": str(row["thumbnail_file"] or ""),
        "subtitle_style": subtitle_style,
        "voice_preset": str(row["voice_preset"]),
        "kenburns_enabled": bool(int(row["kenburns_enabled"])),
        "bgm_file": str(row["bgm_file"] or ""),
        "bgm_volume_db": int(row["bgm_volume_db"]),
        "bgm_ducking_enabled": bool(int(row["bgm_ducking_enabled"])),
        "render_formats": cast(list[RenderFormat], [fmt for fmt in render_formats if fmt in {"landscape", "shorts"}] or ["landscape"]),
        "youtube_schedule_at": str(row["youtube_schedule_at"] or ""),
        "tts_state": cast(TaskState, row["tts_state"]),
        "tts_progress": int(row["tts_progress"]),
        "render_state": cast(TaskState, row["render_state"]),
        "render_progress": int(row["render_progress"]),
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
    for key in ("sentences", "media_order", "subtitle_style", "render_formats"):
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
