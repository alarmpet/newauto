import json
from pathlib import Path

import pytest

from scripts.smoke_installed_longform_workflow import (
    validate_installed_smoke_result,
    verify_image_manifest,
    verify_prompt_manifest,
    verify_render_report,
    verify_tts_consistency,
)


def test_static_smoke_verifiers_accept_complete_contract(tmp_path: Path):
    project_dir = tmp_path
    (project_dir / "image_prompts_manifest.json").write_text(
        json.dumps(
            {
                "prompts": [
                    {"sentence_idx": 0, "prompt_hash": "p1"},
                    {"sentence_idx": 1, "prompt_hash": "p2"},
                ]
            }
        ),
        encoding="utf-8",
    )
    (project_dir / "body_image_manifest.json").write_text(
        json.dumps(
            {
                "selected": [
                    {"sentence_idx": 0, "seed": 1, "prompt_hash": "p1", "qa": {"score": 0.9}, "perceptual_hash": "i1"},
                    {"sentence_idx": 1, "seed": 2, "prompt_hash": "p2", "qa": {"score": 0.9}, "perceptual_hash": "i2"},
                ]
            }
        ),
        encoding="utf-8",
    )
    (project_dir / "tts").mkdir()
    (project_dir / "tts" / "tts_consistency_report.json").write_text(
        json.dumps({"metadata_consistent": True, "audio_consistency_passed": True}),
        encoding="utf-8",
    )
    (project_dir / "render_report.json").write_text(
        json.dumps({"duration_guard_passed": True, "output_duration_sec": 35.0}),
        encoding="utf-8",
    )

    verify_prompt_manifest(project_dir, min_unique_prompt_ratio=1.0)
    verify_image_manifest(project_dir, min_unique_image_ratio=1.0)
    verify_tts_consistency(project_dir)
    verify_render_report(project_dir, min_duration_sec=30.0)


def test_prompt_manifest_rejects_low_diversity(tmp_path: Path):
    (tmp_path / "image_prompts_manifest.json").write_text(
        json.dumps({"prompts": [{"prompt_hash": "same"}, {"prompt_hash": "same"}]}),
        encoding="utf-8",
    )

    with pytest.raises(AssertionError, match="prompt diversity"):
        verify_prompt_manifest(tmp_path, min_unique_prompt_ratio=1.0)


def test_installed_smoke_result_requires_visual_and_tts_quality():
    bad = {
        "script_contains_korean": True,
        "sentence_count": 6,
        "visual_mapping_count": 0,
        "render_plan_media_count": 0,
        "tts_consistency_passed": False,
        "blocking_preflight_checks": ["tts_consistency", "visual_relevance"],
        "render_state": "done",
        "output_exists": True,
    }

    issues = validate_installed_smoke_result(bad)

    assert "visual_mapping_count 0 does not match sentence_count 6" in issues
    assert "render_plan_media_count 0 does not match sentence_count 6" in issues
    assert "tts_consistency_passed is false" in issues
    assert "blocking preflight checks remain: tts_consistency, visual_relevance" in issues
