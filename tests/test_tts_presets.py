from pathlib import Path
import unittest

from app.config import VOICE_PRESETS, VOICE_PRESET_LABELS, VOICE_SAMPLE_TEXT
from scripts.generate_voice_samples import build_parser


class TtsPresetTests(unittest.TestCase):
    def test_korean_voice_presets_exist(self) -> None:
        preset_ids = {
            "male-deep-calm",
            "male-mid-clear",
            "female-bright-clear",
            "female-low-calm",
            "elder-narration",
            "whisper-story",
        }
        self.assertTrue(preset_ids.issubset(VOICE_PRESETS.keys()))
        self.assertTrue(preset_ids.issubset(VOICE_PRESET_LABELS.keys()))

    def test_new_presets_have_distinct_guidance(self) -> None:
        deep = VOICE_PRESETS["male-deep-calm"]
        bright = VOICE_PRESETS["female-bright-clear"]
        whisper = VOICE_PRESETS["whisper-story"]

        self.assertEqual(deep["language"], "ko")
        self.assertEqual(deep["mode"], "design")
        self.assertEqual(deep["speed"], 0.96)
        self.assertIn("deep calm", deep["instruct"])

        self.assertEqual(bright["language"], "ko")
        self.assertEqual(bright["guidance_scale"], 3.0)
        self.assertIn("bright clear", bright["instruct"])

        self.assertEqual(whisper["num_step"], 40)
        self.assertEqual(whisper["speed"], 0.92)
        self.assertIn("storytelling", whisper["instruct"])

    def test_sample_text_mentions_comparison(self) -> None:
        self.assertIn("OmniVoice", VOICE_SAMPLE_TEXT)
        self.assertIn("비교", VOICE_SAMPLE_TEXT)

    def test_index_contains_new_preset_options(self) -> None:
        index_html = Path("app/static/index.html").read_text(encoding="utf-8")
        self.assertIn('option value="male-deep-calm"', index_html)
        self.assertIn('option value="female-bright-clear"', index_html)
        self.assertIn('option value="whisper-story"', index_html)
        self.assertIn('option value="english-bright"', index_html)

    def test_sample_script_parser_supports_repeated_presets(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "--text",
                "sample",
                "--output-dir",
                "storage/voice_samples/test",
                "--preset",
                "male-deep-calm",
                "--preset",
                "whisper-story",
            ]
        )
        self.assertEqual(args.text, "sample")
        self.assertEqual(args.output_dir, Path("storage/voice_samples/test"))
        self.assertEqual(args.presets, ["male-deep-calm", "whisper-story"])
