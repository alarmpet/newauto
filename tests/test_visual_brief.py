import unittest

from app.services.visual_brief import build_visual_brief


class VisualBriefTests(unittest.TestCase):
    def test_build_visual_brief_keeps_must_show(self) -> None:
        brief = build_visual_brief(
            text="작은 계획 하나가 마음의 소음을 천천히 줄이기 시작한다.",
            visual_tokens=["holding a large checklist with three bold check marks"],
            template_key="default",
        )

        self.assertEqual(brief["main_subject"], "editorial symbolic concept scene")
        self.assertEqual(brief["visual_mode"], "symbolic_concept")
        self.assertEqual(brief["primary_prop"], "holding a large checklist with three bold check marks")
        self.assertGreaterEqual(len(brief["must_show"]), 1)
        self.assertIn("text", brief["avoid"])

    def test_build_visual_brief_uses_tech_domain_defaults(self) -> None:
        brief = build_visual_brief(
            text="Obscura는 오픈소스 헤드리스 브라우저 자동화 도구입니다.",
            visual_tokens=["browser window with terminal panel and automation cursor"],
            template_key="default",
            domain="tech",
        )

        self.assertEqual(brief["mode"], "keyword_image")
        self.assertEqual(brief["scene"], "clean software workspace")
        self.assertEqual(brief["main_subject"], "technology interface scene")
        self.assertEqual(brief["domain"], "tech")
        self.assertIn("running fast", brief["avoid"])

    def test_generic_fallback_does_not_use_checklist(self) -> None:
        brief = build_visual_brief(
            text="A quiet sentence without a direct visual token.",
            visual_tokens=[],
            template_key="default",
        )

        self.assertNotIn("checklist", brief["primary_prop"].lower())
        self.assertNotIn("single everyday object", brief["primary_prop"].lower())
        self.assertEqual(brief["scene"], "grounded editorial environment")


if __name__ == "__main__":
    unittest.main()
