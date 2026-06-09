from __future__ import annotations

import html
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any


DUCKDUCKGO_SEARCH_ENDPOINTS = (
    ("duckduckgo_html", "https://duckduckgo.com/html/"),
    ("duckduckgo_html_direct", "https://html.duckduckgo.com/html/"),
    ("duckduckgo_lite", "https://lite.duckduckgo.com/lite/"),
)
GOOGLE_NEWS_RSS_SEARCH_URL = "https://news.google.com/rss/search"
NEWS_QUERY_HINTS = (
    "news",
    "latest",
    "headline",
    "breaking",
    "뉴스",
    "최신",
    "기사",
    "속보",
)


@dataclass(frozen=True)
class WebSearchResult:
    title: str
    url: str
    snippet: str = ""


@dataclass(frozen=True)
class WebSearchResponse:
    ok: bool
    query: str
    source_method: str
    retrieved_at: str
    results: list[WebSearchResult]
    search_url: str = ""
    failure_class: str = ""
    message: str = ""
    next_action_suggestion: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["results"] = [asdict(item) for item in self.results]
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def clean_html_text(value: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", value)).split())


def normalize_duckduckgo_href(href: str) -> str:
    candidate = html.unescape(href.strip())
    if candidate.startswith("//"):
        candidate = "https:" + candidate
    parsed = urllib.parse.urlparse(candidate)
    query = urllib.parse.parse_qs(parsed.query)
    redirected = query.get("uddg")
    if redirected and redirected[0]:
        return urllib.parse.unquote(redirected[0])
    return candidate


class DuckDuckGoResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[WebSearchResult] = []
        self._capture_title = False
        self._current_href = ""
        self._current_text: list[str] = []
        self._capture_snippet = False
        self._snippet_text: list[str] = []
        self._snippet_index = -1

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: value or "" for key, value in attrs}
        class_name = attr_map.get("class", "")
        if tag == "a" and ("result__a" in class_name or "result-link" in class_name):
            self._capture_title = True
            self._current_href = attr_map.get("href", "")
            self._current_text = []
            return
        if "result__snippet" in class_name or "result-snippet" in class_name:
            self._capture_snippet = True
            self._snippet_text = []
            self._snippet_index = len(self.results) - 1

    def handle_data(self, data: str) -> None:
        if self._capture_title:
            self._current_text.append(data)
        if self._capture_snippet:
            self._snippet_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._capture_title and tag == "a":
            title = clean_html_text("".join(self._current_text))
            url = normalize_duckduckgo_href(self._current_href)
            if title and url:
                self.results.append(WebSearchResult(title=title, url=url, snippet=""))
            self._capture_title = False
            self._current_href = ""
            self._current_text = []
            return
        if self._capture_snippet and tag in {"a", "div", "td"}:
            snippet = clean_html_text("".join(self._snippet_text))
            if snippet and 0 <= self._snippet_index < len(self.results):
                current = self.results[self._snippet_index]
                self.results[self._snippet_index] = WebSearchResult(
                    title=current.title,
                    url=current.url,
                    snippet=snippet,
                )
            self._capture_snippet = False
            self._snippet_text = []
            self._snippet_index = -1


def dedupe_results(results: list[WebSearchResult], limit: int) -> list[WebSearchResult]:
    seen_urls: set[str] = set()
    deduped: list[WebSearchResult] = []
    for result in results:
        url = result.url.strip()
        title = result.title.strip()
        if not url or not title or url in seen_urls:
            continue
        if not url.startswith(("http://", "https://")):
            continue
        seen_urls.add(url)
        deduped.append(WebSearchResult(title=title, url=url, snippet=result.snippet.strip()))
        if len(deduped) >= limit:
            break
    return deduped


def parse_duckduckgo_html(page: str, *, limit: int = 5) -> list[WebSearchResult]:
    parser = DuckDuckGoResultParser()
    parser.feed(page)
    return dedupe_results(parser.results, max(1, min(limit, 10)))


def looks_like_news_query(query: str) -> bool:
    lowered = query.lower()
    return any(hint in lowered for hint in NEWS_QUERY_HINTS)


def parse_google_news_rss(feed: bytes, *, limit: int = 5) -> list[WebSearchResult]:
    try:
        root = ET.fromstring(feed)
    except ET.ParseError:
        return []

    results: list[WebSearchResult] = []
    for item in root.findall("./channel/item"):
        title = clean_html_text(item.findtext("title") or "")
        link = (item.findtext("link") or "").strip()
        snippet = clean_html_text(item.findtext("description") or "")
        if title and link:
            results.append(WebSearchResult(title=title, url=link, snippet=snippet))
    return dedupe_results(results, max(1, min(limit, 10)))


def search_google_news_rss(query: str, *, limit: int, timeout_sec: int) -> tuple[str, list[WebSearchResult], str]:
    search_url = GOOGLE_NEWS_RSS_SEARCH_URL + "?" + urllib.parse.urlencode(
        {"q": query, "hl": "ko", "gl": "KR", "ceid": "KR:ko"}
    )
    request = urllib.request.Request(
        search_url,
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/rss+xml, application/xml"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            feed = response.read()
    except Exception as exc:
        return search_url, [], f"{type(exc).__name__}: {exc}"
    return search_url, parse_google_news_rss(feed, limit=limit), ""


def search_web(query: str, *, max_results: int = 5, timeout_sec: int = 25) -> WebSearchResponse:
    cleaned_query = query.strip()
    if not cleaned_query:
        return WebSearchResponse(
            ok=False,
            query=query,
            source_method="duckduckgo_html",
            retrieved_at=_now(),
            results=[],
            failure_class="empty_query",
            message="Search query is empty.",
            next_action_suggestion="provide_query",
        )

    limit = max(1, min(int(max_results), 10))
    last_url = ""
    last_error = ""
    last_failure_class = "search_parse_failed"

    if looks_like_news_query(cleaned_query):
        search_url, results, rss_error = search_google_news_rss(cleaned_query, limit=limit, timeout_sec=timeout_sec)
        if results:
            return WebSearchResponse(
                ok=True,
                query=cleaned_query,
                source_method="google_news_rss",
                retrieved_at=_now(),
                results=results,
                search_url=search_url,
            )
        last_url = search_url
        if rss_error:
            last_error = rss_error
            last_failure_class = "search_request_failed"

    for source_method, base_url in DUCKDUCKGO_SEARCH_ENDPOINTS:
        search_url = base_url + "?" + urllib.parse.urlencode({"q": cleaned_query})
        last_url = search_url
        request = urllib.request.Request(
            search_url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_sec) as response:
                page = response.read().decode("utf-8", errors="replace")
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            last_failure_class = "search_request_failed"
            continue

        results = parse_duckduckgo_html(page, limit=limit)
        if results:
            return WebSearchResponse(
                ok=True,
                query=cleaned_query,
                source_method=source_method,
                retrieved_at=_now(),
                results=results,
                search_url=search_url,
            )
        last_error = "DuckDuckGo HTML returned no parsed results."
        last_failure_class = "search_parse_failed"

    return WebSearchResponse(
        ok=False,
        query=cleaned_query,
        source_method="duckduckgo_multi_endpoint",
        retrieved_at=_now(),
        results=[],
        search_url=last_url,
        failure_class=last_failure_class,
        message=last_error or "DuckDuckGo search failed.",
        next_action_suggestion="try_http_request_or_browser",
    )


def format_search_response(response: WebSearchResponse, *, snippet_limit: int = 500) -> str:
    if not response.ok:
        return (
            "search_web failed\n"
            f"query: {response.query}\n"
            f"source_method: {response.source_method}\n"
            f"failure_class: {response.failure_class}\n"
            f"message: {response.message}\n"
            f"next_action_suggestion: {response.next_action_suggestion}"
        )

    lines = [
        "=== search_web results ===",
        f"query: {response.query}",
        f"source_method: {response.source_method}",
        f"retrieved_at: {response.retrieved_at}",
        f"search_url: {response.search_url}",
        "instruction: Use these URLs as sources. Prefer official docs when present.",
        "",
    ]
    for index, result in enumerate(response.results, start=1):
        lines.append(f"{index}. {result.title}")
        lines.append(f"   url: {result.url}")
        if result.snippet:
            lines.append(f"   snippet: {result.snippet[:snippet_limit]}")
    return "\n".join(lines)
