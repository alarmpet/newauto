from __future__ import annotations

import json

from .. import db


def load_character_descriptor(project_id: str) -> dict[str, object] | None:
    project_dir = db.project_dir(project_id)
    for filename in ("character_descriptor.json", "character_sheet.json"):
        path = project_dir / filename
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None
    return None
