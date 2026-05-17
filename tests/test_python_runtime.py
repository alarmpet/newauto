import unittest
from unittest.mock import patch

from app.services.python_runtime import (
    get_omnivoice_runtime_status,
    resolve_omnivoice_python_with_probes,
    probe_omnivoice_python_candidates,
    resolve_omnivoice_python,
)


class PythonRuntimeTests(unittest.TestCase):
    def test_get_omnivoice_runtime_status_returns_first_resolved_candidate(self) -> None:
        with patch(
            "app.services.python_runtime._candidate_paths",
            return_value=["c:/bad/python.exe", "c:/good/python.exe"],
        ), patch(
            "app.services.python_runtime.probe_omnivoice_python",
            side_effect=[
                {
                    "resolved": False,
                    "python_path": "c:/bad/python.exe",
                    "omnivoice_import_ok": False,
                    "torch_import_ok": False,
                    "cuda_available": False,
                    "error": "import failed",
                },
                {
                    "resolved": True,
                    "python_path": "c:/good/python.exe",
                    "omnivoice_import_ok": True,
                    "torch_import_ok": True,
                    "cuda_available": True,
                    "error": "",
                },
            ],
        ):
            status = get_omnivoice_runtime_status()

        self.assertTrue(status["resolved"])
        self.assertEqual(status["python_path"], "c:/good/python.exe")
        self.assertTrue(status["omnivoice_import_ok"])
        self.assertTrue(status["torch_import_ok"])

    def test_resolve_omnivoice_python_raises_when_not_resolved(self) -> None:
        unresolved = {
            "resolved": False,
            "python_path": "",
            "omnivoice_import_ok": False,
            "torch_import_ok": False,
            "cuda_available": False,
            "error": "No usable OmniVoice Python environment found.",
        }
        with patch("app.services.python_runtime.resolve_omnivoice_python_with_probes", return_value=(unresolved, [])):
            with self.assertRaisesRegex(RuntimeError, "No usable OmniVoice Python environment found."):
                resolve_omnivoice_python()

    def test_probe_omnivoice_python_candidates_preserves_order(self) -> None:
        with patch(
            "app.services.python_runtime._candidate_paths",
            return_value=["c:/bad/python.exe", "c:/good/python.exe"],
        ), patch(
            "app.services.python_runtime.probe_omnivoice_python",
            side_effect=[
                {
                    "resolved": False,
                    "python_path": "c:/bad/python.exe",
                    "omnivoice_import_ok": False,
                    "torch_import_ok": False,
                    "cuda_available": False,
                    "error": "import failed",
                },
                {
                    "resolved": True,
                    "python_path": "c:/good/python.exe",
                    "omnivoice_import_ok": True,
                    "torch_import_ok": True,
                    "cuda_available": True,
                    "error": "",
                },
            ],
        ):
            candidates = probe_omnivoice_python_candidates()

        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0]["python_path"], "c:/bad/python.exe")
        self.assertEqual(candidates[1]["python_path"], "c:/good/python.exe")
        self.assertTrue(candidates[1]["resolved"])

    def test_resolve_omnivoice_python_with_probes_selects_first_resolved(self) -> None:
        with patch(
            "app.services.python_runtime._candidate_paths",
            return_value=["c:/bad/python.exe", "c:/good/python.exe", "c:/also-good/python.exe"],
        ), patch(
            "app.services.python_runtime.probe_omnivoice_python",
            side_effect=[
                {
                    "resolved": False,
                    "python_path": "c:/bad/python.exe",
                    "omnivoice_import_ok": False,
                    "torch_import_ok": False,
                    "cuda_available": False,
                    "error": "import failed",
                },
                {
                    "resolved": True,
                    "python_path": "c:/good/python.exe",
                    "omnivoice_import_ok": True,
                    "torch_import_ok": True,
                    "cuda_available": True,
                    "error": "",
                },
                {
                    "resolved": True,
                    "python_path": "c:/also-good/python.exe",
                    "omnivoice_import_ok": True,
                    "torch_import_ok": True,
                    "cuda_available": True,
                    "error": "",
                },
            ],
        ):
            selected_status, candidate_statuses = resolve_omnivoice_python_with_probes()

        self.assertEqual(selected_status["python_path"], "c:/good/python.exe")
        self.assertEqual(len(candidate_statuses), 3)
        self.assertTrue(candidate_statuses[1]["resolved"])
