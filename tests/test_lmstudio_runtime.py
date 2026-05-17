import subprocess
import unittest
from unittest.mock import patch

from app.services.lmstudio_runtime import loaded_lmstudio_models


class LmStudioRuntimeTest(unittest.TestCase):
    @patch("app.services.lmstudio_runtime._lms_exe_path")
    @patch("app.services.lmstudio_runtime.subprocess.run")
    def test_loaded_models_uses_lms_ps_no_models_as_empty(self, run_mock, path_mock) -> None:
        path_mock.return_value.is_file.return_value = True
        run_mock.return_value = subprocess.CompletedProcess(
            args=["lms", "ps"],
            returncode=0,
            stdout="No models are currently loaded.\n",
            stderr="",
        )

        self.assertEqual(loaded_lmstudio_models(), [])


if __name__ == "__main__":
    unittest.main()
