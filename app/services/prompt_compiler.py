import re

from ..types import SdxlDualPrompt, VisualBrief
from .visual_vocab import domain_global_avoid, load_domain_vocab

PROMPT_BLOCKLIST = [
    "running fast",
    "under heavy rain",
    "standing in front of a large door",
    "inside a simple room",
    "holding one large clear symbol that represents the sentence keyword",
]
ROAD_TERMS = (" road", "street", "path", "crossroads", "highway", "intersection")
VEHICLE_BAN_TERMS = ["car", "vehicle", "traffic"]
GENERIC_DRIFT_TERMS = [
    "car",
    "automobile",
    "vehicle",
    "truck",
    "bus",
    "traffic",
    "compass",
    "map",
    "signpost",
    "checklist",
    "clipboard",
    "magnifying glass",
    "clock",
    "calendar",
    "trophy",
    "medal",
    "graph",
    "chart",
    "coins",
    "seedling",
]
GENERIC_FALLBACK_TERMS = [
    "single everyday object in a quiet realistic room",
    "quiet realistic environment",
    "abstract representation of industry",
    "empty room",
    "generic object",
    "browser window with terminal panel and automation cursor",
    "structured data table flowing out of a browser window",
    "gpu rack cluster with glowing interconnect lines",
    "generic server room",
    "abstract network only",
    "isometric blueprint maze",
    "tiny scattered icons",
    "dense dashboard ui",
]
TEXT_RISK_NEGATIVES = [
    "readable text",
    "letters",
    "alphabet",
    "messy handwriting",
    "scribbles",
    "signature",
    "watermark",
]
FRAMING_NEGATIVES = [
    "macro",
    "extreme close-up",
    "cropped",
    "cut off",
    "detached limb",
    "arm-only",
    "hand-only closeup",
    "out of frame",
]
SDXL_ARTIFACT_NEGATIVES = [
    "generic stock photo",
    "clip art",
    "white background",
    "simple illustration",
    "3d render",
    "plastic",
    "toy",
    "distorted hands",
    "extra fingers",
    "deformed",
    "asymmetrical eyes",
    "low resolution",
    "compression artifacts",
]
_NON_ASCII_RE = re.compile(r"[^\x00-\x7f]")
_HANGUL_RE = re.compile(r"[\uac00-\ud7a3]")


def _is_simple_diagram_brief(brief: VisualBrief, style_hint: str = "") -> bool:
    rationale = str(brief.get("rationale", "")).lower()
    return "style_preset=simple_diagram" in rationale or "simple flat 2d explainer diagram" in style_hint.lower()


def _is_editorial_symbolic_brief(brief: VisualBrief, style_hint: str = "") -> bool:
    rationale = str(brief.get("rationale", "")).lower()
    return (
        "style_preset=editorial_symbolic" in rationale
        or "editorial symbolic" in style_hint.lower()
        or (
            str(brief.get("domain") or "").strip().lower() == "ai_policy_conflict"
            and not _is_simple_diagram_brief(brief, style_hint)
        )
    )


def _allows_numeric_badges(brief: VisualBrief) -> bool:
    template = str(brief.get("composition_template") or "").strip().lower()
    haystack = " ".join(
        [
            template,
            str(brief.get("primary_prop") or ""),
            str(brief.get("secondary_prop") or ""),
            str(brief.get("action") or ""),
            str(brief.get("scene") or ""),
        ]
    ).lower()
    return "growthmetriccomparison" in template or "numeric badge" in haystack or "percent" in haystack


def _format_primary_prop(primary_prop: str) -> str:
    lowered = primary_prop.lower()
    if lowered.startswith("large "):
        return f"{primary_prop} clearly visible"
    return f"large {primary_prop} clearly visible"


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = value.strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def _join_slots(values: list[str]) -> str:
    return ", ".join(_dedupe(values))


def _is_prompt_safe_phrase(value: str) -> bool:
    cleaned = value.strip()
    if not cleaned:
        return False
    if _HANGUL_RE.search(cleaned):
        return False
    non_ascii_count = len(_NON_ASCII_RE.findall(cleaned))
    return non_ascii_count / max(1, len(cleaned)) <= 0.25


def _safe_part(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip() if _is_prompt_safe_phrase(value) else ""


def _allowed_objects(brief: VisualBrief) -> list[str]:
    allow_objects = brief.get("allow_objects")
    if not isinstance(allow_objects, list):
        return []
    return [
        item.strip().lower()
        for item in allow_objects
        if isinstance(item, str) and item.strip()
    ]


def _essay_positive_slots(*, shot: str, style_hint: str, brief: VisualBrief) -> list[str]:
    literal_simile = brief.get("literal_simile")
    visual_priority = brief.get("visual_priority")
    slots = [
        shot,
        _safe_part(brief["main_subject"]) or "grounded editorial scene",
        _format_primary_prop(_safe_part(brief["primary_prop"]) or "concrete visual subject from the sentence"),
        _safe_part(brief["action"]) or "arranged as a clear real-world visual metaphor",
        _safe_part(brief["scene"]) or "grounded editorial environment",
    ]
    secondary_prop = _safe_part(brief["secondary_prop"])
    if secondary_prop:
        slots.append(secondary_prop)
    prompt_hint = _safe_part(brief.get("prompt_hint", ""))
    if prompt_hint:
        slots.append(prompt_hint)
    if visual_priority == "literal_simile" and isinstance(literal_simile, str) and _is_prompt_safe_phrase(literal_simile):
        slots.insert(0, literal_simile.strip())
    slots.extend(
        [
            style_hint,
            "cinematic editorial photography",
            "clear subject action environment composition",
            "medium wide shot",
            "35mm lens",
            "natural color",
            "sharp focus",
            "detailed real-world textures",
            "soft natural lighting",
            "no readable text",
        ]
    )
    return slots


def _food_trend_positive_slots(*, shot: str, style_hint: str, brief: VisualBrief) -> list[str]:
    slots = [
        shot,
        _safe_part(brief["main_subject"]) or "clean editorial food trend scene",
        _format_primary_prop(_safe_part(brief["primary_prop"]) or "clearly visible food product display"),
        _safe_part(brief["action"]) or "shown as a direct product and consumer trend visual",
        _safe_part(brief["scene"]) or "retail shelf or cafe display setting",
    ]
    secondary_prop = _safe_part(brief["secondary_prop"])
    if secondary_prop:
        slots.append(secondary_prop)
    composition_template = _safe_part(brief.get("composition_template", ""))
    if composition_template:
        slots.append(f"composition template {composition_template}")
    prompt_hint = _safe_part(brief.get("prompt_hint", ""))
    if prompt_hint:
        slots.append(prompt_hint)
    slots.extend(
        [
            style_hint,
            "clean editorial food illustration",
            "product-focused scene",
            "purple ube color accent",
            "clear cafe or retail environment when relevant",
            "simple direct composition",
            "medium wide shot",
            "natural appetizing color",
            "sharp focus",
            "no readable text",
        ]
    )
    return slots


def _science_agriculture_positive_slots(*, shot: str, style_hint: str, brief: VisualBrief) -> list[str]:
    slots = [
        shot,
        _safe_part(brief["main_subject"]) or "environmental science editorial scene",
        _format_primary_prop(_safe_part(brief["primary_prop"]) or "clear material sample"),
        _safe_part(brief["action"]) or "shown as a concrete agricultural or material process",
        _safe_part(brief["scene"]) or "farm field or clean research workspace",
    ]
    secondary_prop = _safe_part(brief["secondary_prop"])
    if secondary_prop:
        slots.append(secondary_prop)
    composition_template = _safe_part(brief.get("composition_template", ""))
    if composition_template:
        slots.append(f"composition template {composition_template}")
    prompt_hint = _safe_part(brief.get("prompt_hint", ""))
    if prompt_hint:
        slots.append(prompt_hint)
    slots.extend(
        [
            style_hint,
            "editorial documentary photography",
            "clean agricultural photography",
            "natural daylight",
            "medium wide shot",
            "soil texture",
            "natural material closeup",
            "clear process relationship",
            "sharp focus",
            "natural color",
            "no readable text",
        ]
    )
    return slots


def _diagram_positive_slots(*, shot: str, style_hint: str, brief: VisualBrief) -> list[str]:
    primary_keywords = brief.get("primary_keywords")
    keyword_hint = ""
    if isinstance(primary_keywords, list):
        keyword_hint = ", ".join(
            value.strip()
            for value in primary_keywords[:3]
            if isinstance(value, str) and _is_prompt_safe_phrase(value)
        )
    slots = [
        shot,
        _safe_part(brief["main_subject"]) or "simple centered explainer icon composition",
        _format_primary_prop(_safe_part(brief["primary_prop"]) or "central explainer icon"),
        _safe_part(brief["action"]) or "one central icon with one or two supporting symbols in a clean explanation",
        _safe_part(brief["scene"]) or "plain warm background with generous empty space",
    ]
    secondary_prop = _safe_part(brief["secondary_prop"])
    if secondary_prop:
        slots.append(secondary_prop)
    if keyword_hint:
        slots.append(f"keywords visualized as {keyword_hint}")
    slots.extend(
        [
            style_hint,
            "simple flat explainer illustration",
            "clean black outline",
            "large readable icons",
            "minimal shapes",
            "plain background",
            "clear arrow or comparison structure",
            "no readable text",
        ]
    )
    return slots


def _editorial_symbolic_positive_slots(*, shot: str, style_hint: str, brief: VisualBrief) -> list[str]:
    scene_anchor = (
        _safe_part(brief.get("scene_anchor", ""))
        or _safe_part(brief.get("scene", ""))
        or "grounded editorial public policy environment"
    )
    hero_subject = (
        _safe_part(brief.get("hero_subject", ""))
        or _safe_part(brief.get("primary_prop", ""))
        or "one clear symbolic subject"
    )
    symbolic_marker = _safe_part(brief.get("symbolic_marker", "")) or _safe_part(brief.get("secondary_prop", ""))
    action = _safe_part(brief.get("action", "")) or "arranged as a direct editorial visual metaphor"
    prompt_hint = _safe_part(brief.get("prompt_hint", ""))
    composition_template = _safe_part(brief.get("composition_template", ""))
    concept_slots = [
        shot,
        f"high-quality editorial scene in {scene_anchor}",
        _format_primary_prop(hero_subject),
        action,
    ]
    if symbolic_marker:
        concept_slots.append(f"one supporting symbolic marker: {symbolic_marker}")
    if prompt_hint:
        concept_slots.append(prompt_hint)
    if composition_template:
        concept_slots.append(f"composition grammar {composition_template}")
    concept_slots.extend(
        [
            "one clear subject",
            "one or two symbolic objects only",
        ]
    )
    style_slots = [
        style_hint,
        "premium editorial illustration",
        "cinematic but clean composition",
        "real place or product-like setting",
        "medium wide shot",
        "clear foreground subject",
        "subtle background detail",
        "sharp focus",
        "natural color with restrained accent",
        "no readable text",
    ]
    return [*concept_slots, *style_slots]


def _default_positive_slots(*, shot: str, style_hint: str, brief: VisualBrief) -> list[str]:
    domain = _brief_domain(brief)
    parts: list[str] = []
    if domain not in {"essay", "generic", "news_explainer", "ai_policy_conflict", "food_trend", "ev_battery"}:
        parts.extend(["Flipchartvisu", "Stick figure"])
    parts.extend(
        [
            shot,
            brief["main_subject"],
            _format_primary_prop(brief["primary_prop"]),
            brief["action"],
            brief["scene"],
            brief["emotion"],
        ]
    )
    if brief["secondary_prop"]:
        parts.append(brief["secondary_prop"])
    parts.extend(
        [
            style_hint,
            "bold black outline",
            "plain white background",
            "high contrast",
            "no text",
        ]
    )
    return [part for part in parts if part]


def _build_dual_prompt(*, prompt_g_slots: list[str], prompt_l_slots: list[str]) -> SdxlDualPrompt:
    prompt_g = _join_slots(prompt_g_slots)
    prompt_l = _join_slots(prompt_l_slots)
    combined = _join_slots([prompt_g, prompt_l])
    return {
        "prompt_g": prompt_g,
        "prompt_l": prompt_l,
        "combined": combined,
    }


def _normalize_positive_prompt(value: str | SdxlDualPrompt) -> SdxlDualPrompt:
    if isinstance(value, dict):
        prompt_g = str(value.get("prompt_g") or "").strip()
        prompt_l = str(value.get("prompt_l") or "").strip()
        combined = str(value.get("combined") or "").strip()
        if not combined:
            combined = _join_slots([prompt_g, prompt_l])
        if not prompt_g:
            prompt_g = combined
        if not prompt_l:
            prompt_l = combined
        return {
            "prompt_g": prompt_g,
            "prompt_l": prompt_l,
            "combined": combined,
        }
    text = value.strip()
    return {
        "prompt_g": text,
        "prompt_l": text,
        "combined": text,
    }


def _brief_domain(brief: VisualBrief) -> str:
    domain = brief.get("domain")
    if isinstance(domain, str) and domain.strip():
        return domain.strip().lower()
    rationale = str(brief.get("rationale", "")).lower()
    if "domain=tech" in rationale:
        return "tech"
    return "generic"


def find_blocked_prompt_phrases(prompt: str) -> list[str]:
    lowered = prompt.lower()
    return [phrase for phrase in PROMPT_BLOCKLIST if phrase in lowered]


def compile_positive_prompt(
    *,
    shot: str,
    style_hint: str,
    brief: VisualBrief,
) -> SdxlDualPrompt:
    domain = _brief_domain(brief)
    if _is_simple_diagram_brief(brief, style_hint):
        numeric_badges = _allows_numeric_badges(brief)
        concept_slots = [
            shot,
            _safe_part(brief["main_subject"]) or "simple centered explainer icon composition",
            _format_primary_prop(_safe_part(brief["primary_prop"]) or "central explainer icon"),
            _safe_part(brief["action"]) or "one central icon with one or two supporting symbols in a clean explanation",
            _safe_part(brief["scene"]) or "plain warm background with generous empty space",
        ]
        secondary_prop = _safe_part(brief["secondary_prop"])
        if secondary_prop:
            concept_slots.append(secondary_prop)
        prompt_g_slots = [slot for slot in concept_slots if slot]
        prompt_l_slots = [
            style_hint,
            "simple flat explainer illustration",
            "clean black outline",
            "large readable icons",
            "minimal shapes",
            "plain background",
            "clear arrow or comparison structure",
            "large clean numeric badges only, no words" if numeric_badges else "no readable text",
        ]
        return _build_dual_prompt(prompt_g_slots=prompt_g_slots, prompt_l_slots=prompt_l_slots)
    if _is_editorial_symbolic_brief(brief, style_hint):
        editorial_slots = _editorial_symbolic_positive_slots(shot=shot, style_hint=style_hint, brief=brief)
        prompt_g_slots = editorial_slots[:8]
        prompt_l_slots = editorial_slots[8:]
        return _build_dual_prompt(prompt_g_slots=prompt_g_slots, prompt_l_slots=prompt_l_slots)
    if domain == "tech":
        numeric_badges = _allows_numeric_badges(brief)
        concept_slots = [
            shot,
            brief["main_subject"],
            _format_primary_prop(brief["primary_prop"]),
            brief["action"],
            brief["scene"],
            brief["emotion"],
        ]
        if brief["secondary_prop"]:
            concept_slots.append(brief["secondary_prop"])
        prompt_l_slots = [
            style_hint,
            "cinematic technology documentary still",
            "clean interface composition",
            "monitor glow lighting",
            "precise explainer visual",
            "widescreen frame",
            "35mm lens",
            "sharp focus",
            "natural color",
            "large clean numeric badges only, no words" if numeric_badges else "no text",
        ]
        return _build_dual_prompt(prompt_g_slots=[part for part in concept_slots if part], prompt_l_slots=prompt_l_slots)
    if domain in {"agriculture_environment", "science_materials"}:
        science_slots = _science_agriculture_positive_slots(shot=shot, style_hint=style_hint, brief=brief)
        prompt_g_slots = science_slots[:6]
        prompt_l_slots = science_slots[6:]
        return _build_dual_prompt(prompt_g_slots=prompt_g_slots, prompt_l_slots=prompt_l_slots)
    if domain == "food_trend":
        food_slots = _food_trend_positive_slots(shot=shot, style_hint=style_hint, brief=brief)
        prompt_g_slots = food_slots[:7]
        prompt_l_slots = food_slots[7:]
        return _build_dual_prompt(prompt_g_slots=prompt_g_slots, prompt_l_slots=prompt_l_slots)
    if domain == "essay":
        essay_slots = _essay_positive_slots(shot=shot, style_hint=style_hint, brief=brief)
        prompt_g_slots = essay_slots[:5]
        prompt_l_slots = essay_slots[5:]
        return _build_dual_prompt(prompt_g_slots=prompt_g_slots, prompt_l_slots=prompt_l_slots)
    default_slots = _default_positive_slots(shot=shot, style_hint=style_hint, brief=brief)
    prompt_g_slots = default_slots[:6]
    prompt_l_slots = default_slots[6:]
    return _build_dual_prompt(prompt_g_slots=prompt_g_slots, prompt_l_slots=prompt_l_slots)


def compile_positive_prompt_text(
    *,
    shot: str,
    style_hint: str,
    brief: VisualBrief,
) -> str:
    return compile_positive_prompt(shot=shot, style_hint=style_hint, brief=brief)["combined"]


def compile_negative_prompt(
    *,
    template_negative: str,
    brief: VisualBrief,
) -> str:
    domain = _brief_domain(brief)
    if _is_simple_diagram_brief(brief):
        diagram_vocab = load_domain_vocab("diagram")
        numeric_badges = _allows_numeric_badges(brief)
        defaults = [
            "text",
            "logo",
            "watermark",
            "paragraph text",
            "readable text",
            "letters",
            "messy handwriting",
            "photorealistic",
            "cinematic lighting",
            "realistic skin",
            "3d render",
            "oil painting texture",
            "dense background",
            "room interior photo",
            "crowd",
            "clutter",
            "tiny subject",
            "tiny icons",
            "tiny scattered icons",
            "abstract icon cloud",
            "abstract network only",
            "dense dashboard UI",
            "complex infographic",
            "infographic poster",
            "flowchart web",
            "many small labels",
            "many tiny nodes",
            "many panels",
            "multiple panels",
            "thin faint lines",
            "washed out low contrast diagram",
            "generic server room",
            "gpu rack cluster",
            "browser automation interface",
            "terminal panel",
            "isometric blueprint",
            "blueprint maze",
            "detailed architecture",
            "floor plan",
            "document panels",
            "many small buildings",
            "unreadable forms",
            "hand-only closeup",
            "phone screen closeup only",
        ]
        if numeric_badges:
            defaults = [item for item in defaults if item not in {"text", "readable text", "letters"}]
            defaults.extend(["words", "sentences", "paragraph labels", "tiny numbers"])
        avoid = [item for item in brief["avoid"] if item and item not in defaults]
        for item in domain_global_avoid(diagram_vocab):
            if item not in avoid:
                avoid.append(item)
        return ", ".join([template_negative, *defaults, *avoid]).strip(", ")
    if _is_editorial_symbolic_brief(brief):
        vocab = load_domain_vocab(domain) if domain else {}
        defaults = [
            "dashboard",
            "flowchart",
            "infographic poster",
            "tiny icons",
            "tiny labels",
            "multiple panels",
            "flat icon only",
            "generic shield icon only",
            "empty diagram",
            "abstract geometry only",
            "abstract network only",
            "dense analytics dashboard",
            "isometric blueprint maze",
            "floor plan",
            "many small buildings",
            "unreadable text",
            "readable text",
            "logo",
            "watermark",
            "blurry",
            "low quality",
            "clutter",
            "crowd",
            "tiny subject",
        ]
        avoid = [item for item in brief["avoid"] if item and item not in defaults]
        for item in domain_global_avoid(vocab):
            if item not in avoid:
                avoid.append(item)
        return ", ".join([template_negative, *defaults, *avoid]).strip(", ")
    if domain == "tech":
        numeric_badges = _allows_numeric_badges(brief)
        defaults = [
            "text",
            "logo",
            "watermark",
            "blurry",
            "low quality",
            "clutter",
            "crowd",
            "duplicate screens",
            "deformed hardware",
            "tiny subject",
        ]
        if numeric_badges:
            defaults = [item for item in defaults if item != "text"]
            defaults.extend(["words", "paragraph labels", "tiny numbers", "dense spreadsheet"])
        avoid = [item for item in brief["avoid"] if item and item not in defaults]
        return ", ".join([template_negative, *defaults, *avoid]).strip(", ")
    if domain in {"agriculture_environment", "science_materials"}:
        vocab = load_domain_vocab(domain)
        defaults = [
            "text",
            "logo",
            "watermark",
            "blurry",
            "low quality",
            "generic stock photo",
            "abstract dashboard",
            "circuit diagram",
            "AI brain icon",
            "neural network",
            "server rack",
            "cartoon character",
            "tiny icons",
            "generic lab shelves",
            "unreadable labels",
            "hay bales",
            "pipe rolls",
            "empty field only",
            "dry desert unless drought is the topic",
        ]
        avoid = [item for item in brief["avoid"] if item and item not in defaults]
        for item in domain_global_avoid(vocab):
            if item not in avoid:
                avoid.append(item)
        return ", ".join([template_negative, *defaults, *avoid]).strip(", ")
    if domain == "food_trend":
        vocab = load_domain_vocab("food_trend")
        defaults = [
            "text",
            "logo",
            "watermark",
            "blurry",
            "low quality",
            "empty living room",
            "generic interior",
            "gear mechanism",
            "abstract sculpture",
            "abstract industry",
            "factory machine",
            "random furniture",
            "office",
            "car",
            "road",
            "human portrait",
            "hand-only closeup",
            "phone-only closeup",
            "readable text",
            "letters",
            *SDXL_ARTIFACT_NEGATIVES,
        ]
        avoid = [item for item in brief["avoid"] if item and item not in defaults]
        for item in domain_global_avoid(vocab):
            if item not in avoid:
                avoid.append(item)
        return ", ".join([template_negative, *defaults, *avoid]).strip(", ")
    if domain == "essay":
        essay_vocab = load_domain_vocab("essay")
        allowed = _allowed_objects(brief)
        defaults = [
            "text",
            "logo",
            "watermark",
            "blurry",
            "low quality",
            "duplicate people",
            "hand only closeup",
            "phone screen closeup only",
            "tiny subject",
            "clutter",
            "random surreal object",
            *TEXT_RISK_NEGATIVES,
            *FRAMING_NEGATIVES,
            *SDXL_ARTIFACT_NEGATIVES,
        ]
        avoid = [item for item in brief["avoid"] if item and item not in defaults]
        for item in [*domain_global_avoid(essay_vocab), *GENERIC_DRIFT_TERMS]:
            if item.lower() not in allowed and item not in avoid:
                avoid.append(item)
        positive_hint = " ".join(
            str(brief.get(key, "")).lower()
            for key in ("primary_prop", "secondary_prop", "scene", "action")
        )
        if any(term in positive_hint for term in ROAD_TERMS):
            for item in VEHICLE_BAN_TERMS:
                if item not in allowed and item not in avoid:
                    avoid.append(item)
        return ", ".join([template_negative, *defaults, *avoid]).strip(", ")
    defaults = [
        "tiny subject",
        "missing main prop",
        "crowd",
        "multiple characters",
        "text",
        "logo",
        "detailed landscape",
        "photorealistic",
        "clutter",
    ]
    avoid = [item for item in brief["avoid"] if item and item not in defaults]
    return ", ".join([template_negative, *defaults, *avoid]).strip(", ")


def check_prompt_compliance(prompt: str | SdxlDualPrompt, brief: VisualBrief) -> list[str]:
    prompt_text = _normalize_positive_prompt(prompt)["combined"]
    lowered = prompt_text.lower()
    missing: list[str] = []
    for item in brief["must_show"]:
        if item.lower() not in lowered:
            missing.append(item)
    for phrase in find_blocked_prompt_phrases(prompt_text):
        missing.append(f"BLOCKLIST:{phrase}")
    return missing
