from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import db
from app.services.operator_summary import build_operator_summary
from scripts import flow_browser_automation

STATUS_FILENAME = "flow_generate_all_status.json"
RUN_LOG_FILENAME = "flow_run_log.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _status_path(project_id: str) -> Path:
    return db.project_dir(project_id) / STATUS_FILENAME


def _run_log_path(project_id: str) -> Path:
    return db.project_dir(project_id) / RUN_LOG_FILENAME


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _project_coverage(project: dict[str, Any]) -> dict[str, object]:
    sentences = project.get("sentences")
    mappings = project.get("body_image_mappings")
    total = len(sentences) if isinstance(sentences, list) else 0
    mapped: set[int] = set()
    if isinstance(mappings, list):
        for mapping in mappings:
            if not isinstance(mapping, dict):
                continue
            try:
                idx = int(mapping.get("sentence_idx"))
            except (TypeError, ValueError):
                continue
            if 0 <= idx < total:
                mapped.add(idx)
    return {
        "attached": len(mapped),
        "total": total,
        "missing": [idx + 1 for idx in range(total) if idx not in mapped],
    }


def _flow_log_items(result: dict[str, Any]) -> list[dict[str, object]]:
    records = result.get("records")
    if not isinstance(records, list):
        return []
    items: list[dict[str, object]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        status = str(record.get("status") or "unknown")
        item: dict[str, object] = {
            "timestamp": _now(),
            "runner": "flow_playwright_direct",
            "surface_mode": "flow",
            "sentence_number": record.get("sentence_number"),
            "status": status,
            "attempt": record.get("attempt", 0),
            "path": record.get("path", ""),
            "attached": record.get("attached", []),
        }
        if status != "ok":
            item["failure_class"] = "flow_generation_failed"
            item["error"] = record.get("error", "")
            item["body_excerpt"] = record.get("body_excerpt", "")
        items.append(item)
    return items


def run(project_id: str, *, start_sentence_number: int, limit: int) -> int:
    db.init_db()
    project = db.get_project(project_id)
    if project is None:
        _write_json(
            _status_path(project_id),
            {
                "ok": False,
                "status": "error",
                "project_id": project_id,
                "error": "project_not_found",
                "updated_at": _now(),
            },
        )
        return 2

    status_path = _status_path(project_id)
    started_at = _now()
    db.update_project(
        project_id,
        body_image_state="running",
        body_image_progress=0,
        body_image_error="",
        body_image_phase="flow_generate_all",
        body_image_last_log="Flow generate-all worker started.",
        body_image_started_at=started_at,
        body_image_heartbeat_at=started_at,
    )
    _write_json(
        status_path,
        {
            "ok": None,
            "status": "running",
            "project_id": project_id,
            "pid": os.getpid(),
            "started_at": started_at,
            "updated_at": started_at,
            "start_sentence_number": start_sentence_number,
            "limit": limit,
            "coverage_before": _project_coverage(dict(project)),
        },
    )

    try:
        result = flow_browser_automation.fill_or_generate(
            project_id,
            start_sentence_number=start_sentence_number,
            limit=limit,
            click_generate=True,
        )
        refreshed = db.get_project(project_id)
        coverage_after = _project_coverage(dict(refreshed)) if refreshed is not None else {}
        ok = bool(result.get("ok") is True and not coverage_after.get("missing"))
        status = "done" if ok else "partial" if result.get("ok") is True else "error"
        flow_log = {
            "version": 1,
            "project_id": project_id,
            "runner": "flow_playwright_direct",
            "surface_mode": "flow",
            "started_at": started_at,
            "finished_at": _now(),
            "result": result,
            "items": _flow_log_items(result),
        }
        _write_json(_run_log_path(project_id), flow_log)
        db.update_project(
            project_id,
            body_image_state="done" if ok else "error",
            body_image_progress=100 if ok else int(100 * int(coverage_after.get("attached", 0)) / max(1, int(coverage_after.get("total", 1)))),
            body_image_error="" if ok else str(result.get("message") or "Flow generate-all did not complete every scene."),
            body_image_phase="flow_generate_all_done" if ok else "flow_generate_all_blocked",
            body_image_last_log=str(result.get("message") or f"Flow generate-all status: {status}"),
            body_image_heartbeat_at=_now(),
        )
        refreshed_after_update = db.get_project(project_id)
        operator_summary = build_operator_summary(refreshed_after_update) if refreshed_after_update is not None else None
        _write_json(
            status_path,
            {
                "ok": ok,
                "status": status,
                "project_id": project_id,
                "pid": os.getpid(),
                "started_at": started_at,
                "updated_at": _now(),
                "finished_at": _now(),
                "coverage_before": _project_coverage(dict(project)),
                "coverage_after": coverage_after,
                "result": result,
                "operator_summary": operator_summary,
            },
        )
        return 0 if ok else 1
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        db.update_project(
            project_id,
            body_image_state="error",
            body_image_error=error,
            body_image_phase="flow_generate_all_error",
            body_image_last_log=error,
            body_image_heartbeat_at=_now(),
        )
        refreshed = db.get_project(project_id)
        operator_summary = build_operator_summary(refreshed) if refreshed is not None else None
        _write_json(
            status_path,
            {
                "ok": False,
                "status": "error",
                "project_id": project_id,
                "pid": os.getpid(),
                "started_at": started_at,
                "updated_at": _now(),
                "finished_at": _now(),
                "error": error,
                "operator_summary": operator_summary,
            },
        )
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate all missing Flow assets for a project.")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--start-sentence-number", type=int, default=1)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    raise SystemExit(
        run(
            args.project_id,
            start_sentence_number=max(1, args.start_sentence_number),
            limit=max(0, args.limit),
        )
    )


if __name__ == "__main__":
    main()
