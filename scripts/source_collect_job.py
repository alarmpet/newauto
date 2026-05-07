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
from app.types import SourceDraftFactNote, SourceDraftSource


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
    _set_done(pid, "url", url, [extracted.source], extracted.fact_notes, extracted.warnings)


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
            except HTTPException:
                skipped += 1
                continue
            sources.append(extracted.source)
            fact_notes.extend(extracted.fact_notes)
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
