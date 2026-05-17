import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, TypedDict, cast

from PIL import Image, ImageDraw, ImageFont

from .. import db
from ..types import (
    BodyImageMapping,
    FinalSceneReview,
    FinalSceneReviewEntry,
    ProjectRecord,
    VisualRelevanceRow,
    VisualRelevanceSummary,
)
from .domain_detection import is_ai_policy_conflict_domain, is_food_trend_domain, is_news_explainer_domain
from .prompt_compiler import GENERIC_FALLBACK_TERMS
from .text_health import any_mojibake, looks_mojibake


class VisualRelevanceIssue(TypedDict):
    code: str
    message: str
    sentence_idx: int | None
    path: str


GENERATED_IMAGE_MIN_CANDIDATE_SCORE = 0.55
GENERATED_IMAGE_FINAL_MIN_CANDIDATE_SCORE = 0.72
FINAL_BLOCKING_VISION_ISSUES = {
    "DENSE_DIAGRAM_CLUTTER",
    "DOMINANT_SUBJECT_TOO_SMALL",
    "ABSTRACT_UI_NO_CLEAR_SUBJECT",
    "TINY_ICON_GRID",
    "GENERIC_DASHBOARD_LAYOUT",
}
SIMPLE_DIAGRAM_COMBO_BLOCKING_VISION_ISSUES = {
    "LOW_EDGE_DETAIL",
    "LOW_ENTROPY",
    "LOW_CONTRAST",
    "EXTREME_EXPOSURE",
}
MANUAL_LIGHT_BLOCKING_VISION_ISSUES = {
    "LOW_RESOLUTION",
    "EXTREME_EXPOSURE",
}
DIAGRAM_SOFT_EXPOSURE_MIN_SCORE = 0.72
ValidationPolicy = Literal["strict_generated", "manual_light", "upload_only", "skip_legacy"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_sentence_for_hash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def sentence_hash(text: str) -> str:
    normalized = normalize_sentence_for_hash(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def mapping_matches_current_sentence(project: ProjectRecord, mapping: BodyImageMapping) -> bool:
    sentence_idx = mapping["sentence_idx"]
    if sentence_idx < 0 or sentence_idx >= len(project["sentences"]):
        return False
    stored_hash = mapping.get("sentence_hash", "")
    if not stored_hash:
        return False
    return stored_hash == sentence_hash(project["sentences"][sentence_idx])


def _prompt_manifest_by_sentence(project: ProjectRecord) -> dict[int, dict[str, object]]:
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
    items: dict[int, dict[str, object]] = {}
    for item in prompts:
        if not isinstance(item, dict):
            continue
        sentence_idx = item.get("sentence_idx")
        if isinstance(sentence_idx, int):
            items[sentence_idx] = item
    return items


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _candidate_reviews(project: ProjectRecord) -> dict[str, dict[str, object]]:
    raw_reviews = project["body_image_options"].get("candidate_reviews")
    if not isinstance(raw_reviews, dict):
        return {}
    reviews: dict[str, dict[str, object]] = {}
    for key, value in raw_reviews.items():
        if isinstance(key, str) and isinstance(value, dict):
            reviews[key] = value
    return reviews


def _strict_final_gate_enabled(project: ProjectRecord, prompt_item: dict[str, object] | None) -> bool:
    visual_brief = prompt_item.get("visual_brief") if prompt_item is not None else None
    if not isinstance(visual_brief, dict):
        return project["visual_source_mode"] == "comfyui_auto"
    domain = str(visual_brief.get("domain") or "").strip().lower()
    rationale = str(visual_brief.get("rationale") or "").strip().lower()
    composition_template = str(visual_brief.get("composition_template") or "").strip()
    strict_domains = {
        "ai_policy_conflict",
        "news_explainer",
        "tech",
    }
    return domain in strict_domains or bool(composition_template) or "style_preset=simple_diagram" in rationale


def _mapping_has_generated_metadata(mapping: BodyImageMapping) -> bool:
    return bool(
        mapping.get("prompt_id")
        or mapping.get("manifest_sentence_hash")
        or "candidate_score" in mapping
        or mapping.get("candidate_score_version")
    )


def _is_simple_diagram_prompt(prompt_item: dict[str, object] | None) -> bool:
    if prompt_item is None:
        return False
    visual_brief = prompt_item.get("visual_brief")
    if isinstance(visual_brief, dict):
        rationale = str(visual_brief.get("rationale") or "").lower()
        composition_template = str(visual_brief.get("composition_template") or "").lower()
        domain = str(visual_brief.get("domain") or "").lower()
        if (
            "style_preset=simple_diagram" in rationale
            or composition_template
            or domain in {"ai_policy_conflict", "news_explainer", "tech"}
        ):
            return True
    positive_prompt = str(prompt_item.get("positive_prompt") or "").lower()
    return "simple flat" in positive_prompt or "explainer diagram" in positive_prompt


def _soften_generated_exposure_failure(
    *,
    prompt_item: dict[str, object] | None,
    candidate_score: object,
    vision_codes: list[object],
) -> bool:
    if not _is_simple_diagram_prompt(prompt_item):
        return False
    if not isinstance(candidate_score, (int, float)) or candidate_score < DIAGRAM_SOFT_EXPOSURE_MIN_SCORE:
        return False
    hard_codes = {code for code in vision_codes if isinstance(code, str)}
    return bool(hard_codes) and hard_codes.issubset({"EXTREME_EXPOSURE", "LOW_ENTROPY", "LOW_EDGE_DETAIL", "LOW_CONTRAST"})


def _blocking_simple_diagram_combo(vision_codes: list[object]) -> list[str]:
    codes = {code for code in vision_codes if isinstance(code, str)}
    if "LOW_EDGE_DETAIL" in codes and ({"LOW_ENTROPY", "LOW_CONTRAST"} & codes):
        return [code for code in ("LOW_EDGE_DETAIL", "LOW_ENTROPY", "LOW_CONTRAST") if code in codes]
    if "EXTREME_EXPOSURE" in codes and "LOW_EDGE_DETAIL" in codes:
        return [code for code in ("EXTREME_EXPOSURE", "LOW_EDGE_DETAIL") if code in codes]
    return []


def _validation_policy(
    project: ProjectRecord,
    mapping: BodyImageMapping | None,
    prompt_item: dict[str, object] | None,
) -> ValidationPolicy:
    if project["visual_source_mode"] == "comfyui_auto":
        return "strict_generated"
    if mapping is not None and _mapping_has_generated_metadata(mapping):
        return "strict_generated"
    if _as_bool(project["body_image_options"].get("manual_art_directed")):
        return "manual_light"
    if _as_bool(project["body_image_options"].get("force_render_with_failed_visuals")):
        return "skip_legacy"
    if _as_bool(project["body_image_options"].get("allow_low_quality_generated_images")):
        return "skip_legacy"
    if prompt_item is not None:
        return "strict_generated"
    return "upload_only"


def validate_generated_image_mappings(project: ProjectRecord) -> list[VisualRelevanceIssue]:
    if not project["sentences"]:
        return []

    mappings_by_idx = {mapping["sentence_idx"]: mapping for mapping in project["body_image_mappings"]}
    media_order = set(project["media_order"])
    manifest_by_idx = _prompt_manifest_by_sentence(project)
    candidate_reviews = _candidate_reviews(project)
    issues: list[VisualRelevanceIssue] = []
    for sentence_idx, sentence in enumerate(project["sentences"]):
        mapping = mappings_by_idx.get(sentence_idx)
        prompt_item = manifest_by_idx.get(sentence_idx)
        policy = _validation_policy(project, mapping, prompt_item)
        strict_final_gate = _strict_final_gate_enabled(project, prompt_item)
        if policy in {"upload_only", "skip_legacy"}:
            continue
        if mapping is None:
            issues.append(
                {
                    "code": "IMAGE_SELECTION_MISSING",
                    "message": f"Sentence {sentence_idx} has no generated image mapping.",
                    "sentence_idx": sentence_idx,
                    "path": "",
                }
            )
            continue
        path = mapping["path"]
        if path not in media_order:
            issues.append(
                {
                    "code": "IMAGE_MAPPING_NOT_IN_MEDIA_ORDER",
                    "message": f"Sentence {sentence_idx} maps to media that is not in media_order: {path}",
                    "sentence_idx": sentence_idx,
                    "path": path,
                }
            )
        stored_hash = mapping.get("sentence_hash", "")
        expected_hash = sentence_hash(sentence)
        if prompt_item is None and policy == "strict_generated":
            issues.append(
                {
                    "code": "IMAGE_PROMPT_MANIFEST_MISSING",
                    "message": f"Sentence {sentence_idx} does not have prompt manifest metadata.",
                    "sentence_idx": sentence_idx,
                    "path": path,
                }
            )
        elif prompt_item is not None:
            positive_prompt = str(prompt_item.get("positive_prompt") or "")
            if looks_mojibake(sentence) or looks_mojibake(positive_prompt):
                issues.append(
                    {
                        "code": "TEXT_HEALTH_FAILED",
                        "message": f"Sentence {sentence_idx} text or prompt contains mojibake; regenerate source and prompts.",
                        "sentence_idx": sentence_idx,
                        "path": path,
                    }
                )
            prompt_hash = prompt_item.get("sentence_hash")
            if not isinstance(prompt_hash, str) or not prompt_hash:
                issues.append(
                    {
                        "code": "IMAGE_PROMPT_MANIFEST_MISSING",
                        "message": f"Sentence {sentence_idx} prompt manifest is missing sentence_hash.",
                        "sentence_idx": sentence_idx,
                        "path": path,
                    }
                )
            elif prompt_hash != expected_hash:
                issues.append(
                    {
                        "code": "IMAGE_SENTENCE_HASH_MISMATCH",
                        "message": f"Sentence {sentence_idx} prompt manifest was generated for different text.",
                        "sentence_idx": sentence_idx,
                        "path": path,
                    }
                )
            visual_brief = prompt_item.get("visual_brief")
            if policy == "strict_generated" and not isinstance(visual_brief, dict):
                issues.append(
                    {
                        "code": "IMAGE_VISUAL_BRIEF_MISSING",
                        "message": f"Sentence {sentence_idx} prompt manifest is missing visual_brief.",
                        "sentence_idx": sentence_idx,
                        "path": path,
                    }
                )
            missing_must_show = prompt_item.get("missing_must_show")
            if isinstance(missing_must_show, list) and missing_must_show:
                if any_mojibake([item for item in missing_must_show if isinstance(item, str)]):
                    issues.append(
                        {
                            "code": "TEXT_HEALTH_FAILED",
                            "message": f"Sentence {sentence_idx} prompt coverage metadata contains mojibake.",
                            "sentence_idx": sentence_idx,
                            "path": path,
                        }
                    )
                blocklist_hits = [
                    item.split(":", 1)[1]
                    for item in missing_must_show
                    if isinstance(item, str) and item.startswith("BLOCKLIST:")
                ]
                if blocklist_hits:
                    issues.append(
                        {
                            "code": "IMAGE_PROMPT_BLOCKLIST",
                            "message": f"Sentence {sentence_idx} prompt contains blocked generic phrases: {', '.join(blocklist_hits)}",
                            "sentence_idx": sentence_idx,
                            "path": path,
                        }
                    )
                if any(isinstance(item, str) and not item.startswith("BLOCKLIST:") for item in missing_must_show):
                    issues.append(
                        {
                            "code": "IMAGE_PROMPT_MUST_SHOW_MISSING",
                            "message": f"Sentence {sentence_idx} prompt is missing required visual targets.",
                            "sentence_idx": sentence_idx,
                            "path": path,
                        }
                    )
            keyword_coverage = prompt_item.get("keyword_coverage")
            if (
                policy == "strict_generated"
                and isinstance(keyword_coverage, dict)
                and keyword_coverage.get("passed") is False
                and strict_final_gate
            ):
                issues.append(
                    {
                        "code": "IMAGE_PROMPT_QUALITY_FAILED",
                        "message": f"Sentence {sentence_idx} prompt quality repair did not converge.",
                        "sentence_idx": sentence_idx,
                        "path": path,
                    }
                )
            positive_prompt = str(prompt_item.get("positive_prompt") or "")
            expected_keywords = _expected_visual_keywords(project, sentence)
            prompt_keyword_hits = _prompt_keyword_hits(positive_prompt, expected_keywords)
            semantic_match_score = len(prompt_keyword_hits) / max(1, len(expected_keywords))
            if (
                policy == "strict_generated"
                and expected_keywords
                and semantic_match_score < 0.34
                and strict_final_gate
            ):
                issues.append(
                    {
                        "code": "IMAGE_SEMANTIC_MATCH_TOO_LOW",
                        "message": (
                            f"Sentence {sentence_idx} prompt semantic match {semantic_match_score:.2f} is too low; "
                            "strict regeneration is required."
                        ),
                        "sentence_idx": sentence_idx,
                        "path": path,
                    }
                )
        selected_reason = str(mapping.get("selected_reason") or "")
        review = candidate_reviews.get(str(sentence_idx), {})
        candidate_score = mapping.get("candidate_score")
        if (
            policy == "strict_generated"
            and isinstance(candidate_score, (int, float))
            and candidate_score < GENERATED_IMAGE_MIN_CANDIDATE_SCORE
            and strict_final_gate
        ):
            issues.append(
                {
                    "code": "IMAGE_CANDIDATE_SCORE_LOW",
                    "message": (
                        f"Sentence {sentence_idx} selected image score {candidate_score:.2f} is below "
                        f"{GENERATED_IMAGE_MIN_CANDIDATE_SCORE:.2f}."
                    ),
                    "sentence_idx": sentence_idx,
                    "path": path,
                }
            )
        if (
            isinstance(candidate_score, (int, float))
            and candidate_score < GENERATED_IMAGE_FINAL_MIN_CANDIDATE_SCORE
            and strict_final_gate
        ):
            issues.append(
                {
                    "code": "FINAL_IMAGE_SCORE_TOO_LOW",
                    "message": (
                        f"Sentence {sentence_idx} selected image final score {candidate_score:.2f} is below "
                        f"{GENERATED_IMAGE_FINAL_MIN_CANDIDATE_SCORE:.2f}; strict retry is required."
                    ),
                    "sentence_idx": sentence_idx,
                    "path": path,
                }
            )
        if "borderline" in selected_reason and strict_final_gate:
            issues.append(
                {
                    "code": "IMAGE_CANDIDATE_BORDERLINE_RETRY_REQUIRED",
                    "message": f"Sentence {sentence_idx} selected image is borderline and needs strict retry.",
                    "sentence_idx": sentence_idx,
                    "path": path,
                }
            )
        if (
            policy == "strict_generated"
            and strict_final_gate
            and ("retry_recommended" in selected_reason or review.get("retry_recommended") is True)
        ):
            retry_reason = str(review.get("retry_reason") or "retry_recommended")
            issues.append(
                {
                    "code": "IMAGE_CANDIDATE_RETRY_RECOMMENDED",
                    "message": f"Sentence {sentence_idx} selected image was marked for retry: {retry_reason}.",
                    "sentence_idx": sentence_idx,
                    "path": path,
                }
            )
        raw_vision_codes = mapping.get("vision_qa_issue_codes")
        vision_codes = raw_vision_codes if isinstance(raw_vision_codes, list) else review.get("vision_qa_issue_codes", [])
        if isinstance(vision_codes, list):
            blocking_codes = [code for code in vision_codes if isinstance(code, str) and code in FINAL_BLOCKING_VISION_ISSUES]
            if (
                not blocking_codes
                and _is_simple_diagram_prompt(prompt_item)
                and (policy == "strict_generated" or strict_final_gate)
            ):
                blocking_codes = _blocking_simple_diagram_combo(vision_codes)
            if blocking_codes and (policy == "strict_generated" or strict_final_gate):
                issues.append(
                    {
                        "code": "FINAL_IMAGE_DIAGRAM_QA_FAILED",
                        "message": f"Sentence {sentence_idx} selected diagram image failed QA: {', '.join(blocking_codes)}.",
                        "sentence_idx": sentence_idx,
                        "path": path,
                    }
                )
            manual_blocking_codes = [
                code for code in vision_codes if isinstance(code, str) and code in MANUAL_LIGHT_BLOCKING_VISION_ISSUES
            ]
            if manual_blocking_codes and _soften_generated_exposure_failure(
                prompt_item=prompt_item,
                candidate_score=candidate_score,
                vision_codes=vision_codes,
            ):
                manual_blocking_codes = []
            strict_generated_hard_fail = bool(manual_blocking_codes) and (
                strict_final_gate or "LOW_RESOLUTION" in manual_blocking_codes
            )
            if policy == "strict_generated" and strict_generated_hard_fail:
                issues.append(
                    {
                        "code": "FINAL_IMAGE_DIAGRAM_QA_FAILED",
                        "message": f"Sentence {sentence_idx} selected generated image failed hard QA: {', '.join(manual_blocking_codes)}.",
                        "sentence_idx": sentence_idx,
                        "path": path,
                    }
                )
            if policy == "manual_light" and manual_blocking_codes:
                issues.append(
                    {
                        "code": "MANUAL_LIGHT_IMAGE_QA_FAILED",
                        "message": f"Sentence {sentence_idx} manual image failed hard QA: {', '.join(manual_blocking_codes)}.",
                        "sentence_idx": sentence_idx,
                        "path": path,
                    }
                )
        if not stored_hash:
            issues.append(
                {
                    "code": "IMAGE_SENTENCE_HASH_MISSING",
                    "message": f"Sentence {sentence_idx} image mapping has no sentence_hash.",
                    "sentence_idx": sentence_idx,
                    "path": path,
                }
            )
        elif stored_hash != expected_hash:
            issues.append(
                {
                    "code": "IMAGE_SENTENCE_HASH_MISMATCH",
                    "message": f"Sentence {sentence_idx} image mapping was generated for different text.",
                    "sentence_idx": sentence_idx,
                    "path": path,
                }
            )
        manifest_sentence_hash = mapping.get("manifest_sentence_hash", "")
        if manifest_sentence_hash and manifest_sentence_hash != expected_hash:
            issues.append(
                {
                    "code": "IMAGE_SENTENCE_HASH_MISMATCH",
                    "message": f"Sentence {sentence_idx} queued image job was generated for different text.",
                    "sentence_idx": sentence_idx,
                    "path": path,
                }
            )
    return issues


def build_visual_relevance_rows(project: ProjectRecord) -> list[VisualRelevanceRow]:
    if not project["sentences"]:
        return []
    issues_by_idx: dict[int, list[VisualRelevanceIssue]] = {}
    for issue in validate_generated_image_mappings(project):
        sentence_idx = issue["sentence_idx"]
        if sentence_idx is None:
            continue
        issues_by_idx.setdefault(sentence_idx, []).append(issue)
    mappings_by_idx = {mapping["sentence_idx"]: mapping for mapping in project["body_image_mappings"]}
    rows: list[VisualRelevanceRow] = []
    for sentence_idx, sentence in enumerate(project["sentences"]):
        mapping = mappings_by_idx.get(sentence_idx)
        issue_list = issues_by_idx.get(sentence_idx, [])
        if mapping is None:
            rows.append(
                {
                    "sentence_idx": sentence_idx,
                    "sentence_text": sentence,
                    "status": "missing",
                    "path": "",
                    "reason": "아직 이 문장에 연결된 생성 이미지가 없습니다.",
                    "issue_codes": ["IMAGE_SELECTION_MISSING"],
                }
            )
            continue
        if issue_list:
            rows.append(
                {
                    "sentence_idx": sentence_idx,
                    "sentence_text": sentence,
                    "status": "stale",
                    "path": mapping["path"],
                    "reason": issue_list[0]["message"],
                    "issue_codes": [item["code"] for item in issue_list],
                }
            )
            continue
        rows.append(
            {
                "sentence_idx": sentence_idx,
                "sentence_text": sentence,
                "status": "pass",
                "path": mapping["path"],
                "reason": "현재 문장과 이미지 매핑이 일치합니다.",
                "issue_codes": [],
            }
        )
    return rows


def summarize_visual_relevance(rows: list[VisualRelevanceRow]) -> VisualRelevanceSummary:
    summary: VisualRelevanceSummary = {
        "total": len(rows),
        "pass_count": 0,
        "stale_count": 0,
        "missing_count": 0,
    }
    for row in rows:
        if row["status"] == "pass":
            summary["pass_count"] += 1
        elif row["status"] == "stale":
            summary["stale_count"] += 1
        else:
            summary["missing_count"] += 1
    return summary


def attach_visual_relevance(project: ProjectRecord) -> ProjectRecord:
    rows = build_visual_relevance_rows(project)
    enriched = dict(project)
    enriched["visual_relevance_rows"] = rows
    enriched["visual_relevance_summary"] = summarize_visual_relevance(rows)
    return cast(ProjectRecord, enriched)


def _expected_visual_keywords(project: ProjectRecord, sentence: str) -> list[str]:
    lowered = sentence.lower()
    keywords: list[str] = []
    if is_ai_policy_conflict_domain(project, sentence):
        if any(needle in lowered for needle in ("aircraft", "target", "\ud56d\uacf5\uae30", "\ubaa9\ud45c\ubb3c")):
            return ["aircraft icon", "target reticle"]
        if any(needle in lowered for needle in ("decision authority", "control", "\uacb0\uc815\uad8c", "\ub3c5\uc790", "\uc6b4\uc601 \ubc29\uc2dd")):
            return ["AI company cube", "control lock", "decision authority"]
        policy_rules: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
            (("white house", "\ubc31\uc545\uad00", "\uc81c\ub3d9", "restriction", "blocked", "spread", "\ud655\uc0b0"), ("White House", "stop button", "access barrier", "AI model nodes")),
            (("senate", "hearing", "defense", "criticism", "\uc0c1\uc6d0", "\uccad\ubb38", "\uad6d\ubc29", "\ube44\ud310"), ("senate hearing", "defense official", "warning speech bubble")),
            (("government", "federal", "intervention", "oversight", "regulation", "\uc815\ubd80", "\uc5f0\ubc29", "\uac1c\uc785", "\uaddc\uc81c", "\uc815\ucc45"), ("government shield", "policy document", "AI model under review")),
            (("anthropic", "\uc564\uc2a4\ub85c\ud53d", "company", "\uae30\uc5c5", "conflict", "\uac08\ub4f1"), ("AI company building", "government building", "warning divider")),
            (("security", "\uc548\ubcf4", "risk", "\uc704\ud5d8", "innovation", "\ud601\uc2e0"), ("security shield", "innovation lightbulb", "balance scale")),
        )
        for needles, terms in policy_rules:
            if any(needle in lowered for needle in needles):
                keywords.extend(terms)
        if not keywords:
            keywords.extend(("government shield", "AI company cube", "warning divider"))
    if is_news_explainer_domain(project, sentence):
        news_rules: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
            (("comment", "comments", "\ub313\uae00"), ("news comment panel", "comment bubbles")),
            (("alert", "notification", "email", "\uc54c\ub9bc", "\uba54\uc77c"), ("alert arrow", "newsroom receiver")),
            (("spike", "anomaly", "detect", "\uae09\uc99d", "\uc774\uc0c1", "\uac10\uc9c0"), ("reaction counters", "warning detector")),
            (("election", "public opinion", "\uc120\uac70", "\uc5ec\ub860"), ("public opinion scale", "election ballot")),
        )
        for needles, terms in news_rules:
            if any(needle in lowered for needle in needles):
                keywords.extend(terms)
    if is_food_trend_domain(project, sentence):
        food_rules: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
            (("우베", "ube", "보라", "자색", "참마"), ("ube", "purple yam", "purple dessert")),
            (("말차", "matcha"), ("matcha", "green dessert", "ube")),
            (("소셜", "sns", "social"), ("smartphone feed", "purple dessert photos", "share icons")),
            (("카페", "베이커리", "cafe", "bakery"), ("bakery display case", "ube cake", "ube latte")),
            (("편의점", "대형마트", "마트", "supermarket", "convenience"), ("convenience store shelf", "supermarket display", "purple packaged drinks")),
            (("수출", "필리핀", "해외", "export", "philippines"), ("shipping boxes", "philippines", "global retail shelf")),
            (("식품", "트렌드", "소비자", "업계"), ("food store display", "purple products", "new product shelf")),
        )
        for needles, terms in food_rules:
            if any(needle in lowered for needle in needles):
                keywords.extend(terms)
    if not keywords:
        words = re.findall(r"[A-Za-z]{3,}|[가-힣]{2,}", sentence)
        keywords.extend(words[:4])
    return list(dict.fromkeys(item for item in keywords if item.strip()))


_KEYWORD_TOKEN_STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "with",
    "without",
    "of",
    "for",
    "to",
    "in",
    "on",
    "at",
    "new",
    "clear",
    "large",
    "small",
}


def _keyword_tokens(value: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z]{2,}|[가-힣]{2,}", value.lower())
    return [token for token in tokens if token not in _KEYWORD_TOKEN_STOPWORDS]


def _keyword_present(prompt: str, keyword: str) -> bool:
    prompt_lower = prompt.lower()
    if keyword.lower() in prompt_lower:
        return True
    tokens = _keyword_tokens(keyword)
    if not tokens:
        return False
    matched = sum(1 for token in tokens if token in prompt_lower)
    if len(tokens) == 1:
        return matched == 1
    if len(tokens) == 2:
        return matched >= 1
    return matched >= 2


def _prompt_keyword_hits(prompt: str, expected_keywords: list[str]) -> list[str]:
    return [item for item in expected_keywords if _keyword_present(prompt, item)]


def _generic_fallback_hits(*values: str) -> list[str]:
    lowered = " ".join(values).lower()
    return [term for term in GENERIC_FALLBACK_TERMS if term in lowered]


def build_visual_mismatch_report(project: ProjectRecord) -> dict[str, object]:
    manifest_by_idx = _prompt_manifest_by_sentence(project)
    mappings_by_idx = {mapping["sentence_idx"]: mapping for mapping in project["body_image_mappings"]}
    reviews = _candidate_reviews(project)
    issues_by_idx: dict[int, list[VisualRelevanceIssue]] = {}
    for issue in validate_generated_image_mappings(project):
        sentence_idx = issue["sentence_idx"]
        if sentence_idx is None:
            continue
        issues_by_idx.setdefault(sentence_idx, []).append(issue)

    rows: list[dict[str, object]] = []
    fallback_count = 0
    retry_selected_count = 0
    below_threshold_count = 0
    below_final_threshold_count = 0
    quality_failed_count = 0
    for sentence_idx, sentence in enumerate(project["sentences"]):
        prompt_item = manifest_by_idx.get(sentence_idx, {})
        mapping = mappings_by_idx.get(sentence_idx)
        validation_policy = _validation_policy(project, mapping, prompt_item if prompt_item else None)
        review = reviews.get(str(sentence_idx), {})
        visual_brief = prompt_item.get("visual_brief")
        visual_plan = prompt_item.get("visual_plan")
        source = ""
        if isinstance(visual_plan, dict):
            source = str(visual_plan.get("source") or "")
        if source == "fallback":
            fallback_count += 1
        candidate_score = mapping.get("candidate_score") if mapping is not None else None
        if isinstance(candidate_score, (int, float)) and candidate_score < GENERATED_IMAGE_MIN_CANDIDATE_SCORE:
            below_threshold_count += 1
        selected_reason = str(mapping.get("selected_reason") or "") if mapping is not None else ""
        if "retry_recommended" in selected_reason or review.get("retry_recommended") is True:
            retry_selected_count += 1
        issue_codes = [issue["code"] for issue in issues_by_idx.get(sentence_idx, [])]
        if "FINAL_IMAGE_SCORE_TOO_LOW" in issue_codes:
            below_final_threshold_count += 1
        if "IMAGE_PROMPT_QUALITY_FAILED" in issue_codes:
            quality_failed_count += 1
        must_show: list[str] = []
        core_meaning = ""
        if isinstance(visual_brief, dict):
            raw_must_show = visual_brief.get("must_show")
            if isinstance(raw_must_show, list):
                must_show = [item for item in raw_must_show if isinstance(item, str)]
            core_meaning = str(visual_brief.get("core_meaning") or visual_brief.get("emotion") or "")
        positive_prompt = str(prompt_item.get("positive_prompt") or "")
        expected_keywords = _expected_visual_keywords(project, sentence)
        prompt_keyword_hits = _prompt_keyword_hits(positive_prompt, expected_keywords)
        missing_expected_keywords = [
            item for item in expected_keywords if item not in prompt_keyword_hits
        ]
        semantic_match_score = len(prompt_keyword_hits) / max(1, len(expected_keywords))
        generic_fallback_hits = _generic_fallback_hits(positive_prompt, " ".join(must_show))
        diagnosis = "pass"
        if issue_codes:
            diagnosis = ", ".join(issue_codes)
        elif source == "fallback":
            diagnosis = "fallback visual plan used"
        decision = "pass"
        if issue_codes or generic_fallback_hits or (
            is_food_trend_domain(project, sentence) and expected_keywords and not prompt_keyword_hits
        ) or (
            _strict_final_gate_enabled(project, prompt_item if prompt_item else None)
            and expected_keywords
            and semantic_match_score < 0.34
        ):
            decision = "block_and_retry"
        elif missing_expected_keywords:
            decision = "warn"
        rows.append(
            {
                "sentence_idx": sentence_idx,
                "sentence": sentence,
                "sentence_source": "project_record",
                "core_meaning": core_meaning,
                "must_show": must_show,
                "positive_prompt": positive_prompt,
                "expected_keywords": expected_keywords,
                "prompt_keyword_hits": prompt_keyword_hits,
                "missing_expected_keywords": missing_expected_keywords,
                "generic_fallback_hits": generic_fallback_hits,
                "semantic_match_score": round(semantic_match_score, 3),
                "selected_image": mapping["path"] if mapping is not None else "",
                "candidate_score": candidate_score,
                "selected_reason": selected_reason,
                "strict_retry_attempted": review.get("strict_retry_attempted") is True,
                "vision_qa_issue_codes": review.get("vision_qa_issue_codes") if isinstance(review.get("vision_qa_issue_codes"), list) else [],
                "visual_plan_source": source,
                "validation_policy": validation_policy,
                "issue_codes": issue_codes,
                "diagnosis": diagnosis,
                "decision": decision,
            }
        )
    return {
        "project_id": project["id"],
        "total_sentences": len(project["sentences"]),
        "fallback_scene_plans": fallback_count,
        "retry_recommended_selected_images": retry_selected_count,
        "below_threshold_selected_images": below_threshold_count,
        "below_final_threshold_selected_images": below_final_threshold_count,
        "quality_failed_images": quality_failed_count,
        "rows": rows,
    }


def write_visual_mismatch_report(project: ProjectRecord) -> tuple[Path, Path]:
    report = build_visual_mismatch_report(project)
    project_dir = db.project_dir(project["id"])
    json_path = project_dir / "visual_mismatch_report.json"
    md_path = project_dir / "visual_mismatch_report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        f"# Visual Mismatch Report: {project['id']}",
        "",
        f"- total_sentences: {report['total_sentences']}",
        f"- fallback_scene_plans: {report['fallback_scene_plans']}",
        f"- retry_recommended_selected_images: {report['retry_recommended_selected_images']}",
        f"- below_threshold_selected_images: {report['below_threshold_selected_images']}",
        f"- below_final_threshold_selected_images: {report['below_final_threshold_selected_images']}",
        f"- quality_failed_images: {report['quality_failed_images']}",
        "",
    ]
    rows = report.get("rows")
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            lines.extend(
                [
                    f"## Sentence {row.get('sentence_idx', '')}",
                    "",
                    f"- sentence: {row.get('sentence', '')}",
                    f"- sentence_source: {row.get('sentence_source', '')}",
                    f"- selected_image: {row.get('selected_image', '')}",
                    f"- candidate_score: {row.get('candidate_score', '')}",
                    f"- selected_reason: {row.get('selected_reason', '')}",
                    f"- strict_retry_attempted: {row.get('strict_retry_attempted', '')}",
                    f"- visual_plan_source: {row.get('visual_plan_source', '')}",
                    f"- validation_policy: {row.get('validation_policy', '')}",
                    f"- vision_qa_issue_codes: {', '.join(item for item in row.get('vision_qa_issue_codes', []) if isinstance(item, str)) if isinstance(row.get('vision_qa_issue_codes'), list) else ''}",
                    f"- must_show: {', '.join(item for item in row.get('must_show', []) if isinstance(item, str)) if isinstance(row.get('must_show'), list) else ''}",
                    f"- expected_keywords: {', '.join(item for item in row.get('expected_keywords', []) if isinstance(item, str)) if isinstance(row.get('expected_keywords'), list) else ''}",
                    f"- prompt_keyword_hits: {', '.join(item for item in row.get('prompt_keyword_hits', []) if isinstance(item, str)) if isinstance(row.get('prompt_keyword_hits'), list) else ''}",
                    f"- missing_expected_keywords: {', '.join(item for item in row.get('missing_expected_keywords', []) if isinstance(item, str)) if isinstance(row.get('missing_expected_keywords'), list) else ''}",
                    f"- generic_fallback_hits: {', '.join(item for item in row.get('generic_fallback_hits', []) if isinstance(row.get('generic_fallback_hits'), list) and isinstance(item, str))}",
                    f"- semantic_match_score: {row.get('semantic_match_score', '')}",
                    f"- issue_codes: {', '.join(item for item in row.get('issue_codes', []) if isinstance(item, str)) if isinstance(row.get('issue_codes'), list) else ''}",
                    f"- diagnosis: {row.get('diagnosis', '')}",
                    f"- decision: {row.get('decision', '')}",
                    "",
                ]
            )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def build_final_scene_review(project: ProjectRecord) -> FinalSceneReview:
    manifest_by_idx = _prompt_manifest_by_sentence(project)
    mappings_by_idx = {mapping["sentence_idx"]: mapping for mapping in project["body_image_mappings"]}
    reviews = _candidate_reviews(project)
    entries: list[FinalSceneReviewEntry] = []
    fallback_scene_plan_count = 0
    retry_recommended_count = 0
    for sentence_idx, sentence in enumerate(project["sentences"]):
        prompt_item = manifest_by_idx.get(sentence_idx, {})
        visual_plan = prompt_item.get("visual_plan")
        visual_brief = prompt_item.get("visual_brief")
        mapping = mappings_by_idx.get(sentence_idx)
        review = reviews.get(str(sentence_idx), {})
        visual_plan_source = ""
        visual_mode = ""
        scene_anchor = ""
        semantic_anchor_type = ""
        semantic_anchor_tokens: list[str] = []
        if isinstance(visual_plan, dict):
            visual_plan_source = str(visual_plan.get("source") or "")
            visual_mode = str(visual_plan.get("visual_mode") or "")
            scene_anchor = str(visual_plan.get("scene_anchor") or "")
            semantic_anchor_type = str(visual_plan.get("semantic_anchor_type") or "")
            raw_tokens = visual_plan.get("semantic_anchor_tokens")
            if isinstance(raw_tokens, list):
                semantic_anchor_tokens = [item for item in raw_tokens if isinstance(item, str)]
        if visual_plan_source == "fallback":
            fallback_scene_plan_count += 1
        retry_recommended = review.get("retry_recommended") is True
        if retry_recommended:
            retry_recommended_count += 1
        composition_template = ""
        hero_subject = ""
        if isinstance(visual_brief, dict):
            composition_template = str(visual_brief.get("composition_template") or "")
            hero_subject = str(
                visual_brief.get("hero_subject")
                or visual_brief.get("main_subject")
                or ""
            )
        candidate_score = 0.0
        candidate_score_version = ""
        selected_reason = ""
        selected_image = ""
        if mapping is not None:
            selected_image = mapping["path"]
            selected_reason = str(mapping.get("selected_reason") or "")
            raw_score = mapping.get("candidate_score")
            if isinstance(raw_score, (int, float)):
                candidate_score = float(raw_score)
            candidate_score_version = str(mapping.get("candidate_score_version") or "")
        selection_reason = str(review.get("selection_reason") or selected_reason)
        raw_issue_codes = review.get("vision_qa_issue_codes")
        vision_qa_issue_codes = [item for item in raw_issue_codes if isinstance(item, str)] if isinstance(raw_issue_codes, list) else []
        entries.append(
            {
                "sentence_idx": sentence_idx,
                "sentence": sentence,
                "selected_image": selected_image,
                "selected_reason": selected_reason,
                "candidate_score": candidate_score,
                "candidate_score_version": candidate_score_version,
                "selection_reason": selection_reason,
                "repair_attempted": review.get("repair_attempted") is True,
                "repair_reason": str(review.get("repair_reason") or ""),
                "retry_recommended": retry_recommended,
                "retry_reason": str(review.get("retry_reason") or ""),
                "fallback_downgrade_applied": review.get("fallback_downgrade_applied") is True,
                "fallback_downgrade_reason": str(review.get("fallback_downgrade_reason") or ""),
                "operator_intervention_required": review.get("operator_intervention_required") is True,
                "operator_intervention_reason": str(review.get("operator_intervention_reason") or ""),
                "visual_plan_source": visual_plan_source,
                "visual_mode": visual_mode,
                "scene_anchor": scene_anchor,
                "semantic_anchor_type": semantic_anchor_type,
                "semantic_anchor_tokens": semantic_anchor_tokens,
                "composition_template": composition_template,
                "hero_subject": hero_subject,
                "vision_qa_issue_codes": vision_qa_issue_codes,
            }
        )
    return {
        "project_id": project["id"],
        "title": project["title"],
        "created_at": _now_iso(),
        "total_sentences": len(project["sentences"]),
        "fallback_scene_plan_count": fallback_scene_plan_count,
        "retry_recommended_count": retry_recommended_count,
        "entries": entries,
    }


def write_final_scene_review(project: ProjectRecord) -> Path:
    review = build_final_scene_review(project)
    output_path = db.project_dir(project["id"]) / "final_scene_review.json"
    output_path.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def load_final_scene_review(pid: str) -> FinalSceneReview | None:
    output_path = db.project_dir(pid) / "final_scene_review.json"
    if not output_path.exists():
        return None
    try:
        payload = json.loads(output_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return cast(FinalSceneReview, payload)


def _contact_sheet_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for font_name in ("malgun.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(font_name, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap_text(text: str, *, width: int) -> list[str]:
    compact = re.sub(r"\s+", " ", text).strip()
    if not compact:
        return [""]
    lines: list[str] = []
    current = ""
    for word in compact.split(" "):
        candidate = f"{current} {word}".strip()
        if len(candidate) <= width:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = word
    if current:
        lines.append(current)
    return lines[:4]


def write_visual_contact_sheet(project: ProjectRecord) -> Path:
    report = build_visual_mismatch_report(project)
    rows_raw = report.get("rows")
    rows = [row for row in rows_raw if isinstance(row, dict)] if isinstance(rows_raw, list) else []
    project_dir = db.project_dir(project["id"])
    output_path = project_dir / "diagnostic_contact_sheet.jpg"
    if not rows:
        image = Image.new("RGB", (960, 240), "white")
        draw = ImageDraw.Draw(image)
        draw.text((24, 24), f"No visual rows for project {project['id']}", fill="black", font=_contact_sheet_font(24))
        image.save(output_path, quality=92)
        return output_path

    columns = 2
    cell_w = 720
    cell_h = 430
    padding = 18
    thumb_w = 320
    thumb_h = 180
    header_h = 58
    sheet_w = columns * cell_w
    sheet_h = header_h + ((len(rows) + columns - 1) // columns) * cell_h
    sheet = Image.new("RGB", (sheet_w, sheet_h), (246, 246, 242))
    draw = ImageDraw.Draw(sheet)
    title_font = _contact_sheet_font(24)
    body_font = _contact_sheet_font(18)
    small_font = _contact_sheet_font(15)
    draw.text((padding, 16), f"Diagnostic Contact Sheet: {project['id']}", fill=(20, 20, 20), font=title_font)

    for index, row in enumerate(rows):
        col = index % columns
        line = index // columns
        x = col * cell_w
        y = header_h + line * cell_h
        draw.rectangle([x + 8, y + 8, x + cell_w - 8, y + cell_h - 8], fill=(255, 255, 255), outline=(205, 205, 205))
        media_name = str(row.get("selected_image") or "")
        media_path = project_dir / "media" / media_name
        thumb_box = (x + padding, y + padding, x + padding + thumb_w, y + padding + thumb_h)
        if media_path.exists():
            try:
                with Image.open(media_path) as opened:
                    thumb = opened.convert("RGB")
                    thumb.thumbnail((thumb_w, thumb_h))
                    thumb_bg = Image.new("RGB", (thumb_w, thumb_h), (232, 232, 232))
                    tx = (thumb_w - thumb.width) // 2
                    ty = (thumb_h - thumb.height) // 2
                    thumb_bg.paste(thumb, (tx, ty))
                    sheet.paste(thumb_bg, (thumb_box[0], thumb_box[1]))
            except OSError:
                draw.rectangle(thumb_box, fill=(230, 230, 230), outline=(160, 160, 160))
                draw.text((thumb_box[0] + 10, thumb_box[1] + 10), "image open failed", fill=(120, 0, 0), font=small_font)
        else:
            draw.rectangle(thumb_box, fill=(230, 230, 230), outline=(160, 160, 160))
            draw.text((thumb_box[0] + 10, thumb_box[1] + 10), "missing image", fill=(120, 0, 0), font=small_font)

        text_x = x + padding + thumb_w + 18
        text_y = y + padding
        sentence = str(row.get("sentence") or "")[:140]
        score = row.get("candidate_score")
        score_text = f"{float(score):.3f}" if isinstance(score, (int, float)) else ""
        issue_codes = row.get("issue_codes")
        vision_codes = row.get("vision_qa_issue_codes")
        issue_text = ", ".join(item for item in issue_codes if isinstance(item, str)) if isinstance(issue_codes, list) else ""
        vision_text = ", ".join(item for item in vision_codes if isinstance(item, str)) if isinstance(vision_codes, list) else ""
        lines = [
            f"Scene {row.get('sentence_idx', '')}",
            f"score: {score_text}  policy: {row.get('validation_policy', '')}",
            f"reason: {row.get('selected_reason', '')}",
            f"issues: {issue_text or '-'}",
            f"vision: {vision_text or '-'}",
        ]
        for text in lines:
            draw.text((text_x, text_y), text[:52], fill=(25, 25, 25), font=small_font)
            text_y += 22
        text_y += 6
        for sentence_line in _wrap_text(sentence, width=48):
            draw.text((text_x, text_y), sentence_line, fill=(45, 45, 45), font=body_font)
            text_y += 25
        must_show = row.get("must_show")
        must_show_text = ", ".join(item for item in must_show if isinstance(item, str)) if isinstance(must_show, list) else ""
        draw.text((x + padding, y + padding + thumb_h + 18), f"must_show: {must_show_text[:92]}", fill=(40, 40, 40), font=small_font)
        prompt = str(row.get("positive_prompt") or "")
        for prompt_line in _wrap_text(f"prompt: {prompt[:220]}", width=92):
            draw.text((x + padding, y + padding + thumb_h + 44), prompt_line, fill=(80, 80, 80), font=small_font)
            y += 20

    sheet.save(output_path, quality=92)
    return output_path


def format_visual_relevance_issues(issues: list[VisualRelevanceIssue]) -> str:
    if not issues:
        return ""
    lines = ["Generated images do not match the current script:"]
    for issue in issues[:8]:
        location = f"sentence {issue['sentence_idx']}" if issue["sentence_idx"] is not None else "project"
        path = f" ({issue['path']})" if issue["path"] else ""
        lines.append(f"- {issue['code']} at {location}{path}: {issue['message']}")
    if len(issues) > 8:
        lines.append(f"- ...and {len(issues) - 8} more issue(s).")
    return "\n".join(lines)
