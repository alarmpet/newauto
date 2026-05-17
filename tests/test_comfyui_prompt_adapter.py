import unittest

from app.services.comfyui_prompt_adapter import build_prompt_placeholders, normalize_dual_prompt


class ComfyPromptAdapterTests(unittest.TestCase):
    def test_normalize_dual_prompt_accepts_plain_string(self) -> None:
        dual_prompt = normalize_dual_prompt("quiet editorial interior")
        self.assertEqual(dual_prompt["prompt_g"], "quiet editorial interior")
        self.assertEqual(dual_prompt["prompt_l"], "quiet editorial interior")
        self.assertEqual(dual_prompt["combined"], "quiet editorial interior")

    def test_build_prompt_placeholders_keeps_split_prompts(self) -> None:
        placeholders = build_prompt_placeholders(
            positive_prompt={
                "prompt_g": "central balance scale comparing server stack and country map",
                "prompt_l": "clean black outline, flat vector illustration",
                "combined": "central balance scale comparing server stack and country map, clean black outline, flat vector illustration",
            },
            negative_prompt="text, watermark",
        )
        self.assertEqual(placeholders["__POSITIVE_PROMPT_G__"], "central balance scale comparing server stack and country map")
        self.assertEqual(placeholders["__POSITIVE_PROMPT_L__"], "clean black outline, flat vector illustration")
        self.assertEqual(placeholders["__NEGATIVE_PROMPT_G__"], "text, watermark")
        self.assertEqual(placeholders["__NEGATIVE_PROMPT_L__"], "text, watermark")


if __name__ == "__main__":
    unittest.main()
