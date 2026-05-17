from ..types import PromptRepairDecision, VisualBrief
from .comfyui_prompt_adapter import normalize_dual_prompt
from .prompt_strictifier import strictify_prompt


def _append_missing_terms(base_text: str, additions: list[str]) -> str:
    lowered = base_text.lower()
    merged = base_text
    for addition in additions:
        cleaned = addition.strip()
        if not cleaned:
            continue
        if cleaned.lower() in lowered:
            continue
        merged = f"{cleaned}, {merged}" if merged else cleaned
        lowered = merged.lower()
    return merged


def _append_negative_terms(base_text: str, additions: list[str]) -> str:
    parts = [part.strip() for part in base_text.split(",") if part.strip()]
    lowered = {part.lower() for part in parts}
    for addition in additions:
        cleaned = addition.strip()
        if not cleaned:
            continue
        if cleaned.lower() in lowered:
            continue
        parts.append(cleaned)
        lowered.add(cleaned.lower())
    return ", ".join(parts)


def _rebuild_combined_prompt(prompt_g: str, prompt_l: str) -> str:
    parts: list[str] = []
    for part in (prompt_g.strip(), prompt_l.strip()):
        if part and part not in parts:
            parts.append(part)
    return ", ".join(parts)


def repair_prompts(
    *,
    positive_prompt: object,
    negative_prompt: str,
    brief: VisualBrief,
    issue_codes: list[str],
    attempt: int,
) -> PromptRepairDecision:
    if not issue_codes:
        dual_prompt = normalize_dual_prompt(positive_prompt)
        return {
            "should_retry": False,
            "attempt": attempt,
            "issue_codes": [],
            "repaired_positive_prompt": _rebuild_combined_prompt(dual_prompt["prompt_g"], dual_prompt["prompt_l"]),
            "repaired_prompt_g": dual_prompt["prompt_g"],
            "repaired_prompt_l": dual_prompt["prompt_l"],
            "repaired_negative_prompt": negative_prompt,
            "repair_reason": "empty_issue_codes_skip",
        }
    if "BORDERLINE_CANDIDATE" in issue_codes:
        return strictify_prompt(
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            brief=brief,
            attempt=attempt,
        )
    dual_prompt = normalize_dual_prompt(positive_prompt)
    positive_g = dual_prompt["prompt_g"]
    positive_l = dual_prompt["prompt_l"]
    negative = negative_prompt
    reason_parts: list[str] = []

    if "RAW_TEXT_VISUAL_TARGET" in issue_codes:
        must_show = [item for item in brief.get("must_show", [])[:2] if isinstance(item, str) and item.strip()]
        positive_g = _append_missing_terms(positive_g, must_show)
        reason_parts.append("must_show_reinforced")
    if "GENERIC_SYMBOL_WITHOUT_ALLOW" in issue_codes:
        negative = _append_negative_terms(negative, ["car", "vehicle", "compass", "checklist", "clipboard"])
        positive_g = _append_missing_terms(positive_g, ["clear subject action relationship"])
        reason_parts.append("generic_drift_blocked")
    if "DIAGRAM_STYLE_COLLISION" in issue_codes:
        negative = _append_negative_terms(
            negative,
            ["photorealistic", "cinematic lighting", "realistic skin", "3d render"],
        )
        positive_l = _append_missing_terms(positive_l, ["simple flat explainer illustration", "clean black outline"])
        reason_parts.append("diagram_style_reinforced")
    if "DIAGRAM_COMPLEXITY_RISK" in issue_codes:
        positive_g = _append_missing_terms(positive_g, ["few objects only", "one central icon with two supporting symbols"])
        negative = _append_negative_terms(negative, ["dense background", "crowd", "clutter", "tiny icons"])
        reason_parts.append("diagram_simplified")
    if "BOOK_TEXT_RISK" in issue_codes:
        negative = _append_negative_terms(negative, ["readable text", "letters", "scribbles", "watermark"])
        reason_parts.append("text_risk_blocked")
    if "CLOSEUP_RISK" in issue_codes or "MISSING_FRAMING_SLOT" in issue_codes:
        positive_g = _append_missing_terms(positive_g, ["medium wide shot", "clear full composition"])
        reason_parts.append("framing_repaired")
    if "MISSING_CAMERA_TECHNICAL_SLOT" in issue_codes:
        positive_l = _append_missing_terms(positive_l, ["35mm lens", "sharp focus", "natural color"])
        reason_parts.append("camera_anchor_added")
    if not reason_parts:
        must_show = [item for item in brief.get("must_show", [])[:2] if isinstance(item, str) and item.strip()]
        positive_g = _append_missing_terms(positive_g, [*must_show, "clear visual metaphor"])
        reason_parts.append("generic_retry_reinforcement")

    repaired_positive = _rebuild_combined_prompt(positive_g, positive_l)
    should_retry = (
        positive_g != dual_prompt["prompt_g"]
        or positive_l != dual_prompt["prompt_l"]
        or negative != negative_prompt
    ) and attempt >= 0
    return {
        "should_retry": should_retry,
        "attempt": attempt,
        "issue_codes": list(issue_codes),
        "repaired_positive_prompt": repaired_positive,
        "repaired_prompt_g": positive_g,
        "repaired_prompt_l": positive_l,
        "repaired_negative_prompt": negative,
        "repair_reason": ", ".join(reason_parts),
    }
