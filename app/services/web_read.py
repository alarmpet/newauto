from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any
import urllib.request
from urllib.parse import urlparse

from fastapi import HTTPException

from .source_fetch import analyze_source_url
from .web_search import WebSearchResult
from .web_search import search_web


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _looks_like_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _sort_preferred_domain(results: list[WebSearchResult], prefer_domain: str) -> list[WebSearchResult]:
    domain = prefer_domain.strip().lower()
    if not domain:
        return results

    def key(item: WebSearchResult) -> tuple[int, str]:
        host = urlparse(item.url).netloc.lower()
        return (0 if domain in host else 1, item.title.lower())

    return sorted(results, key=key)


def _looks_like_naver_latest_news_query(value: str) -> bool:
    lowered = value.lower()
    return (
        ("naver" in lowered or "네이버" in lowered)
        and ("news" in lowered or "뉴스" in lowered)
        and any(token in lowered for token in ("latest", "recent", "최신", "오늘", "주요"))
    )


def _minimum_naver_latest_count(requested_count: int) -> int:
    # LM Studio tool-calling models sometimes pass count=1 while the natural
    # language request asks for several latest Naver articles.
    return max(3, requested_count)


def _clean_html_text(value: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", value).split())


def _is_low_summary_value_naver_title(title: str) -> bool:
    stripped = title.strip()
    low_value_prefixes = ("[표]", "[포토]", "[사진]", "[인사]", "[부고]")
    if stripped.startswith(low_value_prefixes):
        return True
    return re.search(r"[가-힣]", stripped) is None


def _decode_naver_html(raw: bytes) -> str:
    for encoding in ("euc-kr", "cp949", "utf-8"):
        try:
            text = raw.decode(encoding)
        except UnicodeDecodeError:
            continue
        if "네이버" in text or encoding == "utf-8":
            return text
    return raw.decode("utf-8", errors="replace")


def _fetch_naver_latest_article_links(*, limit: int) -> list[dict[str, str]]:
    url = "https://news.naver.com/main/list.naver?mode=LSD&mid=sec&sid1=001"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        },
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        page = _decode_naver_html(response.read())

    results: list[dict[str, str]] = []
    seen: set[str] = set()
    seen_titles: set[str] = set()
    pattern = re.compile(
        r'<a[^>]+href="(https://n\.news\.naver\.com/mnews/article/[^"#?]+)[^"]*"[^>]*>(.*?)</a>',
        re.S,
    )
    for match in pattern.finditer(page):
        article_url = match.group(1).strip()
        title = _clean_html_text(match.group(2))
        normalized_title = re.sub(r"\s+", " ", title).strip().lower()
        if (
            not title
            or len(title) < 8
            or article_url in seen
            or normalized_title in seen_titles
            or _is_low_summary_value_naver_title(title)
        ):
            continue
        seen.add(article_url)
        seen_titles.add(normalized_title)
        results.append({"title": title, "url": article_url})
        if len(results) >= limit:
            break
    return results


def _read_naver_latest_news(*, count: int) -> dict[str, Any]:
    limit = max(1, min(_minimum_naver_latest_count(count), 10))
    try:
        links = _fetch_naver_latest_article_links(limit=limit)
    except Exception as exc:
        return {
            "ok": False,
            "mode": "naver_latest",
            "retrieved_at": _now(),
            "failure_class": "naver_latest_list_failed",
            "message": f"{type(exc).__name__}: {exc}",
            "next_action_suggestion": "try_search_web_or_browser",
        }
    if not links:
        return {
            "ok": False,
            "mode": "naver_latest",
            "retrieved_at": _now(),
            "failure_class": "naver_latest_parse_failed",
            "message": "Naver latest news list returned no parsed article links.",
            "next_action_suggestion": "try_search_web_or_browser",
        }

    articles: list[dict[str, Any]] = []
    for link in links:
        try:
            extracted = analyze_source_url(link["url"])
        except HTTPException as exc:
            articles.append(
                {
                    "title": link["title"],
                    "url": link["url"],
                    "ok": False,
                    "failure_class": "article_read_failed",
                    "message": str(exc.detail),
                }
            )
            continue
        fact_notes = extracted.fact_notes[:3] if isinstance(extracted.fact_notes, list) else []
        articles.append(
            {
                "title": extracted.source.get("title") or link["title"],
                "url": extracted.source.get("final_url") or link["url"],
                "ok": True,
                "fact_notes": fact_notes,
                "summary_text": extracted.sanitized_text[:1200],
            }
        )

    return {
        "ok": True,
        "mode": "naver_latest",
        "retrieved_at": _now(),
        "source_url": "https://news.naver.com/main/list.naver?mode=LSD&mid=sec&sid1=001",
        "articles": articles,
    }


def read_url_or_search(query_or_url: str, *, count: int = 3, prefer_domain: str = "") -> dict[str, Any]:
    target = query_or_url.strip()
    if not target:
        return {
            "ok": False,
            "mode": "unknown",
            "retrieved_at": _now(),
            "failure_class": "empty_query_or_url",
            "message": "query_or_url is empty.",
            "next_action_suggestion": "provide_query_or_url",
        }

    if _looks_like_url(target):
        try:
            extracted = analyze_source_url(target)
        except HTTPException as exc:
            return {
                "ok": False,
                "mode": "read_url",
                "retrieved_at": _now(),
                "url": target,
                "failure_class": "url_read_failed",
                "status_code": exc.status_code,
                "message": str(exc.detail),
                "next_action_suggestion": "try_search_web_or_browser",
            }
        return {
            "ok": True,
            "mode": "read_url",
            "retrieved_at": _now(),
            "source": extracted.source,
            "fact_notes": extracted.fact_notes,
            "warnings": extracted.warnings,
            "sanitized_text": extracted.sanitized_text,
        }

    if _looks_like_naver_latest_news_query(target):
        return _read_naver_latest_news(count=count)

    response = search_web(target, max_results=count)
    if not response.ok:
        return {
            "ok": False,
            "mode": "search",
            "retrieved_at": response.retrieved_at,
            "query": target,
            "failure_class": response.failure_class,
            "message": response.message,
            "next_action_suggestion": response.next_action_suggestion,
        }
    results = _sort_preferred_domain(response.results, prefer_domain)[: max(1, min(count, 10))]
    return {
        "ok": True,
        "mode": "search",
        "retrieved_at": response.retrieved_at,
        "query": target,
        "prefer_domain": prefer_domain,
        "source_method": response.source_method,
        "search_url": response.search_url,
        "results": [asdict(item) for item in results],
    }


def format_read_url_or_search(payload: dict[str, Any]) -> str:
    if payload.get("ok") is not True:
        return (
            "read_url_or_search failed\n"
            f"mode: {payload.get('mode', 'unknown')}\n"
            f"failure_class: {payload.get('failure_class', '')}\n"
            f"message: {payload.get('message', '')}\n"
            f"next_action_suggestion: {payload.get('next_action_suggestion', '')}\n"
            f"payload: {json.dumps(payload, ensure_ascii=False, sort_keys=True)}"
        )

    if payload.get("mode") == "read_url":
        raw_source = payload.get("source")
        source: dict[str, Any] = raw_source if isinstance(raw_source, dict) else {}
        raw_fact_notes = payload.get("fact_notes")
        fact_notes: list[Any] = raw_fact_notes if isinstance(raw_fact_notes, list) else []
        lines = [
            "=== read_url_or_search result ===",
            "mode: read_url",
            f"retrieved_at: {payload.get('retrieved_at', '')}",
            f"title: {source.get('title', '')}",
            f"url: {source.get('final_url') or source.get('url', '')}",
            "",
            "fact_notes:",
        ]
        for index, item in enumerate(fact_notes[:6], start=1):
            note = item.get("note", "") if isinstance(item, dict) else str(item)
            lines.append(f"{index}. {note}")
        return "\n".join(lines)

    if payload.get("mode") == "naver_latest":
        lines = [
            "=== read_url_or_search result ===",
            "mode: naver_latest",
            f"retrieved_at: {payload.get('retrieved_at', '')}",
            f"source_url: {payload.get('source_url', '')}",
            "",
        ]
        raw_articles = payload.get("articles")
        articles: list[Any] = raw_articles if isinstance(raw_articles, list) else []
        for index, item in enumerate(articles, start=1):
            if not isinstance(item, dict):
                continue
            lines.append(f"{index}. {item.get('title', '')}")
            lines.append(f"   url: {item.get('url', '')}")
            if item.get("ok") is False:
                lines.append(f"   read_error: {item.get('message', '')}")
                continue
            raw_notes = item.get("fact_notes")
            notes: list[Any] = raw_notes if isinstance(raw_notes, list) else []
            for note_index, note in enumerate(notes[:3], start=1):
                text = note.get("note", "") if isinstance(note, dict) else str(note)
                if text:
                    lines.append(f"   summary_{note_index}: {text}")
            if not notes and item.get("summary_text"):
                lines.append(f"   summary: {str(item.get('summary_text'))[:500]}")
        return "\n".join(lines)

    lines = [
        "=== read_url_or_search result ===",
        "mode: search",
        f"query: {payload.get('query', '')}",
        f"prefer_domain: {payload.get('prefer_domain', '')}",
        f"source_method: {payload.get('source_method', '')}",
        f"retrieved_at: {payload.get('retrieved_at', '')}",
        "",
    ]
    raw_results = payload.get("results")
    results: list[Any] = raw_results if isinstance(raw_results, list) else []
    for index, item in enumerate(results, start=1):
        if not isinstance(item, dict):
            continue
        lines.append(f"{index}. {item.get('title', '')}")
        lines.append(f"   url: {item.get('url', '')}")
        if item.get("snippet"):
            lines.append(f"   snippet: {str(item.get('snippet'))[:500]}")
    return "\n".join(lines)
