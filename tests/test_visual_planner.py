import json
import unittest
from unittest.mock import patch

from app.services.visual_planner import (
    _fallback_entry,
    _normalize_entries,
    _planner_prompt,
    _planner_system_prompt,
    _quick_ollama_ready,
    build_scene_visual_plan,
)
from app.types import ProjectRecord


def _project(**overrides: object) -> ProjectRecord:
    payload: ProjectRecord = {
        "id": "planner-test",
        "title": "essay planner test",
        "script": "속도보다 방향이 중요합니다.",
        "content_mode": "standard",
        "visual_source_mode": "comfyui_auto",
        "user_script": "속도보다 방향이 중요합니다.",
        "compiled_script": "속도보다 방향이 중요합니다.",
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
        "source_draft_query": "에세이",
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
        "sentences": ["속도보다 방향이 중요합니다."],
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


class VisualPlannerTests(unittest.TestCase):
    def test_planner_system_prompt_references_single_operating_guide(self) -> None:
        prompt = _planner_system_prompt("tech")

        self.assertIn("docs/media-prompt-operating-guide.md", prompt)
        self.assertIn("semiconductor business news", prompt)
        self.assertIn("Nvidia", prompt)
        self.assertIn("Jensen Huang", prompt)
        self.assertIn("Set lora_policy to none", prompt)

    def test_planner_prompt_includes_compact_schema_extensions(self) -> None:
        project = _project(
            sentences=[
                "Jensen Huang joined the China business delegation after a direct request from Trump."
            ]
        )

        prompt = _planner_prompt(project, "tech", {"domain": "tech", "terms": []})

        self.assertIn('"sub_strategy": ""', prompt)
        self.assertIn('"template_hint": "txt2img_sdxl_basic"', prompt)
        self.assertIn('"lora_policy": "none"', prompt)
        self.assertIn("semiconductor_business_news", prompt)
        self.assertIn("txt2img_sdxl_stickman_lora", prompt)
        self.assertIn("lora_policy must be none", prompt)

    def test_normalize_entries_preserves_operating_guide_policy_fields(self) -> None:
        project = _project(sentences=["Jensen Huang joined the Nvidia delegation."])

        entries = _normalize_entries(
            project,
            [
                {
                    "sentence_idx": 0,
                    "core_meaning": "Jensen Huang joins Nvidia delegation",
                    "primary_keywords": ["Jensen Huang", "Nvidia"],
                    "must_show": ["Jensen Huang", "Nvidia delegation"],
                    "sub_strategy": "semiconductor_business_news",
                    "template_hint": "txt2img_sdxl_basic",
                    "lora_policy": "none",
                }
            ],
            domain="tech",
            source="llm",
        )

        self.assertEqual(entries[0]["sub_strategy"], "semiconductor_business_news")
        self.assertEqual(entries[0]["template_hint"], "txt2img_sdxl_basic")
        self.assertEqual(entries[0]["lora_policy"], "none")

    def test_quick_ollama_ready_checks_ollama_api_tags(self) -> None:
        request_urls: list[str] = []

        class _UrlOpenStub:
            def __enter__(self) -> "_UrlOpenStub":
                return self

            def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
                return None

            def read(self) -> bytes:
                return b'{"data":[{"id":"google/gemma-4-e4b"}]}'

        def fake_urlopen(request: object, timeout: float | int) -> "_UrlOpenStub":
            request_urls.append(request.full_url)  # type: ignore[attr-defined]
            return _UrlOpenStub()

        with patch("app.services.visual_planner.urlopen", side_effect=fake_urlopen), patch(
            "app.services.visual_planner.LLM_PROVIDER", "ollama"
        ), patch("app.services.visual_planner.OLLAMA_BASE_URL", "http://127.0.0.1:11434"):
            result = _quick_ollama_ready()

        self.assertTrue(result)
        self.assertEqual(len(request_urls), 1)
        self.assertTrue(request_urls[0].endswith("/api/tags"))

    def test_quick_ollama_ready_checks_lmstudio_models_endpoint(self) -> None:
        request_urls: list[str] = []

        class _UrlOpenStub:
            def __enter__(self) -> "_UrlOpenStub":
                return self

            def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
                return None

            def read(self) -> bytes:
                return b'{"data":[{"id":"google/gemma-4-e4b"}]}'

        def fake_urlopen(request: object, timeout: float | int) -> "_UrlOpenStub":
            request_urls.append(request.full_url)  # type: ignore[attr-defined]
            return _UrlOpenStub()

        with patch("app.services.visual_planner.urlopen", side_effect=fake_urlopen), patch(
            "app.services.visual_planner.LLM_PROVIDER", "lmstudio"
        ), patch("app.services.visual_planner.LMSTUDIO_BASE_URL", "http://127.0.0.1:1234"):
            with patch("app.services.visual_planner.loaded_lmstudio_models", return_value=[]):
                result = _quick_ollama_ready()

        self.assertTrue(result)
        self.assertEqual(len(request_urls), 1)
        self.assertTrue(request_urls[0].endswith("/v1/models"))

    def test_quick_ollama_ready_requires_loaded_lmstudio_model_when_available(self) -> None:
        with patch("app.services.visual_planner.LLM_PROVIDER", "lmstudio"), patch(
            "app.services.visual_planner.SCRIPT_LLM_MODEL", "google/gemma-4-e4b"
        ), patch("app.services.visual_planner.loaded_lmstudio_models", return_value=["qwen/qwen3.5-9b"]):
            self.assertFalse(_quick_ollama_ready())
        with patch("app.services.visual_planner.LLM_PROVIDER", "lmstudio"), patch(
            "app.services.visual_planner.SCRIPT_LLM_MODEL", "google/gemma-4-e4b"
        ), patch("app.services.visual_planner.loaded_lmstudio_models", return_value=["google/gemma-4-e4b"]):
            result = _quick_ollama_ready()

        self.assertTrue(result)

    def test_build_scene_visual_plan_falls_back_when_disabled(self) -> None:
        project = _project(body_image_options={"disable_llm_visual_planner": True})
        entries = build_scene_visual_plan(project)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["source"], "fallback")

    def test_build_scene_visual_plan_normalizes_llm_json(self) -> None:
        project = _project()
        llm_json = """
        [
          {
            "sentence_idx": 0,
            "sentence": "속도보다 방향이 중요합니다.",
            "core_meaning": "빠름보다 올바른 방향이 먼저라는 뜻",
            "primary_keywords": ["direction", "pace", "choice"],
            "secondary_keywords": ["city", "clock"],
            "visual_metaphor": "blurred city with a sharp compass on a map",
            "subject_modes": ["environment", "object_metaphor"],
            "must_show": ["compass on a map", "blurred city motion"],
            "may_show": ["clock"],
            "avoid": ["two similar people"],
            "prompt_hint": "medium wide shot",
            "vocab_refs": ["direction and life choice"]
          }
        ]
        """
        with patch("app.services.visual_planner._quick_ollama_ready", return_value=True), patch(
            "app.services.visual_planner.OllamaClient.warm",
            return_value=None,
        ), patch(
            "app.services.visual_planner.OllamaClient.unload",
            return_value=None,
        ), patch(
            "app.services.visual_planner.OllamaClient.generate",
            return_value=type("Resp", (), {"response": llm_json, "model": "gemma4:e4b"})(),
        ):
            entries = build_scene_visual_plan(project)
        self.assertEqual(entries[0]["source"], "llm")
        self.assertEqual(entries[0]["domain"], "essay")
        self.assertNotIn("compass on a map", entries[0]["must_show"])
        self.assertIn("route choice", entries[0]["must_show"])
        self.assertTrue(entries[0]["semantic_anchor_tokens"])

    def test_build_scene_visual_plan_batches_long_scripts(self) -> None:
        sentences = [f"Sentence {idx} about EV battery market." for idx in range(7)]
        project = _project(id="planner-batch-test", title="EV battery", compiled_script=" ".join(sentences), sentences=sentences)

        def response_for_batch(offset: int, size: int) -> object:
            items = [
                {
                    "sentence_idx": local_idx,
                    "sentence": sentences[offset + local_idx],
                    "core_meaning": f"meaning {offset + local_idx}",
                    "primary_keywords": ["battery", "electric vehicle"],
                    "secondary_keywords": ["market"],
                    "visual_metaphor": "battery market comparison",
                    "subject_modes": ["environment", "object_metaphor"],
                    "must_show": [f"battery cell comparison {offset + local_idx}"],
                    "may_show": ["electric car"],
                    "avoid": ["stick figure"],
                    "prompt_hint": "medium wide shot",
                    "vocab_refs": [],
                }
                for local_idx in range(size)
            ]
            return type("Resp", (), {"response": json.dumps(items), "model": "google/gemma-4-e4b"})()

        responses = [response_for_batch(0, 3), response_for_batch(3, 3), response_for_batch(6, 1)]
        with patch("app.services.visual_planner._quick_ollama_ready", return_value=True), patch(
            "app.services.visual_planner._load_cached_plan",
            return_value=None,
        ), patch(
            "app.services.visual_planner._save_plan",
            return_value=None,
        ), patch(
            "app.services.visual_planner.OllamaClient.warm",
            return_value=None,
        ), patch(
            "app.services.visual_planner.OllamaClient.unload",
            return_value=None,
        ), patch(
            "app.services.visual_planner.OllamaClient.generate",
            side_effect=responses,
        ) as generate:
            entries = build_scene_visual_plan(project)

        self.assertEqual(generate.call_count, 3)
        self.assertEqual([entry["sentence_idx"] for entry in entries], list(range(7)))
        self.assertEqual(entries[6]["sentence"], sentences[6])
        self.assertIn("battery cell comparison 6", entries[6]["must_show"])

    def test_fallback_entry_marks_literal_simile_priority(self) -> None:
        project = _project(sentences=["그 피로는 모래 위를 달리는 일과 비슷합니다."])
        entry = _fallback_entry(project, 0, project["sentences"][0], "essay")
        self.assertEqual(entry["source"], "fallback")
        self.assertEqual(entry["visual_priority"], "literal_simile")
        self.assertTrue(entry["literal_simile"])

    def test_news_explainer_fallback_uses_comment_domain_tokens(self) -> None:
        sentence = "핵심은 특정 기사에서 공감이나 비공감이 비정상적으로 급증하면 자동으로 감지하는 기능입니다."
        project = _project(
            title="네이버 뉴스 댓글 관리",
            compiled_script=sentence,
            sentences=[sentence],
        )
        entry = _fallback_entry(project, 0, sentence, "news_explainer")
        self.assertEqual(entry["source"], "fallback")
        self.assertEqual(entry["domain"], "news_explainer")
        self.assertIn("thumbs up and thumbs down counters rising sharply", entry["must_show"])
        self.assertIn("warning sensor icon beside an article card", entry["must_show"])
        self.assertNotIn("single everyday object in a quiet realistic room", entry["must_show"])

    def test_news_explainer_fallback_handles_vague_user_sentence(self) -> None:
        sentence = "이용자 입장에서도 의미가 있습니다."
        project = _project(
            title="네이버 뉴스 댓글 관리",
            compiled_script=sentence,
            sentences=[sentence],
        )
        entry = _fallback_entry(project, 0, sentence, "news_explainer")
        self.assertIn("user icon viewing a news comment panel", entry["must_show"])
        self.assertNotIn("single everyday object in a quiet realistic room", entry["must_show"])

    def test_agriculture_environment_fallback_uses_vocab_tokens(self) -> None:
        sentence = "Researchers made biodegradable mulch film from fallen leaves to protect soil moisture."
        project = _project(
            title="leaf film research",
            compiled_script=sentence,
            sentences=[sentence],
        )
        entry = _fallback_entry(project, 0, sentence, "agriculture_environment")
        self.assertEqual(entry["domain"], "agriculture_environment")
        self.assertEqual(entry["composition_template"], "WasteToMaterial")
        self.assertIn("fallen leaves transforming into thin translucent mulch film sheet", entry["must_show"])
        self.assertIn("arrow from leaf pile to finished material roll", entry["must_show"])

    def test_food_trend_fallback_uses_ube_vocab_tokens(self) -> None:
        sentence = "그 중심에는 바로 보랏빛의 매력을 지닌 우베가 있습니다."
        project = _project(
            title="우베 디저트 트렌드",
            compiled_script=sentence,
            sentences=[sentence],
        )
        entry = _fallback_entry(project, 0, sentence, "food_trend")
        self.assertEqual(entry["domain"], "food_trend")
        self.assertEqual(entry["composition_template"], "IngredientHero")
        self.assertIn("purple yam with cut violet flesh", entry["must_show"])
        self.assertIn("ube cream dessert and purple whipped topping", entry["must_show"])
        self.assertNotIn("single everyday object in a quiet realistic room", entry["must_show"])

    def test_ev_battery_fallback_uses_battery_vocab_tokens(self) -> None:
        sentence = "비싼 가격이 전기차 대중화의 걸림돌이었죠."
        project = _project(
            title="전기차 LFP 배터리 전략",
            compiled_script="LFP와 NCM, 전고체 배터리 경쟁이 이어집니다.",
            sentences=[sentence],
        )
        entry = _fallback_entry(project, 0, sentence, "ev_battery")
        self.assertEqual(entry["domain"], "ev_battery")
        self.assertEqual(entry["composition_template"], "PriceBarrier")
        self.assertIn("electric car stopped before a tall price barrier", entry["must_show"])
        self.assertIn("large price tag blocking the road", entry["must_show"])
        self.assertNotIn("concrete visual subject tied to the sentence", entry["must_show"])

    def test_build_scene_visual_plan_repairs_generic_essay_entry(self) -> None:
        project = _project(sentences=["오늘 한 페이지를 읽고, 한 문장을 쓰고, 한 사람에게 진심을 다하는 일이 중요합니다."])
        llm_json = """
        [
          {
            "sentence_idx": 0,
            "sentence": "오늘 한 페이지를 읽고, 한 문장을 쓰고, 한 사람에게 진심을 다하는 일이 중요합니다.",
            "core_meaning": "small concrete actions rebuild direction",
            "primary_keywords": ["large checklist with three bold check marks"],
            "secondary_keywords": [],
            "visual_metaphor": "simple symbolic scene",
            "subject_modes": ["environment", "object_metaphor"],
            "must_show": ["large checklist with three bold check marks"],
            "may_show": [],
            "avoid": ["text"],
            "prompt_hint": "medium or wide shot",
            "vocab_refs": [],
            "visual_priority": "core_metaphor",
            "literal_simile": "",
            "allow_objects": []
          }
        ]
        """
        with patch("app.services.visual_planner._quick_ollama_ready", return_value=True), patch(
            "app.services.visual_planner.OllamaClient.warm",
            return_value=None,
        ), patch(
            "app.services.visual_planner.OllamaClient.unload",
            return_value=None,
        ), patch(
            "app.services.visual_planner.OllamaClient.generate",
            return_value=type("Resp", (), {"response": llm_json, "model": "gemma4:e4b"})(),
        ):
            entries = build_scene_visual_plan(project)
        self.assertEqual(entries[0]["source"], "essay_semantic_repair")
        self.assertIn("open book page", entries[0]["must_show"])

    def test_fallback_entry_uses_finance_semantic_tokens_instead_of_raw_glue(self) -> None:
        sentence = (
            "\ud558\uc9c0\ub9cc \uc2e4\uc81c \uae08\uc735 \ud604\uc7a5\uc758 \ubcf5\uc7a1\ud55c \uacfc\uc81c\uc5d0 "
            "\uc801\uc6a9\ud558\uc5ec \uc2e4\uc9c8\uc801\uc778 \uc194\ub8e8\uc158\uc744 \uac1c\ubc1c\ud558\ub294 \uacfc\uc815\uc5d0\uc11c, "
            "\uae30\uc220\uc801 \ud55c\uacc4\uc810\ub4e4\uc774 \ub4dc\ub7ec\ub098\uae30 \uc2dc\uc791\ud588\uc2b5\ub2c8\ub2e4."
        )
        project = _project(
            title="\uae08\uc735 \uc591\uc790 \ucef4\ud4e8\ud305",
            compiled_script=sentence,
            sentences=[sentence],
        )
        entry = _fallback_entry(project, 0, sentence, "essay")
        joined_keywords = " ".join(entry["primary_keywords"]).lower()
        joined_must_show = " ".join(entry["must_show"]).lower()
        self.assertIn("financial analyst desk", joined_keywords)
        self.assertIn("technical barrier", joined_must_show)
        self.assertNotIn("\uc2e4\uc81c", joined_keywords)
        self.assertNotIn("\uacfc\uc815", joined_keywords)
        self.assertEqual(entry["semantic_anchor_type"], "technical_barrier")
        self.assertTrue(entry["semantic_anchor_tokens"])
        self.assertIn("technical barrier", " ".join(entry["semantic_anchor_tokens"]).lower())

    def test_build_scene_visual_plan_keeps_llm_semantic_anchor_fields(self) -> None:
        project = _project()
        llm_json = """
        [
          {
            "sentence_idx": 0,
            "sentence": "?띾룄蹂대떎 諛⑺뼢??以묒슂?⑸땲??",
            "core_meaning": "Direction matters more than speed.",
            "primary_keywords": ["direction", "pace", "choice"],
            "secondary_keywords": ["path split"],
            "visual_metaphor": "clear route choice with restrained pace",
            "subject_modes": ["environment", "object_metaphor"],
            "must_show": ["route choice", "pace marker"],
            "may_show": ["goal light"],
            "avoid": ["two similar people"],
            "prompt_hint": "medium wide shot",
            "vocab_refs": ["direction and life choice"],
            "visual_mode": "symbolic_concept",
            "semantic_anchor_type": "future_outlook",
            "semantic_anchor_tokens": ["route choice", "pace marker", "goal light"]
          }
        ]
        """
        with patch("app.services.visual_planner._quick_ollama_ready", return_value=True), patch(
            "app.services.visual_planner.OllamaClient.warm",
            return_value=None,
        ), patch(
            "app.services.visual_planner.OllamaClient.unload",
            return_value=None,
        ), patch(
            "app.services.visual_planner.OllamaClient.generate",
            return_value=type("Resp", (), {"response": llm_json, "model": "gemma4:e4b"})(),
        ):
            entries = build_scene_visual_plan(project)
        self.assertEqual(entries[0]["semantic_anchor_type"], "future_outlook")
        self.assertEqual(entries[0]["semantic_anchor_tokens"], ["route choice", "pace marker", "goal light"])

    def test_build_scene_visual_plan_diversifies_finance_quantum_visual_modes(self) -> None:
        project = _project(
            title="quantum finance article",
            compiled_script=(
                "\ud55c\ub54c \uae08\uc735\uacc4\ub97c \ubc14\uafc0 '\uac8c\uc784 \uccb4\uc778\uc800'\ub85c \ubd88\ub838\ub358 \uc591\uc790 \ucef4\ud4e8\ud305 \uae30\uc220.\n"
                "\ud558\uc9c0\ub9cc \uc2e4\uc81c \uae08\uc735 \ud604\uc7a5\uc758 \ubcf5\uc7a1\ud55c \uacfc\uc81c\uc5d0 \uc801\uc6a9\ud558\ub294 \uacfc\uc815\uc5d0\uc11c \uae30\uc220\uc801 \ud55c\uacc4\uc810\ub4e4\uc774 \ub4dc\ub7ec\ub098\uae30 \uc2dc\uc791\ud588\uc2b5\ub2c8\ub2e4.\n"
                "\uc77c\ubd80 \uae30\uad00\ub4e4\uc740 \uc18d\ub3c4\ub97c \ub290\ucd94\ub294 \ubaa8\uc2b5\uc744 \ubcf4\uc774\uc9c0\ub9cc \ub2e4\ub978 \uc8fc\uc694 \uae08\uc735\uc0ac\ub4e4\uc740 \uc5ec\uc804\ud788 \uc591\uc790 \ucef4\ud4e8\ud305\uc744 \ubbf8\ub798 \uc131\uc7a5 \ub3d9\ub825\uc73c\ub85c \ubcf4\uace0 \ud22c\uc790\ud569\ub2c8\ub2e4."
            ),
            sentences=[
                "\ud55c\ub54c \uae08\uc735\uacc4\ub97c \ubc14\uafc0 '\uac8c\uc784 \uccb4\uc778\uc800'\ub85c \ubd88\ub838\ub358 \uc591\uc790 \ucef4\ud4e8\ud305 \uae30\uc220.",
                "\ud558\uc9c0\ub9cc \uc2e4\uc81c \uae08\uc735 \ud604\uc7a5\uc758 \ubcf5\uc7a1\ud55c \uacfc\uc81c\uc5d0 \uc801\uc6a9\ud558\ub294 \uacfc\uc815\uc5d0\uc11c \uae30\uc220\uc801 \ud55c\uacc4\uc810\ub4e4\uc774 \ub4dc\ub7ec\ub098\uae30 \uc2dc\uc791\ud588\uc2b5\ub2c8\ub2e4.",
                "\uc77c\ubd80 \uae30\uad00\ub4e4\uc740 \uc18d\ub3c4\ub97c \ub290\ucd94\ub294 \ubaa8\uc2b5\uc744 \ubcf4\uc774\uc9c0\ub9cc \ub2e4\ub978 \uc8fc\uc694 \uae08\uc735\uc0ac\ub4e4\uc740 \uc5ec\uc804\ud788 \uc591\uc790 \ucef4\ud4e8\ud305\uc744 \ubbf8\ub798 \uc131\uc7a5 \ub3d9\ub825\uc73c\ub85c \ubcf4\uace0 \ud22c\uc790\ud569\ub2c8\ub2e4.",
            ],
            body_image_options={"disable_llm_visual_planner": True},
        )
        entries = build_scene_visual_plan(project)
        self.assertEqual(entries[0]["visual_mode"], "symbolic_concept")
        self.assertEqual(entries[1]["visual_mode"], "data_diagram")
        self.assertNotEqual(entries[2]["visual_mode"], entries[1]["visual_mode"])

    def test_fallback_entry_uses_anchor_driven_scene_fields_for_future_outlook(self) -> None:
        sentence = "\uc55e\uc73c\ub85c \uc5b4\ub5a4 \ubc29\ud5a5\uc73c\ub85c \uae30\uc220 \uac1c\ubc1c\uacfc \ud22c\uc790\uac00 \uc774\ub8e8\uc5b4\uc9c8\uc9c0 \uadc0\ucd94\uac00 \uc8fc\ubaa9\ub429\ub2c8\ub2e4."
        project = _project(
            title="\uae08\uc735 \uc591\uc790 \ucef4\ud4e8\ud305",
            compiled_script=sentence,
            sentences=[sentence],
        )
        entry = _fallback_entry(project, 0, sentence, "essay")
        self.assertEqual(entry["semantic_anchor_type"], "future_outlook")
        self.assertEqual(entry["visual_mode"], "symbolic_concept")
        self.assertEqual(entry["scene_anchor"], "future outlook concept environment")

    def test_fallback_entry_uses_anchor_driven_scene_fields_for_market_structure(self) -> None:
        sentence = "\ud3ec\ud2b8\ud3f4\ub9ac\uc624 \ucd5c\uc801\ud654\uc640 \ubcf5\uc7a1\ud55c \uc2dc\uc7a5 \ubcc0\ub3d9\uc131 \uc608\uce21\uc774 \ud575\uc2ec \uacfc\uc81c\uc785\ub2c8\ub2e4."
        project = _project(
            title="\uae08\uc735 \uc591\uc790 \ucef4\ud4e8\ud305",
            compiled_script=sentence,
            sentences=[sentence],
        )
        entry = _fallback_entry(project, 0, sentence, "essay")
        self.assertEqual(entry["semantic_anchor_type"], "market_structure")
        self.assertEqual(entry["visual_mode"], "data_diagram")
        self.assertEqual(entry["scene_anchor"], "plain warm portfolio comparison background")


if __name__ == "__main__":
    unittest.main()
