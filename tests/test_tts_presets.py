from pathlib import Path
import unittest

from app.tts_profiles import build_tts_preset_catalog, normalize_tts_profile
from scripts.generate_voice_samples import build_parser


class TtsPresetTests(unittest.TestCase):
    def test_korean_voice_presets_exist(self) -> None:
        catalog = build_tts_preset_catalog()
        preset_ids = {
            "male-deep-calm",
            "male-mid-clear",
            "male-40s-50s-lowmid",
            "male-announcer-40s-50s",
            "male-pastor-40s-50s",
            "male-60s-low",
            "male-pastor-60s",
            "male-narration-60s",
            "male-announcer-60s",
            "female-bright-clear",
            "female-low-calm",
            "elder-narration",
            "whisper-story",
        }
        self.assertTrue(preset_ids.issubset(catalog["presets"].keys()))
        self.assertTrue(preset_ids.issubset(catalog["labels"].keys()))

    def test_catalog_uses_single_source_of_truth(self) -> None:
        catalog = build_tts_preset_catalog()
        self.assertEqual(catalog["presets"]["male-deep-calm"]["instruct"], "male, low pitch")
        self.assertEqual(
            catalog["presets"]["male-40s-50s-lowmid"]["instruct"],
            "male, middle-aged, low pitch",
        )
        self.assertEqual(
            catalog["presets"]["male-announcer-40s-50s"]["instruct"],
            "male, middle-aged, moderate pitch",
        )
        self.assertEqual(
            catalog["presets"]["male-pastor-40s-50s"]["instruct"],
            "male, middle-aged, low pitch",
        )
        self.assertEqual(catalog["presets"]["male-60s-low"]["instruct"], "male, elderly, low pitch")
        self.assertEqual(
            catalog["presets"]["male-pastor-60s"]["instruct"],
            "male, elderly, low pitch",
        )
        self.assertEqual(
            catalog["presets"]["male-narration-60s"]["instruct"],
            "male, elderly, moderate pitch",
        )
        self.assertEqual(
            catalog["presets"]["male-announcer-60s"]["instruct"],
            "male, elderly, moderate pitch",
        )
        self.assertEqual(catalog["aliases"]["male-30s-40s-lowmid"], "male-deep-calm")
        self.assertEqual(catalog["aliases"]["male-pastor-30s-40s"], "male-pastor-40s-50s")

    def test_sample_text_mentions_omnivoice(self) -> None:
        catalog = build_tts_preset_catalog()
        self.assertIn("OmniVoice", catalog["sample_text"])
        self.assertIn("목소리", catalog["sample_text"])

    def test_index_uses_runtime_voice_select(self) -> None:
        index_html = Path("app/static/index.html").read_text(encoding="utf-8")
        self.assertIn('<select id="s3-voice">', index_html)
        self.assertIn('id="s3-effective-profile"', index_html)
        self.assertIn('id="s3-dirty-badge"', index_html)

    def test_legacy_male_id_resolves_to_male_canonical(self) -> None:
        canonical, profile = normalize_tts_profile({}, "male-30s-40s-lowmid")
        self.assertEqual(canonical, "male-deep-calm")
        self.assertEqual(profile["instruct"], "male, low pitch")

    def test_new_60s_presets_resolve(self) -> None:
        low_canonical, low_profile = normalize_tts_profile({}, "male-60s-low")
        pastor_canonical, pastor_profile = normalize_tts_profile({}, "male-pastor-60s")
        narration_canonical, narration_profile = normalize_tts_profile({}, "male-narration-60s")
        announcer_canonical, announcer_profile = normalize_tts_profile({}, "male-announcer-60s")

        self.assertEqual(low_canonical, "male-60s-low")
        self.assertEqual(low_profile["speed"], 0.9)
        self.assertEqual(pastor_canonical, "male-pastor-60s")
        self.assertEqual(pastor_profile["speed"], 0.87)
        self.assertEqual(narration_canonical, "male-narration-60s")
        self.assertEqual(narration_profile["instruct"], "male, elderly, moderate pitch")
        self.assertEqual(announcer_canonical, "male-announcer-60s")
        self.assertEqual(announcer_profile["speed"], 0.96)

    def test_sample_script_parser_supports_repeated_presets(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            [
                "--text",
                "sample",
                "--output-dir",
                "storage/voice_samples/test",
                "--preset",
                "male-60s-low",
                "--preset",
                "male-announcer-60s",
            ]
        )
        self.assertEqual(args.text, "sample")
        self.assertEqual(args.output_dir, Path("storage/voice_samples/test"))
        self.assertEqual(args.presets, ["male-60s-low", "male-announcer-60s"])
