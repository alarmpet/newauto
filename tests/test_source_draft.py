import unittest
from typing import cast

from fastapi import HTTPException

from app.services.source_draft import (
    _build_prompt,
    _risk_threshold_for_mode,
    sanitize_source_draft_script,
)
from app.types import ProjectRecord


def _project_payload() -> dict[str, object]:
    return {
        "source_draft_sources": [{
            "id": "src1",
            "url": "https://example.com/one",
            "final_url": "https://example.com/one",
            "title": "Article 1",
            "domain": "example.com",
            "author": "",
            "published_at": "",
            "language": "ko",
            "excerpt": "First article summary.",
            "fetched_at": "2026-04-26T00:00:00+00:00",
            "word_count": 100,
        }],
        "source_draft_fact_notes": [{"source_id": "src1", "note": "Important fact one"}],
        "source_draft_script": "Previous draft",
        "source_draft_warnings": [],
    }


class SourceDraftPromptTests(unittest.TestCase):
    def test_cleanup_removes_headings_labels_and_directions(self) -> None:
        script = """# Title
**내레이션:** 첫 문장입니다.
(차분하게)
- 장면: 화면 설명
[효과음]
둘째 문장입니다.
"""
        cleaned = sanitize_source_draft_script(script)
        self.assertEqual(cleaned, "Title\n첫 문장입니다.\n화면 설명\n둘째 문장입니다.")

    def test_generate_with_hook_mode_uses_hook_template(self) -> None:
        prompt = _build_prompt(
            cast(ProjectRecord, _project_payload()),
            tone="documentary",
            target_minutes=3,
            language="ko",
            mode="hook",
        )
        self.assertIn("grab attention", prompt)

    def test_auto_target_uses_natural_length_instruction(self) -> None:
        prompt = _build_prompt(
            cast(ProjectRecord, _project_payload()),
            tone="documentary",
            target_minutes=None,
            language="ko",
            mode="",
        )
        self.assertIn("Target length: auto", prompt)
        self.assertIn("do not pad, compress, or force a runtime", prompt)

    def test_lesson_mode_has_stricter_risk_threshold(self) -> None:
        self.assertLess(_risk_threshold_for_mode("lesson"), _risk_threshold_for_mode("point"))

    def test_empty_fact_notes_blocked(self) -> None:
        payload = _project_payload()
        payload["source_draft_fact_notes"] = []
        with self.assertRaises(HTTPException):
            _build_prompt(
                cast(ProjectRecord, payload),
                tone="documentary",
                target_minutes=3,
                language="ko",
                mode="story",
            )
