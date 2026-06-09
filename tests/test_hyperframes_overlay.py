import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.hyperframes_overlay import build_overlay_plan, resolve_korean_font_source, write_overlay_project
from scripts.render_hyperframes_overlay import _run, render_hyperframes_overlay, validate_overlay_probe


class HyperFramesOverlayTests(unittest.TestCase):
    def test_resolve_korean_font_source_returns_existing_file(self) -> None:
        path = resolve_korean_font_source()
        self.assertTrue(path.exists())

    def test_build_overlay_plan_creates_one_lower_third_keyword_per_sentence(self) -> None:
        timings = [
            {"sentence_idx": 0, "start": 0.0, "end": 4.2, "text": "젠슨 황이 경제사절단에 합류했습니다."},
            {"sentence_idx": 1, "start": 4.2, "end": 8.0, "text": "엔비디아가 공식 확인했습니다."},
        ]

        plan = build_overlay_plan(timings)

        self.assertEqual([row["overlay_type"] for row in plan["items"]], ["lower_third_keyword", "lower_third_keyword"])
        self.assertEqual(plan["items"][0]["text"], "경제사절단 합류")
        self.assertEqual(plan["items"][1]["text"], "엔비디아 공식 확인")
        self.assertLessEqual(max(len(row["text"]) for row in plan["items"]), 12)

    def test_write_overlay_project_uses_local_font_and_no_network_urls(self) -> None:
        timings = [{"sentence_idx": 0, "start": 0.0, "end": 3.0, "text": "트럼프가 직접 요청했습니다."}]
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "hyperframes_overlay"

            paths = write_overlay_project(out_dir, timings, width=1920, height=1080)

            html = paths["index_html"].read_text(encoding="utf-8")
            plan = json.loads(paths["overlay_plan"].read_text(encoding="utf-8"))
            self.assertIn("@font-face", html)
            self.assertIn('data-composition-id="newauto-overlay"', html)
            self.assertIn('data-width="1920"', html)
            self.assertIn('data-height="1080"', html)
            self.assertIn('id="overlay-0"', html)
            self.assertIn('class="clip overlay lower_left"', html)
            self.assertIn("window.__timelines", html)
            self.assertIn("assets/fonts/NotoSansKR-Regular.ttf", html)
            self.assertNotIn("https://", html)
            self.assertEqual(plan["items"][0]["text"], "직접 요청")

    def test_build_overlay_plan_preserves_lower_third_and_adds_label_plate(self) -> None:
        timings = [{"sentence_idx": 0, "start": 0.0, "end": 3.0, "text": "Nvidia strategy engine"}]

        plan = build_overlay_plan(
            timings,
            overlay_items=[
                {
                    "sentence_idx": 0,
                    "start": 0.0,
                    "end": 3.0,
                    "overlay_type": "label_plate",
                    "text": "CAPEX",
                    "box": [1180, 210, 420, 160],
                }
            ],
        )

        self.assertEqual(plan["version"], 2)
        self.assertEqual(plan["template"], "stickman_explainer_overlay")
        self.assertEqual([item["overlay_type"] for item in plan["items"]], ["lower_third_keyword", "label_plate"])
        self.assertEqual(plan["items"][1]["box"], [1180, 210, 420, 160])

    def test_write_overlay_project_renders_label_plate_box(self) -> None:
        timings = [{"sentence_idx": 0, "start": 0.0, "end": 3.0, "text": "Nvidia strategy engine"}]
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "hyperframes_overlay"

            paths = write_overlay_project(
                out_dir,
                timings,
                width=1920,
                height=1080,
                overlay_items=[
                    {
                        "sentence_idx": 0,
                        "start": 0.0,
                        "end": 3.0,
                        "overlay_type": "label_plate",
                        "text": "CAPEX",
                        "box": [1180, 210, 420, 160],
                    }
                ],
            )

            html = paths["index_html"].read_text(encoding="utf-8")
            self.assertIn("label-plate", html)
            self.assertIn("label-fit", html)
            self.assertIn("left:1180px; top:210px; width:420px; height:160px", html)
            self.assertIn("CAPEX", html)


if __name__ == "__main__":
    unittest.main()


class HyperFramesOverlayCliTests(unittest.TestCase):
    def test_run_uses_resolved_windows_command_path(self) -> None:
        with patch("scripts.render_hyperframes_overlay.shutil.which", return_value="C:/node/npx.cmd"), patch(
            "scripts.render_hyperframes_overlay.subprocess.run"
        ) as run:
            run.return_value.returncode = 0
            run.return_value.stdout = "ok"
            run.return_value.stderr = ""

            _run(["npx", "--version"])

            self.assertEqual(run.call_args.args[0][0], "C:/node/npx.cmd")
            self.assertEqual(run.call_args.kwargs["encoding"], "utf-8")
            self.assertEqual(run.call_args.kwargs["errors"], "replace")

    def test_validate_overlay_probe_accepts_alpha_duration(self) -> None:
        result = validate_overlay_probe({"pix_fmt": "yuva420p", "duration_sec": 3.04}, expected_duration_sec=3.0)
        self.assertTrue(result["ok"])

    def test_validate_overlay_probe_rejects_missing_alpha(self) -> None:
        result = validate_overlay_probe({"pix_fmt": "yuv420p", "duration_sec": 3.0}, expected_duration_sec=3.0)
        self.assertFalse(result["ok"])
        self.assertIn("alpha", result["error"])

    def test_render_hyperframes_overlay_falls_back_to_mov_when_webm_lacks_alpha(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch("scripts.render_hyperframes_overlay._run") as run, patch(
            "scripts.render_hyperframes_overlay._ffprobe_overlay"
        ) as ffprobe:
            overlay_dir = Path(tmp)
            run.return_value = (0, "ok", "")
            ffprobe.side_effect = [
                {"pix_fmt": "yuv420p", "duration_sec": 3.0},
                {"pix_fmt": "yuva444p12le", "duration_sec": 3.0},
            ]

            report = render_hyperframes_overlay(overlay_dir, expected_duration_sec=3.0)

            self.assertTrue(report["ok"])
            self.assertTrue(str(report["overlay_path"]).endswith("overlay.mov"))
            self.assertTrue((overlay_dir / "hyperframes_overlay_lint.json").exists())
            self.assertTrue((overlay_dir / "hyperframes_overlay_inspect.json").exists())
            self.assertTrue((overlay_dir / "hyperframes_overlay_ffprobe.json").exists())
