import json
import os
import unittest
from pathlib import Path
from typing import ClassVar, cast

from fastapi.testclient import TestClient

from app import db

os.environ.setdefault("NEWAUTO_DISABLE_BACKGROUND_WORKERS", "1")

from app.main import app
from app.services.preflight import build_preflight_report
from app.services.visual_relevance import (
    build_visual_relevance_rows,
    build_visual_mismatch_report,
    sentence_hash,
    summarize_visual_relevance,
    write_final_scene_review,
    validate_generated_image_mappings,
    write_visual_contact_sheet,
)


class VisualRelevanceTests(unittest.TestCase):
    client: ClassVar[TestClient]

    @classmethod
    def setUpClass(cls) -> None:
        db.init_db()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()

    def setUp(self) -> None:
        response = self.client.post("/api/projects", data={"title": "visual-relevance-test"})
        self.assertEqual(response.status_code, 200)
        self.project_id = str(response.json()["id"])

    def tearDown(self) -> None:
        self.client.delete(f"/api/projects/{self.project_id}")

    def _write_manifest(
        self,
        sentence: str,
        *,
        missing_must_show: list[str] | None = None,
        include_visual_brief: bool = True,
    ) -> str:
        manifest_path = db.project_dir(self.project_id) / "image_prompts_manifest.json"
        prompt_item: dict[str, object] = {
            "sentence_idx": 0,
            "sentence": sentence,
            "sentence_hash": sentence_hash(sentence),
            "positive_prompt": "prompt",
            "negative_prompt": "negative",
            "missing_must_show": missing_must_show or [],
        }
        if include_visual_brief:
            prompt_item["visual_brief"] = {
                "mode": "keyword_image",
                "main_subject": "single centered stick figure",
                "action": "holding the primary prop clearly",
                "primary_prop": "large checklist",
                "secondary_prop": "",
                "scene": "simple symbolic scene",
                "emotion": "calm and focused",
                "must_show": ["large checklist"],
                "avoid": ["text", "logo", "crowd"],
                "rationale": "test",
            }
        manifest_path.write_text(
            json.dumps(
                {
                    "project_id": self.project_id,
                    "prompts": [prompt_item],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return str(manifest_path)

    def test_generated_mapping_hash_matches_current_sentence(self) -> None:
        sentence = "현재 문장"
        manifest_path = self._write_manifest(sentence)
        db.update_project(
            self.project_id,
            visual_source_mode="comfyui_auto",
            sentences=[sentence],
            media_order=["scene.png"],
            body_image_options={"image_prompts_manifest_path": manifest_path},
            body_image_mappings=[
                {
                    "sentence_idx": 0,
                    "path": "scene.png",
                    "prompt": "prompt",
                    "sentence_text": sentence,
                    "sentence_hash": sentence_hash(sentence),
                    "project_id": self.project_id,
                    "prompt_id": "prompt-1",
                    "manifest_sentence_hash": sentence_hash(sentence),
                }
            ],
        )
        project = db.get_project(self.project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertEqual(validate_generated_image_mappings(project), [])

    def test_hybrid_generated_low_score_mapping_is_reported(self) -> None:
        sentence = "?꾩옱 臾몄옣"
        manifest_path = self._write_manifest(sentence)
        payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        payload["prompts"][0]["visual_brief"]["domain"] = "news_explainer"
        Path(manifest_path).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        db.update_project(
            self.project_id,
            visual_source_mode="hybrid",
            sentences=[sentence],
            media_order=["scene.png"],
            body_image_options={
                "image_prompts_manifest_path": manifest_path,
                "candidate_reviews": {
                    "0": {
                        "retry_recommended": True,
                        "retry_reason": "low_candidate_score",
                    }
                },
            },
            body_image_mappings=[
                {
                    "sentence_idx": 0,
                    "path": "scene.png",
                    "prompt": "prompt",
                    "sentence_text": sentence,
                    "sentence_hash": sentence_hash(sentence),
                    "project_id": self.project_id,
                    "prompt_id": "prompt-1",
                    "manifest_sentence_hash": sentence_hash(sentence),
                    "selected_reason": "auto_score_v2:0.30:retry_recommended",
                    "candidate_score": 0.30,
                    "candidate_score_version": "candidate_score_v2",
                }
            ],
        )
        project = db.get_project(self.project_id)
        self.assertIsNotNone(project)
        assert project is not None
        issue_codes = [issue["code"] for issue in validate_generated_image_mappings(project)]
        self.assertIn("IMAGE_CANDIDATE_SCORE_LOW", issue_codes)
        self.assertIn("IMAGE_CANDIDATE_RETRY_RECOMMENDED", issue_codes)

    def test_batch_gate_reports_repeated_image_hashes(self) -> None:
        sentences = ["First scene.", "Second scene."]
        db.update_project(
            self.project_id,
            visual_source_mode="comfyui_auto",
            sentences=sentences,
            media_order=["scene-a.png", "scene-b.png"],
            body_image_options={},
            body_image_mappings=[
                {
                    "sentence_idx": 0,
                    "path": "scene-a.png",
                    "prompt": "prompt",
                    "sentence_text": sentences[0],
                    "sentence_hash": sentence_hash(sentences[0]),
                    "project_id": self.project_id,
                    "prompt_id": "prompt-1",
                    "perceptual_hash": "abc123",
                    "candidate_score": 0.9,
                },
                {
                    "sentence_idx": 1,
                    "path": "scene-b.png",
                    "prompt": "prompt",
                    "sentence_text": sentences[1],
                    "sentence_hash": sentence_hash(sentences[1]),
                    "project_id": self.project_id,
                    "prompt_id": "prompt-2",
                    "perceptual_hash": "abc123",
                    "candidate_score": 0.9,
                },
            ],
        )
        project = db.get_project(self.project_id)
        self.assertIsNotNone(project)
        assert project is not None

        issue_codes = [issue["code"] for issue in validate_generated_image_mappings(project)]

        self.assertIn("IMAGE_BATCH_DUPLICATE_HASH", issue_codes)

    def test_character_descriptor_required_must_be_applied_to_selected_mapping(self) -> None:
        sentence = "Mina enters the studio."
        db.update_project(
            self.project_id,
            visual_source_mode="comfyui_auto",
            sentences=[sentence],
            media_order=["scene.png"],
            body_image_options={"character_descriptor_required": True},
            body_image_mappings=[
                {
                    "sentence_idx": 0,
                    "path": "scene.png",
                    "prompt": "prompt",
                    "sentence_text": sentence,
                    "sentence_hash": sentence_hash(sentence),
                    "project_id": self.project_id,
                    "prompt_id": "prompt-1",
                    "candidate_score": 0.9,
                }
            ],
        )
        project = db.get_project(self.project_id)
        self.assertIsNotNone(project)
        assert project is not None

        issue_codes = [issue["code"] for issue in validate_generated_image_mappings(project)]

        self.assertIn("IMAGE_CHARACTER_DESCRIPTOR_NOT_APPLIED", issue_codes)

    def test_allow_low_quality_does_not_skip_generated_metadata(self) -> None:
        sentence = "우베를 활용한 보라색 디저트가 편의점 매대에 출시됩니다."
        manifest_path = self._write_manifest(sentence)
        payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        payload["prompts"][0]["visual_brief"]["domain"] = "news_explainer"
        Path(manifest_path).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        db.update_project(
            self.project_id,
            visual_source_mode="hybrid",
            sentences=[sentence],
            media_order=["scene.png"],
            body_image_options={
                "allow_low_quality_generated_images": True,
                "image_prompts_manifest_path": manifest_path,
            },
            body_image_mappings=[
                {
                    "sentence_idx": 0,
                    "path": "scene.png",
                    "prompt": "prompt",
                    "sentence_text": sentence,
                    "sentence_hash": sentence_hash(sentence),
                    "project_id": self.project_id,
                    "prompt_id": "prompt-1",
                    "manifest_sentence_hash": sentence_hash(sentence),
                    "selected_reason": "auto_score_v2:0.30:retry_recommended",
                    "candidate_score": 0.30,
                    "candidate_score_version": "candidate_score_v2",
                }
            ],
        )
        project = db.get_project(self.project_id)
        self.assertIsNotNone(project)
        assert project is not None
        issue_codes = [issue["code"] for issue in validate_generated_image_mappings(project)]
        self.assertIn("IMAGE_CANDIDATE_SCORE_LOW", issue_codes)

    def test_manual_art_directed_generated_metadata_still_uses_strict_policy(self) -> None:
        sentence = "Leaf waste becomes biodegradable mulch film."
        manifest_path = self._write_manifest(sentence, include_visual_brief=False)
        payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        payload["prompts"][0]["visual_brief"] = {
            "domain": "news_explainer",
            "rationale": "style_preset=simple_diagram",
        }
        Path(manifest_path).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        db.update_project(
            self.project_id,
            visual_source_mode="hybrid",
            sentences=[sentence],
            media_order=["scene.png"],
            body_image_options={
                "manual_art_directed": True,
                "image_prompts_manifest_path": manifest_path,
                "candidate_reviews": {
                    "0": {
                        "retry_recommended": True,
                        "retry_reason": "low_candidate_score",
                    }
                },
            },
            body_image_mappings=[
                {
                    "sentence_idx": 0,
                    "path": "scene.png",
                    "prompt": "manual prompt",
                    "sentence_text": sentence,
                    "sentence_hash": sentence_hash(sentence),
                    "project_id": self.project_id,
                    "prompt_id": "prompt-1",
                    "manifest_sentence_hash": sentence_hash(sentence),
                    "selected_reason": "auto_score_v2:0.30:retry_recommended",
                    "candidate_score": 0.30,
                    "candidate_score_version": "candidate_score_v2:manual_art_directed_v1",
                }
            ],
        )
        project = db.get_project(self.project_id)
        self.assertIsNotNone(project)
        assert project is not None
        issue_codes = [issue["code"] for issue in validate_generated_image_mappings(project)]
        self.assertIn("IMAGE_CANDIDATE_SCORE_LOW", issue_codes)
        self.assertIn("IMAGE_CANDIDATE_RETRY_RECOMMENDED", issue_codes)
        report = build_visual_mismatch_report(project)
        rows = cast(list[object], report["rows"])
        first_row = cast(dict[str, object], rows[0])
        self.assertEqual(first_row["validation_policy"], "strict_generated")

    def test_manual_light_still_blocks_hard_vision_failures(self) -> None:
        sentence = "Leaf waste becomes biodegradable mulch film."
        manifest_path = self._write_manifest(sentence)
        db.update_project(
            self.project_id,
            visual_source_mode="hybrid",
            sentences=[sentence],
            media_order=["scene.png"],
            body_image_options={
                "manual_art_directed": True,
                "image_prompts_manifest_path": manifest_path,
            },
            body_image_mappings=[
                {
                    "sentence_idx": 0,
                    "path": "scene.png",
                    "prompt": "manual prompt",
                    "sentence_text": sentence,
                    "sentence_hash": sentence_hash(sentence),
                    "project_id": self.project_id,
                    "prompt_id": "prompt-1",
                    "manifest_sentence_hash": sentence_hash(sentence),
                    "vision_qa_issue_codes": ["LOW_RESOLUTION"],
                }
            ],
        )
        project = db.get_project(self.project_id)
        self.assertIsNotNone(project)
        assert project is not None
        issue_codes = [issue["code"] for issue in validate_generated_image_mappings(project)]
        self.assertIn("FINAL_IMAGE_DIAGRAM_QA_FAILED", issue_codes)

    def test_news_borderline_mapping_requires_strict_retry(self) -> None:
        sentence = "네이버가 뉴스 댓글 이상 반응을 감지합니다."
        manifest_path = self._write_manifest(sentence)
        payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        payload["prompts"][0]["visual_brief"]["domain"] = "news_explainer"
        payload["prompts"][0]["visual_brief"]["rationale"] = "style_preset=simple_diagram"
        Path(manifest_path).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        db.update_project(
            self.project_id,
            visual_source_mode="comfyui_auto",
            autopilot_options={"quality_mode": "balanced"},
            sentences=[sentence],
            media_order=["scene.png"],
            body_image_options={"image_prompts_manifest_path": manifest_path},
            body_image_mappings=[
                {
                    "sentence_idx": 0,
                    "path": "scene.png",
                    "prompt": "prompt",
                    "sentence_text": sentence,
                    "sentence_hash": sentence_hash(sentence),
                    "project_id": self.project_id,
                    "prompt_id": "prompt-1",
                    "manifest_sentence_hash": sentence_hash(sentence),
                    "selected_reason": "auto_score_v2:0.70:borderline",
                    "candidate_score": 0.70,
                    "candidate_score_version": "candidate_score_v2",
                }
            ],
        )
        project = db.get_project(self.project_id)
        self.assertIsNotNone(project)
        assert project is not None
        issue_codes = [issue["code"] for issue in validate_generated_image_mappings(project)]
        self.assertIn("FINAL_IMAGE_SCORE_TOO_LOW", issue_codes)
        self.assertIn("IMAGE_CANDIDATE_BORDERLINE_RETRY_REQUIRED", issue_codes)

    def test_editorial_generated_low_score_mapping_does_not_block_without_strict_final_gate(self) -> None:
        sentence = "Banking firms are taking different positions on quantum computing."
        manifest_path = self._write_manifest(sentence)
        db.update_project(
            self.project_id,
            visual_source_mode="comfyui_auto",
            sentences=[sentence],
            media_order=["scene.png"],
            body_image_options={
                "image_prompts_manifest_path": manifest_path,
                "candidate_reviews": {
                    "0": {
                        "retry_recommended": True,
                        "retry_reason": "low_candidate_score",
                    }
                },
            },
            body_image_mappings=[
                {
                    "sentence_idx": 0,
                    "path": "scene.png",
                    "prompt": "prompt",
                    "sentence_text": sentence,
                    "sentence_hash": sentence_hash(sentence),
                    "project_id": self.project_id,
                    "prompt_id": "prompt-1",
                    "manifest_sentence_hash": sentence_hash(sentence),
                    "selected_reason": "auto_score_v2:0.45:retry_recommended",
                    "candidate_score": 0.45,
                    "candidate_score_version": "candidate_score_v2",
                }
            ],
        )
        project = db.get_project(self.project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertEqual(validate_generated_image_mappings(project), [])

    def test_news_prompt_quality_failure_still_blocks_under_strict_final_gate(self) -> None:
        sentence = "Financial institutions disagree on how quickly quantum technology will matter."
        manifest_path = self._write_manifest(sentence)
        payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        payload["prompts"][0]["visual_brief"]["domain"] = "news_explainer"
        payload["prompts"][0]["keyword_coverage"] = {"passed": False}
        Path(manifest_path).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        db.update_project(
            self.project_id,
            visual_source_mode="comfyui_auto",
            sentences=[sentence],
            media_order=["scene.png"],
            body_image_options={"image_prompts_manifest_path": manifest_path},
            body_image_mappings=[
                {
                    "sentence_idx": 0,
                    "path": "scene.png",
                    "prompt": "prompt",
                    "sentence_text": sentence,
                    "sentence_hash": sentence_hash(sentence),
                    "project_id": self.project_id,
                    "prompt_id": "prompt-1",
                    "manifest_sentence_hash": sentence_hash(sentence),
                }
            ],
        )
        project = db.get_project(self.project_id)
        self.assertIsNotNone(project)
        assert project is not None
        issue_codes = [issue["code"] for issue in validate_generated_image_mappings(project)]
        self.assertIn("IMAGE_PROMPT_QUALITY_FAILED", issue_codes)

    def test_editorial_generated_exposure_issue_does_not_block_without_strict_final_gate(self) -> None:
        sentence = "Complex financial modeling exposed practical technical limits."
        manifest_path = self._write_manifest(sentence)
        db.update_project(
            self.project_id,
            visual_source_mode="comfyui_auto",
            sentences=[sentence],
            media_order=["scene.png"],
            body_image_options={"image_prompts_manifest_path": manifest_path},
            body_image_mappings=[
                {
                    "sentence_idx": 0,
                    "path": "scene.png",
                    "prompt": "prompt",
                    "sentence_text": sentence,
                    "sentence_hash": sentence_hash(sentence),
                    "project_id": self.project_id,
                    "prompt_id": "prompt-1",
                    "manifest_sentence_hash": sentence_hash(sentence),
                    "vision_qa_issue_codes": ["EXTREME_EXPOSURE"],
                }
            ],
        )
        project = db.get_project(self.project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertEqual(validate_generated_image_mappings(project), [])

    def test_tech_diagram_mapping_under_final_threshold_requires_retry(self) -> None:
        sentence = "Daily active users increased 60 percent compared with last week."
        manifest_path = self._write_manifest(sentence)
        payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        payload["prompts"][0]["visual_brief"]["domain"] = "tech"
        payload["prompts"][0]["visual_brief"]["composition_template"] = "GrowthMetricComparison"
        Path(manifest_path).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        db.update_project(
            self.project_id,
            visual_source_mode="hybrid",
            autopilot_options={"quality_mode": "fast"},
            sentences=[sentence],
            media_order=["scene.png"],
            body_image_options={"image_prompts_manifest_path": manifest_path},
            body_image_mappings=[
                {
                    "sentence_idx": 0,
                    "path": "scene.png",
                    "prompt": "prompt",
                    "sentence_text": sentence,
                    "sentence_hash": sentence_hash(sentence),
                    "project_id": self.project_id,
                    "prompt_id": "prompt-1",
                    "manifest_sentence_hash": sentence_hash(sentence),
                    "selected_reason": "auto_score_v2:0.70:selected",
                    "candidate_score": 0.70,
                    "candidate_score_version": "candidate_score_v2",
                }
            ],
        )
        project = db.get_project(self.project_id)
        self.assertIsNotNone(project)
        assert project is not None
        issue_codes = [issue["code"] for issue in validate_generated_image_mappings(project)]
        self.assertIn("FINAL_IMAGE_SCORE_TOO_LOW", issue_codes)

    def test_hybrid_uploaded_mapping_without_generated_metadata_is_not_blocked(self) -> None:
        sentence = "?꾩옱 臾몄옣"
        db.update_project(
            self.project_id,
            visual_source_mode="hybrid",
            sentences=[sentence],
            media_order=["upload.png"],
            body_image_mappings=[
                {
                    "sentence_idx": 0,
                    "path": "upload.png",
                    "prompt": "manual upload",
                }
            ],
        )
        project = db.get_project(self.project_id)
        self.assertIsNotNone(project)
        assert project is not None
        self.assertEqual(validate_generated_image_mappings(project), [])

    def test_generated_mapping_hash_mismatch_is_reported(self) -> None:
        manifest_path = self._write_manifest("새 문장")
        db.update_project(
            self.project_id,
            visual_source_mode="comfyui_auto",
            sentences=["새 문장"],
            media_order=["scene.png"],
            body_image_options={"image_prompts_manifest_path": manifest_path},
            body_image_mappings=[
                {
                    "sentence_idx": 0,
                    "path": "scene.png",
                    "prompt": "old prompt",
                    "sentence_text": "이전 문장",
                    "sentence_hash": sentence_hash("이전 문장"),
                    "project_id": self.project_id,
                    "prompt_id": "prompt-old",
                }
            ],
        )
        project = db.get_project(self.project_id)
        self.assertIsNotNone(project)
        assert project is not None
        issues = validate_generated_image_mappings(project)
        self.assertEqual(issues[0]["code"], "IMAGE_SENTENCE_HASH_MISMATCH")

    def test_preflight_fails_when_generated_mapping_is_missing_hash(self) -> None:
        sentence = "현재 문장"
        manifest_path = self._write_manifest(sentence)
        db.update_project(
            self.project_id,
            visual_source_mode="comfyui_auto",
            sentences=[sentence],
            media_order=["scene.png"],
            body_image_options={"image_prompts_manifest_path": manifest_path},
            body_image_mappings=[{"sentence_idx": 0, "path": "scene.png", "prompt": "prompt"}],
        )
        project = db.get_project(self.project_id)
        self.assertIsNotNone(project)
        assert project is not None
        report = build_preflight_report(project)
        relevance = next(check for check in report["checks"] if check["key"] == "visual_relevance")
        self.assertFalse(relevance["ok"])
        self.assertIn("sentence_hash", relevance["message"])

    def test_preflight_fails_when_manifest_is_missing(self) -> None:
        sentence = "현재 문장"
        db.update_project(
            self.project_id,
            visual_source_mode="comfyui_auto",
            sentences=[sentence],
            media_order=["scene.png"],
            body_image_mappings=[
                {
                    "sentence_idx": 0,
                    "path": "scene.png",
                    "prompt": "prompt",
                    "sentence_text": sentence,
                    "sentence_hash": sentence_hash(sentence),
                    "project_id": self.project_id,
                    "prompt_id": "prompt-1",
                }
            ],
        )
        project = db.get_project(self.project_id)
        self.assertIsNotNone(project)
        assert project is not None
        issues = validate_generated_image_mappings(project)
        self.assertEqual(issues[0]["code"], "IMAGE_PROMPT_MANIFEST_MISSING")

    def test_upload_only_empty_visual_selection_blocks_render_preflight(self) -> None:
        db.update_project(
            self.project_id,
            script="땅이 혼돈하고 공허하며 흑암이 깊음 위에 있습니다.",
            compiled_script="땅이 혼돈하고 공허하며 흑암이 깊음 위에 있습니다.",
            sentences=["땅이 혼돈하고 공허하며 흑암이 깊음 위에 있습니다."],
            media_order=["abstract.png"],
            visual_source_mode="upload_only",
            tts_state="done",
        )
        project = db.get_project(self.project_id)
        self.assertIsNotNone(project)
        assert project is not None

        report = build_preflight_report(project)
        failed = {check["key"]: check for check in report["checks"] if not check["ok"]}

        self.assertIn("visual_relevance", failed)
        self.assertIn("semantic", failed["visual_relevance"]["message"].lower())

    def test_preflight_fails_when_visual_brief_is_missing(self) -> None:
        sentence = "현재 문장"
        manifest_path = self._write_manifest(sentence, include_visual_brief=False)
        db.update_project(
            self.project_id,
            visual_source_mode="comfyui_auto",
            sentences=[sentence],
            media_order=["scene.png"],
            body_image_options={"image_prompts_manifest_path": manifest_path},
            body_image_mappings=[
                {
                    "sentence_idx": 0,
                    "path": "scene.png",
                    "prompt": "prompt",
                    "sentence_text": sentence,
                    "sentence_hash": sentence_hash(sentence),
                    "project_id": self.project_id,
                    "prompt_id": "prompt-1",
                    "manifest_sentence_hash": sentence_hash(sentence),
                }
            ],
        )
        project = db.get_project(self.project_id)
        self.assertIsNotNone(project)
        assert project is not None
        issues = validate_generated_image_mappings(project)
        self.assertEqual(issues[0]["code"], "IMAGE_VISUAL_BRIEF_MISSING")

    def test_preflight_fails_when_prompt_misses_required_visual_targets(self) -> None:
        sentence = "현재 문장"
        manifest_path = self._write_manifest(sentence, missing_must_show=["large checklist"])
        db.update_project(
            self.project_id,
            visual_source_mode="comfyui_auto",
            sentences=[sentence],
            media_order=["scene.png"],
            body_image_options={"image_prompts_manifest_path": manifest_path},
            body_image_mappings=[
                {
                    "sentence_idx": 0,
                    "path": "scene.png",
                    "prompt": "prompt",
                    "sentence_text": sentence,
                    "sentence_hash": sentence_hash(sentence),
                    "project_id": self.project_id,
                    "prompt_id": "prompt-1",
                    "manifest_sentence_hash": sentence_hash(sentence),
                }
            ],
        )
        project = db.get_project(self.project_id)
        self.assertIsNotNone(project)
        assert project is not None
        issues = validate_generated_image_mappings(project)
        self.assertEqual(issues[0]["code"], "IMAGE_PROMPT_MUST_SHOW_MISSING")

    def test_preflight_fails_when_prompt_contains_blocked_phrase(self) -> None:
        sentence = "현재 문장"
        manifest_path = self._write_manifest(sentence, missing_must_show=["BLOCKLIST:running fast"])
        db.update_project(
            self.project_id,
            visual_source_mode="comfyui_auto",
            sentences=[sentence],
            media_order=["scene.png"],
            body_image_options={"image_prompts_manifest_path": manifest_path},
            body_image_mappings=[
                {
                    "sentence_idx": 0,
                    "path": "scene.png",
                    "prompt": "prompt",
                    "sentence_text": sentence,
                    "sentence_hash": sentence_hash(sentence),
                    "project_id": self.project_id,
                    "prompt_id": "prompt-1",
                    "manifest_sentence_hash": sentence_hash(sentence),
                }
            ],
        )
        project = db.get_project(self.project_id)
        self.assertIsNotNone(project)
        assert project is not None
        issues = validate_generated_image_mappings(project)
        self.assertEqual(issues[0]["code"], "IMAGE_PROMPT_BLOCKLIST")

    def test_visual_relevance_rows_report_pass_and_summary(self) -> None:
        sentence = "현재 문장"
        manifest_path = self._write_manifest(sentence)
        db.update_project(
            self.project_id,
            visual_source_mode="comfyui_auto",
            sentences=[sentence],
            media_order=["scene.png"],
            body_image_options={"image_prompts_manifest_path": manifest_path},
            body_image_mappings=[
                {
                    "sentence_idx": 0,
                    "path": "scene.png",
                    "prompt": "prompt",
                    "sentence_text": sentence,
                    "sentence_hash": sentence_hash(sentence),
                    "project_id": self.project_id,
                    "prompt_id": "prompt-1",
                    "manifest_sentence_hash": sentence_hash(sentence),
                }
            ],
        )
        project = db.get_project(self.project_id)
        self.assertIsNotNone(project)
        assert project is not None
        rows = build_visual_relevance_rows(project)
        self.assertEqual(rows[0]["status"], "pass")
        summary = summarize_visual_relevance(rows)
        self.assertEqual(summary["pass_count"], 1)
        self.assertEqual(summary["stale_count"], 0)
        self.assertEqual(summary["missing_count"], 0)

    def test_visual_mismatch_report_prefers_project_sentence_text(self) -> None:
        sentence = "네이버 댓글 관리가 바뀝니다."
        mojibake = "?ㅼ씠踰??볤?"
        manifest_path = self._write_manifest(mojibake)
        payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        payload["prompts"][0]["sentence"] = mojibake
        payload["prompts"][0]["sentence_hash"] = sentence_hash(sentence)
        Path(manifest_path).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        db.update_project(
            self.project_id,
            visual_source_mode="comfyui_auto",
            sentences=[sentence],
            media_order=["scene.png"],
            body_image_options={"image_prompts_manifest_path": manifest_path},
            body_image_mappings=[
                {
                    "sentence_idx": 0,
                    "path": "scene.png",
                    "prompt": "prompt",
                    "sentence_text": mojibake,
                    "sentence_hash": sentence_hash(sentence),
                    "project_id": self.project_id,
                    "prompt_id": "prompt-1",
                    "manifest_sentence_hash": sentence_hash(sentence),
                }
            ],
        )
        project = db.get_project(self.project_id)
        self.assertIsNotNone(project)
        assert project is not None
        report = build_visual_mismatch_report(project)
        rows = cast(list[object], report["rows"])
        self.assertIsInstance(rows, list)
        first = rows[0]
        self.assertIsInstance(first, dict)
        first_row = cast(dict[str, object], first)
        self.assertEqual(first_row["sentence"], sentence)
        self.assertEqual(first_row["sentence_source"], "project_record")

    def test_visual_mismatch_report_includes_food_keyword_audit(self) -> None:
        sentence = "우베를 활용한 보라색 디저트가 편의점 매대에 출시됩니다."
        manifest_path = self._write_manifest(sentence)
        payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        payload["prompts"][0]["positive_prompt"] = "single everyday object in a quiet realistic room"
        payload["prompts"][0]["visual_brief"]["domain"] = "food_trend"
        payload["prompts"][0]["visual_brief"]["must_show"] = ["single everyday object in a quiet realistic room"]
        Path(manifest_path).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        db.update_project(
            self.project_id,
            visual_source_mode="comfyui_auto",
            sentences=[sentence],
            media_order=["scene.png"],
            body_image_options={"image_prompts_manifest_path": manifest_path},
            body_image_mappings=[
                {
                    "sentence_idx": 0,
                    "path": "scene.png",
                    "prompt": "single everyday object in a quiet realistic room",
                    "sentence_text": sentence,
                    "sentence_hash": sentence_hash(sentence),
                    "project_id": self.project_id,
                    "prompt_id": "prompt-1",
                    "manifest_sentence_hash": sentence_hash(sentence),
                    "candidate_score": 0.82,
                    "candidate_score_version": "candidate_score_v2",
                }
            ],
        )
        project = db.get_project(self.project_id)
        self.assertIsNotNone(project)
        assert project is not None
        report = build_visual_mismatch_report(project)
        rows = cast(list[object], report["rows"])
        first_row = cast(dict[str, object], rows[0])
        expected_keywords = cast(list[str], first_row["expected_keywords"])
        generic_fallback_hits = cast(list[str], first_row["generic_fallback_hits"])
        self.assertIn("ube", expected_keywords)
        self.assertIn("single everyday object in a quiet realistic room", generic_fallback_hits)
        self.assertEqual(first_row["decision"], "block_and_retry")

    def test_visual_mismatch_report_uses_fuzzy_food_keyword_hits(self) -> None:
        sentence = "편의점 식품 매대에서 우베 보라색 디저트가 눈에 띄기 시작했습니다."
        manifest_path = self._write_manifest(sentence)
        payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        payload["prompts"][0]["positive_prompt"] = (
            "modern food market display, purple ube color accent, changing display shelf"
        )
        payload["prompts"][0]["visual_brief"]["domain"] = "food_trend"
        Path(manifest_path).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        db.update_project(
            self.project_id,
            visual_source_mode="comfyui_auto",
            sentences=[sentence],
            media_order=["scene.png"],
            body_image_options={"image_prompts_manifest_path": manifest_path},
            body_image_mappings=[
                {
                    "sentence_idx": 0,
                    "path": "scene.png",
                    "prompt": "food trend prompt",
                    "sentence_text": sentence,
                    "sentence_hash": sentence_hash(sentence),
                    "project_id": self.project_id,
                    "prompt_id": "prompt-1",
                    "manifest_sentence_hash": sentence_hash(sentence),
                    "candidate_score": 0.82,
                    "candidate_score_version": "candidate_score_v2:food_trend_v1",
                }
            ],
        )
        project = db.get_project(self.project_id)
        self.assertIsNotNone(project)
        assert project is not None
        report = build_visual_mismatch_report(project)
        rows = cast(list[object], report["rows"])
        first_row = cast(dict[str, object], rows[0])
        prompt_keyword_hits = cast(list[str], first_row["prompt_keyword_hits"])
        self.assertIn("food store display", prompt_keyword_hits)
        self.assertIn("purple products", prompt_keyword_hits)
        self.assertIn("new product shelf", prompt_keyword_hits)
        self.assertNotEqual(first_row["decision"], "block_and_retry")

    def test_write_visual_contact_sheet_creates_diagnostic_image(self) -> None:
        sentence = "Leaf waste becomes biodegradable mulch film."
        manifest_path = self._write_manifest(sentence)
        media_dir = db.project_dir(self.project_id) / "media"
        media_dir.mkdir(parents=True, exist_ok=True)
        from PIL import Image

        Image.new("RGB", (640, 360), color=(80, 120, 80)).save(media_dir / "scene.png")
        db.update_project(
            self.project_id,
            visual_source_mode="comfyui_auto",
            sentences=[sentence],
            media_order=["scene.png"],
            body_image_options={"image_prompts_manifest_path": manifest_path},
            body_image_mappings=[
                {
                    "sentence_idx": 0,
                    "path": "scene.png",
                    "prompt": "leaf film prompt",
                    "sentence_text": sentence,
                    "sentence_hash": sentence_hash(sentence),
                    "project_id": self.project_id,
                    "prompt_id": "prompt-1",
                    "manifest_sentence_hash": sentence_hash(sentence),
                    "candidate_score": 0.82,
                    "candidate_score_version": "candidate_score_v2",
                }
            ],
        )
        project = db.get_project(self.project_id)
        self.assertIsNotNone(project)
        assert project is not None
        output = write_visual_contact_sheet(project)
        self.assertTrue(output.exists())
        self.assertGreater(output.stat().st_size, 0)

    def test_write_final_scene_review_creates_selection_snapshot(self) -> None:
        sentence = "기관마다 양자 컴퓨팅 투자 방향이 달라지고 있습니다."
        manifest_path = self._write_manifest(sentence)
        payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        visual_brief = cast(dict[str, object], payload["prompts"][0]["visual_brief"])
        visual_brief["composition_template"] = "essay_symbolic"
        payload["prompts"][0]["visual_plan"] = {
            "sentence_idx": 0,
            "sentence": sentence,
            "core_meaning": "institutions are splitting on strategy",
            "primary_keywords": ["institutional strategy", "investment direction"],
            "secondary_keywords": [],
            "visual_metaphor": "branching decision paths",
            "subject_modes": ["environment", "symbolic"],
            "must_show": ["branching direction paths"],
            "may_show": [],
            "avoid": [],
            "prompt_hint": "medium wide shot",
            "vocab_refs": [],
            "domain": "essay",
            "source": "fallback",
            "visual_mode": "symbolic_concept",
            "scene_anchor": "institutional decision concept environment",
            "semantic_anchor_type": "institutional_decision",
            "semantic_anchor_tokens": ["branching direction paths", "institutional strategy"],
        }
        Path(manifest_path).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        db.update_project(
            self.project_id,
            visual_source_mode="comfyui_auto",
            title="final review snapshot",
            sentences=[sentence],
            media_order=["scene.png"],
            body_image_options={
                "image_prompts_manifest_path": manifest_path,
                "candidate_reviews": {
                    "0": {
                        "retry_recommended": True,
                        "retry_reason": "borderline_candidate",
                        "selection_reason": "auto_score_v2:0.61:borderline",
                        "vision_qa_issue_codes": ["LOW_EDGE_DETAIL"],
                    }
                },
            },
            body_image_mappings=[
                {
                    "sentence_idx": 0,
                    "path": "scene.png",
                    "prompt": "prompt",
                    "sentence_text": sentence,
                    "sentence_hash": sentence_hash(sentence),
                    "project_id": self.project_id,
                    "prompt_id": "prompt-1",
                    "manifest_sentence_hash": sentence_hash(sentence),
                    "selected_reason": "auto_score_v2:0.61:borderline",
                    "candidate_score": 0.61,
                    "candidate_score_version": "candidate_score_v2",
                }
            ],
        )
        project = db.get_project(self.project_id)
        self.assertIsNotNone(project)
        assert project is not None
        output = write_final_scene_review(project)
        self.assertTrue(output.exists())
        review = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(review["project_id"], self.project_id)
        self.assertEqual(review["fallback_scene_plan_count"], 1)
        self.assertEqual(review["retry_recommended_count"], 1)
        self.assertEqual(review["entries"][0]["scene_anchor"], "institutional decision concept environment")
        self.assertEqual(review["entries"][0]["semantic_anchor_type"], "institutional_decision")
        self.assertEqual(review["entries"][0]["composition_template"], "essay_symbolic")
        self.assertFalse(review["entries"][0]["repair_attempted"])
        self.assertEqual(review["entries"][0]["repair_reason"], "")
        self.assertEqual(review["entries"][0]["selection_reason"], "auto_score_v2:0.61:borderline")
        self.assertFalse(review["entries"][0]["fallback_downgrade_applied"])
        self.assertFalse(review["entries"][0]["operator_intervention_required"])
        self.assertEqual(review["entries"][0]["vision_qa_issue_codes"], ["LOW_EDGE_DETAIL"])

    def test_project_status_includes_visual_relevance_rows(self) -> None:
        sentence = "현재 문장"
        manifest_path = self._write_manifest(sentence, missing_must_show=["large checklist"])
        db.update_project(
            self.project_id,
            visual_source_mode="comfyui_auto",
            sentences=[sentence],
            media_order=["scene.png"],
            body_image_options={"image_prompts_manifest_path": manifest_path},
            body_image_mappings=[
                {
                    "sentence_idx": 0,
                    "path": "scene.png",
                    "prompt": "prompt",
                    "sentence_text": sentence,
                    "sentence_hash": sentence_hash(sentence),
                    "project_id": self.project_id,
                    "prompt_id": "prompt-1",
                    "manifest_sentence_hash": sentence_hash(sentence),
                }
            ],
        )
        response = self.client.get(f"/api/projects/{self.project_id}/status")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["visual_relevance_rows"][0]["status"], "stale")
        self.assertEqual(payload["visual_relevance_summary"]["stale_count"], 1)


if __name__ == "__main__":
    unittest.main()
