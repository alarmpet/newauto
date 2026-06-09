from __future__ import annotations

import unittest

from app.services.web_search import WebSearchResponse
from app.services.web_search import WebSearchResult
from app.services.web_search import format_search_response
from app.services.web_search import looks_like_news_query
from app.services.web_search import normalize_duckduckgo_href
from app.services.web_search import parse_duckduckgo_html
from app.services.web_search import parse_google_news_rss


class WebSearchTests(unittest.TestCase):
    def test_parse_duckduckgo_html_extracts_title_url_and_snippet(self) -> None:
        page = """
        <html>
          <a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fnews.naver.com%2Farticle%2F001">
            Naver &amp; News <b>Headline</b>
          </a>
          <a class="result__snippet">Snippet &amp; details <b>here</b>.</a>
        </html>
        """

        results = parse_duckduckgo_html(page, limit=3)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Naver & News Headline")
        self.assertEqual(results[0].url, "https://news.naver.com/article/001")
        self.assertEqual(results[0].snippet, "Snippet & details here.")

    def test_parse_duckduckgo_lite_extracts_title_url_and_snippet(self) -> None:
        page = """
        <html>
          <a rel="nofollow" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fblog.google%2Fai%2F" class='result-link'>
            Official Google AI news
          </a>
          <td class='result-snippet'>Latest updates from Google.</td>
        </html>
        """

        results = parse_duckduckgo_html(page, limit=3)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Official Google AI news")
        self.assertEqual(results[0].url, "https://blog.google/ai/")
        self.assertEqual(results[0].snippet, "Latest updates from Google.")

    def test_parse_duckduckgo_html_dedupes_urls(self) -> None:
        page = """
        <a class="result__a" href="https://example.com/a">First</a>
        <a class="result__snippet">one</a>
        <a class="result__a" href="https://example.com/a">Duplicate</a>
        <a class="result__snippet">two</a>
        <a class="result__a" href="https://example.com/b">Second</a>
        <a class="result__snippet">three</a>
        """

        results = parse_duckduckgo_html(page, limit=10)

        self.assertEqual([item.url for item in results], ["https://example.com/a", "https://example.com/b"])

    def test_normalize_duckduckgo_href_decodes_uddg(self) -> None:
        href = "https://duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fhello%3Fa%3D1"

        self.assertEqual(normalize_duckduckgo_href(href), "https://example.com/hello?a=1")

    def test_parse_google_news_rss_extracts_items(self) -> None:
        feed = b"""
        <rss><channel>
          <item>
            <title>Google AI update - Example</title>
            <link>https://news.google.com/rss/articles/example</link>
            <description>&lt;a href=&quot;https://example.com&quot;&gt;source&lt;/a&gt; Summary text.</description>
          </item>
        </channel></rss>
        """

        results = parse_google_news_rss(feed, limit=3)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Google AI update - Example")
        self.assertEqual(results[0].url, "https://news.google.com/rss/articles/example")
        self.assertIn("Summary text.", results[0].snippet)

    def test_news_query_detection_accepts_korean_and_english(self) -> None:
        self.assertTrue(looks_like_news_query("Google latest AI news"))
        self.assertTrue(looks_like_news_query("구글 최신 뉴스"))
        self.assertFalse(looks_like_news_query("python list comprehension"))

    def test_format_search_response_includes_failure_class(self) -> None:
        response = WebSearchResponse(
            ok=False,
            query="",
            source_method="duckduckgo_html",
            retrieved_at="2026-05-15T00:00:00+00:00",
            results=[],
            failure_class="empty_query",
            message="Search query is empty.",
            next_action_suggestion="provide_query",
        )

        text = format_search_response(response)

        self.assertIn("failure_class: empty_query", text)
        self.assertIn("next_action_suggestion: provide_query", text)

    def test_format_search_response_lists_results(self) -> None:
        response = WebSearchResponse(
            ok=True,
            query="test",
            source_method="duckduckgo_html",
            retrieved_at="2026-05-15T00:00:00+00:00",
            search_url="https://duckduckgo.com/html/?q=test",
            results=[WebSearchResult(title="Title", url="https://example.com", snippet="Snippet")],
        )

        text = format_search_response(response)

        self.assertIn("1. Title", text)
        self.assertIn("url: https://example.com", text)
        self.assertIn("snippet: Snippet", text)


if __name__ == "__main__":
    unittest.main()
