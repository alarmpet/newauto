import unittest

from app.services.image_prompt import Z_IMAGE_DEFAULT_NEGATIVE_PROMPT, build_z_image_prompt


class ZImagePromptTests(unittest.TestCase):
    def test_keeps_korean_sentence_verbatim(self) -> None:
        sentence = "젠슨 황이 트럼프 대통령 요청으로 방중 경제사절단에 합류했다."
        prompt = build_z_image_prompt(sentence)
        self.assertIn(sentence, prompt.positive)
        self.assertEqual(prompt.negative, Z_IMAGE_DEFAULT_NEGATIVE_PROMPT)

    def test_adds_visual_brief_hints_without_translation(self) -> None:
        prompt = build_z_image_prompt(
            "반도체 업계가 갑작스러운 일정 변경에 술렁였다.",
            visual_brief={
                "main_subject": "공항 활주로의 전용기",
                "action": "CEO가 급히 탑승하는 장면",
                "primary_prop": "",
                "secondary_prop": "",
                "scene": "알래스카 중간 기착지",
                "emotion": "긴박함",
                "must_show": ["엔비디아 로고 없는 반도체 상징"],
                "avoid": [],
                "rationale": "",
            },
        )
        self.assertIn("공항 활주로의 전용기", prompt.positive)
        self.assertIn("알래스카 중간 기착지", prompt.positive)

    def test_uses_negative_override(self) -> None:
        prompt = build_z_image_prompt("AI 데이터센터 전력 병목을 설명한다.", negative_prompt_override="글자 깨짐, 로고")
        self.assertEqual(prompt.negative, "글자 깨짐, 로고")


if __name__ == "__main__":
    unittest.main()
