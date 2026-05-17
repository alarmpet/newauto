# D1 Demolition Plan — newautostudio Image-Gen Subsystem Teardown (Revision 2)

Date: 2026-05-17 (revised after code-grounded review)
Status: ready for execution review.
Pre-conditions: D0 complete (disk free 59.81 GB, git tag `pre-image-demolition-2026-05-17` at commit `b93b9af`).
Supersedes: D1 Revision 1 (deletion-first ordering, untrue `comfyui_workflows.py` description, incomplete inventory).

## Why a Revision

Revision 1 was reviewed against actual code (`docs/d1-demolition-plan-review-2026-05-17.md`). Every one of the 12 review findings was verified against the repo and confirmed valid:

- `app/main.py:17` imports `flow` and `:176` registers `flow.router`. A `git rm app/routers/flow.py` BEFORE editing `main.py` breaks server import. Revision 1 had no such ordering.
- `app/services/scene_plan.py:5` imports `suggest_image_prompt` from `image_prompting`. Deleting `image_prompting.py` first breaks scene plan import.
- `app/workers/image_worker.py` imports `PromptRepairDecision`, `VisualBriefMode`, `prompt_g`, `prompt_l`, calls `repair_prompts`, `suggest_image_prompt`, `build_prompt_placeholders`. Deletion-first breaks worker.
- `app/services/autopilot.py:11` imports `image_prompting` and contains `_find_stickfigures_lora_name`, `_strip_stickman_trigger_terms`. Deletion-first breaks autopilot.
- `app/services/prompt_strictifier.py:1` imports `PromptRepairDecision` and `normalize_dual_prompt`. Revision 1 missed this file entirely.
- `app/services/image_generation_profiles.py` defines six SDXL-only profiles (`sdxl_fast`, `sdxl_standard`, `sdxl_quality`, `sdxl_low_vram_lightning`, `sdxl_style_reference`, `sdxl_controlnet_depth`). Revision 1 missed it.
- `app/services/comfyui_workflows.py` is a generic placeholder-template renderer (`PlaceholderMap`, `load_workflow_template`, `render_workflow_template`), NOT a `Workflow` registry. Revision 1's gut-edit description was wrong.
- `app/workflow_templates/comfyui/txt2img_sdxl_*.json` (7 files) exist on disk; Revision 1 didn't address them.
- `app/services/model_registry.py:33–97` advertises a `comfyui_stickfigures_lora` entry in system health. Revision 1 wrongly classified `model_registry.py` as "untouched."
- DB live audit: **127 project rows total**; `upload_only` 81, `comfyui_auto` 24, **`flow_assisted` 21**, `hybrid` 1; 6 rows have `flow_` keys inside `body_image_options`; **21 rows have SDXL/ControlNet/IPAdapter/Stickman keys**; 110 idle / 16 done / 1 error. Revision 1's "old flow rows reject on next save is acceptable" was untenable given 21 affected projects.
- 13 test files reference SDXL/Flow/Stickman/`prompt_*` symbols; Revision 1's pytest ignore list only covered 4.
- Frontend line numbers (337–339, 363–365, 450) drift the moment any earlier edit lands; Revision 1's line-anchored deletes were brittle.

This Revision 2 adopts the reviewer's "disable-first, then delete" pattern and adds the missing inventory.

## Goal (unchanged)

Remove every SDXL-, Flow-, ControlNet-, IP-Adapter-, Stickman-, and prompt-repair-loop code path while preserving:

- TTS, render mux, ASS subtitle generation
- Script generation / source research
- DB + project lifecycle (no SCHEMA changes; **read-time tolerance** for legacy keys added)
- Autopilot state machine (with image step explicitly disabled)
- Scene/render plan structure (SDXL-specific fields trimmed)
- System health, runtime probes, preflight (Stickfigures entry removed)
- Frontend Step 1 / Step 3; Step 2 reduced to a single disabled-state panel

After D1: server starts, project list loads, Step 1/Step 3 work, Step 2 shows a stable disabled placeholder, autopilot blocks before the image step with a clear error, and `body_image_state` rows from old projects load tolerantly.

## Two-Layer Demolition

### Layer A — Disable + Stub (one commit)

Make image gen inert without deleting heavy modules. Once Layer A is merged and verified, Layer B's deletions are safe because no caller still wires through the deleted symbols.

### Layer B — Delete (second commit, immediately after Layer A is green)

Now-orphaned modules + tests + scripts get `git rm`. Frontend dead code stripped. Workflow JSON templates moved to archive (not deleted) so a future smoke test of the rollback tag still loads cleanly.

Both commits land on the same `chore/demolish-sdxl-image-gen` branch. Two commits keep history bisectable; both are revertable.

## Non-Goals

- D1 does NOT add Z-Image Turbo (D2) or LTX 2.3 (D3).
- D1 does NOT change SQLite schema. `body_image_options` JSON keys (`prompt_g`, `prompt_l`, `repair_*`, `ip_adapter_*`, `controlnet_*`, `stickman_*`, `flow_*`) are read tolerantly and ignored, not erased.
- D1 does NOT delete ComfyUI weight files on disk (separate post-D1 cleanup).
- D1 does NOT migrate the 21 existing `flow_assisted` projects to a different mode. Read-time coercion in `_visual_source_mode()` returns `"upload_only"` for legacy flow values.

## Two-Commit Boundary

**Commit 1 — Layer A:**

```
chore: disable SDXL image gen + Flow loop behind compatibility shell

Adds image_generation_disabled error helper, returns 503 from image submit
endpoints, removes flow router from main.py, makes db._visual_source_mode()
tolerant of legacy flow_* values (returns upload_only), trims SDXL-specific
fields from autopilot/scene_plan/visual_planner, replaces image_worker
with a disabled shell that marks claimed jobs with IMAGE_GEN_DISABLED_D1,
strips SDXL/Flow UI controls to a single placeholder panel.

After this commit: server starts, 127 existing projects load without
error, autopilot blocks before image step, image submit returns 503.

DB schema: unchanged.
Rollback: git revert HEAD or git checkout pre-image-demolition-2026-05-17.
```

**Commit 2 — Layer B:**

```
chore: remove SDXL/Flow/Stickman modules now that callers are disabled

Deletes image_prompting, prompt_compiler, prompt_repair, prompt_strictifier,
comfyui_prompt_adapter, flow_prompting, visual_brief, image_generation_profiles,
stickman_evidence, stickman_reference_library, stickman_layout_sketch,
app/routers/flow.py, related tests and helper scripts. Moves
workflow_templates/comfyui/txt2img_sdxl_*.json to docs/archive/.

After this commit: forbidden-symbol grep passes; pytest narrowed suite passes.

Rollback: git revert HEAD reinstates files; or
git checkout pre-image-demolition-2026-05-17 to undo D1 entirely.
```

## Full Inventory (verified against working tree)

### Layer A — DISABLE/EDIT (file stays on disk; SDXL paths neutralized)

| File | Action |
|---|---|
| `app/main.py` | Remove `flow` from import + `app.include_router(flow.router)` |
| `app/services/image_generation_disabled.py` | **NEW** — `D1_DISABLED_PAYLOAD: dict[str, str]`, `D1_DISABLED_CODE = "IMAGE_GEN_DISABLED_D1"` |
| `app/routers/image_gen.py` | All POST submit/generate routes return `HTTPException(503, detail=D1_DISABLED_PAYLOAD)`. Status / cancel endpoints remain |
| `app/workers/image_worker.py` | Rewrite as ~80-line shell: claim job → write `IMAGE_GEN_DISABLED_D1` error → release. No retry. On startup, recover stale `queued`/`running` rows to error with the same code |
| `app/services/autopilot.py` | Image step (`enqueue_image_job` or equivalent) short-circuits to `body_image_state="error", body_image_error="IMAGE_GEN_DISABLED_D1"`. No more Stickfigures branching. `_find_stickfigures_lora_name`, `_strip_stickman_trigger_terms`, `_stickman_lora_blocked_for_prompt` deleted. Autopilot continues with `upload_only` projects only |
| `app/services/scene_plan.py` | Remove `from ..services.image_prompting import suggest_image_prompt`. Replace the two `suggest_image_prompt` call sites (lines 117, 123) with a stub that builds an empty `visual_brief`. Flow-mode branches removed |
| `app/services/scene_visual_plan.py` | Same flow-mode removal |
| `app/services/visual_planner.py` | Remove every function/branch that consumes `VisualBriefMode`, `prompt_g`, `prompt_l`, `ip_adapter`, `controlnet`, `stickfigures`. Keep `{subject, mood, environment}` scaffold for D2 |
| `app/services/visual_relevance.py` | Drop SDXL prompt-text-based relevance scoring; keep file-path/timing relevance |
| `app/services/diagnostics.py` | Remove SDXL/Stickman-specific diagnostic emitters |
| `app/services/operator_summary.py` | Remove SDXL profile + stickman summary fields |
| `app/services/prompt_quality.py` | Either delete (if entire file is SDXL prompt-quality scoring) or trim to non-SDXL helpers. Layer A: comment-out SDXL exports; Layer B deletes the file if it's wholly SDXL |
| `app/routers/projects.py` | Remove `body_image_options` writes for SDXL keys; preserve reads (tolerance) |
| `app/services/model_registry.py` | Delete `_find_stickfigures_lora` (line 33) and `comfyui_stickfigures_lora` entry (lines 89–97) |
| `app/services/comfyui_pipeline.py` | Strip SDXL prompt-injection / ControlNet / IP-Adapter / dual-prompt routing. Keep generic `submit_workflow → prompt_id → image_path` core for D2 to reuse |
| `app/services/comfyui_workflows.py` | **KEEP AS IS** — file is a generic placeholder template renderer (`PlaceholderMap`, `load_workflow_template`, `render_workflow_template`). Will be reused by D2. Revision 1 wrongly proposed gutting it |
| `app/db.py:735–738` | Change `_visual_source_mode` to be tolerant: legacy `"flow_assisted" / "flow_auto" / "flow_then_comfyui_fallback"` coerce to `"upload_only"` on **read**. New writes accept only `{"upload_only", "hybrid", "comfyui_auto"}` |
| `app/types.py` | `VisualSourceMode` Literal narrows to `Literal["upload_only", "hybrid", "comfyui_auto"]`. **`SdxlDualPrompt`, `ControlNetDecision`, `LoraDecision`, `PromptRepairDecision`, `VisualBriefMode` stay until Layer B** (callers still reference them in Layer A; deletion order matters) |
| `app/static/index.html` | Remove Step 2 Flow asset attach panel, SDXL preset selector, repair-suggestion cards, dual-prompt preview, ControlNet/LoRA selectors. Add single `<section id="image-gen-disabled-panel">` with "이미지 생성 비활성 (D2 대기 중)" copy |
| `app/static/app.js` | Remove handlers: `handleFlowAssetAttach`, `applyRepairSuggestion`, `submitImageBatch` SDXL path, `controlNetToggle`, `loraStackEdit`, `stickmanPreview`. Endpoint callers for `/api/flow/*` removed |
| `app/static/style.css` | Remove rules: `.flow-panel`, `.repair-suggestion`, `.dual-prompt-preview`, `.stickman-preview` |

### Layer B — DELETE (after Layer A merges green)

| File | Why now safe |
|---|---|
| `app/services/image_prompting.py` | No remaining importers after Layer A |
| `app/services/prompt_compiler.py` | Only Layer-A-edited files imported it |
| `app/services/comfyui_prompt_adapter.py` | Used only by deleted `prompt_compiler`, `prompt_repair`, `prompt_strictifier` |
| `app/services/prompt_repair.py` | Used only by `image_worker` (rewritten in Layer A) and `prompt_strictifier` (deleted) |
| `app/services/prompt_strictifier.py` | **MISSED IN REV 1** — added |
| `app/services/flow_prompting.py` | Used only by `app/routers/flow.py` (deleted next) |
| `app/routers/flow.py` | No longer wired in `main.py` after Layer A |
| `app/services/visual_brief.py` | Only `image_prompting` (deleted) consumed it |
| `app/services/image_generation_profiles.py` | **MISSED IN REV 1** — pure SDXL profile catalog |
| `app/services/stickman_evidence.py` | Caller chain (`autopilot`, scripts) cleaned in Layer A |
| `app/services/stickman_reference_library.py` | Same |
| `app/services/stickman_layout_sketch.py` | Same |
| `app/types.py` final pass | Delete `SdxlDualPrompt`, `ControlNetDecision`, `LoraDecision`, `PromptRepairDecision`, `VisualBriefMode`, `VisualBriefMode` field on `VisualBrief` |
| `scripts/run_stickman_evidence_images.py` | Stickman pipeline runner |
| `scripts/build_stickman_business_evidence.py` | Same |
| `scripts/build_stickman_layout_sketches.py` | Same |
| `scripts/run_stickman_lora_batch.py` | **MISSED IN REV 1** — added |
| `scripts/check_comfyui_smoke.py` | **MISSED IN REV 1** — imports deleted modules |
| `app/workflow_templates/comfyui/txt2img_sdxl_basic.json` | → move to `docs/archive/workflows_legacy_sdxl/` |
| `app/workflow_templates/comfyui/txt2img_sdxl_lightning.json` | → archive |
| `app/workflow_templates/comfyui/txt2img_sdxl_lora.json` | → archive |
| `app/workflow_templates/comfyui/txt2img_sdxl_stickman_lora.json` | → archive |
| `app/workflow_templates/comfyui/txt2img_sdxl_controlnet_depth.json` | → archive |
| `app/workflow_templates/comfyui/txt2img_sdxl_ipadapter_style.json` | → archive |
| `app/workflow_templates/comfyui/txt2img_sdxl_ipadapter_style_lora.json` | → archive |

### Test Migration Table (13 files)

| Test | Action | Reason |
|---|---|---|
| `tests/test_image_prompting.py` | **DELETE** (Layer B) | Target module deleted |
| `tests/test_prompt_compiler.py` | **DELETE** | Target module deleted |
| `tests/test_prompt_repair.py` | **DELETE** | Target module deleted |
| `tests/test_stickman_evidence.py` | **DELETE** | Target module deleted |
| `tests/test_visual_brief.py` | **DELETE** | Target module deleted |
| `tests/test_image_worker.py` | **REWRITE** in Layer A to assert disabled behavior (`IMAGE_GEN_DISABLED_D1` error code, no retry, queued→error transition) |
| `tests/test_visual_planner.py` | **REWRITE** in Layer A to drop SDXL assertions; keep abstract `{subject, mood, environment}` builder tests |
| `tests/test_comfyui_routes.py` | **REWRITE** in Layer A to assert 503 from submit endpoints, status endpoint still 200 |
| `tests/test_comfyui_workflows.py` | **KEEP** (file under review tests the generic placeholder renderer; only delete SDXL-template-specific assertions) |
| `tests/test_flow_files.py` | **DELETE** | Target module + router deleted |
| `tests/test_render_report.py` | **EDIT** | Remove `flow_prompting` import + Flow-specific report assertions; rest survives |
| `tests/test_autopilot_worker.py` | **EDIT** | Assert image step short-circuits to `IMAGE_GEN_DISABLED_D1`; remove Stickman assertions |
| `tests/test_diagnostics.py` | **EDIT** | Remove SDXL diagnostic emitters; keep others |
| `tests/test_hyperframes_overlay.py` | **KEEP** (hyperframes is a separate future feature, not part of D1) |
| `tests/test_feature_workflow.py` | **EDIT** | Remove SDXL feature-flag assertions |
| `tests/test_candidate_selection.py` | **EDIT** | Remove SDXL candidate review assertions |

Total: 5 deletes, 3 rewrites (Layer A), 5 edits (Layer A), 3 keep.

## API Contract for Disabled State (Layer A)

New shared module `app/services/image_generation_disabled.py`:

```python
from fastapi import HTTPException

IMAGE_GEN_DISABLED_CODE = "IMAGE_GEN_DISABLED_D1"
IMAGE_GEN_DISABLED_MESSAGE = "Image generation is disabled until D2 Z-Image backend lands."

def disabled_payload() -> dict[str, str]:
    return {"error": IMAGE_GEN_DISABLED_CODE, "message": IMAGE_GEN_DISABLED_MESSAGE}

def raise_disabled() -> None:
    raise HTTPException(status_code=503, detail=disabled_payload())
```

Used by:
- All `POST /api/projects/{pid}/comfyui/...` submit/generate routes
- All `POST /api/flow/...` routes (returned in a transitional shim before Layer B removes the router entirely)
- The image worker's job-error message

Status / queue / cancel endpoints continue to work so the frontend can still poll project state.

## DB Read-Time Tolerance (Layer A)

Current `db.py:735`:

```python
def _visual_source_mode(value: object) -> VisualSourceMode:
    if value in {"hybrid", "comfyui_auto", "flow_assisted", "flow_auto", "flow_then_comfyui_fallback"}:
        return cast(VisualSourceMode, value)
    return "upload_only"
```

New:

```python
def _visual_source_mode(value: object) -> VisualSourceMode:
    if value in {"hybrid", "comfyui_auto"}:
        return cast(VisualSourceMode, value)
    return "upload_only"  # legacy flow_* and unknown values coerce to upload_only
```

Verification — every existing project row should load without raising:

```bash
cd C:/Users/petbl/newauto
python -c "
from app import db
db.init_db()
projects = db.list_projects(limit=200)
ok = all(p['visual_source_mode'] in {'upload_only', 'hybrid', 'comfyui_auto'} for p in projects)
assert ok, 'unexpected visual_source_mode after read'
print(f'project loading ok: {len(projects)} rows')
"
```

Expected: `project loading ok: 127 rows` (or more). No exception.

Note: this means the 21 `flow_assisted` rows now **load as `upload_only`**. They still keep their uploaded media intact since `body_image_mappings` and media files are untouched. Operators wanting Flow back can `git checkout pre-image-demolition-2026-05-17`. Operators wanting to keep working on those projects can re-upload media manually after D1.

## Bite-Sized Step List

### Step D1.0 — Branch + working tree check

```bash
cd C:/Users/petbl/newauto
git status -s
git log --oneline -3
git checkout -b chore/demolish-sdxl-image-gen
```

Expected: clean tree, branch created at `b93b9af` (snapshot commit) + the d1 review/plan docs as untracked under `docs/`. Add those plan docs to a Layer A prep commit if desired or just commit them separately first.

### Step D1.A.1 — Add shared disabled helper (new file)

Create `app/services/image_generation_disabled.py` with the `IMAGE_GEN_DISABLED_CODE`, `disabled_payload()`, `raise_disabled()` shown above. Run `python -m compileall app/services/image_generation_disabled.py`.

### Step D1.A.2 — Disable image submit routes in `image_gen.py`

In every `POST` handler that previously called `submit_workflow`, replace the body with `raise_disabled()`. Keep all GET / DELETE / status / cancel handlers. Remove imports that will become unused (will catch in compileall).

Run: `python -m compileall app/routers/image_gen.py`. Expected: passes (some imports may need to be commented; iterate).

### Step D1.A.3 — Rewrite `image_worker.py` to disabled shell

Replace the body with the ~80-line shell:

```python
from .. import db
from ..services.image_generation_disabled import IMAGE_GEN_DISABLED_CODE
# ... existing lifecycle imports

def _mark_stale_jobs_disabled():
    for project in db.list_projects_with_image_state(["queued", "running"]):
        db.update_project(project["id"],
            body_image_state="error",
            body_image_error=IMAGE_GEN_DISABLED_CODE,
        )

def image_worker():
    _mark_stale_jobs_disabled()
    while True:
        job = db.claim_image_job()
        if job is None:
            time.sleep(1.0)
            continue
        db.update_project(job["id"],
            body_image_state="error",
            body_image_error=IMAGE_GEN_DISABLED_CODE,
            body_image_last_log="image generation disabled (D1)",
        )
```

Run: `python -m compileall app/workers/image_worker.py`.

### Step D1.A.4 — Disable image step in `autopilot.py`

At the image step entry point (find by grep for `body_image_state` write + `_enqueue_image`/`run_image_job` etc.), short-circuit to set `body_image_state="error", body_image_error=IMAGE_GEN_DISABLED_CODE` and skip onward. Delete `_find_stickfigures_lora_name`, `_strip_stickman_trigger_terms`, `_stickman_lora_blocked_for_prompt`. Comment-out the `suggest_image_prompt_batch` call site for now (Layer B deletes the imports).

Run: `python -m compileall app/services/autopilot.py`.

### Step D1.A.5 — Trim `scene_plan.py` and `scene_visual_plan.py`

Stub the two `suggest_image_prompt` calls to return an empty visual brief. Remove `flow_*` mode branches.

Run: `python -m compileall app/services/scene_plan.py app/services/scene_visual_plan.py`.

### Step D1.A.6 — Trim `visual_planner.py` (large file)

Remove every function that consumes `VisualBriefMode`, `ControlNet`, `IPAdapter`, `Stickfigures`, dual-prompt logic. Keep the `{subject, mood, environment}` builder. Run compileall after each batch of deletions.

### Step D1.A.7 — Trim `visual_relevance.py`, `diagnostics.py`, `operator_summary.py`, `prompt_quality.py`

Strip SDXL-specific emitters. Comment-out (don't delete) functions that will be unused; Layer B removes them.

Run: `python -m compileall app/services/`.

### Step D1.A.8 — Remove Stickfigures entry from `model_registry.py`

Delete `_find_stickfigures_lora()` and the `comfyui_stickfigures_lora` entry (lines 33–97). Run compileall.

### Step D1.A.9 — Edit `app/main.py` to drop flow router

Remove `flow` from the import on line 17 and the `app.include_router(flow.router)` on line 176. Run `python -m compileall app/main.py`.

### Step D1.A.10 — Edit `app/db.py:735` for tolerance

Change `_visual_source_mode` per the section above. Run the project-load smoke:

```bash
python -c "from app import db; db.init_db(); projects = db.list_projects(limit=200); print(len(projects))"
```

Expected: `127` (or more), no exception.

### Step D1.A.11 — Frontend strip (symbol-based, not line-based)

Use `rg` to find each forbidden anchor in `app/static/index.html`, `app.js`, `style.css` and remove the enclosing element/handler/rule:

```bash
rg -n "flow-asset-input|apply-repair-suggestion|preferredStyleReferenceValue|preferredControlImageValue|renderImagePromptPreview|submitComfyUiWorkflow|submitImageBatch|stickman-preview|dual-prompt-preview|repair-suggestion|sdxl_low_vram_lightning|sdxl_style_reference|sdxl_controlnet_depth|flow_assisted|flow_auto|flow_then_comfyui_fallback" app/static
```

Replace the entire Step 2 panel with a single disabled-state section. Run `npm run typecheck:frontend`.

### Step D1.A.12 — Layer A test pass

```bash
pytest tests/ -x \
  --ignore=tests/test_image_prompting.py \
  --ignore=tests/test_prompt_compiler.py \
  --ignore=tests/test_prompt_repair.py \
  --ignore=tests/test_stickman_evidence.py \
  --ignore=tests/test_visual_brief.py \
  --ignore=tests/test_flow_files.py
```

`test_image_worker.py`, `test_visual_planner.py`, `test_comfyui_routes.py` must be rewritten to pass against the disabled shape before this command goes green. `test_render_report.py`, `test_autopilot_worker.py`, `test_diagnostics.py`, `test_feature_workflow.py`, `test_candidate_selection.py` must be edited.

### Step D1.A.13 — Server smoke

```powershell
./run-newauto-9001.cmd
# wait 15 s
curl http://127.0.0.1:9001/api/system/health
curl -X POST http://127.0.0.1:9001/api/projects/<existing_flow_assisted_pid>/comfyui/workflow/submit
```

Expected:
- `/api/system/health` returns 200 JSON
- Submit endpoint returns **HTTP 503** with body `{"detail": {"error": "IMAGE_GEN_DISABLED_D1", "message": ...}}`
- Browser at `http://127.0.0.1:9001/` shows project list, Step 2 panel reads "이미지 생성 비활성 (D2 대기 중)", no console errors

### Step D1.A.14 — Layer A commit

```bash
git add -A
git status -s    # verify only intended files staged
git commit -m "$(cat <<'EOF'
chore: disable SDXL image gen + Flow loop behind compatibility shell
[full message per "Two-Commit Boundary" above]
EOF
)"
```

### Step D1.B.1 — Layer B deletions

```bash
git rm \
  app/services/image_prompting.py \
  app/services/prompt_compiler.py \
  app/services/comfyui_prompt_adapter.py \
  app/services/prompt_repair.py \
  app/services/prompt_strictifier.py \
  app/services/flow_prompting.py \
  app/services/visual_brief.py \
  app/services/image_generation_profiles.py \
  app/services/stickman_evidence.py \
  app/services/stickman_reference_library.py \
  app/services/stickman_layout_sketch.py \
  app/routers/flow.py \
  tests/test_image_prompting.py \
  tests/test_prompt_compiler.py \
  tests/test_prompt_repair.py \
  tests/test_stickman_evidence.py \
  tests/test_visual_brief.py \
  tests/test_flow_files.py \
  scripts/run_stickman_evidence_images.py \
  scripts/build_stickman_business_evidence.py \
  scripts/build_stickman_layout_sketches.py \
  scripts/run_stickman_lora_batch.py \
  scripts/check_comfyui_smoke.py
```

Then move workflow templates to archive (Git-tracked move, not delete):

```bash
mkdir -p docs/archive/workflows_legacy_sdxl
git mv app/workflow_templates/comfyui/txt2img_sdxl_basic.json docs/archive/workflows_legacy_sdxl/
git mv app/workflow_templates/comfyui/txt2img_sdxl_lightning.json docs/archive/workflows_legacy_sdxl/
git mv app/workflow_templates/comfyui/txt2img_sdxl_lora.json docs/archive/workflows_legacy_sdxl/
git mv app/workflow_templates/comfyui/txt2img_sdxl_stickman_lora.json docs/archive/workflows_legacy_sdxl/
git mv app/workflow_templates/comfyui/txt2img_sdxl_controlnet_depth.json docs/archive/workflows_legacy_sdxl/
git mv app/workflow_templates/comfyui/txt2img_sdxl_ipadapter_style.json docs/archive/workflows_legacy_sdxl/
git mv app/workflow_templates/comfyui/txt2img_sdxl_ipadapter_style_lora.json docs/archive/workflows_legacy_sdxl/
```

### Step D1.B.2 — Final type cleanup in `app/types.py`

Delete the now-unused class blocks:

- `class SdxlDualPrompt(TypedDict)`
- `class ControlNetDecision(TypedDict)`
- `class LoraDecision(TypedDict)`
- `class PromptRepairDecision(TypedDict)`
- `VisualBriefMode = Literal[...]`
- The `mode: VisualBriefMode` field on `class VisualBrief(TypedDict)` (if `VisualBrief` retained)

Run: `python -m compileall app/types.py`. Then full `python -m compileall app`.

### Step D1.B.3 — Forbidden-symbol acceptance check

```bash
rg -n "prompt_g|prompt_l|SdxlDualPrompt|ControlNetDecision|LoraDecision|PromptRepairDecision|VisualBriefMode|flow_assisted|flow_auto|flow_then_comfyui_fallback|txt2img_sdxl|Stickfigures|stickfigures|ip_adapter|controlnet_depth" \
  app/ scripts/ tests/
```

Expected output: zero matches under `app/` and live `scripts/` and live `tests/`. Hits inside `docs/` and `docs/archive/` are allowed (historical record).

### Step D1.B.4 — Narrowed pytest

```bash
pytest tests/ -x
```

Expected: 0 errors. The `--ignore` flags from Layer A become unnecessary because the offending tests are deleted/rewritten.

### Step D1.B.5 — Frontend typecheck final

```bash
npm run typecheck:frontend
```

Expected: 0 errors.

### Step D1.B.6 — Layer B commit

```bash
git add -A
git status -s
git commit -m "$(cat <<'EOF'
chore: remove SDXL/Flow/Stickman modules now that callers are disabled
[full message per "Two-Commit Boundary" above]
EOF
)"
```

### Step D1.B.7 — Rollback round-trip

```bash
git stash
git checkout pre-image-demolition-2026-05-17 -- app/
git status -s          # should show many SDXL files restored
git checkout chore/demolish-sdxl-image-gen -- app/
git stash pop
```

Expected: clean round-trip; rollback restores the SDXL tree; forward checkout restores demolished state.

### Step D1.B.8 — Merge to main

```bash
git checkout main
git merge --no-ff chore/demolish-sdxl-image-gen
git log --oneline -5
git branch -d chore/demolish-sdxl-image-gen
```

D1 complete. Two commits land on `main`.

## Risk Register (Revision 2)

| Risk | Mitigation |
|---|---|
| `visual_planner.py` 1910 lines tangled | Layer A deletions are batched per function; compileall after each |
| `app.js` 4839 lines, Flow/SDXL handlers interleaved with kept code | Symbol-anchored deletion via `rg`, not line-based |
| 21 existing `flow_assisted` rows + 21 SDXL-keyed rows | `_visual_source_mode` returns `upload_only` for legacy values; `body_image_options` JSON keys ignored at read time |
| Long-running queued image jobs at the time of deploy | Worker startup marks stale jobs as `IMAGE_GEN_DISABLED_D1` error |
| Reviewer-recommended autopilot test missing | Added `tests/test_autopilot_worker.py` edit (assert image step short-circuits) |
| ComfyUI workflow JSON templates would otherwise dangle | `git mv` to `docs/archive/workflows_legacy_sdxl/` preserves them as rollback fixtures |
| `model_registry.py` Stickfigures advertisement misleads users | Removed in D1.A.8 |
| `image_generation_profiles.py` was missed in Rev 1 | Added to Layer B delete |
| `prompt_strictifier.py` was missed in Rev 1 | Added to Layer B delete |
| MCP scripts (`newauto_mcp.py`, `newauto_stepwise_mcp.py`) might still reference deleted symbols | Pre-commit `rg` check in D1.B.3 covers them |
| Frontend brittle if line numbers drift | Symbol-anchored deletion; verified by post-edit `rg` |
| Server startup with stale jobs marks them all errors | Acceptable; clear `IMAGE_GEN_DISABLED_D1` code in `body_image_error` lets operator know |

## Rollback Procedures

**Plan A — full revert (cleanest):**

```bash
git checkout pre-image-demolition-2026-05-17
# or
git revert HEAD HEAD~1    # revert both Layer A and Layer B in one history-preserving go
```

**Plan B — Layer-B-only revert (keep disable, restore deleted code):**

```bash
git revert <layer-b-sha>
# Layer A's disable remains; only the deletions are undone.
# Useful if D2 hits a wall and we want the SDXL stack back as fallback while keeping the new typed boundary.
```

**Plan C — partial restore (cherry-pick one file):**

```bash
git checkout pre-image-demolition-2026-05-17 -- app/services/image_prompting.py
```

## Acceptance Checklist

D1 is **complete** when every item is true.

### Layer A acceptance

- [ ] Branch `chore/demolish-sdxl-image-gen` at HEAD
- [ ] `app/services/image_generation_disabled.py` exists
- [ ] `image_gen.py` POST handlers return 503 with `IMAGE_GEN_DISABLED_D1`
- [ ] `image_worker.py` is a disabled shell; stale jobs recovered to error on startup
- [ ] `autopilot.py` image step short-circuits to error, no Stickman branches
- [ ] `scene_plan.py`, `scene_visual_plan.py`, `visual_planner.py`, `visual_relevance.py`, `diagnostics.py`, `operator_summary.py`, `prompt_quality.py` trimmed
- [ ] `model_registry.py` Stickfigures entry removed
- [ ] `app/main.py` no longer imports/registers `flow`
- [ ] `db.py:735` coerces legacy `flow_*` to `upload_only` at read time
- [ ] `types.py` `VisualSourceMode` narrowed; SDXL types still present (deleted in Layer B)
- [ ] Frontend Step 2 collapsed to single disabled panel
- [ ] 8 Layer A tests rewritten/edited as per migration table
- [ ] `python -m compileall app` exit 0
- [ ] `npm run typecheck:frontend` exit 0
- [ ] `pytest tests/ -x --ignore=...` exit 0
- [ ] Project-load smoke prints `127` rows (or current count) without error
- [ ] Server starts; submit returns 503; browser Step 2 shows disabled panel
- [ ] Layer A commit lands with canonical message

### Layer B acceptance

- [ ] 23 files deleted via `git rm`
- [ ] 7 SDXL workflow JSON templates moved to `docs/archive/workflows_legacy_sdxl/` via `git mv`
- [ ] `app/types.py` final pass removes `SdxlDualPrompt` family + `VisualBriefMode`
- [ ] Forbidden-symbol `rg` returns zero hits under `app/`, `scripts/`, live `tests/`
- [ ] `python -m compileall app` exit 0
- [ ] `pytest tests/ -x` exit 0 (no `--ignore` needed)
- [ ] `npm run typecheck:frontend` exit 0
- [ ] Rollback round-trip succeeds (D1.B.7)
- [ ] Layer B commit lands; both commits on `main`

Time estimate: **~4 hours** Layer A + **~1 hour** Layer B. Total ~5 hours, vs Rev 1's ~3 hours optimistic. The extra time buys safer ordering and verified DB compatibility.

---

**Saved at:** `C:\Users\petbl\newauto\docs\d1-demolition-plan-2026-05-17.md`
