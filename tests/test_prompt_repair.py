import unittest

from app.services.prompt_repair import repair_prompts
from app.types import VisualBrief


class PromptRepairTests(unittest.TestCase):
    def test_repair_prompts_skips_empty_issue_codes(self) -> None:
        brief: VisualBrief = {
            "mode": "keyword_image",
            "main_subject": "leaf film",
            "action": "transforming",
            "primary_prop": "transparent film",
            "secondary_prop": "soil",
            "scene": "farm field",
            "emotion": "clear",
            "must_show": ["leaf pile", "transparent film"],
            "avoid": [],
            "rationale": "manual_article_editorial",
        }
        repaired = repair_prompts(
            positive_prompt="fallen leaves become transparent mulch film",
            negative_prompt="text, watermark",
            brief=brief,
            issue_codes=[],
            attempt=1,
        )
        self.assertFalse(repaired["should_retry"])
        self.assertEqual(repaired["repair_reason"], "empty_issue_codes_skip")
        self.assertNotIn("clear visual metaphor", repaired["repaired_positive_prompt"])

    def test_repair_prompts_reinforces_must_show_for_raw_text_target(self) -> None:
        brief: VisualBrief = {
            "mode": "keyword_image",
            "main_subject": "simple centered explainer icon composition",
            "action": "generic diagram",
            "primary_prop": "central icon",
            "secondary_prop": "",
            "scene": "plain background",
            "emotion": "clear and direct",
            "must_show": ["server stack", "power meter"],
            "avoid": [],
            "rationale": "style_preset=simple_diagram",
        }
        repaired = repair_prompts(
            positive_prompt="generic diagram",
            negative_prompt="text, watermark",
            brief=brief,
            issue_codes=["RAW_TEXT_VISUAL_TARGET"],
            attempt=1,
        )
        self.assertTrue(repaired["should_retry"])
        self.assertIn("server stack", repaired["repaired_positive_prompt"])
        self.assertIn("server stack", repaired["repaired_prompt_g"])
        self.assertEqual(repaired["repaired_prompt_l"], "generic diagram")
        self.assertIn("must_show_reinforced", repaired["repair_reason"])

    def test_repair_prompts_adds_negative_blocks_for_diagram_collision(self) -> None:
        brief: VisualBrief = {
            "mode": "keyword_image",
            "main_subject": "balance scale",
            "action": "comparison layout",
            "primary_prop": "balance scale",
            "secondary_prop": "",
            "scene": "plain background",
            "emotion": "neutral",
            "must_show": ["balance scale"],
            "avoid": [],
            "rationale": "style_preset=simple_diagram",
        }
        repaired = repair_prompts(
            positive_prompt={
                "prompt_g": "central balance scale comparison",
                "prompt_l": "cinematic scene",
                "combined": "central balance scale comparison, cinematic scene",
            },
            negative_prompt="text",
            brief=brief,
            issue_codes=["DIAGRAM_STYLE_COLLISION"],
            attempt=1,
        )
        self.assertIn("simple flat explainer illustration", repaired["repaired_positive_prompt"])
        self.assertEqual(repaired["repaired_prompt_g"], "central balance scale comparison")
        self.assertIn("clean black outline", repaired["repaired_prompt_l"])
        self.assertIn("photorealistic", repaired["repaired_negative_prompt"])

    def test_repair_prompts_splits_framing_and_camera_between_g_and_l(self) -> None:
        brief: VisualBrief = {
            "mode": "keyword_image",
            "main_subject": "person at desk",
            "action": "reading and thinking",
            "primary_prop": "notebook",
            "secondary_prop": "",
            "scene": "quiet room",
            "emotion": "focused",
            "must_show": ["person at desk"],
            "avoid": [],
            "rationale": "essay_editorial",
        }
        repaired = repair_prompts(
            positive_prompt={
                "prompt_g": "person at desk with notebook",
                "prompt_l": "soft natural lighting",
                "combined": "person at desk with notebook, soft natural lighting",
            },
            negative_prompt="text",
            brief=brief,
            issue_codes=["MISSING_FRAMING_SLOT", "MISSING_CAMERA_TECHNICAL_SLOT"],
            attempt=1,
        )
        self.assertIn("medium wide shot", repaired["repaired_prompt_g"])
        self.assertIn("35mm lens", repaired["repaired_prompt_l"])
        self.assertNotIn("35mm lens", repaired["repaired_prompt_g"])

    def test_repair_prompts_uses_strictifier_for_borderline_diagram(self) -> None:
        brief: VisualBrief = {
            "mode": "keyword_image",
            "main_subject": "news explainer",
            "action": "generic dashboard",
            "primary_prop": "comment panel",
            "secondary_prop": "reaction counters",
            "scene": "plain background",
            "emotion": "clear",
            "must_show": ["comment panel", "reaction counters"],
            "avoid": [],
            "rationale": "style_preset=simple_diagram",
            "domain": "news_explainer",
            "composition_template": "SpikeDetection",
        }
        repaired = repair_prompts(
            positive_prompt={
                "prompt_g": "wide centered explainer diagram shot, simple centered explainer icon composition",
                "prompt_l": "simple flat 2d explainer diagram",
                "combined": "wide centered explainer diagram shot, simple centered explainer icon composition",
            },
            negative_prompt="text",
            brief=brief,
            issue_codes=["BORDERLINE_CANDIDATE"],
            attempt=1,
        )
        self.assertTrue(repaired["should_retry"])
        self.assertIn("giant reaction counters", repaired["repaired_prompt_g"])
        self.assertIn("dense analytics dashboard", repaired["repaired_negative_prompt"])
        self.assertEqual(repaired["repair_reason"], "strict_borderline_retry")


if __name__ == "__main__":
    unittest.main()
