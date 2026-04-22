from pathlib import Path
import unittest

from app.config import VOICE_PRESETS, VOICE_PRESET_LABELS, VOICE_SAMPLE_TEXT
from scripts.generate_voice_samples import build_parser


class TtsPresetTests(unittest.TestCase):
    def test_new_male_presets_exist(self) -> None:
        preset_ids = {
            "male-30s-40s-lowmid",
            "male-40s-50s-lowmid",
            "male-announcer-30s-40s",
            "male-low-30s-40s",
            "male-pastor-30s-40s",
        }
        self.assertTrue(preset_ids.issubset(VOICE_PRESETS.keys()))
        self.assertTrue(preset_ids.issubset(VOICE_PRESET_LABELS.keys()))

    def test_new_male_presets_have_expected_guidance(self) -> None:
        announcer = VOICE_PRESETS["male-announcer-30s-40s"]
        pastor = VOICE_PRESETS["male-pastor-30s-40s"]
        low_voice = VOICE_PRESETS["male-low-30s-40s"]
        middle_aged = VOICE_PRESETS["male-40s-50s-lowmid"]

        self.assertEqual(announcer["pitch"], "medium")
        self.assertEqual(announcer["speed"], 1.02)
        self.assertEqual(announcer["instruct"], "male, young adult, moderate pitch, korean accent")

        self.assertEqual(pastor["pitch"], "low")
        self.assertEqual(pastor["speed"], 0.94)
        self.assertEqual(pastor["instruct"], "male, middle-aged, low pitch, korean accent")

        self.assertEqual(low_voice["pitch"], "low")
        self.assertEqual(low_voice["speed"], 0.97)
        self.assertEqual(low_voice["instruct"], "male, young adult, very low pitch, korean accent")
        self.assertEqual(middle_aged["instruct"], "male, middle-aged, low pitch, korean accent")

    def test_sample_text_mentions_comparison(self) -> None:
        self.assertIn("OmniVoice", VOICE_SAMPLE_TEXT)
        self.assertIn("비교용 샘플", VOICE_SAMPLE_TEXT)

    def test_index_contains_new_preset_options(self) -> None:
        index_html = Path("app/static/index.html").read_text(encoding="utf-8")
        self.assertIn('option value="male-30s-40s-lowmid"', index_html)
        self.assertIn('option value="male-40s-50s-lowmid"', index_html)
        self.assertIn('option value="male-announcer-30s-40s"', index_html)
        self.assertIn('option value="male-low-30s-40s"', index_html)
        self.assertIn('option value="male-pastor-30s-40s"', index_html)

    def test_sample_script_parser_supports_repeated_presets(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "--text",
                "sample",
                "--output-dir",
                "storage/voice_samples/test",
                "--preset",
                "male-low-30s-40s",
                "--preset",
                "male-pastor-30s-40s",
            ]
        )
        self.assertEqual(args.text, "sample")
        self.assertEqual(args.output_dir, Path("storage/voice_samples/test"))
        self.assertEqual(args.presets, ["male-low-30s-40s", "male-pastor-30s-40s"])
