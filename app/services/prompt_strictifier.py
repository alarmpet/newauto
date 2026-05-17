from ..types import PromptRepairDecision, VisualBrief
from .comfyui_prompt_adapter import normalize_dual_prompt

STRICT_NEGATIVE_TERMS = [
    "abstract radar dashboard",
    "dense analytics dashboard",
    "tiny scattered icons",
    "decorative circuit board",
    "generic blueprint interface",
    "complex infographic grid",
    "radar-only dashboard",
    "tiny icon grid",
]

TEMPLATE_LAYOUTS: dict[str, str] = {
    "AlertFlow": "left platform monitor, bold alert arrow, right newsroom receiver",
    "SpikeDetection": "one article card, giant reaction counters, warning detector",
    "SortingControl": "large comment list, highlighted sort slider, reordered reaction bubbles",
    "CoordinationPressure": "many account nodes aiming at one comment box, bending public opinion scale",
    "UserView": "single user icon, news comment panel, question mark or magnifier",
    "LimitationShield": "imperfect shield with gaps, suspicious dots slipping through",
    "SpeedResponse": "threshold knobs, stopwatch, fast response arrow",
    "PreserveAndReveal": "comment panel remains visible, highlighted abnormal signal, response speed arrow",
    "PolicyPressureDual": "left senate hearing podium, right White House stop button, center AI company cube",
    "GovernmentVsCompany": "government shield, warning divider, AI company cube",
    "HearingCriticism": "senate hearing podium, defense official silhouette, warning speech bubble",
    "AccessRestriction": "White House stop button, red access barrier, branching AI model nodes",
}

GENERIC_SCAFFOLD = [
    "wide centered explainer diagram shot",
    "simple centered explainer icon composition",
    "plain warm background with generous empty space",
    "simple flat 2d explainer diagram",
    "minimal editorial cartoon",
    "calm neutral palette",
]


def _append_negative(base_text: str, additions: list[str]) -> str:
    parts = [part.strip() for part in base_text.split(",") if part.strip()]
    lowered = {part.lower() for part in parts}
    for addition in additions:
        if addition.lower() not in lowered:
            parts.append(addition)
            lowered.add(addition.lower())
    return ", ".join(parts)


def _strip_generic_scaffold(text: str) -> str:
    parts = [part.strip() for part in text.split(",") if part.strip()]
    generic = {item.lower() for item in GENERIC_SCAFFOLD}
    kept = [part for part in parts if part.lower() not in generic]
    return ", ".join(kept)


def strictify_prompt(
    *,
    positive_prompt: object,
    negative_prompt: str,
    brief: VisualBrief,
    attempt: int,
) -> PromptRepairDecision:
    dual = normalize_dual_prompt(positive_prompt)
    template_name = str(brief.get("composition_template", "")).strip()
    layout = TEMPLATE_LAYOUTS.get(template_name, "")
    must_show = [item for item in brief.get("must_show", [])[:3] if item.strip()]
    subject = str(brief.get("primary_prop", "") or brief.get("main_subject", "")).strip()
    action = str(brief.get("action", "")).strip()
    core_parts = [part for part in [layout, subject, action, *must_show] if part]
    strict_g = ", ".join(dict.fromkeys(core_parts))
    if not strict_g:
        strict_g = _strip_generic_scaffold(dual["prompt_g"])
    strict_l = "simple flat explainer illustration, clean black outline, one dominant subject, max two supporting icon groups, generous empty space, no readable text"
    strict_negative = _append_negative(negative_prompt, STRICT_NEGATIVE_TERMS)
    combined = ", ".join(part for part in [strict_g, strict_l] if part)
    return {
        "should_retry": bool(combined.strip()),
        "attempt": attempt,
        "issue_codes": ["BORDERLINE_CANDIDATE"],
        "repaired_positive_prompt": combined,
        "repaired_prompt_g": strict_g,
        "repaired_prompt_l": strict_l,
        "repaired_negative_prompt": strict_negative,
        "repair_reason": "strict_borderline_retry",
    }
