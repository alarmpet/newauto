import io
import unittest
from typing import ClassVar

from fastapi.testclient import TestClient

from app import db
from app.main import app
from app.services.subtitle import DEFAULT_SUBTITLE_STYLE


class MediaWorkflowTests(unittest.TestCase):
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

    def create_project(self, title: str = "media-test") -> str:
        response = self.client.post("/api/projects", data={"title": title})
        self.assertEqual(response.status_code, 200)
        project_id = str(response.json()["id"])
        self.project_ids.append(project_id)
        return project_id

    def test_upload_response_includes_media_progress_and_skipped_files(self) -> None:
        project_id = self.create_project()
        response = self.client.post(
            f"/api/projects/{project_id}/media",
            files=[
                ("files", ("first.jpg", io.BytesIO(b"jpg"), "image/jpeg")),
                ("files", ("second.png", io.BytesIO(b"png"), "image/png")),
                ("files", ("skip.txt", io.BytesIO(b"text"), "text/plain")),
            ],
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["accepted_files"]), 2)
        self.assertEqual(len(payload["skipped_files"]), 1)
        self.assertEqual(payload["project"]["media_upload_state"], "done")
        self.assertEqual(payload["project"]["media_upload_progress"], 100)
        self.assertEqual(payload["project"]["media_upload_completed"], 2)
        self.assertEqual(payload["project"]["media_upload_total"], 2)
        self.assertEqual(payload["project"]["media_order"], ["first.jpg", "second.png"])

        status = self.client.get(f"/api/projects/{project_id}/status")
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()["media_upload_state"], "done")
        self.assertEqual(status.json()["media_upload_progress"], 100)

    def test_reorder_keeps_unspecified_media_and_persists_order(self) -> None:
        project_id = self.create_project()
        upload = self.client.post(
            f"/api/projects/{project_id}/media",
            files=[
                ("files", ("one.jpg", io.BytesIO(b"1"), "image/jpeg")),
                ("files", ("two.jpg", io.BytesIO(b"2"), "image/jpeg")),
                ("files", ("three.jpg", io.BytesIO(b"3"), "image/jpeg")),
            ],
        )
        self.assertEqual(upload.status_code, 200)

        reorder = self.client.put(
            f"/api/projects/{project_id}/media/order",
            json=["three.jpg", "one.jpg"],
        )
        self.assertEqual(reorder.status_code, 200)
        self.assertEqual(reorder.json()["media_order"], ["three.jpg", "one.jpg", "two.jpg"])

        refreshed = self.client.get(f"/api/projects/{project_id}")
        self.assertEqual(refreshed.status_code, 200)
        self.assertEqual(refreshed.json()["media_order"], ["three.jpg", "one.jpg", "two.jpg"])

    def test_project_includes_default_thumbnail_and_subtitle_style(self) -> None:
        project_id = self.create_project()
        response = self.client.get(f"/api/projects/{project_id}")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["thumbnail_file"], "")
        self.assertEqual(payload["subtitle_style"]["position"], DEFAULT_SUBTITLE_STYLE["position"])
        self.assertEqual(payload["subtitle_style"]["effect"], DEFAULT_SUBTITLE_STYLE["effect"])

    def test_thumbnail_upload_replace_get_and_delete(self) -> None:
        project_id = self.create_project()
        upload = self.client.post(
            f"/api/projects/{project_id}/thumbnail",
            files={"file": ("thumb.jpg", io.BytesIO(b"jpg-thumbnail"), "image/jpeg")},
        )
        self.assertEqual(upload.status_code, 200)
        self.assertEqual(upload.json()["project"]["thumbnail_file"], "thumbnail.jpg")

        thumbnail = self.client.get(f"/api/projects/{project_id}/thumbnail")
        self.assertEqual(thumbnail.status_code, 200)
        self.assertEqual(thumbnail.content, b"jpg-thumbnail")

        replace = self.client.post(
            f"/api/projects/{project_id}/thumbnail",
            files={"file": ("thumb.png", io.BytesIO(b"png-thumbnail"), "image/png")},
        )
        self.assertEqual(replace.status_code, 200)
        self.assertEqual(replace.json()["project"]["thumbnail_file"], "thumbnail.png")
        self.assertFalse((db.project_dir(project_id) / "thumbnail" / "thumbnail.jpg").exists())

        deleted = self.client.delete(f"/api/projects/{project_id}/thumbnail")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(deleted.json()["thumbnail_file"], "")
        missing = self.client.get(f"/api/projects/{project_id}/thumbnail")
        self.assertEqual(missing.status_code, 404)

    def test_thumbnail_rejects_unsupported_file_type(self) -> None:
        project_id = self.create_project()
        response = self.client.post(
            f"/api/projects/{project_id}/thumbnail",
            files={"file": ("thumb.txt", io.BytesIO(b"text"), "text/plain")},
        )
        self.assertEqual(response.status_code, 400)

    def test_subtitle_style_save_merge_and_validation(self) -> None:
        project_id = self.create_project()
        response = self.client.put(
            f"/api/projects/{project_id}/subtitle-style",
            json={
                "font_size": 54,
                "primary_color": "#FFE66D",
                "position": "top",
                "effect": "fade",
            },
        )
        self.assertEqual(response.status_code, 200)
        style = response.json()["effective_style"]
        self.assertEqual(style["font_size"], 54)
        self.assertEqual(style["primary_color"], "#FFE66D")
        self.assertEqual(style["position"], "top")
        self.assertEqual(style["effect"], "fade")
        self.assertEqual(style["outline_width"], DEFAULT_SUBTITLE_STYLE["outline_width"])

        refreshed = self.client.get(f"/api/projects/{project_id}/subtitle-style")
        self.assertEqual(refreshed.status_code, 200)
        self.assertEqual(refreshed.json()["font_size"], 54)

        invalid = self.client.put(
            f"/api/projects/{project_id}/subtitle-style",
            json={"primary_color": "white"},
        )
        self.assertEqual(invalid.status_code, 422)
