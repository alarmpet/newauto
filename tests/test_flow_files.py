import base64
import os
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import ClassVar
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import db

os.environ.setdefault("NEWAUTO_DISABLE_BACKGROUND_WORKERS", "1")

from app.main import app
from app.services.flow_prompting import attach_flow_asset_to_manifest
from app.services.operator_summary import operator_summary_path
from scripts import flow_generate_all_worker


def _tiny_png_bytes() -> bytes:
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wn0l1sAAAAASUVORK5CYII="
    )


class FlowFilesTests(unittest.TestCase):
    client: ClassVar[TestClient]

    @classmethod
    def setUpClass(cls) -> None:
        db.init_db()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()

    def setUp(self) -> None:
        self.project_ids: list[str] = []

    def tearDown(self) -> None:
        for project_id in self.project_ids:
            self.client.delete(f"/api/projects/{project_id}")

    def create_project_with_sentences(self) -> str:
        response = self.client.post("/api/projects", data={"title": "flow-files-test"})
        self.assertEqual(response.status_code, 200)
        project_id = str(response.json()["id"])
        self.project_ids.append(project_id)
        db.update_project(project_id, sentences=["첫 문장", "두 번째 문장"])
        return project_id

    def create_flow_prompts(self, project_id: str) -> None:
        response = self.client.post(f"/api/flow/prompts/{project_id}", json={"aspect_ratio": "9:16"})
        self.assertEqual(response.status_code, 200)

    def test_flow_prompts_csv_and_sentence_text_routes(self) -> None:
        project_id = self.create_project_with_sentences()
        self.create_flow_prompts(project_id)

        csv_response = self.client.get(f"/api/flow/prompts/{project_id}/csv")
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("sentence_number,prompt,negative_prompt,section,narration", csv_response.text)
        self.assertIn("첫 문장", csv_response.text)

        text_response = self.client.get(f"/api/flow/prompts/{project_id}/sentence/1")
        self.assertEqual(text_response.status_code, 200)
        self.assertIn("Narration language: Korean.", text_response.text)
        self.assertNotIn("첫 문장", text_response.text)

    def removed_prepare_legacy_prompt_files_route(self) -> None:
        project_id = self.create_project_with_sentences()
        self.create_flow_prompts(project_id)

        response = self.client.post(f"/api/flow/prompts/{project_id}/legacy/prepare")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        csv_path = Path(str(payload["csv_path"]))
        prompt_paths = [Path(str(path)) for path in payload["prompt_paths"]]
        self.assertTrue(csv_path.exists())
        self.assertEqual(len(prompt_paths), 2)
        self.assertTrue(prompt_paths[0].exists())
        self.assertIn("첫 문장", csv_path.read_text(encoding="utf-8"))

    def test_attach_renamed_flow_assets_maps_by_filename_sentence_number(self) -> None:
        project_id = self.create_project_with_sentences()
        self.create_flow_prompts(project_id)

        with TemporaryDirectory() as temp_dir:
            source_dir = Path(temp_dir)
            first = source_dir / "flow_s002_20260507T010000.png"
            second = source_dir / "flow_s001_20260507T005900.png"
            first.write_bytes(_tiny_png_bytes())
            second.write_bytes(_tiny_png_bytes())

            response = self.client.post(
                f"/api/flow/assets/{project_id}/attach-renamed",
                json={"search_dir": str(source_dir), "since_minutes": 60},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["attached"], ["flow_sentence_001.png", "flow_sentence_002.png"])
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        mappings = project["body_image_mappings"]
        self.assertEqual([mapping["sentence_idx"] for mapping in mappings], [0, 1])
        self.assertEqual(mappings[0]["selected_reason"], "flow_renamed_download")
        self.assertTrue((db.project_dir(project_id) / "media" / "flow_sentence_001.png").exists())

    def test_flow_generate_all_worker_writes_status_and_operator_summary(self) -> None:
        project_id = self.create_project_with_sentences()
        self.create_flow_prompts(project_id)

        def fake_fill_or_generate(pid: str, *, start_sentence_number: int, limit: int, click_generate: bool) -> dict[str, object]:
            project = db.get_project(pid)
            self.assertIsNotNone(project)
            assert project is not None
            media_dir = db.project_dir(pid) / "media"
            flow_assets_dir = db.project_dir(pid) / "flow_assets"
            media_dir.mkdir(parents=True, exist_ok=True)
            flow_assets_dir.mkdir(parents=True, exist_ok=True)
            mappings = []
            media_order = []
            records = []
            for sentence_idx in range(len(project["sentences"])):
                saved_name = f"flow_sentence_{sentence_idx + 1:03d}.png"
                source = db.project_dir(pid) / f"generated_{sentence_idx + 1}.png"
                source.write_bytes(_tiny_png_bytes())
                shutil.copy2(source, media_dir / saved_name)
                shutil.copy2(source, flow_assets_dir / saved_name)
                attach_flow_asset_to_manifest(project, sentence_idx=sentence_idx, asset_path=saved_name)
                mappings.append(
                    {
                        "sentence_idx": sentence_idx,
                        "path": saved_name,
                        "prompt": f"prompt {sentence_idx + 1}",
                        "selected_reason": "flow_playwright_direct",
                    }
                )
                media_order.append(saved_name)
                records.append(
                    {
                        "sentence_number": sentence_idx + 1,
                        "status": "ok",
                        "attempt": 1,
                        "path": str(source),
                        "attached": [saved_name],
                    }
                )
            db.update_project(pid, body_image_mappings=mappings, media_order=media_order)
            return {
                "ok": True,
                "mode": "flow_direct_generate_attach",
                "processed": len(records),
                "requested": len(records),
                "attached": media_order,
                "records": records,
            }

        with patch.object(flow_generate_all_worker.flow_browser_automation, "fill_or_generate", fake_fill_or_generate):
            exit_code = flow_generate_all_worker.run(project_id, start_sentence_number=1, limit=0)

        self.assertEqual(exit_code, 0)
        status = flow_generate_all_worker._status_path(project_id).read_text(encoding="utf-8")
        self.assertIn('"status": "done"', status)
        self.assertTrue((db.project_dir(project_id) / "flow_run_log.json").exists())
        self.assertTrue(operator_summary_path(project_id).exists())
        project = db.get_project(project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertEqual(project["body_image_state"], "done")
        self.assertEqual(len(project["body_image_mappings"]), 2)


if __name__ == "__main__":
    unittest.main()
