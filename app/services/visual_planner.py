import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import cast
from urllib.error import URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from .. import db
from ..config import LLM_PROVIDER, LMSTUDIO_BASE_URL, OLLAMA_BASE_URL, SCRIPT_LLM_MODEL
from ..types import (
    ProjectRecord,
    SemanticAnchorType,
    VisualPlanEntry,
    VisualPlanSubjectMode,
    VisualPriority,
    VisualSceneMode,
)
from .domain_detection import (
    is_ai_policy_conflict_domain,
    is_agriculture_environment_domain,
    is_ev_battery_domain,
    is_food_trend_domain,
    is_news_explainer_domain,
    is_science_materials_domain,
    is_tech_domain,
)
from .literal_simile import extract_literal_simile
from .lmstudio_runtime import loaded_lmstudio_models
from .llm_ollama import OllamaClient
from .visual_brief import build_visual_brief
from .visual_relevance import sentence_hash
from .visual_vocab import domain_global_avoid, load_domain_vocab

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_HANGUL_TOKEN_RE = re.compile(r"[\uac00-\ud7a3]{2,}")
_DEFAULT_SUBJECT_MODES: list[VisualPlanSubjectMode] = ["environment", "object_metaphor"]
_PLANNER_CACHE_VERSION = 11
_PLANNER_BATCH_SIZE = 3
_GENERIC_ESSAY_TERMS = {
    "compass on a folded map",
    "quiet road fork",
    "large checklist with three bold check marks",
    "simple symbolic scene",
    "single everyday object in a quiet realistic room",
    "quiet realistic environment",
    "abstract representation of industry",
    "empty room",
    "generic object",
    "food product display tied to the sentence",
    "concrete visual subject tied to the sentence",
}

_GROWTH_METRIC_MUST_SHOW = [
    "clean growth metric diagram with two rising bars",
    "large numeric badges for 130 percent and 60 percent when mentioned",
    "upward arrow showing user growth",
]
_KOREAN_PARTICLE_SUFFIXES = (
    "\uc740",
    "\ub294",
    "\uc774",
    "\uac00",
    "\uc744",
    "\ub97c",
    "\uc5d0",
    "\uc640",
    "\uacfc",
    "\ub85c",
    "\ub3c4",
    "\ub9cc",
)
_GENERIC_SENTENCE_GLUE = {
    "\uadf8\ub9ac\uace0",
    "\ud558\uc9c0\ub9cc",
    "\uadf8\ub7ec\ub098",
    "\ub530\ub77c\uc11c",
    "\ub610\ud55c",
    "\uc608\ub97c",
    "\ub4e4\uc5b4",
    "\uc2e4\uc81c",
    "\uc77c\ubd80",
    "\uae30\uad00\ub4e4",
    "\ubaa8\uc2b5",
    "\uacfc\uc815",
    "\uae30\uc220",
    "\ubc1c\uc804",
    "\ud65c\uc6a9",
    "\ubbf8\ub798",
    "\uc131\uc7a5",
    "\ub3d9\ub825",
    "\ud574\uacb0",
    "\uacfc\uc81c",
    "\ud55c\uacc4",
    "\ud55c\uacc4\uc810\ub4e4",
    "\ub54c\ubb38",
    "\uc774\ub85c",
    "\uc778\ud574",
    "\ub2e4\ub978",
    "\uc5ec\uc804\ud788",
    "\uc2dc\uc791",
    "\ubcbd",
    "direction",
    "speed",
    "choice",
}

_OFFICE_SCENE_TERMS = {
    "financial strategy desk",
    "analyst workstation reviewing market volatility",
    "institutional investment committee reviewing a quantum roadmap",
    "major bank strategy desk with mixed momentum signals",
    "market volatility dashboard reviewed by analysts",
}

_VISUAL_MODE_SEQUENCE: tuple[VisualSceneMode, ...] = (
    "editorial_scene",
    "symbolic_concept",
    "simple_explainer",
    "data_diagram",
)


def _cache_path(project: ProjectRecord) -> Path:
    return db.project_dir(project["id"]) / "scene_visual_plan.json"


def _load_vocab(domain: str) -> dict[str, object]:
    if domain == "ai_policy_conflict":
        vocab = load_domain_vocab("ai_policy_conflict")
        if vocab.get("terms"):
            return vocab
        return load_domain_vocab("diagram")
    if domain == "news_explainer":
        vocab = load_domain_vocab("news_explainer")
        if vocab.get("terms"):
            return vocab
        return load_domain_vocab("diagram")
    return load_domain_vocab(domain)


def _sentence_hashes(project: ProjectRecord) -> list[str]:
    return [sentence_hash(sentence) for sentence in project["sentences"]]


def _domain_for_project(project: ProjectRecord) -> str:
    if project["content_mode"] == "bible_longform":
        return "bible"
    sample_text = "\n".join(project["sentences"][:4]) or project["compiled_script"] or project["script"]
    if is_food_trend_domain(project, sample_text):
        return "food_trend"
    if is_agriculture_environment_domain(project, sample_text):
        return "agriculture_environment"
    if is_science_materials_domain(project, sample_text):
        return "science_materials"
    if is_ev_battery_domain(project, sample_text):
        return "ev_battery"
    if is_ai_policy_conflict_domain(project, sample_text):
        return "ai_policy_conflict"
    if is_news_explainer_domain(project, sample_text):
        return "news_explainer"
    if is_tech_domain(project, sample_text):
        return "tech"
    return "essay"


def _extract_visual_tokens(project: ProjectRecord, text: str, *, is_tech: bool) -> list[str]:
    lowered = text.lower()
    tokens: list[str] = []
    if is_tech:
        if any(needle in lowered for needle in ("browser", "headless", "automation", "javascript", "runtime")):
            tokens.extend(
                [
                    "browser window with terminal panel and automation cursor",
                    "structured data table",
                ]
            )
        if any(needle in lowered for needle in ("gpu", "chip", "model", "training", "inference", "ai")):
            tokens.extend(
                [
                    "gpu rack cluster with glowing interconnect lines",
                    "layered model workflow diagram",
                ]
            )
    else:
        if any(
            needle in lowered
            for needle in (
                "\ubc29\ud5a5",
                "\uae38",
                "\uc120\ud0dd",
                "direction",
                "path",
                "choice",
            )
        ):
            tokens.extend(["compass on a folded map", "quiet road fork"])
        if any(
            needle in lowered
            for needle in (
                "\uc18d\ub3c4",
                "\ubc14\uc068",
                "\ubc14\uc05c",
                "speed",
                "busy",
                "alarm",
            )
        ):
            tokens.extend(["sharp alarm clock", "unfinished to-do notebook"])
        if any(
            needle in lowered
            for needle in ("\uc54c\ub9bc", "\ud578\ub4dc\ud3f0", "phone", "notification")
        ):
            tokens.extend(["smartphone notifications", "morning room"])
        if any(needle in lowered for needle in ("우베", "ube", "자색", "참마", "보라색", "보랏빛")):
            tokens.extend(["purple yam with cut violet flesh", "ube cream dessert"])
        if any(needle in lowered for needle in ("말차", "matcha")):
            tokens.extend(["green matcha dessert beside purple ube dessert", "side-by-side dessert comparison"])
        if any(needle in lowered for needle in ("카페", "베이커리", "cafe", "bakery")):
            tokens.extend(["bakery display case with purple ube cake", "ube latte and purple pastries"])
        if any(needle in lowered for needle in ("편의점", "대형마트", "마트", "supermarket", "convenience store")):
            tokens.extend(["convenience store shelf filled with purple packaged drinks", "supermarket dessert display"])
        if any(needle in lowered for needle in ("수출", "필리핀", "해외", "export", "philippines")):
            tokens.extend(["shipping boxes with purple yam symbols", "global retail shelf"])
    return list(dict.fromkeys(tokens))


def _extract_concrete_tokens(sentence: str) -> list[str]:
    compact = re.sub(r"\s+", " ", sentence).strip()
    if not compact:
        return []
    tokens = re.findall(r"[A-Za-z][A-Za-z\-]+", compact)
    hangul_tokens = _HANGUL_TOKEN_RE.findall(compact)
    values: list[str] = []
    for token in [*tokens, *hangul_tokens]:
        normalized = token.strip().lower().strip("-")
        if _HANGUL_TOKEN_RE.fullmatch(normalized):
            for suffix in _KOREAN_PARTICLE_SUFFIXES:
                if normalized.endswith(suffix) and len(normalized) - len(suffix) >= 2:
                    normalized = normalized[: -len(suffix)]
                    break
        if len(normalized) < 2 or normalized in _GENERIC_SENTENCE_GLUE:
            continue
        if _HANGUL_TOKEN_RE.fullmatch(normalized):
            if normalized in {"\ubc29\ud5a5", "\uc18d\ub3c4", "\uc0dd\ud65c", "\uc778\uc0dd"}:
                continue
        elif normalized in {"this", "that", "those", "into", "from", "still", "some", "many", "real"}:
            continue
        if normalized not in values:
            values.append(normalized)
        if len(values) >= 4:
            break
    return values


def _project_repeated_hangul_terms(project: ProjectRecord) -> list[str]:
    counts: dict[str, int] = {}
    for sentence in project["sentences"]:
        for token in _extract_concrete_tokens(sentence):
            if not _HANGUL_TOKEN_RE.fullmatch(token):
                continue
            counts[token] = counts.get(token, 0) + 1
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [term for term, count in ordered if count >= 3][:3]


def _lookup_literal_simile_vocab(simile_phrase: str, vocab: dict[str, object]) -> list[str]:
    raw_examples = vocab.get("literal_simile_examples")
    if not isinstance(raw_examples, list):
        return []
    for item in raw_examples:
        if not isinstance(item, dict):
            continue
        pattern = item.get("pattern")
        if not isinstance(pattern, str) or pattern not in simile_phrase:
            continue
        must_show = item.get("must_show")
        if not isinstance(must_show, list):
            return []
        values = [value for value in must_show if isinstance(value, str) and value.strip()]
        if values:
            return values
    return []


def _essay_semantic_tokens(sentence: str) -> list[str]:
    lowered = sentence.lower()
    if any(needle in lowered for needle in ("quantum", "\uc591\uc790")) and any(
        needle in lowered
        for needle in (
            "\uae08\uc735",
            "\uc740\ud589",
            "\ud22c\uc790",
            "\ud3ec\ud2b8\ud3f4\ub9ac\uc624",
            "\uc2dc\uc7a5",
            "finance",
            "bank",
            "investment",
            "portfolio",
            "market",
        )
    ):
        if any(
            needle in lowered
            for needle in (
                "\ud55c\uacc4",
                "\ud55c\uacc4\uc810",
                "\ubcbd",
                "\uacfc\uc81c",
                "\ubcf5\uc7a1",
                "limitation",
                "barrier",
                "complex",
                "challenge",
                "bottleneck",
            )
        ):
            return [
                "financial analyst desk comparing many market variables",
                "quantum processor prototype facing a visible technical barrier",
                "risk model board with tangled probability paths",
            ]
        if any(
            needle in lowered
            for needle in (
                "\ub290\ucd94",
                "\uc9c0\uc5f0",
                "\ud22c\uc790",
                "\uc9c0\uc18d",
                "\uc18d\ub3c4",
                "slow",
                "delay",
                "investment",
                "continue",
            )
        ):
            return [
                "institutional investment committee reviewing a quantum roadmap",
                "split capital allocation board showing pause versus continued investment",
                "major bank strategy desk with mixed momentum signals",
            ]
        return [
            "quantum processor glow above a financial strategy desk",
            "portfolio optimization board linked by probability lines",
            "market volatility dashboard reviewed by analysts",
        ]
    rules: tuple[tuple[tuple[str, ...], list[str]], ...] = (
        (
            ("\ubaa8\ub798 \uc704", "\ube44\uc2b7\ud569\ub2c8\ub2e4"),
            ["person running on sand", "shallow footprints", "soft sand resistance"],
        ),
        (
            ("\ubc1c\uc790\uad6d", "\uc758\uc2ec"),
            ["shallow footprints in sand", "fading trail marks", "disturbed sand surface"],
        ),
        (
            ("\uc5b4\ub514\ub85c \uac00\uace0", "\uc124\uba85"),
            ["unfinished route sketch", "question card on a desk", "faded destination mark"],
        ),
        (
            ("\uac00\uce58", "\uc9c8\ubb38"),
            ["open notebook with one underlined phrase", "question card on a table", "quiet window light"],
        ),
        (
            ("\ud55c \ud398\uc774\uc9c0", "\ud55c \ubb38\uc7a5", "\ud55c \uc0ac\ub78c"),
            ["open book page", "pen writing one sentence", "a sincere handwritten note"],
        ),
        (
            ("\ub290\ub824", "\uad1c\ucc2e"),
            ["slow deliberate footsteps", "soft dawn walkway", "steady forward motion"],
        ),
        (
            ("\uc774 \uae38", "\uc789\uc9c0 \uc54a"),
            ["person walking a quiet trail", "guiding light ahead", "steady footsteps"],
        ),
        (
            ("\ud758\uc5b4\uc9c0\uc9c0", "\ubc18\ubcf5"),
            ["aligned handwritten notes", "single lit destination", "steady footprints on one trail"],
        ),
        (
            ("\ud53c\uace4", "\ud55c \uc2dc\uac04"),
            ["steady footsteps on one marked trail", "soft morning light on a clear route", "focused destination ahead"],
        ),
        (
            ("\ubc29\ud5a5\uc774 \uc815\ud574\uc9c0", "\uacb0\uc2ec"),
            ["small handwritten checklist", "single marked route line", "calm morning desk"],
        ),
        (
            ("\uc774 \uae38\uc744 \uac77", "\uc789\uc9c0 \uc54a"),
            ["person walking a quiet trail", "guiding light ahead", "steady footsteps"],
        ),
        (
            ("\uc88b\uc740 \uc778\uc0dd", "\uc774 \uae38"),
            ["person walking a quiet trail", "guiding light ahead", "steady footsteps"],
        ),
        (
            ("\ubc29\ud5a5\uc744 \uc783\uc9c0", "\uac00\uae4c\uc774"),
            ["steady footsteps toward a warm horizon", "single trail leading forward", "distant welcoming light"],
        ),
        (
            ("\uac19\uc740 \ud55c \uc2dc\uac04", "\uc9c0\uce69"),
            ["steady footsteps on one clear trail", "soft morning light on a marked path", "one destination light"],
        ),
    )
    for needles, tokens_for_rule in rules:
        if all(needle in lowered for needle in needles):
            return list(tokens_for_rule)
    return []


def _semantic_anchor_type(
    *,
    sentence: str,
    domain: str,
    composition_template: str,
    must_show: list[str],
) -> SemanticAnchorType:
    lowered = f"{sentence.lower()} {composition_template.lower()} {' '.join(must_show).lower()}"
    if domain in {"news_explainer", "ai_policy_conflict"}:
        return "comparison_frame"
    if any(
        needle in lowered
        for needle in (
            "future",
            "outlook",
            "direction",
            "roadmap",
            "growth driver",
            "\ubbf8\ub798",
            "\ubc29\ud5a5",
            "\uc804\ub9dd",
            "\ub85c\ub4dc\ub9f5",
            "\uc131\uc7a5 \ub3d9\ub825",
            "\uac8c\uc784 \uccb4\uc778\uc800",
        )
    ):
        return "future_outlook"
    if any(
        needle in lowered
        for needle in (
            "barrier",
            "limit",
            "limitation",
            "challenge",
            "bottleneck",
            "wall",
            "friction",
            "\ud55c\uacc4",
            "\ud55c\uacc4\uc810",
            "\ubcbd",
            "\ub9c8\ucc30",
        )
    ) and not any(
        needle in lowered
        for needle in (
            "\ud3ec\ud2b8\ud3f4\ub9ac\uc624",
            "\ubcc0\ub3d9\uc131",
            "portfolio",
            "volatility",
            "allocation",
        )
    ):
        return "technical_barrier"
    if any(
        needle in lowered
        for needle in (
            "investment",
            "investor",
            "capital",
            "committee",
            "bank",
            "institution",
            "\ud22c\uc790",
            "\uc740\ud589",
            "\uae30\uad00",
            "\uc704\uc6d0\ud68c",
        )
    ):
        return "institutional_decision"
    if any(
        needle in lowered
        for needle in (
            "market",
            "portfolio",
            "volatility",
            "allocation",
            "probability",
            "signal",
            "\uc2dc\uc7a5",
            "\ud3ec\ud2b8\ud3f4\ub9ac\uc624",
            "\ubcc0\ub3d9\uc131",
            "\ubc30\ubd84",
            "\ud655\ub960",
        )
    ):
        return "market_structure"
    if any(
        needle in lowered
        for needle in (
            "compare",
            "comparison",
            "split",
            "versus",
            "timeline",
            "axis",
            "\ube44\uad50",
            "\uc5c7\uac08",
            "\uac08\ub9bc",
            "\uc2dc\uc810",
        )
    ):
        return "comparison_frame"
    if any(
        needle in lowered
        for needle in (
            "continue",
            "pause",
            "delay",
            "slow",
            "momentum",
            "\uc9c0\uc18d",
            "\uc870\uc808",
            "\ub290\ucd94",
            "\uc9c0\uc5f0",
            "\uc18d\ub3c4",
        )
    ):
        return "investment_signal"
    return "generic"


def _semantic_anchor_tokens(
    *,
    sentence: str,
    domain: str,
    primary_keywords: list[str],
    must_show: list[str],
    composition_template: str,
) -> list[str]:
    preferred = _safe_visual_list(primary_keywords + must_show, limit=4)
    if preferred:
        return preferred
    fallback = _essay_semantic_tokens(sentence) if domain == "essay" else []
    if fallback:
        return _safe_visual_list(fallback, limit=4)
    return _safe_visual_list(_extract_concrete_tokens(sentence), limit=4)


def _visual_mode_candidates(
    *,
    sentence: str,
    domain: str,
    must_show: list[str],
    composition_template: str = "",
    semantic_anchor_type: SemanticAnchorType = "generic",
) -> list[VisualSceneMode]:
    sentence_lower = sentence.lower()
    lowered = f"{sentence_lower} {' '.join(must_show)} {composition_template}".lower()
    if domain in {"news_explainer", "ai_policy_conflict"}:
        return ["simple_explainer", "data_diagram", "symbolic_concept"]
    if domain == "tech":
        return ["editorial_scene", "data_diagram", "simple_explainer"]
    if domain != "essay":
        return ["editorial_scene", "symbolic_concept", "simple_explainer"]
    if semantic_anchor_type == "technical_barrier":
        return ["symbolic_concept", "data_diagram", "editorial_scene"]
    if semantic_anchor_type == "institutional_decision":
        return ["editorial_scene", "data_diagram", "symbolic_concept"]
    if semantic_anchor_type == "investment_signal":
        return ["editorial_scene", "simple_explainer", "symbolic_concept"]
    if semantic_anchor_type == "market_structure":
        return ["data_diagram", "symbolic_concept", "editorial_scene"]
    if semantic_anchor_type == "comparison_frame":
        return ["simple_explainer", "data_diagram", "symbolic_concept"]
    if semantic_anchor_type == "future_outlook":
        return ["symbolic_concept", "simple_explainer", "editorial_scene"]
    if any(
        needle in sentence_lower
        for needle in (
            "barrier",
            "limit",
            "limitation",
            "challenge",
            "bottleneck",
            "gap",
            "mismatch",
            "slow",
            "delay",
            "pause",
            "한계",
            "한계점",
            "장벽",
            "과제",
            "격차",
            "지연",
        )
    ):
        return ["symbolic_concept", "simple_explainer", "editorial_scene"]
    if any(
        needle in sentence_lower
        for needle in (
            "institution",
            "committee",
            "analyst",
            "investment",
            "investor",
            "bank",
            "financial company",
            "major bank",
            "기관",
            "위원회",
            "투자",
            "금융사",
            "은행",
        )
    ):
        return ["editorial_scene", "symbolic_concept", "data_diagram"]
    if any(
        needle in sentence_lower
        for needle in (
            "future",
            "expectation",
            "promise",
            "growth driver",
            "concept",
            "game changer",
            "전망",
            "기대",
            "미래",
            "성장 동력",
            "게임 체인저",
        )
    ):
        return ["simple_explainer", "symbolic_concept", "editorial_scene"]
    if any(
        needle in lowered
        for needle in (
            "probability",
            "risk",
            "variable",
            "comparison",
            "compare",
            "allocation",
            "signal",
            "portfolio",
            "volatility",
            "확률",
            "위험",
            "변수",
            "비교",
            "배분",
            "포트폴리오",
            "변동성",
        )
    ):
        return ["data_diagram", "symbolic_concept", "editorial_scene"]
    if any(
        needle in lowered
        for needle in (
            "bank",
            "financial",
            "finance",
            "investment",
            "institution",
            "committee",
            "analyst",
            "market",
            "quantum",
            "금융",
            "은행",
            "투자",
            "기관",
            "위원회",
            "시장",
            "양자",
        )
    ):
        return ["editorial_scene", "symbolic_concept", "data_diagram"]
    return ["symbolic_concept", "editorial_scene", "simple_explainer"]


def _choose_visual_mode(
    *,
    sentence: str,
    domain: str,
    must_show: list[str],
    composition_template: str = "",
    semantic_anchor_type: SemanticAnchorType = "generic",
    previous_mode: VisualSceneMode | None = None,
) -> VisualSceneMode:
    candidates = _visual_mode_candidates(
        sentence=sentence,
        domain=domain,
        must_show=must_show,
        composition_template=composition_template,
        semantic_anchor_type=semantic_anchor_type,
    )
    if previous_mode is not None:
        for candidate in candidates:
            if candidate != previous_mode:
                return candidate
    return candidates[0]


def _scene_fields_for_visual_mode(
    *,
    visual_mode: VisualSceneMode,
    must_show: list[str],
    brief_scene: str,
    domain: str,
    semantic_anchor_type: SemanticAnchorType = "generic",
) -> tuple[str, str, str]:
    scene_anchor = brief_scene.strip() or "grounded editorial environment"
    hero_subject = must_show[0] if must_show else ""
    symbolic_marker = must_show[1] if len(must_show) > 1 else ""
    if visual_mode == "editorial_scene":
        if domain == "essay":
            if semantic_anchor_type == "institutional_decision":
                scene_anchor = "institutional finance strategy environment"
            elif semantic_anchor_type == "investment_signal":
                scene_anchor = "capital allocation review environment"
            elif semantic_anchor_type == "market_structure":
                scene_anchor = "market analysis environment"
            elif any(term in hero_subject.lower() for term in _OFFICE_SCENE_TERMS):
                scene_anchor = "institutional finance environment"
        return scene_anchor, hero_subject, symbolic_marker
    if visual_mode == "symbolic_concept":
        if semantic_anchor_type == "technical_barrier":
            scene_anchor = "lab-to-market barrier concept environment"
        elif semantic_anchor_type == "future_outlook":
            scene_anchor = "future outlook concept environment"
        else:
            scene_anchor = "clean editorial concept environment"
        return scene_anchor, hero_subject, symbolic_marker
    if visual_mode == "data_diagram":
        if semantic_anchor_type == "market_structure":
            scene_anchor = "plain warm portfolio comparison background"
        else:
            scene_anchor = "plain warm comparison background"
        if not symbolic_marker and len(must_show) > 2:
            symbolic_marker = must_show[2]
        return scene_anchor, hero_subject, symbolic_marker
    if semantic_anchor_type == "comparison_frame":
        scene_anchor = "plain warm comparison explainer background"
    elif semantic_anchor_type == "future_outlook":
        scene_anchor = "plain warm roadmap explainer background"
    else:
        scene_anchor = "plain warm explainer background"
    return scene_anchor, hero_subject, symbolic_marker


def _apply_adjacent_visual_diversity(entries: list[VisualPlanEntry], *, domain: str) -> list[VisualPlanEntry]:
    if domain != "essay":
        return entries
    diversified: list[VisualPlanEntry] = []
    previous_mode: VisualSceneMode | None = None
    for entry in entries:
        current_mode = cast(VisualSceneMode, str(entry.get("visual_mode") or ""))
        if current_mode not in _VISUAL_MODE_SEQUENCE:
            current_mode = _choose_visual_mode(
                sentence=entry["sentence"],
                domain=domain,
                must_show=entry["must_show"],
                composition_template=str(entry.get("composition_template", "")).strip(),
                semantic_anchor_type=cast(SemanticAnchorType, str(entry.get("semantic_anchor_type") or "generic")),
                previous_mode=previous_mode,
            )
            updated = dict(entry)
            updated["visual_mode"] = current_mode
            scene_anchor, hero_subject, symbolic_marker = _scene_fields_for_visual_mode(
                visual_mode=current_mode,
                must_show=entry["must_show"],
                brief_scene=entry["visual_metaphor"],
                domain=domain,
                semantic_anchor_type=cast(SemanticAnchorType, str(entry.get("semantic_anchor_type") or "generic")),
            )
            updated["scene_anchor"] = scene_anchor
            updated["hero_subject"] = hero_subject
            updated["symbolic_marker"] = symbolic_marker
            entry = cast(VisualPlanEntry, updated)
        elif previous_mode == current_mode:
            replacement = _choose_visual_mode(
                sentence=entry["sentence"],
                domain=domain,
                must_show=entry["must_show"],
                composition_template=str(entry.get("composition_template", "")).strip(),
                semantic_anchor_type=cast(SemanticAnchorType, str(entry.get("semantic_anchor_type") or "generic")),
                previous_mode=previous_mode,
            )
            if replacement != current_mode:
                updated = dict(entry)
                updated["visual_mode"] = replacement
                scene_anchor, hero_subject, symbolic_marker = _scene_fields_for_visual_mode(
                    visual_mode=replacement,
                    must_show=entry["must_show"],
                    brief_scene=entry["visual_metaphor"],
                    domain=domain,
                    semantic_anchor_type=cast(SemanticAnchorType, str(entry.get("semantic_anchor_type") or "generic")),
                )
                updated["scene_anchor"] = scene_anchor
                updated["hero_subject"] = hero_subject
                updated["symbolic_marker"] = symbolic_marker
                entry = cast(VisualPlanEntry, updated)
                current_mode = replacement
        diversified.append(entry)
        previous_mode = current_mode
    return diversified


def _safe_visual_list(values: list[str], *, limit: int = 3) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        item = value.strip()
        lowered = item.lower()
        if not item or lowered in _GENERIC_SENTENCE_GLUE:
            continue
        if _HANGUL_TOKEN_RE.fullmatch(lowered):
            continue
        if item not in cleaned:
            cleaned.append(item)
        if len(cleaned) >= limit:
            break
    return cleaned


def _safe_brief_prop(value: str) -> str:
    item = value.strip()
    lowered = item.lower()
    if not item or lowered in _GENERIC_SENTENCE_GLUE:
        return ""
    if _HANGUL_TOKEN_RE.fullmatch(lowered):
        return ""
    return item


def _news_explainer_tokens(sentence: str) -> list[str]:
    lowered = sentence.lower()
    rules: tuple[tuple[tuple[str, ...], list[str]], ...] = (
        (
            ("댓글", "관리"),
            [
                "browser news article card with comment bubbles",
                "policy update arrow and settings gear icon",
                "election ballot icon",
            ],
        ),
        (
            ("공감", "비공감", "급증"),
            [
                "thumbs up and thumbs down counters rising sharply",
                "warning sensor icon beside an article card",
                "news article comment panel",
            ],
        ),
        (
            ("공감", "비공감", "폭증"),
            [
                "thumbs up and thumbs down counters rising sharply",
                "short timer with warning badge",
                "news article comment panel",
            ],
        ),
        (
            ("공감", "비공감", "몰리"),
            [
                "thumbs up and thumbs down counters rising sharply",
                "short timer with warning badge",
                "news article comment panel",
            ],
        ),
        (
            ("정렬", "댓글"),
            [
                "comment list with sort slider",
                "filter funnel and direction arrow icon",
                "one-sided reaction wave being reduced",
            ],
        ),
        (
            ("이상 징후", "언론사"),
            [
                "alert arrow from platform monitor to newsroom desk icon",
                "envelope and bell icon",
                "news article comment panel",
            ],
        ),
        (
            ("알림", "언론사"),
            [
                "alert arrow from platform monitor to newsroom desk icon",
                "envelope and bell icon",
                "newsroom desk icon",
            ],
        ),
        (
            ("감지 기준", "대응"),
            [
                "detection threshold tuning knobs",
                "fast response arrow to newsroom desk icon",
                "warning sensor icon",
            ],
        ),
        (
            ("좌표찍기", "여론"),
            [
                "many small nodes pointing at one comment panel",
                "public opinion scale bending under pressure",
                "election ballot icon",
            ],
        ),
        (
            ("조직적", "여론"),
            [
                "many small nodes pointing at one comment panel",
                "public opinion scale bending under pressure",
                "coordinated reaction flow",
            ],
        ),
        (
            ("인기 댓글", "의심"),
            [
                "inflated popular comment bubble",
                "user icon with question mark bubble",
                "news article comment panel",
            ],
        ),
        (
            ("이용자", "의미"),
            [
                "user icon viewing a news comment panel",
                "small question mark bubble",
                "news article comment bubbles",
            ],
        ),
        (
            ("만능 해법",),
            [
                "shield icon with visible gaps",
                "comment panel still exposed to small warning signs",
                "limited protection symbol",
            ],
        ),
        (
            ("댓글 공간", "대응 속도"),
            [
                "abnormal signal revealed early in comment panel",
                "fast response arrow",
                "news article comment bubbles preserved",
            ],
        ),
    )
    for needles, tokens_for_rule in rules:
        if all(needle in lowered for needle in needles):
            return list(tokens_for_rule)
    if any(needle in lowered for needle in ("뉴스", "기사", "댓글")):
        return [
            "browser news article card with comment bubbles",
            "policy update arrow and settings gear icon",
            "news article comment panel",
        ]
    if any(needle in lowered for needle in ("언론사", "알림", "메일")):
        return [
            "alert arrow from platform monitor to newsroom desk icon",
            "envelope and bell icon",
            "newsroom desk icon",
        ]
    if any(needle in lowered for needle in ("여론", "선거", "대선")):
        return [
            "public opinion scale bending under pressure",
            "election ballot icon",
            "comment panel pressure lines",
        ]
    return []


def _domain_vocab_tokens(sentence: str, domain: str) -> tuple[list[str], str]:
    lowered = sentence.lower()
    if domain == "ai_policy_conflict":
        has_hearing = any(
            needle in lowered
            for needle in ("senate", "hearing", "defense", "criticism", "\uc0c1\uc6d0", "\uccad\ubb38", "\uad6d\ubc29", "\ube44\ud310")
        )
        has_access = any(
            needle in lowered
            for needle in ("white house", "restriction", "blocked", "spread", "\ubc31\uc545\uad00", "\uc81c\ub3d9", "\uc81c\ud55c", "\ud655\uc0b0")
        )
        if has_hearing and has_access:
            return [
                "senate hearing room and White House security gate",
                "glowing AI company cube under government pressure",
                "red warning folder and stop barrier",
            ], "PolicyPressureDual"
        if has_access:
            return [
                "White House security gate",
                "glowing AI network sphere stopped at the gate",
                "red stop barrier blocking the AI model spread",
            ], "AccessRestriction"
        if has_hearing:
            return [
                "senate hearing room",
                "empty hearing podium facing a glowing AI model cube",
                "red warning folder on the hearing table",
            ], "HearingCriticism"
    vocab = _load_vocab(domain)
    terms = vocab.get("terms")
    if not isinstance(terms, list):
        return [], ""
    matches: list[tuple[int, dict[str, object]]] = []
    for item in terms:
        if not isinstance(item, dict):
            continue
        raw_keywords = item.get("keywords")
        if not isinstance(raw_keywords, list):
            continue
        keywords = [
            keyword.strip().lower()
            for keyword in raw_keywords
            if isinstance(keyword, str) and keyword.strip()
        ]
        hits = [keyword for keyword in keywords if keyword in lowered]
        if not hits:
            continue
        score = ((len(hits) * 100) + max(len(hit) for hit in hits)) if domain == "ev_battery" else max(len(hit) for hit in hits)
        matches.append((score, item))
    matches.sort(key=lambda pair: pair[0], reverse=True)
    if not matches:
        return [], ""
    best = matches[0][1]
    tokens: list[str] = []
    if domain == "ai_policy_conflict":
        for key in ("scene", "hero_object", "symbol", "relation"):
            value = best.get(key)
            if isinstance(value, str) and value.strip():
                tokens.append(value.strip())
    else:
        for key in ("icon", "support", "relation"):
            value = best.get(key)
            if isinstance(value, str) and value.strip():
                tokens.append(value.strip())
    composition_template = best.get("composition_template")
    return list(dict.fromkeys(tokens)), composition_template.strip() if isinstance(composition_template, str) else ""


def _contains_growth_metric(sentence: str) -> bool:
    lowered = sentence.lower()
    if re.search(r"\d+\s*%", lowered):
        return True
    return any(
        term in lowered
        for term in (
            "\uc804\ub144 \ub300\ube44",
            "\uc804\uc8fc \ub300\ube44",
            "\uae09\uc99d",
            "\uc99d\uac00",
            "\ub298\uc5c8",
            "\uc0c1\uc2b9 \ub9c9\ub300",
            "\uc22b\uc790 \ubc30\uc9c0",
            "\uc131\uc7a5 \uc18d\ub3c4",
            "\uc2e0\uaddc \uc774\uc6a9\uc790",
            "\uc77c\uc77c\ud65c\uc131\uc774\uc6a9\uc790",
            "dau",
            "new users",
            "active users",
            "growth",
            "increased",
        )
    )


def _entry_mentions_growth_metric(entry: VisualPlanEntry) -> bool:
    haystack = " ".join(
        [
            *entry["primary_keywords"],
            *entry["secondary_keywords"],
            *entry["must_show"],
            entry["visual_metaphor"],
            entry.get("composition_template", ""),
        ]
    ).lower()
    return any(
        term in haystack
        for term in (
            "growth",
            "metric",
            "bar",
            "chart",
            "arrow",
            "130",
            "60",
            "percent",
            "\uc99d\uac00",
            "\uae09\uc99d",
        )
    )


def _repair_growth_metric_entry(entry: VisualPlanEntry) -> VisualPlanEntry:
    repaired = dict(entry)
    existing_keywords = _string_list(repaired.get("primary_keywords"))
    repaired["primary_keywords"] = list(
        dict.fromkeys(
            [
                "user growth metrics",
                "new users 130 percent increase",
                "daily active users 60 percent increase",
                *existing_keywords[:2],
            ]
        )
    )
    repaired["secondary_keywords"] = [
        "ChatGPT image model adoption",
        "week over week growth",
    ]
    repaired["must_show"] = list(_GROWTH_METRIC_MUST_SHOW)
    repaired["may_show"] = [
        "simple app icon",
        "small user icons beside the bars",
    ]
    repaired["visual_metaphor"] = (
        "two clean rising bars compare new users up 130 percent and daily active users up 60 percent"
    )
    repaired["subject_modes"] = ["symbolic", "object_metaphor"]
    repaired["prompt_hint"] = "simple diagram layout, large readable numeric badges, no words except numbers"
    repaired["composition_template"] = "GrowthMetricComparison"
    repaired["source"] = "growth_metric_repair"
    avoid = _string_list(repaired.get("avoid"), limit=12)
    for item in ("photorealistic office", "generic dashboard", "tiny unreadable chart", "dense labels"):
        if item not in avoid:
            avoid.append(item)
    repaired["avoid"] = avoid
    return cast(VisualPlanEntry, repaired)


def _repair_ai_policy_conflict_entry(sentence: str, entry: VisualPlanEntry) -> VisualPlanEntry:
    vocab_tokens, composition_template = _domain_vocab_tokens(sentence, "ai_policy_conflict")
    if not vocab_tokens:
        vocab_tokens = [
            "government briefing room table",
            "glowing AI company cube behind glass",
            "warning folder between the government side and AI company cube",
        ]
        composition_template = "GovernmentVsCompany"
    repaired = dict(entry)
    repaired["primary_keywords"] = list(dict.fromkeys([*vocab_tokens[:2], *entry["primary_keywords"][:2]]))
    repaired["secondary_keywords"] = list(dict.fromkeys([*vocab_tokens[1:3], *entry["secondary_keywords"][:1]]))
    repaired["must_show"] = vocab_tokens[:2]
    repaired["may_show"] = []
    repaired["visual_metaphor"] = (
        f"{vocab_tokens[0]} with {vocab_tokens[1]}" if len(vocab_tokens) > 1 else ", ".join(vocab_tokens)
    )
    repaired["subject_modes"] = ["environment", "object_metaphor"]
    repaired["prompt_hint"] = (
        "editorial symbolic scene, real environment anchor, one hero object, one supporting symbol, no diagram slide"
    )
    repaired["composition_template"] = composition_template or "GovernmentVsCompany"
    repaired["source"] = f"{entry['source']}_policy_template_repair"
    avoid = _string_list(repaired.get("avoid"), limit=16)
    for item in (
        "Anthropic logo",
        "company logo",
        "abstract radar dashboard",
        "dense analytics dashboard",
        "tiny scattered icons",
        "generic blueprint interface",
        "gpu rack cluster",
        "browser window",
        "terminal panel",
        "detailed architecture",
        "floor plan",
        "document panels",
        "many small buildings",
    ):
        if item not in avoid:
            avoid.append(item)
    repaired["avoid"] = avoid
    return cast(VisualPlanEntry, repaired)


def _vocab_summary(vocab: dict[str, object]) -> str:
    terms = vocab.get("terms")
    if not isinstance(terms, list):
        return ""
    lines: list[str] = []
    for item in terms[:10]:
        if not isinstance(item, dict):
            continue
        keywords = item.get("keywords")
        concept = item.get("concept")
        metaphor_examples = item.get("metaphor_examples")
        avoid = item.get("avoid")
        icon = item.get("icon")
        support = item.get("support")
        relation = item.get("relation")
        composition_template = item.get("composition_template")
        layout = item.get("layout")
        keyword_text = ", ".join(keyword for keyword in keywords if isinstance(keyword, str)) if isinstance(keywords, list) else ""
        example_text = "; ".join(example for example in metaphor_examples if isinstance(example, str)) if isinstance(metaphor_examples, list) else ""
        avoid_text = ", ".join(word for word in avoid if isinstance(word, str)) if isinstance(avoid, list) else ""
        lines.append(
            f"- keywords: {keyword_text}\n"
            f"  concept: {concept if isinstance(concept, str) else ''}\n"
            f"  metaphor_examples: {example_text}\n"
            f"  icon: {icon if isinstance(icon, str) else ''}\n"
            f"  support: {support if isinstance(support, str) else ''}\n"
            f"  relation: {relation if isinstance(relation, str) else ''}\n"
            f"  composition_template: {composition_template if isinstance(composition_template, str) else ''}\n"
            f"  layout: {layout if isinstance(layout, str) else ''}\n"
            f"  avoid: {avoid_text}"
        )
    return "\n".join(lines)


_OPERATING_GUIDE_PATH = "docs/media-prompt-operating-guide.md"


def _operating_guide_compact_rules(domain: str) -> str:
    base_rules = [
        f"Operating guide source: {_OPERATING_GUIDE_PATH}",
        "Use the guide as policy: preserve sentence-specific main_subject, action, environment, must_show, and avoid.",
        "Do not use placeholder phrases such as 'concrete visual subject tied to the sentence'.",
        "Do not drift into generic office, dashboard, empty building, road, signpost, checklist, or city scenes unless the sentence explicitly requires them.",
        "Set lora_policy to none unless the sentence is a simple non-real-person educational metaphor.",
        "Do not use stickfigure or Stickfigures LoRA for named real executives, political/business delegation news, semiconductor business news, or EV battery topics.",
        "Prefer txt2img_sdxl_basic unless a style reference or ControlNet input is explicitly available.",
    ]
    domain_rules: dict[str, list[str]] = {
        "ev_battery": [
            "EV battery domain: must_show should include EV/battery cell or pack plus the sentence-specific concept such as LFP, NCM, solid-state, price, safety, range, charging, or energy density.",
            "EV battery domain: avoid isolated glossy battery product renders, unrelated showrooms, server rooms, stick figures, and cartoon mascots.",
            "EV battery domain: template_hint should be txt2img_sdxl_basic and lora_policy should be none.",
        ],
        "news_explainer": [
            "News explainer domain: show the news mechanism or institution, such as article confirmation, newsroom, official announcement, public reaction, timeline, or notification flow.",
            "News explainer domain: avoid generic airport displays, random dashboards, and decorative UI screens unless the sentence requires them.",
        ],
        "ai_policy_conflict": [
            "AI policy conflict domain: show institution, AI company/model, policy/restriction/security object, and the conflict action.",
            "AI policy conflict domain: avoid generic GPU racks, browser windows, server rooms, and abstract icon clouds unless explicitly required.",
        ],
        "tech": [
            "Tech domain: preserve chip, GPU, semiconductor, AI infrastructure, datacenter, company, or business-government context when present.",
            "Tech domain semiconductor business news sub-strategy: for Nvidia, Jensen Huang, CEO, Trump, delegation, Air Force One, Beijing, Alaska, or China-trip sentences, show named executive proxy, company cue, official request/delegation/travel cue, and avoid empty conference buildings or unrelated server rooms.",
        ],
        "food_trend": [
            "Food trend domain: product or food item must dominate; show retail, cafe, bakery, shelf, drink, dessert, or ingredient context when relevant.",
            "Food trend domain: avoid empty interiors and generic industry metaphors.",
        ],
        "agriculture_environment": [
            "Agriculture/environment domain: show soil, field, crop, plant, biodegradable film, sample, or environmental material tied to the sentence.",
            "Agriculture/environment domain: avoid AI brain, server rack, and unrelated office scenes.",
        ],
        "science_materials": [
            "Science/materials domain: show polymer, cellulose, lab sample, thin film, material test, or decomposition context tied to the sentence.",
            "Science/materials domain: avoid generic AI or office imagery.",
        ],
        "essay": [
            "Essay domain: use specific object/environment metaphors and avoid repeated checklist, road fork, compass, signpost, or empty office defaults.",
        ],
        "generic": [
            "Generic domain: pick a concrete scene from sentence meaning; avoid safe but meaningless stock imagery.",
        ],
    }
    return "\n".join(f"- {rule}" for rule in [*base_rules, *domain_rules.get(domain, [])])


def _planner_system_prompt(domain: str) -> str:
    return (
        "You are a visual planning model for Korean narrated videos.\n"
        "- Return only valid JSON.\n"
        "- Infer the sentence meaning, not just literal nouns.\n"
        "- Prefer environment or object metaphors for abstract essay lines.\n"
        "- Avoid weird closeups, duplicate people, and irrelevant objects.\n"
        "- If a sentence contains a vivid physical simile, prefer that literal scene over a generic symbol.\n"
        "- Do not turn every path or direction sentence into a vehicle road scene.\n"
        "- Do not collapse multiple essay sentences into the same compass/checklist metaphor.\n"
        "- For AI policy conflict, show the relationship: government actor, AI company/model, and the action such as criticism, restriction, oversight, or security balance.\n"
        "- For AI policy conflict, avoid generic GPU racks, browser windows, server rooms, and abstract icon clouds unless the sentence explicitly asks for them.\n"
        f"{_operating_guide_compact_rules(domain)}\n"
        f"- The current domain is {domain}.\n"
    )


def _planner_prompt(project: ProjectRecord, domain: str, vocab: dict[str, object]) -> str:
    sentence_lines = "\n".join(
        f"{idx}. {sentence.strip()}"
        for idx, sentence in enumerate(project["sentences"])
        if sentence.strip()
    )
    return (
        "Create a JSON array with one item per sentence.\n\n"
        "[Output Schema]\n"
        "[\n"
        "  {\n"
        '    "sentence_idx": 0,\n'
        '    "sentence": "...",\n'
        '    "core_meaning": "...",\n'
        '    "primary_keywords": ["..."],\n'
        '    "secondary_keywords": ["..."],\n'
        '    "visual_metaphor": "...",\n'
        '    "subject_modes": ["environment"],\n'
        '    "must_show": ["..."],\n'
        '    "may_show": ["..."],\n'
        '    "avoid": ["..."],\n'
        '    "prompt_hint": "...",\n'
        '    "vocab_refs": ["direction and life choice"],\n'
        '    "visual_priority": "core_metaphor",\n'
        '    "literal_simile": "",\n'
        '    "allow_objects": [],\n'
        '    "visual_mode": "symbolic_concept",\n'
        '    "semantic_anchor_type": "market_structure",\n'
        '    "semantic_anchor_tokens": ["portfolio optimization", "market volatility"],\n'
        '    "sub_strategy": "",\n'
        '    "template_hint": "txt2img_sdxl_basic",\n'
        '    "lora_policy": "none"\n'
        "  }\n"
        "]\n\n"
        "[Rules]\n"
        "- Each sentence must produce one item.\n"
        "- Use concise English phrases for must_show, may_show, and avoid so prompt compilation is stable.\n"
        "- Keep primary_keywords focused on 3-5 core concepts.\n"
        "- Use visual_mode from: editorial_scene, symbolic_concept, simple_explainer, data_diagram.\n"
        "- Use semantic_anchor_type from: institutional_decision, technical_barrier, investment_signal, market_structure, comparison_frame, future_outlook, generic.\n"
        "- semantic_anchor_tokens must preserve the sentence-specific business or editorial meaning, not generic office props.\n"
        "- Use sub_strategy only when helpful, for example semiconductor_business_news, political_business_delegation, executive_travel_diplomacy, or finance_market_explainer.\n"
        "- Use template_hint from: txt2img_sdxl_basic, txt2img_sdxl_lora, txt2img_sdxl_stickman_lora, txt2img_sdxl_lightning, txt2img_sdxl_ipadapter_style, txt2img_sdxl_ipadapter_style_lora, txt2img_sdxl_controlnet_depth.\n"
        "- Use lora_policy from: none, stickman_allowed, style_reference_allowed, controlnet_allowed.\n"
        "- For named real executives, political/business delegation, semiconductor business news, and EV battery topics, lora_policy must be none.\n"
        "- Use subject_modes from: person, environment, object_metaphor, symbolic.\n"
        "- If the line is abstract, prefer environment or object_metaphor.\n"
        "- Do not default to two similar people.\n"
        "- Do not make hand-only or phone-screen-only closeups unless the sentence truly needs that framing.\n"
        "- If the sentence contains a literal simile or concrete physical comparison, set visual_priority to literal_simile and fill literal_simile.\n"
        "- Do not automatically use compass or road for every direction sentence.\n"
        "- If you use a road or path image in essay domain and vehicles are not central, add car, vehicle, traffic to avoid.\n"
        "- Keep must_show distinct across sentences; do not repeat the same generic symbol more than twice.\n\n"
        "- Before falling back to a generic office or explainer scene, identify the sentence's business meaning such as capital allocation, commercialization timing, strategy reset, investment split, or future outlook.\n\n"
        "[Vocabulary Guide]\n"
        f"{_vocab_summary(vocab)}\n\n"
        "[Sentences]\n"
        f"{sentence_lines}\n"
    )


def _extract_json_payload(text: str) -> str:
    fenced = _JSON_BLOCK_RE.search(text)
    if fenced:
        return fenced.group(1).strip()
    return text.strip()


def _quick_ollama_ready() -> bool:
    if LLM_PROVIDER == "lmstudio":
        loaded_models = loaded_lmstudio_models()
        if loaded_models:
            return SCRIPT_LLM_MODEL in loaded_models
        endpoint = urljoin(LMSTUDIO_BASE_URL.rstrip("/") + "/", "v1/models")
        request = Request(endpoint, method="GET")
        try:
            with urlopen(request, timeout=1.0) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
        except (OSError, URLError, json.JSONDecodeError):
            return False
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            return False
        return any(isinstance(item, dict) and item.get("id") == SCRIPT_LLM_MODEL for item in data)
    else:
        endpoint = urljoin(OLLAMA_BASE_URL.rstrip("/") + "/", "api/tags")
        request = Request(endpoint, method="GET")
        try:
            with urlopen(request, timeout=1.0):
                return True
        except (OSError, URLError):
            return False


def _normalize_subject_modes(raw: object) -> list[VisualPlanSubjectMode]:
    normalized: list[VisualPlanSubjectMode] = []
    if not isinstance(raw, list):
        return list(_DEFAULT_SUBJECT_MODES)
    for item in raw:
        if item in {"person", "environment", "object_metaphor", "symbolic"}:
            normalized.append(item)
    return normalized or list(_DEFAULT_SUBJECT_MODES)


def _string_list(raw: object, *, limit: int = 6) -> list[str]:
    if not isinstance(raw, list):
        return []
    values: list[str] = []
    for item in raw:
        if isinstance(item, str):
            stripped = item.strip()
            if stripped and stripped not in values:
                values.append(stripped)
        if len(values) >= limit:
            break
    return values


def _normalize_visual_priority(raw: object, *, fallback: VisualPriority) -> VisualPriority:
    if raw in {"literal_simile", "core_metaphor", "concrete_action", "object_symbol"}:
        return cast(VisualPriority, raw)
    return fallback


def _is_generic_essay_entry(entry: VisualPlanEntry) -> bool:
    primary = str(entry["must_show"][0]).strip().lower() if entry["must_show"] else ""
    visual_metaphor = str(entry["visual_metaphor"]).strip().lower()
    return primary in _GENERIC_ESSAY_TERMS or visual_metaphor in _GENERIC_ESSAY_TERMS


def _contains_generic_fallback(entry: VisualPlanEntry) -> bool:
    haystack = " ".join(
        [
            *entry["primary_keywords"],
            *entry["must_show"],
            entry["visual_metaphor"],
        ]
    ).lower()
    return any(term in haystack for term in _GENERIC_ESSAY_TERMS)


def _repair_generic_essay_entry(sentence: str, entry: VisualPlanEntry) -> VisualPlanEntry:
    semantic_tokens = _essay_semantic_tokens(sentence)
    if not semantic_tokens:
        return entry
    repaired = dict(entry)
    repaired["primary_keywords"] = semantic_tokens[:3]
    repaired["secondary_keywords"] = semantic_tokens[1:3]
    repaired["must_show"] = semantic_tokens[:3]
    repaired["may_show"] = semantic_tokens[1:2]
    repaired["visual_metaphor"] = ", ".join(semantic_tokens[:2])
    repaired["source"] = "essay_semantic_repair"
    avoid = list(entry["avoid"])
    for item in ("compass on a folded map", "quiet road fork", "large checklist with three bold check marks"):
        if item not in avoid:
            avoid.append(item)
    repaired["avoid"] = avoid
    repaired["semantic_anchor_tokens"] = semantic_tokens[:4]
    repaired["semantic_anchor_type"] = _semantic_anchor_type(
        sentence=sentence,
        domain=str(entry.get("domain") or "essay"),
        composition_template=str(entry.get("composition_template") or ""),
        must_show=semantic_tokens[:3],
    )
    return cast(VisualPlanEntry, repaired)


def _fallback_entry(project: ProjectRecord, sentence_idx: int, sentence: str, domain: str) -> VisualPlanEntry:
    is_tech = domain == "tech"
    vocab = _load_vocab(domain)
    visual_tokens = _extract_visual_tokens(project, sentence, is_tech=is_tech)
    template_key = "tech_documentary" if is_tech else "default"
    brief = build_visual_brief(
        text=sentence,
        visual_tokens=visual_tokens,
        template_key=template_key,
        domain="tech" if is_tech else domain,
    )
    literal_simile = extract_literal_simile(sentence)
    simile_must_show = _lookup_literal_simile_vocab(literal_simile, vocab) if literal_simile else []
    semantic_context = f"{project['title']} {project['compiled_script'] or project['script']} {sentence}"
    semantic_tokens = _essay_semantic_tokens(semantic_context) if domain == "essay" else []
    news_tokens = _news_explainer_tokens(sentence) if domain in {"news_explainer", "ai_policy_conflict"} else []
    vocab_tokens, vocab_composition_template = (
        _domain_vocab_tokens(sentence, domain)
        if domain in {"tech", "ai_policy_conflict", "agriculture_environment", "science_materials", "food_trend", "ev_battery"}
        else ([], "")
    )
    if domain == "tech" and _contains_growth_metric(sentence):
        vocab_tokens = list(_GROWTH_METRIC_MUST_SHOW)
        vocab_composition_template = "GrowthMetricComparison"
    if domain == "food_trend" and not vocab_tokens:
        food_context = f"{sentence} {project['compiled_script'] or project['script']}".lower()
        if any(needle in food_context for needle in ("\uc601\ud5a5\ub825", "\uba48\ucd94\uc9c0", "\ud655\uc7a5", "\uc720\ud1b5", "expand", "spread")):
            vocab_tokens = [
                "convenience store shelf filled with purple packaged drinks",
                "supermarket dessert display with ube products",
                "ube drinks and desserts expand from specialty shops into everyday retail shelves",
            ]
            vocab_composition_template = "RetailShelf"
    sentence_tokens = _extract_concrete_tokens(sentence)
    repeated_terms = _project_repeated_hangul_terms(project) if domain == "food_trend" else []
    primary_keywords = _safe_visual_list(
        vocab_tokens[:3]
        + simile_must_show[:2]
        + news_tokens[:3]
        + semantic_tokens[:3]
        + visual_tokens[:2]
        + sentence_tokens[:2]
        + repeated_terms[:1],
        limit=4,
    )
    subject_modes: list[VisualPlanSubjectMode] = (
        ["environment", "object_metaphor"]
        if domain in {"essay", "news_explainer", "ai_policy_conflict", "food_trend", "ev_battery"}
        else ["person"]
    )
    must_show = list(brief["must_show"])
    if simile_must_show:
        must_show = simile_must_show
    elif news_tokens:
        must_show = news_tokens
    elif vocab_tokens:
        must_show = vocab_tokens
    elif semantic_tokens:
        must_show = semantic_tokens
    elif sentence_tokens:
        must_show = sentence_tokens[:2] + must_show[:1]
    avoid = list(brief["avoid"])
    avoid.extend(domain_global_avoid(vocab))
    if literal_simile or semantic_tokens or news_tokens:
        for generic_item in ("compass on a folded map", "quiet road fork", "large checklist with three bold check marks"):
            if generic_item not in avoid:
                avoid.append(generic_item)
    if domain in {"news_explainer", "ai_policy_conflict"}:
        for generic_item in ("single everyday object in a quiet realistic room", "quiet realistic environment", "empty room", "abstract architecture", "3d sculpture"):
            if generic_item not in avoid:
                avoid.append(generic_item)
    if domain == "food_trend":
        for generic_item in ("single everyday object in a quiet realistic room", "quiet realistic environment", "empty room", "abstract representation of industry", "gear mechanism"):
            if generic_item not in avoid:
                avoid.append(generic_item)
    visual_priority: VisualPriority = "literal_simile" if literal_simile else "core_metaphor"
    if domain == "ev_battery":
        composition_template = vocab_composition_template or "BatteryCellComparison"
    elif domain == "ai_policy_conflict":
        composition_template = vocab_composition_template or _news_composition_template(sentence, news_tokens)
    elif domain == "news_explainer":
        composition_template = _news_composition_template(sentence, news_tokens)
    else:
        composition_template = vocab_composition_template
    secondary_keywords = _safe_visual_list(news_tokens[1:3] or semantic_tokens[1:3] or visual_tokens[1:3], limit=2)
    safe_secondary_prop = _safe_brief_prop(brief["secondary_prop"])
    semantic_anchor_tokens = _semantic_anchor_tokens(
        sentence=sentence,
        domain=domain,
        primary_keywords=primary_keywords,
        must_show=list(dict.fromkeys(item for item in must_show if item.strip())),
        composition_template=composition_template,
    )
    semantic_anchor_type = _semantic_anchor_type(
        sentence=sentence,
        domain=domain,
        composition_template=composition_template,
        must_show=list(dict.fromkeys(item for item in must_show if item.strip())),
    )
    visual_mode = _choose_visual_mode(
        sentence=sentence,
        domain=domain,
        must_show=list(dict.fromkeys(item for item in must_show if item.strip())),
        composition_template=composition_template,
        semantic_anchor_type=semantic_anchor_type,
    )
    scene_anchor, hero_subject, symbolic_marker = _scene_fields_for_visual_mode(
        visual_mode=visual_mode,
        must_show=list(dict.fromkeys(item for item in must_show if item.strip())),
        brief_scene=brief["scene"],
        domain=domain,
        semantic_anchor_type=semantic_anchor_type,
    )
    return {
        "sentence_idx": sentence_idx,
        "sentence": sentence,
        "core_meaning": sentence,
        "primary_keywords": primary_keywords or [_safe_brief_prop(brief["primary_prop"]) or brief["scene"]],
        "secondary_keywords": secondary_keywords,
        "visual_metaphor": literal_simile or (", ".join(news_tokens[:2]) if news_tokens else (", ".join(semantic_tokens[:2]) if semantic_tokens else brief["scene"])),
        "subject_modes": subject_modes,
        "must_show": list(dict.fromkeys(item for item in must_show if item.strip())),
        "may_show": [safe_secondary_prop] if safe_secondary_prop else repeated_terms[:1],
        "avoid": list(dict.fromkeys(item for item in avoid if item.strip())),
        "prompt_hint": "medium or wide shot",
        "vocab_refs": [],
        "domain": domain,
        "source": "fallback",
        "visual_priority": visual_priority,
        "literal_simile": literal_simile,
        "allow_objects": [],
        "composition_template": composition_template,
        "scene_anchor": scene_anchor,
        "hero_subject": hero_subject,
        "symbolic_marker": symbolic_marker,
        "visual_mode": visual_mode,
        "semantic_anchor_type": semantic_anchor_type,
        "semantic_anchor_tokens": semantic_anchor_tokens,
    }


def _news_composition_template(sentence: str, tokens: list[str]) -> str:
    lowered = sentence.lower()
    haystack = f"{lowered} {' '.join(tokens).lower()}"
    if any(term in haystack for term in ("만능", "모든 조작", "shield", "slipping through")):
        return "LimitationShield"
    if any(term in haystack for term in ("이용자", "인기 댓글", "의심", "부풀", "user icon", "magnifier")):
        return "UserView"
    if any(term in haystack for term in ("좌표", "조직", "여론", "왜곡", "public opinion scale")):
        return "CoordinationPressure"
    if any(term in haystack for term in ("감지 기준", "정교", "성패", "threshold", "stopwatch")):
        return "SpeedResponse"
    if any(term in haystack for term in ("없애", "댓글 공간", "드러내", "response speed")):
        return "PreserveAndReveal"
    if any(term in haystack for term in ("정렬", "sorting", "sort slider")):
        return "SortingControl"
    if any(term in haystack for term in ("언론사", "메일", "알림", "newsroom", "alert arrow")):
        return "AlertFlow"
    if any(term in haystack for term in ("공감", "비공감", "급증", "폭증", "counter", "spike")):
        return "SpikeDetection"
    return "SortingControl"


def _normalize_entries(
    project: ProjectRecord,
    raw_entries: object,
    *,
    domain: str,
    source: str,
) -> list[VisualPlanEntry]:
    raw_list = raw_entries if isinstance(raw_entries, list) else []
    normalized: list[VisualPlanEntry] = []
    for sentence_idx, sentence in enumerate(project["sentences"]):
        fallback = _fallback_entry(project, sentence_idx, sentence, domain)
        matched_item: dict[str, object] | None = None
        for item in raw_list:
            if not isinstance(item, dict):
                continue
            raw_idx = item.get("sentence_idx")
            raw_sentence = item.get("sentence")
            if raw_idx == sentence_idx or (isinstance(raw_sentence, str) and raw_sentence.strip() == sentence.strip()):
                matched_item = item
                break
        if matched_item is None:
            normalized.append(fallback)
            continue
        core_meaning = str(matched_item.get("core_meaning") or fallback["core_meaning"]).strip()
        primary_keywords = _string_list(matched_item.get("primary_keywords")) or fallback["primary_keywords"]
        secondary_keywords = _string_list(matched_item.get("secondary_keywords")) or fallback["secondary_keywords"]
        visual_metaphor = str(matched_item.get("visual_metaphor") or fallback["visual_metaphor"]).strip()
        must_show = _string_list(matched_item.get("must_show")) or fallback["must_show"]
        may_show = _string_list(matched_item.get("may_show")) or fallback["may_show"]
        avoid = _string_list(matched_item.get("avoid")) or fallback["avoid"]
        prompt_hint = str(matched_item.get("prompt_hint") or fallback["prompt_hint"]).strip()
        vocab_refs = _string_list(matched_item.get("vocab_refs")) or fallback["vocab_refs"]
        allow_objects = _string_list(matched_item.get("allow_objects")) or fallback.get("allow_objects", [])
        literal_simile = str(matched_item.get("literal_simile") or fallback.get("literal_simile", "")).strip()
        visual_priority = _normalize_visual_priority(
            matched_item.get("visual_priority"),
            fallback=cast(VisualPriority, fallback.get("visual_priority", "core_metaphor")),
        )
        composition_template = str(
            matched_item.get("composition_template")
            or fallback.get("composition_template", "")
            or (_news_composition_template(sentence, must_show) if domain == "news_explainer" else "")
        ).strip()
        scene_anchor = str(matched_item.get("scene_anchor") or fallback.get("scene_anchor", "")).strip()
        hero_subject = str(matched_item.get("hero_subject") or fallback.get("hero_subject", "")).strip()
        symbolic_marker = str(matched_item.get("symbolic_marker") or fallback.get("symbolic_marker", "")).strip()
        visual_mode = str(matched_item.get("visual_mode") or fallback.get("visual_mode", "")).strip()
        semantic_anchor_type_raw = str(
            matched_item.get("semantic_anchor_type") or fallback.get("semantic_anchor_type", "generic")
        ).strip()
        semantic_anchor_tokens = _string_list(matched_item.get("semantic_anchor_tokens"), limit=4) or list(
            fallback.get("semantic_anchor_tokens", [])
        )
        sub_strategy = str(matched_item.get("sub_strategy") or fallback.get("sub_strategy", "")).strip()
        template_hint = str(matched_item.get("template_hint") or fallback.get("template_hint", "")).strip()
        lora_policy = str(matched_item.get("lora_policy") or fallback.get("lora_policy", "")).strip()
        if visual_mode not in _VISUAL_MODE_SEQUENCE:
            visual_mode = _choose_visual_mode(
                sentence=sentence,
                domain=domain,
                must_show=must_show,
                composition_template=composition_template,
                semantic_anchor_type=cast(SemanticAnchorType, semantic_anchor_type_raw or "generic"),
            )
        scene_anchor, hero_subject, symbolic_marker = _scene_fields_for_visual_mode(
            visual_mode=cast(VisualSceneMode, visual_mode),
            must_show=must_show,
            brief_scene=scene_anchor or visual_metaphor or fallback["visual_metaphor"],
            domain=domain,
            semantic_anchor_type=cast(SemanticAnchorType, semantic_anchor_type_raw or "generic"),
        )
        semantic_anchor_type = semantic_anchor_type_raw if semantic_anchor_type_raw in {
            "institutional_decision",
            "technical_barrier",
            "investment_signal",
            "market_structure",
            "comparison_frame",
            "future_outlook",
            "generic",
        } else _semantic_anchor_type(
            sentence=sentence,
            domain=domain,
            composition_template=composition_template,
            must_show=must_show,
        )
        if not semantic_anchor_tokens:
            semantic_anchor_tokens = _semantic_anchor_tokens(
                sentence=sentence,
                domain=domain,
                primary_keywords=primary_keywords,
                must_show=must_show,
                composition_template=composition_template,
            )
        entry: VisualPlanEntry = {
            "sentence_idx": sentence_idx,
            "sentence": sentence,
            "core_meaning": core_meaning or fallback["core_meaning"],
            "primary_keywords": primary_keywords,
            "secondary_keywords": secondary_keywords,
            "visual_metaphor": visual_metaphor or fallback["visual_metaphor"],
            "subject_modes": _normalize_subject_modes(matched_item.get("subject_modes")),
            "must_show": must_show,
            "may_show": may_show,
            "avoid": avoid,
            "prompt_hint": prompt_hint or fallback["prompt_hint"],
            "vocab_refs": vocab_refs,
            "domain": domain,
            "source": source,
            "visual_priority": visual_priority,
            "literal_simile": literal_simile,
            "allow_objects": allow_objects,
            "composition_template": composition_template,
            "scene_anchor": scene_anchor,
            "hero_subject": hero_subject,
            "symbolic_marker": symbolic_marker,
            "visual_mode": cast(VisualSceneMode, visual_mode),
            "semantic_anchor_type": cast(SemanticAnchorType, semantic_anchor_type),
            "semantic_anchor_tokens": semantic_anchor_tokens,
            "sub_strategy": sub_strategy,
            "template_hint": template_hint,
            "lora_policy": lora_policy,
        }
        if domain == "essay" and _is_generic_essay_entry(entry):
            entry = _repair_generic_essay_entry(sentence, entry)
        if domain == "ai_policy_conflict":
            entry = _repair_ai_policy_conflict_entry(sentence, entry)
        if domain == "food_trend" and _contains_generic_fallback(entry):
            entry = fallback
        if domain == "tech" and _contains_growth_metric(sentence) and not _entry_mentions_growth_metric(entry):
            entry = _repair_growth_metric_entry(entry)
        normalized.append(entry)
    return _apply_adjacent_visual_diversity(normalized, domain=domain)


def _load_cached_plan(project: ProjectRecord) -> list[VisualPlanEntry] | None:
    target = _cache_path(project)
    if not target.exists():
        return None
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    hashes = payload.get("sentence_hashes")
    entries = payload.get("entries")
    version = payload.get("planner_version", 1)
    current_domain = _domain_for_project(project)
    if hashes != _sentence_hashes(project):
        return None
    if version != _PLANNER_CACHE_VERSION:
        return None
    cached_domain = str(payload.get("domain") or "").strip()
    if cached_domain and cached_domain != current_domain:
        return None
    return _normalize_entries(
        project,
        entries,
        domain=str(payload.get("domain") or current_domain),
        source=str(payload.get("source") or "cache"),
    )


def _save_plan(project: ProjectRecord, *, domain: str, model: str, source: str, entries: list[VisualPlanEntry]) -> None:
    target = _cache_path(project)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "project_id": project["id"],
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "domain": domain,
        "model": model,
        "source": source,
        "planner_version": _PLANNER_CACHE_VERSION,
        "sentence_hashes": _sentence_hashes(project),
        "entries": entries,
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _project_sentence_slice(project: ProjectRecord, start_idx: int, sentences: list[str]) -> ProjectRecord:
    sliced = dict(project)
    sliced["sentences"] = sentences
    sliced["compiled_script"] = " ".join(sentence.strip() for sentence in sentences if sentence.strip())
    return cast(ProjectRecord, sliced)


def _remap_batch_entries(entries: list[VisualPlanEntry], start_idx: int) -> list[VisualPlanEntry]:
    remapped: list[VisualPlanEntry] = []
    for entry in entries:
        next_entry = dict(entry)
        local_idx = int(next_entry.get("sentence_idx", 0))
        next_entry["sentence_idx"] = start_idx + local_idx
        remapped.append(cast(VisualPlanEntry, next_entry))
    return remapped


def _generate_llm_visual_plan(
    project: ProjectRecord,
    *,
    domain: str,
    vocab: dict[str, object],
) -> tuple[list[VisualPlanEntry], str, str]:
    client = OllamaClient(model=SCRIPT_LLM_MODEL)
    client.warm()
    raw_text = ""
    model_name = ""
    try:
        response = client.generate(
            prompt=_planner_prompt(project, domain, vocab),
            system=_planner_system_prompt(domain),
            num_predict=1800,
            temperature=0.25,
        )
        raw_text = response.response
        model_name = response.model
    finally:
        client.unload()

    parsed_entries: object = []
    parsed_source = "llm"
    try:
        parsed_entries = json.loads(_extract_json_payload(raw_text))
    except json.JSONDecodeError:
        client = OllamaClient(model=SCRIPT_LLM_MODEL)
        client.warm()
        try:
            repair = client.generate(
                prompt=(
                    "Convert the following content into a valid JSON array only. "
                    "Keep the same meaning and fields.\n\n"
                    f"{raw_text}"
                ),
                system="Return only valid JSON.",
                num_predict=1800,
                temperature=0.0,
            )
            parsed_entries = json.loads(_extract_json_payload(repair.response))
            parsed_source = "llm_repair"
            if not model_name:
                model_name = repair.model
        except json.JSONDecodeError:
            parsed_entries = []
            parsed_source = "fallback"
        finally:
            client.unload()

    return _normalize_entries(project, parsed_entries, domain=domain, source=parsed_source), model_name, parsed_source


def _generate_batched_visual_plan(
    project: ProjectRecord,
    *,
    domain: str,
    vocab: dict[str, object],
) -> tuple[list[VisualPlanEntry], str, str]:
    if len(project["sentences"]) <= _PLANNER_BATCH_SIZE:
        return _generate_llm_visual_plan(project, domain=domain, vocab=vocab)

    entries: list[VisualPlanEntry] = []
    model_names: list[str] = []
    sources: list[str] = []
    for start_idx in range(0, len(project["sentences"]), _PLANNER_BATCH_SIZE):
        batch_sentences = project["sentences"][start_idx : start_idx + _PLANNER_BATCH_SIZE]
        batch_project = _project_sentence_slice(project, start_idx, batch_sentences)
        batch_entries, model_name, source = _generate_llm_visual_plan(batch_project, domain=domain, vocab=vocab)
        entries.extend(_remap_batch_entries(batch_entries, start_idx))
        if model_name and model_name not in model_names:
            model_names.append(model_name)
        if source not in sources:
            sources.append(source)

    combined_source = "llm_batched" if sources == ["llm"] else "llm_batched_mixed"
    if sources and all(source == "fallback" for source in sources):
        combined_source = "fallback"
    return entries, ", ".join(model_names), combined_source


def build_scene_visual_plan(project: ProjectRecord) -> list[VisualPlanEntry]:
    if not project["sentences"]:
        return []
    if project["body_image_options"].get("disable_llm_visual_planner") is True:
        return _normalize_entries(project, [], domain=_domain_for_project(project), source="fallback")
    cached = _load_cached_plan(project)
    if cached is not None:
        return cached

    domain = _domain_for_project(project)
    vocab = _load_vocab(domain)
    if not _quick_ollama_ready():
        fallback = _normalize_entries(project, [], domain=domain, source="fallback")
        _save_plan(project, domain=domain, model="", source="fallback", entries=fallback)
        return fallback

    normalized, model_name, parsed_source = _generate_batched_visual_plan(project, domain=domain, vocab=vocab)
    _save_plan(project, domain=domain, model=model_name, source=parsed_source, entries=normalized)
    return normalized
