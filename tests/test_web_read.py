from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.services.web_read import format_read_url_or_search
from app.services.web_read import _is_low_summary_value_naver_title
from app.services.web_read import _minimum_naver_latest_count
from app.services.web_read import read_url_or_search
from app.services.web_search import WebSearchResponse
from app.services.web_search import WebSearchResult


class WebReadTests(unittest.TestCase):
    def test_low_summary_value_naver_titles_are_detected(self) -> None:
        self.assertTrue(_is_low_summary_value_naver_title("[포토] 행사 사진"))
        self.assertTrue(_is_low_summary_value_naver_title("[표] 외국환율고시표"))
        self.assertTrue(_is_low_summary_value_naver_title("MIDEAST PALESTINIANS ISRAEL CONFLICT"))
        self.assertFalse(_is_low_summary_value_naver_title("정부, 주택공급에 속도낸다"))

    def test_naver_latest_count_has_minimum_three(self) -> None:
        self.assertEqual(_minimum_naver_latest_count(1), 3)
        self.assertEqual(_minimum_naver_latest_count(3), 3)
        self.assertEqual(_minimum_naver_latest_count(5), 5)

    def test_read_url_or_search_reads_url(self) -> None:
        extracted = type(
            "Extracted",
            (),
            {
                "source": {"title": "Story", "final_url": "https://example.com/story", "url": "https://example.com/story"},
                "fact_notes": [{"note": "A useful fact note."}],
                "warnings": [],
                "sanitized_text": "A useful fact note.",
            },
        )()
        with patch("app.services.web_read.analyze_source_url", return_value=extracted):
            payload = read_url_or_search("https://example.com/story")

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["mode"], "read_url")
        self.assertEqual(payload["source"]["title"], "Story")

    def test_read_url_or_search_reports_url_failure(self) -> None:
        with patch("app.services.web_read.analyze_source_url", side_effect=HTTPException(400, "blocked")):
            payload = read_url_or_search("https://example.com/story")

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["failure_class"], "url_read_failed")
        self.assertEqual(payload["next_action_suggestion"], "try_search_web_or_browser")

    def test_read_url_or_search_sorts_preferred_domain(self) -> None:
        response = WebSearchResponse(
            ok=True,
            query="news",
            source_method="duckduckgo_html",
            retrieved_at="2026-05-15T00:00:00+00:00",
            search_url="https://duckduckgo.com/html/?q=news",
            results=[
                WebSearchResult(title="Other", url="https://example.com/a", snippet=""),
                WebSearchResult(title="Naver", url="https://news.naver.com/b", snippet=""),
            ],
        )
        with patch("app.services.web_read.search_web", return_value=response):
            payload = read_url_or_search("news", prefer_domain="news.naver.com")

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["mode"], "search")
        self.assertEqual(payload["results"][0]["url"], "https://news.naver.com/b")

    def test_read_url_or_search_uses_naver_latest_fallback(self) -> None:
        extracted = type(
            "Extracted",
            (),
            {
                "source": {
                    "title": "Latest Story",
                    "final_url": "https://n.news.naver.com/mnews/article/001/0001",
                    "url": "https://n.news.naver.com/mnews/article/001/0001",
                },
                "fact_notes": [{"note": "Latest story summary."}],
                "warnings": [],
                "sanitized_text": "Latest story summary.",
            },
        )()
        with patch(
            "app.services.web_read._fetch_naver_latest_article_links",
            return_value=[
                {
                    "title": "Latest Story",
                    "url": "https://n.news.naver.com/mnews/article/001/0001",
                }
            ],
        ), patch("app.services.web_read.analyze_source_url", return_value=extracted):
            payload = read_url_or_search("네이버뉴스 최신뉴스 3개", count=1)

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["mode"], "naver_latest")
        self.assertEqual(payload["articles"][0]["title"], "Latest Story")

    def test_format_read_url_or_search_formats_naver_latest(self) -> None:
        text = format_read_url_or_search(
            {
                "ok": True,
                "mode": "naver_latest",
                "retrieved_at": "2026-05-15T00:00:00+00:00",
                "source_url": "https://news.naver.com/main/list.naver?mode=LSD&mid=sec&sid1=001",
                "articles": [
                    {
                        "ok": True,
                        "title": "Latest Story",
                        "url": "https://n.news.naver.com/mnews/article/001/0001",
                        "fact_notes": [{"note": "Latest story summary."}],
                    }
                ],
            }
        )

        self.assertIn("mode: naver_latest", text)
        self.assertIn("1. Latest Story", text)
        self.assertIn("summary_1: Latest story summary.", text)

    def test_format_read_url_or_search_failure_includes_next_action(self) -> None:
        text = format_read_url_or_search(
            {
                "ok": False,
                "mode": "search",
                "failure_class": "search_parse_failed",
                "message": "none",
                "next_action_suggestion": "try_http_request_or_browser",
            }
        )

        self.assertIn("failure_class: search_parse_failed", text)
        self.assertIn("next_action_suggestion: try_http_request_or_browser", text)


if __name__ == "__main__":
    unittest.main()
