import unittest

from app.services.comfyui_pipeline import _select_best_candidate


class ComfyUiPipelineTests(unittest.TestCase):
    def test_ev_battery_candidate_below_strong_threshold_requires_retry(self) -> None:
        candidate = {
            "path": "scene.png",
            "prompt": "battery cell",
            "prompt_id": "pid",
            "candidate_index": 1,
            "candidate_total": 1,
            "candidate_score": 0.68,
            "candidate_score_version": "candidate_score_v2:ev_battery_v1",
        }

        decision = _select_best_candidate([candidate], fallback=candidate)

        self.assertTrue(decision["retry_recommended"])
        self.assertEqual(decision["retry_reason"], "strict_domain_low_candidate_score")

    def test_ev_battery_semantic_mismatch_requires_retry_even_with_high_score(self) -> None:
        candidate = {
            "path": "scene.png",
            "prompt": "battery cell",
            "prompt_id": "pid",
            "candidate_index": 1,
            "candidate_total": 1,
            "candidate_score": 0.82,
            "candidate_score_version": "candidate_score_v2:ev_battery_v1",
            "vision_qa_issue_codes": ["IMAGE_SEMANTIC_MATCH_TOO_LOW"],
        }

        decision = _select_best_candidate([candidate], fallback=candidate)

        self.assertTrue(decision["retry_recommended"])
        self.assertEqual(decision["retry_reason"], "strict_domain_semantic_mismatch")


if __name__ == "__main__":
    unittest.main()
