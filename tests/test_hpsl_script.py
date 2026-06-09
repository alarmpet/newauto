import unittest
from typing import cast

from app.services.hpsl_script import _build_prompt, _fallback_payload_from_fact_notes, _target_sentence_count
from app.types import ProjectRecord


def _project_with_notes(count: int) -> ProjectRecord:
    return cast(
        ProjectRecord,
        {
            "id": "hpsl-test",
            "title": "HPSL test",
            "source_draft_sources": [
                {
                    "id": "src1",
                    "url": "https://example.com",
                    "final_url": "https://example.com",
                    "title": "Example",
                    "domain": "example.com",
                    "author": "",
                    "published_at": "",
                    "language": "ko",
                    "excerpt": " ".join(f"fact {index}" for index in range(count)),
                    "fetched_at": "",
                    "word_count": 100,
                }
            ],
            "source_draft_fact_notes": [
                {"source_id": "src1", "note": f"fact note {index + 1}"}
                for index in range(count)
            ],
        },
    )


class HpslScriptTests(unittest.TestCase):
    def test_one_minute_sentence_target_follows_fact_count(self) -> None:
        self.assertEqual(_target_sentence_count(_project_with_notes(3), 1), 3)
        self.assertEqual(_target_sentence_count(_project_with_notes(5), 1), 5)
        self.assertEqual(_target_sentence_count(_project_with_notes(12), 1), 8)

    def test_auto_sentence_target_follows_source_density(self) -> None:
        self.assertEqual(_target_sentence_count(_project_with_notes(3), None), 3)
        self.assertEqual(_target_sentence_count(_project_with_notes(14), None), 14)

    def test_prompt_does_not_seed_fixed_six_scene_shape(self) -> None:
        prompt = _build_prompt(_project_with_notes(9), tone="설명형", target_minutes=None, language="ko")

        self.assertIn("Do not default to six scenes", prompt)
        self.assertIn('"points":[]', prompt)
        self.assertNotIn('"points":["","",""]', prompt)

    def test_fallback_payload_is_not_fixed_to_six_sentences(self) -> None:
        short_payload = _fallback_payload_from_fact_notes(_project_with_notes(5), tone="설명형", target_minutes=1)
        rich_payload = _fallback_payload_from_fact_notes(_project_with_notes(9), tone="설명형", target_minutes=1)

        self.assertEqual(len(short_payload["sentences"]), 5)
        self.assertEqual(len(rich_payload["sentences"]), 8)


if __name__ == "__main__":
    unittest.main()
