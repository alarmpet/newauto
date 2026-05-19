import json
from typing import cast

from .. import db
from ..services.visual_planner import build_scene_visual_plan
from ..services.visual_relevance import mapping_matches_current_sentence
from ..types import ProjectRecord, Region, RenderFormat, ScenePlan, ScenePlanScene, TimingEntry, VisualPlanEntry


def _style_for_project(project: ProjectRecord) -> str:
    if project["content_mode"] == "bible_longform":
        return "reverent biblical illustration"
    if project["visual_source_mode"] == "comfyui_auto":
        return "image generation disabled"
    if project["visual_source_mode"] == "hybrid":
        return "mixed uploaded and generated documentary"
    return "uploaded visual sequence"


def _load_timings(project: ProjectRecord) -> list[TimingEntry]:
    timings_path = db.project_dir(project["id"]) / "tts" / "timings.json"
    if not timings_path.exists():
        return []
    try:
        payload = json.loads(timings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, list):
        return []
    timings: list[TimingEntry] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        idx = item.get("idx")
        text = item.get("text")
        start = item.get("start")
        end = item.get("end")
        dur = item.get("dur")
        region = item.get("region")
        if (
            isinstance(idx, int)
            and isinstance(text, str)
            and isinstance(start, (int, float))
            and isinstance(end, (int, float))
            and isinstance(dur, (int, float))
        ):
            timing: TimingEntry = {
                "idx": idx,
                "text": text,
                "start": float(start),
                "end": float(end),
                "dur": float(dur),
            }
            if region in {"intro", "body", "bible"}:
                timing["region"] = region
            timings.append(timing)
    return timings


def _scene_duration_from_timing(
    timing: TimingEntry | None,
    next_timing: TimingEntry | None,
    sentence: str,
) -> float:
    if timing is None:
        return max(2.0, min(8.0, len(sentence) / 12))
    if next_timing is not None and next_timing["start"] > timing["start"]:
        return max(0.2, float(next_timing["start"] - timing["start"]))
    return max(0.2, float(timing["end"] - timing["start"]))


def _has_complete_current_mappings(project: ProjectRecord) -> bool:
    mappings_by_idx = {item["sentence_idx"]: item for item in project["body_image_mappings"]}
    return bool(project["sentences"]) and all(
        (mapping := mappings_by_idx.get(sentence_idx)) is not None
        and mapping_matches_current_sentence(project, mapping)
        and bool(mapping["path"].strip())
        for sentence_idx in range(len(project["sentences"]))
    )


def build_scene_plan(project: ProjectRecord, *, render_format: RenderFormat = "landscape") -> ScenePlan:
    timings = _load_timings(project)
    timings_by_idx = {item["idx"]: item for item in timings}
    mappings_by_idx = {item["sentence_idx"]: item for item in project["body_image_mappings"]}
    skip_visual_planner = _has_complete_current_mappings(project)
    visual_plan_by_idx: dict[int, VisualPlanEntry] = {}
    if not skip_visual_planner:
        visual_plan_by_idx = {
            item["sentence_idx"]: item for item in build_scene_visual_plan(project)
        }
    style = _style_for_project(project)
    scenes: list[ScenePlanScene] = []
    total_duration = 0.0
    regional_sentences = project["regional_sentences"]

    for sentence_idx, sentence in enumerate(project["sentences"]):
        timing = timings_by_idx.get(sentence_idx)
        next_timing = timings_by_idx.get(sentence_idx + 1)
        region = "body"
        if sentence_idx < len(regional_sentences):
            region = regional_sentences[sentence_idx]["region"]
        visual_plan_entry = visual_plan_by_idx.get(sentence_idx)
        prompt = ""
        media_path = ""
        mapping = mappings_by_idx.get(sentence_idx)
        if mapping is not None and mapping_matches_current_sentence(project, mapping):
            prompt = mapping["prompt"]
            media_path = mapping["path"]
        elif project["visual_source_mode"] == "upload_only" and sentence_idx < len(project["media_order"]):
            media_path = project["media_order"][sentence_idx]
            prompt = (
                visual_plan_entry["core_meaning"]
                if visual_plan_entry is not None and visual_plan_entry["core_meaning"].strip()
                else sentence
            )
        else:
            prompt = (
                visual_plan_entry["core_meaning"]
                if visual_plan_entry is not None and visual_plan_entry["core_meaning"].strip()
                else sentence
            )
        duration_sec = _scene_duration_from_timing(timing, next_timing, sentence)
        visual_brief = None
        primary_prop = ""
        secondary_prop = ""
        scene_background = ""
        visual_metaphor = ""
        subject = ""
        avoid: list[str] = []
        if isinstance(visual_brief, dict):
            primary_prop = str(visual_brief.get("primary_prop", "")).strip()
            secondary_prop = str(visual_brief.get("secondary_prop", "")).strip()
            scene_background = str(visual_brief.get("scene", "")).strip()
            visual_metaphor = str(visual_brief.get("mode", "")).strip()
            subject = str(visual_brief.get("main_subject", "")).strip()
            raw_avoid = visual_brief.get("avoid")
            if isinstance(raw_avoid, list):
                avoid = [item for item in raw_avoid if isinstance(item, str) and item.strip()]
        props = [item for item in (primary_prop, secondary_prop) if item]
        scene: ScenePlanScene = {
            "idx": len(scenes) + 1,
            "sentence_idx": sentence_idx,
            "text": sentence,
            "region": cast(Region, region),
            "duration_sec": duration_sec,
            "visual_intent": (
                visual_plan_entry["core_meaning"]
                if visual_plan_entry is not None and visual_plan_entry["core_meaning"].strip()
                else sentence
            ),
            "prompt": prompt,
            "style": style,
            "media_path": media_path,
        }
        if project["visual_source_mode"] == "upload_only":
            scene["visual_source_mode"] = "upload_only"
            scene["uploaded_media_index"] = sentence_idx if sentence_idx < len(project["media_order"]) else -1
        if primary_prop:
            scene["key_concept"] = primary_prop
        elif visual_plan_entry is not None and visual_plan_entry["primary_keywords"]:
            scene["key_concept"] = visual_plan_entry["primary_keywords"][0]
        if visual_metaphor:
            scene["visual_metaphor"] = visual_metaphor
        if subject:
            scene["subject"] = subject
        elif visual_plan_entry is not None:
            scene["subject"] = visual_plan_entry.get("hero_subject") or (
                visual_plan_entry["primary_keywords"][0] if visual_plan_entry["primary_keywords"] else sentence
            )
        if props:
            scene["props"] = props
        elif visual_plan_entry is not None and visual_plan_entry["must_show"]:
            scene["props"] = list(visual_plan_entry["must_show"][:2])
        if scene_background:
            scene["background"] = scene_background
        if avoid:
            scene["avoid"] = avoid
        if visual_plan_entry is not None:
            scene["core_meaning"] = visual_plan_entry["core_meaning"]
            if visual_plan_entry["primary_keywords"]:
                scene["primary_keywords"] = list(visual_plan_entry["primary_keywords"])
            if visual_plan_entry["secondary_keywords"]:
                scene["secondary_keywords"] = list(visual_plan_entry["secondary_keywords"])
            if visual_plan_entry["subject_modes"]:
                scene["subject_modes"] = list(visual_plan_entry["subject_modes"])
            if visual_plan_entry["must_show"]:
                scene["must_show"] = list(visual_plan_entry["must_show"])
            if visual_plan_entry["may_show"]:
                scene["may_show"] = list(visual_plan_entry["may_show"])
            if visual_plan_entry["prompt_hint"].strip():
                scene["prompt_hint"] = visual_plan_entry["prompt_hint"]
            if visual_plan_entry["vocab_refs"]:
                scene["vocab_refs"] = list(visual_plan_entry["vocab_refs"])
            if visual_plan_entry["domain"].strip():
                scene["domain"] = visual_plan_entry["domain"]
        scenes.append(scene)
        total_duration += duration_sec

    return {
        "version": 2,
        "format": render_format,
        "total_duration": total_duration,
        "scenes": scenes,
    }
