import os
import unittest
from typing import ClassVar

from fastapi.testclient import TestClient

from app import db
from app.services.script_compile import compile_bible_longform_script, compile_standard_script

os.environ.setdefault("NEWAUTO_DISABLE_BACKGROUND_WORKERS", "1")

from app.main import app


class ScriptCompileTests(unittest.TestCase):
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
            project = db.get_project(project_id)
            if project is not None:
                self.client.delete(f"/api/projects/{project_id}")

    def create_project(self) -> str:
        response = self.client.post("/api/projects", data={"title": "script-compile"})
        self.assertEqual(response.status_code, 200)
        project_id = str(response.json()["id"])
        self.project_ids.append(project_id)
        return project_id

    def test_standard_compile_marks_sentences_as_body(self) -> None:
        compiled_script, regional_sentences = compile_standard_script("Intro sentence.\nBody sentence.")

        self.assertEqual(compiled_script, "Intro sentence.\nBody sentence.")
        self.assertEqual([item["text"] for item in regional_sentences], ["Intro sentence.", "Body sentence."])
        self.assertEqual([item["region"] for item in regional_sentences], ["body", "body"])

    def test_bible_compile_strips_markers_from_tts_sentences(self) -> None:
        compiled_script, regional_sentences = compile_bible_longform_script(
            "<<intro>>\nOpening sentence.\n<<bible>>\nJohn 3:16 Verse text."
        )

        self.assertIn("<<intro>>", compiled_script)
        self.assertEqual(
            regional_sentences,
            [
                {"idx": 0, "text": "Opening sentence.", "region": "intro"},
                {"idx": 1, "text": "John 3:16 Verse text.", "region": "bible"},
            ],
        )

    def test_save_script_persists_compile_fields(self) -> None:
        project_id = self.create_project()
        response = self.client.put(
            f"/api/projects/{project_id}/script",
            data={
                "title": "compiled",
                "script": "<<intro>>\nOpening sentence.\n<<body>>\nBody sentence.",
                "content_mode": "bible_longform",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["content_mode"], "bible_longform")
        self.assertEqual(payload["user_script"], "<<intro>>\nOpening sentence.\n<<body>>\nBody sentence.")
        self.assertEqual(payload["sentences"], ["Opening sentence.", "Body sentence."])
        self.assertEqual(
            [item["region"] for item in payload["regional_sentences"]],
            ["intro", "body"],
        )
        self.assertTrue((db.project_dir(project_id) / "compiled_script.txt").exists())


if __name__ == "__main__":
    unittest.main()
