import unittest
from typing import cast
from unittest.mock import patch

from app.services.preflight import build_preflight_report
from app.types import ProjectRecord


def _project(enabled: bool) -> ProjectRecord:
    return cast(
        ProjectRecord,
        {
            "id": "hyperframes_preflight",
            "sentences": ["문장"],
            "tts_state": "done",
            "media_order": [],
            "body_image_options": {"hyperframes_overlay_enabled": enabled},
            "subtitle_style": {},
            "render_formats": ["landscape"],
            "scene_plan": None,
            "render_plan": None,
        },
    )


class HyperFramesPreflightTests(unittest.TestCase):
    @patch("app.services.preflight.write_visual_mismatch_report")
    @patch("app.services.preflight.resolve_korean_font_source")
    @patch("app.services.preflight._tts_manifest_text_summary", return_value=(True, "ok"))
    @patch("app.services.preflight._tts_consistency_summary", return_value=(True, "ok"))
    @patch("app.services.preflight._operator_intervention_summary", return_value=(True, "ok"))
    @patch("app.services.preflight.validate_generated_image_mappings", return_value=[])
    @patch("app.services.preflight.probe_hyperframes_runtime")
    def test_preflight_reports_failed_hyperframes_when_enabled(
        self,
        probe,
        _validate,
        _operator,
        _tts_consistency,
        _tts_text,
        _font,
        _write_report,
    ) -> None:
        probe.return_value = {
            "node_available": False,
            "node_version": "",
            "npx_available": False,
            "npx_version": "",
            "doctor_ok": False,
            "doctor_detail": "node not found",
            "ffmpeg_alpha_ok": False,
            "ffmpeg_alpha_detail": "",
        }

        report = build_preflight_report(_project(True))

        checks = {row["key"]: row for row in report["checks"]}
        self.assertFalse(checks["hyperframes_overlay"]["ok"])
        self.assertIn("node not found", checks["hyperframes_overlay"]["message"])

    @patch("app.services.preflight.write_visual_mismatch_report")
    @patch("app.services.preflight.resolve_korean_font_source", side_effect=FileNotFoundError("font missing"))
    @patch("app.services.preflight._tts_manifest_text_summary", return_value=(True, "ok"))
    @patch("app.services.preflight._tts_consistency_summary", return_value=(True, "ok"))
    @patch("app.services.preflight._operator_intervention_summary", return_value=(True, "ok"))
    @patch("app.services.preflight.validate_generated_image_mappings", return_value=[])
    @patch("app.services.preflight.probe_hyperframes_runtime")
    def test_preflight_reports_missing_hyperframes_font_when_enabled(
        self,
        probe,
        _validate,
        _operator,
        _tts_consistency,
        _tts_text,
        _font,
        _write_report,
    ) -> None:
        probe.return_value = {
            "node_available": True,
            "node_version": "v22.16.0",
            "npx_available": True,
            "npx_version": "10.9.2",
            "doctor_ok": True,
            "doctor_detail": "ok",
            "ffmpeg_alpha_ok": True,
            "ffmpeg_alpha_detail": "ok",
        }

        report = build_preflight_report(_project(True))

        checks = {row["key"]: row for row in report["checks"]}
        self.assertFalse(checks["hyperframes_overlay"]["ok"])
        self.assertIn("font missing", checks["hyperframes_overlay"]["message"])


if __name__ == "__main__":
    unittest.main()
