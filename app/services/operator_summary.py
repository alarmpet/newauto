import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from .. import db
from ..types import ProjectRecord
from .render_report import load_render_report


def operator_summary_path(pid: str) -> Path:
    return db.project_dir(pid) / "operator_summary.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mapped_sentence_indexes(project: ProjectRecord) -> set[int]:
    indexes: set[int] = set()
    for mapping in project["body_image_mappings"]:
        try:
            indexes.add(int(mapping["sentence_idx"]))
        except (KeyError, TypeError, ValueError):
            continue
    return indexes


def _asset_coverage(project: ProjectRecord, prompt_count: int) -> dict[str, object]:
    total = max(len(project["sentences"]), prompt_count)
    mapped = sorted(idx for idx in _mapped_sentence_indexes(project) if 0 <= idx < total)
    missing = [idx + 1 for idx in range(total) if idx not in mapped]
    attached = len(mapped)
    ratio = attached / total if total else 0.0
    return {
        "attached": attached,
        "total": total,
        "missing": missing,
        "ratio": round(ratio, 4),
    }


def _detect_outputs(pid: str, render_report: dict[str, Any] | None) -> list[dict[str, object]]:
    outputs: list[dict[str, object]] = []
    if render_report is not None:
        raw_outputs = render_report.get("outputs")
        if isinstance(raw_outputs, list):
            for item in raw_outputs:
                if isinstance(item, dict):
                    outputs.append(dict(item))
    if outputs:
        return outputs

    project_dir = db.project_dir(pid)
    for format_name, filename in (("shorts", "output_shorts.mp4"), ("landscape", "output.mp4")):
        path = project_dir / filename
        if path.exists():
            outputs.append(
                {
                    "format": format_name,
                    "path": filename,
                    "exists": True,
                    "size_bytes": path.stat().st_size,
                }
            )
    return outputs


def _load_flow_log(project: ProjectRecord) -> tuple[dict[str, int], int, str]:
    path = db.project_dir(project["id"]) / "flow_run_log.json"
    return {}, 0, str(path)


def _load_generate_all_status(project: ProjectRecord) -> dict[str, object]:
    return {"status": "disabled_d1", "path": str(db.project_dir(project["id"]) / "flow_generate_all_status.json")}


def _project_error(project: ProjectRecord) -> tuple[str, str]:
    error_fields = (("source_draft_error", "source_draft_error"), ("body_image_error", "flow_error"), ("tts_error", "tts_error"))
    for field, failure_class in error_fields:
        value = str(project.get(field, "") or "").strip()
        if value:
            return failure_class, value
    if project["render_state"] in {"error", "failed"}:
        value = str(project.get("render_last_log", "") or "").strip()
        if value:
            return "render_error", value
    return "", ""


def _stage_and_next(
    *,
    project: ProjectRecord,
    asset_coverage: dict[str, object],
    outputs: list[dict[str, object]],
    render_report: dict[str, Any] | None,
    failure_class: str,
) -> tuple[str, str, bool, str, str]:
    total = int(cast(int | float | str, asset_coverage["total"]))
    attached = int(cast(int | float | str, asset_coverage["attached"]))
    render_done = project["render_state"] == "done" or any(bool(item.get("exists")) for item in outputs)
    report_done = render_report is not None and str(render_report.get("status") or "") == "done"
    if render_done or report_done:
        return "complete", "none", False, "", "no_action_needed"
    if failure_class:
        return "blocked", "ask_openrouter_subagent", True, failure_class, "classify_failure_and_repair"
    if project["render_state"] in {"queued", "running"}:
        return "render", "continue_video_workflow", False, "", "wait_or_continue_render_worker"
    if project["tts_state"] in {"queued", "running"}:
        return "tts", "continue_video_workflow", False, "", "wait_or_continue_tts_worker"
    if project["source_draft_state"] in {"queued", "running"}:
        return "source_draft", "continue_video_workflow", False, "", "wait_or_continue_source_draft_worker"
    if not project["sentences"]:
        return "script", "continue_video_workflow", False, "", "generate_or_compile_script"
    if total > 0 and attached < total:
        return "flow", "continue_video_workflow", False, "", "generate_missing_flow_images"
    if project["tts_state"] != "done":
        return "tts", "continue_video_workflow", False, "", "start_or_continue_tts"
    if project["render_state"] != "done":
        return "render", "continue_video_workflow", False, "", "start_or_continue_render"
    return "unknown", "diagnose_runtime", False, "", "refresh_summary"


def build_operator_summary(project: ProjectRecord) -> dict[str, object]:
    prompt_count = len(project["sentences"])
    coverage = _asset_coverage(project, prompt_count)
    render_report = load_render_report(project["id"])
    render_report_dict = cast(dict[str, Any] | None, render_report)
    outputs = _detect_outputs(project["id"], render_report_dict)
    flow_failure_counts, placeholder_count, flow_log_path = _load_flow_log(project)
    generate_all_status = _load_generate_all_status(project)
    failure_class, error_detail = _project_error(project)
    if not failure_class and flow_failure_counts:
        failure_class = next(iter(flow_failure_counts))
        error_detail = failure_class

    current_stage, recommended_next_tool, human_required, human_reason, next_action = _stage_and_next(
        project=project,
        asset_coverage=coverage,
        outputs=outputs,
        render_report=render_report_dict,
        failure_class=failure_class,
    )
    path = operator_summary_path(project["id"])
    summary: dict[str, object] = {
        "version": 1,
        "generated_at": _now(),
        "project_id": project["id"],
        "title": project["title"],
        "current_stage": current_stage,
        "source_draft_state": project["source_draft_state"],
        "source_draft_progress": project["source_draft_progress"],
        "source_draft_phase": project["source_draft_phase"],
        "source_draft_error": project["source_draft_error"],
        "script_sentence_count": len(project["sentences"]),
        "flow_prompt_count": prompt_count,
        "generated_image_count": int(cast(int | float | str, coverage["attached"])),
        "placeholder_image_count": placeholder_count,
        "asset_coverage": coverage,
        "flow_failure_class_counts": flow_failure_counts,
        "flow_log_path": flow_log_path,
        "flow_generate_all_status": generate_all_status,
        "tts_state": project["tts_state"],
        "tts_progress": project["tts_progress"],
        "tts_error": project["tts_error"],
        "render_state": project["render_state"],
        "render_progress": project["render_progress"],
        "render_phase": project["render_phase"],
        "render_error": project["render_last_log"],
        "render_report_exists": render_report is not None,
        "outputs": outputs,
        "failure_class": failure_class,
        "error_detail": error_detail,
        "recommended_next_tool": recommended_next_tool,
        "human_intervention_required": human_required,
        "human_intervention_reason": human_reason,
        "next_autonomous_action": next_action,
        "operator_summary_path": str(path),
    }
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def load_operator_summary(pid: str) -> dict[str, object] | None:
    path = operator_summary_path(pid)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None
