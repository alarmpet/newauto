import json
from dataclasses import dataclass
from typing import Literal, cast

from fastapi import HTTPException
from typing_extensions import NotRequired, TypedDict

from .. import db
from ..config import SCRIPT_LLM_MODEL
from ..types import ProjectRecord
from .llm_ollama import OllamaClient
from .parse_utils import JsonExtractionError, extract_json_from_llm_response
from .script_safety import copy_risk_score, detect_long_quotes
from .source_draft import sanitize_source_draft_script

HpslSection = Literal["hook", "point", "story", "lesson"]


class HpslSource(TypedDict):
    id: str
    url: str
    title: str
    used_facts: list[str]


class HpslSentence(TypedDict):
    index: int
    section: HpslSection
    narration: str
    source_ids: list[str]
    core_keyword: str
    visual_keyword: str
    emotion: str
    estimated_seconds: float
    flow_prompt: NotRequired[str]
    comfyui_prompt: NotRequired[str]
    negative_prompt: NotRequired[str]


class HpslPayload(TypedDict):
    topic: str
    angle: str
    sources: list[HpslSource]
    hook: str
    points: list[str]
    story: str
    lesson: str
    sentences: list[HpslSentence]


@dataclass(frozen=True)
class GeneratedHpslDraft:
    script: str
    payload: HpslPayload
    warnings: list[str]
    model: str
    risk_score: float
    previous_script: str


def _as_string_list(value: object, *, limit: int = 6) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            items.append(item.strip())
        if len(items) >= limit:
            break
    return items


def _section(value: object, fallback: HpslSection) -> HpslSection:
    if value in {"hook", "point", "story", "lesson"}:
        return cast(HpslSection, value)
    return fallback


def _compact_fact_notes(project: ProjectRecord, *, max_chars: int = 2200) -> str:
    lines: list[str] = []
    used_chars = 0
    source_titles = {source["id"]: source["title"] for source in project["source_draft_sources"]}
    for note in project["source_draft_fact_notes"][:14]:
        source_id = note["source_id"]
        title = source_titles.get(source_id, source_id)
        note_text = note["note"].strip()
        if len(note_text) > 180:
            note_text = f"{note_text[:177]}..."
        line = f"- [{source_id}] {title[:80]}: {note_text}"
        if used_chars + len(line) > max_chars:
            break
        lines.append(line)
        used_chars += len(line)
    return "\n".join(lines)


def _source_block(project: ProjectRecord, *, max_sources: int = 3) -> str:
    lines: list[str] = []
    for source in project["source_draft_sources"][:max_sources]:
        lines.append(
            "\n".join(
                [
                    f"- id: {source['id']}",
                    f"  title: {source['title']}",
                    f"  url: {source['final_url'] or source['url']}",
                    f"  domain: {source['domain']}",
                ]
            )
        )
    return "\n".join(lines)


def _target_sentence_count(project: ProjectRecord, target_minutes: int | None) -> int:
    notes = [item for item in project["source_draft_fact_notes"] if item["note"].strip()]
    note_count = len(notes)
    if target_minutes is None:
        return max(1, min(18, note_count))
    if note_count <= 0:
        return max(1, min(18, target_minutes * 6))
    if target_minutes <= 1:
        # Shorts do not need a fixed six-scene structure. Keep the HPSL arc,
        # but let sparse source material stay concise and richer material grow.
        return min(8, note_count) if note_count < 4 else max(4, min(8, note_count))
    return min(note_count, 4) if note_count < 5 else max(5, min(30, target_minutes * 6, note_count))


def _build_prompt(
    project: ProjectRecord,
    *,
    tone: str,
    target_minutes: int | None,
    language: str,
) -> str:
    if not project["source_draft_sources"] or not project["source_draft_fact_notes"]:
        raise HTTPException(400, "Prepare source material and fact notes first.")
    sentence_target = _target_sentence_count(project, target_minutes)
    fact_notes = _compact_fact_notes(project)
    if not fact_notes.strip():
        raise HTTPException(400, "Fact notes are empty.")
    length_rule = (
        f"target_minutes={target_minutes}; sentence_count={sentence_target}"
        if target_minutes is not None
        else (
            "target_minutes=auto; sentence_count=auto_from_fact_notes; "
            f"natural_sentence_count_hint={sentence_target}; do not pad or compress to hit a runtime"
        )
    )
    return f"""Create a compact Korean YouTube script from fact notes.

Rules: use only facts, no copied wording, no unsupported claims, JSON only.
Style: HPSL = Hook, Point, Story, Lesson. In Korean: 훅, 포인트, 스토리, 교훈.
Do not interpret HPSL as "High Productivity Scripting Language".
One sentence = one Flow scene.
Language={language}; tone={tone}; {length_rule}
Create exactly {sentence_target} sentence objects in "sentences". Do not default to six scenes.
The "points" list is only a summary and may have any natural length; it must not control sentence count.

Return this compact JSON object:
{{"topic":"","angle":"","sources":[{{"id":"","url":"","title":"","used_facts":[""]}}],"hook":"","points":[],"story":"","lesson":"","sentences":[{{"index":1,"section":"hook","narration":"","source_ids":[""],"core_keyword":"","visual_keyword":"","emotion":"curiosity","estimated_seconds":4.0}}]}}

[Sources]
{_source_block(project)}

[Fact Notes]
{fact_notes}
"""


def _repair_prompt(raw_response: str) -> str:
    return f"""Repair the following text into valid JSON object only.
Do not add facts. Do not explain. Return only JSON.

[Broken JSON]
{raw_response[:12000]}
"""


def _fallback_payload_from_fact_notes(
    project: ProjectRecord,
    *,
    tone: str,
    target_minutes: int | None,
) -> HpslPayload:
    notes = [item["note"].strip() for item in project["source_draft_fact_notes"] if item["note"].strip()]
    if not notes:
        raise HTTPException(400, "Fact notes are empty.")
    sentence_count = _target_sentence_count(project, target_minutes)
    selected_notes = notes[:sentence_count]
    source_id = project["source_draft_sources"][0]["id"] if project["source_draft_sources"] else ""
    sections: list[HpslSection] = ["hook"]
    sections.extend(["point"] * max(1, len(selected_notes) - 3))
    sections.extend(["story", "lesson"])
    sections = sections[: len(selected_notes)]
    sentences: list[HpslSentence] = []
    for index, note in enumerate(selected_notes, start=1):
        compact = note
        if len(compact) > 120:
            compact = f"{compact[:117]}..."
        section = sections[index - 1] if index - 1 < len(sections) else "point"
        sentences.append(
            {
                "index": index,
                "section": section,
                "narration": compact,
                "source_ids": [source_id] if source_id else [],
                "core_keyword": compact[:80],
                "visual_keyword": compact[:80],
                "emotion": "curiosity" if section == "hook" else "focused",
                "estimated_seconds": 4.0,
            }
        )
    return {
        "topic": project["title"] or "source-based topic",
        "angle": tone,
        "sources": _normalize_sources(project, {}),
        "hook": sentences[0]["narration"],
        "points": [sentence["narration"] for sentence in sentences if sentence["section"] == "point"][:3],
        "story": " ".join(sentence["narration"] for sentence in sentences if sentence["section"] == "story"),
        "lesson": sentences[-1]["narration"],
        "sentences": sentences,
    }


def _parse_with_repair(client: OllamaClient, raw_response: str) -> dict[str, object]:
    try:
        return extract_json_from_llm_response(raw_response)
    except JsonExtractionError:
        repaired = client.generate(
            prompt=_repair_prompt(raw_response),
            system="Return only a valid JSON object.",
            num_predict=1800,
            temperature=0.0,
        )
        try:
            return extract_json_from_llm_response(repaired.response)
        except JsonExtractionError as exc:
            raise HTTPException(502, f"HPSL JSON parsing failed after repair: {exc}") from exc


def _normalize_sources(project: ProjectRecord, payload: dict[str, object]) -> list[HpslSource]:
    source_by_id = {source["id"]: source for source in project["source_draft_sources"]}
    raw_sources = payload.get("sources")
    normalized: list[HpslSource] = []
    if isinstance(raw_sources, list):
        for item in raw_sources:
            if not isinstance(item, dict):
                continue
            raw_id = item.get("id")
            source_id = raw_id if isinstance(raw_id, str) and raw_id in source_by_id else ""
            if not source_id:
                continue
            source = source_by_id[source_id]
            normalized.append(
                {
                    "id": source_id,
                    "url": source["final_url"] or source["url"],
                    "title": source["title"],
                    "used_facts": _as_string_list(item.get("used_facts"), limit=6),
                }
            )
    if normalized:
        return normalized
    return [
        {
            "id": source["id"],
            "url": source["final_url"] or source["url"],
            "title": source["title"],
            "used_facts": [],
        }
        for source in project["source_draft_sources"][:5]
    ]


def _normalize_sentences(payload: dict[str, object]) -> list[HpslSentence]:
    raw_sentences = payload.get("sentences")
    if not isinstance(raw_sentences, list):
        raise HTTPException(502, "HPSL response is missing sentences.")
    normalized: list[HpslSentence] = []
    section_fallbacks: list[HpslSection] = ["hook", "point", "story", "lesson"]
    for index, item in enumerate(raw_sentences, start=1):
        if not isinstance(item, dict):
            continue
        narration = str(item.get("narration") or "").strip()
        if not narration:
            continue
        source_ids = _as_string_list(item.get("source_ids"), limit=5)
        estimated = item.get("estimated_seconds")
        estimated_seconds = float(estimated) if isinstance(estimated, (int, float)) else max(2.0, min(7.5, len(narration) / 12))
        normalized.append(
            {
                "index": index,
                "section": _section(item.get("section"), section_fallbacks[min(len(normalized), 3)]),
                "narration": narration,
                "source_ids": source_ids,
                "core_keyword": str(item.get("core_keyword") or "").strip()[:120],
                "visual_keyword": str(item.get("visual_keyword") or "").strip()[:120],
                "emotion": str(item.get("emotion") or "curiosity").strip()[:80],
                "estimated_seconds": max(1.5, min(12.0, estimated_seconds)),
            }
        )
    if not normalized:
        raise HTTPException(502, "HPSL response did not contain usable narration sentences.")
    return normalized


def _normalize_payload(project: ProjectRecord, payload: dict[str, object]) -> HpslPayload:
    sentences = _normalize_sentences(payload)
    return {
        "topic": str(payload.get("topic") or project["title"] or "Untitled topic").strip(),
        "angle": str(payload.get("angle") or "").strip(),
        "sources": _normalize_sources(project, payload),
        "hook": str(payload.get("hook") or "").strip(),
        "points": _as_string_list(payload.get("points"), limit=6),
        "story": str(payload.get("story") or "").strip(),
        "lesson": str(payload.get("lesson") or "").strip(),
        "sentences": sentences,
    }


def hpsl_script_text(payload: HpslPayload) -> str:
    return sanitize_source_draft_script("\n".join(sentence["narration"] for sentence in payload["sentences"]))


def hpsl_payload_path(pid: str) -> str:
    return str(db.project_dir(pid) / "hpsl_script.json")


def save_hpsl_payload(pid: str, payload: HpslPayload) -> None:
    path = db.project_dir(pid) / "hpsl_script.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_hpsl_payload(project: ProjectRecord) -> HpslPayload | None:
    path = db.project_dir(project["id"]) / "hpsl_script.json"
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    return _normalize_payload(project, cast(dict[str, object], raw))


def generate_hpsl_draft(
    project: ProjectRecord,
    *,
    tone: str,
    target_minutes: int | None,
    language: str = "ko",
) -> GeneratedHpslDraft:
    prompt = _build_prompt(project, tone=tone, target_minutes=target_minutes, language=language)
    source_text = "\n".join(source["excerpt"] for source in project["source_draft_sources"])
    previous_script = project["source_draft_script"]
    fallback_reason = ""
    if target_minutes == 1:
        payload = _fallback_payload_from_fact_notes(project, tone=tone, target_minutes=target_minutes)
        model_name = f"{SCRIPT_LLM_MODEL}:deterministic-hpsl-1min"
        fallback_reason = "1-minute HPSL drafts use deterministic assembly to avoid local model timeout/context failures."
    else:
        payload = _generate_hpsl_payload_with_llm(
            project,
            prompt=prompt,
            tone=tone,
            target_minutes=target_minutes,
        )
        model_name = SCRIPT_LLM_MODEL
        if payload["angle"].startswith("deterministic-fallback:"):
            model_name = f"{SCRIPT_LLM_MODEL}:deterministic-fallback"
            fallback_reason = payload["angle"].replace("deterministic-fallback:", "", 1).strip()
            payload["angle"] = tone
    script = hpsl_script_text(payload)
    if not script:
        raise HTTPException(502, "Generated HPSL script was empty after cleanup.")
    risk_score = copy_risk_score(source_text, script)
    warnings = list(project["source_draft_warnings"])
    if fallback_reason:
        warnings.append(f"HPSL JSON generation fell back to deterministic script assembly: {fallback_reason}")
    if risk_score >= 0.30:
        warnings.append(f"Source wording overlap looks high ({risk_score:.0%}). Review and rewrite the phrasing.")
    for quote in detect_long_quotes(source_text, script):
        warnings.append(f"Possible long quote overlap detected: {quote[:40].strip()}...")
    return GeneratedHpslDraft(
        script=script,
        payload=payload,
        warnings=list(dict.fromkeys(warnings)),
        model=model_name,
        risk_score=risk_score,
        previous_script=previous_script,
    )


def _generate_hpsl_payload_with_llm(
    project: ProjectRecord,
    *,
    prompt: str,
    tone: str,
    target_minutes: int | None,
) -> HpslPayload:
    client = OllamaClient(model=SCRIPT_LLM_MODEL)
    client.warm()
    try:
        try:
            response = client.generate(
                prompt=prompt,
                system="Return compact valid JSON only.",
                num_predict=1400 if target_minutes is None else max(1000, min(1600, target_minutes * 650)),
                temperature=0.25,
            )
            raw_payload = _parse_with_repair(client, response.response)
            return _normalize_payload(project, raw_payload)
        except Exception as exc:
            payload = _fallback_payload_from_fact_notes(project, tone=tone, target_minutes=target_minutes)
            payload["angle"] = f"deterministic-fallback: {str(exc)[:180]}"
            return payload
    finally:
        client.unload()
