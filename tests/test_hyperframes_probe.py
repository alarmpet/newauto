import unittest
from unittest.mock import patch

from app.services.hyperframes_probe import (
    HYPERFRAMES_PACKAGE,
    _run_text,
    parse_node_major,
    probe_hyperframes_runtime,
)


class HyperFramesProbeTests(unittest.TestCase):
    def test_parse_node_major_accepts_v22(self) -> None:
        self.assertEqual(parse_node_major("v22.16.0\n"), 22)

    def test_parse_node_major_rejects_unparseable_output(self) -> None:
        self.assertIsNone(parse_node_major("not node"))

    @patch("app.services.hyperframes_probe.subprocess.run")
    def test_run_text_decodes_with_utf8_replacement(self, run) -> None:
        run.return_value.returncode = 0
        run.return_value.stdout = "ok"
        run.return_value.stderr = ""

        _run_text(["node", "--version"])

        self.assertEqual(run.call_args.kwargs["encoding"], "utf-8")
        self.assertEqual(run.call_args.kwargs["errors"], "replace")

    @patch("app.services.hyperframes_probe.shutil.which")
    def test_probe_reports_missing_node_without_running_doctor(self, which) -> None:
        which.return_value = None

        status = probe_hyperframes_runtime(refresh=True)

        self.assertFalse(status["node_available"])
        self.assertFalse(status["doctor_ok"])
        self.assertIn("node not found", status["doctor_detail"])

    @patch("app.services.hyperframes_probe._run_text")
    @patch("app.services.hyperframes_probe.shutil.which")
    def test_probe_uses_pinned_hyperframes_package(self, which, run_text) -> None:
        which.side_effect = lambda name: f"C:/bin/{name}.exe"
        run_text.side_effect = [
            (0, "v22.16.0\n", ""),
            (0, "10.9.2\n", ""),
            (0, "doctor ok\n", ""),
            (0, " V..... libvpx-vp9\n V..... prores_ks\n", ""),
        ]

        status = probe_hyperframes_runtime(refresh=True)

        self.assertTrue(status["node_available"])
        self.assertTrue(status["npx_available"])
        self.assertTrue(status["doctor_ok"])
        self.assertTrue(status["ffmpeg_alpha_ok"])
        self.assertIn(HYPERFRAMES_PACKAGE, run_text.call_args_list[2].args[0])

    @patch("app.services.hyperframes_probe._run_text")
    @patch("app.services.hyperframes_probe.shutil.which")
    def test_probe_runs_resolved_windows_command_paths(self, which, run_text) -> None:
        paths = {
            "node": "C:/Program Files/nodejs/node.exe",
            "npx": "C:/Program Files/nodejs/npx.cmd",
            "ffmpeg": "C:/ffmpeg/bin/ffmpeg.exe",
        }
        which.side_effect = lambda name: paths.get(name)
        run_text.side_effect = [
            (0, "v22.16.0\n", ""),
            (0, "10.9.2\n", ""),
            (0, "doctor ok\n", ""),
            (0, " V..... libvpx-vp9\n V..... prores_ks\n", ""),
        ]

        probe_hyperframes_runtime(refresh=True)

        self.assertEqual(run_text.call_args_list[0].args[0][0], paths["node"])
        self.assertEqual(run_text.call_args_list[1].args[0][0], paths["npx"])
        self.assertEqual(run_text.call_args_list[2].args[0][0], paths["npx"])
        self.assertEqual(run_text.call_args_list[3].args[0][0], paths["ffmpeg"])

    @patch("app.services.hyperframes_probe._run_text")
    @patch("app.services.hyperframes_probe.shutil.which")
    def test_probe_treats_doctor_failed_checks_as_not_ready(self, which, run_text) -> None:
        which.side_effect = lambda name: f"C:/bin/{name}.exe"
        run_text.side_effect = [
            (0, "v22.16.0\n", ""),
            (0, "10.9.2\n", ""),
            (0, "✗ Chrome           Not found\n◇  Some checks failed", ""),
            (0, " V..... libvpx-vp9\n V..... prores_ks\n", ""),
        ]

        status = probe_hyperframes_runtime(refresh=True)

        self.assertFalse(status["doctor_ok"])
        self.assertIn("Chrome", status["doctor_detail"])

    @patch("app.services.hyperframes_probe._run_text")
    @patch("app.services.hyperframes_probe.shutil.which")
    def test_probe_allows_docker_running_failure_when_chrome_is_ready(self, which, run_text) -> None:
        which.side_effect = lambda name: f"C:/bin/{name}.exe"
        run_text.side_effect = [
            (0, "v22.16.0\n", ""),
            (0, "10.9.2\n", ""),
            (0, "✓ Chrome           cache: chrome-headless-shell.exe\n✗ Docker running   Not running\n◇  Some checks failed", ""),
            (0, " V..... libvpx-vp9\n V..... prores_ks\n", ""),
        ]

        status = probe_hyperframes_runtime(refresh=True)

        self.assertTrue(status["doctor_ok"])

    @patch("app.services.system_health.probe_hyperframes_runtime")
    def test_system_health_exposes_hyperframes_probe(self, probe) -> None:
        from app.services.system_health import get_system_health

        probe.return_value = {
            "node_available": True,
            "node_version": "v22.16.0",
            "node_major": 22,
            "npx_available": True,
            "npx_version": "10.9.2",
            "doctor_ok": True,
            "doctor_detail": "ok",
            "ffmpeg_alpha_ok": True,
            "ffmpeg_alpha_detail": "libvpx-vp9 prores_ks",
        }

        health = get_system_health(refresh_runtime=True)

        self.assertTrue(health["hyperframes_node_available"])
        self.assertEqual(health["hyperframes_node_version"], "v22.16.0")
        self.assertTrue(health["hyperframes_doctor_ok"])
        self.assertTrue(health["hyperframes_ffmpeg_alpha_ok"])


if __name__ == "__main__":
    unittest.main()
