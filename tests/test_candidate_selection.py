import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

from app.services.comfyui_pipeline import (
    _compute_candidate_score,
    _compute_candidate_score_details,
    _editorial_science_issue_codes,
    _refresh_style_consistency_reviews,
    _select_best_candidate,
)
from app.services.image_quality import analyze_image_quality
from app.types import ProjectRecord


class CandidateSelectionTests(unittest.TestCase):
    def test_analyze_image_quality_flags_near_duplicate_previous(self) -> None:
        with TemporaryDirectory() as temp_dir:
            first = Path(temp_dir) / "first.png"
            second = Path(temp_dir) / "second.png"
            from PIL import Image

            Image.new("RGB", (1024, 576), color=(128, 128, 128)).save(first)
            Image.new("RGB", (1024, 576), color=(128, 128, 128)).save(second)
            result = analyze_image_quality(second, previous_image_path=first)
            self.assertIn("NEAR_DUPLICATE_PREVIOUS", result["issue_codes"])
            self.assertEqual(result["version"], "vision_qa_v1")

    def test_score_rewards_literal_simile_and_non_fallback_plan(self) -> None:
        with TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "image.png"
            source_path.write_bytes(b"x" * 2_000_000)
            project = cast(ProjectRecord, {"body_image_options": {}})
            simile_score = _compute_candidate_score(
                project=project,
                source_path=source_path,
                sentence_idx=0,
                prompt_item={
                    "positive_prompt": "running on sand, person running on sand, shallow footprints, cinematic editorial still",
                    "negative_prompt": "text, logo, watermark, car, vehicle, traffic, truck, bus, parked car, driveway, garage, luxury house exterior, highway, intersection, tail lights",
                    "visual_brief": {
                        "must_show": ["person running on sand", "shallow footprints"],
                        "avoid": ["car", "vehicle", "traffic"],
                        "domain": "essay",
                        "visual_priority": "literal_simile",
                        "literal_simile": "running on sand",
                        "primary_keywords": ["sand", "footprints"],
                    },
                    "visual_plan": {"source": "llm"},
                },
            )
            fallback_score = _compute_candidate_score(
                project=project,
                source_path=source_path,
                sentence_idx=0,
                prompt_item={
                    "positive_prompt": "compass on a folded map, cinematic editorial still",
                    "negative_prompt": "text, logo, watermark, car, vehicle, traffic, truck, bus, parked car, driveway, garage, luxury house exterior, highway, intersection, tail lights",
                    "visual_brief": {
                        "must_show": ["compass on a folded map"],
                        "avoid": ["car", "vehicle", "traffic"],
                        "domain": "essay",
                        "primary_keywords": ["compass on a folded map"],
                    },
                    "visual_plan": {
                        "source": "fallback",
                        "primary_keywords": ["compass on a folded map"],
                    },
                },
            )
            self.assertGreater(simile_score, fallback_score)
            self.assertGreaterEqual(simile_score, 0.0)
            self.assertLessEqual(simile_score, 1.0)
            self.assertGreaterEqual(fallback_score, 0.0)
            self.assertLessEqual(fallback_score, 1.0)

    def test_manual_art_directed_score_profile_does_not_penalize_missing_visual_plan(self) -> None:
        with TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "image.png"
            source_path.write_bytes(b"x" * 2_000_000)
            project = cast(ProjectRecord, {"body_image_options": {"manual_art_directed": True}})
            details = _compute_candidate_score_details(
                project=project,
                source_path=source_path,
                sentence_idx=0,
                prompt_item={
                    "positive_prompt": "fallen leaves transforming into transparent mulch film over soil",
                    "negative_prompt": "text, watermark",
                    "template_key": "manual_article_editorial",
                    "visual_brief": {
                        "must_show": ["fallen leaves", "transparent mulch film"],
                        "avoid": ["text"],
                        "domain": "agriculture_environment",
                        "primary_keywords": ["leaves", "film", "soil"],
                    },
                },
            )
            self.assertIn("manual_art_directed_v1", details["score_version"])
            self.assertGreater(details["score_components"]["manual_art_direction"], 0.0)
            self.assertGreater(details["score"], 0.0)

    def test_agriculture_environment_score_profile_uses_domain_version(self) -> None:
        with TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "image.png"
            source_path.write_bytes(b"x" * 2_000_000)
            project = cast(ProjectRecord, {"body_image_options": {}})
            details = _compute_candidate_score_details(
                project=project,
                source_path=source_path,
                sentence_idx=0,
                prompt_item={
                    "positive_prompt": "fallen leaves transforming into thin translucent mulch film sheet, protected crop row",
                    "negative_prompt": "text, watermark, abstract dashboard, circuit diagram",
                    "visual_brief": {
                        "must_show": ["fallen leaves transforming into thin translucent mulch film sheet"],
                        "avoid": ["abstract dashboard"],
                        "domain": "agriculture_environment",
                        "primary_keywords": ["fallen leaves", "mulch film", "soil"],
                    },
                    "visual_plan": {"source": "fallback"},
                },
            )
            self.assertIn("agriculture_environment_v1", details["score_version"])
            self.assertGreater(details["score_components"]["file_sanity"], 0.0)

    def test_score_penalizes_semantic_drift_issue_codes(self) -> None:
        with TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "image.png"
            source_path.write_bytes(b"x" * 2_000_000)
            project = cast(ProjectRecord, {"body_image_options": {}})
            details = _compute_candidate_score_details(
                project=project,
                source_path=source_path,
                sentence_idx=0,
                prompt_item={
                    "positive_prompt": "\uc77c\ubd80, \uae30\uad00\ub4e4, sharp alarm clock, cinematic editorial still",
                    "negative_prompt": "text, logo, watermark, car, vehicle, traffic",
                    "visual_brief": {
                        "must_show": ["financial strategy desk with quantum processor glow"],
                        "avoid": ["car", "vehicle", "traffic"],
                        "domain": "essay",
                        "primary_keywords": ["financial strategy desk", "quantum processor glow"],
                        "primary_prop": "\uc77c\ubd80",
                        "secondary_prop": "\uae30\uad00\ub4e4",
                        "action": "environment-led editorial scene",
                        "scene": "grounded editorial environment",
                    },
                    "visual_plan": {
                        "source": "llm",
                        "symbolic_marker": "sharp alarm clock",
                    },
                },
            )
            self.assertLess(details["score_components"]["semantic_alignment_penalty"], 0.0)
            self.assertLess(details["score_components"]["generic_penalty"], 0.0)

    def test_score_penalizes_office_repetition_for_explainer_visual_mode(self) -> None:
        with TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "image.png"
            source_path.write_bytes(b"x" * 2_000_000)
            project = cast(ProjectRecord, {"body_image_options": {}})
            details = _compute_candidate_score_details(
                project=project,
                source_path=source_path,
                sentence_idx=0,
                prompt_item={
                    "positive_prompt": "simple flat explainer diagram, office desk, monitor wall, screen glow",
                    "negative_prompt": "text, logo, watermark",
                    "visual_brief": {
                        "must_show": ["quantum processor glow", "future growth arrow"],
                        "avoid": ["office desk"],
                        "domain": "essay",
                        "visual_mode": "simple_explainer",
                        "primary_keywords": ["quantum processor glow", "future growth arrow"],
                    },
                    "visual_plan": {"source": "llm"},
                },
            )
            self.assertLess(details["score_components"]["scene_variety_penalty"], 0.0)

    def test_score_penalizes_repeated_scene_family_from_previous_manifest_entries(self) -> None:
        with TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "image.png"
            source_path.write_bytes(b"x" * 2_000_000)
            manifest_path = Path(temp_dir) / "manifest.json"
            manifest_path.write_text(
                """
                {
                  "prompts": [
                    {
                      "sentence_idx": 0,
                      "visual_brief": {
                        "visual_mode": "editorial_scene",
                        "scene_anchor": "institutional finance strategy environment",
                        "hero_subject": "institutional investment committee reviewing a quantum roadmap",
                        "composition_template": "",
                        "semantic_anchor_type": "institutional_decision",
                        "semantic_anchor_tokens": [
                          "institutional investment committee reviewing a quantum roadmap",
                          "split capital allocation board showing pause versus continued investment"
                        ]
                      },
                      "visual_plan": {
                        "visual_mode": "editorial_scene",
                        "scene_anchor": "institutional finance strategy environment",
                        "hero_subject": "institutional investment committee reviewing a quantum roadmap",
                        "composition_template": "",
                        "semantic_anchor_type": "institutional_decision",
                        "semantic_anchor_tokens": [
                          "institutional investment committee reviewing a quantum roadmap",
                          "split capital allocation board showing pause versus continued investment"
                        ]
                      }
                    }
                  ]
                }
                """,
                encoding="utf-8",
            )
            project = cast(
                ProjectRecord,
                {"body_image_options": {"image_prompts_manifest_path": str(manifest_path)}},
            )
            details = _compute_candidate_score_details(
                project=project,
                source_path=source_path,
                sentence_idx=1,
                prompt_item={
                    "positive_prompt": "institutional investment committee reviewing a quantum roadmap, cinematic editorial still",
                    "negative_prompt": "text, logo, watermark",
                    "visual_brief": {
                        "must_show": ["institutional investment committee reviewing a quantum roadmap"],
                        "avoid": [],
                        "domain": "essay",
                        "visual_mode": "editorial_scene",
                        "scene_anchor": "institutional finance strategy environment",
                        "hero_subject": "institutional investment committee reviewing a quantum roadmap",
                        "composition_template": "",
                        "semantic_anchor_type": "institutional_decision",
                        "semantic_anchor_tokens": [
                            "institutional investment committee reviewing a quantum roadmap",
                            "split capital allocation board showing pause versus continued investment",
                        ],
                        "primary_keywords": ["institutional investment committee", "capital allocation"],
                    },
                    "visual_plan": {
                        "source": "llm",
                        "visual_mode": "editorial_scene",
                        "scene_anchor": "institutional finance strategy environment",
                        "hero_subject": "institutional investment committee reviewing a quantum roadmap",
                        "composition_template": "",
                        "semantic_anchor_type": "institutional_decision",
                        "semantic_anchor_tokens": [
                            "institutional investment committee reviewing a quantum roadmap",
                            "split capital allocation board showing pause versus continued investment",
                        ],
                    },
                },
            )
            self.assertLess(details["score_components"]["scene_family_repeat_penalty"], 0.0)

    def test_editorial_science_issue_codes_flag_missing_film_prompt(self) -> None:
        issue_codes = _editorial_science_issue_codes(
            prompt_item={
                "positive_prompt": "beautiful generic green farm field",
                "visual_brief": {
                    "domain": "agriculture_environment",
                    "must_show": ["thin translucent mulch film sheet", "protected crop row"],
                    "composition_template": "FieldMulchFunction",
                },
            },
            vision_issue_codes=["EDITORIAL_SUBJECT_TOO_SMALL"],
        )
        self.assertIn("MISSING_DOMINANT_FILM_OBJECT", issue_codes)
        self.assertIn("SYMBOLIC_ONLY_WHEN_LITERAL_REQUIRED", issue_codes)

    def test_select_best_candidate_marks_retry_for_low_score(self) -> None:
        decision = _select_best_candidate(
            [
                {
                    "path": "cand_a.png",
                    "prompt": "prompt a",
                    "prompt_id": "prompt-a",
                    "candidate_index": 1,
                    "candidate_total": 2,
                    "candidate_score": 0.42,
                    "candidate_score_version": "candidate_score_v2",
                },
                {
                    "path": "cand_b.png",
                    "prompt": "prompt b",
                    "prompt_id": "prompt-b",
                    "candidate_index": 2,
                    "candidate_total": 2,
                    "candidate_score": 0.55,
                    "candidate_score_version": "candidate_score_v2",
                },
            ],
            fallback={
                "path": "fallback.png",
                "prompt": "fallback",
                "prompt_id": "fallback",
                "candidate_index": 1,
                "candidate_total": 1,
                "candidate_score": 0.1,
                "candidate_score_version": "candidate_score_v2",
            },
        )
        self.assertEqual(decision["selected_path"], "cand_b.png")
        self.assertTrue(decision["retry_recommended"])
        self.assertEqual(decision["retry_reason"], "low_candidate_score")

    def test_select_best_candidate_marks_borderline_for_strict_retry(self) -> None:
        decision = _select_best_candidate(
            [
                {
                    "path": "cand.png",
                    "prompt": "prompt",
                    "prompt_id": "prompt-id",
                    "candidate_index": 1,
                    "candidate_total": 1,
                    "candidate_score": 0.70,
                    "candidate_score_version": "candidate_score_v2",
                }
            ],
            fallback={
                "path": "fallback.png",
                "prompt": "fallback",
                "prompt_id": "fallback",
                "candidate_index": 1,
                "candidate_total": 1,
                "candidate_score": 0.1,
                "candidate_score_version": "candidate_score_v2",
            },
        )
        self.assertEqual(decision["selection_reason"], "auto_score_v2:0.70:borderline")
        self.assertTrue(decision["retry_recommended"])
        self.assertEqual(decision["retry_reason"], "borderline_candidate")

    def test_style_consistency_review_rewards_matching_adjacent_style_metadata(self) -> None:
        candidate_groups = {
            "0": [
                {
                    "path": "scene0.png",
                    "selected": True,
                    "generation_profile": "sdxl_style_reference",
                    "template_id": "txt2img_sdxl_ipadapter_style_lora",
                    "style_reference_image": "ref.png",
                    "lora_name": "stickfigures.safetensors",
                    "width": 1024,
                    "height": 576,
                }
            ],
            "1": [
                {
                    "path": "scene1.png",
                    "selected": True,
                    "generation_profile": "sdxl_style_reference",
                    "template_id": "txt2img_sdxl_ipadapter_style_lora",
                    "style_reference_image": "ref.png",
                    "lora_name": "stickfigures.safetensors",
                    "width": 1024,
                    "height": 576,
                }
            ],
            "2": [
                {
                    "path": "scene2.png",
                    "selected": True,
                    "generation_profile": "sdxl_standard",
                    "template_id": "txt2img_sdxl_basic",
                    "style_reference_image": "",
                    "lora_name": "",
                    "width": 1024,
                    "height": 576,
                }
            ],
        }
        candidate_reviews = cast(dict[str, dict[str, object]], {
            "0": {"best_path": "scene0.png"},
            "1": {"best_path": "scene1.png"},
            "2": {"best_path": "scene2.png"},
        })
        updated = _refresh_style_consistency_reviews(candidate_groups, candidate_reviews)
        self.assertEqual(updated["0"]["style_consistency_reason"], "first_scene_baseline")
        self.assertGreater(
            cast(float, updated["1"]["style_consistency_score"]),
            cast(float, updated["2"]["style_consistency_score"]),
        )
        self.assertEqual(updated["1"]["style_consistency_version"], "style_consistency_v1")


if __name__ == "__main__":
    unittest.main()
