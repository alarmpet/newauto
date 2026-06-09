from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import HTTPException

from app import db
from app.services.source_fetch import analyze_source_url
from app.services.source_research import collect_sources_from_keyword
from app.services.text_health import looks_mojibake
from app.types import SourceDraftFactNote, SourceDraftSource


def _hangul_count(text: str) -> int:
    return sum(1 for char in text if "\uac00" <= char <= "\ud7a3")


def _mojibake_marker_count(text: str) -> int:
    markers = ("\ufffd", "\u00c3", "\u00e2", "\u00ec", "\u00ed", "\u00eb", "\u00ea", "\u0080")
    return sum(text.count(marker) for marker in markers)


def _repair_mojibake_text(text: str) -> str:
    if not text or not looks_mojibake(text):
        return text
    candidates: list[str] = []
    for encoding in ("latin-1", "cp1252"):
        try:
            candidates.append(text.encode(encoding).decode("utf-8"))
        except UnicodeError:
            continue
    if not candidates:
        return text
    repaired = min(
        candidates,
        key=lambda candidate: (_mojibake_marker_count(candidate), -_hangul_count(candidate), len(candidate)),
    )
    if _hangul_count(repaired) > _hangul_count(text) or _mojibake_marker_count(repaired) < _mojibake_marker_count(text):
        return repaired
    return text


def _repair_source(source: SourceDraftSource) -> SourceDraftSource:
    repaired = dict(source)
    for key in ("title", "author", "excerpt"):
        value = repaired.get(key)
        if isinstance(value, str):
            repaired[key] = _repair_mojibake_text(value)
    return SourceDraftSource(
        id=str(repaired["id"]),
        url=str(repaired["url"]),
        final_url=str(repaired["final_url"]),
        title=str(repaired["title"]),
        domain=str(repaired["domain"]),
        author=str(repaired["author"]),
        published_at=str(repaired["published_at"]),
        language=str(repaired["language"]),
        excerpt=str(repaired["excerpt"]),
        fetched_at=str(repaired["fetched_at"]),
        word_count=int(repaired["word_count"]),
    )


def _repair_fact_note(note: SourceDraftFactNote) -> SourceDraftFactNote:
    return SourceDraftFactNote(
        source_id=note["source_id"],
        note=_repair_mojibake_text(note["note"]),
    )


def _error_text(exc: BaseException) -> str:
    if isinstance(exc, HTTPException):
        return str(exc.detail)
    return str(exc)


def _set_running(pid: str, mode: str, query: str) -> None:
    db.update_project(
        pid,
        source_draft_state="running",
        source_draft_progress=5,
        source_draft_error="",
        source_draft_input_mode=mode,
        source_draft_query=query.strip(),
        source_draft_sources=[],
        source_draft_fact_notes=[],
        source_draft_script="",
        source_draft_previous_script="",
        source_draft_warnings=[],
        source_draft_model="",
        source_draft_risk_score=0.0,
        source_draft_phase="collecting sources",
        source_draft_last_log="Source collection started by MCP background job.",
    )


def _set_error(pid: str, mode: str, query: str, exc: BaseException) -> None:
    db.update_project(
        pid,
        source_draft_state="error",
        source_draft_progress=0,
        source_draft_error=_error_text(exc),
        source_draft_input_mode=mode,
        source_draft_query=query.strip(),
        source_draft_sources=[],
        source_draft_fact_notes=[],
        source_draft_script="",
        source_draft_previous_script="",
        source_draft_warnings=[],
        source_draft_model="",
        source_draft_risk_score=0.0,
        source_draft_phase="",
        source_draft_last_log="Source collection failed in MCP background job.",
    )


def _set_done(
    pid: str,
    mode: str,
    query: str,
    sources: list[SourceDraftSource],
    fact_notes: list[SourceDraftFactNote],
    warnings: list[str],
) -> None:
    db.update_project(
        pid,
        source_draft_state="done",
        source_draft_progress=100,
        source_draft_error="",
        source_draft_input_mode=mode,
        source_draft_query=query.strip(),
        source_draft_sources=sources,
        source_draft_fact_notes=fact_notes,
        source_draft_script="",
        source_draft_previous_script="",
        source_draft_warnings=warnings,
        source_draft_model="",
        source_draft_risk_score=0.0,
        source_draft_phase="",
        source_draft_last_log="Source collection completed by MCP background job.",
    )


def _collect_url(pid: str, url: str) -> None:
    _set_running(pid, "url", url)
    try:
        extracted = analyze_source_url(url)
    except Exception as exc:
        _set_error(pid, "url", url, exc)
        raise
    _set_done(
        pid,
        "url",
        url,
        [_repair_source(extracted.source)],
        [_repair_fact_note(note) for note in extracted.fact_notes],
        extracted.warnings,
    )


def _collect_keyword(pid: str, keyword: str) -> None:
    _set_running(pid, "keyword", keyword)
    try:
        search_results, usage = collect_sources_from_keyword(keyword)
        sources: list[SourceDraftSource] = []
        fact_notes: list[SourceDraftFactNote] = []
        skipped = 0
        for result in search_results:
            try:
                extracted = analyze_source_url(result.url)
            except Exception:
                skipped += 1
                continue
            sources.append(_repair_source(extracted.source))
            fact_notes.extend(_repair_fact_note(note) for note in extracted.fact_notes)
            if len(sources) >= 5:
                break
        if not sources:
            raise RuntimeError("No analyzable source body was found from keyword results.")
        warnings = [
            f"Search usage: {usage.get('used', '?')}/{usage.get('limit', '?')}, remaining {usage.get('remaining', '?')}",
        ]
        cache_value = usage.get("cache")
        if cache_value == "hit":
            warnings.append("Search results came from cache.")
        brave_error = usage.get("brave_error")
        if isinstance(brave_error, str) and brave_error:
            warnings.append(f"Brave fallback reason: {brave_error[:300]}")
        if skipped:
            warnings.append(f"{skipped} search result(s) were skipped because article extraction failed.")
    except Exception as exc:
        _set_error(pid, "keyword", keyword, exc)
        raise
    _set_done(pid, "keyword", keyword, sources, fact_notes, warnings)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--mode", choices=["keyword", "url"], required=True)
    parser.add_argument("--query", required=True)
    args = parser.parse_args()
    if args.mode == "url":
        _collect_url(args.project_id, args.query)
    else:
        _collect_keyword(args.project_id, args.query)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
