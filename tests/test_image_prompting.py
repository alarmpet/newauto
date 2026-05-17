import unittest
from unittest.mock import patch
from typing import cast

from app.services.image_prompting import suggest_image_prompt, suggest_image_prompt_batch
from app.types import ProjectRecord, VisualPlanEntry


def _project(**overrides: object) -> ProjectRecord:
    payload: ProjectRecord = {
        "id": "p1",
        "title": "test",
        "script": "첫 문장",
        "content_mode": "standard",
        "visual_source_mode": "hybrid",
        "user_script": "첫 문장",
        "compiled_script": "첫 문장\n둘째 문장",
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
        "body_image_options": {"disable_llm_visual_planner": True},
        "source_draft_state": "done",
        "source_draft_progress": 100,
        "source_draft_error": "",
        "source_draft_input_mode": "url",
        "source_draft_query": "",
        "source_draft_sources": [
            {
                "id": "src1",
                "url": "https://example.com/a",
                "final_url": "https://example.com/a",
                "title": "Example Article",
                "domain": "example.com",
                "author": "",
                "published_at": "",
                "language": "ko",
                "excerpt": "요약",
                "fetched_at": "",
                "word_count": 120,
            }
        ],
        "source_draft_fact_notes": [
            {"source_id": "src1", "note": "중요 사실 하나"},
            {"source_id": "src1", "note": "중요 사실 둘"},
        ],
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
        "sentences": ["첫 문장", "둘째 문장"],
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
        if key == "body_image_options" and isinstance(value, dict):
            merged_options = dict(payload["body_image_options"])
            merged_options.update(value)
            payload["body_image_options"] = merged_options
            continue
        payload[cast(str, key)] = value  # type: ignore[literal-required]
    return payload


class ImagePromptingTests(unittest.TestCase):
    def test_suggest_image_prompt_uses_reference_library(self) -> None:
        payload = suggest_image_prompt(_project(), 1)
        positive_prompt = cast(str, payload["positive_prompt"])
        style_hint = cast(str, payload["style_hint"])
        visual_tokens = cast(list[str], payload["visual_tokens"])
        visual_brief = cast(dict[str, object], payload["visual_brief"])
        template_key = cast(str, payload["template_key"])
        reference_names = cast(list[str], payload["reference_names"])
        missing_must_show = cast(list[str], payload["missing_must_show"])

        self.assertEqual(payload["sentence_idx"], 1)
        self.assertNotIn("Flipchartvisu", positive_prompt)
        self.assertNotIn("Stick figure", positive_prompt)
        self.assertIn("minimalist 2d stickman explainer poster", style_hint)
        self.assertGreaterEqual(len(visual_tokens), 1)
        self.assertEqual(template_key, "default")
        self.assertIn("Civitai Stickfigures SDXL LoRA", reference_names)
        self.assertIn("sentence_hash", payload)
        self.assertIn("must_show", visual_brief)
        self.assertGreaterEqual(len(cast(list[str], visual_brief["must_show"])), 1)
        self.assertEqual(missing_must_show, [])

    def test_suggest_image_prompt_batch_stops_at_last_sentence(self) -> None:
        prompts = suggest_image_prompt_batch(
            _project(
                sentences=["first sentence", "second sentence"],
                compiled_script="first sentence\nsecond sentence",
            ),
            start_idx=1,
            count=48,
        )

        self.assertEqual(len(prompts), 1)
        self.assertEqual(prompts[0]["sentence_idx"], 1)
        self.assertEqual(prompts[0]["sentence"], "second sentence")

    def test_suggest_image_prompt_detects_ai_project_as_tech_domain(self) -> None:
        payload = suggest_image_prompt(
            _project(
                title="latest ai news",
                compiled_script="AI 모델 학습과 GPU 인프라 변화",
                sentences=["AI 모델 학습 인프라가 빠르게 바뀌고 있습니다."],
            ),
            0,
        )
        positive_prompt = cast(str, payload["positive_prompt"])
        visual_brief = cast(dict[str, object], payload["visual_brief"])
        self.assertNotIn("Stick figure", positive_prompt)
        self.assertEqual(visual_brief["domain"], "tech")
        self.assertEqual(payload["template_key"], "tech_documentary")
        self.assertEqual(payload["recommended_style_preset"], "editorial_symbolic")

    def test_generic_visual_plan_uses_basic_editorial_not_stickman(self) -> None:
        payload = suggest_image_prompt(
            _project(sentences=["Jensen Huang joined the Nvidia China delegation after a Trump request."]),
            0,
            visual_plan_entry={
                "sentence_idx": 0,
                "sentence": "Jensen Huang joined the Nvidia China delegation after a Trump request.",
                "core_meaning": "Executive delegation news",
                "primary_keywords": ["Jensen Huang", "Nvidia", "delegation"],
                "secondary_keywords": [],
                "visual_metaphor": "formal executive arrival",
                "subject_modes": ["person", "environment"],
                "must_show": ["grounded editorial scene with one dominant real-world subject"],
                "may_show": [],
                "avoid": [],
                "prompt_hint": "formal executive arrival",
                "vocab_refs": [],
                "domain": "generic",
                "source": "fallback",
                "visual_priority": "literal",
                "literal_simile": "",
                "allow_objects": [],
                "composition_template": "",
                "scene_anchor": "grounded editorial environment",
                "hero_subject": "executive delegation arrival",
                "symbolic_marker": "",
                "visual_mode": "editorial_scene",
                "semantic_anchor_type": "generic",
                "semantic_anchor_tokens": ["jensen", "nvidia", "delegation"],
            },
        )

        positive_prompt = cast(str, payload["positive_prompt"])
        self.assertEqual(payload["template_id"], "txt2img_sdxl_basic")
        self.assertEqual(payload["lora_strength"], 0.0)
        self.assertNotIn("Flipchartvisu", positive_prompt)
        self.assertNotIn("Stick figure", positive_prompt)

    def test_jensen_delegation_uses_simple_news_caricature(self) -> None:
        payload = suggest_image_prompt(
            _project(
                sentences=[
                    "젠슨 황(Jensen Huang) 엔비디아(Nvidia) CEO가 트럼프 대통령의 요청으로 방중 경제사절단에 합류했다."
                ],
                autopilot_options={"quality_mode": "fast"},
            ),
            0,
        )

        positive_prompt = cast(str, payload["positive_prompt"])
        negative_prompt = cast(str, payload["negative_prompt"])
        visual_brief = cast(dict[str, object], payload["visual_brief"])
        self.assertEqual(payload["template_key"], "news_caricature")
        self.assertEqual(payload["template_id"], "txt2img_sdxl_basic")
        self.assertEqual(payload["lora_strength"], 0.0)
        self.assertIn("simple 2d caricature", positive_prompt)
        self.assertIn("presidential figure", positive_prompt)
        self.assertIn("fantasy landscape", negative_prompt)
        self.assertEqual(visual_brief["sub_strategy"], "political_business_delegation")

    def test_disabled_llm_visual_planner_still_uses_deterministic_fallback_plan(self) -> None:
        sentence = "DAU increased 60% after the AI image model launch."
        prompts = suggest_image_prompt_batch(
            _project(
                title="latest AI news ChatGPT Image 2.0 AI model GPU",
                compiled_script=sentence,
                sentences=[sentence],
                body_image_options={
                    "disable_llm_visual_planner": True,
                    "style_preset": "simple_diagram",
                },
            ),
            start_idx=0,
            count=1,
        )

        self.assertEqual(len(prompts), 1)
        payload = prompts[0]
        visual_plan = cast(dict[str, object], payload["visual_plan"])
        visual_brief = cast(dict[str, object], payload["visual_brief"])
        positive_prompt = cast(str, payload["positive_prompt"]).lower()

        self.assertEqual(visual_plan["source"], "fallback")
        self.assertEqual(visual_plan["domain"], "tech")
        self.assertEqual(visual_plan["composition_template"], "GrowthMetricComparison")
        self.assertEqual(visual_brief["composition_template"], "GrowthMetricComparison")
        self.assertTrue("60 percent" in positive_prompt or "60%" in positive_prompt)
        self.assertIn("rising bars", positive_prompt)

    def test_bible_mode_uses_biblical_style(self) -> None:
        payload = suggest_image_prompt(_project(content_mode="bible_longform"), 0)
        positive_prompt = cast(str, payload["positive_prompt"])
        negative_prompt = cast(str, payload["negative_prompt"])
        self.assertIn("minimalist 2d stickman biblical poster", positive_prompt)
        self.assertIn("photorealistic face", negative_prompt)

    def test_suggest_image_prompt_applies_k_webtoon_style_preset(self) -> None:
        payload = suggest_image_prompt(
            _project(
                body_image_options={"style_preset": "k_webtoon"},
                sentences=["조용한 아침에 한 사람이 창가에서 오늘의 방향을 생각합니다."],
            ),
            0,
        )
        positive_prompt = cast(str, payload["positive_prompt"])
        style_hint = cast(str, payload["style_hint"])
        self.assertIn("korean webtoon illustration", positive_prompt)
        self.assertIn("korean webtoon illustration", style_hint)
        self.assertIn("cinematic webtoon panel shot", positive_prompt)
        keyword_coverage = cast(dict[str, object], payload["keyword_coverage"])
        issue_codes = cast(list[str], keyword_coverage["issue_codes"])
        self.assertNotIn("GENERIC_SYMBOL_WITHOUT_ALLOW", issue_codes)
        self.assertNotIn("RAW_TEXT_VISUAL_TARGET", issue_codes)

    def test_suggest_image_prompt_applies_simple_diagram_style_preset(self) -> None:
        payload = suggest_image_prompt(
            _project(
                body_image_options={"style_preset": "simple_diagram"},
                title="AI agent workflow",
                sentences=["AI 에이전트가 일정과 결제와 메시지를 한 번에 처리합니다."],
            ),
            0,
        )
        positive_prompt = cast(str, payload["positive_prompt"])
        negative_prompt = cast(str, payload["negative_prompt"])
        visual_brief = cast(dict[str, object], payload["visual_brief"])
        self.assertIn("simple flat explainer illustration", positive_prompt)
        self.assertIn("large readable icons", positive_prompt)
        self.assertNotIn("35mm lens", positive_prompt)
        self.assertNotIn("detailed real-world textures", positive_prompt)
        self.assertTrue(
            "large readable icons" in positive_prompt
            or "simple flat explainer illustration" in positive_prompt
        )
        self.assertIn("photorealistic", negative_prompt)
        self.assertEqual(visual_brief["main_subject"], "simple centered explainer icon composition")
        keyword_coverage = cast(dict[str, object], payload["keyword_coverage"])
        issue_codes = cast(list[str], keyword_coverage["issue_codes"])
        self.assertNotIn("GENERIC_SYMBOL_WITHOUT_ALLOW", issue_codes)
        self.assertNotIn("DIAGRAM_STYLE_COLLISION", issue_codes)
        self.assertEqual(payload["requested_style_preset"], "simple_diagram")
        self.assertEqual(payload["recommended_style_preset"], "")
        self.assertEqual(payload["template_id"], "txt2img_sdxl_basic")
        self.assertEqual(payload["lora_name"], "")
        self.assertEqual(payload["lora_strength"], 0.0)

    def test_suggest_image_prompt_applies_stickman_business_style_preset(self) -> None:
        payload = suggest_image_prompt(
            _project(
                body_image_options={"style_preset": "stickman_business"},
                title="Nvidia AI strategy",
                sentences=["Nvidia strategy turns GPU sales into a developer ecosystem engine."],
            ),
            0,
        )

        positive_prompt = cast(str, payload["positive_prompt"])
        negative_prompt = cast(str, payload["negative_prompt"])
        self.assertEqual(payload["requested_style_preset"], "stickman_business")
        self.assertEqual(payload["template_key"], "machine_pipeline")
        self.assertEqual(payload["template_id"], "txt2img_sdxl_stickman_lora")
        self.assertEqual(payload["lora_strength"], 0.8)
        self.assertIn("Stick figure", positive_prompt)
        self.assertIn("Flipchartvisu", positive_prompt)
        self.assertIn("blank signboards", positive_prompt)
        self.assertIn("no readable text", positive_prompt)
        self.assertIn("central mechanical pipeline machine", positive_prompt)
        self.assertNotIn("gpu rack cluster", positive_prompt)
        self.assertNotIn("35mm lens", positive_prompt)
        self.assertNotIn("detailed real-world textures", positive_prompt)
        self.assertNotIn("technology interface scene", positive_prompt)
        self.assertNotIn(", ,", positive_prompt)
        self.assertIn("youtube controls", negative_prompt)

    def test_stickman_business_style_selects_bottleneck_template(self) -> None:
        payload = suggest_image_prompt(
            _project(
                body_image_options={"style_preset": "stickman_business"},
                title="AI power infrastructure",
                sentences=["Power grid infrastructure becomes a bottleneck for AI data center growth."],
            ),
            0,
        )

        positive_prompt = cast(str, payload["positive_prompt"])
        self.assertEqual(payload["template_key"], "infrastructure_bottleneck")
        self.assertEqual(payload["template_id"], "txt2img_sdxl_stickman_lora")
        self.assertIn("funnel bottleneck", positive_prompt)

    def test_stickman_business_style_selects_scale_comparison_template(self) -> None:
        payload = suggest_image_prompt(
            _project(
                body_image_options={"style_preset": "stickman_business"},
                title="Copilot versus competitors",
                sentences=["Copilot is compared with competing models on a business value scale."],
            ),
            0,
        )

        positive_prompt = cast(str, payload["positive_prompt"])
        self.assertEqual(payload["template_key"], "scale_comparison")
        self.assertEqual(payload["template_id"], "txt2img_sdxl_stickman_lora")
        self.assertIn("balance scale", positive_prompt)

    def test_news_comment_project_recommends_simple_diagram(self) -> None:
        payload = suggest_image_prompt(
            _project(
                title="네이버 뉴스 댓글 관리",
                sentences=["네이버가 대선을 앞두고 뉴스 댓글 관리 방식을 바꾸기로 했습니다."],
            ),
            0,
        )
        self.assertEqual(payload["recommended_style_preset"], "simple_diagram")

    def test_ai_policy_project_recommends_editorial_symbolic(self) -> None:
        payload = suggest_image_prompt(
            _project(
                title="Anthropic government policy conflict",
                compiled_script="The White House blocked the spread of Claude models after a senate hearing.",
                sentences=["The White House blocked the spread of Claude models after a senate hearing."],
            ),
            0,
        )
        visual_brief = cast(dict[str, object], payload["visual_brief"])
        self.assertEqual(payload["recommended_style_preset"], "editorial_symbolic")
        self.assertEqual(visual_brief["domain"], "ai_policy_conflict")
        self.assertEqual(payload["template_key"], "editorial_symbolic")

    def test_simple_diagram_prefers_specific_tech_icon_over_generic_ai(self) -> None:
        payload = suggest_image_prompt(
            _project(
                body_image_options={"style_preset": "simple_diagram"},
                title="latest ai news",
                sentences=["흩어져 있는 여러 개의 GPU 자원을 하나의 거대한 자원처럼 묶습니다."],
            ),
            0,
        )
        positive_prompt = cast(str, payload["positive_prompt"])
        self.assertIn("stacked GPU rack icon", positive_prompt)
        self.assertNotIn("large central AI brain icon clearly visible", positive_prompt)

    def test_essay_visual_mode_simple_explainer_uses_explainer_template(self) -> None:
        sentence = "\ud55c\ub54c \uae08\uc735\uacc4\ub97c \ubc14\uafc0 \uac8c\uc784 \uccb4\uc778\uc800\ub85c \ubd88\ub838\ub358 \uc591\uc790 \ucef4\ud4e8\ud305 \uae30\uc220."
        payload = suggest_image_prompt(
            _project(
                title="\uae08\uc735 \uc591\uc790 \ucef4\ud4e8\ud305",
                compiled_script=sentence,
                sentences=[sentence],
                body_image_options={"disable_llm_visual_planner": True},
            ),
            0,
        )
        visual_brief = cast(dict[str, object], payload["visual_brief"])
        positive_prompt = cast(str, payload["positive_prompt"]).lower()
        self.assertEqual(visual_brief["visual_mode"], "symbolic_concept")
        self.assertEqual(payload["template_key"], "essay_symbolic")
        self.assertIn("premium editorial illustration", positive_prompt)
        self.assertNotIn("monitor wall", positive_prompt)

    def test_essay_visual_mode_symbolic_concept_avoids_generic_office_prompt(self) -> None:
        sentence = "\ud558\uc9c0\ub9cc \uc2e4\uc81c \uae08\uc735 \ud604\uc7a5\uc758 \ubcf5\uc7a1\ud55c \uacfc\uc81c\uc5d0 \uc801\uc6a9\ud558\ub294 \uacfc\uc815\uc5d0\uc11c \uae30\uc220\uc801 \ud55c\uacc4\uc810\ub4e4\uc774 \ub4dc\ub7ec\ub098\uae30 \uc2dc\uc791\ud588\uc2b5\ub2c8\ub2e4."
        payload = suggest_image_prompt(
            _project(
                title="\uae08\uc735 \uc591\uc790 \ucef4\ud4e8\ud305",
                compiled_script=sentence,
                sentences=[sentence],
                body_image_options={"disable_llm_visual_planner": True},
            ),
            0,
        )
        visual_brief = cast(dict[str, object], payload["visual_brief"])
        negative_prompt = cast(str, payload["negative_prompt"]).lower()
        self.assertEqual(visual_brief["visual_mode"], "symbolic_concept")
        self.assertEqual(payload["template_key"], "essay_symbolic")
        self.assertIn("monitor wall", negative_prompt)
        self.assertEqual(visual_brief["semantic_anchor_type"], "technical_barrier")
        self.assertTrue(cast(list[str], visual_brief["semantic_anchor_tokens"]))

    def test_simple_diagram_handles_korean_company_shift_sentence(self) -> None:
        payload = suggest_image_prompt(
            _project(
                body_image_options={"style_preset": "simple_diagram"},
                title="latest ai news",
                sentences=["하지만 이제 구글과 같은 선도 기업들은 이 패러다임을 바꾸고 있습니다."],
            ),
            0,
        )
        positive_prompt = cast(str, payload["positive_prompt"])
        self.assertIn("company building icon", positive_prompt)
        self.assertIn("turning arrow and blueprint icon", positive_prompt)

    def test_suggest_image_prompt_maps_keyword_to_template(self) -> None:
        payload = suggest_image_prompt(
            _project(sentences=["소년은 돌멩이를 쥐고 거인을 향해 달려갑니다."]),
            0,
        )
        positive_prompt = cast(str, payload["positive_prompt"])
        visual_tokens = cast(list[str], payload["visual_tokens"])
        template_key = cast(str, payload["template_key"])

        self.assertIn("oversized sling and stone", positive_prompt)
        self.assertEqual(template_key, "giant_battle")
        self.assertTrue(any("stone" in token for token in visual_tokens))

    def test_suggest_image_prompt_uses_tech_vocab_for_browser_sentence(self) -> None:
        payload = suggest_image_prompt(
            _project(
                sentences=["Obscura는 오픈소스 헤드리스 브라우저 자동화 도구입니다."],
                source_draft_fact_notes=[{"source_id": "src1", "note": "browser automation with javascript runtime"}],
            ),
            0,
        )
        positive_prompt = cast(str, payload["positive_prompt"])
        visual_brief = cast(dict[str, object], payload["visual_brief"])
        visual_tokens = cast(list[str], payload["visual_tokens"])

        self.assertIn("browser window", positive_prompt)
        self.assertIn("automation cursor", positive_prompt)
        self.assertEqual(visual_brief["scene"], "clean software workspace")
        self.assertEqual(visual_brief["main_subject"], "technology interface scene")
        self.assertTrue(any("browser window" in token for token in visual_tokens))

    def test_suggest_image_prompt_uses_environmental_science_template(self) -> None:
        visual_plan_entry: VisualPlanEntry = {
            "sentence_idx": 0,
            "sentence": "Researchers made biodegradable mulch film from fallen leaves for soil moisture.",
            "core_meaning": "leaf waste becomes useful agricultural film",
            "primary_keywords": ["fallen leaves", "mulch film", "soil"],
            "secondary_keywords": ["crop row"],
            "visual_metaphor": "fallen leaves transform into translucent mulch film over protected soil",
            "subject_modes": ["environment", "object_metaphor"],
            "must_show": ["thin translucent mulch film sheet", "fallen leaves", "protected crop row"],
            "may_show": ["moist soil"],
            "avoid": ["AI brain icon", "technology dashboard"],
            "prompt_hint": "left-to-right before and after composition",
            "vocab_refs": ["leaf waste becomes mulch film"],
            "domain": "agriculture_environment",
            "source": "fallback",
            "visual_priority": "core_metaphor",
            "literal_simile": "",
            "allow_objects": [],
            "composition_template": "WasteToMaterial",
        }
        payload = suggest_image_prompt(
            _project(sentences=["Researchers made biodegradable mulch film from fallen leaves for soil moisture."]),
            0,
            visual_plan_entry=visual_plan_entry,
        )
        positive_prompt = cast(str, payload["positive_prompt"])
        negative_prompt = cast(str, payload["negative_prompt"])
        visual_brief = cast(dict[str, object], payload["visual_brief"])
        self.assertEqual(payload["template_key"], "environmental_science_editorial")
        self.assertEqual(payload["template_id"], "txt2img_sdxl_basic")
        self.assertEqual(visual_brief["domain"], "agriculture_environment")
        self.assertIn("clean agricultural documentary photography", positive_prompt)
        self.assertIn("thin translucent mulch film sheet", positive_prompt)
        self.assertIn("abstract dashboard", negative_prompt)
        self.assertEqual(payload["recommended_style_preset"], "")

    def test_suggest_image_prompt_repairs_quality_gate_gaps(self) -> None:
        visual_plan_entry: VisualPlanEntry = {
            "sentence_idx": 0,
            "sentence": "A reflective notebook scene.",
            "core_meaning": "reflection and focus",
            "primary_keywords": ["notebook", "desk"],
            "secondary_keywords": [],
            "visual_metaphor": "open notebook on a quiet desk",
            "subject_modes": ["environment"],
            "must_show": ["open notebook", "quiet desk"],
            "may_show": [],
            "avoid": [],
            "prompt_hint": "",
            "vocab_refs": [],
            "domain": "essay",
            "source": "llm",
            "visual_priority": "core_metaphor",
            "literal_simile": "",
            "allow_objects": [],
        }
        with patch("app.services.image_prompting.compile_positive_prompt", return_value="open notebook on desk"), patch(
            "app.services.image_prompting.compile_negative_prompt",
            return_value="text, logo, watermark",
        ):
            payload = suggest_image_prompt(
                _project(sentences=["A reflective notebook scene."]),
                0,
                visual_plan_entry=visual_plan_entry,
            )
        positive_prompt = cast(str, payload["positive_prompt"])
        negative_prompt = cast(str, payload["negative_prompt"])
        self.assertIn("medium wide shot", positive_prompt)
        self.assertIn("35mm lens", positive_prompt)
        self.assertIn("letters", negative_prompt)
        self.assertGreaterEqual(cast(int, payload["retry_count"]), 1)

    def test_finance_article_prompt_avoids_checklist_and_raw_korean_tokens(self) -> None:
        sentence = (
            "\uc77c\ubd80 \uae30\uad00\ub4e4\uc740 \uc18d\ub3c4\ub97c \ub0ae\ucd94\ub294 \ubaa8\uc2b5\uc744 \ubcf4\uc774\uc9c0\ub9cc, "
            "\ub2e4\ub978 \uc8fc\uc694 \uae08\uc735\uc0ac\ub4e4\uc740 \uc5ec\uc804\ud788 \uc591\uc790 \ucef4\ud4e8\ud305\uc744 \ubbf8\ub798 \uc131\uc7a5 "
            "\ub3d9\ub825\uc73c\ub85c \ubcf4\uace0 \ub9c9\ub300\ud55c \ud22c\uc790\ub97c \uc9c0\uc18d\ud558\uace0 \uc788\uc2b5\ub2c8\ub2e4."
        )
        payload = suggest_image_prompt(
            _project(
                title="\uae08\uc735 \uc591\uc790 \ucef4\ud4e8\ud305",
                compiled_script=sentence,
                sentences=[sentence],
            ),
            0,
        )
        positive_prompt = cast(str, payload["positive_prompt"]).lower()
        keyword_coverage = cast(dict[str, object], payload["keyword_coverage"])
        issue_codes = cast(list[str], keyword_coverage["issue_codes"])
        self.assertTrue(
            "institutional investment committee" in positive_prompt
            or "major bank strategy desk" in positive_prompt
            or "financial strategy desk" in positive_prompt
        )
        self.assertNotIn("large checklist with three bold check marks", positive_prompt)
        self.assertNotIn("\uc77c\ubd80", positive_prompt)
        self.assertNotIn("\uae30\uad00\ub4e4", positive_prompt)
        self.assertNotIn("RAW_TEXT_VISUAL_TARGET", issue_codes)

    def test_ev_battery_prompt_preserves_sentence_keywords(self) -> None:
        sentence = "단순히 중국을 뒤쫓는 것이 아니라, 에너지 밀도를 높인 한국형 LFP 기술로 차별화를 꾀하고 있습니다."
        payload = suggest_image_prompt(
            _project(
                title="전기차 LFP 배터리 전략",
                compiled_script="전기차 LFP와 NCM, 전고체 배터리 경쟁을 다룹니다.",
                sentences=[sentence],
            ),
            0,
        )
        positive_prompt = cast(str, payload["positive_prompt"]).lower()
        negative_prompt = cast(str, payload["negative_prompt"]).lower()
        visual_brief = cast(dict[str, object], payload["visual_brief"])

        self.assertEqual(visual_brief["domain"], "ev_battery")
        self.assertEqual(payload["template_key"], "ev_battery_explainer")
        self.assertEqual(payload["template_id"], "txt2img_sdxl_basic")
        self.assertEqual(payload["lora_name"], "")
        self.assertEqual(payload["lora_strength"], 0.0)
        self.assertIn("korean lfp battery", positive_prompt)
        self.assertIn("energy density", positive_prompt)
        self.assertIn("battery", positive_prompt)
        self.assertIn("flat 2d electric vehicle battery explainer diagram", positive_prompt)
        self.assertNotIn("stick figure", positive_prompt)
        self.assertNotIn("flipchartvisu", positive_prompt)
        self.assertIn("desert", negative_prompt)
        self.assertIn("glossy 3d cylinder battery only", negative_prompt)
        self.assertNotIn("grounded editorial scene with one dominant real-world subject", positive_prompt)

    def test_ev_battery_prompt_repair_includes_fourth_must_show(self) -> None:
        sentence = "LFP 배터리는 가격이 저렴하고 화재 위험이 낮지만 주행 거리는 조금 짧습니다."
        payload = suggest_image_prompt(
            _project(
                title="전기차 LFP 배터리 전략",
                compiled_script="전기차 LFP와 NCM, 전고체 배터리 경쟁을 다룹니다.",
                sentences=[sentence],
            ),
            0,
            visual_plan_entry={
                "sentence_idx": 0,
                "sentence": sentence,
                "core_meaning": "LFP battery tradeoff",
                "primary_keywords": ["LFP battery", "price", "safety", "range"],
                "secondary_keywords": [],
                "visual_metaphor": "LFP battery tradeoff comparison",
                "subject_modes": ["environment", "object_metaphor"],
                "must_show": ["LFP battery cell", "price tag", "safety shield icon", "range indicator"],
                "may_show": [],
                "avoid": [],
                "prompt_hint": "wide clean comparison",
                "vocab_refs": [],
                "domain": "ev_battery",
                "source": "llm",
                "visual_priority": "core_metaphor",
                "literal_simile": "",
                "allow_objects": [],
                "composition_template": "LfpTradeoff",
                "scene_anchor": "clean EV battery comparison",
                "hero_subject": "LFP battery cell",
                "symbolic_marker": "range indicator",
                "visual_mode": "symbolic_concept",
                "semantic_anchor_type": "comparison_frame",
                "semantic_anchor_tokens": ["LFP battery", "price", "safety", "range"],
            },
        )
        positive_prompt = cast(str, payload["positive_prompt"]).lower()
        keyword_coverage = cast(dict[str, object], payload["keyword_coverage"])
        self.assertIn("range indicator", positive_prompt)
        self.assertEqual(keyword_coverage["missing_must_show"], [])


if __name__ == "__main__":
    unittest.main()
