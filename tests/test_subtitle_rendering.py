import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app import db
from app.services import yt_upload
from app.services.subtitle import DEFAULT_SUBTITLE_STYLE, normalize_subtitle_style, write_ass, write_srt
from app.types import SubtitleStyle, TimingEntry


class FakeCredentials:
    valid = True


class FakeUploadRequest:
    def next_chunk(self) -> tuple[None, dict[str, str]]:
        return None, {"id": "video123"}


class FakeExecuteRequest:
    def __init__(self) -> None:
        self.executed = False

    def execute(self) -> dict[str, bool]:
        self.executed = True
        return {"ok": True}


class FakeVideosResource:
    def insert(self, part: str, body: dict[str, object], media_body: object) -> FakeUploadRequest:
        self.part = part
        self.body = body
        self.media_body = media_body
        return FakeUploadRequest()


class FakeThumbnailsResource:
    def __init__(self) -> None:
        self.video_id = ""
        self.media_body: object | None = None
        self.request = FakeExecuteRequest()

    def set(self, videoId: str, media_body: object) -> FakeExecuteRequest:
        self.video_id = videoId
        self.media_body = media_body
        return self.request


class FakeYouTubeService:
    def __init__(self) -> None:
        self.videos_resource = FakeVideosResource()
        self.thumbnails_resource = FakeThumbnailsResource()

    def videos(self) -> FakeVideosResource:
        return self.videos_resource

    def thumbnails(self) -> FakeThumbnailsResource:
        return self.thumbnails_resource


class FakeMediaFileUpload:
    def __init__(self, path: str, **kwargs: object) -> None:
        self.path = path
        self.kwargs = kwargs


class SubtitleRenderingTests(unittest.TestCase):
    def test_write_ass_applies_style_and_effect(self) -> None:
        timings: list[TimingEntry] = [
            {
                "idx": 0,
                "text": "첫 번째 문장입니다. 두 번째 줄입니다.",
                "start": 0.0,
                "end": 2.5,
                "dur": 2.5,
            }
        ]
        style: SubtitleStyle = {
            **DEFAULT_SUBTITLE_STYLE,
            "font_size": 60,
            "primary_color": "#FFE66D",
            "position": "top",
            "margin_h": 144,
            "effect": "fade",
            "max_line_chars": 12,
        }
        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "subtitles.ass"
            write_ass(timings, output_path, style)
            content = output_path.read_text(encoding="utf-8")

        self.assertIn("Style: Default,Malgun Gothic,60", content)
        self.assertIn("&H006DE6FF", content)
        self.assertIn(",8,144,144,80,", content)
        self.assertIn(r"{\fad(120,120)}", content)
        self.assertIn(r"\N", content)

    def test_write_ass_supports_five_position_layout(self) -> None:
        timings: list[TimingEntry] = [
            {"idx": 0, "text": "가운데보다 조금 위에 배치되는 자막입니다.", "start": 0.0, "end": 0.7, "dur": 0.7}
        ]
        style: SubtitleStyle = {
            **DEFAULT_SUBTITLE_STYLE,
            "position": "upper",
            "margin_v": 48,
            "min_display_sec": 1.4,
        }
        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "subtitles.ass"
            write_ass(timings, output_path, style)
            content = output_path.read_text(encoding="utf-8")

        self.assertIn(",8,120,120,270,", content)
        self.assertIn("Dialogue: 0,0:00:00.00,0:00:01.40,", content)

    def test_write_srt_extends_short_cues_without_overlap(self) -> None:
        timings: list[TimingEntry] = [
            {"idx": 0, "text": "첫 문장입니다.", "start": 0.0, "end": 0.4, "dur": 0.4},
            {"idx": 1, "text": "두 번째 문장입니다.", "start": 1.0, "end": 1.3, "dur": 0.3},
        ]
        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "subtitles.srt"
            write_srt(timings, output_path)
            content = output_path.read_text(encoding="utf-8")

        self.assertIn("00:00:00,000 --> 00:00:00,950", content)
        self.assertIn("00:00:01,000 --> 00:00:02,000", content)

    def test_normalize_subtitle_style_accepts_new_fields(self) -> None:
        style = normalize_subtitle_style(
            {
                "position": "lower",
                "margin_h": 180,
                "min_display_sec": 2.25,
            }
        )

        self.assertEqual(style["position"], "lower")
        self.assertEqual(style["margin_h"], 180)
        self.assertEqual(style["min_display_sec"], 2.25)

    def test_write_ass_wraps_long_lines_into_two_lines(self) -> None:
        timings: list[TimingEntry] = [
            {
                "idx": 0,
                "text": "이 문장은 자동 줄바꿈이 필요할 만큼 충분히 길어서 보기 좋은 두 줄 자막으로 나뉘어야 합니다.",
                "start": 0.0,
                "end": 2.4,
                "dur": 2.4,
            }
        ]
        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "subtitles.ass"
            write_ass(timings, output_path, {**DEFAULT_SUBTITLE_STYLE, "max_line_chars": 24})
            content = output_path.read_text(encoding="utf-8")

        self.assertIn(r"\N", content)
        self.assertNotIn(r"\N\N", content)

    def test_youtube_upload_sets_thumbnail_when_present(self) -> None:
        db.init_db()
        project = db.create_project("youtube-thumb")
        project_id = project["id"]
        project_dir = db.project_dir(project_id)
        thumbnail_dir = project_dir / "thumbnail"
        thumbnail_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "output.mp4").write_bytes(b"video")
        (thumbnail_dir / "thumbnail.jpg").write_bytes(b"thumb")
        db.update_project(project_id, thumbnail_file="thumbnail.jpg")
        youtube = FakeYouTubeService()

        try:
            with patch("app.services.yt_upload._load_creds", return_value=FakeCredentials()), patch(
                "googleapiclient.discovery.build",
                return_value=youtube,
            ), patch("googleapiclient.http.MediaFileUpload", FakeMediaFileUpload):
                yt_upload.run_upload_job(project_id, "title", "description", ["tag"], "private")

            updated = db.get_project(project_id)
            self.assertIsNotNone(updated)
            assert updated is not None
            self.assertEqual(updated["upload_state"], "done")
            self.assertEqual(updated["youtube_id"], "video123")
            self.assertEqual(youtube.thumbnails_resource.video_id, "video123")
            media_body = youtube.thumbnails_resource.media_body
            self.assertIsInstance(media_body, FakeMediaFileUpload)
            assert isinstance(media_body, FakeMediaFileUpload)
            self.assertTrue(media_body.path.endswith("thumbnail.jpg"))
        finally:
            db.delete_project(project_id)
