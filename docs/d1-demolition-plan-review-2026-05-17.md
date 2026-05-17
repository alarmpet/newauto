# D1 Demolition Plan Review

Date: 2026-05-17
Reviewed plan: `C:\Users\petbl\newauto\docs\d1-demolition-plan-2026-05-17.md`

## Verdict

The D1 direction is technically possible, but the current plan is not yet safe to execute as written.

My recommendation: keep D1, but revise it into a two-layer demolition:

1. First land a no-op compatibility shell that disables image generation while keeping imports, DB loading, project pages, and old project records stable.
2. Then delete SDXL/Flow/Stickman modules only after every caller and test has been removed or rewritten.

The plan correctly identifies most SDXL/Flow/Stickman files, but it underestimates how deeply these symbols are still connected through `scene_plan`, `autopilot`, `image_gen`, `image_worker`, frontend state, tests, MCP scripts, and persisted SQLite project rows.

## Current Repo State

Verified:

- Current HEAD is `b93b9af`.
- Tag `pre-image-demolition-2026-05-17` exists.
- Working tree is not clean: `docs/d1-demolition-plan-2026-05-17.md` is untracked.
- ComfyUI workflow templates still exist:
  - `txt2img_sdxl_basic.json`
  - `txt2img_sdxl_lightning.json`
  - `txt2img_sdxl_lora.json`
  - `txt2img_sdxl_ipadapter_style.json`
  - `txt2img_sdxl_ipadapter_style_lora.json`
  - `txt2img_sdxl_controlnet_depth.json`
  - `txt2img_sdxl_stickman_lora.json`
- `app/main.py` still imports and registers `flow`:
  - `from .routers import autopilot, flow, image_gen, projects, render, stock, system, youtube`
  - `app.include_router(flow.router)`

This means D1.1's expected clean tree is false right now, and D1.2 deleting `app/routers/flow.py` will break app import unless `app/main.py` is edited in the same step.

## DB Findings

SQLite path:

`C:\Users\petbl\newauto\storage\app.db`

Project rows by `visual_source_mode`:

| Mode | Count |
|---|---:|
| `upload_only` | 81 |
| `comfyui_auto` | 24 |
| `flow_assisted` | 21 |
| `hybrid` | 1 |

Other persisted state:

- 6 project rows contain `flow_` in `body_image_options`.
- 21 project rows contain SDXL/ControlNet/IPAdapter/Stickman-style body image option keys.
- body image states: `idle` 110, `done` 16, `error` 1.

Important correction: the plan says "No DB migration" and "old flow rows reject on next save is acceptable." I do not think that is acceptable for this repo because there are already 21 `flow_assisted` projects. At minimum, D1 should keep the loader tolerant and add a read-time compatibility rule:

- Existing `flow_*` rows should load as `upload_only` or `comfyui_auto_disabled`, not become invisible or fail later.
- New writes should reject `flow_*`.
- A diagnostics note should list affected project IDs before demolition.

## Major Problems In The Plan

### 1. Deleting modules before callers are removed will break imports

The plan deletes these files early:

- `app/services/image_prompting.py`
- `app/services/prompt_compiler.py`
- `app/services/comfyui_prompt_adapter.py`
- `app/services/prompt_repair.py`
- `app/services/flow_prompting.py`
- `app/services/stickman_evidence.py`
- `app/services/stickman_reference_library.py`
- `app/services/stickman_layout_sketch.py`
- `app/services/visual_brief.py`
- `app/routers/flow.py`

But current callers still include:

- `app/services/scene_plan.py` imports `suggest_image_prompt`.
- `app/workers/image_worker.py` imports `PromptRepairDecision`, `VisualBriefMode`, and uses `prompt_g`, `prompt_l`, SDXL template IDs, LoRA routing, repair retry state.
- `app/routers/image_gen.py` is heavily SDXL-specific.
- `app/services/autopilot.py` still builds SDXL prompt manifest fields and routes stickman LoRA.
- `app/services/prompt_strictifier.py` imports `PromptRepairDecision`.
- `app/services/visual_brief.py` is referenced by `tests/test_visual_brief.py`.
- `scripts/check_comfyui_smoke.py`, `scripts/run_stickman_lora_batch.py`, and stickman scripts import the deleted prompt adapter/prompting services.
- `app/main.py` imports `flow`.

Improvement: add an explicit D1.2a "remove/replace imports and route registration" before any `git rm`, or delete and edit in the same atomic patch with `python -m compileall app` immediately after.

### 2. Group A test list is incomplete

The plan ignores/deletes some tests, but many remaining tests assert SDXL behavior:

- `tests/test_comfyui_workflows.py`
- `tests/test_comfyui_routes.py`
- `tests/test_image_worker.py`
- `tests/test_visual_planner.py`
- `tests/test_visual_brief.py`
- `tests/test_flow_files.py`
- `tests/test_render_report.py` imports `flow_prompting`
- `tests/test_candidate_selection.py`
- `tests/test_autopilot_worker.py`

The D1.16 pytest ignore list is too small. It will not pass after D1 unless these tests are deleted, rewritten, or explicitly moved to an archive.

Improvement: create a D1 test migration table with three columns: delete, rewrite as disabled-image-gen behavior, keep unchanged.

### 3. `image_generation_profiles.py` is missing from the plan

This file is purely SDXL profile logic:

- `GenerationProfileName = "sdxl_fast" | "sdxl_standard" | ...`
- profile workflow templates point to `txt2img_sdxl_*`
- `requires_ipadapter`, `requires_controlnet`, Lightning checkpoint fields are SDXL-era concepts.

The plan lists it under Group C-ish adjacency but does not trim it. That leaves a dead SDXL API surface after D1.

Recommendation: either delete it in D1 or replace it with a tiny disabled/placeholder profile module that D2 will refill with Z-Image profiles.

### 4. `prompt_strictifier.py` is missing from the plan

`app/services/prompt_strictifier.py` imports `PromptRepairDecision` and returns `repaired_prompt_g` / `repaired_prompt_l`. If D1 deletes `PromptRepairDecision` from `types.py`, this file breaks.

Recommendation: delete `prompt_strictifier.py` with prompt repair, or keep `PromptRepairDecision` until the strictifier is removed.

### 5. `model_registry.py` is only "orthogonal" if Stickfigures entries are removed

The plan says `model_registry.py` is untouched, but it still has Stickfigures LoRA detection and messaging. If SDXL + Stickman are demolished, keeping this registry entry is misleading and can make system health advertise a feature that no longer exists.

Recommendation: remove Stickfigures-specific registry entry in D1, or mark it `legacy_hidden`.

### 6. `comfyui_workflows.py` description does not match actual file

The plan says keep `Workflow` type and `WORKFLOWS` dict, but the current file does not have that shape. It currently provides:

- `PlaceholderMap`
- `WorkflowPayload`
- `load_workflow_template`
- `render_workflow_template`
- placeholder replacement/unresolved placeholder checks

This module is actually a generic template renderer, not a registry. It can stay useful for D2 Z-Image.

Recommendation: do not gut this file to an empty registry. Keep the generic loader/renderer and simply remove SDXL JSON templates later when D2 templates exist. If image generation is disabled in D1, this module can remain harmless.

### 7. Deleting workflow JSON templates in D1 is not addressed

The plan deletes Python code but leaves `app/workflow_templates/comfyui/txt2img_sdxl_*.json`. That creates a half-demolished system: frontend/backend may no longer expose SDXL, but dead templates remain.

Recommendation: either:

- leave them intentionally and document as rollback fixtures, or
- move them to `docs/archive/workflows_legacy_sdxl/` in D1, or
- delete them only after D2 Z-Image templates exist.

My preference: keep them through D1 as rollback fixtures, remove after D2 smoke passes.

### 8. Frontend line-based deletion is fragile

The plan references exact lines in `index.html` and `app.js`. Those line numbers are brittle and already likely to drift.

Recommendation: replace line-number instructions with symbol/block markers:

- `image-generation-profile`
- `flow-asset-input`
- `apply-repair-suggestion`
- `preferredStyleReferenceValue`
- `preferredControlImageValue`
- `renderImagePromptPreview`
- `submitComfyUiWorkflow`
- `submitImageBatch`

Then verify by `rg` that forbidden symbols are gone.

### 9. The UI placeholder must be specified as an API contract

The plan says Step 2 should show image generation disabled, but does not define the backend response contract.

Recommendation:

- Keep `/api/projects/{pid}/comfyui/status` or equivalent status endpoint returning `disabled_until_d2`.
- New image submit endpoints should return HTTP 503 with stable JSON:

```json
{
  "error": "image_generation_disabled",
  "message": "Image generation is disabled until D2 Z-Image backend lands."
}
```

This is better than deleting endpoints and causing frontend/network errors.

### 10. Autopilot should degrade cleanly, not silently skip

Current `autopilot.py` defaults to `visual_source_mode: comfyui_auto` and later generates prompt manifests. If D1 disables image gen, autopilot must explicitly switch visual behavior:

- Either set `visual_source_mode=upload_only` during D1.
- Or allow autopilot to continue through TTS/render only when user uploads media.
- Or make the image step produce a clear blocked status and stop before render.

Recommendation: add an acceptance test that autopilot does not enqueue image generation during D1.

### 11. The worker skeleton should not loop-error every queued project

The proposed `image_worker.py` skeleton marks each claimed job as error. That is better than crashing, but if any old queued/running jobs exist, startup will mark them all as errors.

Recommendation:

- On startup, recover stale jobs to a D1 disabled state.
- Worker should mark one job as error with code `IMAGE_GEN_DISABLED_D1`, not retry.
- Avoid retry-with-backoff for a known disabled feature.

### 12. "No SCHEMA changes" is good, but JSON typed surfaces still need migration behavior

No SQLite schema migration is needed. However, `ProjectRecord` loading and update validation need a compatibility posture for old JSON:

- Keep `body_image_options` as opaque JSON.
- Ignore old `prompt_g`, `prompt_l`, `repair_*`, `ip_adapter_*`, `controlnet_*`, `stickman_*`, `flow_*`.
- Do not erase them unless the user saves feature settings.
- Make diagnostics report legacy keys.

This preserves old projects and supports rollback.

## Recommended Revised D1 Order

I would revise D1 into this safer order:

1. Add `app/services/image_generation_disabled.py` with stable error payload/helpers.
2. Change `image_worker.py` to a small disabled worker that marks queued image jobs as `error` with `IMAGE_GEN_DISABLED_D1`.
3. Change `image_gen.py` endpoints to keep status/cancel and return 503 for submit/render/generate routes.
4. Remove `flow` router from `app/main.py`, then delete or stub `app/routers/flow.py`.
5. Make `db._visual_source_mode()` tolerate old `flow_*` reads as `upload_only`, while project feature writes reject `flow_*`.
6. Simplify `scene_plan.py` so it never imports `image_prompting`; it should build scenes from existing mappings or text-only visual intent.
7. Simplify `autopilot.py` so D1 cannot enqueue image generation.
8. Remove frontend SDXL/Flow controls and show a single disabled panel for Step 2.
9. Delete prompt/image modules after import checks are clean.
10. Delete or rewrite tests in one explicit test migration pass.
11. Run `python -m compileall app`.
12. Run frontend typecheck.
13. Run a narrowed but meaningful test suite.
14. Start server and verify `/api/system/health`, project list, Step 1, disabled Step 2, Step 3.

## Files To Add To D1 Inventory

Add these to Group B or Group A:

- `app/services/image_generation_profiles.py`
- `app/services/prompt_strictifier.py`
- `app/main.py`
- `scripts/check_comfyui_smoke.py`
- `scripts/run_stickman_lora_batch.py`
- `tests/test_comfyui_workflows.py`
- `tests/test_comfyui_routes.py`
- `tests/test_image_worker.py`
- `tests/test_visual_planner.py`
- `tests/test_visual_brief.py`
- `tests/test_flow_files.py`
- `tests/test_candidate_selection.py`

Assess these before claiming D1 complete:

- `app/services/model_registry.py`
- `app/services/system_health.py`
- `app/services/preflight.py`
- `app/services/operator_summary.py`
- `scripts/newauto_mcp.py`
- `scripts/newauto_stepwise_mcp.py`

## Concrete Acceptance Criteria I Would Add

Forbidden-symbol check after D1:

```powershell
rg -n "prompt_g|prompt_l|SdxlDualPrompt|ControlNetDecision|LoraDecision|PromptRepairDecision|VisualBriefMode|flow_assisted|flow_auto|flow_then_comfyui_fallback|txt2img_sdxl|Stickfigures|ip_adapter|controlnet" app scripts tests
```

Allowed exceptions should be explicitly listed. For example, archived docs may contain these strings, but runtime code should not.

DB compatibility check:

```powershell
@'
from app import db
db.init_db()
for project in db.list_projects(limit=200):
    assert project["visual_source_mode"] in {"upload_only", "hybrid", "comfyui_auto"}
print("project loading ok")
'@ | python -
```

Disabled endpoint check:

```powershell
curl -X POST http://127.0.0.1:9001/api/projects/<pid>/comfyui/workflow/submit
```

Expected: HTTP 503 with `image_generation_disabled`.

Autopilot check:

- Starting autopilot in D1 should not enqueue ComfyUI jobs.
- It should either stop at image generation with a clear disabled error or require uploaded media.

## Final Opinion

I agree with the strategic goal of D1: remove the SDXL/Flow prompt-repair tangle before rebuilding around Z-Image and LTX.

But I would not execute the current plan verbatim. It is too deletion-first. The safer engineering move is disable-first, then delete once compile/import/frontend/test surfaces are already clean. This matters especially because the DB already contains real `flow_assisted` and SDXL-era project rows, and because `image_worker.py`, `image_gen.py`, `scene_plan.py`, and `autopilot.py` are still deeply coupled to the modules the plan deletes in Step D1.2.

Recommended status for the original D1 plan: **revise before execution**.

