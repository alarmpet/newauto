import json
from typing import cast
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from ..config import PEXELS_API_KEY, PIXABAY_API_KEY
from ..types import StockSearchItem, StockSearchResponse


def _read_json(url: str, headers: dict[str, str] | None = None) -> dict[str, object]:
    request = Request(url, headers=headers or {})
    with urlopen(request, timeout=10) as response:  # noqa: S310
        payload = response.read().decode("utf-8")
    return cast(dict[str, object], json.loads(payload))


def _search_pexels(query: str) -> list[StockSearchItem]:
    if not PEXELS_API_KEY:
        return []
    payload = _read_json(
        f"https://api.pexels.com/v1/search?query={quote_plus(query)}&per_page=6",
        headers={"Authorization": PEXELS_API_KEY},
    )
    photos = payload.get("photos")
    if not isinstance(photos, list):
        return []
    results: list[StockSearchItem] = []
    for item in photos:
        if not isinstance(item, dict):
            continue
        src = item.get("src")
        if not isinstance(src, dict):
            continue
        medium = src.get("medium")
        original = src.get("original")
        page_url = item.get("url")
        photographer = item.get("photographer")
        if not all(isinstance(value, str) for value in (medium, original, page_url)):
            continue
        media_url = str(original)
        thumbnail_url = str(medium)
        attribution_url = str(page_url)
        results.append(
            {
                "provider": "pexels",
                "title": str(photographer or "Pexels asset"),
                "media_url": media_url,
                "thumbnail_url": thumbnail_url,
                "attribution_url": attribution_url,
            }
        )
    return results


def _search_pixabay(query: str) -> list[StockSearchItem]:
    if not PIXABAY_API_KEY:
        return []
    payload = _read_json(
        f"https://pixabay.com/api/?key={quote_plus(PIXABAY_API_KEY)}&q={quote_plus(query)}&image_type=photo&per_page=6"
    )
    hits = payload.get("hits")
    if not isinstance(hits, list):
        return []
    results: list[StockSearchItem] = []
    for item in hits:
        if not isinstance(item, dict):
            continue
        preview = item.get("previewURL")
        large = item.get("largeImageURL")
        page_url = item.get("pageURL")
        user = item.get("user")
        if not all(isinstance(value, str) for value in (preview, large, page_url)):
            continue
        media_url = str(large)
        thumbnail_url = str(preview)
        attribution_url = str(page_url)
        results.append(
            {
                "provider": "pixabay",
                "title": str(user or "Pixabay asset"),
                "media_url": media_url,
                "thumbnail_url": thumbnail_url,
                "attribution_url": attribution_url,
            }
        )
    return results


def search_stock_media(query: str) -> StockSearchResponse:
    cleaned_query = query.strip()
    if not cleaned_query:
        return {"query": "", "results": []}
    results = _search_pexels(cleaned_query) + _search_pixabay(cleaned_query)
    return {
        "query": cleaned_query,
        "results": results,
    }
