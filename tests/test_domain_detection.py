import unittest

from app.services.domain_detection import (
    is_ai_policy_conflict_domain,
    is_agriculture_environment_domain,
    is_ev_battery_domain,
    is_food_trend_domain,
    is_news_explainer_domain,
    is_tech_domain,
)
from app.types import ProjectRecord


def _project(**overrides: object) -> ProjectRecord:
    payload: ProjectRecord = {
        "id": "domain-test",
        "title": "latest ai news",
        "script": "",
        "content_mode": "standard",
        "visual_source_mode": "hybrid",
        "user_script": "",
        "compiled_script": "",
        "regional_sentences": [],
        "bible_query": "",
        "selected_verses": [],
        "bible_background_file": "",
        "body_image_state": "idle",
        "body_image_progress": 0,
        "body_image_error": "",
        "body_image_mappings": [],
        "body_image_job_id": "",
        "body_image_started_at": "",
        "body_image_heartbeat_at": "",
        "body_image_phase": "",
        "body_image_last_log": "",
        "body_image_options": {},
        "source_draft_state": "done",
        "source_draft_progress": 100,
        "source_draft_error": "",
        "source_draft_input_mode": "keyword",
        "source_draft_query": "",
        "source_draft_sources": [],
        "source_draft_fact_notes": [],
        "source_draft_script": "",
        "source_draft_previous_script": "",
        "source_draft_warnings": [],
        "source_draft_model": "",
        "source_draft_risk_score": 0.0,
        "source_draft_regenerate_mode": "",
        "source_draft_regenerate_note": "",
        "source_draft_job_id": "",
        "source_draft_started_at": "",
        "source_draft_heartbeat_at": "",
        "source_draft_phase": "",
        "source_draft_last_log": "",
        "source_draft_options": {},
        "autopilot_state": "idle",
        "autopilot_progress": 0,
        "autopilot_phase": "",
        "autopilot_last_log": "",
        "autopilot_error": "",
        "autopilot_job_id": "",
        "autopilot_started_at": "",
        "autopilot_heartbeat_at": "",
        "autopilot_options": {},
        "autopilot_last_error_code": "",
        "autopilot_debug_summary": "",
        "autopilot_wait_started_at": "",
        "autopilot_retry_count": 0,
        "scene_plan": None,
        "render_plan": None,
        "sentences": [],
        "media_order": [],
        "thumbnail_file": "",
        "subtitle_style": {
            "font_family": "Malgun Gothic",
            "font_size": 48,
            "primary_color": "#FFFFFF",
            "outline_color": "#000000",
            "background_color": "#000000",
            "background_opacity": 0.0,
            "outline_width": 2,
            "shadow": 1,
            "position": "bottom",
            "margin_h": 120,
            "margin_v": 80,
            "max_line_chars": 26,
            "min_display_sec": 1.0,
            "effect": "none",
        },
        "voice_preset": "auto",
        "tts_profile": {
            "mode": "auto",
            "seed_mode": "per_sentence",
            "language": "ko",
            "instruct": "",
            "speed": 1.0,
            "duration": None,
            "num_step": 32,
            "guidance_scale": 2.6,
            "denoise": True,
            "postprocess_output": True,
            "seed": None,
        },
        "kenburns_enabled": True,
        "bgm_file": "",
        "bgm_volume_db": -20,
        "bgm_ducking_enabled": True,
        "render_formats": ["landscape"],
        "youtube_schedule_at": "",
        "tts_state": "idle",
        "tts_progress": 0,
        "tts_error": "",
        "tts_job_id": "",
        "tts_started_at": "",
        "tts_heartbeat_at": "",
        "render_state": "idle",
        "render_progress": 0,
        "render_phase": "",
        "render_phase_pct": 0,
        "render_progress_detail": "",
        "render_speed_x": 0.0,
        "render_eta_sec": 0,
        "render_job_id": "",
        "render_started_at": "",
        "render_heartbeat_at": "",
        "render_last_log": "",
        "upload_state": "idle",
        "upload_progress": 0,
        "media_upload_state": "idle",
        "media_upload_progress": 0,
        "media_upload_completed": 0,
        "media_upload_total": 0,
        "media_upload_error": "",
        "youtube_id": None,
        "created_at": "",
        "updated_at": "",
    }
    for key, value in overrides.items():
        payload[str(key)] = value  # type: ignore[literal-required]
    return payload


class DomainDetectionTests(unittest.TestCase):
    def test_research_alone_is_not_tech(self) -> None:
        project = _project(
            title="quiet science note",
            compiled_script="A research team published a careful field study.",
            source_draft_fact_notes=[],
            source_draft_sources=[],
        )
        self.assertFalse(is_tech_domain(project, "The research was discussed in a short article."))

    def test_research_with_ai_is_tech(self) -> None:
        project = _project(
            title="AI research update",
            compiled_script="AI research team trained a new model for inference.",
            source_draft_fact_notes=[],
            source_draft_sources=[],
        )
        self.assertTrue(is_tech_domain(project, "The research focused on model training."))

    def test_ai_policy_conflict_takes_policy_context(self) -> None:
        project = _project(
            title="Anthropic and US government clash",
            compiled_script=(
                "The White House restricted the spread of Anthropic Claude while "
                "a defense secretary criticized the company in a Senate hearing."
            ),
            source_draft_fact_notes=[],
            source_draft_sources=[],
        )
        self.assertTrue(is_ai_policy_conflict_domain(project, "The government intervention intensified."))
        self.assertTrue(is_tech_domain(project, "Claude is an AI model."))

    def test_research_with_soil_leaf_film_is_agriculture_environment(self) -> None:
        project = _project(
            title="leaf film research",
            compiled_script="Researchers made biodegradable mulch film from fallen leaves for soil and crop fields.",
            source_draft_fact_notes=[],
            source_draft_sources=[],
        )
        self.assertFalse(is_tech_domain(project, "Leaf film research for soil moisture."))
        self.assertTrue(is_agriculture_environment_domain(project, "Leaf film research for soil moisture."))

    def test_is_tech_domain_uses_notes_and_source_context(self) -> None:
        project = _project(
            title="quiet essay",
            source_draft_fact_notes=[{"source_id": "src1", "note": "browser automation with javascript runtime"}],
            source_draft_sources=[
                {
                    "id": "src1",
                    "url": "https://example.com",
                    "final_url": "https://example.com",
                    "title": "Obscura browser automation",
                    "domain": "example.com",
                    "author": "",
                    "published_at": "",
                    "language": "en",
                    "excerpt": "headless browser and cdp",
                    "fetched_at": "",
                    "word_count": 120,
                }
            ],
        )
        self.assertTrue(is_tech_domain(project, "A calm description with no explicit tech nouns."))

    def test_is_news_explainer_domain_detects_comment_election_context(self) -> None:
        project = _project(
            title="네이버 뉴스 댓글 관리",
            compiled_script="대선을 앞두고 댓글 공감과 비공감 급증을 감지합니다.",
        )
        self.assertTrue(is_news_explainer_domain(project, "언론사에 알림과 메일을 보냅니다."))

    def test_is_food_trend_domain_detects_ube_article(self) -> None:
        project = _project(
            title="우베 디저트 트렌드",
            compiled_script="식품 업계에서 우베를 활용한 보라색 디저트와 음료 제품이 확산되고 있습니다.",
        )
        self.assertTrue(is_food_trend_domain(project, "편의점과 대형마트에서도 우베 음료가 출시됩니다."))
        self.assertFalse(is_news_explainer_domain(project, "편의점과 대형마트에서도 우베 음료가 출시됩니다."))

    def test_is_ev_battery_domain_detects_lfp_script(self) -> None:
        project = _project(
            title="전기차 LFP 배터리 전략",
            compiled_script="전기차 구매에서 LFP 배터리와 NCM 배터리, 전고체 배터리, K-배터리 기술 주권이 중요합니다.",
        )
        self.assertTrue(is_ev_battery_domain(project, "한국형 LFP는 에너지 밀도를 높이는 전략입니다."))
        self.assertFalse(is_food_trend_domain(project, "한국형 LFP는 에너지 밀도를 높이는 전략입니다."))


if __name__ == "__main__":
    unittest.main()
