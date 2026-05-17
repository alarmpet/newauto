import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from ..types import VisualBrief
from .literal_simile import extract_literal_simile
from .prompt_compiler import GENERIC_DRIFT_TERMS, GENERIC_FALLBACK_TERMS, check_prompt_compliance
from .visual_vocab import domain_global_avoid, load_domain_vocab

_GENERIC_PRIMARY_TERMS = {
    "large checklist with three bold check marks",
    "compass on a folded map",
    "quiet road fork",
    "single signpost",
}
_ROAD_TERMS = (" road", "street", "path", "crossroads", "highway", "intersection")
_VEHICLE_TERMS = ("car", "vehicle", "traffic")
_BOOK_TEXT_TERMS = ("book", "notebook", "page", "document", "paper", "screen", "phone")
_TEXT_CONTROL_TERMS = ("no readable text", "readable text", "letters", "scribbles", "watermark")
_READABLE_TEXT_CONTROL_TERMS = ("no readable text", "readable text", "letters", "alphabet", "messy handwriting", "scribbles")
_CLOSEUP_RISK_TERMS = (
    "hand only",
    "hand-only",
    "phone screen closeup",
    "extreme close-up",
    "macro",
    "cropped limb",
    "detached limb",
    "arm-only",
)
_TECHNICAL_ANCHORS = ("35mm", "50mm", "sharp focus", "natural color", "detailed real-world textures")
_DIAGRAM_STYLE_COLLISION_TERMS = (
    "35mm lens",
    "50mm lens",
    "sharp focus",
    "natural color",
    "detailed real-world textures",
    "cinematic editorial photography",
    "photorealistic",
    "realistic skin",
    "3d render",
)
_DIAGRAM_TEXT_TERMS = ("readable text", "letters", "messy handwriting", "watermark")
_DIAGRAM_COMPLEXITY_TERMS = (
    "crowd",
    "multiple characters",
    "dense background",
    "room interior photo",
    "detailed landscape",
    "hand only closeup",
    "phone screen closeup only",
)
_NEWS_GENERIC_DIAGRAM_TERMS = (
    "abstract radar dashboard",
    "dense analytics dashboard",
    "tiny scattered icons",
    "decorative circuit board",
    "generic blueprint interface",
    "complex infographic grid",
)
_FOOD_REQUIRED_TERMS = (
    "ube",
    "purple",
    "yam",
    "dessert",
    "drink",
    "bakery",
    "cafe",
    "retail",
    "shelf",
    "supermarket",
    "shipping",
    "philippines",
)
_EV_BATTERY_REQUIRED_TERMS = (
    "battery",
    "battery cell",
    "electric vehicle",
    "ev",
    "lfp",
    "ncm",
    "solid-state",
    "solid state",
    "price barrier",
    "fire safety",
    "energy density",
    "charging",
    "cathode",
)
_EV_BATTERY_FORBIDDEN_STYLE_TERMS = (
    "stick figure",
    "stickfigures",
    "flipchartvisu",
    "cartoon mascot",
)


def _allowed_objects(brief: VisualBrief) -> list[str]:
    allow_objects = brief.get("allow_objects")
    if not isinstance(allow_objects, list):
        return []
    return [
        item.strip().lower()
        for item in allow_objects
        if isinstance(item, str) and item.strip()
    ]


def _has_raw_visual_text(brief: VisualBrief) -> bool:
    for key in ("primary_prop", "secondary_prop", "action", "scene"):
        value = brief.get(key)
        if isinstance(value, str) and any("\uac00" <= char <= "\ud7a3" for char in value):
            return True
    return False


def _is_simple_diagram_brief(brief: VisualBrief) -> bool:
    rationale = str(brief.get("rationale", "")).lower()
    return "style_preset=simple_diagram" in rationale


def build_keyword_coverage(
    *,
    positive_prompt: str,
    negative_prompt: str,
    brief: VisualBrief,
) -> dict[str, object]:
    missing = check_prompt_compliance(positive_prompt, brief)
    non_blocklist_missing = [
        item
        for item in missing
        if isinstance(item, str) and not item.startswith("BLOCKLIST:")
    ]
    blocklist_hits = [
        item.split(":", 1)[1]
        for item in missing
        if isinstance(item, str) and item.startswith("BLOCKLIST:")
    ]
    avoid_hits = [
        item
        for item in brief["avoid"]
        if item.strip() and item.lower() in negative_prompt.lower()
    ]
    issue_codes: list[str] = []
    domain = str(brief.get("domain", "")).strip().lower()
    positive_lower = positive_prompt.lower()
    negative_lower = negative_prompt.lower()
    must_show_lower = " ".join(
        item.lower()
        for item in brief["must_show"]
        if isinstance(item, str)
    )
    if any(term in must_show_lower for term in GENERIC_FALLBACK_TERMS):
        issue_codes.append("GENERIC_FALLBACK_IN_MUST_SHOW")
    if any(term in positive_lower for term in GENERIC_FALLBACK_TERMS):
        issue_codes.append("GENERIC_FALLBACK_IN_PROMPT")
    is_simple_diagram = _is_simple_diagram_brief(brief)
    if is_simple_diagram:
        if any(term in positive_lower for term in _DIAGRAM_STYLE_COLLISION_TERMS):
            issue_codes.append("DIAGRAM_STYLE_COLLISION")
        if not all(term in negative_lower for term in _DIAGRAM_TEXT_TERMS):
            issue_codes.append("DIAGRAM_TEXT_CONTROL_MISSING")
        if any(term in positive_lower for term in _DIAGRAM_COMPLEXITY_TERMS):
            issue_codes.append("DIAGRAM_COMPLEXITY_RISK")
        if domain == "news_explainer":
            composition_template = str(brief.get("composition_template", "")).strip()
            if not composition_template:
                issue_codes.append("NEWS_DIAGRAM_TOO_GENERIC")
            if "comment" not in positive_lower and "댓글" not in positive_lower:
                issue_codes.append("NEWS_COMMENT_PANEL_MISSING")
            if any(term in positive_lower for term in _NEWS_GENERIC_DIAGRAM_TERMS):
                issue_codes.append("DENSE_DASHBOARD_RISK")
            if composition_template == "SpikeDetection" and not all(term in positive_lower for term in ("counter", "warning")):
                issue_codes.append("REACTION_SPIKE_NOT_DOMINANT")
            if composition_template == "UserView" and "user" not in positive_lower:
                issue_codes.append("USER_VIEWPOINT_MISSING")
            if composition_template == "LimitationShield" and "shield" not in positive_lower:
                issue_codes.append("LIMITATION_METAPHOR_MISSING")
    if domain == "essay" and not is_simple_diagram:
        essay_vocab = load_domain_vocab("essay")
        global_avoid = domain_global_avoid(essay_vocab)
        missing_forbidden = [
            item for item in global_avoid if item.lower() not in negative_prompt.lower()
        ]
        if missing_forbidden:
            issue_codes.append("FORBIDDEN_OBJECT_IN_NEGATIVE_MISSING")
        allowed = _allowed_objects(brief)
        if any(term in positive_lower for term in _ROAD_TERMS) and not any(item in allowed for item in _VEHICLE_TERMS):
            if not all(item in negative_lower for item in _VEHICLE_TERMS):
                issue_codes.append("ESSAY_ROAD_WITHOUT_VEHICLE_BAN")
        drift_hits = [
            item
            for item in GENERIC_DRIFT_TERMS
            if item not in allowed and item in positive_lower
        ]
        if drift_hits:
            issue_codes.append("GENERIC_SYMBOL_WITHOUT_ALLOW")
        if _has_raw_visual_text(brief):
            issue_codes.append("RAW_TEXT_VISUAL_TARGET")
        if any(term in positive_lower for term in _BOOK_TEXT_TERMS) and not any(term in negative_lower for term in _READABLE_TEXT_CONTROL_TERMS):
            issue_codes.append("BOOK_TEXT_RISK")
        if any(term in positive_lower for term in _CLOSEUP_RISK_TERMS):
            issue_codes.append("CLOSEUP_RISK")
        if not str(brief.get("main_subject", "")).strip():
            issue_codes.append("MISSING_SUBJECT_SLOT")
        if not str(brief.get("scene", "")).strip():
            issue_codes.append("MISSING_ENVIRONMENT_SLOT")
        if not any(anchor in positive_lower for anchor in ("wide shot", "medium wide", "medium shot", "establishing shot")):
            issue_codes.append("MISSING_FRAMING_SLOT")
        if not any(anchor in positive_lower for anchor in _TECHNICAL_ANCHORS):
            issue_codes.append("MISSING_CAMERA_TECHNICAL_SLOT")
        core_meaning = str(brief.get("core_meaning", "")).strip()
        simile_phrase = str(brief.get("literal_simile", "")).strip() or extract_literal_simile(core_meaning)
        if simile_phrase:
            simile_lower = simile_phrase.lower()
            must_show = brief.get("must_show")
            simile_reflected = simile_lower in positive_lower
            if isinstance(must_show, list):
                simile_reflected = simile_reflected or any(
                    isinstance(item, str) and item.lower() in positive_lower
                    for item in must_show
                )
            if not simile_reflected:
                issue_codes.append("LITERAL_SIMILE_IGNORED")
    if domain == "food_trend":
        if not any(term in positive_lower for term in _FOOD_REQUIRED_TERMS):
            issue_codes.append("FOOD_TREND_CORE_VISUAL_MISSING")
        if any(term in positive_lower for term in ("empty living room", "quiet realistic room", "gear mechanism", "abstract industry")):
            issue_codes.append("FOOD_TREND_GENERIC_DRIFT")
    if domain == "ev_battery":
        ev_haystack = f"{positive_lower} {must_show_lower}"
        if not any(term in ev_haystack for term in _EV_BATTERY_REQUIRED_TERMS):
            issue_codes.append("EV_BATTERY_CORE_VISUAL_MISSING")
        if any(term in ev_haystack for term in _EV_BATTERY_FORBIDDEN_STYLE_TERMS):
            issue_codes.append("EV_BATTERY_STICKFIGURE_STYLE_BLOCKED")
    return {
        "passed": not non_blocklist_missing and not blocklist_hits and not issue_codes,
        "missing_must_show": non_blocklist_missing,
        "blocklist_hits": blocklist_hits,
        "avoid_hits": avoid_hits,
        "issue_codes": issue_codes,
    }


def build_prompt_quality_report(prompts: list[dict[str, object]]) -> dict[str, object]:
    primary_terms: list[str] = []
    repeated_scene_phrases: list[str] = []
    fallback_count = 0
    forbidden_in_negative_count = 0
    road_without_vehicle_ban_count = 0
    literal_simile_ignored_count = 0
    generic_symbol_without_allow_count = 0
    raw_text_visual_target_count = 0
    book_text_risk_count = 0
    closeup_risk_count = 0
    diagram_style_collision_count = 0
    diagram_text_control_missing_count = 0
    diagram_complexity_risk_count = 0
    news_issue_count = 0
    generic_must_show_terms: list[str] = []
    generic_fallback_issue_count = 0
    food_trend_issue_count = 0
    ev_battery_issue_count = 0
    for prompt in prompts:
        visual_brief = prompt.get("visual_brief")
        if not isinstance(visual_brief, dict):
            continue
        visual_plan = prompt.get("visual_plan")
        if isinstance(visual_plan, dict) and visual_plan.get("source") == "fallback":
            fallback_count += 1
        primary_prop = visual_brief.get("primary_prop")
        if isinstance(primary_prop, str) and primary_prop.strip():
            primary_terms.append(primary_prop.strip().lower())
            if primary_prop.strip().lower() in _GENERIC_PRIMARY_TERMS:
                generic_must_show_terms.append(primary_prop.strip().lower())
        positive_prompt = prompt.get("positive_prompt")
        if isinstance(positive_prompt, str):
            repeated_scene_phrases.extend(
                phrase
                for phrase in (
                    "phone screen closeup only",
                    "hand only closeup",
                    "multiple characters",
                    "inside a simple room",
                )
                if phrase in positive_prompt.lower()
            )
        keyword_coverage = prompt.get("keyword_coverage")
        if isinstance(keyword_coverage, dict):
            issue_codes = keyword_coverage.get("issue_codes")
            if isinstance(issue_codes, list):
                for item in issue_codes:
                    if item == "FORBIDDEN_OBJECT_IN_NEGATIVE_MISSING":
                        forbidden_in_negative_count += 1
                    elif item == "ESSAY_ROAD_WITHOUT_VEHICLE_BAN":
                        road_without_vehicle_ban_count += 1
                    elif item == "LITERAL_SIMILE_IGNORED":
                        literal_simile_ignored_count += 1
                    elif item == "GENERIC_SYMBOL_WITHOUT_ALLOW":
                        generic_symbol_without_allow_count += 1
                    elif item == "RAW_TEXT_VISUAL_TARGET":
                        raw_text_visual_target_count += 1
                    elif item == "BOOK_TEXT_RISK":
                        book_text_risk_count += 1
                    elif item == "CLOSEUP_RISK":
                        closeup_risk_count += 1
                    elif item == "DIAGRAM_STYLE_COLLISION":
                        diagram_style_collision_count += 1
                    elif item == "DIAGRAM_TEXT_CONTROL_MISSING":
                        diagram_text_control_missing_count += 1
                    elif item == "DIAGRAM_COMPLEXITY_RISK":
                        diagram_complexity_risk_count += 1
                    elif item in {
                        "NEWS_DIAGRAM_TOO_GENERIC",
                        "NEWS_COMMENT_PANEL_MISSING",
                        "REACTION_SPIKE_NOT_DOMINANT",
                        "USER_VIEWPOINT_MISSING",
                        "LIMITATION_METAPHOR_MISSING",
                        "DENSE_DASHBOARD_RISK",
                    }:
                        news_issue_count += 1
                    elif item in {"GENERIC_FALLBACK_IN_MUST_SHOW", "GENERIC_FALLBACK_IN_PROMPT"}:
                        generic_fallback_issue_count += 1
                    elif item in {"FOOD_TREND_CORE_VISUAL_MISSING", "FOOD_TREND_GENERIC_DRIFT"}:
                        food_trend_issue_count += 1
                    elif item in {"EV_BATTERY_CORE_VISUAL_MISSING", "EV_BATTERY_STICKFIGURE_STYLE_BLOCKED"}:
                        ev_battery_issue_count += 1
    duplicates = [term for term, count in Counter(primary_terms).items() if count >= 3]
    generic_must_show_repeats = [
        term for term, count in Counter(generic_must_show_terms).items() if count >= 3
    ]
    generic_repeats = [term for term, count in Counter(repeated_scene_phrases).items() if count >= 2]
    fallback_rate = fallback_count / len(prompts) if prompts else 0.0
    project_issue_codes: list[str] = []
    if fallback_rate > 0.2:
        project_issue_codes.append("FALLBACK_RATE_HIGH")
    if generic_must_show_repeats:
        project_issue_codes.append("GENERIC_MUST_SHOW_REPEATED")
    if generic_symbol_without_allow_count:
        project_issue_codes.append("GENERIC_SYMBOL_WITHOUT_ALLOW")
    if raw_text_visual_target_count:
        project_issue_codes.append("RAW_TEXT_VISUAL_TARGET")
    if book_text_risk_count:
        project_issue_codes.append("BOOK_TEXT_RISK")
    if closeup_risk_count:
        project_issue_codes.append("CLOSEUP_RISK")
    if diagram_style_collision_count:
        project_issue_codes.append("DIAGRAM_STYLE_COLLISION")
    if diagram_text_control_missing_count:
        project_issue_codes.append("DIAGRAM_TEXT_CONTROL_MISSING")
    if diagram_complexity_risk_count:
        project_issue_codes.append("DIAGRAM_COMPLEXITY_RISK")
    if news_issue_count:
        project_issue_codes.append("NEWS_EXPLAINER_PROMPT_QUALITY_FAILED")
    if generic_fallback_issue_count:
        project_issue_codes.append("GENERIC_FALLBACK_BLOCKED")
    if food_trend_issue_count:
        project_issue_codes.append("FOOD_TREND_PROMPT_QUALITY_FAILED")
    if ev_battery_issue_count:
        project_issue_codes.append("EV_BATTERY_PROMPT_QUALITY_FAILED")
    prompt_rows: list[dict[str, object]] = []
    for prompt in prompts:
        prompt_rows.append(
            {
                "sentence_idx": prompt.get("sentence_idx", -1),
                "template_key": prompt.get("template_key", ""),
                "retry_count": prompt.get("retry_count", 0),
                "keyword_coverage": prompt.get("keyword_coverage", {}),
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "prompt_count": len(prompts),
        "repeated_primary_terms": duplicates,
        "generic_must_show_repeats": generic_must_show_repeats,
        "generic_phrase_repeats": generic_repeats,
        "fallback_rate": fallback_rate,
        "fallback_rate_high": fallback_rate > 0.2,
        "forbidden_in_negative_count": forbidden_in_negative_count,
        "road_without_vehicle_ban_count": road_without_vehicle_ban_count,
        "literal_simile_ignored_count": literal_simile_ignored_count,
        "generic_symbol_without_allow_count": generic_symbol_without_allow_count,
        "raw_text_visual_target_count": raw_text_visual_target_count,
        "book_text_risk_count": book_text_risk_count,
        "closeup_risk_count": closeup_risk_count,
        "diagram_style_collision_count": diagram_style_collision_count,
        "diagram_text_control_missing_count": diagram_text_control_missing_count,
        "diagram_complexity_risk_count": diagram_complexity_risk_count,
        "news_issue_count": news_issue_count,
        "generic_fallback_issue_count": generic_fallback_issue_count,
        "food_trend_issue_count": food_trend_issue_count,
        "ev_battery_issue_count": ev_battery_issue_count,
        "project_issue_codes": project_issue_codes,
        "prompts": prompt_rows,
    }


def save_prompt_quality_report(target_path: Path, report: dict[str, object]) -> Path:
    target_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return target_path
