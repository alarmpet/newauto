import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import cast
from copy import deepcopy

from ..types import (
    ProjectRecord,
    SdxlDualPrompt,
    SemanticAnchorType,
    VisualBrief,
    VisualBriefMode,
    VisualPlanEntry,
    VisualPriority,
    VisualSceneMode,
)
from .comfyui_prompt_adapter import normalize_dual_prompt
from .domain_detection import (
    is_ai_policy_conflict_domain,
    is_agriculture_environment_domain,
    is_food_trend_domain,
    is_news_explainer_domain,
    is_science_materials_domain,
    is_tech_domain,
)
from .image_generation_profiles import micro_conditioning_values, normalize_quality_mode, profile_for_quality_mode
from .stickman_reference_library import (
    DEFAULT_STICKMAN_TEMPLATE,
    STICKMAN_REFERENCES,
    STICKMAN_TEMPLATES,
    StickmanTemplate,
)
from .prompt_compiler import check_prompt_compliance, compile_negative_prompt, compile_positive_prompt
from .prompt_quality import build_keyword_coverage
from .visual_brief import build_visual_brief
from .visual_relevance import sentence_hash
from .visual_planner import build_scene_visual_plan
from .visual_vocab import domain_global_avoid, load_domain_vocab

_VISUAL_KEYWORD_MAP: tuple[tuple[tuple[str, ...], str], ...] = (
    (("pray", "prayer", "기도"), "kneeling on both knees with hands clasped at chest in prayer"),
    (("tear", "cry", "눈물"), "crying with large visible tears"),
    (("smile", "joy", "기쁨"), "big smile and joyful pose"),
    (("fall", "drop", "추락"), "falling down in shock"),
    (("stand", "rise", "recover", "회복"), "standing up again with determination"),
    (("road", "path", "선택", "갈림길"), "standing where one road splits clearly into left and right"),
    (("sea", "ocean", "wave", "바다", "파도"), "facing one oversized dark wave directly ahead"),
    (("book", "notebook", "bible", "책"), "holding an oversized open book or notebook"),
    (("screen", "smartphone", "mobile", "연락", "메시지"), "looking at a bright phone message screen"),
    (("coin", "cash", "money", "돈"), "holding one large green banknote clearly in front of chest"),
    (("clock", "time", "시계", "시간"), "oversized clock directly behind the hero"),
    (("shield", "battle", "sword", "방패"), "facing danger with a sword and shield"),
    (("giant", "stone", "sling", "거인"), "holding a sling and a large visible stone"),
    (("study", "desk", "공부", "책상"), "studying at a desk"),
    (("office", "job", "work", "사무실", "업무"), "inside an office with a desk"),
    (("tempt", "temptation", "forbidden", "유혹"), "reaching toward one glowing forbidden object"),
    (("plan", "goal", "목표", "계획"), "holding a large checklist with three bold check marks"),
)

_EMOTION_MAP: tuple[tuple[tuple[str, ...], str], ...] = (
    (("fear", "afraid", "불안", "두려"), "anxious expression"),
    (("courage", "bold", "용기"), "brave confident pose"),
    (("hope", "희망"), "hopeful upward gaze"),
    (("despair", "give up", "포기"), "collapsed hopeless pose"),
    (("decision", "choose", "결단", "선택"), "decisive pose at a crossroads"),
    (("victory", "win", "승리"), "victory pose with raised arms"),
)
_GENERIC_PLAN_TERMS = {
    "large checklist with three bold check marks",
    "compass on a folded map",
    "quiet road fork",
    "simple symbolic scene",
    "concrete visual subject tied to the sentence",
    "single everyday object in a quiet realistic room",
    "quiet realistic environment",
}

_TEMPLATE_MATCHERS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("giant", "sling", "stone", "거인"), "giant_battle"),
    (("pray", "prayer", "기도"), "prayer"),
    (("clock", "time", "시계", "시간"), "time_pressure"),
    (("cash", "money", "돈", "decision", "path", "선택"), "money_choice"),
    (("tempt", "temptation", "forbidden", "유혹"), "temptation"),
    (("recover", "comeback", "회복"), "recovery"),
    (("storm", "sea", "ocean", "wave", "폭풍", "파도"), "storm_fear"),
    (("study", "book", "bible", "공부", "책"), "study_focus"),
)

_TECH_VOCAB_PATH = Path("storage/visual_vocab/tech.json")
_TECH_VOCAB_CACHE: list[dict[str, object]] | None = None
TECH_DOCUMENTARY_TEMPLATE: StickmanTemplate = {
    "key": "tech_documentary",
    "label": "Tech Documentary",
    "positive_core": (
        "high-detail technology documentary illustration, layered product interface, "
        "infrastructure diagram realism, editorial composition, crisp monitor lighting"
    ),
    "negative_extra": (
        "text, logo, watermark, blurry, low quality, crowd, duplicate screens, "
        "deformed hardware, messy composition"
    ),
    "trigger_hint": "",
    "shot_hint": "wide cinematic shot",
}

ESSAY_EDITORIAL_TEMPLATE: StickmanTemplate = {
    "key": "essay_editorial",
    "label": "Essay Editorial",
    "positive_core": (
        "high-detail cinematic editorial illustration, reflective visual storytelling, "
        "clear object and environment composition, soft natural lighting"
    ),
    "negative_extra": (
        "text, logo, watermark, blurry, low quality, duplicate people, clutter, "
        "random surreal object, hand-only closeup"
    ),
    "trigger_hint": "",
    "shot_hint": "medium wide editorial shot",
}

ESSAY_SYMBOLIC_TEMPLATE: StickmanTemplate = {
    "key": "essay_symbolic",
    "label": "Essay Symbolic",
    "positive_core": (
        "high-detail editorial symbolic illustration, grounded real-world metaphor, "
        "one clear hero subject, restrained palette, clean layered composition, no readable text"
    ),
    "negative_extra": (
        "text, logo, watermark, blurry, low quality, dashboard-only scene, monitor wall, "
        "tiny icons, office cubicle repetition, abstract geometry only, clutter"
    ),
    "trigger_hint": "",
    "shot_hint": "medium wide editorial symbolic shot",
}

ESSAY_EXPLAINER_TEMPLATE: StickmanTemplate = {
    "key": "essay_explainer",
    "label": "Essay Explainer",
    "positive_core": (
        "simple flat 2d explainer diagram, minimal editorial cartoon, large central concept, "
        "clean outline, plain warm background, no readable text"
    ),
    "negative_extra": (
        "text, logo, watermark, blurry, low quality, photorealistic office, realistic monitor wall, "
        "conference room, clutter, dense infographic grid, many tiny labels"
    ),
    "trigger_hint": "",
    "shot_hint": "wide centered explainer shot",
}

ESSAY_DATA_DIAGRAM_TEMPLATE: StickmanTemplate = {
    "key": "essay_data_diagram",
    "label": "Essay Data Diagram",
    "positive_core": (
        "simple flat 2d explainer diagram, clean comparative editorial visual, "
        "two or three oversized comparison elements, restrained palette, no readable text"
    ),
    "negative_extra": (
        "text, logo, watermark, blurry, low quality, realistic trading desk, dashboard wall, "
        "tiny chart labels, spreadsheet screenshot, clutter, dense infographic grid"
    ),
    "trigger_hint": "",
    "shot_hint": "wide comparative explainer shot",
}

ENVIRONMENTAL_SCIENCE_TEMPLATE: StickmanTemplate = {
    "key": "environmental_science_editorial",
    "label": "Environmental Science Editorial",
    "positive_core": (
        "high-detail environmental science editorial still, clean agricultural documentary photography, "
        "concrete material process, natural daylight, clear soil and plant texture"
    ),
    "negative_extra": (
        "text, logo, watermark, blurry, low quality, abstract dashboard, circuit diagram, AI brain icon, "
        "server rack, cartoon character, tiny icons, generic stock photo"
    ),
    "trigger_hint": "",
    "shot_hint": "medium wide editorial documentary shot",
}

FOOD_TREND_EDITORIAL_TEMPLATE: StickmanTemplate = {
    "key": "food_trend_editorial",
    "label": "Food Trend Editorial",
    "positive_core": (
        "clean editorial food illustration, simple direct composition, "
        "product-focused scene, purple ube color accent, retail or cafe environment, no readable text"
    ),
    "negative_extra": (
        "empty living room, generic interior, gear mechanism, abstract sculpture, random furniture, "
        "office, car, road, human portrait, readable text, logo"
    ),
    "trigger_hint": "",
    "shot_hint": "medium wide editorial food shot",
}

EDITORIAL_SYMBOLIC_TEMPLATE: StickmanTemplate = {
    "key": "editorial_symbolic",
    "label": "Editorial Symbolic",
    "positive_core": (
        "editorial symbolic high-quality illustration, real-world scene anchor, "
        "one clear hero subject, one or two symbolic objects only, cinematic but clean composition, "
        "subtle background detail, no readable text"
    ),
    "negative_extra": (
        "dashboard, flowchart, infographic poster, tiny icons, tiny labels, multiple panels, "
        "flat icon only, generic shield icon only, empty diagram, abstract geometry only, "
        "unreadable text, logo, watermark, clutter"
    ),
    "trigger_hint": "",
    "shot_hint": "medium wide editorial symbolic shot",
}

STYLE_PRESET_OVERRIDES: dict[str, dict[str, str]] = {
    "k_webtoon": {
        "label_suffix": "K-Webtoon",
        "positive_core": (
            "high-detail korean webtoon illustration, clean inked line art, cinematic vertical-panel energy, "
            "expressive character acting, polished cel shading, modern k-webtoon color styling"
        ),
        "negative_extra": (
            "text, logo, watermark, blurry, low quality, duplicate people, clutter, random surreal object, "
            "hand-only closeup, muddy colors, painterly oil texture, 3d render"
        ),
        "shot_hint": "medium wide cinematic webtoon panel shot",
    },
    "simple_diagram": {
        "label_suffix": "Simple Diagram",
        "positive_core": (
            "simple flat 2d explainer diagram, minimal editorial cartoon, clean outline, centered composition, "
            "one single pictogram scene, two to four oversized symbols only, thick black outlines, "
            "large readable icons, generous empty space, calm neutral palette"
        ),
        "negative_extra": (
            "text, logo, watermark, blurry, low quality, photorealistic, cinematic lighting, realistic skin, "
            "3d render, dense background, clutter, crowd, tiny subject, paragraph text, complex infographic, "
            "small labels, many tiny nodes, many panels, dashboard layout, blueprint layout"
        ),
        "shot_hint": "wide centered explainer diagram shot",
    },
    "editorial_symbolic": {
        "label_suffix": "Editorial Symbolic",
        "positive_core": (
            "editorial symbolic high-quality illustration, real-world scene anchor, one clear hero subject, "
            "one or two symbolic objects only, cinematic but clean composition, subtle background detail, "
            "no readable text"
        ),
        "negative_extra": (
            "dashboard, flowchart, infographic poster, tiny icons, tiny labels, multiple panels, flat icon only, "
            "generic shield icon only, empty diagram, abstract geometry only, dense analytics dashboard, "
            "unreadable text, logo, watermark, clutter"
        ),
        "shot_hint": "medium wide editorial symbolic shot",
    },
}

NEWS_COMPOSITION_LAYOUTS: dict[str, str] = {
    "AlertFlow": "left platform monitor, bold center alert arrow, right newsroom receiver, one envelope icon",
    "SpikeDetection": "one large article card, giant thumbs up and thumbs down counters, warning detector circle",
    "SortingControl": "large comment list, highlighted sort slider, reaction bubbles being reordered",
    "CoordinationPressure": "many account nodes aiming at one comment box, public opinion scale bending",
    "UserView": "single user icon facing a news comment panel, question mark and magnifier",
    "LimitationShield": "imperfect shield with gaps, suspicious reaction dots slipping through",
    "SpeedResponse": "threshold knobs, stopwatch, fast arrow toward media response button",
    "PreserveAndReveal": "comment panel remains visible, abnormal signal highlighted early, response speed arrow",
    "GovernmentVsCompany": "only three oversized symbols: left government shield icon, center warning divider, right AI company cube icon, plain background",
    "HearingCriticism": "only three oversized symbols: senate hearing podium, defense official silhouette, warning speech bubble aimed at one company cube",
    "AccessRestriction": "only three oversized symbols: White House stop button, red access barrier, one branching AI model node",
    "PolicyOversight": "only three oversized symbols: government shield, magnifying glass, AI model cube under review",
    "SecurityRiskBalance": "only one oversized balance scale: innovation lightbulb on one side and security shield on the other",
    "PolicyPressureDual": "only four oversized symbols: left senate hearing podium, right White House stop button, center AI company cube, two bold arrows",
}

NEWS_DIAGRAM_NEGATIVES = (
    "abstract radar dashboard",
    "dense analytics dashboard",
    "tiny scattered icons",
    "decorative circuit board",
    "generic blueprint interface",
    "complex infographic grid",
    "infographic poster",
    "many small labels",
    "many tiny nodes",
    "many small icons",
    "multiple panels",
    "flowchart web",
    "faint thin lines",
    "low contrast pale drawing",
    "washed out background",
    "radar-only dashboard",
)


def _load_tech_vocab() -> list[dict[str, object]]:
    global _TECH_VOCAB_CACHE
    if _TECH_VOCAB_CACHE is not None:
        return _TECH_VOCAB_CACHE
    try:
        payload = json.loads(_TECH_VOCAB_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        _TECH_VOCAB_CACHE = []
        return _TECH_VOCAB_CACHE
    terms = payload.get("terms")
    if not isinstance(terms, list):
        _TECH_VOCAB_CACHE = []
        return _TECH_VOCAB_CACHE
    _TECH_VOCAB_CACHE = [item for item in terms if isinstance(item, dict)]
    return _TECH_VOCAB_CACHE


def _sentence_for_index(project: ProjectRecord, sentence_idx: int) -> str:
    sentences = project["sentences"]
    if 0 <= sentence_idx < len(sentences):
        return sentences[sentence_idx].strip()
    if sentences:
        return sentences[0].strip()
    compiled = (project["compiled_script"] or project["script"]).strip()
    if not compiled:
        return ""
    return compiled.splitlines()[0].strip()


def _fact_keywords(project: ProjectRecord, limit: int = 3) -> list[str]:
    notes: list[str] = []
    for item in project["source_draft_fact_notes"]:
        note = item.get("note", "").strip()
        if note:
            notes.append(note)
        if len(notes) >= limit:
            break
    return notes


def _base_template_for_project(project: ProjectRecord) -> StickmanTemplate:
    if project["content_mode"] == "bible_longform":
        return {
            "key": "biblical_default",
            "label": "Biblical Poster",
            "positive_core": (
                "minimalist 2d stickman biblical poster, single hero character centered, "
                "one clear action, one oversized prop, bold outline, flat shading, "
                "high contrast lighting, simple background, no text"
            ),
            "negative_extra": DEFAULT_STICKMAN_TEMPLATE["negative_extra"],
            "trigger_hint": DEFAULT_STICKMAN_TEMPLATE["trigger_hint"],
            "shot_hint": "medium action shot, full body view",
        }
    return DEFAULT_STICKMAN_TEMPLATE


def _select_template(text: str, project: ProjectRecord, *, is_tech: bool) -> StickmanTemplate:
    if is_tech:
        return TECH_DOCUMENTARY_TEMPLATE
    lowered = text.lower()
    template_map = {item["key"]: item for item in STICKMAN_TEMPLATES}
    for needles, template_key in _TEMPLATE_MATCHERS:
        if any(needle in lowered for needle in needles):
            return template_map[template_key]
    return _base_template_for_project(project)


def _template_for_visual_plan(
    project: ProjectRecord,
    text: str,
    visual_plan_entry: VisualPlanEntry | None,
    *,
    is_tech: bool,
) -> StickmanTemplate:
    if visual_plan_entry is not None:
        visual_mode = str(visual_plan_entry.get("visual_mode") or "").strip().lower()
        if _style_preset_name(project) == "editorial_symbolic":
            return _apply_style_preset(project, EDITORIAL_SYMBOLIC_TEMPLATE)
        if visual_plan_entry["domain"] == "ai_policy_conflict":
            return _apply_style_preset(project, EDITORIAL_SYMBOLIC_TEMPLATE)
        if visual_plan_entry["domain"] == "tech":
            return _apply_style_preset(project, TECH_DOCUMENTARY_TEMPLATE)
        if visual_plan_entry["domain"] in {"agriculture_environment", "science_materials"}:
            return _apply_style_preset(project, ENVIRONMENTAL_SCIENCE_TEMPLATE)
        if visual_plan_entry["domain"] == "food_trend":
            return _apply_style_preset(project, FOOD_TREND_EDITORIAL_TEMPLATE)
        if visual_plan_entry["domain"] == "essay":
            if visual_mode == "symbolic_concept":
                return _apply_style_preset(project, ESSAY_SYMBOLIC_TEMPLATE)
            if visual_mode == "simple_explainer":
                return _apply_style_preset(project, ESSAY_EXPLAINER_TEMPLATE)
            if visual_mode == "data_diagram":
                return _apply_style_preset(project, ESSAY_DATA_DIAGRAM_TEMPLATE)
            return _apply_style_preset(project, ESSAY_EDITORIAL_TEMPLATE)
    if is_food_trend_domain(project, text):
        return _apply_style_preset(project, FOOD_TREND_EDITORIAL_TEMPLATE)
    if _style_preset_name(project) == "editorial_symbolic" or is_ai_policy_conflict_domain(project, text):
        return _apply_style_preset(project, EDITORIAL_SYMBOLIC_TEMPLATE)
    if is_agriculture_environment_domain(project, text) or is_science_materials_domain(project, text):
        return _apply_style_preset(project, ENVIRONMENTAL_SCIENCE_TEMPLATE)
    return _apply_style_preset(project, _select_template(text, project, is_tech=is_tech))


def _style_preset_name(project: ProjectRecord) -> str:
    value = project["body_image_options"].get("style_preset")
    if not isinstance(value, str):
        return ""
    return value.strip().lower()


def _visual_plan_is_generic(entry: VisualPlanEntry) -> bool:
    haystack = " ".join(
        [
            *entry.get("primary_keywords", []),
            *entry.get("must_show", []),
            str(entry.get("visual_metaphor", "")),
        ]
    ).lower()
    return any(term in haystack for term in _GENERIC_PLAN_TERMS)


def _recommended_style_preset(project: ProjectRecord, sentence: str) -> str:
    if project["content_mode"] == "bible_longform":
        return ""
    if _style_preset_name(project):
        return ""
    if is_agriculture_environment_domain(project, sentence) or is_science_materials_domain(project, sentence):
        return ""
    if is_food_trend_domain(project, sentence):
        return ""
    if (
        not is_ai_policy_conflict_domain(project, sentence)
        and not is_tech_domain(project, sentence)
        and not is_news_explainer_domain(project, sentence)
    ):
        return ""
    if is_news_explainer_domain(project, sentence) and not is_ai_policy_conflict_domain(project, sentence):
        return "simple_diagram"
    return "editorial_symbolic"


def _is_simple_diagram_preset(project: ProjectRecord) -> bool:
    return _style_preset_name(project) == "simple_diagram"


def _is_simple_diagram_preset_from_brief(brief: VisualBrief) -> bool:
    rationale = str(brief.get("rationale", "")).lower()
    visual_mode = str(brief.get("visual_mode") or "").strip().lower()
    return (
        "style_preset=simple_diagram" in rationale
        or visual_mode in {"simple_explainer", "data_diagram"}
    )


def _relax_keyword_coverage_for_style_preset(
    project: ProjectRecord,
    keyword_coverage: dict[str, object],
) -> dict[str, object]:
    preset_name = _style_preset_name(project)
    if preset_name not in {"k_webtoon", "simple_diagram", "editorial_symbolic"}:
        return keyword_coverage
    issue_codes = keyword_coverage.get("issue_codes")
    if not isinstance(issue_codes, list):
        return keyword_coverage
    filtered_issue_codes = [
        item
        for item in issue_codes
        if item not in {"GENERIC_SYMBOL_WITHOUT_ALLOW"}
    ]
    if len(filtered_issue_codes) == len(issue_codes):
        return keyword_coverage
    updated = dict(keyword_coverage)
    updated["issue_codes"] = filtered_issue_codes
    non_blocklist_missing = updated.get("missing_must_show")
    blocklist_hits = updated.get("blocklist_hits")
    updated["passed"] = not non_blocklist_missing and not blocklist_hits and not filtered_issue_codes
    return updated


def _apply_style_preset(project: ProjectRecord, template: StickmanTemplate) -> StickmanTemplate:
    preset_name = _style_preset_name(project)
    override = STYLE_PRESET_OVERRIDES.get(preset_name)
    if override is None:
        return template
    updated = deepcopy(template)
    label_suffix = override.get("label_suffix", "").strip()
    if label_suffix:
        updated["label"] = f"{template['label']} {label_suffix}".strip()
    positive_core = override.get("positive_core", "").strip()
    if positive_core:
        updated["positive_core"] = positive_core
    negative_extra = override.get("negative_extra", "").strip()
    if negative_extra:
        updated["negative_extra"] = negative_extra
    shot_hint = override.get("shot_hint", "").strip()
    if shot_hint:
        updated["shot_hint"] = shot_hint
    return updated


def _fallback_tokens(*, is_tech: bool, text: str) -> list[str]:
    compact = re.sub(r"\s+", " ", text).strip()
    if not compact:
        return ["standing in a simple spotlight"]
    if is_tech:
        return [
            "browser window with terminal panel and automation cursor",
            "structured data table flowing out of a browser window",
            "gpu rack cluster with glowing interconnect lines",
        ]
    lowered = compact.lower()
    if any(needle in lowered for needle in ("quantum", "finance", "investment", "portfolio", "market", "bank")):
        return [
            "financial strategy desk with one dominant analytical display",
            "probability lines linking portfolio variables",
            "editorial finance lab environment",
        ]
    if "?" in compact:
        return ["confused stickman thinking with a large question mark pose"]
    return ["grounded editorial scene with one dominant real-world subject"]


def _extract_tech_visual_tokens(text: str) -> list[str]:
    lowered = text.lower()
    matched_terms: list[tuple[int, dict[str, object]]] = []
    for item in _load_tech_vocab():
        keywords = item.get("keywords")
        if not isinstance(keywords, list):
            continue
        normalized_keywords = [
            keyword.lower()
            for keyword in keywords
            if isinstance(keyword, str) and keyword.strip()
        ]
        matched_keywords = [keyword for keyword in normalized_keywords if keyword in lowered]
        if not matched_keywords:
            continue
        score = max(len(keyword) for keyword in matched_keywords)
        if any(keyword in {"ai", "artificial intelligence", "인공지능", "ai 기술"} for keyword in matched_keywords):
            score -= 100
        matched_terms.append((score, item))
    matched_terms.sort(key=lambda pair: pair[0], reverse=True)

    tokens: list[str] = []
    for _, item in matched_terms:
        primary_prop = item.get("primary_prop")
        secondary_prop = item.get("secondary_prop")
        if isinstance(primary_prop, str) and primary_prop not in tokens:
            tokens.append(primary_prop)
        if isinstance(secondary_prop, str) and secondary_prop not in tokens:
            tokens.append(secondary_prop)
    return tokens[:4]


def _extract_generic_visual_tokens(text: str) -> list[str]:
    lowered = text.lower()
    tokens: list[str] = []
    for needles, prompt_token in _VISUAL_KEYWORD_MAP:
        if any(needle in lowered for needle in needles):
            tokens.append(prompt_token)
    for needles, prompt_token in _EMOTION_MAP:
        if any(needle in lowered for needle in needles):
            tokens.append(prompt_token)
    return tokens[:4]


def _extract_visual_tokens(project: ProjectRecord, text: str, *, is_tech: bool) -> list[str]:
    tokens: list[str] = []
    if is_tech:
        tokens.extend(_extract_tech_visual_tokens(text))
    else:
        lowered = f"{project['title']} {project['compiled_script'] or project['script']} {text}".lower()
        if any(needle in lowered for needle in ("quantum", "finance", "investment", "portfolio", "market", "bank")):
            tokens.extend(
                [
                    "financial strategy desk with quantum processor glow",
                    "portfolio risk board linked by probability lines",
                    "analyst workstation reviewing market volatility",
                ]
            )
    tokens.extend(token for token in _extract_generic_visual_tokens(text) if token not in tokens)
    if tokens:
        return tokens[:4]
    return _fallback_tokens(is_tech=is_tech, text=text)


def _supporting_context(project: ProjectRecord) -> list[str]:
    context: list[str] = []
    for note in _fact_keywords(project, limit=2):
        cleaned = re.sub(r"\s+", " ", note).strip()
        if cleaned:
            context.append(cleaned)
    source = project["source_draft_sources"][0] if project["source_draft_sources"] else None
    if source is not None:
        title = source.get("title", "").strip()
        if title:
            context.append(title)
    return context[:2]


def _diagram_vocab_matches(text: str, keywords: list[str]) -> list[dict[str, object]]:
    vocab = load_domain_vocab("diagram")
    terms = vocab.get("terms")
    if not isinstance(terms, list):
        return []
    sentence_haystack = text.lower()
    keyword_haystack = " ".join(item.lower() for item in keywords)
    matches: list[tuple[int, dict[str, object]]] = []
    for item in terms:
        if not isinstance(item, dict):
            continue
        raw_keywords = item.get("keywords")
        if not isinstance(raw_keywords, list):
            continue
        normalized = [
            value.strip().lower()
            for value in raw_keywords
            if isinstance(value, str) and value.strip()
        ]
        sentence_hits = [value for value in normalized if value in sentence_haystack]
        keyword_hits = [value for value in normalized if value in keyword_haystack and value not in sentence_hits]
        if not sentence_hits and not keyword_hits:
            continue
        score = 0
        if sentence_hits:
            score += 100 + max(len(value) for value in sentence_hits)
        if keyword_hits:
            score += 10 + max(len(value) for value in keyword_hits)
        concept = _diagram_value(item, "concept").lower()
        if concept == "ai system":
            score -= 40
        matches.append((score, item))
    matches.sort(key=lambda pair: pair[0], reverse=True)
    ordered = [item for _, item in matches[:3]]
    if len(ordered) > 1:
        ordered = sorted(
            ordered,
            key=lambda item: 1 if _diagram_value(item, "concept").lower() == "ai system" else 0,
        )
    return ordered


def _diagram_value(item: dict[str, object], key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str):
        return ""
    return value.strip()


def _apply_simple_diagram_brief(
    *,
    project: ProjectRecord,
    sentence: str,
    brief: VisualBrief,
) -> VisualBrief:
    vocab = load_domain_vocab("diagram")
    keyword_pool = list(brief.get("primary_keywords", [])) + list(brief.get("secondary_keywords", []))
    matches = _diagram_vocab_matches(sentence, keyword_pool)
    sentence_lower = sentence.lower()
    if any(term in sentence_lower for term in ("google", "구글", "company", "companies", "기업", "선도")):
        prioritized: list[dict[str, object]] = []
        deferred: list[dict[str, object]] = []
        for item in matches:
            concept = _diagram_value(item, "concept").lower()
            if concept == "company-led shift":
                prioritized.append(item)
            else:
                deferred.append(item)
        matches = prioritized + deferred
    primary_prop = brief["primary_prop"]
    secondary_prop = brief["secondary_prop"]
    action = "one central icon with one or two supporting symbols in a clean visual explanation"
    scene = "plain warm background with generous empty space"
    main_subject = "simple centered explainer icon composition"
    emotion = "clear and direct"
    must_show = list(brief["must_show"])
    composition_template = str(brief.get("composition_template", "")).strip()
    if brief.get("domain") == "tech" and composition_template:
        primary_prop = must_show[0] if must_show else primary_prop
        secondary_prop = must_show[1] if len(must_show) > 1 else secondary_prop
        action = brief["action"]
        main_subject = f"{composition_template} tech explainer composition"
        matches = []
    if brief.get("domain") == "ai_policy_conflict" and composition_template:
        focus, focus_action = _ai_policy_simple_focus(sentence, composition_template)
        must_show = focus
        primary_prop = focus[0]
        secondary_prop = focus[1] if len(focus) > 1 else ""
        action = focus_action
        scene = "plain warm background with only one centered pictogram"
        main_subject = "simple two-symbol policy explainer"
        matches = []
    if matches:
        primary_icon = _diagram_value(matches[0], "icon")
        support_icon = _diagram_value(matches[0], "support")
        relation = _diagram_value(matches[0], "relation")
        if primary_icon:
            primary_prop = primary_icon
        if support_icon:
            secondary_prop = support_icon
        if relation:
            action = relation
        must_show = [item for item in [primary_prop, secondary_prop] if item]
        for extra in matches[1:]:
            extra_icon = _diagram_value(extra, "icon")
            if extra_icon and extra_icon not in must_show:
                must_show.append(extra_icon)
            if len(must_show) >= 3:
                break
    if brief.get("domain") in {"news_explainer", "ai_policy_conflict"}:
        if not composition_template:
            composition_template = _news_template_from_brief(brief)
        layout = NEWS_COMPOSITION_LAYOUTS.get(composition_template, "")
        if layout and brief.get("domain") != "ai_policy_conflict":
            main_subject = f"{composition_template} news explainer composition"
            action = layout
            scene = "plain warm background with one dominant central diagram and generous empty space"
            must_show = _news_must_show_for_template(composition_template, must_show)
    literal_simile = str(brief.get("literal_simile", "")).strip()
    visual_priority = str(brief.get("visual_priority", "")).strip()
    if brief.get("domain") != "tech" and visual_priority == "literal_simile" and literal_simile:
        main_subject = "simple flat explainer scene"
        action = f"{literal_simile}, simplified into a clear flat illustration"
        scene = "minimal open background with one obvious action"
        emotion = "simple and intuitive"
    avoid = list(dict.fromkeys([*brief["avoid"], *domain_global_avoid(vocab)]))
    updated: VisualBrief = {
        **brief,
        "main_subject": main_subject,
        "action": action,
        "primary_prop": primary_prop,
        "secondary_prop": secondary_prop,
        "scene": scene,
        "emotion": emotion,
        "must_show": must_show[:2] if brief.get("domain") == "ai_policy_conflict" else must_show[:3],
        "avoid": avoid,
        "allow_objects": ["icon", "arrows", "balance scale"],
        "composition_template": composition_template,
    }
    return updated


def _news_template_from_brief(brief: VisualBrief) -> str:
    haystack = " ".join(
        str(value)
        for value in [
            brief.get("core_meaning", ""),
            brief.get("primary_prop", ""),
            brief.get("secondary_prop", ""),
            " ".join(brief.get("must_show", [])),
        ]
    ).lower()
    if any(term in haystack for term in ("white house", "stop button", "access restriction", "blocked access", "\ubc31\uc545\uad00", "\uc81c\ub3d9")):
        return "AccessRestriction"
    if any(term in haystack for term in ("senate", "hearing", "defense", "criticism", "podium", "\uc0c1\uc6d0", "\uccad\ubb38", "\uad6d\ubc29", "\ube44\ud310")):
        return "HearingCriticism"
    if any(term in haystack for term in ("oversight", "intervention", "regulation", "policy document", "\uac1c\uc785", "\uaddc\uc81c", "\uc815\ucc45")):
        return "PolicyOversight"
    if any(term in haystack for term in ("security", "national security", "safety", "\uc548\ubcf4", "\uad6d\uac00 \uc548\ubcf4")):
        return "SecurityRiskBalance"
    if any(term in haystack for term in ("government", "company", "conflict", "anthropic", "\uc815\ubd80", "\uae30\uc5c5", "\uc564\uc2a4\ub85c\ud53d", "\uac08\ub4f1")):
        return "GovernmentVsCompany"
    if any(term in haystack for term in ("shield", "만능", "slipping")):
        return "LimitationShield"
    if any(term in haystack for term in ("user", "이용자", "magnifier", "question")):
        return "UserView"
    if any(term in haystack for term in ("public opinion", "좌표", "조직", "scale")):
        return "CoordinationPressure"
    if any(term in haystack for term in ("threshold", "stopwatch", "감지 기준")):
        return "SpeedResponse"
    if any(term in haystack for term in ("remains visible", "댓글 공간", "response speed")):
        return "PreserveAndReveal"
    if any(term in haystack for term in ("alert", "newsroom", "언론사", "mail")):
        return "AlertFlow"
    if any(term in haystack for term in ("counter", "spike", "공감", "비공감")):
        return "SpikeDetection"
    return "SortingControl"


def _news_must_show_for_template(template_name: str, fallback: list[str]) -> list[str]:
    templates: dict[str, list[str]] = {
        "AlertFlow": ["platform monitor", "alert arrow", "newsroom receiver"],
        "SpikeDetection": ["giant reaction counters", "warning detector", "article card"],
        "SortingControl": ["comment list", "sort slider", "reordered reaction bubbles"],
        "CoordinationPressure": ["account nodes targeting one comment", "bending public opinion scale"],
        "UserView": ["user icon", "news comment panel", "question mark or magnifier"],
        "LimitationShield": ["imperfect shield", "small gaps", "suspicious dots slipping through"],
        "SpeedResponse": ["threshold knobs", "stopwatch", "fast response arrow"],
        "PreserveAndReveal": ["comment panel remains visible", "highlighted abnormal signal", "response speed arrow"],
        "GovernmentVsCompany": ["government shield", "warning divider", "AI company cube"],
        "HearingCriticism": ["senate hearing podium", "defense official silhouette", "warning speech bubble"],
        "AccessRestriction": ["White House stop button", "red access barrier", "branching AI model nodes"],
        "PolicyOversight": ["government shield", "policy document", "AI model under review"],
        "SecurityRiskBalance": ["innovation lightbulb", "security shield", "balance scale"],
        "PolicyPressureDual": ["senate hearing podium", "White House stop button", "AI company cube"],
    }
    return templates.get(template_name, fallback)[:3]


def _ai_policy_simple_focus(sentence: str, template_name: str) -> tuple[list[str], str]:
    text = sentence.lower()
    if any(term in text for term in ("항공기", "aircraft", "목표물", "target")):
        return (
            ["aircraft icon", "target reticle"],
            "one large aircraft icon pointing at one target reticle",
        )
    if any(term in text for term in ("백악관", "white house", "제동", "확산", "restriction", "blocked")):
        return (
            ["White House stop sign", "AI model nodes"],
            "one large White House stop sign blocking two AI model nodes",
        )
    if any(term in text for term in ("청문회", "상원", "국방", "장관", "비판", "hearing", "defense", "criticism")):
        return (
            ["hearing podium", "warning speech bubble"],
            "one large hearing podium sending one warning speech bubble to an AI cube",
        )
    if any(term in text for term in ("결정권", "운영 방식", "독자", "decision", "authority")):
        return (
            ["AI company cube", "control lock"],
            "one large AI company cube beside one control lock icon",
        )
    if template_name == "SecurityRiskBalance":
        return (
            ["security shield", "innovation lightbulb"],
            "one large balance scale with a security shield and an innovation lightbulb",
        )
    return (
        ["government shield", "AI company cube"],
        "one large government shield facing one AI company cube",
    )


def _compile_simple_policy_prompt(brief: VisualBrief) -> SdxlDualPrompt:
    must_show = [item for item in brief["must_show"][:2] if item.strip()]
    action = brief["action"].strip()
    focus = ", ".join(must_show)
    prompt_g = (
        f"{action}, {focus}, plain background, no text"
        if focus
        else f"{action}, plain background, no text"
    )
    prompt_l = (
        "simple flat 2d icon illustration, one single pictogram scene, "
        "maximum two large symbols, thick clean black outline, high contrast, centered composition, "
        "generous empty space, no small icons, no labels"
    )
    return normalize_dual_prompt(
        {
            "prompt_g": prompt_g,
            "prompt_l": prompt_l,
            "combined": f"{prompt_g}, {prompt_l}",
        }
    )


def _visual_plan_for_sentence(project: ProjectRecord, sentence_idx: int) -> VisualPlanEntry | None:
    for item in build_scene_visual_plan(project):
        if item["sentence_idx"] == sentence_idx:
            return item
    return None


def _clean_keywords(values: list[str], *, fallback: list[str]) -> list[str]:
    normalized = [value.strip() for value in values if value.strip()]
    return normalized or fallback


def _visual_brief_from_plan(
    *,
    sentence: str,
    template: StickmanTemplate,
    visual_plan_entry: VisualPlanEntry,
) -> VisualBrief:
    primary_keywords = _clean_keywords(
        visual_plan_entry["primary_keywords"],
        fallback=[sentence],
    )
    secondary_keywords = _clean_keywords(
        visual_plan_entry["secondary_keywords"],
        fallback=[],
    )
    subject_modes = visual_plan_entry["subject_modes"] or ["environment"]
    domain = visual_plan_entry["domain"]
    visual_mode = cast(VisualSceneMode, str(visual_plan_entry.get("visual_mode") or "editorial_scene"))
    mode = "symbolic_metaphor" if "object_metaphor" in subject_modes or "symbolic" in subject_modes else "keyword_image"
    if visual_mode in {"simple_explainer", "data_diagram"}:
        mode = "keyword_image"
    elif visual_mode == "symbolic_concept":
        mode = "symbolic_metaphor"
    if domain == "ai_policy_conflict":
        main_subject = "policy conflict editorial scene"
    elif domain == "tech":
        main_subject = "technology interface scene"
    elif visual_mode == "data_diagram":
        main_subject = "clean comparative data explainer composition"
    elif visual_mode == "simple_explainer":
        main_subject = "simple centered explainer icon composition"
    elif visual_mode == "symbolic_concept":
        main_subject = "editorial symbolic concept scene"
    elif "person" in subject_modes and "environment" not in subject_modes:
        main_subject = "single human subject in a grounded editorial scene"
    else:
        main_subject = "environment-led editorial scene"
    action = visual_plan_entry["visual_metaphor"]
    literal_simile = str(visual_plan_entry.get("literal_simile", "")).strip()
    visual_priority = str(visual_plan_entry.get("visual_priority", "")).strip()
    if visual_plan_entry["prompt_hint"].strip():
        action = f"{action}, {visual_plan_entry['prompt_hint'].strip()}"
    primary_prop = visual_plan_entry["must_show"][0] if visual_plan_entry["must_show"] else primary_keywords[0]
    secondary_prop = ""
    if len(visual_plan_entry["must_show"]) > 1:
        secondary_prop = visual_plan_entry["must_show"][1]
    elif secondary_keywords:
        secondary_prop = secondary_keywords[0]
    scene = visual_plan_entry["visual_metaphor"] or template["shot_hint"]
    allow_objects = list(visual_plan_entry.get("allow_objects", []))
    avoid = list(dict.fromkeys(visual_plan_entry["avoid"]))
    if visual_mode in {"simple_explainer", "data_diagram"}:
        scene = "plain warm background with generous empty space"
        allow_objects = list(dict.fromkeys([*allow_objects, "icon", "arrows", "comparison bars", "probability lines"]))
        for banned in ("office desk", "monitor wall", "conference room", "laptop-only scene"):
            if banned not in avoid:
                avoid.append(banned)
    elif visual_mode == "symbolic_concept":
        scene = "clean editorial setting with one grounded symbolic anchor"
        allow_objects = list(dict.fromkeys([*allow_objects, "symbolic object", "path marker", "barrier shape"]))
        for banned in ("monitor wall", "dashboard-only scene", "office cubicle repetition"):
            if banned not in avoid:
                avoid.append(banned)
    semantic_anchor_tokens_raw = visual_plan_entry.get("semantic_anchor_tokens", [])
    semantic_anchor_tokens = (
        [item for item in semantic_anchor_tokens_raw if isinstance(item, str) and item.strip()]
        if isinstance(semantic_anchor_tokens_raw, list)
        else []
    )
    return {
        "mode": cast(VisualBriefMode, mode),
        "main_subject": main_subject,
        "action": action,
        "primary_prop": primary_prop,
        "secondary_prop": secondary_prop,
        "scene": scene,
        "emotion": visual_plan_entry["core_meaning"],
        "must_show": list(visual_plan_entry["must_show"]),
        "avoid": avoid,
        "rationale": (
            f"template={template['key']}; domain={domain}; "
            f"keywords={', '.join(primary_keywords)}; source={visual_plan_entry['source']}"
        ),
        "domain": domain,
        "core_meaning": visual_plan_entry["core_meaning"],
        "primary_keywords": primary_keywords,
        "secondary_keywords": secondary_keywords,
        "subject_modes": list(subject_modes),
        "prompt_hint": visual_plan_entry["prompt_hint"],
        "may_show": list(visual_plan_entry["may_show"]),
        "vocab_refs": list(visual_plan_entry["vocab_refs"]),
        "visual_priority": cast(VisualPriority, visual_priority) if visual_priority else "core_metaphor",
        "literal_simile": literal_simile,
        "allow_objects": allow_objects,
        "composition_template": str(visual_plan_entry.get("composition_template", "")).strip(),
        "scene_anchor": str(visual_plan_entry.get("scene_anchor", scene)).strip(),
        "hero_subject": str(visual_plan_entry.get("hero_subject", primary_prop)).strip(),
        "symbolic_marker": str(visual_plan_entry.get("symbolic_marker", secondary_prop)).strip(),
        "visual_mode": visual_mode,
        "semantic_anchor_type": cast(
            SemanticAnchorType,
            str(visual_plan_entry.get("semantic_anchor_type", "generic")).strip() or "generic",
        ),
        "semantic_anchor_tokens": semantic_anchor_tokens,
    }


def _repair_positive_prompt(
    *,
    positive_prompt: str,
    brief: VisualBrief,
    retry_index: int,
) -> str:
    must_show = list(brief["must_show"])
    if retry_index == 1:
        strong_prefix = ", ".join(item for item in must_show[:3] if item.strip())
        if strong_prefix:
            return f"{strong_prefix}, {positive_prompt}"
        return positive_prompt
    focus_terms: list[str] = []
    primary_keywords = brief.get("primary_keywords")
    if isinstance(primary_keywords, list):
        focus_terms.extend(item for item in primary_keywords[:3] if isinstance(item, str) and item.strip())
    if must_show:
        focus_terms.extend(item for item in must_show[:2] if item.strip())
    unique_focus = ", ".join(dict.fromkeys(focus_terms))
    if unique_focus:
        return f"{unique_focus}, clear visual metaphor, {positive_prompt}"
    return positive_prompt


def _repair_quality_issues(
    *,
    positive_prompt: str,
    negative_prompt: str,
    brief: VisualBrief,
    issue_codes: list[str],
) -> tuple[str, str]:
    positive = positive_prompt
    negative = negative_prompt
    is_simple_diagram = _is_simple_diagram_preset_from_brief(brief)
    is_editorial_symbolic = "style_preset=editorial_symbolic" in str(brief.get("rationale", "")).lower()
    if "MISSING_FRAMING_SLOT" in issue_codes and "medium wide shot" not in positive.lower():
        positive = f"medium wide shot, {positive}"
    if "MISSING_CAMERA_TECHNICAL_SLOT" in issue_codes and not is_simple_diagram and not is_editorial_symbolic:
        technical_anchor = "35mm lens, sharp focus, natural color, detailed real-world textures"
        if technical_anchor.lower() not in positive.lower():
            positive = f"{positive}, {technical_anchor}"
    if "MISSING_CAMERA_TECHNICAL_SLOT" in issue_codes and is_editorial_symbolic:
        editorial_anchor = "premium editorial illustration, medium wide shot, clear foreground subject, real scene anchor"
        if editorial_anchor.lower() not in positive.lower():
            positive = f"{positive}, {editorial_anchor}"
    if "MISSING_CAMERA_TECHNICAL_SLOT" in issue_codes and is_simple_diagram:
        diagram_anchor = "flat icon diagram, clean outline, few objects only"
        if diagram_anchor.lower() not in positive.lower():
            positive = f"{positive}, {diagram_anchor}"
    if "BOOK_TEXT_RISK" in issue_codes:
        for token in ("no readable text", "letters", "scribbles", "watermark"):
            if token not in negative.lower():
                negative = f"{negative}, {token}".strip(", ")
    return positive, negative


def _template_runtime_settings(template: StickmanTemplate, project: ProjectRecord) -> dict[str, object]:
    quality_mode = normalize_quality_mode(project["autopilot_options"].get("quality_mode"))
    profile = profile_for_quality_mode(quality_mode)
    profile_settings: dict[str, object] = {
        "quality_mode": quality_mode,
        "generation_profile": profile["profile_name"],
        "sampler_name": profile["sampler_name"],
        "scheduler": profile["scheduler"],
        "steps": profile["steps"],
        "cfg": profile["cfg"],
        "denoise": profile["denoise"],
        "request_timeout_sec": profile["request_timeout_sec"],
        "seed_policy": profile["seed_policy"],
        "score_version": profile["score_version"],
        **micro_conditioning_values(profile=profile, width=1344, height=768),
    }
    if _is_simple_diagram_preset(project):
        return {
            "template_id": "txt2img_sdxl_basic",
            "lora_name": "",
            "lora_strength": 0.0,
            "width": 1344,
            "height": 768,
            **profile_settings,
        }
    if template["key"] in {"essay_editorial", "essay_symbolic", "essay_explainer", "essay_data_diagram"}:
        return {
            "template_id": "txt2img_sdxl_basic",
            "lora_name": "",
            "lora_strength": 0.0,
            "width": 1344,
            "height": 768,
            **profile_settings,
        }
    if template["key"] == "tech_documentary":
        return {
            "template_id": "txt2img_sdxl_basic",
            "lora_name": "",
            "lora_strength": 0.0,
            "width": 1344,
            "height": 768,
            **profile_settings,
        }
    if template["key"] == "environmental_science_editorial":
        return {
            "template_id": "txt2img_sdxl_basic",
            "lora_name": "",
            "lora_strength": 0.0,
            "width": 1344,
            "height": 768,
            **profile_settings,
        }
    if template["key"] == "food_trend_editorial":
        return {
            "template_id": "txt2img_sdxl_basic",
            "lora_name": "",
            "lora_strength": 0.0,
            "width": 1344,
            "height": 768,
            **profile_settings,
        }
    profile_settings = {
        **profile_settings,
        **micro_conditioning_values(profile=profile, width=1024, height=576),
    }
    return {
        "template_id": "txt2img_sdxl_stickman_lora",
        "lora_name": "",
        "lora_strength": 0.8,
        "width": 1024,
        "height": 576,
        **profile_settings,
    }


def suggest_image_prompt(
    project: ProjectRecord,
    sentence_idx: int,
    *,
    visual_plan_entry: VisualPlanEntry | None = None,
) -> dict[str, object]:
    sentence = _sentence_for_index(project, sentence_idx)
    if not sentence:
        raise ValueError("No sentence is available for image prompt suggestion.")

    if visual_plan_entry is None:
        visual_plan_entry = _visual_plan_for_sentence(project, sentence_idx)
    prompt_visual_plan_entry = visual_plan_entry
    if (
        prompt_visual_plan_entry is not None
        and prompt_visual_plan_entry["source"] == "fallback"
        and _style_preset_name(project) != "simple_diagram"
        and prompt_visual_plan_entry["domain"] in {"essay", "generic", "tech"}
        and _visual_plan_is_generic(prompt_visual_plan_entry)
    ):
        prompt_visual_plan_entry = None
    is_tech = is_tech_domain(project, sentence)
    template = _template_for_visual_plan(project, sentence, prompt_visual_plan_entry, is_tech=is_tech)
    visual_tokens = _extract_visual_tokens(project, sentence, is_tech=is_tech)
    if prompt_visual_plan_entry is not None:
        domain = prompt_visual_plan_entry["domain"]
    elif is_agriculture_environment_domain(project, sentence):
        domain = "agriculture_environment"
    elif is_science_materials_domain(project, sentence):
        domain = "science_materials"
    elif is_food_trend_domain(project, sentence):
        domain = "food_trend"
    else:
        domain = "tech" if is_tech else "generic"
    visual_brief = (
        _visual_brief_from_plan(sentence=sentence, template=template, visual_plan_entry=prompt_visual_plan_entry)
        if prompt_visual_plan_entry is not None
        else build_visual_brief(
            text=sentence,
            visual_tokens=visual_tokens,
            template_key=template["key"],
            domain=domain,
        )
    )
    if _is_simple_diagram_preset(project) or _is_simple_diagram_preset_from_brief(visual_brief):
        visual_brief = _apply_simple_diagram_brief(
            project=project,
            sentence=sentence,
            brief=visual_brief,
        )
    context_tokens = _supporting_context(project)
    shot = template["shot_hint"] if template.get("shot_hint") else (
        "wide establishing shot, full body view" if sentence_idx <= 0 else "medium action shot, full body view"
    )
    visual_brief["rationale"] += f"; style_preset={_style_preset_name(project) or 'default'}"
    if context_tokens:
        visual_brief["rationale"] += "; context=" + "; ".join(context_tokens)
    dual_prompt = normalize_dual_prompt(
        compile_positive_prompt(
        shot=shot,
        style_hint=template["positive_core"],
        brief=visual_brief,
        )
    )
    if _is_simple_diagram_preset_from_brief(visual_brief) and visual_brief.get("domain") == "ai_policy_conflict":
        dual_prompt = _compile_simple_policy_prompt(visual_brief)
    positive_prompt = dual_prompt["combined"]
    negative_prompt = compile_negative_prompt(
        template_negative=template["negative_extra"],
        brief=visual_brief,
    )
    if _is_simple_diagram_preset_from_brief(visual_brief) and visual_brief.get("domain") == "news_explainer":
        strict_prefix = ", ".join(item for item in visual_brief["must_show"][:3] if item.strip())
        composition_template = str(visual_brief.get("composition_template", "")).strip()
        layout = NEWS_COMPOSITION_LAYOUTS.get(composition_template, "")
        if layout:
            strict_layout = f"{composition_template}: {layout}"
            positive_prompt = f"{strict_layout}, {strict_prefix}, {positive_prompt}".strip(", ")
            dual_prompt = normalize_dual_prompt(
                {
                    "prompt_g": f"{strict_layout}, {strict_prefix}".strip(", "),
                    "prompt_l": dual_prompt["prompt_l"],
                    "combined": positive_prompt,
                }
            )
        negative_prompt = f"{negative_prompt}, {', '.join(NEWS_DIAGRAM_NEGATIVES)}".strip(", ")
    retry_count = 0
    missing_must_show = check_prompt_compliance(positive_prompt, visual_brief)
    while missing_must_show and retry_count < 2:
        retry_count += 1
        positive_prompt = _repair_positive_prompt(
            positive_prompt=positive_prompt,
            brief=visual_brief,
            retry_index=retry_count,
        )
        missing_must_show = check_prompt_compliance(positive_prompt, visual_brief)
    keyword_coverage = build_keyword_coverage(
        positive_prompt=positive_prompt,
        negative_prompt=negative_prompt,
        brief=visual_brief,
    )
    keyword_coverage = _relax_keyword_coverage_for_style_preset(project, keyword_coverage)
    issue_codes = keyword_coverage.get("issue_codes")
    if isinstance(issue_codes, list) and issue_codes:
        repaired_positive, repaired_negative = _repair_quality_issues(
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            brief=visual_brief,
            issue_codes=issue_codes,
        )
        if repaired_positive != positive_prompt or repaired_negative != negative_prompt:
            retry_count += 1
            positive_prompt = repaired_positive
            negative_prompt = repaired_negative
            keyword_coverage = build_keyword_coverage(
                positive_prompt=positive_prompt,
                negative_prompt=negative_prompt,
                brief=visual_brief,
            )
            keyword_coverage = _relax_keyword_coverage_for_style_preset(project, keyword_coverage)
    runtime_settings = _template_runtime_settings(template, project)
    requested_style_preset = _style_preset_name(project)
    recommended_style_preset = _recommended_style_preset(project, sentence)

    return {
        "sentence_idx": sentence_idx,
        "sentence": sentence,
        "sentence_hash": sentence_hash(sentence),
        "positive_prompt": positive_prompt,
        "prompt_g": dual_prompt["prompt_g"],
        "prompt_l": dual_prompt["prompt_l"],
        "negative_prompt": negative_prompt,
        "style_hint": template["positive_core"],
        "visual_source_mode": project["visual_source_mode"],
        "visual_brief": visual_brief,
        "visual_plan": prompt_visual_plan_entry or visual_plan_entry,
        "visual_tokens": visual_tokens,
        "missing_must_show": missing_must_show,
        "keyword_coverage": keyword_coverage,
        "retry_count": retry_count,
        "template_key": template["key"],
        "reference_names": [item["name"] for item in STICKMAN_REFERENCES],
        "requested_style_preset": requested_style_preset,
        "recommended_style_preset": recommended_style_preset,
        **runtime_settings,
    }


def suggest_image_prompt_batch(
    project: ProjectRecord,
    *,
    start_idx: int,
    count: int,
) -> list[dict[str, object]]:
    safe_count = max(1, min(count, 48))
    plan_by_idx: dict[int, VisualPlanEntry] = {}
    visual_plan = build_scene_visual_plan(project)
    plan_by_idx = {item["sentence_idx"]: item for item in visual_plan}
    prompts: list[dict[str, object]] = []
    for sentence_idx in range(max(0, start_idx), max(0, start_idx) + safe_count):
        try:
            prompts.append(
                suggest_image_prompt(
                    project,
                    sentence_idx,
                    visual_plan_entry=plan_by_idx.get(sentence_idx),
                )
            )
        except ValueError:
            break
    return prompts


def save_image_prompt_manifest(
    target_path: Path,
    *,
    project: ProjectRecord,
    source: str,
    prompts: list[dict[str, object]],
) -> Path:
    payload = {
        "project_id": project["id"],
        "title": project["title"],
        "source": source,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "visual_source_mode": project["visual_source_mode"],
        "content_mode": project["content_mode"],
        "prompt_count": len(prompts),
        "reference_library": list(STICKMAN_REFERENCES),
        "prompts": prompts,
    }
    target_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target_path
