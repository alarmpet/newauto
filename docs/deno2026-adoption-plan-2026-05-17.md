# Deno2026 Resource Adoption Plan for newautostudio

Date: 2026-05-17
Status: spec-level plan. Per Superpowers writing-plans, each adopted section below produces its own bite-sized implementation plan before code is written.

## Strategy Update (2026-05-17, post-confirmation)

The earlier draft of this plan was **additive** (keep SDXL, add Z-Image as a parallel backend). The user has confirmed that the current image-generation subsystem has failed too many recovery attempts (see `docs/archive/plans_2026_04/visual-relevance-recovery-plan.md`, `essay-image-context-recovery-plan.md`, `chatgpt-image2-visual-quality-recovery-plan.md`, `visual-mismatch-recovery` series) and a clean rebuild is the correct response.

**Confirmed decisions:**

1. **SDXL ComfyUI image stack is demolished immediately**, from a blank slate. No A/B period. (User answer: "지금 당장 삭제, 백지에서 시작".)
2. **Flow / Veo manual loop is replaced by LTX 2.3 local I2V**. `app/routers/flow.py`, `flow_prompting.py`, and related UI panels are removed. (User answer: "LTX 2.3 I2V로 완전 대체, Flow 코드 삭제".)
3. **Disk reality (revised after live inspection):** C: drive started at 21.4 GB free; D: does not exist.
   - **pip cache + CrashDumps deleted (live)** → 31.83 GB free as of 2026-05-17.
   - **`music-auto/browser_profiles` skipped** — `automation_notebooklm` (8.56 GB) was modified today; music-auto is active. Cleaning that folder would break in-progress work.
   - **Android SDK / WSL Ubuntu** — pending user confirmation; gain ~8.8 GB total.
   - **The real cleanup target is inside `C:\Users\petbl\autotube\ComfyUI\models\` (102 GB)**, not user-profile caches. After D1 lands, SDXL stack files (11.8 GB) become dead weight; LTX 2 19B legacy stack (42.1 GB) and Qwen Image variants (47 GB) are likely removable subject to user confirmation. Cleanup is now **staged across phases** instead of upfront.

4. **ComfyUI install (confirmed live):** `C:\Users\petbl\autotube\ComfyUI` is the ComfyUI server newauto talks to. `app/config.py:86` already sets `COMFYUI_INSTALL_DIR` to that path. `output/` was modified today (2026-05-17 14:51) — ComfyUI is in active use. The hardcoded `D:\ComfyUI Model\models` path in `DenoLTXModelDownloader` widgets must be repointed to `C:\Users\petbl\autotube\ComfyUI\models` before LTX 2.3 weight downloads start.

The original "additive" priority phases (P0–P5) below this section have been replaced by a demolition-first track (D0–D5). The Sources Analyzed and Fit Assessment sections still apply; the architectural recommendations have flipped.

**Risk owned explicitly:** Z-Image Turbo Korean-direct has not been smoke-tested on this project's news / Bible / essay content. By demolishing SDXL before that smoke test, we accept a window where image generation may not work at all if Z-Image disappoints. The recovery path in that window is: revert via `git revert` of the demolition commit, since SDXL code is preserved in git history.

## Sources Analyzed

1. **Windows-Installer-for-Deno-AI-Studio** — https://github.com/Deno2026/Windows-Installer-for-Deno-AI-Studio
   - Electron-style Windows installer (`Deno AI Studio Setup 0.1.60.exe`)
   - Beginner-friendly launcher for open-source AI **audio/TTS/music** models
   - Uses Docker Desktop + WSL 2 for per-model isolation
   - Has a **Runtime Center** screen: GPU + Docker + disk + model readiness gates
   - Multi-language interface, model catalog with one-click install per model
   - Target VRAM: 8–16 GB with low-VRAM options
   - Update channel: `deno-ai-studio/updates/windows-x64/<versioned>.exe`
   - Models in catalog (verified from README): Qwen3-TTS 0.6B/1.7B, VoxCPM 2, Scenema Audio OSS, ACE-Step 1.5 XL SFT/Turbo, HeartMuLa oss-3B "Happy New Year", Stable Audio Open 1.0
   - License/source build is explicitly discouraged — `.exe` distribution only

2. **Deno-Image-Prompt-builder** — https://deno2026.github.io/Deno-Image-Prompt-builder/
   - Static GitHub Pages site, Korean UI, two builders:
     - `image.html` — stepwise card UI for image prompt direction (scene/emotion/color/texture/background, free-text addendum, system-prompt toggle, copy button, reset)
     - `video.html` — T2V vs I2V toggle, then scene mood → cut count → camera movement → motion characteristics; I2V path uploads reference image and lets the LLM read it first
   - **Output is a "LLM 상담 지시문"** (LLM consultation directive): a Korean prompt the user copies and pastes into ChatGPT / Gemini / Claude. The chatbot then asks clarifying questions, then emits the final image/video prompt.
   - This is **not** an inline image generator — it's a structured prompt scaffolder.
   - Channel: @Denoise-AI YouTube cross-link

3. **Google Drive folder** — `1Aq9yzvSMpM9EOQMIVEIwyrXd3LmcM5D6`
   - Title: **"ComfyUI Workflow 공유"** (Shared ComfyUI Workflows)
   - Cannot enumerate files via WebFetch (auth-walled). However, the user has already staged a curated subset locally — see sources #4 and #5 below — which gives us all the concrete artifacts we need without depending on the Drive listing.

4. **Local LTX 2.3 workflow bundle** — `C:\Users\petbl\newauto\LTX2.3\` (inspected directly)
   - Producer: Deno2026 / @Denoise-AI YouTube
   - Base video model: **LTX 2.3** by Lightricks (22B parameters)
   - Files present (sizes confirmed via `stat`):
     - `8GB VRAM Workflow/LTX2.3 8GB VRAM workflow.json` — 138 KB, 60 nodes — low-VRAM I2V variant
     - `8GB VRAM Workflow/LTX2.3 8GB VRAM workflow + Audio to Video.json` — 145 KB, 74 nodes — low-VRAM I2V + Audio→Video combined
     - `Audio To Video/Ltx2.3 Audio to video Deno workflow.json` — 177 KB, 121 nodes — full-quality A2V
     - `Image to Video/ver1 (260318)/Ltx2.3 image to video Deno workflow.json` — 93 KB, 127 nodes — initial I2V
     - `Image to Video/ver2 (dynamic) (260329)/Ltx2.3 ver2-image to video Deno workflow .json` — 117 KB, 110 nodes — dynamic-motion I2V
     - `Image to Video/ver3 (Multi Image) (260412)/LTX2.3 Multi Image Reference.json` — 123 KB, 111 nodes — multi-image reference I2V
     - `Video to audio (wan2.2)/Ltx2.3 Video To Audio Deno workflow.json` — 32 KB, 42 nodes — V2A with Wan2.2 tutorial link
     - One reference image and one reference audio per workflow under each subfolder
     - `Image to Video/ver1/ComfyUI 클라우드 워크플로우 (제한된 기능).txt` — ComfyUI Cloud share link `https://cloud.comfy.org/?share=8c2931d24c42` (cloud variant, fewer custom nodes)
     - `Video to audio (wan2.2)/Tutorial Link.txt` — `https://youtu.be/zqnXskluvM4`
   - Required model weights (from `DenoLTX23PresetLoader` and `LTXAVTextEncoderLoader` widget values):
     - Checkpoint: `ltx-2.3-22b-dev.safetensors`, `ltx-2.3-22b-dev_transformer_only_fp8_scaled.safetensors`, GGUF Q4_K_M: `LTX-2.3-22B-distilled-1.1-Q4_K_M.gguf`
     - Video VAE: `LTX23_video_vae_bf16.safetensors`
     - Audio VAE: `LTX23_audio_vae*` (LTXVAudioVAELoader points at the fp8 checkpoint)
     - Text encoder: `gemma_3_12B_it_fp8_scaled.safetensors`
     - Spatial upscaler: `ltx-2.3-spatial-upscaler-x2-1.0.safetensors`
     - LoRAs: `ltx-2.3-22b-distilled-lora-384.safetensors` (sampling 1–4), `ltx-2-19b-ic-lora-detailer*` (detail enhance), `ltx-2-19b-ic-lora-pose*` (pose)
     - Audio source-separation (Audio→Video): `MelBandRoFormer` from `https://huggingface.co/Kijai/MelBandRoFormer_comfy/tree/main` → `/models/diffusion_models/`
   - Custom node families used:
     - `DenoLTX*`: `DenoLTX23PresetLoader`, `DenoLTXMultiLoraLoader`, `DenoLTXModelDownloader`, `DenoLTXPromptGuide`, `DenoLTXSequencer`, `DenoMultiImageLoader`
     - `LTXV*`: `LTXVConditioning`, `LTXVImgToVideoConditionOnly`, `LTXVSeparateAVLatent`, `LTXVConcatAVLatent`, `LTXVAudioVAEEncode/Decode/Loader`, `LTXVEmptyLatentAudio`, `LTXVPreprocess`, `LTXVCropGuides`, `LTXVLatentUpsampler`, `LatentUpscaleModelLoader`, `LTXAVTextEncoderLoader`, `LTX2AudioLatentNormalizingSampling`, `LTXFloatToInt`, `LTXSequencer`, `LTX2_NAG`, `EmptyLTXVLatentVideo`
     - `MelBand*`: `MelBandRoFormerModelLoader`, `MelBandRoFormerSampler`, `TrimAudioDuration` (audio-source-separation for music vs vocals)
     - rgthree: `Power Lora Loader (rgthree)`, `Fast Groups Bypasser (rgthree)`, `Image Comparer (rgthree)`
     - VHS (video helpers): `VHS_LoadVideo`, `VHS_VideoCombine`, `VHS_VideoInfoSource`, `VHS_VideoInfoLoaded`
     - Post-processing: `RIFEInterpolation` (frame interpolation), `RTXVideoSuperResolution` (RTX SR), `RAMCleanup`, `ResizeImageMaskNode`, `FluxResolutionNode`, `SimpleCalculatorKJ`, `ComfySwitchNode`, `easy showAnything`
   - Recommended runtime settings (verified inside MarkdownNote widgets):
     - Output length: 5–20 seconds
     - FPS: 24 / 25 / 48 / 50
     - **NAG scale 13–15, NAG alpha 0.4–0.5** — primary lever to suppress unwanted on-screen text/subtitles in LTX 2.3 output
     - Two-stage rendering: low-res latent first (e.g. 0.2 MP), then spatial upscaler x2 to final resolution, with seed fixed across stages
   - **LTX 2.3 Prompt Enhancer template** (verbatim from `MarkdownNote title='Write a prompt using GPT'`): "LTX 2.3 Prompt Enhancer — Conversational Dual Output Version v2.1." Produces Prompt A (safe/stable) + Prompt B (cinematic). Rules: structure/action/camera/scene/audio in English; only in-world dialogue/lyrics in source language; preserve reference-image identity; no unsupported interactions.
   - **Foley Artist prompt template** (verbatim from `Video to audio (wan2.2)` MarkdownNote, both KR and EN variants): "당신은 이제부터 영상의 물리적 움직임을 소리로 설계하는 전문 '폴리 아티스트'입니다 … 음악(BGM, Melody)에 대한 묘사는 절대 포함하지 마세요." Output format: Prompt 1 (Realistic & Raw) + Prompt 2 (Detailed & Enhanced), each with a Korean translation summary.

5. **Local Z-Image Turbo workflow** — `C:\Users\petbl\newauto\Z image\` (inspected directly)
   - Files: `Z image turbo.json` (41 KB, 56 nodes) + `ref image.jfif` (73 KB)
   - Base image model: **Z-Image Turbo** — AuraFlow-family architecture (uses `ModelSamplingAuraFlow` node, `EmptySD3LatentImage`)
   - Required weights:
     - UNET: `z_image_turbo_fp8_e4m3fn.safetensors` (path `models/unet/`)
     - CLIP: `qwen_3_4b.safetensors` with type `lumina2` — **Korean prompts route through Qwen-3 4B; no translation required**
     - VAE: `ae.safetensors`
     - GGUF variant available at `https://huggingface.co/unsloth/Z-Image-GGUF/tree/main`
   - Sampler config (verified widget values):
     - 3 KSampler chains with `euler_cfg_pp` / `euler` samplers, `simple` / `beta` schedulers
     - Steps: 4 (turbo low) / 9 / 15
     - CFG: 1 / 1 / 4
     - Denoise: 0.2 / 0.6 / 1.0 (multi-pass refinement)
     - ModelSamplingAuraFlow shift: 3 / 5 / 10
     - Latent: `EmptySD3LatentImage` at 1024×1024×1, then `ImageScaleToTotalPixels bicubic ×3` for upscaled final
   - Built-in negative prompt (verbatim): "worst quality, low quality, lowres, blurry, out of focus, noisy, grainy, jpeg artifacts, compression artifacts, oversharpened, haloing, ringing, artifact, watermark, signature, text, logo, username, caption, frame, border, edge noise, vignette, lens dirt, deformed, disfigured, bad anatomy, extra limbs, mutated hands, poorly drawn hands, poorly drawn face, ugly, disgusting, mutated, …"
   - Sample positive prompts in the file: `"asian girl"`, `"카페에 앉아서 여성이 커피를 마시고 있다."` — confirms Korean-direct input works.
   - `SimplePromptBatcher` is used to batch multiple prompts per run.
   - Tooling helpers: `Image Comparer (rgthree)` for A/B preview, `Power Lora Loader (rgthree)` for stacked LoRAs (none enabled by default).

## Honest Limits of This Analysis

- The Drive folder web view is auth-walled, but the local LTX 2.3 and Z-Image folders provide the workflows directly. Other Drive items (if any) remain unknown.
- The prompt-builder page is mostly client-side; only the top-level UX patterns were observable through WebFetch. The exact card option enumerations (e.g. specific lighting/lens choices) are not visible without rendering the JS. This plan models the *pattern* and lets us mirror exact options later once we screenshot or scrape the rendered DOM.
- The installer is closed-source distribution. Its internals (Electron + Docker orchestration) are inferred from README/INSTALL/llms.txt, not from binary inspection.
- The custom `DenoLTX*` nodes are not currently installed in this newauto ComfyUI environment. The workflows reference them but I have not verified their availability against the local install. P0 must include a `pip / git-clone install` step for the `Deno-LTX-Custom-Nodes` ComfyUI extension before any workflow is loaded.
- Model weight downloads total a large amount of disk: LTX 2.3 fp8 (~22 GB) + GGUF Q4_K_M (~13 GB) + Gemma-3 12B fp8 text encoder (~12 GB) + spatial upscaler + LoRAs + MelBandRoFormer + audio VAE. **Plan must budget ≥ 60 GB free disk before P0 starts.**

## Fit Assessment vs. newauto

| Deno2026 capability | Closest newauto subsystem | Gap to close |
|---|---|---|
| Windows .exe installer + auto-update channel | `run.bat`, manual `omnivoice_env\` setup | We have no packaged installer for non-devs |
| Runtime Center health/gate screen | `/api/system/health` + `app/services/system_health.py` | We have the API; we don't gate the user before kicking off a render |
| Per-model isolated workspace via Docker | Single shared `omnivoice_env` + ComfyUI external | We do not isolate; conflicts surface as Python/torch version drift |
| Multi-language launch UI | English/Korean strings sprinkled across `app.js` | No first-class i18n layer |
| Curated audio model catalog (Qwen3-TTS, VoxCPM 2, Scenema, ACE-Step, HeartMuLa, Stable Audio Open) | OmniVoice TTS only; ACE-Step not integrated | We're TTS-only; we lack background music and song generation |
| Card-stepwise image prompt builder → LLM consultation directive | `app/services/image_prompting.py`, `prompt_compiler.py`, `prompt_repair.py` | We auto-generate prompts; we have no operator-facing scaffolded manual fallback |
| Video prompt builder (T2V/I2V + cut count + camera) | `app/routers/flow.py`, `flow_prompting.py`, `scene_visual_plan.json` | Flow prompts are sentence-locked; we don't expose cut/camera/movement vocabulary explicitly |
| Shared ComfyUI workflow library | `app/services/comfyui_workflows.py` (built-in templates only) | No community workflow ingest path |
| **Z-Image Turbo with Qwen-3-4B CLIP (Korean-direct prompt)** | SDXL pipeline in `app/services/comfyui_pipeline.py`; we translate Korean → English before prompt | We can skip translation entirely and feed Korean to Qwen-3 CLIP |
| **LTX 2.3 local image-to-video** (5–20s, 8GB VRAM variant exists) | Flow / Veo external loop in `app/routers/flow.py` (operator copy-paste) | We have no local video model; LTX 2.3 gives us one |
| **LTX 2.3 audio-to-video** (drives motion from narration WAV) | None | Lets narration drive lip-sync / motion-to-beat |
| **LTX 2.3 video-to-audio + Wan2.2** (foley generation) | `_mix_background_audio` only mixes user-uploaded BGM | Generates SFX/foley from rendered video automatically |
| **NAG scale 13–15 / alpha 0.4–0.5 subtitle suppression** | We burn ASS subtitles after render | LTX 2.3 has a known knob to keep generated frames text-free |
| **Two-stage low-res → spatial upscaler workflow** | Single-pass SDXL gen | Cheaper iteration loop; preview at 0.2 MP then commit |
| **`Power Lora Loader (rgthree)` stacked LoRAs** | `LoraDecision` single-LoRA in `prompt_compiler.py` | Multi-LoRA stack with per-LoRA on/off + strength |
| **LTX 2.3 Prompt Enhancer v2.1 + Foley Artist templates** | `consultation_prompt.py` (P1, not yet built) | Ready-made copy-paste templates we can ship verbatim |

## Demolition + Rebuild Phases (authoritative)

Each phase is a strategic bucket. Each bucket below produces its own bite-sized implementation plan in `writing-plans` format before code is touched. Phases D0 → D4 are the demolition-and-rebuild path; D5 retains the Runtime Center addition from the prior plan. The original additive "P-series" below D5 is kept verbatim as historical reference but is **superseded** — do not follow it as the live plan.

### D0. Disk Cleanup + Pre-Rebuild Snapshot (revised, staged across phases)

**Goal:** Free enough disk for **each phase's** download budget, and capture a known-good git checkpoint before the demolition commit lands. Cleanup is staged, not upfront, because much of the recoverable disk lives inside `autotube/ComfyUI/models/` and only becomes dead weight after the corresponding code is removed.

**Why staged:** The original "free 35 GB upfront" assumption assumed cleanup of user-profile caches. Live inspection showed those caches only yield ~10 GB safely (`music-auto/browser_profiles` is active and cannot be touched). The big disk lives inside ComfyUI models, but those models are still being used by the current SDXL/Qwen Image workflows until D1 lands. So the cleanup follows the demolition, not vice versa.

**Current status (2026-05-17, live):**

- ✅ pip cache deleted (~3.6 GB recovered)
- ✅ CrashDumps deleted (~4.6 GB recovered)
- ✅ git tag `pre-image-demolition-2026-05-17` placed on commit `f13fef6`
- ⏭️ `music-auto/browser_profiles` — SKIPPED (active automation, `automation_notebooklm` used today)
- ⏭️ Android SDK / WSL Ubuntu — pending user decision
- 📊 C: free space: **31.83 GB** (up from 21.4 GB baseline)

**Pre-existing models in `C:\Users\petbl\autotube\ComfyUI\models\` (live audit):**

| Subfolder | File | Size | Status after demolition |
|---|---|---|---|
| `checkpoints/` | `sd_xl_base_1.0.safetensors` | 6.46 GB | **dead after D1** |
| `checkpoints/` | `DreamShaper_8_pruned.safetensors` | 1.99 GB | **dead after D1** |
| `checkpoints/` | `ltx-2-19b-dev-fp8.safetensors` | 25.22 GB | **likely dead** (LTX 2.3 supersedes) |
| `diffusion_models/` | `qwen_image_fp8_e4m3fn.safetensors` | 19.03 GB | unused by newauto workflows; verify |
| `diffusion_models/` | `qwen_image_2512_fp8_e4m3fn.safetensors` | 19.03 GB | unused by newauto workflows; verify |
| `text_encoders/` | `gemma_3_12B_it_fp4_mixed.safetensors` | 8.80 GB | partial: LTX 2.3 wants fp8, this is fp4 |
| `text_encoders/` | `qwen_2.5_vl_7b_fp8_scaled.safetensors` | 8.74 GB | unused by newauto workflows; verify |
| `loras/` | `ltx-2-19b-distilled-lora-384.safetensors` | 7.15 GB | **dead** (LTX 2.3 LoRA differs) |
| `loras/` | `Stickfigures-000005.safetensors` | 0.21 GB | **dead after D1** |
| `clip_vision/` | `CLIP-ViT-H-14-laion2B-...safetensors` | 2.35 GB | **dead after D1** (IP-Adapter) |
| `ipadapter/` | `ip-adapter-plus_sdxl_vit-h.safetensors` | 0.79 GB | **dead after D1** |
| `latent_upscale_models/` | `ltx-2-spatial-upscaler-x2-1.0.safetensors` | 0.93 GB | partial: LTX 2.3 uses 2.3 version |
| `vae/` | `qwen_image_vae.safetensors` | 0.24 GB | unused by newauto workflows; verify |

**Recoverable totals:**
- SDXL stack (dead immediately after D1): **11.81 GB**
- LTX 2 (19B) legacy stack (dead immediately after D3 / can delete earlier if user confirms LTX 2 19B is not used elsewhere): **42.10 GB**
- Qwen Image variants (38 GB diffusion + 8.74 GB encoder + 0.24 GB VAE): **~47 GB** — needs explicit user confirmation; these were generated by `qwen_image_basic_api.json` / `makelens_qwen2511_api.json` workflows under `autotube/ComfyUI/workflows/`, not newauto

**Staged plan:**

| Phase | Cleanup performed | Disk after |
|---|---|---|
| D0 (done) | pip + CrashDumps | 31.83 GB |
| D0.5 (optional, user confirmed) | Android SDK, WSL Ubuntu | ~40 GB |
| D1 lands | (no cleanup yet — verify code runs without SDXL first) | 31.83 GB |
| D1 verified | Delete SDXL stack (11.81 GB) + Stickfigures + IP-Adapter + CLIP-ViT-H | ~44 GB |
| Pre-D3 download | Delete LTX 2 (19B) stack (42.10 GB) | ~86 GB |
| Optional | Delete Qwen Image variants if user confirms unused | ~133 GB |

**Acceptance for D0 baseline (already met):**
- C: free ≥ 30 GB ✅ (31.83 GB)
- `git tag pre-image-demolition-2026-05-17` ✅ at `f13fef6`
- ⚠️ Working tree has uncommitted changes (`.clinerules`, `.gitignore`, `app/config.py`, `app/db.py`, etc.). Before D1, **commit or stash** them so the tag rollback restores a clean state.

### D1. Demolition Commit (single PR, single revert button)

**Goal:** Delete every SDXL- and Flow-specific module in one commit so the codebase is reduced to "no image gen, no motion" before the rebuild starts. Render / TTS / scene plan / DB stay untouched.

**Why a single commit:** Bisect and revert both stay one-click. If Z-Image rebuild fails, `git revert <demolition-sha>` brings everything back.

**Files to delete (verified to exist):**

```
app/services/image_prompting.py
app/services/prompt_compiler.py
app/services/comfyui_prompt_adapter.py
app/services/prompt_repair.py
app/services/flow_prompting.py
app/routers/flow.py
tests/test_image_prompting.py
tests/test_prompt_compiler.py
tests/test_comfyui_prompt_adapter.py
tests/test_prompt_repair.py
tests/test_flow_uivision.py (already deleted in working tree)
```

**Files to gut (delete SDXL templates, keep file as empty registry):**

```
app/services/comfyui_workflows.py — remove txt2img_sdxl_basic, lightning, stickman_lora,
                                    ipadapter_style, ipadapter_style_lora, controlnet_depth.
                                    Leave the module exporting an empty workflow dict and the
                                    Workflow type for D2 to refill.
app/services/comfyui_pipeline.py  — remove SDXL submission paths. Keep only the generic
                                    "submit a workflow JSON, poll, return image" core.
app/services/visual_planner.py    — remove SDXL VisualBriefMode routing. Keep scene-text →
                                    abstract VisualBrief structure for D2 to read.
app/services/scene_plan.py        — strip flow_assisted / flow_auto / flow_then_comfyui_fallback
                                    VisualSourceMode handling. Keep upload_only, hybrid,
                                    comfyui_auto.
app/services/scene_visual_plan.py — same: drop Flow-specific modes.
```

**`app/types.py` removals:**

- `SdxlDualPrompt`, `ControlNetDecision`, `LoraDecision`, `PromptRepairDecision`
- `VisualBriefMode` (keep `VisualBrief` itself with `intent`/`subject`/`mood` only)
- `VisualSourceMode` flow variants: `flow_assisted`, `flow_auto`, `flow_then_comfyui_fallback`
- `VisualPlanSubjectMode` symbolic/metaphor variants if they were SDXL-specific

**`app/workers/image_worker.py` rewrite (not delete):**

- Remove all SDXL prompt repair retry logic, dual-prompt handling, ControlNet/IP-Adapter/LoRA routing, `candidate_reviews.repair_*` writes.
- Keep job lifecycle, heartbeat, queue management, ComfyUI HTTP submission boilerplate.
- After D1, the worker simply submits a workflow JSON and stores the result path. D2 fills in which workflow.

**`app/static/`:**

- Remove Flow asset attach panel, Flow prompt copy button, SDXL repair suggestion cards, dual-prompt preview, ControlNet/LoRA selectors from `index.html` + `app.js` + `style.css`.
- Keep the project list, script editor, TTS panel, render result panel, BGM panel, autopilot controls.

**`app/db.py`:**

- **No SCHEMA changes** in D1 (avoid migrations). The deprecated `body_image_options` keys (`prompt_g`, `prompt_l`, repair_*, ip_adapter_*, controlnet_*) just stop being read or written.
- Add an `image_backend_version: "v0"` marker to new projects so D2 can detect pre-rebuild rows and skip them.

**Acceptance:**

- `pytest` collects without errors (deleted tests, no orphan imports).
- `python -m compileall app` passes.
- Frontend `npm run typecheck:frontend` passes.
- Server starts. Loading an old project shows "이미지 생성 비활성" placeholder (no crash).
- Single commit message: `chore: demolish SDXL image gen + Flow loop (pre-Z-Image rebuild)`

### D2. Z-Image Turbo Rebuild (image generation, Korean-direct)

**Goal:** Stand up Z-Image Turbo (`Z image/Z image turbo.json`) as the **sole** image generation backend. Korean script passes through Qwen-3-4B CLIP without translation.

**Tasks:**

1. **Install custom nodes** (one-time, manual via ComfyUI Manager or git clone into `C:\Users\petbl\autotube\ComfyUI\custom_nodes\`):
   - `rgthree-comfy` (Power Lora Loader, Image Comparer)
2. **Download weights into `C:\Users\petbl\autotube\ComfyUI\models\`** (the existing install — `COMFYUI_INSTALL_DIR` already points here):
   - `models\unet\z_image_turbo_fp8_e4m3fn.safetensors` from `https://huggingface.co/unsloth/Z-Image-GGUF/tree/main` (use the GGUF Q4 if VRAM tight; fp8 e4m3fn fits 8 GB)
   - `models\clip\qwen_3_4b.safetensors` (paired Qwen-3 4B CLIP, type `lumina2`)
   - `models\vae\ae.safetensors`
   - Total ≈ 10 GB → 31.83 GB free is sufficient for D2 without further cleanup
3. **Vendor the workflow:**
   - Copy `Z image/Z image turbo.json` → `app/services/comfyui_workflows/community/deno2026/z_image_turbo_korean.json` with attribution header in a sibling `.metadata.json`.
   - Register in `comfyui_workflows.py` as the single default workflow.
4. **Replace `image_prompting.py` (deleted in D1) with a thin Korean-direct prompt builder** at `app/services/image_prompt.py`:
   - Input: sentence text (Korean as-is), optional VisualBrief mood/subject hints.
   - Output: positive prompt string (Korean), negative prompt string (Z-Image default verbatim).
   - **No translation, no dual prompts, no repair codes.**
   - Pure function. Tested with golden Korean strings.
5. **Rewrite `image_worker.py` submission path:**
   - Load `z_image_turbo_korean.json`.
   - Replace `CLIPTextEncode` widget values (positive + negative) with the strings from step 4.
   - Set `EmptySD3LatentImage` to project-resolved aspect ratio.
   - Set `ImageScaleToTotalPixels` final scale.
   - Submit, poll, save result under `storage/projects/<pid>/media/`.
6. **Project options simplification:**
   - `body_image_options` now contains only: `image_backend_version: "v1"`, `aspect_ratio`, `negative_prompt_override` (optional), `image_count_per_sentence` (default 1).
   - Old keys ignored. Stale projects show a "재생성 필요" badge.
7. **Smoke render:**
   - Run autopilot on one project per content type (news / Bible / essay) end-to-end through Z-Image.
   - Visual inspection: are images on-topic, legible, free of garbled Korean text artifacts?

**Acceptance:**

- `python -m compileall app` passes.
- `pytest tests/test_image_prompt.py -v` green (3 golden Korean prompts).
- `pytest tests/test_z_image_workflow_submission.py::test_submits_with_korean_positive_prompt -v` green (mocked ComfyUI HTTP).
- One manual smoke render of the Jensen/Nvidia news script produces 1 image per sentence with no crashes.
- Operator confirms image quality is **at least as good as** historical SDXL output on the same script. If not, escalate before D3.
- VRAM peak during single-image gen < 7 GB on RTX 4060 Laptop (8 GB total).

### D3. LTX 2.3 I2V Rebuild (motion generation, 8GB VRAM variant)

**Goal:** Stand up `LTX2.3/8GB VRAM Workflow/LTX2.3 8GB VRAM workflow.json` as the sole motion-generation backend. Each Z-Image still optionally becomes a 5-second LTX 2.3 clip.

**Tasks:**

1. **Pre-D3 disk gate:** before any LTX 2.3 download starts, delete the LTX 2 (19B) legacy stack from `C:\Users\petbl\autotube\ComfyUI\models\` (recovers ~42 GB, bringing C: free to ~86 GB). Requires user confirmation that LTX 2 19B is not used by any retained workflow:
   - `checkpoints\ltx-2-19b-dev-fp8.safetensors` (25.22 GB)
   - `loras\ltx-2-19b-distilled-lora-384.safetensors` (7.15 GB)
   - `latent_upscale_models\ltx-2-spatial-upscaler-x2-1.0.safetensors` (0.93 GB)
   - `text_encoders\gemma_3_12B_it_fp4_mixed.safetensors` (8.80 GB) — wrong quantization for LTX 2.3
2. **Install custom nodes** into `C:\Users\petbl\autotube\ComfyUI\custom_nodes\` (manual ComfyUI Manager / git clone):
   - `Deno-LTX-Custom-Nodes` (DenoLTX23PresetLoader, DenoLTXMultiLoraLoader, DenoLTXPromptGuide, DenoLTXSequencer, DenoLTXModelDownloader, DenoMultiImageLoader, LTX2_NAG)
   - `ComfyUI-LTXVideo` (LTXV* family)
   - `ComfyUI-VideoHelperSuite` (VHS_*)
   - `ComfyUI-Frame-Interpolation` (RIFE)
   - `ComfyUI-KJNodes` (SimpleCalculatorKJ)
   - `ComfyUI-RAMCleanup` (RAMCleanup node)
3. **Download GGUF Q4_K_M weights into `C:\Users\petbl\autotube\ComfyUI\models\`** (~35 GB total):
   - `models\checkpoints\LTX-2.3-22B-distilled-1.1-Q4_K_M.gguf` (~13 GB)
   - `models\clip\gemma_3_12B_it_fp8_scaled.safetensors` (~12 GB)
   - `models\vae\LTX23_video_vae_bf16.safetensors` (~1 GB)
   - `models\vae\LTX23_audio_vae*.safetensors` (~1 GB)
   - `models\upscale_models\ltx-2.3-spatial-upscaler-x2-1.0.safetensors` (~3 GB)
   - `models\loras\ltx-2.3-22b-distilled-lora-384.safetensors` (~2 GB)
   - Skip ic-lora-detailer chain initially (YAGNI; add only if motion quality is poor)
4. **Fix the hardcoded path:**
   - `DenoLTXModelDownloader` widget value in the staged workflows defaults to `D:\ComfyUI Model\models`. The newauto-side workflow loader must rewrite this to `C:\Users\petbl\autotube\ComfyUI\models` before submitting to ComfyUI.
4. **Vendor the workflow:**
   - Copy `LTX2.3/8GB VRAM Workflow/LTX2.3 8GB VRAM workflow.json` → `app/services/comfyui_workflows/community/deno2026/ltx23_i2v_8gb.json` with attribution.
5. **New service `app/services/motion_clip.py`:**
   - Pure function `build_motion_clip_job(project, sentence_idx, still_path) -> WorkflowSubmission`.
   - Inputs: still produced by D2, sentence text (for `LTXVConditioning` text prompt), aspect ratio, duration target (default 5s), FPS (default 24 then RIFE → 48).
   - Sets `LTX2_NAG` scale = 14, alpha = 0.45 by default (subtitle suppression).
   - Two-stage policy: stage 1 at 0.2 MP fixed seed → stage 2 spatial upscale ×2 only if `body_image_options["motion_quality"] == "two_stage"`. Default single-stage for speed.
6. **New `app/workers/motion_worker.py`** (parallel to `image_worker.py`):
   - Same lifecycle pattern (heartbeat, queue, retry-with-backoff).
   - Submits the I2V workflow, writes `storage/projects/<pid>/media/motion_<idx>.mp4`.
7. **Render integration:**
   - `app/services/render.py` `_build_visual_track` (line 712) currently treats each media file as either image or video. Verify the video branch (`-t <segment_duration> -i <path>`) handles LTX 2.3 outputs (24/48 fps mp4) without re-encoding loops.
   - Add `body_image_options["motion_enabled"] = bool` (default `True` for new shorts-format projects, `False` for landscape essay projects).
8. **Simplify scene_plan fields:**
   - Drop the old Flow-specific intermediate fields (`flow_prompt_manifest_path`, etc.).
   - Add `motion_clip_path`, `motion_clip_duration_sec`, `motion_clip_nag_scale`, `motion_clip_nag_alpha`.

**Acceptance:**

- `python -m compileall app` passes.
- `pytest tests/test_motion_clip.py -v` green (workflow JSON parametrization, NAG widget value correctness, seed determinism).
- Manual smoke: one shorts-format Jensen/Nvidia scene produces a 5-second LTX 2.3 clip at 768×432, NAG-suppressed (no baked subtitles), in < 5 min on RTX 4060 Laptop.
- RIFE 24→48 fps interpolation holds total duration within ±100 ms.
- `_validate_output_duration` passes after motion clips are stitched into the final video.

### D4. Consultation Mode (paste-in templates, manual fallback)

**Goal:** When Z-Image or LTX 2.3 output disappoints on a specific sentence, give the operator a one-click "복사" button that emits a Korean directive to paste into ChatGPT / Gemini / Claude. Three templates ship verbatim from the LTX 2.3 folder — no rewriting.

**Tasks:**

1. **New service `app/services/consultation_prompt.py`:**
   - `build_image_consultation_directive(project, sentence_idx) -> str` — Korean directive in the Deno2026 image.html shape, asking the LLM to play art director and emit a final Korean Z-Image prompt.
   - `build_video_consultation_directive(project, sentence_idx, mode: Literal["t2v", "i2v"]) -> str` — verbatim **LTX 2.3 Prompt Enhancer v2.1** template from `LTX2.3/Image to Video/ver1/.../MarkdownNote 'Write a prompt using GPT'`.
   - `build_foley_consultation_directive(video_path) -> str` — verbatim **Foley Artist Protocol** template (KR + EN) from `LTX2.3/Video to audio (wan2.2)/.../MarkdownNote`.
2. **New router `app/routers/consultation.py`** with three `POST /api/projects/{pid}/consultation/{image|video|foley}` endpoints returning `{directive, copy_payload}`.
3. **UI:**
   - Sentence card: "🧑‍🎨 이미지 상담문 복사" button next to manual prompt edit field.
   - Sentence card: "🎬 비디오 상담문 복사" button next to motion clip preview.
   - Render result panel: "🔊 폴리 상담문 복사" button per rendered segment.
   - All three open a modal with the directive + a Copy button + a paste-back field that overrides the next render's positive prompt.
4. **No external LLM call.** Operator owns the chatbot session. This is the explicit "operator-in-the-loop" pattern from Deno2026.

**Acceptance:**

- `pytest tests/test_consultation_prompt.py -v` green (3 templates, golden-file comparison against verbatim Deno2026 text).
- Manual smoke: operator copies image directive → pastes into ChatGPT → gets a Korean prompt → pastes back into newauto → next render uses the override.

### D5. Runtime Center Gate (preflight before autopilot)

**Goal:** Promote `/api/system/health` from a debug endpoint to the first-render gate. The autopilot button stays disabled until all hard gates are green.

**Tasks:**

1. Extend `SystemHealth` in `app/types.py`:
   - `z_image_ready: bool` (UNET + CLIP + VAE present)
   - `ltx23_video_ready: bool` (GGUF + Gemma text encoder + VAE + upscaler + LoRA present)
   - `ltx23_custom_nodes_ready: bool` (DenoLTX + LTXV + rgthree + VHS + RIFE installed in ComfyUI)
   - `models_disk_free_gb: float`
2. `app/services/system_health.py` populates the new fields by probing model file existence and ComfyUI `/object_info` endpoint for node availability.
3. New UI route `/runtime` rendered as a status grid: ffmpeg, CUDA, OmniVoice torch, LM Studio reachability, ComfyUI reachability, Z-Image ready, LTX 2.3 ready, custom nodes ready, disk free.
4. Hard-gate `autopilot_start` button: disabled until all hard rows are green. Soft rows (BGM, OAuth) only warn.
5. Preflight integration: `app/services/preflight.py` calls the same probes so worker-side failures match UI-side failures.

**Acceptance:**

- Removing `z_image_turbo_fp8_e4m3fn.safetensors` from disk turns the Z-Image row red and disables autopilot.
- Stopping ComfyUI server flips the ComfyUI row within 30 s.
- `pytest tests/test_system_health.py -v` green.

### Phases D-series Summary

```text
D0 (35 GB cleanup + git tag)                   ── ~30 min, manual
  └─ D1 (demolition commit: SDXL + Flow rm -rf) ── ~2 hours, one PR
       └─ D2 (Z-Image Turbo rebuild)             ── ~1 day + smoke renders
            └─ D3 (LTX 2.3 I2V rebuild)          ── ~2 days + smoke renders
                 └─ D4 (consultation mode)        ── ~0.5 day, templates verbatim
                      └─ D5 (Runtime Center gate) ── ~1 day
```

Total: ~5 working days from D0 to D5. After D5, the codebase is dramatically smaller (≈10 modules deleted, ≈3 added) and the image+motion pipeline runs entirely on local Korean-direct models.

### Rollback Plan

If Z-Image quality fails the D2 smoke acceptance:

```powershell
git checkout pre-image-demolition-2026-05-17
```

Restores the SDXL stack verbatim. The demolition was one commit; the revert is one command. Disk space remains free; downloaded LTX 2.3 weights can stay on disk for a later retry.

---

## Historical: Original Additive P-Series (superseded by D-series above)

The phases below were the original additive proposal. They are kept for context only. **Do not follow them as the live plan** — the D-series is authoritative.

### P0. Workflow Ingest (LTX2.3 + Z-Image + Drive) — lowest risk, highest leverage

**Goal:** Vendor the locally staged Deno2026 workflows (`C:\Users\petbl\newauto\LTX2.3\` and `C:\Users\petbl\newauto\Z image\`) plus any Drive-only workflows into `app/services/comfyui_workflows/community/deno2026/` with attribution, schema validation, manual review gate, and a dependency-check report before submission.

**Why first:** Pure additive change. No new runtime. Reuses existing ComfyUI integration that already loads workflows. Immediate quality lever for image generation, which is currently the largest user-visible failure mode (per `research.md` history: "ComfyUI scenes sometimes match the script weakly"). The local LTX 2.3 + Z-Image bundle gives us **concrete, inspected** workflow JSON we can wire up without waiting on the Drive auth.

**Tasks:**

- Stage workflows under `workflows/_inbox/deno2026/` (already partially done — `LTX2.3/` and `Z image/` exist at the repo root; the import script normalizes them into the canonical inbox).
- New script `scripts/import_comfyui_workflow.py`:
  - Reads each `.json`, asserts ComfyUI version field, lists all referenced nodes, **lists missing custom nodes against the current local install** (in particular the `DenoLTX*`, `LTXV*`, `MelBand*`, `RTXVideoSuperResolution`, `RIFEInterpolation`, `rgthree`, `easy showAnything` families).
  - Lists referenced model files against local model paths: checkpoints, UNETs, CLIPs, VAEs, LoRAs, text encoders, upscalers, audio VAEs.
  - Estimates total disk needed for missing weights against `shutil.disk_usage` free GB.
  - Writes an import report to `storage/comfyui/import_reports/<workflow>.json` with status `ready`, `missing_nodes`, `missing_models`, or `disk_short`.
  - Refuses to copy a workflow that has missing custom nodes; only stages the JSON if every node type is resolvable.
- New service `app/services/comfyui_workflow_catalog.py`:
  - Lists vendored community workflows with `{name, author, license, source_url, required_nodes, required_models, capability_tags}`.
  - Capability tags drawn from workflow content: `image_t2i`, `image_korean_clip`, `video_i2v`, `video_a2v`, `video_v2a`, `low_vram_8gb`, `audio_source_separation`, `multi_image_reference`.
  - Surfaces via `/api/comfyui/workflows` so Step 2 UI can pick a community workflow per project.
- DB: extend `body_image_options` with keys `comfyui_workflow_id` (image gen) and a new `video_workflow_id` (motion stage). No schema migration (JSON blob).
- UI: Step 2 → "Workflow" dropdown lists built-in + community workflows with attribution and capability tags shown. A "missing-deps" inline warning appears if the workflow's required nodes/models are not installed.
- Acceptance:
  - `import_comfyui_workflow.py` flags exactly the missing `DenoLTX*` nodes on our current ComfyUI install (verification: run the script today; expected output ≥ 5 missing-node names).
  - `Z image turbo.json` imports cleanly once `z_image_turbo_fp8_e4m3fn.safetensors`, `qwen_3_4b.safetensors`, and `ae.safetensors` are present.
  - `tests/test_comfyui_workflow_catalog.py::test_rejects_missing_nodes` is red, then green.

**Open question for the user:** Are these workflows freely re-distributable (the user has staged them locally so the answer is likely yes, but author attribution must be preserved — `@Denoise-AI` and any per-workflow author notes). License confirmation determines whether we vendor verbatim or register hash + source URL only.

### P0.5. Z-Image Turbo: Korean-direct image pipeline

**Goal:** Add **Z-Image Turbo** as a first-class image backend alongside the existing SDXL ComfyUI path, eliminating the Korean→English translation step before image generation.

**Why right after P0:** The current pipeline routes Korean script through translation before SDXL prompt assembly (`prompt_compiler.py`, `image_prompting.py`). Z-Image Turbo's `qwen_3_4b.safetensors` CLIP accepts Korean directly. Removing the translation step removes a known semantic-drift source ("scenes match script weakly" in `research.md`).

**Tasks:**

- Install weights (operator step, one-time):
  - `models/unet/z_image_turbo_fp8_e4m3fn.safetensors` from `https://huggingface.co/unsloth/Z-Image-GGUF/tree/main`
  - `models/clip/qwen_3_4b.safetensors`
  - `models/vae/ae.safetensors`
  - Confirm via `app/services/system_health.py` extension (new field `z_image_ready: bool`).
- Wire `Z image turbo.json` into `app/services/comfyui_workflows.py` as a new template name `z_image_turbo_korean`.
- Extend `app/services/comfyui_prompt_adapter.py` to handle the Z-Image shape:
  - Positive prompt: Korean text passed through unchanged.
  - Negative prompt: the verbatim Z-Image default negative is pre-filled and editable.
  - Sampler chain: respect the three-pass design (4 steps → 9 steps → 15 steps, CFG 1/1/4, denoise 0.2/0.6/1.0, ModelSamplingAuraFlow shift 3/5/10).
  - Total pixels: `ImageScaleToTotalPixels bicubic ×3` final upscale.
- Add a project-level toggle `body_image_options["image_backend"] = "sdxl" | "z_image_turbo_korean"`. Default: `sdxl` (no behavior change for existing projects).
- Update `prompt_repair.py` to skip translation-related repair codes when backend is `z_image_turbo_korean` (Korean prompts cannot have "English grammar" issues).
- Acceptance:
  - One sentence from the Jensen/Nvidia smoke project renders via Z-Image Turbo with the Korean script as positive prompt verbatim.
  - Render wall-clock < 30s on RTX 4060 Laptop at 1024×1024×3 upscale.
  - Side-by-side `Image Comparer (rgthree)` shows Z-Image vs SDXL output for the same sentence.
  - `tests/test_z_image_backend.py::test_korean_prompt_passthrough` green.

**YAGNI cut:** Do not port every SDXL knob (ControlNet, IP-Adapter, stickman LoRA). Z-Image Turbo's value is fast Korean-direct generation. ControlNet/IP-Adapter parity belongs to a follow-up plan only if needed.

### P0.7. LTX 2.3 local image-to-video (replaces Flow for shorts)

**Goal:** Adopt the **LTX 2.3 image-to-video** workflows to produce 5-second motion clips per sentence locally, replacing the manual Flow / Veo copy-paste loop for shorts-style projects.

**Why:** The Flow integration in `app/routers/flow.py` requires the operator to open Flow, paste a prompt, generate, and attach the result manually per sentence. LTX 2.3 is a local 22B video model with an 8GB-VRAM variant (`LTX2.3 8GB VRAM workflow.json`) and a quality variant (`v2 dynamic`, `v3 multi-image`). Local generation removes the manual loop and avoids Flow rate limits.

**Tasks:**

- Disk + weights gate:
  - Pre-flight: ≥ 60 GB free under `models/`.
  - Download checkpoints/text-encoder/VAE/LoRAs/upscaler listed in source #4.
  - The `DenoLTXModelDownloader` node points at `D:\ComfyUI Model\models` by default — make this path configurable via newauto config and respected by the downloader node widget value.
- Install custom node packs:
  - `Deno-LTX-Custom-Nodes` (provides `DenoLTX*` and `LTX2_NAG`)
  - `LTXVideo` Comfy custom nodes (provides `LTXV*` family)
  - `rgthree-comfy` (Power Lora Loader, Fast Groups Bypasser, Image Comparer)
  - `ComfyUI-VideoHelperSuite` (VHS nodes)
  - `ComfyUI-Frame-Interpolation` (RIFE)
  - Document each in `app/services/comfyui_workflow_catalog.py` as a required-node manifest.
- Wire three LTX 2.3 workflow variants into newauto:
  - `ltx23_i2v_8gb` (8 GB VRAM) — default for RTX 4060 Laptop
  - `ltx23_i2v_dynamic` (v2) — quality tier when VRAM allows
  - `ltx23_i2v_multi_image` (v3) — multi-image reference for character consistency
- Extend `app/services/scene_plan.py` to optionally emit a per-sentence "motion clip" job that takes the already-generated Z-Image / SDXL still as input and produces an LTX 2.3 video segment.
- Render integration:
  - Each sentence may now have a motion clip (`.mp4`) in addition to a still.
  - `_build_visual_track` in `app/services/render.py` (line 712) already accepts video segments via `VHS_VideoCombine`-style outputs; verify the existing kenburns/still-locked path is bypassed when a motion clip is present.
  - Honor the NAG-suppression note: **NAG scale 13–15, NAG alpha 0.4–0.5** is the default to prevent LTX 2.3 from baking subtitles into the video. These become typed fields under `body_image_options["ltx_nag_scale"]` and `body_image_options["ltx_nag_alpha"]`.
- Two-stage rendering policy:
  - Stage 1 at 0.2 MP / fixed seed for preview.
  - Stage 2 spatial-upscale ×2 only after operator approves stage 1.
  - This matches the Deno2026 memo: "1단계에서 마음에 드는 장면이 나오면 2단계로 업스케일링".
- Acceptance:
  - One sentence from a smoke project renders a 5-second LTX 2.3 clip at 768×432 (low-res) on 8GB VRAM in < 5 minutes.
  - NAG knob removes baked subtitles on a known-bad seed.
  - RIFE interpolation upgrades 24fps to 48fps without duration drift.
  - `_validate_output_duration` in `render.py` still passes when motion clips replace stills.

**Explicit non-goals:**
- LTX 2.3 does **not** replace ComfyUI image gen. Stills are still primary; motion clips are an additive layer for shorts-format projects.
- The full-quality `Ltx2.3 Audio to video Deno workflow.json` (121 nodes) is deferred to a separate phase. P0.7 ships the 8GB and ver2-dynamic variants only.

### P0.8. LTX 2.3 audio-to-video (deferred behind P0.7)

**Goal:** Add the `Audio To Video` and `8GB VRAM + Audio to Video` workflows so a narration WAV can drive video motion directly.

**Why later than P0.7:** Useful primarily for music-video / lyric-video format. News/essay workflows are still served by I2V + still pipeline. Ship only after P0.7 is stable.

**Tasks (outline only — full plan written when scheduled):**

- Add `MelBandRoFormer` weights for music/vocal separation (audio source separation step in the workflow).
- Plumb `tts/audio_raw.wav` (already produced today) directly into `LTXVAudioVAEEncode` instead of using a separate music source.
- Add a `body_image_options["motion_source"] = "image" | "audio"` switch.
- Acceptance: one sentence renders an A2V clip where motion is visibly synced to narration cadence (subjective gate; no automated test).

### P0.9. LTX 2.3 video-to-audio (Wan2.2) — automatic foley

**Goal:** Use the `Video to audio (wan2.2)` workflow to auto-generate foley/SFX backing for rendered video segments, replacing the requirement that the operator upload BGM/SFX manually.

**Tasks (outline only):**

- Capture the **Foley Artist** prompt template verbatim into `app/services/consultation_prompt.py` as `build_foley_consultation_directive(video_path)`.
- The workflow is small (42 nodes) and uses a single Wan2.2 checkpoint; document the model URL.
- Wire output `.wav` into `_mix_background_audio` in `render.py` as the foley track (separate from BGM).
- Strict mode: foley generation is opt-in per project (`body_image_options["foley_enabled"]`).
- Acceptance: a 5-second rendered clip plays with auto-generated foley that matches on-screen physical interactions; user can A/B against no-foley.

### P1. Image / Video / Foley Prompt Consultation Mode (image.html + LTX 2.3 Prompt Enhancer + Foley Artist templates)

**Goal:** Add a stepwise card UI inside Step 2 that emits a Korean "LLM consultation directive" the operator can paste into ChatGPT/Gemini/Claude when our automated prompt + repair loop produces weak images.

**Why second:** Smallest blast radius. Pure additive UI. Reuses existing project artifacts. Acts as a manual fallback for `prompt_repair.py` retries, which today exit with a "suggested prompt" the operator must reword by hand.

**Design:**

- New service `app/services/consultation_prompt.py` with **three** verbatim templates that ship from day one (no rewriting — we already have the canonical text from the LTX 2.3 folder MarkdownNotes):
  - `build_image_consultation_directive(project, sentence_idx) -> str`
    - Korean directive in the Deno2026 image.html shape — "당신은 art director입니다. 아래 문장과 의도를 읽고 누락된 요소(장면/감정/색감/질감/배경)를 질문하세요. 그 후 ComfyUI에 직접 넣을 수 있는 최종 prompt를 prompt_g / prompt_l 두 줄과 negative prompt 한 줄로 출력하세요. 한국어 응답 금지, 결과는 영어."
    - When `image_backend == "z_image_turbo_korean"`, the directive flips: **prompt stays in Korean**, no translation requested.
  - `build_video_consultation_directive(project, sentence_idx, mode: Literal["t2v","i2v"]) -> str`
    - **Use the LTX 2.3 Prompt Enhancer v2.1 template verbatim.** It already enforces dual output (Prompt A stable / Prompt B cinematic), English structure with native-language dialogue, reference-image identity preservation, and physical-plausibility rules. We do not need to re-author this.
  - `build_foley_consultation_directive(video_path) -> str`
    - **Use the Foley Artist template verbatim (both KR and EN versions).** Output format already specifies Prompt 1 (Realistic & Raw) + Prompt 2 (Detailed & Enhanced) with Korean translation summaries.
- Inputs: existing `sentences`, `body_image_mappings`, `image_prompts_manifest.json`, `VisualBrief`, current `candidate_reviews.repair_*` fields, plus `image_backend` and `video_workflow_id` from `body_image_options`.
- New router `app/routers/consultation.py`:
  - `POST /api/projects/{pid}/consultation/image` returns `{directive, target_models, clipboard_payload}`.
  - `POST /api/projects/{pid}/consultation/video` accepts `{sentence_idx, mode: "t2v"|"i2v"}`.
  - `POST /api/projects/{pid}/consultation/foley` accepts `{video_path}`.
- UI: Step 2 sentence card gets:
  - "AI 이미지 상담문 복사" button next to the existing "Repair" action.
  - "AI 비디오 상담문 복사" button next to the Flow attach panel (replaces the no-vocab Flow free-text path).
  - "AI 폴리 상담문 복사" button on the render result panel (post-render).
- Card-step UX (the Deno2026 lift): the modal walks through `scene → emotion → color → texture → background` chips for image, and `scene_mood → cut_count → camera_movement → motion_intensity` chips for video. Chips default-pre-selected from the project's existing `VisualBrief` and `body_image_mappings` motion fields.
- No automated submission to external LLM. Operator pastes into ChatGPT / Gemini / Claude.
- The flip side: once the operator gets back an English prompt, they paste it into the existing manual prompt edit field (`apply repair suggestion` already exists per `research.md` 2026-04-30 notes).
- Acceptance:
  - For a stale-mapping sentence in a known-failing project, the directive contains all five categories pre-filled.
  - Round-trip test: directive → ChatGPT (manual) → paste back → ComfyUI submission succeeds.
  - Unit tests cover empty-VisualBrief and missing-repair-suggestion paths.

**YAGNI cut:** Do not build option cards for every imaginable lens/lighting choice up front. Start with the five categories Deno2026 ships and add only what fails in practice.

### P2. Video Prompt Consultation Mode + Flow Vocabulary

**Goal:** Extend P1 to the video side, modeled on Deno2026's `video.html`. Two paths (T2V and I2V) with explicit vocabulary for **cut count** and **camera movement**, emitted as a consultation directive for Flow / Veo / Sora.

**Why third:** Builds on P1 infrastructure. The current Flow integration in `app/routers/flow.py` produces sentence-locked prompts but does not surface cut/camera vocabulary; this fills that gap.

**Design:**

- Extend `app/services/consultation_prompt.py` with `build_video_consultation_directive(project, sentence_idx, mode: Literal["t2v", "i2v"]) -> str`.
- Add typed enums to `app/types.py`:
  - `CameraMovement = Literal["static", "pan_left", "pan_right", "tilt_up", "tilt_down", "dolly_in", "dolly_out", "orbit_left", "orbit_right", "handheld", "crane_up", "crane_down"]`
  - `CutCount = Literal["single", "two_cuts", "three_cuts"]`
  - `MotionIntensity = Literal["minimal", "subtle", "moderate", "dynamic"]`
- Persist on `body_image_mappings[i]` as optional fields. Default unset.
- UI: existing Flow panel in Step 2 gets a "Video 상담문 복사" button per sentence + a T2V/I2V toggle.
- Acceptance:
  - I2V directive includes the attached reference image filename so the chatbot knows to read it first.
  - T2V directive includes cut count + camera move drawn from the new typed fields.
  - The directive output is deterministic across runs given the same inputs (golden-file test).

### P3. Runtime Center Screen (Deno installer pattern)

**Goal:** Promote `/api/system/health` from a debug endpoint into a first-screen gate. User cannot start an autopilot/render until every required check is green or explicitly waived.

**Why fourth:** Eliminates a large class of "I started a render and it died 30s in" failures, which today only surface in worker logs.

**Design:**

- Extend `SystemHealth` in `app/types.py` with the existing fields + new ones discovered during P0/P0.5/P0.7/P1/P2:
  - `comfyui_workflow_count: int`
  - `community_workflow_count: int`
  - `consultation_mode_ready: bool` (always true; placeholder for future external LLM auth)
  - `node_present: bool`, `node_version: str` (already proposed in the HyperFrames opinion; stays here)
  - `z_image_ready: bool` — UNET + Qwen-3-4B CLIP + VAE present
  - `ltx23_video_ready: bool` — LTX 2.3 fp8 or GGUF + Gemma-3-12B fp8 text encoder + LTX23 VAEs present
  - `ltx23_custom_nodes_ready: bool` — Deno-LTX + LTXV + rgthree + VHS + RIFE installed in ComfyUI
  - `models_disk_free_gb: float` — visible to the operator before triggering large downloads (LTX 2.3 stack ≈ 50–60 GB)
- New UI route `/runtime` rendered as a status grid:
  - rows for ffmpeg, CUDA, OmniVoice torch import, LM Studio reachability, ComfyUI reachability, disk free, oauth ready
  - each row has color + last-checked timestamp + a "재검사" button
  - block-the-button gate: "오토파일럿 시작" stays disabled until all hard gates pass; soft gates (OAuth, BGM) show warnings only
- Preflight integration: `app/services/preflight.py` already exists. Have it consume the same checks the Runtime Center surfaces, so the UI and worker share a single source of truth.
- Acceptance:
  - With ffmpeg removed from PATH, Runtime Center shows red and the autopilot button is disabled.
  - With CUDA available but OmniVoice import broken, the screen names the specific failure and links to `storage/logs/tts_worker.log`.
  - Toggling LM Studio off and on flips the row within 30s.

**Explicitly out of scope:** Docker-based per-model isolation. Our OmniVoice venv + LM Studio + ComfyUI pattern works on this machine; adding Docker doubles install complexity for no current pain.

### P4. Audio Catalog Expansion (BGM + Song Generation)

**Goal:** Borrow the Deno2026 audio-model catalog pattern to add **background music** and **song generation** to newauto, sitting next to the existing OmniVoice narration.

**Why fifth:** Larger surface area, but the most directly user-visible new capability. The Deno2026 catalog tells us exactly which open-source models are viable today and within our 8GB VRAM envelope.

**Targets, in priority order:**

1. **Stable Audio Open 1.0** — short BGM beds keyed to scene mood. Smallest VRAM footprint. Output: ~30s loopable wav.
2. **ACE-Step 1.5 XL Turbo** — full song generation if the script is a music video / lyric video. Larger model; only if VRAM allows.
3. **Qwen3-TTS 0.6B / 1.7B** — alternative narration voice. Could supplement or replace OmniVoice for languages OmniVoice doesn't cover. Korean coverage check required first.

**Design notes:**

- Do **not** add Docker. Add a small per-model `app/services/audio_models/<name>.py` adapter that spawns the model inside its own venv (same pattern as `tts_worker.py`'s OmniVoice spawn).
- Extend `body_image_options` with `bgm_source: Literal["none", "user_upload", "stable_audio_open", "ace_step"]`.
- Existing `_mix_background_audio` in `render.py` already accepts a BGM wav; we just need to produce that wav from a model instead of an upload.
- New `app/services/audio_catalog.py` mirrors `model_registry.py`'s shape so the UI can list installed audio models the same way it lists TTS models.
- Acceptance:
  - One scene of the Jensen/Nvidia smoke project renders with a Stable Audio Open BGM bed under the OmniVoice narration.
  - VRAM peak does not exceed 14 GB during BGM + image generation overlap.
  - BGM is duckable; existing `bgm_ducking_enabled` is respected.

**Explicit non-goal:** Qwen3-TTS does not replace OmniVoice. It is offered as an alternative, not a swap. OmniVoice has tuned Korean profiles already.

### P5. Packaged Windows Installer

**Goal:** Produce a `.exe` that a non-developer can double-click to get newauto running, including ffmpeg, the OmniVoice venv bootstrap, and a desktop shortcut.

**Why last:** Highest engineering cost, lowest immediate user value for the current user (the developer is the only operator today). Worth doing only after P0–P4 have solidified the runtime contract.

**Design notes:**

- **Do not use Electron.** newauto is a Python FastAPI app — wrapping it in Electron just to mimic Deno AI Studio's chrome adds 200MB of Chromium for no benefit.
- **Use Inno Setup or NSIS** to wrap:
  - The repo source under `%LOCALAPPDATA%\newauto\`
  - A `python -m venv` bootstrap on first run (cache `omnivoice_env.zip` and unzip)
  - ffmpeg shipped alongside or downloaded from a pinned mirror at install time
  - A desktop shortcut that launches `run.bat`
- **Auto-update channel** mirrors Deno2026's pattern: `updates/windows-x64/newauto-Setup-<semver>.exe` published as a GitHub release, with the running app polling `/releases/latest` once per launch and offering an in-app upgrade.
- License: ours stays as today; ffmpeg ships as a separate runtime dependency the installer downloads, not bundled, to keep licensing clean.
- Acceptance:
  - Fresh Windows 11 VM with no Python, no ffmpeg, no CUDA → run setup → newauto opens to Runtime Center within 5 minutes.
  - Runtime Center detects the missing CUDA driver and links the user to the NVIDIA driver page instead of failing silently.

## What Not to Do

- Do **not** copy Deno AI Studio's Docker-per-model architecture. Our pipeline is single-machine Python; Docker adds image-build complexity, WSL2 dependency, and disk pressure (>30GB per model) for no current benefit.
- Do **not** treat the prompt builder as a service to call automatically. The whole point of the Deno2026 pattern is operator-in-the-loop — copy/paste into a chatbot the user already pays for. Trying to auto-call ChatGPT/Gemini behind it defeats the design and adds API key plumbing.
- Do **not** mass-import every workflow from the Drive folder without per-workflow review. ComfyUI workflows can reference custom nodes that download arbitrary files; treat them as untrusted input.
- Do **not** rewrite `app.js` to add a heavyweight i18n framework just to mirror Deno2026's multi-language launch. Our UI is mostly Korean already; English mirror strings can be added per-screen as needed.
- Do **not** vendor `Deno AI Studio Setup 0.1.60.exe` itself. Their installer manages their own models on their own update channel; we just borrow patterns.
- Do **not** promise users music generation in the UI until P4 is actually verified on this machine's 8GB VRAM. Add only after a successful smoke render.

## Dependency Plan

- **No new runtime dependencies** required for P0, P1, P2. Pure Python additions over existing services.
- **P3** requires no new dependencies; reuses `system_health.py` and `preflight.py`.
- **P4** adds:
  - `stable-audio-open` weights (~5GB) — manual download, pinned SHA-256.
  - Optional `ace-step` weights (~12GB) — only if `--enable-ace-step` flag is set during install.
  - No new pip packages unless the model demands them (most are stand-alone CLIs or HuggingFace `from_pretrained`).
- **P5** adds Inno Setup or NSIS as a build-time dependency, not a runtime one. ffmpeg downloaded at install time from a pinned mirror.

## Verification Gates (Superpowers verification-before-completion lens)

Per phase, no completion claim until the corresponding command is freshly run and its output captured:

| Phase | Verification command | Pass condition |
|---|---|---|
| P0 | `pytest tests/test_comfyui_workflow_catalog.py -v` | All tests green; vendored workflow renders one image end-to-end |
| P1 | `pytest tests/test_consultation_prompt.py -v` + manual round-trip with one project | Directive contains all five Deno categories; copy button returns clipboard text |
| P2 | `pytest tests/test_consultation_prompt.py::test_video_directive -v` + Flow manual smoke | T2V/I2V toggle reflected; cut count + camera move present |
| P3 | Remove ffmpeg from PATH → load `/runtime` → autopilot button disabled | Disabled state observed in browser; auto-test via Playwright if possible |
| P4 | One Jensen scene renders with BGM bed | VRAM peak < 14 GB; BGM ducked under narration |
| P5 | Fresh Windows VM run-through | Runtime Center green within 5 min on first launch |

## Brainstorming Counter-Check (alternatives considered)

- **Alternative to P0** (workflow ingest): build our own workflows from scratch using the existing ComfyUI custom node set. **Rejected** — slower, no community quality signal, no upside.
- **Alternative to P1** (consultation mode): expand the automated `prompt_repair` loop with more retries. **Rejected** — past retries have shown diminishing returns past the second pass; operator-in-the-loop is the actual escape hatch.
- **Alternative to P3** (Runtime Center): keep the API and let the user `curl` it. **Rejected** — non-devs can't read JSON; the whole point of borrowing the Deno UX is to make the gate visible.
- **Alternative to P4** (audio expansion): keep OmniVoice + user-uploaded BGM only. **Acceptable as steady-state** if VRAM headroom is the bottleneck. Treat P4 as opt-in.
- **Alternative to P5** (installer): keep `run.bat` as the only entry point. **Acceptable** while the developer is the only user. Promote only when handing the tool to non-devs.

## Recommended Sequencing

```text
P0   (workflow ingest)                     ── 1–2 days, immediate quality win
  ├─ P0.5 (Z-Image Turbo Korean-direct)    ── 1–2 days, removes translation step
  │    └─ P1 (consultation: image+video+foley) ── 1 day, paste-in templates already verbatim
  │         └─ P2 (video consultation + Flow vocab) ── 1 day, parallel UX
  │              └─ P3 (Runtime Center screen)      ── 2 days, gate the gates
  ├─ P0.7 (LTX 2.3 I2V 8GB + dynamic)      ── 3–5 days, local video motion
  │    ├─ P0.8 (LTX 2.3 A2V)               ── 2 days, opt-in narration-driven motion
  │    └─ P0.9 (LTX 2.3 V2A foley)         ── 2 days, opt-in auto SFX
  └─ P4 (audio catalog: BGM first)         ── 3–5 days, real new capability
       └─ P5 (Windows installer)           ── 5+ days, only if shipping to non-devs
```

P0 → P0.5 → P0.7 → P3 is the high-leverage block. P0.8, P0.9, P4 are real product expansions. P5 is packaging work that only matters if newauto goes beyond a one-developer tool.

## Verification Gates — additions for new phases

| Phase | Verification command | Pass condition |
|---|---|---|
| P0 | `python scripts/import_comfyui_workflow.py --inbox workflows/_inbox/deno2026 --report-only` | Each of the 8 staged JSONs gets a report; `Z image turbo.json` reports models-only-missing (no node gaps); LTX 2.3 JSONs report 5+ missing-node names |
| P0.5 | `pytest tests/test_z_image_backend.py::test_korean_prompt_passthrough -v` + manual smoke render | Korean prompt → image render < 30s on RTX 4060 Laptop; visual fidelity equal-or-better than SDXL+translation path |
| P0.7 | `pytest tests/test_ltx23_i2v.py::test_8gb_workflow_renders -v` + manual smoke | 5s clip at 768×432 generated < 5 min; NAG knob removes baked subtitles on known-bad seed; RIFE 24→48 fps holds duration |
| P0.8 | Manual smoke render with narration WAV → A2V clip | Subjective: motion cadence visibly tracks narration peaks |
| P0.9 | Manual smoke render with rendered clip → V2A foley | Subjective: foley matches on-screen physical interactions; no melodic BGM bleed |

## Concrete Open Questions Added by the Local Workflows

- The `DenoLTXModelDownloader` node has a hardcoded widget value of `D:\ComfyUI Model\models`. Does this path exist on this machine, or do we need to repoint it before triggering the downloader? (Affects whether P0.7 can run today or needs a config fix first.)
- The 8GB VRAM workflow uses the GGUF Q4_K_M variant. Is the user willing to download Q4_K_M (~13 GB) or do they prefer the fp8 variant (~22 GB) with the spatial upscaler trick? (Affects disk budget and quality ceiling.)
- The `Power Lora Loader` slots have 4 sampling stages, each with the `ltx-2.3-22b-distilled-lora-384` enabled and a 5-slot `ic-lora-detailer` chain. Do we keep all five LoRAs as defaults, or expose them as togglable in the UI?
- For Z-Image Turbo: the workflow ships with the negative prompt prebaked. Do we let the operator edit it per project, or treat it as a frozen "good defaults" string?

## Open Questions for the User

1. **License of Drive workflows** — vendor under our repo or only register URLs and prompt operator to import?
2. **External LLM** for consultation mode — does the operator have ChatGPT Plus / Gemini Advanced / Claude paid access? (Affects which model gets called out in the directive template.)
3. **Audio capability priority** — is BGM under narration the actual need, or full song/lyric video generation? Different model picks.
4. **Installer target audience** — is anyone besides the developer running newauto today? If no, defer P5 indefinitely.

## Bottom Line (post-confirmation)

**The plan is demolition + rebuild, not additive.** The SDXL image stack and Flow manual loop are deleted in one commit. Z-Image Turbo (Korean-direct via Qwen-3-4B CLIP) becomes the sole image backend. LTX 2.3 8 GB VRAM I2V (GGUF Q4_K_M) becomes the sole motion backend. The Korean→English translation step disappears. Consultation mode (using the verbatim LTX 2.3 Prompt Enhancer v2.1 and Foley Artist templates) covers manual fallback. Runtime Center gates the autopilot button.

**Order of execution:**

1. **D0** — Free 35 GB on C:, tag `pre-image-demolition-2026-05-17`. Manual.
2. **D1** — Single demolition commit removing SDXL + Flow modules. ~2 hours.
3. **D2** — Z-Image Turbo rebuild + Korean-direct prompt builder. ~1 day.
4. **D3** — LTX 2.3 I2V 8 GB rebuild + motion worker. ~2 days.
5. **D4** — Consultation mode (3 verbatim templates). ~0.5 day.
6. **D5** — Runtime Center gate. ~1 day.

**Rollback:** `git checkout pre-image-demolition-2026-05-17` restores the SDXL stack verbatim. Demolition is one commit; revert is one command.

**Treat this document as the spec.** Each D-phase still needs a writing-plans-grade bite-sized task list before code is touched. D0 can start now.

---

**Saved at:** `C:\Users\petbl\newauto\docs\deno2026-adoption-plan-2026-05-17.md`
