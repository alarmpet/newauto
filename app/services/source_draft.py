import re
from dataclasses import dataclass

from fastapi import HTTPException

from ..config import SCRIPT_LLM_MODEL
from ..types import ProjectRecord, SourceRegenerateMode
from .llm_ollama import OllamaClient
from .script_safety import copy_risk_score, detect_long_quotes

SYSTEM_PROMPT = """You are a Korean video script editor.
- Do not copy source article text verbatim.
- Rewrite from fact notes.
- Keep unsupported claims out.
- Return only the finished script body.
"""


@dataclass(frozen=True)
class GeneratedSourceDraft:
    script: str
    warnings: list[str]
    model: str
    risk_score: float
    mode: SourceRegenerateMode
    previous_script: str


_MODE_INSTRUCTIONS: dict[SourceRegenerateMode, str] = {
    "": "- Use a balanced flow with one opening, a few body paragraphs, and one closing.\n",
    "hook": (
        "- Make the first 2-4 sentences grab attention strongly.\n"
        "- Lead with a tension, contrast, or surprising point.\n"
    ),
    "point": (
        "- Organize the key facts into 3-5 concise points.\n"
        "- Keep each paragraph focused on one point.\n"
    ),
    "story": (
        "- Make the script feel like events are unfolding in sequence.\n"
        "- Do not invent emotions or missing scenes that are not supported by the source.\n"
    ),
    "lesson": (
        "- End by drawing a takeaway or meaning from the events.\n"
        "- Avoid preachy over-generalization.\n"
    ),
}

_MODE_TEMPERATURE: dict[SourceRegenerateMode, float] = {
    "": 0.4,
    "hook": 0.55,
    "point": 0.30,
    "story": 0.45,
    "lesson": 0.50,
}

_MODE_RISK_THRESHOLD: dict[SourceRegenerateMode, float] = {
    "": 0.30,
    "hook": 0.30,
    "point": 0.40,
    "story": 0.30,
    "lesson": 0.25,
}

_DRAFT_LABEL_RE = re.compile(r"^\*{0,2}\s*(내레이션|장면|이미지|화면|효과음)\s*[:：]\s*", re.IGNORECASE)
_BULLET_RE = re.compile(r"^\s*[-*•]\s+")
_HEADING_RE = re.compile(r"^\s*#{1,6}\s*")
_LEADING_DIRECTION_RE = re.compile(r"^\s*[\(\[][^)\]]{1,80}[\)\]]\s*")
_ONLY_DIRECTION_RE = re.compile(r"^\s*[\(\[][^)\]]{1,120}[\)\]]\s*$")


def _temperature_for_mode(mode: SourceRegenerateMode) -> float:
    return _MODE_TEMPERATURE.get(mode, 0.4)


def _risk_threshold_for_mode(mode: SourceRegenerateMode) -> float:
    return _MODE_RISK_THRESHOLD.get(mode, 0.30)


def risk_threshold_for_mode(mode: SourceRegenerateMode) -> float:
    return _risk_threshold_for_mode(mode)


def sanitize_source_draft_script(text: str) -> str:
    cleaned_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if cleaned_lines and cleaned_lines[-1] != "":
                cleaned_lines.append("")
            continue
        if _ONLY_DIRECTION_RE.match(line):
            continue
        line = _HEADING_RE.sub("", line)
        line = _BULLET_RE.sub("", line)
        line = _DRAFT_LABEL_RE.sub("", line)
        line = re.sub(r"^\*+\s*", "", line)
        line = re.sub(r"\s*\*+$", "", line)
        while True:
            updated = _LEADING_DIRECTION_RE.sub("", line)
            if updated == line:
                break
            line = updated.strip()
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()


def _build_prompt(
    project: ProjectRecord,
    *,
    tone: str,
    target_minutes: int | None,
    language: str,
    mode: SourceRegenerateMode = "",
    note: str = "",
) -> str:
    source = project["source_draft_sources"][0] if project["source_draft_sources"] else None
    fact_notes = [item["note"] for item in project["source_draft_fact_notes"] if item.get("note")]
    if source is None or not fact_notes:
        raise HTTPException(400, "Prepare source material and fact notes first.")
    joined_notes = "\n".join(f"- {item}" for item in fact_notes[:10])
    mode_block = _MODE_INSTRUCTIONS.get(mode, _MODE_INSTRUCTIONS[""])
    note_block = f"\n[Additional Guidance]\n{note.strip()}\n" if note.strip() else ""
    length_rule = (
        f"- Target length: loosely around {target_minutes} minutes, but natural pacing is more important than exact runtime"
        if target_minutes is not None
        else "- Target length: auto; adapt naturally to the source density and do not pad, compress, or force a runtime"
    )
    return f"""Write a Korean video script draft from the material below.

[Constraints]
- Language: {language}
- Tone: {tone}
{length_rule}
- Do not copy the article wording directly
- Explain clearly without exaggeration
{mode_block}{note_block}

[Source]
Title: {source["title"]}
Domain: {source["domain"]}
Excerpt: {source["excerpt"]}

[Fact Notes]
{joined_notes}
"""


def generate_script_draft(
    project: ProjectRecord,
    *,
    tone: str,
    target_minutes: int | None,
    language: str = "ko",
    mode: SourceRegenerateMode = "",
    note: str = "",
) -> GeneratedSourceDraft:
    prompt = _build_prompt(
        project,
        tone=tone,
        target_minutes=target_minutes,
        language=language,
        mode=mode,
        note=note,
    )
    source_text = "\n".join(source["excerpt"] for source in project["source_draft_sources"])
    previous_script = project["source_draft_script"]
    client = OllamaClient(model=SCRIPT_LLM_MODEL)
    client.warm()
    try:
        response = client.generate(
            prompt=prompt,
            system=SYSTEM_PROMPT,
            num_predict=700 if target_minutes is None else max(500, min(1200, target_minutes * 220)),
            temperature=_temperature_for_mode(mode),
        )
    finally:
        client.unload()
    script = sanitize_source_draft_script(response.response.strip())
    if not script:
        raise HTTPException(502, "Generated script draft was empty after cleanup.")
    risk_score = copy_risk_score(source_text, script)
    warnings = list(project["source_draft_warnings"])
    if risk_score >= _risk_threshold_for_mode(mode):
        warnings.append(
            f"Source wording overlap looks high ({risk_score:.0%}). Review and rewrite the phrasing."
        )
    for quote in detect_long_quotes(source_text, script):
        warnings.append(f"Possible long quote overlap detected: {quote[:40].strip()}...")
    return GeneratedSourceDraft(
        script=script,
        warnings=list(dict.fromkeys(warnings)),
        model=response.model,
        risk_score=risk_score,
        mode=mode,
        previous_script=previous_script,
    )
