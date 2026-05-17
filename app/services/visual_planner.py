from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .. import db
from ..types import ProjectRecord, VisualPlanEntry


def _cache_path(project: ProjectRecord) -> Path:
    return db.project_dir(project["id"]) / "scene_visual_plan.json"


def _keywords(text: str, *, limit: int = 4) -> list[str]:
    tokens: list[str] = []
    for raw in text.replace(",", " ").replace(".", " ").split():
        token = raw.strip()
        if len(token) < 2:
            continue
        if token in tokens:
            continue
        tokens.append(token)
        if len(tokens) >= limit:
            break
    return tokens


def _entry(project: ProjectRecord, sentence_idx: int, sentence: str) -> VisualPlanEntry:
    keywords = _keywords(sentence)
    return {
        "sentence_idx": sentence_idx,
        "sentence": sentence,
        "core_meaning": sentence,
        "primary_keywords": keywords[:2],
        "secondary_keywords": keywords[2:],
        "visual_metaphor": "",
        "subject_modes": ["environment"],
        "must_show": keywords[:3],
        "may_show": [],
        "avoid": [],
        "prompt_hint": "",
        "vocab_refs": [],
        "domain": "disabled_image_generation",
        "source": "d1_disabled_scaffold",
        "visual_priority": "core_metaphor",
        "composition_template": "",
        "scene_anchor": "",
        "hero_subject": keywords[0] if keywords else "",
        "symbolic_marker": "",
        "visual_mode": "simple_explainer",
        "semantic_anchor_type": "generic",
        "semantic_anchor_tokens": keywords,
    }


def build_scene_visual_plan(project: ProjectRecord) -> list[VisualPlanEntry]:
    entries = [_entry(project, idx, sentence) for idx, sentence in enumerate(project["sentences"])]
    payload = {
        "project_id": project["id"],
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "d1_disabled_scaffold",
        "entries": entries,
    }
    _cache_path(project).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return entries
