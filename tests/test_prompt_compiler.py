import unittest

from app.services.prompt_compiler import (
    check_prompt_compliance,
    compile_negative_prompt,
    compile_positive_prompt,
    compile_positive_prompt_text,
    find_blocked_prompt_phrases,
)
from app.types import VisualBrief


def _brief() -> VisualBrief:
    return {
        "mode": "keyword_image",
        "main_subject": "single centered stick figure engineer",
        "action": "presenting the primary prop like a clear explainer diagram",
        "primary_prop": "browser window with terminal panel and automation cursor",
        "secondary_prop": "structured data table flowing out of a browser window",
        "scene": "clean software workspace",
        "emotion": "calm and analytical",
        "must_show": [
            "browser window with terminal panel and automation cursor",
            "structured data table flowing out of a browser window",
        ],
        "avoid": ["text", "logo", "crowd", "running fast"],
        "rationale": "template=default; domain=tech",
    }


class PromptCompilerTests(unittest.TestCase):
    def test_compile_positive_prompt_keeps_primary_prop_readable(self) -> None:
        brief = _brief()
        dual_prompt = compile_positive_prompt(
            shot="medium action shot, full body view",
            style_hint="high-detail technology documentary illustration",
            brief=brief,
        )
        prompt = dual_prompt["combined"]
        self.assertNotIn("Flipchartvisu", prompt)
        self.assertNotIn("Stick figure", prompt)
        self.assertIn("cinematic technology documentary still", prompt)
        self.assertIn("browser window with terminal panel and automation cursor clearly visible", prompt)
        self.assertNotIn("large large", prompt)
        self.assertNotEqual(dual_prompt["prompt_g"], "")
        self.assertNotEqual(dual_prompt["prompt_l"], "")

    def test_compile_negative_prompt_includes_avoid_items(self) -> None:
        negative = compile_negative_prompt(
            template_negative="realistic landscape",
            brief=_brief(),
        )
        self.assertIn("duplicate screens", negative)
        self.assertIn("running fast", negative)

    def test_check_prompt_compliance_returns_empty_when_all_must_show_present(self) -> None:
        brief = _brief()
        prompt = compile_positive_prompt_text(
            shot="medium action shot, full body view",
            style_hint="high-detail technology documentary illustration",
            brief=brief,
        )
        self.assertEqual(check_prompt_compliance(prompt, brief), [])

    def test_check_prompt_compliance_flags_blocked_phrases(self) -> None:
        brief = _brief()
        issues = check_prompt_compliance("running fast, browser window with terminal panel and automation cursor", brief)
        self.assertIn("BLOCKLIST:running fast", issues)
        self.assertEqual(find_blocked_prompt_phrases("under heavy rain"), ["under heavy rain"])

    def test_compiler_adds_global_avoid_to_essay_negative(self) -> None:
        brief: VisualBrief = {
            "mode": "symbolic_metaphor",
            "main_subject": "environment-led editorial scene",
            "action": "a quiet stone path with a signpost",
            "primary_prop": "single signpost",
            "secondary_prop": "blurred crowd backdrop",
            "scene": "quiet stone path at dawn",
            "emotion": "a choice about direction",
            "must_show": ["single signpost", "quiet stone path"],
            "avoid": [],
            "rationale": "template=essay_editorial; domain=essay",
            "domain": "essay",
        }
        negative = compile_negative_prompt(template_negative="blurry", brief=brief)
        self.assertIn("car", negative)
        self.assertIn("vehicle", negative)
        self.assertIn("traffic", negative)

    def test_default_prompt_skips_stick_figure_for_news_explainer_domain(self) -> None:
        brief: VisualBrief = {
            "mode": "keyword_image",
            "main_subject": "simple centered explainer icon composition",
            "action": "branching institutional strategy shown as two clear paths",
            "primary_prop": "institution split diagram",
            "secondary_prop": "future roadmap marker",
            "scene": "plain warm background with generous empty space",
            "emotion": "institutional views are diverging",
            "must_show": ["institution split diagram", "future roadmap marker"],
            "avoid": [],
            "rationale": "template=default; domain=news_explainer",
            "domain": "news_explainer",
        }
        dual_prompt = compile_positive_prompt(
            shot="wide centered explainer shot",
            style_hint="clean minimal explainer graphic",
            brief=brief,
        )
        prompt = dual_prompt["combined"]
        self.assertNotIn("Flipchartvisu", prompt)
        self.assertNotIn("Stick figure", prompt)
        self.assertIn("institution split diagram clearly visible", prompt)

    def test_compiler_skips_allowed_object_from_global_avoid(self) -> None:
        brief: VisualBrief = {
            "mode": "symbolic_metaphor",
            "main_subject": "environment-led editorial scene",
            "action": "an empty road as a deliberate car metaphor",
            "primary_prop": "vintage car",
            "secondary_prop": "",
            "scene": "empty road at dawn",
            "emotion": "memory and travel",
            "must_show": ["vintage car"],
            "avoid": [],
            "rationale": "template=essay_editorial; domain=essay",
            "domain": "essay",
            "allow_objects": ["car"],
        }
        negative = compile_negative_prompt(template_negative="blurry", brief=brief)
        self.assertNotIn(", car,", f", {negative},")
        self.assertIn("vehicle", negative)

    def test_simile_priority_places_simile_first(self) -> None:
        brief: VisualBrief = {
            "mode": "symbolic_metaphor",
            "main_subject": "environment-led editorial scene",
            "action": "soft sand resisting each step",
            "primary_prop": "person running on sand",
            "secondary_prop": "shallow footprints",
            "scene": "windy sand field",
            "emotion": "progress feels heavy",
            "must_show": ["person running on sand", "shallow footprints"],
            "avoid": ["car", "vehicle", "traffic"],
            "rationale": "template=essay_editorial; domain=essay",
            "domain": "essay",
            "visual_priority": "literal_simile",
            "literal_simile": "running on sand",
        }
        prompt = compile_positive_prompt_text(
            shot="medium wide editorial shot",
            style_hint="cinematic editorial illustration",
            brief=brief,
        )
        self.assertTrue(prompt.startswith("running on sand,"))
        self.assertIn("35mm lens", prompt)
        self.assertIn("sharp focus", prompt)
        self.assertIn("no readable text", prompt)

    def test_essay_positive_prompt_filters_raw_korean_visual_text(self) -> None:
        brief: VisualBrief = {
            "mode": "symbolic_metaphor",
            "main_subject": "environment-led editorial scene",
            "action": "마음이 흔들리는 느낌",
            "primary_prop": "조용한 방",
            "secondary_prop": "",
            "scene": "생각이 복잡한 아침",
            "emotion": "한글 감정 문장",
            "must_show": ["single everyday object"],
            "avoid": [],
            "rationale": "template=essay_editorial; domain=essay",
            "domain": "essay",
        }
        prompt = compile_positive_prompt_text(
            shot="medium wide editorial shot",
            style_hint="cinematic editorial illustration",
            brief=brief,
        )
        self.assertNotIn("마음", prompt)
        self.assertNotIn("조용한", prompt)
        self.assertIn("concrete visual subject from the sentence", prompt)
        self.assertIn("grounded editorial environment", prompt)

    def test_food_trend_prompt_uses_product_focused_language(self) -> None:
        brief: VisualBrief = {
            "mode": "keyword_image",
            "main_subject": "clean editorial food trend scene",
            "action": "purple yam ingredient becomes a vivid purple dessert product",
            "primary_prop": "purple yam with cut violet flesh",
            "secondary_prop": "ube cream dessert and purple whipped topping",
            "scene": "retail shelf or cafe display setting",
            "emotion": "ube is becoming the center of a food trend",
            "must_show": ["purple yam with cut violet flesh", "ube cream dessert and purple whipped topping"],
            "avoid": ["empty living room"],
            "rationale": "template=food_trend_editorial; domain=food_trend",
            "domain": "food_trend",
            "composition_template": "IngredientHero",
        }
        dual_prompt = compile_positive_prompt(
            shot="medium wide editorial food shot",
            style_hint="clean editorial food illustration",
            brief=brief,
        )
        negative = compile_negative_prompt(template_negative="text, logo", brief=brief)
        self.assertIn("purple yam with cut violet flesh clearly visible", dual_prompt["prompt_g"])
        self.assertIn("purple ube color accent", dual_prompt["prompt_l"])
        self.assertIn("empty living room", negative)
        self.assertIn("gear mechanism", negative)

    def test_simple_diagram_prompt_avoids_camera_language(self) -> None:
        brief: VisualBrief = {
            "mode": "symbolic_metaphor",
            "main_subject": "simple centered explainer icon composition",
            "action": "one central AI icon distributing work to simple supporting icons",
            "primary_prop": "central AI brain icon",
            "secondary_prop": "small tool icons connected by thin arrows",
            "scene": "plain warm background with generous empty space",
            "emotion": "clear and direct",
            "must_show": ["central AI brain icon", "small tool icons connected by thin arrows"],
            "avoid": [],
            "rationale": "template=essay_editorial; domain=essay; style_preset=simple_diagram",
            "domain": "essay",
            "primary_keywords": ["ai", "schedule", "payment"],
        }
        dual_prompt = compile_positive_prompt(
            shot="wide centered explainer diagram shot",
            style_hint="simple flat 2d explainer diagram, minimal editorial cartoon",
            brief=brief,
        )
        prompt = dual_prompt["combined"]
        negative = compile_negative_prompt(
            template_negative="text, logo",
            brief=brief,
        )
        self.assertIn("simple flat explainer illustration", prompt)
        self.assertIn("large readable icons", prompt)
        self.assertNotIn("35mm lens", prompt)
        self.assertNotIn("cinematic editorial photography", prompt)
        self.assertIn("photorealistic", negative)
        self.assertIn("readable text", negative)
        self.assertIn("simple centered explainer icon composition", dual_prompt["prompt_g"])
        self.assertIn("clean black outline", dual_prompt["prompt_l"])

    def test_editorial_symbolic_prompt_uses_scene_anchor_not_diagram_language(self) -> None:
        brief: VisualBrief = {
            "mode": "symbolic_metaphor",
            "main_subject": "policy conflict editorial scene",
            "action": "a red stop barrier blocks an AI model from spreading",
            "primary_prop": "glowing AI network sphere",
            "secondary_prop": "red stop barrier",
            "scene": "White House security gate",
            "emotion": "government intervention slows model expansion",
            "must_show": ["White House security gate", "glowing AI network sphere"],
            "avoid": [],
            "rationale": "template=editorial_symbolic; domain=ai_policy_conflict; style_preset=editorial_symbolic",
            "domain": "ai_policy_conflict",
            "scene_anchor": "White House security gate",
            "hero_subject": "glowing AI network sphere",
            "symbolic_marker": "red stop barrier",
            "composition_template": "AccessRestriction",
        }
        dual_prompt = compile_positive_prompt(
            shot="medium wide editorial symbolic shot",
            style_hint="editorial symbolic high-quality illustration",
            brief=brief,
        )
        negative = compile_negative_prompt(template_negative="logo", brief=brief)

        self.assertIn("White House security gate", dual_prompt["prompt_g"])
        self.assertIn("glowing AI network sphere clearly visible", dual_prompt["prompt_g"])
        self.assertIn("premium editorial illustration", dual_prompt["prompt_l"])
        self.assertNotIn("simple flat explainer illustration", dual_prompt["combined"])
        self.assertIn("flowchart", negative)
        self.assertIn("flat icon only", negative)

    def test_agriculture_environment_prompt_uses_editorial_science_language(self) -> None:
        brief: VisualBrief = {
            "mode": "keyword_image",
            "main_subject": "environmental science editorial scene",
            "action": "fallen leaves transform into translucent mulch film over soil",
            "primary_prop": "thin translucent mulch film sheet",
            "secondary_prop": "fallen leaves and protected crop row",
            "scene": "farm field with dark moist soil",
            "emotion": "waste becomes useful material",
            "must_show": ["thin translucent mulch film sheet", "fallen leaves"],
            "avoid": ["hay bales"],
            "rationale": "template=environmental_science_editorial; domain=agriculture_environment",
            "domain": "agriculture_environment",
            "composition_template": "WasteToMaterial",
        }
        dual_prompt = compile_positive_prompt(
            shot="medium wide editorial documentary shot",
            style_hint="environmental science editorial still",
            brief=brief,
        )
        negative = compile_negative_prompt(template_negative="text, logo", brief=brief)
        self.assertIn("thin translucent mulch film sheet clearly visible", dual_prompt["prompt_g"])
        self.assertIn("editorial documentary photography", dual_prompt["prompt_l"])
        self.assertIn("soil texture", dual_prompt["prompt_l"])
        self.assertIn("abstract dashboard", negative)
        self.assertIn("circuit diagram", negative)
        self.assertIn("hay bales", negative)


if __name__ == "__main__":
    unittest.main()
