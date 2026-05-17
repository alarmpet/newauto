import unittest
from typing import cast

from app.services.prompt_quality import build_keyword_coverage, build_prompt_quality_report
from app.types import VisualBrief


class PromptQualityTests(unittest.TestCase):
    def test_essay_road_without_vehicle_ban_detected(self) -> None:
        brief: VisualBrief = {
            "mode": "symbolic_metaphor",
            "main_subject": "environment-led editorial scene",
            "action": "a quiet stone path with one signpost",
            "primary_prop": "single signpost",
            "secondary_prop": "",
            "scene": "quiet stone path",
            "emotion": "choosing direction",
            "must_show": ["single signpost", "quiet stone path"],
            "avoid": [],
            "rationale": "template=essay_editorial; domain=essay",
            "domain": "essay",
        }
        coverage = build_keyword_coverage(
            positive_prompt="quiet stone path with one signpost, cinematic editorial still",
            negative_prompt="text, logo, watermark",
            brief=brief,
        )
        self.assertIn("ESSAY_ROAD_WITHOUT_VEHICLE_BAN", cast(list[str], coverage["issue_codes"]))

    def test_literal_simile_ignored_detected(self) -> None:
        brief: VisualBrief = {
            "mode": "symbolic_metaphor",
            "main_subject": "environment-led editorial scene",
            "action": "a difficult effort",
            "primary_prop": "compass on a folded map",
            "secondary_prop": "",
            "scene": "empty room",
            "emotion": "it feels like running on sand",
            "must_show": ["person running on sand", "shallow footprints"],
            "avoid": ["car", "vehicle", "traffic"],
            "rationale": "template=essay_editorial; domain=essay",
            "domain": "essay",
            "literal_simile": "running on sand",
        }
        coverage = build_keyword_coverage(
            positive_prompt="compass on a folded map, cinematic editorial still",
            negative_prompt="text, logo, watermark, car, vehicle, traffic, truck, bus, parked car, driveway, garage, luxury house exterior, highway, intersection, tail lights",
            brief=brief,
        )
        self.assertIn("LITERAL_SIMILE_IGNORED", cast(list[str], coverage["issue_codes"]))

    def test_generic_symbol_without_allow_detected(self) -> None:
        brief: VisualBrief = {
            "mode": "symbolic_metaphor",
            "main_subject": "environment-led editorial scene",
            "action": "a choice represented by a compass",
            "primary_prop": "compass on a folded map",
            "secondary_prop": "",
            "scene": "quiet table",
            "emotion": "choosing direction",
            "must_show": ["compass on a folded map"],
            "avoid": [],
            "rationale": "template=essay_editorial; domain=essay",
            "domain": "essay",
        }
        coverage = build_keyword_coverage(
            positive_prompt="medium wide shot, compass on a folded map, 35mm lens, sharp focus",
            negative_prompt="text, logo, watermark, readable text, letters, car, vehicle, traffic, truck, bus, parked car, driveway, garage, luxury house exterior, highway, intersection, tail lights",
            brief=brief,
        )
        self.assertIn("GENERIC_SYMBOL_WITHOUT_ALLOW", cast(list[str], coverage["issue_codes"]))

    def test_book_text_and_closeup_risks_detected(self) -> None:
        brief: VisualBrief = {
            "mode": "symbolic_metaphor",
            "main_subject": "environment-led editorial scene",
            "action": "a hand only closeup holding a notebook",
            "primary_prop": "open notebook",
            "secondary_prop": "",
            "scene": "quiet desk",
            "emotion": "reflection",
            "must_show": ["open notebook"],
            "avoid": [],
            "rationale": "template=essay_editorial; domain=essay",
            "domain": "essay",
        }
        coverage = build_keyword_coverage(
            positive_prompt="extreme close-up, hand only closeup, open notebook, quiet desk",
            negative_prompt="text, logo, watermark",
            brief=brief,
        )
        issue_codes = cast(list[str], coverage["issue_codes"])
        self.assertIn("BOOK_TEXT_RISK", issue_codes)
        self.assertIn("CLOSEUP_RISK", issue_codes)
        self.assertIn("MISSING_FRAMING_SLOT", issue_codes)
        self.assertIn("MISSING_CAMERA_TECHNICAL_SLOT", issue_codes)

    def test_raw_korean_visual_target_detected(self) -> None:
        brief: VisualBrief = {
            "mode": "symbolic_metaphor",
            "main_subject": "environment-led editorial scene",
            "action": "마음이 흔들리는 느낌",
            "primary_prop": "조용한 방",
            "secondary_prop": "",
            "scene": "quiet room",
            "emotion": "reflection",
            "must_show": ["quiet room"],
            "avoid": [],
            "rationale": "template=essay_editorial; domain=essay",
            "domain": "essay",
        }
        coverage = build_keyword_coverage(
            positive_prompt="medium wide shot, quiet room, 35mm lens, sharp focus, natural color",
            negative_prompt="text, logo, watermark, readable text, letters, car, vehicle, traffic, truck, bus, parked car, driveway, garage, luxury house exterior, highway, intersection, tail lights",
            brief=brief,
        )
        self.assertIn("RAW_TEXT_VISUAL_TARGET", cast(list[str], coverage["issue_codes"]))

    def test_fallback_rate_above_20pct_flagged(self) -> None:
        prompts = [
            {
                "sentence_idx": 0,
                "template_key": "essay_editorial",
                "retry_count": 0,
                "visual_brief": {"primary_prop": "compass on a folded map"},
                "visual_plan": {"source": "fallback"},
                "keyword_coverage": {"issue_codes": []},
            },
            {
                "sentence_idx": 1,
                "template_key": "essay_editorial",
                "retry_count": 0,
                "visual_brief": {"primary_prop": "single signpost"},
                "visual_plan": {"source": "llm"},
                "keyword_coverage": {"issue_codes": []},
            },
        ]
        report = build_prompt_quality_report(prompts)
        self.assertIn("FALLBACK_RATE_HIGH", cast(list[str], report["project_issue_codes"]))

    def test_project_report_counts_new_issue_codes(self) -> None:
        report = build_prompt_quality_report(
            [
                {
                    "sentence_idx": 0,
                    "template_key": "essay_editorial",
                    "retry_count": 0,
                    "visual_brief": {"primary_prop": "compass on a folded map"},
                    "visual_plan": {"source": "llm"},
                    "keyword_coverage": {
                        "issue_codes": [
                            "GENERIC_SYMBOL_WITHOUT_ALLOW",
                            "BOOK_TEXT_RISK",
                            "CLOSEUP_RISK",
                            "RAW_TEXT_VISUAL_TARGET",
                        ]
                    },
                }
            ]
        )
        issue_codes = cast(list[str], report["project_issue_codes"])
        self.assertIn("GENERIC_SYMBOL_WITHOUT_ALLOW", issue_codes)
        self.assertIn("BOOK_TEXT_RISK", issue_codes)
        self.assertIn("CLOSEUP_RISK", issue_codes)
        self.assertIn("RAW_TEXT_VISUAL_TARGET", issue_codes)

    def test_simple_diagram_style_collision_detected(self) -> None:
        brief: VisualBrief = {
            "mode": "symbolic_metaphor",
            "main_subject": "simple centered explainer icon composition",
            "action": "one central icon with supporting symbols",
            "primary_prop": "central AI brain icon",
            "secondary_prop": "small tool icons connected by thin arrows",
            "scene": "plain warm background with generous empty space",
            "emotion": "clear and direct",
            "must_show": ["central AI brain icon"],
            "avoid": [],
            "rationale": "template=essay_editorial; domain=essay; style_preset=simple_diagram",
            "domain": "essay",
        }
        coverage = build_keyword_coverage(
            positive_prompt="wide centered explainer diagram shot, central AI brain icon, cinematic editorial photography, 35mm lens, sharp focus",
            negative_prompt="text, logo, watermark",
            brief=brief,
        )
        issue_codes = cast(list[str], coverage["issue_codes"])
        self.assertIn("DIAGRAM_STYLE_COLLISION", issue_codes)
        self.assertIn("DIAGRAM_TEXT_CONTROL_MISSING", issue_codes)

    def test_ev_battery_core_visual_missing_detected(self) -> None:
        brief: VisualBrief = {
            "mode": "symbolic_metaphor",
            "main_subject": "generic strategy scene",
            "action": "abstract competition symbols",
            "primary_prop": "glowing trophy",
            "secondary_prop": "city skyline",
            "scene": "generic editorial background",
            "emotion": "competition",
            "must_show": ["market competition symbol"],
            "avoid": [],
            "rationale": "template=ev_battery_explainer; domain=ev_battery",
            "domain": "ev_battery",
        }
        coverage = build_keyword_coverage(
            positive_prompt="generic trophy and city skyline, cinematic editorial still",
            negative_prompt="text, logo, watermark",
            brief=brief,
        )
        self.assertIn("EV_BATTERY_CORE_VISUAL_MISSING", cast(list[str], coverage["issue_codes"]))

    def test_ev_battery_stickfigure_style_blocked(self) -> None:
        brief: VisualBrief = {
            "mode": "symbolic_metaphor",
            "main_subject": "battery explainer",
            "action": "compare LFP and NCM battery cells",
            "primary_prop": "LFP battery cell",
            "secondary_prop": "NCM battery cell",
            "scene": "clean technical explainer",
            "emotion": "clear",
            "must_show": ["LFP battery cell", "NCM battery cell"],
            "avoid": [],
            "rationale": "template=ev_battery_explainer; domain=ev_battery",
            "domain": "ev_battery",
        }
        coverage = build_keyword_coverage(
            positive_prompt="stick figure presenter comparing LFP battery cell and NCM battery cell",
            negative_prompt="text, logo, watermark",
            brief=brief,
        )
        self.assertIn("EV_BATTERY_STICKFIGURE_STYLE_BLOCKED", cast(list[str], coverage["issue_codes"]))

    def test_project_report_counts_ev_battery_issue_codes(self) -> None:
        report = build_prompt_quality_report(
            [
                {
                    "sentence_idx": 0,
                    "template_key": "ev_battery_explainer",
                    "retry_count": 0,
                    "visual_brief": {"primary_prop": "market competition symbol"},
                    "visual_plan": {"source": "llm"},
                    "keyword_coverage": {
                        "issue_codes": [
                            "EV_BATTERY_CORE_VISUAL_MISSING",
                            "EV_BATTERY_STICKFIGURE_STYLE_BLOCKED",
                        ]
                    },
                }
            ]
        )
        self.assertEqual(report["ev_battery_issue_count"], 2)
        self.assertIn("EV_BATTERY_PROMPT_QUALITY_FAILED", cast(list[str], report["project_issue_codes"]))


if __name__ == "__main__":
    unittest.main()
