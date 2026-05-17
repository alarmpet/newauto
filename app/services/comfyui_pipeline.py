import re
import shutil
from pathlib import Path
import json
from typing import TypedDict, cast
from typing_extensions import NotRequired

from fastapi import HTTPException

from .. import db
from ..config import ALLOWED_IMAGE_EXT, COMFYUI_INSTALL_DIR
from ..types import BodyImageMapping, ProjectRecord, VisualBrief
from .prompt_quality import build_keyword_coverage
from .parse_utils import to_float, to_int
from .visual_vocab import domain_global_avoid, load_domain_vocab
from .comfyui_client import ComfyImageResult, ComfyUIClient
from .comfyui_workflows import PlaceholderMap, render_workflow_template
from .image_quality import analyze_image_quality
from .visual_relevance import sentence_hash

SCORE_VERSION = "candidate_score_v2"
RETRY_SCORE_THRESHOLD = 0.6
STRONG_SCORE_THRESHOLD = 0.72
STRICT_DOMAIN_SCORE_THRESHOLD = 0.72


class CandidateScoreDetails(TypedDict):
    score: float
    score_version: str
    score_components: dict[str, float]


class CandidateSelectionDecision(TypedDict):
    selected_path: str
    selected_prompt: str
    selected_prompt_id: str
    selected_index: int
    selected_total: int
    selected_score: float
    selected_score_version: str
    selection_reason: str
    retry_recommended: bool
    retry_reason: str
    repair_attempted: NotRequired[bool]
    repair_issue_codes: NotRequired[list[str]]
    repair_reason: NotRequired[str]


STYLE_CONSISTENCY_VERSION = "style_consistency_v1"


def _sanitize_filename(filename: str) -> str:
    clean_name = re.sub(r"[^\w\-.]+", "_", filename).strip("._")
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_IMAGE_EXT:
        suffix = ".png"
    stem = Path(clean_name).stem or "image"
    return f"{stem}{suffix}"


def _unique_media_path(media_dir: Path, filename: str) -> Path:
    base_name = _sanitize_filename(filename)
    target = media_dir / base_name
    counter = 0
    while target.exists():
        counter += 1
        target = media_dir / f"{target.stem}_{counter}{target.suffix}"
    return target


def resolve_comfy_output_path(result: ComfyImageResult, install_dir: Path = COMFYUI_INSTALL_DIR) -> Path:
    base_dir = install_dir / result.type
    candidate = base_dir / result.subfolder / result.filename if result.subfolder else base_dir / result.filename
    if candidate.exists():
        return candidate
    fallback = install_dir / "output" / result.filename
    if fallback.exists():
        return fallback
    raise HTTPException(404, f"ComfyUI output file not found: {result.filename}")


def _manifest_prompt_item(project: ProjectRecord, sentence_idx: int) -> dict[str, object]:
    raw_path = project["body_image_options"].get("image_prompts_manifest_path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        return {}
    try:
        payload = json.loads(Path(raw_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    prompts = payload.get("prompts")
    if not isinstance(prompts, list):
        return {}
    for item in prompts:
        if isinstance(item, dict) and item.get("sentence_idx") == sentence_idx:
            return item
    return {}


def _manifest_prompt_items(project: ProjectRecord) -> list[dict[str, object]]:
    raw_path = project["body_image_options"].get("image_prompts_manifest_path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        return []
    try:
        payload = json.loads(Path(raw_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    prompts = payload.get("prompts")
    if not isinstance(prompts, list):
        return []
    return [item for item in prompts if isinstance(item, dict)]


def _manifest_prompt_item_by_idx(project: ProjectRecord) -> dict[int, dict[str, object]]:
    indexed: dict[int, dict[str, object]] = {}
    for item in _manifest_prompt_items(project):
        sentence_idx = item.get("sentence_idx")
        if isinstance(sentence_idx, int):
            indexed[sentence_idx] = item
    return indexed


def _clamp_score(value: float) -> float:
    return max(0.0, min(1.0, value))


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _is_manual_art_directed_prompt(project: ProjectRecord, prompt_item: dict[str, object]) -> bool:
    if _as_bool(project["body_image_options"].get("manual_art_directed")):
        return True
    if _as_bool(prompt_item.get("manual_art_directed")):
        return True
    source = str(prompt_item.get("source") or prompt_item.get("manifest_source") or "").strip().lower()
    template_key = str(prompt_item.get("template_key") or "").strip().lower()
    generation_profile = str(prompt_item.get("generation_profile") or "").strip().lower()
    return (
        source.startswith("manual")
        or template_key.startswith("manual")
        or generation_profile.startswith("manual")
    )


def _selected_candidate_item(group_items: list[dict[str, object]]) -> dict[str, object] | None:
    for item in group_items:
        if isinstance(item, dict) and item.get("selected") is True:
            return item
    return None


def _same_nonempty(left: object, right: object) -> bool:
    return isinstance(left, str) and isinstance(right, str) and left.strip() != "" and left == right


def _style_consistency_details(
    previous_item: dict[str, object] | None,
    current_item: dict[str, object],
) -> tuple[float, dict[str, float], str]:
    if previous_item is None:
        return 1.0, {"first_scene_baseline": 1.0}, "first_scene_baseline"

    components: dict[str, float] = {
        "same_generation_profile": 0.0,
        "same_template_family": 0.0,
        "same_style_reference": 0.0,
        "same_lora": 0.0,
        "same_aspect_ratio": 0.0,
    }
    if _same_nonempty(previous_item.get("generation_profile"), current_item.get("generation_profile")):
        components["same_generation_profile"] = 0.35
    if _same_nonempty(previous_item.get("template_id"), current_item.get("template_id")):
        components["same_template_family"] = 0.2
    if _same_nonempty(previous_item.get("style_reference_image"), current_item.get("style_reference_image")):
        components["same_style_reference"] = 0.25
    if _same_nonempty(previous_item.get("lora_name"), current_item.get("lora_name")):
        components["same_lora"] = 0.15
    previous_aspect = f"{to_int(previous_item.get('width'), 0)}x{to_int(previous_item.get('height'), 0)}"
    current_aspect = f"{to_int(current_item.get('width'), 0)}x{to_int(current_item.get('height'), 0)}"
    if previous_aspect == current_aspect and previous_aspect != "0x0":
        components["same_aspect_ratio"] = 0.05

    score = _clamp_score(sum(components.values()))
    if score >= 0.8:
        reason = "strong_adjacent_style_match"
    elif score >= 0.5:
        reason = "partial_adjacent_style_match"
    else:
        reason = "weak_adjacent_style_match"
    return score, components, reason


def _refresh_style_consistency_reviews(
    candidate_groups: dict[str, list[dict[str, object]]],
    candidate_reviews: dict[str, dict[str, object]],
) -> dict[str, dict[str, object]]:
    previous_selected: dict[str, object] | None = None
    for sentence_idx in sorted((key for key in candidate_groups.keys() if str(key).isdigit()), key=int):
        group_items = candidate_groups.get(sentence_idx)
        if not isinstance(group_items, list):
            continue
        selected_item = _selected_candidate_item([item for item in group_items if isinstance(item, dict)])
        review = candidate_reviews.get(sentence_idx)
        if not isinstance(review, dict) or selected_item is None:
            continue
        score, components, reason = _style_consistency_details(previous_selected, selected_item)
        review["style_consistency_score"] = score
        review["style_consistency_version"] = STYLE_CONSISTENCY_VERSION
        review["style_consistency_reason"] = reason
        review["style_consistency_components"] = components
        candidate_reviews[sentence_idx] = review
        previous_selected = selected_item
    return candidate_reviews


def _previous_selected_media_path(project: ProjectRecord, sentence_idx: int) -> Path | None:
    previous_candidates = [item for item in project["body_image_mappings"] if item["sentence_idx"] < sentence_idx]
    if not previous_candidates:
        return None
    previous_item = max(previous_candidates, key=lambda item: to_int(item["sentence_idx"], -1))
    previous_path = db.project_dir(project["id"]) / "media" / str(previous_item.get("path") or "")
    if previous_path.exists():
        return previous_path
    return None


def _text_contains_any(text: str, needles: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(needle in lowered for needle in needles)


def _editorial_science_issue_codes(
    *,
    prompt_item: dict[str, object],
    vision_issue_codes: list[str],
) -> list[str]:
    visual_brief = prompt_item.get("visual_brief")
    if not isinstance(visual_brief, dict):
        return []
    domain = str(visual_brief.get("domain") or "").strip().lower()
    if domain not in {"agriculture_environment", "science_materials"}:
        return []
    positive_prompt = str(prompt_item.get("positive_prompt") or "")
    must_show = visual_brief.get("must_show")
    must_show_text = " ".join(item for item in must_show if isinstance(item, str)) if isinstance(must_show, list) else ""
    haystack = f"{positive_prompt} {must_show_text} {visual_brief.get('composition_template', '')}"
    issue_codes: list[str] = []
    if _text_contains_any(must_show_text, ("film", "mulch", "sheet")) and not _text_contains_any(
        positive_prompt,
        ("film", "mulch", "sheet", "transparent", "translucent"),
    ):
        issue_codes.append("MISSING_DOMINANT_FILM_OBJECT")
    if _text_contains_any(haystack, ("microplastic", "plastic fragment", "fragments", "particle")) and not _text_contains_any(
        positive_prompt,
        ("fragment", "particle", "soil", "ground-level"),
    ):
        issue_codes.append("SOIL_WITHOUT_PLASTIC_FRAGMENT")
    if _text_contains_any(haystack, ("lab", "extraction", "beaker", "water-based")) and not _text_contains_any(
        positive_prompt,
        ("process", "flow", "beaker", "fiber", "tray"),
    ):
        issue_codes.append("LAB_WITHOUT_PROCESS_FLOW")
    if _text_contains_any(haystack, ("field", "crop", "farm")) and not _text_contains_any(
        positive_prompt,
        ("film", "soil", "split", "crop row", "protected"),
    ):
        issue_codes.append("GENERIC_FIELD_ONLY")
    if _text_contains_any(haystack, ("decomposition", "degrade", "breaking down", "breaks down")) and not _text_contains_any(
        positive_prompt,
        ("sequence", "breaking", "broken", "soil layer", "intact"),
    ):
        issue_codes.append("DECOMPOSITION_NOT_VISIBLE")
    if "EDITORIAL_SUBJECT_TOO_SMALL" in vision_issue_codes and _text_contains_any(haystack, ("film", "sample", "fragment")):
        issue_codes.append("SYMBOLIC_ONLY_WHEN_LITERAL_REQUIRED")
    return list(dict.fromkeys(issue_codes))


def _food_trend_issue_codes(
    *,
    prompt_item: dict[str, object],
    vision_issue_codes: list[str],
) -> list[str]:
    visual_brief = prompt_item.get("visual_brief")
    if not isinstance(visual_brief, dict):
        return []
    domain = str(visual_brief.get("domain") or "").strip().lower()
    if domain != "food_trend":
        return []
    positive_prompt = str(prompt_item.get("positive_prompt") or "")
    must_show = visual_brief.get("must_show")
    must_show_text = " ".join(item for item in must_show if isinstance(item, str)) if isinstance(must_show, list) else ""
    haystack = f"{positive_prompt} {must_show_text} {visual_brief.get('composition_template', '')}"
    issue_codes: list[str] = []
    if _text_contains_any(haystack, ("ube", "purple", "yam")) and "FOOD_TREND_PURPLE_ACCENT_WEAK" in vision_issue_codes:
        issue_codes.append("MISSING_UBE_COLOR_SIGNAL")
    if _text_contains_any(haystack, ("dessert", "drink", "cake", "latte", "bakery", "cafe")) and "FOOD_TREND_SUBJECT_TOO_SMALL" in vision_issue_codes:
        issue_codes.append("FOOD_PRODUCT_NOT_DOMINANT")
    if _text_contains_any(haystack, ("shelf", "retail", "supermarket", "convenience", "display", "packaged")) and any(
        code in vision_issue_codes for code in ("FOOD_TREND_EMPTY_INTERIOR", "FOOD_TREND_GENERIC_INTERIOR")
    ):
        issue_codes.append("RETAIL_CONTEXT_NOT_VISIBLE")
    return list(dict.fromkeys(issue_codes))


def _scene_family_repeat_penalty(
    *,
    project: ProjectRecord,
    sentence_idx: int,
    prompt_item: dict[str, object],
) -> float:
    visual_brief = prompt_item.get("visual_brief")
    visual_plan = prompt_item.get("visual_plan")
    if not isinstance(visual_brief, dict) or not isinstance(visual_plan, dict):
        return 0.0
    prompt_index = _manifest_prompt_item_by_idx(project)
    if not prompt_index:
        return 0.0
    current_visual_mode = str(visual_brief.get("visual_mode") or "").strip().lower()
    current_scene_anchor = str(visual_brief.get("scene_anchor") or visual_plan.get("scene_anchor") or "").strip().lower()
    current_hero_subject = str(visual_brief.get("hero_subject") or visual_plan.get("hero_subject") or "").strip().lower()
    current_composition = str(visual_brief.get("composition_template") or visual_plan.get("composition_template") or "").strip().lower()
    current_anchor_type = str(
        visual_brief.get("semantic_anchor_type") or visual_plan.get("semantic_anchor_type") or ""
    ).strip().lower()
    current_anchor_tokens_raw = visual_brief.get("semantic_anchor_tokens") or visual_plan.get("semantic_anchor_tokens")
    current_anchor_tokens = {
        str(item).strip().lower()
        for item in current_anchor_tokens_raw
        if isinstance(item, str) and item.strip()
    } if isinstance(current_anchor_tokens_raw, list) else set()

    penalty = 0.0
    for previous_idx in range(max(0, sentence_idx - 2), sentence_idx):
        previous_item = prompt_index.get(previous_idx)
        if not isinstance(previous_item, dict):
            continue
        previous_brief = previous_item.get("visual_brief")
        previous_plan = previous_item.get("visual_plan")
        if not isinstance(previous_brief, dict) or not isinstance(previous_plan, dict):
            continue
        previous_visual_mode = str(previous_brief.get("visual_mode") or "").strip().lower()
        previous_scene_anchor = str(
            previous_brief.get("scene_anchor") or previous_plan.get("scene_anchor") or ""
        ).strip().lower()
        previous_hero_subject = str(
            previous_brief.get("hero_subject") or previous_plan.get("hero_subject") or ""
        ).strip().lower()
        previous_composition = str(
            previous_brief.get("composition_template") or previous_plan.get("composition_template") or ""
        ).strip().lower()
        previous_anchor_type = str(
            previous_brief.get("semantic_anchor_type") or previous_plan.get("semantic_anchor_type") or ""
        ).strip().lower()
        previous_anchor_tokens_raw = previous_brief.get("semantic_anchor_tokens") or previous_plan.get("semantic_anchor_tokens")
        previous_anchor_tokens = {
            str(item).strip().lower()
            for item in previous_anchor_tokens_raw
            if isinstance(item, str) and item.strip()
        } if isinstance(previous_anchor_tokens_raw, list) else set()

        overlap_count = sum(
            1
            for matched in (
                current_visual_mode and current_visual_mode == previous_visual_mode,
                current_scene_anchor and current_scene_anchor == previous_scene_anchor,
                current_hero_subject and current_hero_subject == previous_hero_subject,
                current_composition and current_composition == previous_composition,
                current_anchor_type and current_anchor_type == previous_anchor_type,
            )
            if matched
        )
        if current_anchor_tokens and previous_anchor_tokens:
            overlap_count += 1 if len(current_anchor_tokens & previous_anchor_tokens) >= 2 else 0
        if overlap_count >= 4:
            penalty -= 0.18
        elif overlap_count == 3:
            penalty -= 0.12
        elif overlap_count == 2:
            penalty -= 0.06
    return max(-0.24, penalty)


def _compute_candidate_score_details(
    *,
    project: ProjectRecord,
    source_path: Path,
    sentence_idx: int,
    prompt_item: dict[str, object],
) -> CandidateScoreDetails:
    components: dict[str, float] = {
        "coverage_pass": 0.0,
        "must_show_coverage": 0.0,
        "issue_free": 0.0,
        "literal_simile": 0.0,
        "keyword_hits": 0.0,
        "non_fallback": 0.0,
        "semantic_alignment_penalty": 0.0,
        "generic_penalty": 0.0,
        "negative_global_avoid": 0.0,
        "file_sanity": 0.0,
        "scene_variety_penalty": 0.0,
        "scene_family_repeat_penalty": 0.0,
    }
    manual_art_directed = _is_manual_art_directed_prompt(project, prompt_item)
    visual_brief = prompt_item.get("visual_brief")
    visual_plan = prompt_item.get("visual_plan")
    positive_prompt = prompt_item.get("positive_prompt")
    negative_prompt = prompt_item.get("negative_prompt")
    if isinstance(visual_brief, dict) and isinstance(positive_prompt, str) and isinstance(negative_prompt, str):
        brief = cast(VisualBrief, visual_brief)
        coverage = build_keyword_coverage(
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            brief=brief,
        )
        if coverage["passed"] is True:
            components["coverage_pass"] = 0.24
        missing_must_show = coverage.get("missing_must_show")
        if isinstance(missing_must_show, list):
            must_show = brief.get("must_show")
            total_must_show = len(must_show) if isinstance(must_show, list) and must_show else 1
            hit_count = max(0, total_must_show - len(missing_must_show))
            components["must_show_coverage"] = (hit_count / total_must_show) * 0.22
        issue_codes = coverage.get("issue_codes")
        if isinstance(issue_codes, list) and not issue_codes:
            components["issue_free"] = 0.18
        if isinstance(issue_codes, list):
            penalty_weights = {
                "RAW_TEXT_VISUAL_TARGET": 0.14,
                "GENERIC_SYMBOL_WITHOUT_ALLOW": 0.12,
                "GENERIC_FALLBACK_IN_PROMPT": 0.1,
                "GENERIC_FALLBACK_IN_MUST_SHOW": 0.1,
                "MISSING_SUBJECT_SLOT": 0.06,
            }
            semantic_penalty = sum(penalty_weights.get(str(code), 0.0) for code in issue_codes)
            if semantic_penalty:
                components["semantic_alignment_penalty"] = -min(0.24, semantic_penalty)
        visual_priority = brief.get("visual_priority")
        literal_simile = brief.get("literal_simile")
        if visual_priority == "literal_simile" and isinstance(literal_simile, str) and literal_simile.strip():
            components["literal_simile"] = 0.08
        primary_keywords = brief.get("primary_keywords")
        if isinstance(primary_keywords, list):
            keyword_hits = sum(
                1
                for item in primary_keywords[:3]
                if isinstance(item, str) and item.strip() and item.lower() in positive_prompt.lower()
            )
            components["keyword_hits"] = min(0.08, keyword_hits * 0.03)
    if isinstance(visual_plan, dict):
        if visual_plan.get("source") == "fallback":
            components["non_fallback"] = -0.08
        else:
            components["non_fallback"] = 0.08
        primary_keywords = visual_plan.get("primary_keywords")
        if isinstance(primary_keywords, list):
            generic_hits = sum(
                1
                for item in primary_keywords
                if isinstance(item, str)
                and item.strip().lower() in {"compass on a folded map", "large checklist with three bold check marks"}
            )
            if generic_hits:
                components["generic_penalty"] = -min(0.1, generic_hits * 0.05)
        symbolic_marker = str(visual_plan.get("symbolic_marker") or "").strip().lower()
        if symbolic_marker in {"sharp alarm clock", "large checklist with three bold check marks"}:
            components["generic_penalty"] -= 0.08
    visual_mode = ""
    if isinstance(visual_brief, dict):
        visual_mode = str(visual_brief.get("visual_mode") or "").strip().lower()
    prompt_haystack = f"{positive_prompt or ''} {str(prompt_item.get('style_hint') or '')}".lower()
    office_hits = sum(
        1
        for term in ("office", "desk", "monitor", "screen", "workstation", "conference room")
        if term in prompt_haystack
    )
    if visual_mode in {"simple_explainer", "data_diagram", "symbolic_concept"} and office_hits:
        components["scene_variety_penalty"] = -min(0.16, 0.05 * office_hits)
    elif manual_art_directed:
        components["non_fallback"] = 0.0
        components["manual_art_direction"] = 0.25
    components["scene_family_repeat_penalty"] = _scene_family_repeat_penalty(
        project=project,
        sentence_idx=sentence_idx,
        prompt_item=prompt_item,
    )
    essay_vocab = load_domain_vocab("essay")
    global_avoid = domain_global_avoid(essay_vocab)
    if isinstance(negative_prompt, str) and global_avoid:
        included = sum(1 for item in global_avoid if item.lower() in negative_prompt.lower())
        components["negative_global_avoid"] = min(0.08, included / len(global_avoid) * 0.08)
    brief_domain = ""
    if isinstance(visual_brief, dict):
        brief_domain = str(visual_brief.get("domain") or "").strip().lower()
    science_editorial = brief_domain in {"agriculture_environment", "science_materials"}
    food_editorial = brief_domain == "food_trend"
    editorial_symbolic = False
    if isinstance(visual_brief, dict):
        rationale = str(visual_brief.get("rationale") or "").lower()
        editorial_symbolic = "style_preset=editorial_symbolic" in rationale or brief_domain == "ai_policy_conflict"
    size_divisor = 3_000_000 if manual_art_directed or science_editorial or editorial_symbolic else 5_000_000
    if food_editorial:
        size_divisor = 4_000_000
    size_norm = min(1.0, source_path.stat().st_size / size_divisor)
    components["file_sanity"] = size_norm * 0.04
    score = _clamp_score(sum(components.values()))
    score_version = SCORE_VERSION
    if science_editorial:
        score_version = f"{SCORE_VERSION}:{brief_domain}_v1"
    if food_editorial:
        score_version = f"{SCORE_VERSION}:food_trend_v1"
    if editorial_symbolic:
        score_version = f"{SCORE_VERSION}:editorial_symbolic_v1"
    if manual_art_directed:
        score_version = f"{SCORE_VERSION}:manual_art_directed_v1"
    return {
        "score": score,
        "score_version": score_version,
        "score_components": components,
    }


def _compute_candidate_score(
    *,
    project: ProjectRecord,
    source_path: Path,
    sentence_idx: int,
    prompt_item: dict[str, object],
) -> float:
    return _compute_candidate_score_details(
        project=project,
        source_path=source_path,
        sentence_idx=sentence_idx,
        prompt_item=prompt_item,
    )["score"]


def _select_best_candidate(group_items: list[dict[str, object]], *, fallback: dict[str, object]) -> CandidateSelectionDecision:
    best_candidate = max(
        (item for item in group_items if isinstance(item, dict)),
        key=lambda item: to_float(item.get("candidate_score", 0.0), 0.0),
        default=fallback,
    )
    selected_path = str(best_candidate.get("path", fallback.get("path", "")))
    selected_prompt = str(best_candidate.get("prompt", fallback.get("prompt", "")))
    selected_prompt_id = str(best_candidate.get("prompt_id", fallback.get("prompt_id", "")))
    selected_index = to_int(best_candidate.get("candidate_index", fallback.get("candidate_index", 1)), 1)
    selected_total = to_int(best_candidate.get("candidate_total", fallback.get("candidate_total", 1)), 1)
    selected_score = to_float(best_candidate.get("candidate_score", fallback.get("candidate_score", 0.0)), 0.0)
    selected_score_version = str(best_candidate.get("candidate_score_version", fallback.get("candidate_score_version", SCORE_VERSION)))
    strict_domain = "ev_battery" in selected_score_version
    raw_issue_codes = best_candidate.get("vision_qa_issue_codes")
    issue_codes = [str(item) for item in raw_issue_codes] if isinstance(raw_issue_codes, list) else []
    retry_threshold = STRICT_DOMAIN_SCORE_THRESHOLD if strict_domain else RETRY_SCORE_THRESHOLD
    if strict_domain and "IMAGE_SEMANTIC_MATCH_TOO_LOW" in issue_codes:
        selection_reason = f"auto_score_v2:{selected_score:.2f}:semantic_retry_recommended"
        retry_recommended = True
        retry_reason = "strict_domain_semantic_mismatch"
    elif selected_score < retry_threshold:
        selection_reason = f"auto_score_v2:{selected_score:.2f}:retry_recommended"
        retry_recommended = True
        retry_reason = "strict_domain_low_candidate_score" if strict_domain else "low_candidate_score"
    elif selected_score < STRONG_SCORE_THRESHOLD:
        selection_reason = f"auto_score_v2:{selected_score:.2f}:borderline"
        retry_recommended = True
        retry_reason = "borderline_candidate"
    else:
        selection_reason = f"auto_score_v2:{selected_score:.2f}"
        retry_recommended = False
        retry_reason = ""
    return {
        "selected_path": selected_path,
        "selected_prompt": selected_prompt,
        "selected_prompt_id": selected_prompt_id,
        "selected_index": selected_index,
        "selected_total": selected_total,
        "selected_score": selected_score,
        "selected_score_version": selected_score_version,
        "selection_reason": selection_reason,
        "retry_recommended": retry_recommended,
        "retry_reason": retry_reason,
    }


def import_history_image(
    project: ProjectRecord,
    *,
    prompt_id: str,
    sentence_idx: int,
    prompt: str,
    manifest_sentence_hash: str = "",
    candidate_index: int = 1,
    candidate_total: int = 1,
    selected_reason: str = "",
    template_id: str = "",
    generation_profile: str = "",
    style_reference_image: str = "",
    lora_name: str = "",
    width: int = 0,
    height: int = 0,
    prompt_item_override: dict[str, object] | None = None,
    install_dir: Path = COMFYUI_INSTALL_DIR,
) -> tuple[ProjectRecord, str, str]:
    history = ComfyUIClient().get_history(prompt_id)
    images = ComfyUIClient().extract_image_results(history, prompt_id)
    if not images:
        raise HTTPException(404, "ComfyUI history does not contain any generated images.")
    source_path = resolve_comfy_output_path(images[0], install_dir)
    media_dir = db.project_dir(project["id"]) / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    target_path = _unique_media_path(media_dir, source_path.name)
    shutil.copy2(source_path, target_path)

    media_order = list(project["media_order"])
    media_order.append(target_path.name)
    mappings = list(project["body_image_mappings"])
    options = dict(project["body_image_options"])
    raw_candidate_groups = options.get("candidate_groups", {})
    candidate_groups: dict[str, list[dict[str, object]]] = {}
    if isinstance(raw_candidate_groups, dict):
        for key, value in raw_candidate_groups.items():
            if isinstance(key, str) and isinstance(value, list):
                candidate_groups[key] = [item for item in value if isinstance(item, dict)]
    raw_candidate_reviews = options.get("candidate_reviews", {})
    candidate_reviews: dict[str, dict[str, object]] = {}
    if isinstance(raw_candidate_reviews, dict):
        for key, value in raw_candidate_reviews.items():
            if isinstance(key, str) and isinstance(value, dict):
                candidate_reviews[key] = dict(value)
    sentence_text = project["sentences"][sentence_idx] if 0 <= sentence_idx < len(project["sentences"]) else ""
    prompt_item = prompt_item_override if isinstance(prompt_item_override, dict) and prompt_item_override else _manifest_prompt_item(project, sentence_idx)
    candidate_score_details = _compute_candidate_score_details(
        project=project,
        source_path=source_path,
        sentence_idx=sentence_idx,
        prompt_item=prompt_item,
    )
    previous_image_path = _previous_selected_media_path(project, sentence_idx)
    visual_brief = prompt_item.get("visual_brief")
    style_mode = ""
    if isinstance(visual_brief, dict):
        visual_mode = str(visual_brief.get("visual_mode") or "").strip().lower()
        if visual_mode in {"simple_explainer", "data_diagram"}:
            style_mode = "simple_diagram"
        elif visual_mode == "symbolic_concept":
            style_mode = "editorial_symbolic"
        if str(visual_brief.get("domain") or "") == "news_explainer":
            style_mode = "simple_diagram"
        elif str(visual_brief.get("domain") or "") in {"agriculture_environment", "science_materials"}:
            style_mode = "editorial_science"
        elif str(visual_brief.get("domain") or "") == "food_trend":
            style_mode = "food_trend_editorial"
        elif str(visual_brief.get("domain") or "") == "ai_policy_conflict":
            style_mode = "editorial_symbolic"
        elif "style_preset=editorial_symbolic" in str(visual_brief.get("rationale") or "").lower():
            style_mode = "editorial_symbolic"
        elif "style_preset=simple_diagram" in str(visual_brief.get("rationale") or "").lower():
            style_mode = "simple_diagram"
    vision_qa = analyze_image_quality(target_path, previous_image_path=previous_image_path, style_mode=style_mode)
    science_issue_codes = _editorial_science_issue_codes(
        prompt_item=prompt_item,
        vision_issue_codes=vision_qa["issue_codes"],
    )
    if science_issue_codes:
        merged_codes = list(dict.fromkeys([*vision_qa["issue_codes"], *science_issue_codes]))
        vision_qa["issue_codes"] = merged_codes
        science_penalty = min(0.16, 0.04 * len(science_issue_codes))
        vision_qa["components"]["editorial_science_prompt_penalty"] = -science_penalty
        vision_qa["score"] = _clamp_score(vision_qa["score"] - science_penalty)
        vision_qa["reason"] = "editorial_science_issue_codes"
    food_issue_codes = _food_trend_issue_codes(
        prompt_item=prompt_item,
        vision_issue_codes=vision_qa["issue_codes"],
    )
    if food_issue_codes:
        merged_codes = list(dict.fromkeys([*vision_qa["issue_codes"], *food_issue_codes]))
        vision_qa["issue_codes"] = merged_codes
        food_penalty = min(0.16, 0.04 * len(food_issue_codes))
        vision_qa["components"]["food_trend_prompt_penalty"] = -food_penalty
        vision_qa["score"] = _clamp_score(vision_qa["score"] - food_penalty)
        vision_qa["reason"] = "food_trend_issue_codes"
    editorial_symbolic_issue_codes = [
        code
        for code in vision_qa["issue_codes"]
        if code
        in {
            "EDITORIAL_FLAT_SHAPE_ONLY",
            "EDITORIAL_CLUTTERED_SYMBOLS",
            "GENERIC_DASHBOARD_LAYOUT",
            "TINY_ICON_GRID",
        }
    ]
    if style_mode == "editorial_symbolic" and editorial_symbolic_issue_codes:
        editorial_penalty = min(0.18, 0.05 * len(editorial_symbolic_issue_codes))
        vision_qa["components"]["editorial_symbolic_prompt_penalty"] = -editorial_penalty
        vision_qa["score"] = _clamp_score(vision_qa["score"] - editorial_penalty)
        vision_qa["reason"] = "editorial_symbolic_issue_codes"
    if _is_manual_art_directed_prompt(project, prompt_item):
        candidate_score = _clamp_score((candidate_score_details["score"] * 0.50) + (vision_qa["score"] * 0.50))
    else:
        candidate_score = _clamp_score((candidate_score_details["score"] * 0.85) + (vision_qa["score"] * 0.15))
    mapping: BodyImageMapping = {
        "sentence_idx": sentence_idx,
        "path": target_path.name,
        "prompt": prompt,
        "sentence_text": sentence_text,
        "sentence_hash": sentence_hash(sentence_text),
        "project_id": project["id"],
        "prompt_id": prompt_id,
        "manifest_sentence_hash": manifest_sentence_hash,
        "selected_reason": selected_reason or ("only_candidate" if candidate_total <= 1 else ""),
        "candidate_index": candidate_index,
        "candidate_total": candidate_total,
        "candidate_score": candidate_score,
        "candidate_score_version": candidate_score_details["score_version"],
    }
    group_key = str(sentence_idx)
    group_items = candidate_groups.get(group_key, [])
    candidate_entry = {
        "path": target_path.name,
        "prompt": prompt,
        "prompt_id": prompt_id,
        "sentence_hash": manifest_sentence_hash or sentence_hash(sentence_text),
        "candidate_index": candidate_index,
        "candidate_total": candidate_total,
        "candidate_score": candidate_score,
        "candidate_score_version": candidate_score_details["score_version"],
        "candidate_score_components": candidate_score_details["score_components"],
        "vision_qa_score": vision_qa["score"],
        "vision_qa_version": vision_qa["version"],
        "vision_qa_reason": vision_qa["reason"],
        "vision_qa_issue_codes": vision_qa["issue_codes"],
        "vision_qa_components": vision_qa["components"],
        "template_id": template_id,
        "generation_profile": generation_profile,
        "style_reference_image": style_reference_image,
        "lora_name": lora_name,
        "width": width,
        "height": height,
        "selected": False,
        "strict_retry_attempted": False,
    }
    if selected_reason == "strict_retry":
        candidate_entry["strict_retry_attempted"] = True
    group_items.append(candidate_entry)
    decision = _select_best_candidate(group_items, fallback=candidate_entry)
    updated_group_items: list[dict[str, object]] = []
    for item in group_items:
        if not isinstance(item, dict):
            continue
        item = dict(item)
        item["selected"] = str(item.get("path", "")) == decision["selected_path"]
        updated_group_items.append(item)
    candidate_groups[group_key] = updated_group_items
    options["candidate_groups"] = candidate_groups
    selected_candidate_item = _selected_candidate_item(updated_group_items) or candidate_entry
    selected_issue_codes = selected_candidate_item.get("vision_qa_issue_codes")
    resolved_issue_codes = list(selected_issue_codes) if isinstance(selected_issue_codes, list) else list(vision_qa["issue_codes"])
    if decision["retry_reason"] == "borderline_candidate" and "BORDERLINE_CANDIDATE" not in resolved_issue_codes:
        resolved_issue_codes.append("BORDERLINE_CANDIDATE")
    selected_components = selected_candidate_item.get("vision_qa_components")
    resolved_components = dict(selected_components) if isinstance(selected_components, dict) else dict(vision_qa["components"])
    selected_score_components = selected_candidate_item.get("candidate_score_components")
    resolved_score_components = (
        dict(selected_score_components)
        if isinstance(selected_score_components, dict)
        else dict(candidate_score_details["score_components"])
    )
    candidate_reviews[group_key] = {
        "best_path": decision["selected_path"],
        "best_score": decision["selected_score"],
        "score_version": decision["selected_score_version"],
        "score_component_summary": resolved_score_components,
        "retry_recommended": decision["retry_recommended"],
        "retry_reason": decision["retry_reason"],
        "selection_reason": decision["selection_reason"],
        "vision_qa_score": to_float(selected_candidate_item.get("vision_qa_score"), vision_qa["score"]),
        "vision_qa_version": str(selected_candidate_item.get("vision_qa_version") or vision_qa["version"]),
        "vision_qa_reason": str(selected_candidate_item.get("vision_qa_reason") or vision_qa["reason"]),
        "vision_qa_issue_codes": resolved_issue_codes,
        "vision_qa_components": resolved_components,
        "strict_retry_attempted": bool(selected_candidate_item.get("strict_retry_attempted") is True),
    }
    candidate_reviews = _refresh_style_consistency_reviews(candidate_groups, candidate_reviews)
    options["candidate_reviews"] = candidate_reviews
    filtered_mappings = [item for item in mappings if item["sentence_idx"] != sentence_idx]
    filtered_mappings.append(
        {
            "sentence_idx": sentence_idx,
            "path": decision["selected_path"],
            "prompt": decision["selected_prompt"],
            "sentence_text": sentence_text,
            "sentence_hash": sentence_hash(sentence_text),
            "project_id": project["id"],
            "prompt_id": decision["selected_prompt_id"],
            "manifest_sentence_hash": manifest_sentence_hash,
            "selected_reason": selected_reason or ("only_candidate" if decision["selected_total"] <= 1 else decision["selection_reason"]),
            "candidate_index": decision["selected_index"],
            "candidate_total": decision["selected_total"],
            "candidate_score": decision["selected_score"],
            "candidate_score_version": decision["selected_score_version"],
            "vision_qa_issue_codes": resolved_issue_codes,
        }
    )
    batch_items = options.get("batch_items")
    is_batch_import = isinstance(batch_items, list) and any(isinstance(item, dict) for item in batch_items)
    update_fields: dict[str, object] = {
        "media_order": media_order,
        "body_image_mappings": filtered_mappings,
        "body_image_options": options,
    }
    if not is_batch_import:
        update_fields.update(
            {
                "body_image_state": "done",
                "body_image_progress": 100,
                "body_image_error": "",
                "body_image_phase": "done",
                "body_image_last_log": "",
            }
        )
    updated_project = db.update_project(
        project["id"],
        **update_fields,
    )
    if updated_project is None:
        raise HTTPException(404, f"project {project['id']} not found")
    return updated_project, target_path.name, str(source_path)


def submit_template(
    *,
    template_id: str,
    placeholders: PlaceholderMap,
    client_id: str,
    timeout_sec: int = 30,
) -> str:
    workflow = render_workflow_template(template_id, placeholders)
    submission = ComfyUIClient(timeout_sec=timeout_sec).submit_workflow(workflow, client_id=client_id)
    return submission.prompt_id
