from __future__ import annotations

import io
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scripts import openrouter_subagent_harness as harness


class OpenRouterSubagentHarnessTests(unittest.TestCase):
    def test_resolve_task_text_accepts_at_file_shorthand(self) -> None:
        task, task_file = harness.resolve_task_text("@storage/tmp/openrouter-task.txt", "")

        self.assertEqual(task, "")
        self.assertEqual(task_file, "storage/tmp/openrouter-task.txt")

    def test_task_stdin_preserves_complex_prompt_text(self) -> None:
        prompt = 'Flow 실패 원인 분석: "Generate" 버튼, 줄바꿈\n--model 값은 건드리지 말 것'
        with patch("sys.stdin", io.StringIO(prompt)):
            result = harness.run_harness(
                mode="debug",
                task="",
                task_stdin=True,
                dry_run=True,
                max_input_chars=6000,
            )

        self.assertTrue(result.ok)
        self.assertTrue(result.skipped)
        self.assertEqual((result.packed_context or {}).get("task"), prompt)

    def test_task_file_path_keeps_complex_prompt_out_of_cli_args(self) -> None:
        with TemporaryDirectory(dir=harness.ROOT_DIR) as temp_dir:
            task_path = Path(temp_dir) / "openrouter-task.txt"
            task_path.write_text("복잡한 프롬프트\n--model should remain separate", encoding="utf-8")

            result = harness.run_harness(
                mode="review",
                task=f"@{task_path}",
                dry_run=True,
                max_input_chars=6000,
            )

        self.assertTrue(result.ok)
        self.assertEqual(
            (result.packed_context or {}).get("task"),
            "복잡한 프롬프트\n--model should remain separate",
        )


if __name__ == "__main__":
    unittest.main()
