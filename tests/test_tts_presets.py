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
        self.assertEqual(catalog["presets"]["male-40s-50s-lowmid"]["instruct"], "male, middle-aged, low pitch")
        self.assertEqual(catalog["presets"]["male-announcer-40s-50s"]["instruct"], "male, middle-aged, moderate pitch")
        self.assertEqual(catalog["presets"]["male-pastor-40s-50s"]["instruct"], "male, middle-aged, low pitch")
        self.assertEqual(catalog["presets"]["female-bright-clear"]["instruct"], "female, high pitch")
        self.assertEqual(catalog["presets"]["whisper-story"]["instruct"], "whisper, young adult")
        self.assertEqual(catalog["aliases"]["male-30s-40s-lowmid"], "male-deep-calm")
        self.assertEqual(catalog["aliases"]["male-pastor-30s-40s"], "male-pastor-40s-50s")

    def test_sample_text_mentions_comparison(self) -> None:
        catalog = build_tts_preset_catalog()
        self.assertIn("OmniVoice", catalog["sample_text"])
        self.assertIn("비교", catalog["sample_text"])

    def test_index_uses_runtime_voice_select(self) -> None:
        index_html = Path("app/static/index.html").read_text(encoding="utf-8")
        self.assertIn('<select id="s3-voice">', index_html)
        self.assertIn('id="s3-effective-profile"', index_html)
        self.assertIn('id="s3-dirty-badge"', index_html)

    def test_legacy_male_id_resolves_to_male_canonical(self) -> None:
        canonical, profile = normalize_tts_profile({}, "male-30s-40s-lowmid")
        self.assertEqual(canonical, "male-deep-calm")
        self.assertEqual(profile["instruct"], "male, low pitch")

    def test_new_40s_50s_presets_resolve(self) -> None:
        lowmid_canonical, lowmid_profile = normalize_tts_profile({}, "male-40s-50s-lowmid")
        announcer_canonical, announcer_profile = normalize_tts_profile({}, "male-announcer-40s-50s")
        pastor_canonical, pastor_profile = normalize_tts_profile({}, "male-pastor-40s-50s")

        self.assertEqual(lowmid_canonical, "male-40s-50s-lowmid")
        self.assertEqual(lowmid_profile["instruct"], "male, middle-aged, low pitch")
        self.assertEqual(announcer_canonical, "male-announcer-40s-50s")
        self.assertEqual(announcer_profile["instruct"], "male, middle-aged, moderate pitch")
        self.assertEqual(pastor_canonical, "male-pastor-40s-50s")
        self.assertEqual(pastor_profile["instruct"], "male, middle-aged, low pitch")

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
