import shutil
import time
from typing import cast

from .. import db
from ..config import CLIENT_SECRET_PATH, LLM_PROVIDER, LMSTUDIO_BASE_URL, OLLAMA_BASE_URL, PROJECTS_DIR, SCRIPT_LLM_MODEL
from ..types import (
    AutopilotState,
    AutopilotRunSummary,
    ModelStatus,
    OperatorAutopilotMetrics,
    OperatorQueueStatus,
    OperatorStatus,
    SystemHealth,
    ToolStatus,
    UsageRecord,
)
from .gpu_guard import get_status as get_gpu_status
from .hyperframes_probe import probe_hyperframes_runtime
from .lmstudio_runtime import loaded_lmstudio_models
from .model_registry import list_model_status
from .python_runtime import get_omnivoice_runtime_status
from .render_report import summarize_recent_render_reports
from .tool_registry import list_tool_status
from .usage_registry import list_usage_records

OMNIVOICE_RUNTIME_CACHE_TTL_SEC = 600.0
_omnivoice_runtime_cache: tuple[float, dict[str, object]] | None = None


def _empty_omnivoice_status(error: str) -> dict[str, object]:
    return {
        "resolved": False,
        "python_path": "",
        "omnivoice_import_ok": False,
        "torch_import_ok": False,
        "cuda_available": False,
        "error": error,
    }


def _get_omnivoice_status(*, refresh_runtime: bool = False) -> dict[str, object]:
    global _omnivoice_runtime_cache
    now = time.monotonic()
    if _omnivoice_runtime_cache is not None:
        cached_at, cached_status = _omnivoice_runtime_cache
        if not refresh_runtime and now - cached_at <= OMNIVOICE_RUNTIME_CACHE_TTL_SEC:
            return dict(cached_status)
    if not refresh_runtime:
        return _empty_omnivoice_status("runtime probe not cached; run /api/system/diagnostics for a full probe")
    status = dict(get_omnivoice_runtime_status())
    _omnivoice_runtime_cache = (now, status)
    return dict(status)


def get_system_health(*, refresh_runtime: bool = False) -> SystemHealth:
    usage = shutil.disk_usage(PROJECTS_DIR)
    omnivoice_status = _get_omnivoice_status(refresh_runtime=refresh_runtime)
    hyperframes_status = probe_hyperframes_runtime(refresh=refresh_runtime)
    lmstudio_models = loaded_lmstudio_models() if LLM_PROVIDER == "lmstudio" else []
    llm_base_url = LMSTUDIO_BASE_URL if LLM_PROVIDER == "lmstudio" else OLLAMA_BASE_URL
    return {
        "ffmpeg_available": shutil.which("ffmpeg") is not None,
        "oauth_ready": CLIENT_SECRET_PATH.exists(),
        "llm_provider": LLM_PROVIDER,
        "llm_model": SCRIPT_LLM_MODEL,
        "llm_base_url": llm_base_url,
        "llm_ready": SCRIPT_LLM_MODEL in lmstudio_models if LLM_PROVIDER == "lmstudio" else bool(SCRIPT_LLM_MODEL.strip()),
        "lmstudio_loaded_models": lmstudio_models,
        "omnivoice_python_found": bool(omnivoice_status["resolved"]),
        "omnivoice_python_path": str(omnivoice_status["python_path"]),
        "omnivoice_import_ok": bool(omnivoice_status["omnivoice_import_ok"]),
        "omnivoice_torch_ok": bool(omnivoice_status["torch_import_ok"]),
        "omnivoice_cuda_available": bool(omnivoice_status["cuda_available"]),
        "hyperframes_node_available": bool(hyperframes_status["node_available"]),
        "hyperframes_node_version": str(hyperframes_status["node_version"]),
        "hyperframes_npx_available": bool(hyperframes_status["npx_available"]),
        "hyperframes_npx_version": str(hyperframes_status["npx_version"]),
        "hyperframes_doctor_ok": bool(hyperframes_status["doctor_ok"]),
        "hyperframes_doctor_detail": str(hyperframes_status["doctor_detail"]),
        "hyperframes_ffmpeg_alpha_ok": bool(hyperframes_status["ffmpeg_alpha_ok"]),
        "disk_free_gb": round(usage.free / (1024 ** 3), 2),
        "storage_path": str(PROJECTS_DIR),
    }


def get_system_tools() -> list[ToolStatus]:
    return list_tool_status()


def get_system_models() -> list[ModelStatus]:
    return list_model_status()


def _get_queue_status() -> OperatorQueueStatus:
    with db.tx() as connection:
        row = connection.execute(
            """
            SELECT
                SUM(CASE WHEN source_draft_state='queued' THEN 1 ELSE 0 END) AS source_draft_queued,
                SUM(CASE WHEN source_draft_state='running' THEN 1 ELSE 0 END) AS source_draft_running,
                SUM(CASE WHEN autopilot_state='queued' THEN 1 ELSE 0 END) AS autopilot_queued,
                SUM(CASE WHEN autopilot_state='running' THEN 1 ELSE 0 END) AS autopilot_running,
                SUM(CASE WHEN autopilot_state='paused' THEN 1 ELSE 0 END) AS autopilot_paused,
                SUM(CASE WHEN render_state='queued' THEN 1 ELSE 0 END) AS render_queued,
                SUM(CASE WHEN render_state='running' THEN 1 ELSE 0 END) AS render_running,
                SUM(CASE WHEN tts_state='queued' THEN 1 ELSE 0 END) AS tts_queued,
                SUM(CASE WHEN tts_state='running' THEN 1 ELSE 0 END) AS tts_running
            FROM projects
            """
        ).fetchone()
    return {
        "source_draft_queued": int(row["source_draft_queued"] or 0),
        "source_draft_running": int(row["source_draft_running"] or 0),
        "autopilot_queued": int(row["autopilot_queued"] or 0),
        "autopilot_running": int(row["autopilot_running"] or 0),
        "autopilot_paused": int(row["autopilot_paused"] or 0),
        "render_queued": int(row["render_queued"] or 0),
        "render_running": int(row["render_running"] or 0),
        "tts_queued": int(row["tts_queued"] or 0),
        "tts_running": int(row["tts_running"] or 0),
    }


def _get_autopilot_metrics(limit: int = 20) -> OperatorAutopilotMetrics:
    with db.tx() as connection:
        rows = connection.execute(
            """
            SELECT autopilot_state
            FROM projects
            WHERE autopilot_started_at <> '' OR autopilot_state <> 'idle'
            ORDER BY
                CASE WHEN autopilot_started_at = '' THEN updated_at ELSE autopilot_started_at END DESC,
                updated_at DESC
            LIMIT ?
            """,
            (max(1, limit),),
        ).fetchall()
    states = [str(row["autopilot_state"] or "") for row in rows]
    return {
        "total": len(states),
        "done": sum(1 for state in states if state == "done"),
        "paused": sum(1 for state in states if state == "paused"),
        "error": sum(1 for state in states if state == "error"),
        "running": sum(1 for state in states if state == "running"),
        "queued": sum(1 for state in states if state == "queued"),
    }


def _get_recent_autopilot_runs(limit: int = 5) -> list[AutopilotRunSummary]:
    with db.tx() as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                title,
                autopilot_state,
                autopilot_phase,
                autopilot_progress,
                updated_at,
                autopilot_started_at,
                autopilot_job_id,
                autopilot_last_error_code
            FROM projects
            WHERE autopilot_started_at <> '' OR autopilot_state <> 'idle'
            ORDER BY
                CASE WHEN autopilot_started_at = '' THEN updated_at ELSE autopilot_started_at END DESC,
                updated_at DESC
            LIMIT ?
            """,
            (max(1, limit),),
        ).fetchall()
    return [
        {
            "project_id": str(row["id"]),
            "title": str(row["title"] or ""),
            "state": cast(AutopilotState, str(row["autopilot_state"] or "idle")),
            "phase": str(row["autopilot_phase"] or ""),
            "progress": int(row["autopilot_progress"] or 0),
            "updated_at": str(row["updated_at"] or ""),
            "started_at": str(row["autopilot_started_at"] or ""),
            "job_id": str(row["autopilot_job_id"] or ""),
            "last_error_code": str(row["autopilot_last_error_code"] or ""),
        }
        for row in rows
    ]


def get_system_usage() -> list[UsageRecord]:
    return list_usage_records()


def get_operator_status() -> OperatorStatus:
    return {
        "health": get_system_health(),
        "tools": get_system_tools(),
        "models": get_system_models(),
        "usage": get_system_usage(),
        "gpu": get_gpu_status(),
        "queue": _get_queue_status(),
        "render_metrics": summarize_recent_render_reports(),
        "autopilot_metrics": _get_autopilot_metrics(),
        "recent_autopilot_runs": _get_recent_autopilot_runs(),
    }
