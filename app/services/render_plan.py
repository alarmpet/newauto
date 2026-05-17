import json

from .. import db
from ..types import ProjectRecord, RenderPlan, RenderPlanSegment, RenderPlanSegmentMedia, TimingEntry


_MICRO_MOTION_DOMAINS = {"agriculture_environment", "science_materials"}


def _default_motion(region: str, duration_sec: float, *, lock_still: bool = False) -> str:
    if lock_still:
        return "still_locked"
    if duration_sec <= 2.5:
        return "none"
    if region == "intro":
        return "slow_zoom_in"
    if region == "bible":
        return "slow_zoom_out"
    return "slow_zoom_in"


def _default_effect(region: str, duration_sec: float) -> str:
    if duration_sec <= 2.0:
        return "none"
    if region == "intro":
        return "fade"
    return "none"


def _default_caption_style(region: str) -> str:
    if region == "intro":
        return "emphasis"
    if region == "bible":
        return "quote"
    return "plain"


def _prefers_micro_motion(scene: object) -> bool:
    if not isinstance(scene, dict):
        return False
    domain = str(scene.get("domain") or "").strip()
    if domain not in _MICRO_MOTION_DOMAINS:
        return False
    style = str(scene.get("style") or "").lower()
    prompt = str(scene.get("prompt") or "").lower()
    dense_diagram_markers = (
        "simple_diagram",
        "diagram",
        "infographic",
        "flowchart",
        "map",
        "blueprint",
        "text panel",
    )
    return not any(marker in style or marker in prompt for marker in dense_diagram_markers)


def _motion_for_scene(scene: object, media_path: str) -> str:
    if isinstance(scene, dict):
        duration_sec = float(scene.get("duration_sec") or 0.0)
        if media_path and duration_sec > 2.5 and _prefers_micro_motion(scene):
            return "micro_motion_locked"
        region = str(scene.get("region") or "body")
        return _default_motion(region, duration_sec, lock_still=bool(media_path))
    return "still_locked" if media_path else "none"


def _load_timing_total_duration(project: ProjectRecord) -> float:
    timings_path = db.project_dir(project["id"]) / "tts" / "timings.json"
    if not timings_path.exists():
        return 0.0
    try:
        payload = json.loads(timings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0.0
    if not isinstance(payload, list):
        return 0.0
    timings: list[TimingEntry] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        end = item.get("end")
        if isinstance(end, (int, float)):
            timings.append({"idx": 0, "text": "", "start": 0.0, "end": float(end), "dur": 0.0})
    return max((item["end"] for item in timings), default=0.0)


def _fallback_total_duration(project: ProjectRecord, media_count: int) -> float:
    timing_duration = _load_timing_total_duration(project)
    if timing_duration > 0:
        return timing_duration
    if project["sentences"]:
        return sum(max(2.0, min(8.0, len(sentence) / 12)) for sentence in project["sentences"])
    return max(2.0, media_count * 3.0)


def build_render_plan(project: ProjectRecord) -> RenderPlan:
    scene_plan = project["scene_plan"]
    if scene_plan and scene_plan["scenes"]:
        segments: list[RenderPlanSegment] = []
        cursor = 0.0
        media_counts: dict[str, int] = {}
        for scene in scene_plan["scenes"]:
            media_path = scene["media_path"]
            if media_path:
                media_counts[media_path] = media_counts.get(media_path, 0) + 1
        unique_media_count = len(media_counts)
        for scene in scene_plan["scenes"]:
            media: list[RenderPlanSegmentMedia] = []
            media_path = scene["media_path"]
            if media_path:
                media.append({"path": media_path, "kind": "image"})
            render_segment: RenderPlanSegment = {
                "region": scene["region"],
                "start": cursor,
                "end": cursor + scene["duration_sec"],
                "media": media,
                "sentence_idx": scene["sentence_idx"],
                "motion": _motion_for_scene(scene, media_path),
                "effect": _default_effect(scene["region"], scene["duration_sec"]),
                "caption_style": _default_caption_style(scene["region"]),
            }
            segments.append(render_segment)
            cursor += scene["duration_sec"]
        return {
            "version": 2,
            "total_duration": cursor,
            "segments": segments,
        }

    media = [
        {"path": path, "kind": "video" if path.lower().endswith((".mp4", ".mov", ".webm")) else "image"}
        for path in project["media_order"]
    ]
    total_duration = _fallback_total_duration(project, len(media))
    per_item_duration = total_duration / len(media) if media else total_duration
    fallback_segments: list[RenderPlanSegment] = []
    cursor = 0.0
    for media_item in media:
        end = cursor + per_item_duration
        fallback_segments.append(
            {
                "region": "body",
                "start": cursor,
                "end": end,
                "media": [media_item],
                "motion": "still_locked"
                if len(media) == 1
                else ("slow_zoom_in" if project["kenburns_enabled"] else "none"),
                "effect": "none",
                "caption_style": "plain",
            }
        )
        cursor = end
    return {
        "version": 1,
        "total_duration": total_duration,
        "segments": fallback_segments,
    }
