import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app import db
from app.services import yt_upload
from app.services.subtitle import (
    DEFAULT_SUBTITLE_STYLE,
    _ass_margin_v,
    _effective_max_line_chars,
    _estimate_block_height_px,
    _smart_wrap,
    normalize_subtitle_style,
    write_ass,
    write_srt,
)
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
    def test_smart_wrap_keeps_first_line_within_max_len(self) -> None:
        text = "여러분 혹시 내 몸에 전혀 맞지 않는 무겁고 거추장스러운 옷을 입고 하루 종일 사람들을 상대해 본 적이 있으신가요"
        wrapped = _smart_wrap(text, 20)

        first_line = wrapped.split("\n", maxsplit=1)[0]
        self.assertLessEqual(len(first_line), 20)

    def test_smart_wrap_returns_at_most_two_lines(self) -> None:
        wrapped = _smart_wrap("x" * 100, 10)
        self.assertLessEqual(wrapped.count("\n"), 1)

    def test_effective_max_chars_lowers_floor_for_large_font(self) -> None:
        style: SubtitleStyle = {
            **DEFAULT_SUBTITLE_STYLE,
            "font_size": 96,
            "margin_h": 400,
            "max_line_chars": 20,
        }
        self.assertLessEqual(_effective_max_line_chars(style), 12)

    def test_effective_max_chars_uses_realistic_korean_width_for_large_font(self) -> None:
        style: SubtitleStyle = {
            **DEFAULT_SUBTITLE_STYLE,
            "font_size": 96,
            "margin_h": 120,
            "max_line_chars": 20,
        }
        effective = _effective_max_line_chars(style)
        self.assertGreaterEqual(effective, 14)
        self.assertLessEqual(effective, 18)

    def test_ass_margin_v_lower_places_center_near_lower_third(self) -> None:
        margin_v = _ass_margin_v("lower", user_margin_v=100, font_size=96, line_count=2, outline=2)
        block_height = _estimate_block_height_px(96, 2, 2)
        caption_center_y = 1080 - margin_v - (block_height // 2)

        self.assertLess(abs(caption_center_y - 842), 6)

    def test_ass_margin_v_top_uses_user_margin_for_fine_tune(self) -> None:
        base = _ass_margin_v("top", user_margin_v=0, font_size=48, line_count=1, outline=2)
        tuned = _ass_margin_v("top", user_margin_v=50, font_size=48, line_count=1, outline=2)

        self.assertLess(tuned, base)

    def test_screenshot_case_wraps_into_readable_lines(self) -> None:
        style: SubtitleStyle = {
            **DEFAULT_SUBTITLE_STYLE,
            "font_size": 96,
            "position": "lower",
            "margin_h": 120,
            "margin_v": 100,
            "max_line_chars": 20,
            "outline_width": 2,
        }
        effective = _effective_max_line_chars(style)
        wrapped = _smart_wrap(
            "여러분, 혹시 내 몸에 전혀 맞지 않는 무겁고 거추장스러운 옷을 입고 하루 종일 사람들을 상대해 본 적이 있으신가요?",
            effective,
        )

        self.assertLessEqual(effective, 20)
        self.assertLessEqual(wrapped.count("\n"), 1)
        self.assertLessEqual(len(wrapped.split("\n", maxsplit=1)[0]), effective)
        self.assertIn("\n", wrapped)

    def test_write_ass_applies_style_and_effect(self) -> None:
        timings: list[TimingEntry] = [
            {
                "idx": 0,
                "text": "첫 번째 문장입니다. 두 번째 줄로 자연스럽게 나뉘는지 확인합니다.",
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
            "max_line_chars": 18,
        }
        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "subtitles.ass"
            write_ass(timings, output_path, style)
            content = output_path.read_text(encoding="utf-8")

        self.assertIn("Style: Default,Malgun Gothic,60", content)
        self.assertIn("&H006DE6FF", content)
        self.assertIn("Style: Default,Malgun Gothic,60,&H006DE6FF", content)
        self.assertIn(",2,144,144,80,", content)
        self.assertIn("Dialogue: 0,0:00:00.00,0:00:02.50,Default,,0,0,", content)
        self.assertIn(r"{\fad(120,120)}", content)
        self.assertIn(r"\N", content)

    def test_write_ass_supports_adjusted_upper_and_lower_layout(self) -> None:
        timings: list[TimingEntry] = [
            {"idx": 0, "text": "위쪽 고정 위치 테스트", "start": 0.0, "end": 0.7, "dur": 0.7}
        ]
        upper_style: SubtitleStyle = {
            **DEFAULT_SUBTITLE_STYLE,
            "position": "upper",
            "margin_v": 48,
            "min_display_sec": 1.4,
        }
        lower_style: SubtitleStyle = {
            **DEFAULT_SUBTITLE_STYLE,
            "position": "lower",
            "margin_v": 48,
        }
        with TemporaryDirectory() as temp_dir:
            upper_output = Path(temp_dir) / "upper.ass"
            lower_output = Path(temp_dir) / "lower.ass"
            write_ass(timings, upper_output, upper_style)
            write_ass(timings, lower_output, lower_style)
            upper_content = upper_output.read_text(encoding="utf-8")
            lower_content = lower_output.read_text(encoding="utf-8")

        self.assertIn(",2,120,120,48,", upper_content)
        self.assertIn(",2,120,120,48,", lower_content)
        self.assertRegex(upper_content, r"Dialogue: 0,0:00:00\.00,0:00:01\.40,Default,,0,0,\d+,,")
        self.assertRegex(lower_content, r"Dialogue: 0,0:00:00\.00,0:00:01\.00,Default,,0,0,\d+,,")
        self.assertIn("Dialogue: 0,0:00:00.00,0:00:01.40,", upper_content)

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
        self.assertEqual(style["max_line_chars"], 26)

    def test_write_ass_wraps_long_lines_with_shorter_default_policy(self) -> None:
        timings: list[TimingEntry] = [
            {
                "idx": 0,
                "text": "이 문장은 화면에 너무 길게 보이지 않도록 더 짧은 두 줄 자막으로 나뉘어야 합니다.",
                "start": 0.0,
                "end": 2.4,
                "dur": 2.4,
            }
        ]
        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "subtitles.ass"
            write_ass(timings, output_path, DEFAULT_SUBTITLE_STYLE)
            content = output_path.read_text(encoding="utf-8")

        self.assertIn(r"\N", content)
        self.assertNotIn(r"\N\N", content)
        self.assertNotIn("화면에 너무 길게 보이지 않도록 더 짧은 두 줄 자막으로 나뉘어야 합니다.", content)

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
