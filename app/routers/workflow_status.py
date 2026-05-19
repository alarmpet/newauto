from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import db

router = APIRouter(prefix="/api/projects", tags=["workflow-status"])

PRIMARY_ACTIONS = {
    "script": "save script",
    "prepare_input": "review input",
    "script_compile": "compile script",
    "visual": "review prompts",
    "visual_plan": "rebuild prompts",
    "image": "regenerate failed image",
    "tts": "retry full passage",
    "render_plan": "rebuild render plan",
    "preflight": "run preflight",
    "render": "resume autopilot",
}


def _stage_cards(manifest: dict[str, object]) -> list[dict[str, object]]:
    raw_status = manifest.get("stage_status")
    stage_status = raw_status if isinstance(raw_status, dict) else {}
    cards: list[dict[str, object]] = []
    for stage, raw in stage_status.items():
        status = raw if isinstance(raw, dict) else {}
        error_code = str(status.get("error_code") or "")
        cards.append(
            {
                "stage": stage,
                "state": str(status.get("state") or "idle"),
                "issues": [error_code] if error_code else [],
                "primary_action": PRIMARY_ACTIONS.get(str(stage), "review"),
            }
        )
    return cards


@router.get("/{pid}/workflow-status")
def workflow_status(pid: str) -> dict[str, object]:
    project = db.get_project(pid)
    if project is None:
        raise HTTPException(404, f"project {pid} not found")
    manifest = dict(project["pipeline_manifest"])
    return {
        "project_id": pid,
        "pipeline_manifest": manifest,
        "stage_cards": _stage_cards(manifest),
    }
