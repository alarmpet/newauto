---
title: "newauto Studio pipeline contract recovery"
date: 2026-05-19
category: workflow-issues
problem_type: workflow_issue
module: pipeline
tags:
  - pipeline-manifest
  - prompt-contract
  - image-qa
  - tts
  - autopilot
---

# newauto Studio Pipeline Contract Recovery

## Problem

The studio workflow had useful individual checks, but script, prompt, image, TTS, render, and autopilot stages did not share one durable artifact contract. That made failures hard to trace and let weak prompts, stale image mappings, noisy TTS, or implicit autopilot waits survive until late render preflight.

## Solution

Add a versioned `pipeline_manifest` to project records and keep each stage status in a consistent shape: `state`, `error_code`, `recovery_hint`, `input_hash`, and `output_hash`. Use that contract as the common surface for prompt manifests, image QA gates, TTS retry decisions, workflow status cards, and installed smoke checks.

Key implementation points:

- `app/services/pipeline_manifest.py` builds and validates the stage manifest.
- `app/db.py` persists `pipeline_manifest` and rebuilds it when compiled script fields change.
- `app/services/prompt_director_manifest.py` emits sentence-specific visual contracts with `required_props`, prompt hashes, and QA expectations.
- `app/services/visual_relevance.py` blocks repeated image hashes and missing character-descriptor application.
- `app/workers/tts_worker.py` retries noisy sentence-mode output with `full_passage` and fixed seed settings.
- `app/services/pipeline_runner.py` initializes explicit autopilot stage boundaries.
- `/api/projects/{pid}/workflow-status` exposes manifest-backed stage cards for the operator UI.

## Why This Works

Every stage can now answer the same diagnostic questions: what input it consumed, what output it produced, whether it is idle, queued, done, or blocked, and what recovery action should be taken. The manifest turns a chain of side effects into an inspectable pipeline.

## Prevention

When adding or changing pipeline stages, write the failing contract test first. The test should prove the stage records stable input and output hashes, preserves per-sentence metadata, and blocks render when selected artifacts are stale, duplicated, low quality, or missing required generation context.

## Verification

Focused verification used during this recovery:

```powershell
python -m pytest tests/test_pipeline_manifest.py tests/test_preset_text_health.py tests/test_korean_longform_script_integrity.py tests/test_script_compile.py tests/test_prompt_contract.py tests/test_image_prompt.py -q
python -m pytest tests/test_character_workflow_contract.py tests/test_z_image_workflow_submission.py tests/test_image_prompt.py -q
python -m pytest tests/test_visual_relevance.py tests/test_image_quality.py -q
python -m pytest tests/test_tts_pipeline.py tests/test_tts_presets.py tests/test_tts_worker.py -q
python -m pytest tests/test_autopilot_routes.py tests/test_static_workflow_ui.py tests/test_workflow_status.py tests/test_installed_pipeline_quality_smoke.py -q
node --check app/static/app.js
```
