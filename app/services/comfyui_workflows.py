import json
import re
from pathlib import Path

from fastapi import HTTPException

from ..config import COMFYUI_WORKFLOW_DIR

PlaceholderMap = dict[str, str | int | float | bool]
WorkflowPayload = dict[str, object]
_PLACEHOLDER_PATTERN = re.compile(r"__[A-Z0-9_]+__")


def _template_path(template_id: str, base_dir: Path = COMFYUI_WORKFLOW_DIR) -> Path:
    normalized = template_id.strip()
    if not normalized:
        raise HTTPException(400, "ComfyUI workflow template id is required.")
    return base_dir / f"{normalized}.json"


def load_workflow_template(template_id: str, base_dir: Path = COMFYUI_WORKFLOW_DIR) -> WorkflowPayload:
    path = _template_path(template_id, base_dir)
    if not path.exists():
        raise HTTPException(404, f"ComfyUI workflow template not found: {template_id}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(500, f"ComfyUI workflow template is invalid: {template_id}") from exc
    if not isinstance(payload, dict):
        raise HTTPException(500, f"ComfyUI workflow template root must be an object: {template_id}")
    return payload


def _replace_string(value: str, placeholders: PlaceholderMap) -> str | int | float | bool:
    if value in placeholders:
        return placeholders[value]
    replaced = value
    for key, replacement in placeholders.items():
        replaced = replaced.replace(key, str(replacement))
    return replaced


def _inject_placeholders(value: object, placeholders: PlaceholderMap) -> object:
    if isinstance(value, dict):
        return {str(key): _inject_placeholders(item, placeholders) for key, item in value.items()}
    if isinstance(value, list):
        return [_inject_placeholders(item, placeholders) for item in value]
    if isinstance(value, str):
        return _replace_string(value, placeholders)
    return value


def _find_unresolved_placeholders(value: object) -> set[str]:
    if isinstance(value, dict):
        unresolved: set[str] = set()
        for item in value.values():
            unresolved.update(_find_unresolved_placeholders(item))
        return unresolved
    if isinstance(value, list):
        unresolved = set()
        for item in value:
            unresolved.update(_find_unresolved_placeholders(item))
        return unresolved
    if isinstance(value, str):
        return set(_PLACEHOLDER_PATTERN.findall(value))
    return set()


def render_workflow_template(
    template_id: str,
    placeholders: PlaceholderMap,
    base_dir: Path = COMFYUI_WORKFLOW_DIR,
) -> WorkflowPayload:
    workflow = load_workflow_template(template_id, base_dir)
    rendered = _inject_placeholders(workflow, placeholders)
    if not isinstance(rendered, dict):
        raise HTTPException(500, f"Rendered ComfyUI workflow must be an object: {template_id}")
    unresolved = sorted(_find_unresolved_placeholders(rendered))
    if unresolved:
        joined = ", ".join(unresolved[:10])
        suffix = "" if len(unresolved) <= 10 else f" and {len(unresolved) - 10} more"
        raise HTTPException(500, f"Rendered ComfyUI workflow has unresolved placeholders: {joined}{suffix}")
    return rendered
