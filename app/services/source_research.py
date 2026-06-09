import json
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, unquote, urlencode, urlparse
from urllib.request import Request, urlopen

from fastapi import HTTPException

from ..config import BRAVE_API_KEY, BRAVE_FREE_MONTHLY_LIMIT, BRAVE_USAGE_PATH, SOURCE_RESEARCH_CACHE_DIR
from .web_search import parse_duckduckgo_html
from .usage_registry import get_provider_usage, reserve_provider_usage

BRAVE_WEB_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
DUCKDUCKGO_HTML_SEARCH_URL = "https://duckduckgo.com/html/"
KEYWORD_CACHE_TTL = timedelta(hours=24)


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    description: str


def _current_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _keyword_cache_path(query: str) -> Path:
    digest = hashlib.sha256(query.strip().lower().encode("utf-8")).hexdigest()
    return SOURCE_RESEARCH_CACHE_DIR / f"{digest}.json"


def _read_usage(path: Path = BRAVE_USAGE_PATH) -> dict[str, object]:
    if path != BRAVE_USAGE_PATH:
        if not path.exists():
            return {"month": _current_month(), "count": 0}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"month": _current_month(), "count": 0}
        month = payload.get("month")
        count = payload.get("count")
        if not isinstance(month, str) or not isinstance(count, int):
            return {"month": _current_month(), "count": 0}
        if month != _current_month():
            return {"month": _current_month(), "count": 0}
        return {"month": month, "count": count}
    record = get_provider_usage("brave_search", month_limit=BRAVE_FREE_MONTHLY_LIMIT)
    return {"month": record["last_month_reset"], "count": record["month_count"]}


def _write_usage(payload: dict[str, object], path: Path = BRAVE_USAGE_PATH) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def get_brave_usage_status(path: Path = BRAVE_USAGE_PATH) -> dict[str, int | str]:
    usage = _read_usage(path)
    count = usage["count"]
    if not isinstance(count, int):
        count = 0
    return {
        "month": str(usage["month"]),
        "used": count,
        "remaining": max(BRAVE_FREE_MONTHLY_LIMIT - count, 0),
        "limit": BRAVE_FREE_MONTHLY_LIMIT,
    }


def _reserve_brave_query(path: Path = BRAVE_USAGE_PATH) -> dict[str, int | str]:
    if not BRAVE_API_KEY:
        raise HTTPException(400, "BRAVE_API_KEY가 설정되지 않아 키워드 리서치를 실행할 수 없습니다.")
    if path != BRAVE_USAGE_PATH:
        usage = _read_usage(path)
        count = usage["count"]
        if not isinstance(count, int):
            count = 0
        if count >= BRAVE_FREE_MONTHLY_LIMIT:
            raise HTTPException(429, f"이번 달 Brave 무료 검색 한도 {BRAVE_FREE_MONTHLY_LIMIT}건을 모두 사용했습니다.")
        new_count = count + 1
        updated = {"month": str(usage["month"]), "count": new_count}
        _write_usage(updated, path)
        return {
            "month": str(updated["month"]),
            "used": new_count,
            "remaining": max(BRAVE_FREE_MONTHLY_LIMIT - new_count, 0),
            "limit": BRAVE_FREE_MONTHLY_LIMIT,
        }
    updated_record = reserve_provider_usage("brave_search", month_limit=BRAVE_FREE_MONTHLY_LIMIT)
    updated_month = updated_record["last_month_reset"]
    updated_count = updated_record["month_count"]
    return {
        "month": updated_month,
        "used": updated_count,
        "remaining": max(BRAVE_FREE_MONTHLY_LIMIT - updated_count, 0),
        "limit": BRAVE_FREE_MONTHLY_LIMIT,
    }


def _html_unescape(text: str) -> str:
    import html

    return html.unescape(re.sub(r"<[^>]+>", " ", text)).strip()


def _duckduckgo_result_url(raw_url: str) -> str:
    parsed = urlparse(raw_url)
    if "duckduckgo.com" not in parsed.netloc:
        return raw_url
    query = parse_qs(parsed.query)
    uddg = query.get("uddg")
    if uddg and uddg[0]:
        return unquote(uddg[0])
    return raw_url


def _collect_sources_from_duckduckgo_html(query: str, *, count: int) -> tuple[list[SearchResult], dict[str, int | str]]:
    params = urlencode({"q": query, "kl": "kr-ko"})
    request = Request(
        f"{DUCKDUCKGO_HTML_SEARCH_URL}?{params}",
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) newauto-source-research/1.0",
            "Accept": "text/html,application/xhtml+xml",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=20) as response:
            html_text = response.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError) as exc:
        raise HTTPException(502, f"DuckDuckGo HTML 검색에 연결하지 못했습니다: {exc}") from exc

    results = [
        SearchResult(title=item.title, url=item.url, description=item.snippet)
        for item in parse_duckduckgo_html(html_text, limit=max(1, min(count, 10)))
    ]
    if not results:
        raise HTTPException(404, "DuckDuckGo HTML 검색에서도 수집할 검색 결과를 찾지 못했습니다.")
    usage = get_brave_usage_status()
    usage["provider"] = "duckduckgo_html"
    usage["cache"] = "fallback"
    return results, usage


def _read_keyword_cache(query: str) -> tuple[list[SearchResult], dict[str, int | str]] | None:
    cache_path = _keyword_cache_path(query)
    if not cache_path.exists():
        return None
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    cached_at = payload.get("cached_at")
    results_payload = payload.get("results")
    if not isinstance(cached_at, str) or not isinstance(results_payload, list):
        return None
    try:
        cached_dt = datetime.fromisoformat(cached_at)
    except ValueError:
        return None
    if datetime.now(timezone.utc) - cached_dt.astimezone(timezone.utc) > KEYWORD_CACHE_TTL:
        return None
    results: list[SearchResult] = []
    for item in results_payload:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        url = item.get("url")
        description = item.get("description")
        if isinstance(title, str) and isinstance(url, str) and isinstance(description, str):
            results.append(SearchResult(title=title, url=url, description=description))
    if not results:
        return None
    usage = get_brave_usage_status()
    usage["cache"] = "hit"
    return results, usage


def _write_keyword_cache(query: str, results: list[SearchResult]) -> None:
    cache_path = _keyword_cache_path(query)
    payload = {
        "cached_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "results": [
            {
                "title": item.title,
                "url": item.url,
                "description": item.description,
            }
            for item in results
        ],
    }
    cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def collect_sources_from_keyword(query: str, *, count: int = 5) -> tuple[list[SearchResult], dict[str, int | str]]:
    normalized_query = query.strip()
    if not normalized_query:
        raise HTTPException(400, "키워드를 입력해 주세요.")
    cached = _read_keyword_cache(normalized_query)
    if cached is not None:
        return cached
    try:
        usage = _reserve_brave_query()
    except HTTPException:
        fallback_results, fallback_usage = _collect_sources_from_duckduckgo_html(normalized_query, count=count)
        _write_keyword_cache(normalized_query, fallback_results)
        return fallback_results, fallback_usage
    params = urlencode({
        "q": normalized_query,
        "count": max(1, min(count, 10)),
        "search_lang": "ko",
        "country": "KR",
    })
    request = Request(
        f"{BRAVE_WEB_SEARCH_URL}?{params}",
        headers={
            "Accept": "application/json",
            "X-Subscription-Token": BRAVE_API_KEY,
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        fallback_results, fallback_usage = _collect_sources_from_duckduckgo_html(normalized_query, count=count)
        _write_keyword_cache(normalized_query, fallback_results)
        fallback_usage["brave_error"] = f"HTTP {exc.code} {detail}".strip()[:300]
        return fallback_results, fallback_usage
    except URLError as exc:
        fallback_results, fallback_usage = _collect_sources_from_duckduckgo_html(normalized_query, count=count)
        _write_keyword_cache(normalized_query, fallback_results)
        fallback_usage["brave_error"] = str(exc)[:300]
        return fallback_results, fallback_usage
    web_section = payload.get("web", {})
    raw_results = web_section.get("results", []) if isinstance(web_section, dict) else []
    results: list[SearchResult] = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        title = item.get("title")
        description = item.get("description")
        if isinstance(url, str) and isinstance(title, str):
            results.append(
                SearchResult(
                    title=title.strip(),
                    url=url.strip(),
                    description=description.strip() if isinstance(description, str) else "",
                )
            )
    if not results:
        raise HTTPException(404, "키워드로 수집할 검색 결과를 찾지 못했습니다.")
    _write_keyword_cache(normalized_query, results)
    return results, usage
