import hashlib
import html
import ipaddress
import json
import re
import socket
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler

from fastapi import HTTPException

from ..config import SOURCE_CACHE_DIR
from ..db import now_iso
from ..types import SourceDraftFactNote, SourceDraftSource

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0 Safari/537.36 "
    "newauto-source-fetch/1.0"
)
REQUEST_TIMEOUT_SEC = 10
MAX_REDIRECTS = 3
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
CACHE_TTL = timedelta(hours=24)
SUSPICIOUS_PATTERNS = (
    r"ignore (?:all )?previous instructions",
    r"system prompt",
    r"<\|im_start\|>",
    r"<\|im_end\|>",
    r"```(?:system|assistant)",
    r"이전 지시(?:를|문)? 무시",
)
BOILERPLATE_LINE_PATTERNS = (
    r"이동\s*통신망을\s*이용하여\s*음성을\s*재생하면",
    r"별도의\s*데이터\s*통화료가\s*부과",
    r"구독|좋아요|댓글|공유하기",
)


@dataclass(frozen=True)
class ExtractedSource:
    source: SourceDraftSource
    fact_notes: list[SourceDraftFactNote]
    warnings: list[str]
    sanitized_text: str


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: object,
        code: int,
        msg: str,
        headers: object,
        newurl: str,
    ) -> None:
        return None


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ignore_depth = 0
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self._current_tag = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._current_tag = tag.lower()
        if self._current_tag in {"script", "style", "noscript"}:
            self._ignore_depth += 1
        if self._current_tag in {"p", "br", "div", "article", "section", "li", "h1", "h2", "h3"}:
            self.text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        lower_tag = tag.lower()
        if lower_tag in {"script", "style", "noscript"} and self._ignore_depth > 0:
            self._ignore_depth -= 1
        if lower_tag in {"p", "br", "div", "article", "section", "li", "h1", "h2", "h3"}:
            self.text_parts.append("\n")
        self._current_tag = ""

    def handle_data(self, data: str) -> None:
        if self._ignore_depth > 0:
            return
        cleaned = re.sub(r"\s+", " ", html.unescape(data)).strip()
        if not cleaned:
            return
        if self._current_tag == "title":
            self.title_parts.append(cleaned)
        self.text_parts.append(cleaned)


def _cache_path(url: str) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return SOURCE_CACHE_DIR / f"{digest}.json"


def _parse_domain(url: str) -> str:
    return urlparse(url).netloc.lower()


def _normalize_url(url: str) -> str:
    normalized = url.strip()
    if not normalized:
        raise HTTPException(400, "URL을 입력해 주세요.")
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(400, "http 또는 https URL만 분석할 수 있습니다.")
    if not parsed.netloc:
        raise HTTPException(400, "올바른 기사 URL 형식이 아닙니다.")
    _assert_public_host(parsed.hostname or "")
    return parsed.geturl()


def _assert_public_host(hostname: str) -> None:
    if not hostname:
        raise HTTPException(400, "호스트 이름을 확인할 수 없습니다.")
    lower_host = hostname.lower()
    if lower_host in {"localhost", "127.0.0.1", "::1"}:
        raise HTTPException(400, "로컬 주소는 분석할 수 없습니다.")
    try:
        ip = ipaddress.ip_address(lower_host)
        candidates = [ip]
    except ValueError:
        try:
            candidates = []
            for item in socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP):
                sockaddr = item[4]
                address = sockaddr[0]
                candidates.append(ipaddress.ip_address(address))
        except socket.gaierror as exc:
            raise HTTPException(400, f"호스트를 조회할 수 없습니다: {hostname}") from exc
    for candidate in candidates:
        if (
            candidate.is_private
            or candidate.is_loopback
            or candidate.is_link_local
            or candidate.is_multicast
            or candidate.is_reserved
            or candidate.is_unspecified
        ):
            raise HTTPException(400, "내부망 또는 예약 주소는 분석할 수 없습니다.")


def sanitize_extracted_text(raw: str) -> str:
    sanitized = raw
    for pattern in SUSPICIOUS_PATTERNS:
        sanitized = re.sub(pattern, "[REDACTED]", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\n{3,}", "\n\n", sanitized)
    return sanitized.strip()[:8000]


def _mojibake_score(text: str) -> int:
    marker_count = sum(
        text.count(marker)
        for marker in (
            "\u00c2",
            "\u00c3",
            "\u00e2",
            "\u00ec",
            "\u00ed",
            "\u00eb",
            "\u00ea",
            "\u0080",
            "\u0081",
            "\ufffd",
        )
    )
    hangul_count = len(re.findall(r"[가-힣]", text))
    return marker_count * 10 + text.count("\ufffd") * 20 - min(hangul_count, 200)


def _looks_mojibake(text: str) -> bool:
    return _mojibake_score(text) > 80 and len(re.findall(r"[가-힣]", text)) < 20


def _read_cache(url: str) -> ExtractedSource | None:
    cache_path = _cache_path(url)
    if not cache_path.exists():
        return None
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    cached_at = payload.get("cached_at")
    if not isinstance(cached_at, str):
        return None
    try:
        cached_dt = datetime.fromisoformat(cached_at)
    except ValueError:
        return None
    if datetime.now(timezone.utc) - cached_dt.astimezone(timezone.utc) > CACHE_TTL:
        return None
    source = payload.get("source")
    fact_notes = payload.get("fact_notes")
    warnings = payload.get("warnings")
    sanitized_text = payload.get("sanitized_text")
    if (
        not isinstance(source, dict)
        or not isinstance(fact_notes, list)
        or not isinstance(warnings, list)
        or not isinstance(sanitized_text, str)
    ):
        return None
    if _looks_mojibake(sanitized_text):
        return None
    return ExtractedSource(
        source=source,  # type: ignore[arg-type]
        fact_notes=fact_notes,  # type: ignore[arg-type]
        warnings=[item for item in warnings if isinstance(item, str)],
        sanitized_text=sanitized_text,
    )


def _write_cache(url: str, extracted: ExtractedSource) -> None:
    cache_path = _cache_path(url)
    payload = {
        "cached_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": extracted.source,
        "fact_notes": extracted.fact_notes,
        "warnings": extracted.warnings,
        "sanitized_text": extracted.sanitized_text,
    }
    cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _decode_html_body(body: bytes, charset: str | None) -> str:
    head = body[:4096].decode("ascii", errors="ignore")
    meta_match = re.search(
        r"<meta[^>]+charset=[\"']?\s*([a-zA-Z0-9_\-]+)",
        head,
        flags=re.IGNORECASE,
    )
    candidates: list[str] = []
    if meta_match:
        candidates.append(meta_match.group(1))
    if charset:
        candidates.append(charset)
    candidates.append("utf-8")

    decoded_by_charset: dict[str, str] = {}
    for candidate in candidates:
        normalized = candidate.strip().lower()
        if not normalized or normalized in decoded_by_charset:
            continue
        try:
            decoded_by_charset[normalized] = body.decode(normalized, errors="replace")
        except LookupError:
            continue

    if decoded_by_charset:
        # Naver can be served with a misleading ISO-8859-1 header while the
        # document itself is UTF-8. Prefer the decode that avoids mojibake.
        def score(text: str) -> int:
            return _mojibake_score(text) + text.count("챙") + text.count("챘") + text.count("챠")

        return min(decoded_by_charset.values(), key=score)
    return body.decode("utf-8", errors="replace")


def _fetch_html(url: str) -> tuple[str, str]:
    opener = build_opener(_NoRedirectHandler())
    request_url = url
    for _ in range(MAX_REDIRECTS + 1):
        parsed = urlparse(request_url)
        _assert_public_host(parsed.hostname or "")
        request = Request(
            request_url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        try:
            with opener.open(request, timeout=REQUEST_TIMEOUT_SEC) as response:
                final_url = response.geturl()
                final_parsed = urlparse(final_url)
                _assert_public_host(final_parsed.hostname or "")
                content_type = response.headers.get("Content-Type", "")
                if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                    raise HTTPException(400, "HTML 기사 페이지만 분석할 수 있습니다.")
                body = response.read(MAX_RESPONSE_BYTES + 1)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise HTTPException(400, "응답이 너무 커서 분석할 수 없습니다.")
                charset = response.headers.get_content_charset()
                return final_url, _decode_html_body(body, charset)
        except HTTPError as exc:
            if exc.code in {301, 302, 303, 307, 308}:
                location = exc.headers.get("Location")
                if not location:
                    raise HTTPException(400, "리디렉션 주소를 확인할 수 없습니다.") from exc
                request_url = urljoin(request_url, location)
                continue
            raise HTTPException(exc.code, f"기사 페이지를 가져오지 못했습니다: HTTP {exc.code}") from exc
        except URLError as exc:
            raise HTTPException(400, "기사 페이지에 연결하지 못했습니다.") from exc
    raise HTTPException(400, "리디렉션이 너무 많아 분석을 중단했습니다.")


def _extract_text(html_text: str) -> tuple[str, str]:
    parser = _HTMLTextExtractor()
    parser.feed(html_text)
    title = re.sub(r"\s+", " ", " ".join(parser.title_parts)).strip()
    raw_text = "\n".join(parser.text_parts)
    lines = [re.sub(r"\s+", " ", line).strip() for line in raw_text.splitlines()]
    filtered = [
        line
        for line in lines
        if len(line) >= 30
        and not any(re.search(pattern, line, flags=re.IGNORECASE) for pattern in BOILERPLATE_LINE_PATTERNS)
    ]
    article_text = "\n".join(filtered)
    return title, article_text


def _split_sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    chunks = re.split(r"(?<=[.!?。！？다])\s+|\n+", normalized)
    return [chunk.strip(" -") for chunk in chunks if len(chunk.strip(" -")) >= 20]


def _build_fact_notes(source_id: str, article_text: str) -> list[SourceDraftFactNote]:
    fact_notes: list[SourceDraftFactNote] = []
    seen: set[str] = set()
    for sentence in _split_sentences(article_text):
        compact = sentence[:220]
        key = compact.lower()
        if key in seen:
            continue
        seen.add(key)
        fact_notes.append({"source_id": source_id, "note": compact})
        if len(fact_notes) >= 6:
            break
    return fact_notes


def analyze_source_url(url: str) -> ExtractedSource:
    normalized_url = _normalize_url(url)
    cached = _read_cache(normalized_url)
    if cached is not None:
        return cached

    final_url, html_text = _fetch_html(normalized_url)
    title, article_text = _extract_text(html_text)
    sanitized_text = sanitize_extracted_text(article_text)
    if len(sanitized_text) < 120:
        raise HTTPException(400, "기사 본문을 충분히 추출하지 못했습니다.")

    source_id = hashlib.sha256(final_url.encode("utf-8")).hexdigest()[:12]
    fact_notes = _build_fact_notes(source_id, sanitized_text)
    if not fact_notes:
        raise HTTPException(400, "핵심 사실 후보를 만들 만큼 본문을 읽지 못했습니다.")

    source: SourceDraftSource = {
        "id": source_id,
        "url": normalized_url,
        "final_url": final_url,
        "title": title or _parse_domain(final_url),
        "domain": _parse_domain(final_url),
        "author": "",
        "published_at": "",
        "language": "ko" if re.search(r"[가-힣]", sanitized_text) else "",
        "excerpt": sanitized_text[:480],
        "fetched_at": now_iso(),
        "word_count": len(sanitized_text.split()),
    }
    warnings = [
        "자동 추출 결과이므로 사실 관계와 맥락은 한 번 더 확인해 주세요.",
        "원문 문장을 그대로 대본에 복사하지 말고, fact note 기반으로 다시 구성해야 합니다.",
    ]
    extracted = ExtractedSource(
        source=source,
        fact_notes=fact_notes,
        warnings=warnings,
        sanitized_text=sanitized_text,
    )
    _write_cache(normalized_url, extracted)
    return extracted
