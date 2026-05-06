import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal
from unittest.mock import patch

from fastapi import HTTPException

from app.services import source_research


class SourceResearchTests(unittest.TestCase):
    def test_brave_usage_resets_by_month(self) -> None:
        with TemporaryDirectory() as temp_dir:
            usage_path = Path(temp_dir) / "usage.json"
            usage_path.write_text(json.dumps({"month": "2026-03", "count": 999}), encoding="utf-8")
            status = source_research.get_brave_usage_status(usage_path)
        self.assertEqual(status["used"], 0)
        self.assertEqual(status["remaining"], 1000)

    def test_brave_limit_blocks_overage(self) -> None:
        with TemporaryDirectory() as temp_dir, patch("app.services.source_research.BRAVE_API_KEY", "test-key"):
            usage_path = Path(temp_dir) / "usage.json"
            usage_path.write_text(json.dumps({"month": source_research._current_month(), "count": 1000}), encoding="utf-8")
            with self.assertRaises(HTTPException) as captured:
                source_research._reserve_brave_query(usage_path)
        self.assertEqual(captured.exception.status_code, 429)

    def test_collect_sources_from_keyword_parses_results(self) -> None:
        payload = {
            "web": {
                "results": [
                    {
                        "url": "https://example.com/news",
                        "title": "테스트 뉴스",
                        "description": "설명",
                    }
                ]
            }
        }

        class ResponseStub:
            def __enter__(self) -> "ResponseStub":
                return self

            def __exit__(self, exc_type: object, exc: object, tb: object) -> Literal[False]:
                return False

            def read(self) -> bytes:
                return json.dumps(payload).encode("utf-8")

        with TemporaryDirectory() as temp_dir, patch(
            "app.services.source_research.SOURCE_RESEARCH_CACHE_DIR",
            Path(temp_dir),
        ), patch("app.services.source_research.BRAVE_API_KEY", "test-key"), patch(
            "app.services.source_research._reserve_brave_query",
            return_value={"used": 1, "remaining": 999, "limit": 1000, "month": "2026-04"},
        ), patch(
            "app.services.source_research.urlopen",
            return_value=ResponseStub(),
        ):
            results, usage = source_research.collect_sources_from_keyword("테스트", count=3)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].url, "https://example.com/news")
        self.assertEqual(usage["used"], 1)

    def test_keyword_cache_hit_skips_brave_call(self) -> None:
        cached_results = [
            source_research.SearchResult(
                title="캐시된 기사",
                url="https://example.com/cached",
                description="cached",
            )
        ]
        with TemporaryDirectory() as temp_dir, patch(
            "app.services.source_research.SOURCE_RESEARCH_CACHE_DIR",
            Path(temp_dir),
        ), patch("app.services.source_research.urlopen") as mocked_urlopen:
            source_research._write_keyword_cache("테스트 키워드", cached_results)
            results, usage = source_research.collect_sources_from_keyword("테스트 키워드")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].url, "https://example.com/cached")
        self.assertEqual(usage["cache"], "hit")
        mocked_urlopen.assert_not_called()

    def test_collect_sources_from_keyword_falls_back_to_duckduckgo_html_without_brave_key(self) -> None:
        html_payload = """
        <html><body>
          <a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fgemini">Gemini 기사</a>
          <a class="result__snippet">Gemini 관련 설명입니다.</a>
        </body></html>
        """

        class ResponseStub:
            def __enter__(self) -> "ResponseStub":
                return self

            def __exit__(self, exc_type: object, exc: object, tb: object) -> Literal[False]:
                return False

            def read(self) -> bytes:
                return html_payload.encode("utf-8")

        with TemporaryDirectory() as temp_dir, patch(
            "app.services.source_research.SOURCE_RESEARCH_CACHE_DIR",
            Path(temp_dir),
        ), patch("app.services.source_research.BRAVE_API_KEY", ""), patch(
            "app.services.source_research.urlopen",
            return_value=ResponseStub(),
        ):
            results, usage = source_research.collect_sources_from_keyword("gemini", count=3)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].url, "https://example.com/gemini")
        self.assertEqual(results[0].title, "Gemini 기사")
        self.assertEqual(usage["provider"], "duckduckgo_html")
