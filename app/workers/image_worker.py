import threading
import time
from contextlib import suppress
from pathlib import Path
from typing import cast

from .. import db
from ..config import STORAGE_DIR
from ..services import gpu_guard
from ..services.comfyui_client import ComfyUIClient
from ..services.comfyui_pipeline import import_history_image, submit_template
from ..services.comfyui_prompt_adapter import build_prompt_placeholders
from ..services.comfyui_workflows import PlaceholderMap
from ..services.image_prompting import suggest_image_prompt
from ..services.parse_utils import to_int
from ..services.prompt_repair import repair_prompts
from ..services.render_plan import build_render_plan
from ..services.scene_plan import build_scene_plan
from ..services.visual_relevance import write_visual_contact_sheet, write_visual_mismatch_report
from ..types import ProjectRecord, PromptRepairDecision, RenderFormat, VisualBrief, VisualBriefMode, VisualPlanEntry, VisualSceneMode
from .worker_lock import single_instance_lock

POLL_INTERVAL_SEC = 3.0
HEARTBEAT_INTERVAL_SEC = 10.0
HISTORY_POLL_SEC = 2.0
HISTORY_TIMEOUT_SEC = 900.0
WORKER_LOCK_PATH = STORAGE_DIR / "locks" / "image_worker.lock"
MAX_PLAN_RETRIES = 1
MAX_FALLBACK_DOWNGRADES = 1
_BLOCKING_PROMPT_QUALITY_CODES = {
    "EV_BATTERY_CORE_VISUAL_MISSING",
    "EV_BATTERY_STICKFIGURE_STYLE_BLOCKED",
    "GENERIC_FALLBACK_IN_MUST_SHOW",
    "GENERIC_FALLBACK_IN_PROMPT",
}
_ANCHOR_MODE_SEQUENCE: dict[str, tuple[VisualSceneMode, ...]] = {
    "technical_barrier": ("symbolic_concept", "data_diagram", "editorial_scene"),
    "institutional_decision": ("editorial_scene", "data_diagram", "symbolic_concept"),
    "investment_signal": ("editorial_scene", "simple_explainer", "symbolic_concept"),
    "market_structure": ("data_diagram", "symbolic_concept", "editorial_scene"),
    "comparison_frame": ("simple_explainer", "data_diagram", "symbolic_concept"),
    "future_outlook": ("symbolic_concept", "simple_explainer", "editorial_scene"),
    "generic": ("symbolic_concept", "editorial_scene", "simple_explainer", "data_diagram"),
}
_SAFE_FALLBACK_MODE_BY_ANCHOR: dict[str, VisualSceneMode] = {
    "technical_barrier": "symbolic_concept",
    "institutional_decision": "editorial_scene",
    "investment_signal": "editorial_scene",
    "market_structure": "data_diagram",
    "comparison_frame": "simple_explainer",
    "future_outlook": "simple_explainer",
    "generic": "simple_explainer",
}


def _as_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _review_issue_codes(review: dict[str, object]) -> list[object]:
    raw = review.get("vision_qa_issue_codes")
    return list(raw) if isinstance(raw, list) else []


def _blocking_prompt_quality_codes(item: dict[str, object]) -> list[str]:
    keyword_coverage = item.get("keyword_coverage")
    if not isinstance(keyword_coverage, dict):
        return []
    issue_codes = keyword_coverage.get("issue_codes")
    if not isinstance(issue_codes, list):
        return []
    blocking_codes = [
        str(code)
        for code in issue_codes
        if isinstance(code, str) and code in _BLOCKING_PROMPT_QUALITY_CODES
    ]
    visual_brief = item.get("visual_brief")
    domain = str(visual_brief.get("domain") or "").strip().lower() if isinstance(visual_brief, dict) else ""
    if domain in {"ev_battery", "food_trend", "news_explainer", "ai_policy_conflict"} and keyword_coverage.get("passed") is False:
        blocking_codes.append("STRICT_PROMPT_COVERAGE_FAILED")
    return list(dict.fromkeys(blocking_codes))


def _progress(value: int) -> int:
    return max(0, min(100, value))


def _preferred_render_format(project: ProjectRecord) -> RenderFormat:
    for render_format in project["render_formats"]:
        if render_format in {"landscape", "shorts"}:
            return render_format
    return "landscape"


def _is_heavy_retry_item(item: dict[str, object]) -> bool:
    visual_brief = item.get("visual_brief")
    if isinstance(visual_brief, dict) and str(visual_brief.get("domain") or "").strip().lower() == "ev_battery":
        return False
    if str(item.get("control_image") or "").strip():
        return True
    if str(item.get("style_reference_image") or "").strip():
        return True
    return bool(str(item.get("lora_name") or "").strip())


def _is_manual_art_directed_item(project: ProjectRecord, item: dict[str, object]) -> bool:
    if _as_bool(project["body_image_options"].get("manual_art_directed"), False):
        return True
    if _as_bool(item.get("manual_art_directed"), False):
        return True
    source = str(item.get("source") or item.get("manifest_source") or "").strip().lower()
    template_key = str(item.get("template_key") or "").strip().lower()
    generation_profile = str(item.get("generation_profile") or "").strip().lower()
    return (
        source.startswith("manual")
        or template_key.startswith("manual")
        or generation_profile.startswith("manual")
    )


def _repair_brief(item: dict[str, object]) -> VisualBrief:
    raw_brief = item.get("visual_brief")
    if isinstance(raw_brief, dict):
        return {
            "mode": cast(VisualBriefMode, str(raw_brief.get("mode") or "keyword_image")),
            "main_subject": str(raw_brief.get("main_subject") or ""),
            "action": str(raw_brief.get("action") or ""),
            "primary_prop": str(raw_brief.get("primary_prop") or ""),
            "secondary_prop": str(raw_brief.get("secondary_prop") or ""),
            "scene": str(raw_brief.get("scene") or ""),
            "emotion": str(raw_brief.get("emotion") or ""),
            "must_show": list(raw_brief.get("must_show") or []),
            "avoid": list(raw_brief.get("avoid") or []),
            "rationale": str(raw_brief.get("rationale") or ""),
        }
    return {
        "mode": "keyword_image",
        "main_subject": "",
        "action": "",
        "primary_prop": "",
        "secondary_prop": "",
        "scene": "",
        "emotion": "",
        "must_show": [],
        "avoid": [],
        "rationale": "",
    }


def _update_candidate_review_repair_metadata(
    pid: str,
    *,
    sentence_idx: int,
    repair_attempted: bool,
    repair_reason: str,
    repair_issue_codes: list[str],
    current_negative_prompt: str = "",
    suggested_positive_prompt: str = "",
    suggested_prompt_g: str = "",
    suggested_prompt_l: str = "",
    suggested_negative_prompt: str = "",
    suggested_repair_reason: str = "",
    fallback_downgrade_applied: bool | None = None,
    fallback_downgrade_reason: str = "",
    operator_intervention_required: bool | None = None,
    operator_intervention_reason: str = "",
) -> None:
    project = db.get_project(pid)
    if project is None:
        return
    options = dict(project["body_image_options"])
    raw_candidate_reviews = options.get("candidate_reviews", {})
    if not isinstance(raw_candidate_reviews, dict):
        return
    group_key = str(sentence_idx)
    raw_review = raw_candidate_reviews.get(group_key)
    if not isinstance(raw_review, dict):
        return
    candidate_reviews: dict[str, dict[str, object]] = {}
    for key, value in raw_candidate_reviews.items():
        if isinstance(key, str) and isinstance(value, dict):
            candidate_reviews[key] = dict(value)
    review = dict(candidate_reviews.get(group_key, {}))
    review["repair_attempted"] = repair_attempted
    review["repair_reason"] = repair_reason
    review["repair_issue_codes"] = list(repair_issue_codes)
    if current_negative_prompt.strip():
        review["current_negative_prompt"] = current_negative_prompt
    if suggested_positive_prompt.strip():
        review["suggested_positive_prompt"] = suggested_positive_prompt
    if suggested_prompt_g.strip():
        review["suggested_prompt_g"] = suggested_prompt_g
    if suggested_prompt_l.strip():
        review["suggested_prompt_l"] = suggested_prompt_l
    if suggested_negative_prompt.strip():
        review["suggested_negative_prompt"] = suggested_negative_prompt
    if suggested_repair_reason.strip():
        review["suggested_repair_reason"] = suggested_repair_reason
    if fallback_downgrade_applied is not None:
        review["fallback_downgrade_applied"] = fallback_downgrade_applied
    if fallback_downgrade_reason.strip():
        review["fallback_downgrade_reason"] = fallback_downgrade_reason
    if operator_intervention_required is not None:
        review["operator_intervention_required"] = operator_intervention_required
    if operator_intervention_reason.strip():
        review["operator_intervention_reason"] = operator_intervention_reason
    candidate_reviews[group_key] = review
    options["candidate_reviews"] = candidate_reviews
    db.update_project(pid, body_image_options=options)


def _build_repair_suggestion(
    current_item: dict[str, object],
    *,
    issue_codes: list[str],
    attempt: int,
) -> PromptRepairDecision:
    current_positive_prompt = str(current_item.get("positive_prompt") or "")
    current_negative_prompt = str(current_item.get("negative_prompt") or "")
    repair = repair_prompts(
        positive_prompt={
            "prompt_g": str(current_item.get("prompt_g") or current_positive_prompt),
            "prompt_l": str(current_item.get("prompt_l") or current_positive_prompt),
            "combined": current_positive_prompt,
        },
        negative_prompt=current_negative_prompt,
        brief=_repair_brief(current_item),
        issue_codes=issue_codes,
        attempt=attempt,
    )
    reason_parts = [part.strip() for part in repair["repair_reason"].split(",") if part.strip()]
    prompt_g = repair["repaired_prompt_g"]
    prompt_l = repair["repaired_prompt_l"]
    negative = repair["repaired_negative_prompt"]
    if str(current_item.get("control_image") or "").strip():
        prompt_g = f"follow control composition strictly, {prompt_g}" if prompt_g else "follow control composition strictly"
        negative = f"{negative}, layout drift, camera angle change".strip(", ")
        reason_parts.append("preserve_control_layout")
    if str(current_item.get("style_reference_image") or "").strip():
        prompt_l = f"consistent reference-driven style, {prompt_l}" if prompt_l else "consistent reference-driven style"
        reason_parts.append("preserve_style_reference")
    if str(current_item.get("lora_name") or "").strip():
        prompt_l = f"preserve lora-driven character/style consistency, {prompt_l}" if prompt_l else "preserve lora-driven character/style consistency"
        reason_parts.append("preserve_lora_style")
    repair["repaired_prompt_g"] = prompt_g
    repair["repaired_prompt_l"] = prompt_l
    repair["repaired_positive_prompt"] = ", ".join(
        part for part in (prompt_g.strip(), prompt_l.strip()) if part
    )
    repair["repaired_negative_prompt"] = negative
    repair["repair_reason"] = ", ".join(dict.fromkeys(reason_parts))
    return repair


def _manifest_prompt_item_for_sentence(project: ProjectRecord, sentence_idx: int) -> dict[str, object]:
    raw_path = project["body_image_options"].get("image_prompts_manifest_path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        return {}
    try:
        import json

        payload = json.loads(Path(raw_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    prompts = payload.get("prompts")
    if not isinstance(prompts, list):
        return {}
    for item in prompts:
        if isinstance(item, dict) and item.get("sentence_idx") == sentence_idx:
            return item
    return {}


def _alternate_visual_mode(current_mode: str, anchor_type: str) -> VisualSceneMode | None:
    sequence = _ANCHOR_MODE_SEQUENCE.get(anchor_type, _ANCHOR_MODE_SEQUENCE["generic"])
    normalized_current = str(current_mode).strip().lower()
    if normalized_current not in sequence:
        return sequence[0]
    current_index = sequence.index(cast(VisualSceneMode, normalized_current))
    if current_index + 1 >= len(sequence):
        return None
    return sequence[current_index + 1]


def _regenerated_scene_anchor(visual_mode: VisualSceneMode, anchor_type: str) -> str:
    if visual_mode == "editorial_scene":
        if anchor_type == "institutional_decision":
            return "institutional finance strategy environment"
        if anchor_type == "investment_signal":
            return "capital allocation review environment"
        if anchor_type == "market_structure":
            return "market analysis environment"
        return "institutional finance environment"
    if visual_mode == "symbolic_concept":
        if anchor_type == "technical_barrier":
            return "lab-to-market barrier concept environment"
        if anchor_type == "future_outlook":
            return "future outlook concept environment"
        return "clean editorial concept environment"
    if visual_mode == "data_diagram":
        if anchor_type == "market_structure":
            return "plain warm portfolio comparison background"
        return "plain warm comparison background"
    if anchor_type == "comparison_frame":
        return "plain warm comparison explainer background"
    if anchor_type == "future_outlook":
        return "plain warm roadmap explainer background"
    return "plain warm explainer background"


def _safe_fallback_visual_mode(anchor_type: str) -> VisualSceneMode:
    return _SAFE_FALLBACK_MODE_BY_ANCHOR.get(anchor_type, _SAFE_FALLBACK_MODE_BY_ANCHOR["generic"])


def _build_regenerated_prompt_item(
    project: ProjectRecord,
    current_item: dict[str, object],
    *,
    sentence_idx: int,
) -> dict[str, object] | None:
    manifest_prompt_item = _manifest_prompt_item_for_sentence(project, sentence_idx)
    visual_plan = manifest_prompt_item.get("visual_plan")
    if not isinstance(visual_plan, dict):
        return None
    current_mode = str(visual_plan.get("visual_mode") or "")
    anchor_type = str(visual_plan.get("semantic_anchor_type") or "generic").strip().lower()
    next_mode = _alternate_visual_mode(current_mode, anchor_type)
    if next_mode is None:
        return None
    regenerated_plan: VisualPlanEntry = cast(VisualPlanEntry, dict(visual_plan))
    regenerated_plan["visual_mode"] = next_mode
    regenerated_plan["scene_anchor"] = _regenerated_scene_anchor(next_mode, anchor_type)
    suggestion = suggest_image_prompt(
        project,
        sentence_idx,
        visual_plan_entry=regenerated_plan,
    )
    updated_item = dict(current_item)
    updated_item["positive_prompt"] = str(suggestion.get("positive_prompt") or "")
    updated_item["negative_prompt"] = str(suggestion.get("negative_prompt") or "")
    updated_item["prompt_g"] = str(suggestion.get("prompt_g") or updated_item.get("positive_prompt") or "")
    updated_item["prompt_l"] = str(suggestion.get("prompt_l") or updated_item.get("positive_prompt") or "")
    updated_item["prompt"] = str(suggestion.get("positive_prompt") or "")
    updated_item["visual_brief"] = suggestion.get("visual_brief")
    raw_suggestion_plan = suggestion.get("visual_plan")
    if isinstance(raw_suggestion_plan, dict):
        merged_suggestion_plan = dict(regenerated_plan)
        merged_suggestion_plan.update(raw_suggestion_plan)
        updated_item["visual_plan"] = merged_suggestion_plan
    else:
        updated_item["visual_plan"] = regenerated_plan
    updated_item["manifest_prompt_item"] = suggestion
    updated_item["template_id"] = str(suggestion.get("template_id") or updated_item.get("template_id") or "txt2img_sdxl_basic")
    updated_item["generation_profile"] = str(suggestion.get("generation_profile") or updated_item.get("generation_profile") or "")
    updated_item["steps"] = suggestion.get("steps", updated_item.get("steps"))
    updated_item["cfg"] = suggestion.get("cfg", updated_item.get("cfg"))
    updated_item["sampler_name"] = suggestion.get("sampler_name", updated_item.get("sampler_name"))
    updated_item["scheduler"] = suggestion.get("scheduler", updated_item.get("scheduler"))
    updated_item["denoise"] = suggestion.get("denoise", updated_item.get("denoise"))
    updated_item["_plan_regenerated"] = True
    updated_item["_plan_regeneration_reason"] = f"scene_plan_regenerated:{anchor_type}:{current_mode}->{next_mode}"
    return updated_item


def _build_fallback_downgraded_prompt_item(
    project: ProjectRecord,
    current_item: dict[str, object],
    *,
    sentence_idx: int,
) -> dict[str, object] | None:
    raw_current_plan = current_item.get("visual_plan")
    if isinstance(raw_current_plan, dict):
        visual_plan = raw_current_plan
    else:
        manifest_prompt_item = _manifest_prompt_item_for_sentence(project, sentence_idx)
        fallback_plan = manifest_prompt_item.get("visual_plan")
        if not isinstance(fallback_plan, dict):
            return None
        visual_plan = fallback_plan
    current_mode = str(visual_plan.get("visual_mode") or "")
    anchor_type = str(visual_plan.get("semantic_anchor_type") or "generic").strip().lower()
    downgraded_mode = _safe_fallback_visual_mode(anchor_type)
    if current_item.get("_fallback_downgraded") is True and current_mode.strip().lower() == downgraded_mode:
        return None
    downgraded_plan: VisualPlanEntry = cast(VisualPlanEntry, dict(visual_plan))
    downgraded_plan["visual_mode"] = downgraded_mode
    downgraded_plan["scene_anchor"] = _regenerated_scene_anchor(downgraded_mode, anchor_type)
    suggestion = suggest_image_prompt(
        project,
        sentence_idx,
        visual_plan_entry=downgraded_plan,
    )
    updated_item = dict(current_item)
    updated_item["positive_prompt"] = str(suggestion.get("positive_prompt") or "")
    updated_item["negative_prompt"] = str(suggestion.get("negative_prompt") or "")
    updated_item["prompt_g"] = str(suggestion.get("prompt_g") or updated_item.get("positive_prompt") or "")
    updated_item["prompt_l"] = str(suggestion.get("prompt_l") or updated_item.get("positive_prompt") or "")
    updated_item["prompt"] = str(suggestion.get("positive_prompt") or "")
    updated_item["visual_brief"] = suggestion.get("visual_brief")
    raw_suggestion_plan = suggestion.get("visual_plan")
    if isinstance(raw_suggestion_plan, dict):
        merged_suggestion_plan = dict(downgraded_plan)
        merged_suggestion_plan.update(raw_suggestion_plan)
        updated_item["visual_plan"] = merged_suggestion_plan
    else:
        updated_item["visual_plan"] = downgraded_plan
    updated_item["manifest_prompt_item"] = suggestion
    updated_item["template_id"] = str(suggestion.get("template_id") or updated_item.get("template_id") or "txt2img_sdxl_basic")
    updated_item["generation_profile"] = str(suggestion.get("generation_profile") or updated_item.get("generation_profile") or "")
    updated_item["steps"] = suggestion.get("steps", updated_item.get("steps"))
    updated_item["cfg"] = suggestion.get("cfg", updated_item.get("cfg"))
    updated_item["sampler_name"] = suggestion.get("sampler_name", updated_item.get("sampler_name"))
    updated_item["scheduler"] = suggestion.get("scheduler", updated_item.get("scheduler"))
    updated_item["denoise"] = suggestion.get("denoise", updated_item.get("denoise"))
    updated_item["_fallback_downgraded"] = True
    updated_item["_fallback_downgrade_reason"] = f"fallback_downgrade:{anchor_type}:{current_mode}->{downgraded_mode}"
    return updated_item

def _refresh_project_plans(pid: str) -> tuple[bool, str]:
    project = db.get_project(pid)
    if project is None:
        return False, "Project disappeared before plan refresh."
    render_format = _preferred_render_format(project)
    scene_plan = build_scene_plan(project, render_format=render_format)
    updated = db.update_project(pid, scene_plan=scene_plan)
    if updated is None:
        return False, "Failed to save refreshed scene plan."
    render_plan = build_render_plan(updated)
    if db.update_project(pid, render_plan=render_plan) is None:
        return False, "Failed to save refreshed render plan."
    latest = db.get_project(pid)
    if latest is not None:
        with suppress(Exception):
            write_visual_mismatch_report(latest)
            write_visual_contact_sheet(latest)
    return True, "Generated images and refreshed scene/render plans."


def _run_job_with_heartbeat(pid: str) -> None:
    stop_event = threading.Event()
    gpu_owner = f"image-job:{pid}"

    def heartbeat() -> None:
        while not stop_event.wait(HEARTBEAT_INTERVAL_SEC):
            with suppress(Exception):
                db.touch_body_image_heartbeat(pid)

    heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
    heartbeat_thread.start()
    try:
        project = db.get_project(pid)
        if project is None:
            return
        options = project["body_image_options"]
        auto_build_plans = _as_bool(options.get("auto_build_plans_after_image"), True)
        batch_items_raw = options.get("batch_items")
        if isinstance(batch_items_raw, list) and batch_items_raw:
            job_items = [item for item in batch_items_raw if isinstance(item, dict)]
        else:
            job_items = [options]
        total_items = max(1, len(job_items))
        retry_messages: list[str] = []
        operator_intervention_required = False

        while not gpu_guard.acquire("comfyui", gpu_owner, timeout_sec=int(HISTORY_TIMEOUT_SEC)):
            owner = gpu_guard.current_owner()
            db.update_project(
                pid,
                body_image_phase="wait_gpu",
                body_image_progress=10,
                body_image_last_log=f"Waiting for GPU to become available ({owner or 'unknown owner'}).",
            )
            if stop_event.wait(2.0):
                return

        client = ComfyUIClient()
        for index, item in enumerate(job_items):
            current_item = dict(item)
            blocking_prompt_codes = _blocking_prompt_quality_codes(current_item)
            if blocking_prompt_codes:
                message = (
                    f"Prompt quality gate blocked sentence {to_int(current_item.get('sentence_idx'), 0)} "
                    f"before ComfyUI submit: {', '.join(blocking_prompt_codes)}."
                )
                db.update_project(
                    pid,
                    body_image_state="blocked",
                    body_image_phase="prompt_quality_gate",
                    body_image_error=message,
                    body_image_last_log=message,
                )
                return
            template_id = str(current_item.get("template_id") or "txt2img_sdxl_basic")
            client_id = str(current_item.get("client_id") or "newauto")
            sentence_idx = to_int(current_item.get("sentence_idx"), 0)
            manifest_sentence_hash = str(current_item.get("sentence_hash") or "")
            base_candidate_index = to_int(current_item.get("candidate_index"), 1)
            repair_retry_limit = max(0, to_int(current_item.get("repair_retry_limit"), to_int(options.get("repair_retry_limit"), 1)))
            plan_retry_limit = min(MAX_PLAN_RETRIES, max(0, to_int(current_item.get("plan_retry_limit"), to_int(options.get("plan_retry_limit"), 1))))
            fallback_downgrade_limit = min(
                MAX_FALLBACK_DOWNGRADES,
                max(0, to_int(current_item.get("fallback_downgrade_limit"), to_int(options.get("fallback_downgrade_limit"), 1))),
            )
            plan_retry_count = 0
            fallback_downgrade_count = 0
            total_attempts = 1 + repair_retry_limit + plan_retry_limit + fallback_downgrade_limit
            base_progress = int(index / total_items * 100)
            attempt = 0
            while attempt < total_attempts:
                current_prompt = str(current_item.get("prompt") or current_item.get("positive_prompt") or "")
                current_positive_prompt = str(current_item.get("positive_prompt") or "")
                current_negative_prompt = str(current_item.get("negative_prompt") or "")
                placeholders: PlaceholderMap = {
                    "__CHECKPOINT__": str(current_item.get("checkpoint") or ""),
                    "__WIDTH__": to_int(current_item.get("width"), 1024),
                    "__HEIGHT__": to_int(current_item.get("height"), 576),
                    "__SEED__": to_int(current_item.get("seed"), 1),
                    "__STEPS__": to_int(current_item.get("steps"), 30),
                    "__CFG__": float(current_item.get("cfg") or 5.8),
                    "__SAMPLER__": str(current_item.get("sampler_name") or "dpmpp_2m"),
                    "__SCHEDULER__": str(current_item.get("scheduler") or "karras"),
                    "__DENOISE__": float(current_item.get("denoise") or 1.0),
                    "__ORIGINAL_WIDTH__": to_int(current_item.get("original_width"), to_int(current_item.get("width"), 1024)),
                    "__ORIGINAL_HEIGHT__": to_int(current_item.get("original_height"), to_int(current_item.get("height"), 576)),
                    "__TARGET_WIDTH__": to_int(current_item.get("target_width"), to_int(current_item.get("width"), 1024)),
                    "__TARGET_HEIGHT__": to_int(current_item.get("target_height"), to_int(current_item.get("height"), 576)),
                    "__CROP_W__": to_int(current_item.get("crop_w"), 0),
                    "__CROP_H__": to_int(current_item.get("crop_h"), 0),
                    "__FILENAME_PREFIX__": str(current_item.get("filename_prefix") or "newauto"),
                    "__LORA_NAME__": str(current_item.get("lora_name") or ""),
                    "__LORA_STRENGTH__": float(current_item.get("lora_strength") or 0.8),
                    "__STYLE_REFERENCE_IMAGE__": str(current_item.get("style_reference_image") or ""),
                    "__STYLE_REFERENCE_STRENGTH__": float(current_item.get("style_reference_strength") or 0.65),
                    "__CONTROL_IMAGE__": str(current_item.get("control_image") or ""),
                    "__CONTROL_STRENGTH__": float(current_item.get("control_strength") or 0.75),
                }
                placeholders.update(
                    build_prompt_placeholders(
                        positive_prompt={
                            "prompt_g": str(current_item.get("prompt_g") or current_positive_prompt),
                            "prompt_l": str(current_item.get("prompt_l") or current_positive_prompt),
                            "combined": current_positive_prompt,
                        },
                        negative_prompt=current_negative_prompt,
                    )
                )
                db.update_project(
                    pid,
                    body_image_phase="submit",
                    body_image_progress=_progress(max(10, base_progress + 10)),
                    body_image_last_log=f"Submitting ComfyUI workflow {index + 1}/{total_items} attempt {attempt + 1}/{total_attempts}...",
                )
                prompt_id = submit_template(
                    template_id=template_id,
                    placeholders=placeholders,
                    client_id=client_id,
                    timeout_sec=to_int(current_item.get("request_timeout_sec"), 180),
                )
                deadline = time.monotonic() + HISTORY_TIMEOUT_SEC
                next_poll_status_at = time.monotonic()
                db.update_project(
                    pid,
                    body_image_phase="poll_history",
                    body_image_progress=_progress(max(20, base_progress + 35)),
                    body_image_last_log=f"Waiting for ComfyUI history {index + 1}/{total_items} attempt {attempt + 1}/{total_attempts} ({prompt_id})...",
                )
                while time.monotonic() < deadline:
                    now = time.monotonic()
                    if now >= next_poll_status_at:
                        remaining_sec = max(0, int(deadline - now))
                        db.update_project(
                            pid,
                            body_image_phase="poll_history",
                            body_image_progress=_progress(max(20, base_progress + 35)),
                            body_image_last_log=(
                                f"Polling ComfyUI history {index + 1}/{total_items} "
                                f"attempt {attempt + 1}/{total_attempts} ({prompt_id}); "
                                f"timeout in {remaining_sec}s."
                            ),
                        )
                        db.touch_body_image_heartbeat(pid)
                        next_poll_status_at = now + 15.0
                    history = client.get_history(prompt_id)
                    images = client.extract_image_results(history, prompt_id)
                    if images:
                        break
                    execution_error = client.extract_execution_error(history, prompt_id)
                    if execution_error:
                        raise RuntimeError(execution_error)
                    if stop_event.wait(HISTORY_POLL_SEC):
                        return
                else:
                    raise RuntimeError("ComfyUI history did not produce an image before timeout.")

                db.update_project(
                    pid,
                    body_image_phase="import_media",
                    body_image_progress=_progress(max(30, base_progress + 70)),
                    body_image_last_log=f"Importing generated image {index + 1}/{total_items} attempt {attempt + 1}/{total_attempts} into project media...",
                )
                refreshed = db.get_project(pid)
                if refreshed is None:
                    return
                candidate_total = max(to_int(current_item.get("candidate_total"), 1), base_candidate_index + repair_retry_limit)
                candidate_index = base_candidate_index + attempt
                import_history_image(
                    refreshed,
                    prompt_id=prompt_id,
                    sentence_idx=sentence_idx,
                    prompt=current_prompt,
                    manifest_sentence_hash=manifest_sentence_hash,
                    candidate_index=candidate_index,
                    candidate_total=candidate_total,
                    selected_reason="strict_retry" if current_item.get("_repair_reason") == "strict_borderline_retry" else "",
                    template_id=template_id,
                    generation_profile=str(current_item.get("generation_profile") or ""),
                    style_reference_image=str(current_item.get("style_reference_image") or ""),
                    lora_name=str(current_item.get("lora_name") or ""),
                    width=to_int(current_item.get("width"), 0),
                    height=to_int(current_item.get("height"), 0),
                    prompt_item_override=cast(dict[str, object], current_item.get("manifest_prompt_item"))
                    if isinstance(current_item.get("manifest_prompt_item"), dict)
                    else None,
                )
                refreshed_after_import = db.get_project(pid)
                if refreshed_after_import is None:
                    break
                candidate_reviews = refreshed_after_import["body_image_options"].get("candidate_reviews", {})
                if not isinstance(candidate_reviews, dict):
                    break
                review = candidate_reviews.get(str(sentence_idx))
                if isinstance(review, dict) and current_item.get("_repair_attempted") is True:
                    repair_reason = str(current_item.get("_repair_reason") or "repair_retry_completed")
                    raw_issue_codes = current_item.get("_repair_issue_codes")
                    repair_issue_codes = list(raw_issue_codes) if isinstance(raw_issue_codes, list) else []
                    _update_candidate_review_repair_metadata(
                        pid,
                        sentence_idx=sentence_idx,
                        repair_attempted=True,
                        repair_reason=repair_reason,
                        repair_issue_codes=repair_issue_codes,
                        current_negative_prompt=str(current_item.get("negative_prompt") or ""),
                    )
                    refreshed_after_import = db.get_project(pid)
                    if refreshed_after_import is None:
                        break
                    candidate_reviews = refreshed_after_import["body_image_options"].get("candidate_reviews", {})
                    if not isinstance(candidate_reviews, dict):
                        break
                    review = candidate_reviews.get(str(sentence_idx))
                if isinstance(review, dict) and current_item.get("_fallback_downgraded") is True:
                    raw_issue_codes = current_item.get("_repair_issue_codes")
                    downgrade_issue_codes = list(raw_issue_codes) if isinstance(raw_issue_codes, list) else []
                    _update_candidate_review_repair_metadata(
                        pid,
                        sentence_idx=sentence_idx,
                        repair_attempted=bool(current_item.get("_repair_attempted") is True),
                        repair_reason=str(current_item.get("_repair_reason") or "fallback_downgrade_completed"),
                        repair_issue_codes=downgrade_issue_codes,
                        current_negative_prompt=str(current_item.get("negative_prompt") or ""),
                        fallback_downgrade_applied=True,
                        fallback_downgrade_reason=str(current_item.get("_fallback_downgrade_reason") or "fallback_downgrade"),
                    )
                    refreshed_after_import = db.get_project(pid)
                    if refreshed_after_import is None:
                        break
                    candidate_reviews = refreshed_after_import["body_image_options"].get("candidate_reviews", {})
                    if not isinstance(candidate_reviews, dict):
                        break
                    review = candidate_reviews.get(str(sentence_idx))
                if not isinstance(review, dict) or review.get("retry_recommended") is not True:
                    break
                retry_reason = str(review.get("retry_reason") or "low_candidate_score")
                retry_message = f"Candidate review for sentence {sentence_idx} recommends retry: {retry_reason}."
                retry_messages.append(retry_message)
                db.update_project(
                    pid,
                    body_image_last_log=retry_message,
                )
                if (
                    plan_retry_count < plan_retry_limit
                    and retry_reason in {"low_candidate_score", "borderline_candidate"}
                    and not _is_heavy_retry_item(current_item)
                    and not _is_manual_art_directed_item(project, current_item)
                ):
                    refreshed_for_regen = db.get_project(pid)
                    if refreshed_for_regen is not None:
                        regenerated_item = _build_regenerated_prompt_item(
                            refreshed_for_regen,
                            current_item,
                            sentence_idx=sentence_idx,
                        )
                    else:
                        regenerated_item = None
                    if regenerated_item is not None:
                        current_item = regenerated_item
                        current_item["filename_prefix"] = f"{str(item.get('filename_prefix') or 'newauto')}_replan_{plan_retry_count + 1}"
                        current_item["_repair_attempted"] = False
                        current_item["_repair_reason"] = str(current_item.get("_plan_regeneration_reason") or "scene_plan_regenerated")
                        current_item["_repair_issue_codes"] = _review_issue_codes(review)
                        plan_retry_count += 1
                        regen_message = (
                            f"Scene-plan regeneration queued for sentence {sentence_idx}: "
                            f"{current_item.get('_plan_regeneration_reason') or 'scene_plan_regenerated'}."
                        )
                        retry_messages.append(regen_message)
                        db.update_project(
                            pid,
                            body_image_last_log=regen_message,
                        )
                        attempt += 1
                        continue
                if (
                    fallback_downgrade_count < fallback_downgrade_limit
                    and retry_reason in {"low_candidate_score", "borderline_candidate"}
                    and not _is_heavy_retry_item(current_item)
                    and not _is_manual_art_directed_item(project, current_item)
                ):
                    refreshed_for_downgrade = db.get_project(pid)
                    if refreshed_for_downgrade is not None:
                        downgraded_item = _build_fallback_downgraded_prompt_item(
                            refreshed_for_downgrade,
                            current_item,
                            sentence_idx=sentence_idx,
                        )
                    else:
                        downgraded_item = None
                    if downgraded_item is not None:
                        current_item = downgraded_item
                        current_item["filename_prefix"] = f"{str(item.get('filename_prefix') or 'newauto')}_fallback_{fallback_downgrade_count + 1}"
                        current_item["_repair_attempted"] = False
                        current_item["_repair_reason"] = str(
                            current_item.get("_fallback_downgrade_reason") or "fallback_downgrade"
                        )
                        current_item["_repair_issue_codes"] = _review_issue_codes(review)
                        fallback_downgrade_count += 1
                        downgrade_message = (
                            f"Fallback downgrade queued for sentence {sentence_idx}: "
                            f"{current_item.get('_fallback_downgrade_reason') or 'fallback_downgrade'}."
                        )
                        retry_messages.append(downgrade_message)
                        db.update_project(
                            pid,
                            body_image_last_log=downgrade_message,
                        )
                        attempt += 1
                        continue
                if attempt >= repair_retry_limit:
                    issue_codes = review.get("vision_qa_issue_codes")
                    repair_issue_codes = list(issue_codes) if isinstance(issue_codes, list) else []
                    repair_suggestion = _build_repair_suggestion(
                        current_item,
                        issue_codes=repair_issue_codes,
                        attempt=attempt + 1,
                    )
                    _update_candidate_review_repair_metadata(
                        pid,
                        sentence_idx=sentence_idx,
                        repair_attempted=bool(current_item.get("_repair_attempted") is True),
                        repair_reason=f"retry_limit_reached:{retry_reason}",
                        repair_issue_codes=repair_issue_codes,
                        current_negative_prompt=str(current_item.get("negative_prompt") or ""),
                        suggested_positive_prompt=repair_suggestion["repaired_positive_prompt"],
                        suggested_prompt_g=repair_suggestion["repaired_prompt_g"],
                        suggested_prompt_l=repair_suggestion["repaired_prompt_l"],
                        suggested_negative_prompt=repair_suggestion["repaired_negative_prompt"],
                        suggested_repair_reason=repair_suggestion["repair_reason"],
                        fallback_downgrade_applied=bool(current_item.get("_fallback_downgraded") is True),
                        fallback_downgrade_reason=str(current_item.get("_fallback_downgrade_reason") or ""),
                        operator_intervention_required=True,
                        operator_intervention_reason=f"operator_review_required:{retry_reason}",
                    )
                    operator_intervention_required = True
                    operator_message = (
                        f"Operator review required for sentence {sentence_idx}: "
                        f"retry persisted after regeneration/downgrade ({retry_reason})."
                    )
                    retry_messages.append(operator_message)
                    db.update_project(
                        pid,
                        body_image_last_log=operator_message,
                    )
                    break
                status = gpu_guard.get_status()
                if status["locked"] and status["owner"] != gpu_owner:
                    skip_message = f"Skipped repair retry for sentence {sentence_idx} because GPU is owned by {status['owner'] or 'another worker'}."
                    retry_messages.append(skip_message)
                    db.update_project(
                        pid,
                        body_image_last_log=skip_message,
                    )
                    issue_codes = review.get("vision_qa_issue_codes")
                    repair_issue_codes = list(issue_codes) if isinstance(issue_codes, list) else []
                    repair_suggestion = _build_repair_suggestion(
                        current_item,
                        issue_codes=repair_issue_codes,
                        attempt=attempt + 1,
                    )
                    _update_candidate_review_repair_metadata(
                        pid,
                        sentence_idx=sentence_idx,
                        repair_attempted=False,
                        repair_reason="repair_retry_skipped_gpu_busy",
                        repair_issue_codes=repair_issue_codes,
                        current_negative_prompt=str(current_item.get("negative_prompt") or ""),
                        suggested_positive_prompt=repair_suggestion["repaired_positive_prompt"],
                        suggested_prompt_g=repair_suggestion["repaired_prompt_g"],
                        suggested_prompt_l=repair_suggestion["repaired_prompt_l"],
                        suggested_negative_prompt=repair_suggestion["repaired_negative_prompt"],
                        suggested_repair_reason=repair_suggestion["repair_reason"],
                    )
                    break
                if _is_heavy_retry_item(current_item):
                    skip_message = f"Skipped repair retry for sentence {sentence_idx} because the item uses a heavy style/control path."
                    retry_messages.append(skip_message)
                    db.update_project(
                        pid,
                        body_image_last_log=skip_message,
                    )
                    issue_codes = review.get("vision_qa_issue_codes")
                    repair_issue_codes = list(issue_codes) if isinstance(issue_codes, list) else []
                    repair_suggestion = _build_repair_suggestion(
                        current_item,
                        issue_codes=repair_issue_codes,
                        attempt=attempt + 1,
                    )
                    _update_candidate_review_repair_metadata(
                        pid,
                        sentence_idx=sentence_idx,
                        repair_attempted=False,
                        repair_reason="repair_retry_skipped_heavy_path",
                        repair_issue_codes=repair_issue_codes,
                        current_negative_prompt=str(current_item.get("negative_prompt") or ""),
                        suggested_positive_prompt=repair_suggestion["repaired_positive_prompt"],
                        suggested_prompt_g=repair_suggestion["repaired_prompt_g"],
                        suggested_prompt_l=repair_suggestion["repaired_prompt_l"],
                        suggested_negative_prompt=repair_suggestion["repaired_negative_prompt"],
                        suggested_repair_reason=repair_suggestion["repair_reason"],
                    )
                    break
                if _is_manual_art_directed_item(project, current_item):
                    skip_message = f"Skipped repair retry for sentence {sentence_idx} because the item is manual art-directed."
                    retry_messages.append(skip_message)
                    db.update_project(
                        pid,
                        body_image_last_log=skip_message,
                    )
                    issue_codes = review.get("vision_qa_issue_codes")
                    repair_issue_codes = list(issue_codes) if isinstance(issue_codes, list) else []
                    _update_candidate_review_repair_metadata(
                        pid,
                        sentence_idx=sentence_idx,
                        repair_attempted=False,
                        repair_reason="manual_art_directed_skip",
                        repair_issue_codes=repair_issue_codes,
                        current_negative_prompt=str(current_item.get("negative_prompt") or ""),
                    )
                    break
                issue_codes = review.get("vision_qa_issue_codes")
                resolved_issue_codes = list(issue_codes) if isinstance(issue_codes, list) else []
                repair = _build_repair_suggestion(
                    current_item,
                    issue_codes=resolved_issue_codes,
                    attempt=attempt + 1,
                )
                if repair["should_retry"] is not True:
                    _update_candidate_review_repair_metadata(
                        pid,
                        sentence_idx=sentence_idx,
                        repair_attempted=False,
                        repair_reason=repair["repair_reason"],
                        repair_issue_codes=resolved_issue_codes,
                        current_negative_prompt=str(current_item.get("negative_prompt") or ""),
                        suggested_positive_prompt=repair["repaired_positive_prompt"],
                        suggested_prompt_g=repair["repaired_prompt_g"],
                        suggested_prompt_l=repair["repaired_prompt_l"],
                        suggested_negative_prompt=repair["repaired_negative_prompt"],
                        suggested_repair_reason=repair["repair_reason"],
                    )
                    break
                current_item["positive_prompt"] = repair["repaired_positive_prompt"]
                current_item["negative_prompt"] = repair["repaired_negative_prompt"]
                current_item["prompt_g"] = repair["repaired_prompt_g"]
                current_item["prompt_l"] = repair["repaired_prompt_l"]
                current_item["prompt"] = repair["repaired_positive_prompt"]
                current_item["filename_prefix"] = f"{str(item.get('filename_prefix') or 'newauto')}_repair_{attempt + 1}"
                current_item["_repair_attempted"] = True
                current_item["_repair_reason"] = repair["repair_reason"]
                current_item["_repair_issue_codes"] = list(resolved_issue_codes)
                repair_message = f"Repair retry queued for sentence {sentence_idx}: {repair['repair_reason']}."
                retry_messages.append(repair_message)
                db.update_project(
                    pid,
                    body_image_last_log=repair_message,
                )
                attempt += 1
                continue
            # end while attempt
        final_phase = "done"
        final_log = ""
        if auto_build_plans:
            db.update_project(
                pid,
                body_image_phase="refresh_plans",
                body_image_progress=95,
                body_image_last_log="Refreshing scene/render plans from generated images...",
            )
            ok, final_log = _refresh_project_plans(pid)
            final_phase = "done" if ok else "done_with_plan_warning"
        if retry_messages:
            retry_summary = " ".join(retry_messages)
            final_log = f"{final_log} {retry_summary}".strip()
        if operator_intervention_required:
            final_phase = "done_with_operator_warning"
        db.update_project(
            pid,
            body_image_state="done",
            body_image_progress=100,
            body_image_error="",
            body_image_phase=final_phase,
            body_image_last_log=final_log,
        )
    except Exception as exc:
        db.update_project(
            pid,
            body_image_state="error",
            body_image_progress=0,
            body_image_error=str(exc),
            body_image_phase="",
            body_image_last_log=str(exc)[:500],
        )
    finally:
        gpu_guard.release(gpu_owner)
        stop_event.set()
        heartbeat_thread.join(timeout=1.0)


def main() -> int:
    db.init_db()
    with single_instance_lock(WORKER_LOCK_PATH) as acquired:
        if not acquired:
            return 0
        while True:
            pid = db.claim_next_queued_body_image()
            if pid is None:
                time.sleep(POLL_INTERVAL_SEC)
                continue
            _run_job_with_heartbeat(pid)


if __name__ == "__main__":
    raise SystemExit(main())
