# Visual Relevance Recovery Plan (Revised)

Status: `[Phase 0, Phase 1, Phase 2, Phase 3, Phase 5, Phase 6a, and Phase 4 foundation implemented - Phase 6b next]`

Goal: generated images must match the current script at least at the core-keyword level, and preferably at the sentence/context level. The current Stickfigures LoRA path is installed and callable, but the image planning layer does not yet prove that an image belongs to the active sentence.

## 2026-04-27 Implementation Update

- Phase 0 emergency guard implemented:
  - generated ComfyUI image mappings now store `sentence_text`, `sentence_hash`, `project_id`, and `prompt_id`
  - scene plan ignores stale generated mappings
  - preflight exposes `visual_relevance`
  - render blocks mismatched generated media before FFmpeg
- Phase 1 keyword fixture cleanup implemented:
  - `app/services/image_prompting.py` was rebuilt with clean UTF-8 Korean keyword tables
  - `scripts/run_stickman_lora_batch.py` now uses clean Korean sample sentences
  - `tests/test_image_prompting.py` now uses clean Korean fixtures and daily-script keyword cases
- Phase 2 visual brief generator implemented:
  - `app/services/visual_brief.py` creates structured `VisualBrief` records
  - prompt suggestions now include `visual_brief`
  - each brief includes `mode`, `main_subject`, `action`, `primary_prop`, `scene`, `emotion`, `must_show`, `avoid`, and `rationale`
  - `must_show` is guaranteed to have at least one concrete item
- Phase 3 prompt compiler implemented:
  - `app/services/prompt_compiler.py` compiles positive/negative prompts from `VisualBrief`
  - positive prompts now start with the visual target instead of generic narration dump structure
  - prompt suggestions now include `missing_must_show`
  - `check_prompt_compliance()` verifies whether every `must_show` item is present in the compiled prompt
- Phase 5 preflight relevance gate implemented:
  - manifest-backed prompt metadata is now validated during preflight/render
  - `visual_relevance` now checks for `IMAGE_PROMPT_MANIFEST_MISSING`
  - `visual_relevance` now checks for `IMAGE_VISUAL_BRIEF_MISSING`
  - `visual_relevance` now checks for `IMAGE_PROMPT_MUST_SHOW_MISSING`
  - queued image jobs preserve `manifest_sentence_hash` so stale queued jobs can be detected after script changes
- Phase 6a sentence-level status display implemented:
  - `GET /api/projects/{pid}` and `GET /api/projects/{pid}/status` now include `visual_relevance_rows` and `visual_relevance_summary`
  - Step 2 image panel now shows per-sentence `PASS / STALE / MISSING` rows
  - each row surfaces the sentence, selected media path, first failure reason, and issue codes
- Phase 4 candidate generation/selection foundation implemented:
  - batch image jobs now support `variants_per_scene`
  - generated candidates are stored per sentence in `body_image_options["candidate_groups"]`
  - selected render mapping now keeps `selected_reason`, `candidate_index`, `candidate_total`, and `candidate_score`
  - when multiple candidates exist, the current selection is updated automatically from the highest candidate score
  - `POST /api/projects/{pid}/comfyui/candidates/select` now allows explicit manual selection for one sentence
- Verified:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`
  - `python -m pytest tests\test_prompt_compiler.py tests\test_visual_brief.py tests\test_image_prompting.py tests\test_visual_relevance.py tests\test_comfyui_routes.py tests\test_image_worker.py -q`

## Root Cause Summary

The latest Korean sample exposed four separate problems.

1. **Images were reused from a different script**
   - Final project `31309d66a597` used UTF-8 Korean narration from `storage/fixtures/korean_e2e_script.txt`.
   - Its media files were copied from earlier LoRA batches generated for different sample sentences.
   - Result: TTS/subtitles matched the Korean story, but images described unrelated concepts.

2. **Korean keyword matching is too shallow**
   - [app/services/image_prompting.py:14-44](app/services/image_prompting.py#L14-L44) `_VISUAL_KEYWORD_MAP` + `_EMOTION_MAP` — Korean literals are **clean UTF-8** (verified: `기도`, `눈물`, `기쁨`, `달리`, etc.).
   - [scripts/run_stickman_lora_batch.py:24-33](scripts/run_stickman_lora_batch.py#L24-L33) `DEFAULT_SENTENCES` — also **clean UTF-8** (verified: `"소년은 돌을 쥐고 거인을 향해 달려갑니다."` etc.).
   - **Therefore the encoding claim from the previous draft is partially outdated.** Real problem is *coverage* and *fallback*, not encoding:
     - When a sentence has no keyword match, fallback `"clear storytelling pose, single important object, strong emotional moment"` is generic and meaningless.
     - Many concrete Korean nouns (`연락`, `결심`, `편지`, `깨달음`, `평온`) are not in the map.
   - Mojibake was historically present in `app/static/index.html`, `app/static/app.js`, `agent.md`, `app/config.py` (per [render-subtitle-fixes-plan.md](render-subtitle-fixes-plan.md) Phase 5), already remediated. **Phase 1 below should focus on coverage expansion + an automated regression test, not re-cleaning files that are already clean.**

3. **The system does not have a real semantic planning stage**
   - Current [image_prompting.py:153-188](app/services/image_prompting.py#L153-L188) `suggest_image_prompt()` is keyword/template matching — it doesn't first decide subject / action / prop / place / emotion / visual fallback.
   - For abstract sentences, it should deliberately choose a keyword image, icon-like metaphor, or concrete object. Today it often produces generic poses.

4. **No quality gate verifies image relevance**
   - We save `image_prompts_manifest.json` ([image_prompting.py:207](app/services/image_prompting.py#L207) `save_image_prompt_manifest`), but no acceptance rule checks:
     - prompt was generated from the same project/script
     - sentence hash matches
     - expected keyword/prop/action appears in the prompt
     - selected media was generated for that sentence
   - Manual best-of selection happened after generation, but the final render path can still reuse stale media.

## Verified Code Reality (이미 있음 vs 추가)

| 영역 | 이미 있음 | 추가할 것 |
|---|---|---|
| LoRA workflow | `app/workflow_templates/comfyui/txt2img_sdxl_stickman_lora.json` ([검증]) | LoRA name/strength 를 **project config 에서 읽기** — 현재는 workflow JSON 안에 하드코딩 |
| Keyword map | `_VISUAL_KEYWORD_MAP` (24항목), `_EMOTION_MAP` (7항목), `_TEMPLATE_MATCHERS` (8항목) | 추상 명사·동사 표 확장 (`연락`, `결심`, `편지`, `평온`, `깨달음`, `회복`, `약속` 등) + 미스 시 fallback 강화 |
| Manifest | `save_image_prompt_manifest()` 가 `project_id`, `title`, `source`, `generated_at`, `visual_source_mode`, `content_mode`, `prompts[]` 저장 | `sentence_hash` (NFKC+SHA256) per-prompt 추가 |
| BodyImageMapping | `{sentence_idx, path, prompt}` ([types.py:68-71](app/types.py#L68-L71)) | `sentence_hash`, `sentence_text`, `selected_reason`, `user_accepted_at` 추가 |
| Visual mode | `VisualSourceMode = "upload_only" | "hybrid" | "comfyui_auto"` ([types.py](app/types.py)) | 새 mode 추가 X — 기존 enum 안에서 manual_import 표시는 **mapping 의 origin 필드**로 처리 |
| Preflight | `app/services/preflight.py` 존재 | 신규 relevance check 들을 **기존 preflight 에 추가** (별도 system 신설 X) |
| Scene/Render plan | `app/services/scene_plan.py`, `render_plan.py` 존재 | mapping `sentence_hash` 검증을 render_plan build 단계에 통합 |

## Required Policy Change

From now on, generated media must be treated as derived artifacts tied to one script version.

### Sentence hash 정의 (원본 plan 누락)

```python
import hashlib
import unicodedata

def sentence_hash(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).strip()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return digest[:16]   # 저장 공간 절약, 충돌 무시 가능 수준
```

→ **NFKC 정규화 + strip → SHA256 → 16자**. typo 수정 시 hash 변동 (의도). 띄어쓰기 수정도 변동 (NFKC 가 보장).

### Mapping schema 확장

```json
{
  "project_id": "...",
  "sentence_idx": 3,
  "sentence_text": "...",
  "sentence_hash": "a3f1b2...",
  "visual_brief": {
    "mode": "keyword_image",
    "main_subject": "single person",
    "action": "choosing between two options",
    "primary_prop": "large checklist",
    "scene": "forked path",
    "emotion": "hesitation",
    "must_show": ["forked path", "two arrows", "large checklist"]
  },
  "positive_prompt": "...",
  "negative_prompt": "...",
  "prompt_id": "...",
  "media_path": "scene_003.png",
  "lora_name": "Stickfigures-000005.safetensors",
  "lora_strength": 0.8,
  "origin": "generated",     // generated | manual_import | stock
  "user_accepted_at": "",     // ISO ts when 사용자가 명시적 override
  "selected_reason": "manual_pick" // manual_pick | auto_score | only_candidate
}
```

If `sentence_hash` does not match the current project sentence, render preflight must warn or block.

## Phase 0. Stop Stale Media Reuse

Goal: prevent the exact failure seen in `31309d66a597`.

Implementation status: `[Done - emergency guard]`

Implemented:

- `app/services/visual_relevance.py` added sentence hash helpers and generated-image mapping validation.
- `BodyImageMapping` now preserves `sentence_text`, `sentence_hash`, `project_id`, and `prompt_id`.
- ComfyUI imports now attach current sentence metadata to each generated image mapping.
- Scene plan building ignores stale generated mappings.
- Preflight now includes a `visual_relevance` check for `comfyui_auto` projects.
- Render now fails before FFmpeg if generated image mappings do not match the current script.

Verified:

- `powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1`
- `python -m pytest tests\test_visual_relevance.py tests\test_scene_plan.py tests\test_comfyui_routes.py tests\test_image_worker.py tests\test_render_plan.py -q`

Tasks:

- [types.py](app/types.py) `BodyImageMapping` 확장 — `sentence_hash`, `sentence_text`, `origin`, `user_accepted_at`, `selected_reason` 추가
- 새 컬럼 또는 기존 `body_image_options` JSON 안에 `mapping_manifest` 추가 (DB migration)
- render_plan build 시 (`app/services/render_plan.py`) 각 mapping 의 `sentence_hash` 가 현재 script 의 `sentences[sentence_idx]` hash 와 일치하는지 검증
- 스크립트가 변경되면 **`body_image_mappings[i].stale = True` 로 마킹** (TaskState `body_image_state` 와는 분리 — 전체 작업 상태가 아니라 per-sentence 상태)
- preflight 경고 코드 추가:
  - `IMAGE_SENTENCE_HASH_MISMATCH` (action: 해당 sentence 만 재생성 또는 manual accept)
  - `IMAGE_PROMPT_MANIFEST_MISSING` (action: 이미지 일괄 재생성)
  - `IMAGE_FROM_DIFFERENT_PROJECT` (action: 다른 프로젝트에서 복사된 미디어 — 명시 accept 필요)
- 수동 clone/import 시 `origin = "manual_import"` 로 마킹, 사용자가 명시 accept (`user_accepted_at`) 해야 render 통과

Acceptance:

- A project cannot silently render images generated for a different script.
- Reusing old images requires explicit `user_accepted_at` set, visible in render report.
- 기존 mapping (마이그레이션 시점) 은 `origin = "manual_import"` + `user_accepted_at = "<migration_ts>"` 로 자동 채움 (역호환).

## Phase 1. Korean Keyword Coverage + Encoding Regression Lock

Goal: keyword 매칭이 실패하는 빈도를 줄이고, encoding 회귀 자동 차단.

**원본 plan 의 "encoding cleanup" 부분 정정**: `image_prompting.py` 와 `run_stickman_lora_batch.py` 의 한글은 이미 clean UTF-8 (위 §"Verified Code Reality" 참조). 따라서:

Tasks:

- `_VISUAL_KEYWORD_MAP` 확장 — abstract Korean nouns 추가:
  - `연락`, `편지`, `메시지` → `holding a message envelope or phone with text bubble`
  - `결심`, `다짐` → `clenched fist with determined face`
  - `깨달음`, `이해` → `lightbulb above head`
  - `평온`, `고요`, `잠재` → `calm seated meditation pose`
  - `회복`, `재시작` → `phoenix-like upward gesture`
  - `약속`, `언약` → `two hands shaking firmly`
  - `갈림길` → `single character at a path that splits left and right`
  - `용서`, `화해` → `two characters facing each other with open hands`
- 한국어 동사형 어미 (`-했다`, `-합니다`, `-되었다`) 정규화 후 매칭
- Fallback 대체:
  - 현재 `["clear storytelling pose", "single important object", "strong emotional moment"]` (generic)
  - 신규: `must_show` 가 비면 sentence 의 명사 빈도 상위 1개를 prop 으로 강제 발탁 (Korean morphology 없이 단순 띄어쓰기 + 명사형 어미 휴리스틱)
- **회귀 자동화 (원본 plan 에서 좋은 아이디어)**:
  - `tests/test_image_prompting_encoding.py` — 파일 바이트를 read 해서 `image_prompting.py`, `run_stickman_lora_batch.py`, `app/services/stickman_reference_library.py` 등의 알려진 한글 literal 이 round-trip 통과 검증
  - `scripts/check_encoding.py` (이미 존재) 에 image 관련 파일 추가
- PowerShell inline Korean 회피: 모든 sample 는 `storage/fixtures/*.txt` (UTF-8) 또는 API/browser 입력으로

Acceptance:

- 신규 한국어 키워드 8개 매칭 테스트 통과
- 한국어 sentence 50개 sample (varied topic) 중 최소 80% 가 generic fallback 이 아닌 specific keyword 에 매칭
- `image_prompts_manifest.json` 의 한국어가 round-trip 안전

## Phase 2. Visual Brief Before Prompt

Goal: convert sentence/context into a structured visual decision before SDXL prompt text exists.

### Mode 결정 로직 (원본 plan 의 추상 규칙 구체화)

원본 plan: `mode = literal_scene | keyword_image | symbolic_metaphor` — "concrete vs abstract" 만 명시. 한국어에서 자동 분류는 Mecab/형태소 분석기 없이는 어려움.

**V1 (단순, 권장)**: 모든 sentence 에 `keyword_image` 기본 적용. `mode` 필드는 정보용. 핵심은 `primary_prop` 이 항상 채워지는 것.

```python
def build_visual_brief(text: str, project: ProjectRecord) -> VisualBrief:
    visual_tokens = _extract_visual_tokens(text)   # 기존 함수 재사용
    template = _select_template(text, project)
    primary_prop = visual_tokens[0] if visual_tokens else _fallback_prop_from_nouns(text)
    must_show = [primary_prop]
    if len(visual_tokens) > 1:
        must_show.append(visual_tokens[1])
    return {
        "mode": "keyword_image",   # V1 default
        "main_subject": "single stick figure",
        "action": _action_from_text(text),
        "primary_prop": primary_prop,
        "secondary_prop": visual_tokens[1] if len(visual_tokens) > 1 else "",
        "scene": template["key"],
        "emotion": _emotion_from_text(text),
        "must_show": must_show,
        "avoid": ["text", "logo", "crowd"],
        "rationale": f"matched: {visual_tokens}, template: {template['key']}",
    }
```

**V2 (선택, Ollama)**: gemma4:e4b 가 sentence + context 받아서 mode/subject/action/prop/emotion JSON 출력. VRAM 경합 정책 따름 (직렬). source draft 와 동일 GPU guard.

`app/services/visual_brief.py` 신규. **`image_prompting.py` 의 keyword 매칭은 그대로 유지** — visual_brief 가 그 결과를 더 풍부하게 구조화. 폐기 X.

### 통합 흐름

```
sentence
  → image_prompting._extract_visual_tokens()  (기존)
  → image_prompting._select_template()        (기존)
  → visual_brief.build_visual_brief()         (신규 — 위 두 결과 흡수)
  → prompt_compiler.compile()                 (Phase 3)
  → ComfyUI 호출
```

Acceptance:

- Each sentence has a readable brief in `image_prompts_manifest.json`
- `must_show` always contains at least one specific item (never empty)

## Phase 3. Prompt Compiler V2

Goal: make prompts short, object-first, and checkable.

Rules:

- Start with the required object/action, not generic style.
- Include both Stickfigures triggers: `Flipchartvisu`, `Stick figure`
- Keep one subject and one main prop.
- Generate prompt from `VisualBrief`, not raw sentence.

Prompt shape:

```text
Flipchartvisu, Stick figure, single centered stickman,
large [PRIMARY_PROP] clearly visible,
[ACTION],
[SCENE],
bold black outline, plain white background, high contrast, no text
```

Negative shape:

```text
tiny subject, missing main prop, crowd, multiple characters, text,
logo, detailed landscape, photorealistic, clutter
```

**Prompt compliance check (Phase 5 의 게이트 데이터)**:

```python
def check_prompt_compliance(prompt: str, brief: VisualBrief) -> list[str]:
    """반환: 누락된 must_show 항목 목록. 빈 리스트면 OK."""
    lowered = prompt.lower()
    missing = []
    for item in brief["must_show"]:
        if item.lower() not in lowered:
            missing.append(item)
    return missing
```

Acceptance:

- The positive prompt contains every `must_show` item or a known synonym (synonyms table 도입).
- The negative prompt includes `missing main prop` and `tiny subject`.

## Phase 4. Candidate Generation and Selection

Goal: stop trusting one image blindly. **단, 비용 관리 필수**.

### 비용 분석 (원본 plan 누락)

SDXL ~25s/image 가정:
- 60s 영상 (30 sentences) × 1 candidate = 12분 (현재)
- 60s × 3 candidates = 37분
- 60s × 5 best-of = 62분

Default 3 candidates 는 너무 무겁다. 권장:

| Project type | Default | Hard sentence (abstract/no-match) |
|---|---|---|
| Quick test | 1 | 1 |
| Standard | 1 | 3 |
| Quality | 3 | 5 |

UI 토글: `image_quality: "quick" | "standard" | "quality"` (project 단위).

Hard sentence 자동 감지:
- `_VISUAL_KEYWORD_MAP` 매칭 0건
- 또는 길이 ≥ 30자 에 명사 적음
- 또는 사용자가 manual flag

### Candidate metadata

각 candidate 에 저장:
- seed
- prompt
- visual brief
- sentence hash
- prompt id
- (optional) prompt compliance score (Phase 3 의 누락 must_show 개수)

### Selection

- Phase 4a: manual review in UI (체크박스 + 이미지 그리드)
- Phase 4b: lightweight automated scoring:
  - prompt compliance score (가중치 50%)
  - filename/metadata (가중치 20%)
  - 이미지 sharpness/contrast (가중치 30%, OpenCV 단순 측정 — 무거우면 skip)
- Phase 4c (선택): vision LLM 기반 — gemma4:e4b multimodal 활용 가능. VRAM 경합 정책 필수

Acceptance:

- 선택된 image 에 `selected_reason` 저장 (`manual_pick` | `auto_score:0.85` | `only_candidate`)
- Render uses selected candidates only, not arbitrary media order

## Phase 5. Render Preflight Relevance Gate

Goal: catch mismatches before wasting TTS/render time.

**기존 [app/services/preflight.py](app/services/preflight.py) 에 새 check 추가** — 별도 system 신설 X.

새 check 들:
- 모든 sentence 에 selected image 또는 user-accepted fallback 존재
- selected image 의 `sentence_hash` 가 현재 sentence 와 일치
- selected image 에 prompt/brief metadata 존재
- prompt 가 최소 1개의 must_show 항목 포함

새 error code (master plan 의 prefix 체계 따름):
- `IMAGE_VISUAL_BRIEF_MISSING`
- `IMAGE_SENTENCE_HASH_MISMATCH`
- `IMAGE_SELECTION_MISSING`
- `IMAGE_PROMPT_MUST_SHOW_MISSING`

Action hint table (사용자가 보는 텍스트):

```python
ACTION_HINTS = {
    "IMAGE_SENTENCE_HASH_MISMATCH": (
        "{n}개 이미지가 다른 버전의 스크립트로 생성되었습니다. "
        "[stale 만 재생성] 또는 각 이미지를 명시적으로 'Use anyway' 처리하세요."
    ),
    "IMAGE_VISUAL_BRIEF_MISSING": (
        "이미지가 visual brief 없이 만들어졌습니다 (legacy 또는 manual import). "
        "[전체 재생성] 또는 'Use anyway'."
    ),
    ...
}
```

**자동 복구 옵션**: preflight failure → UI 가 `[stale 만 재생성]` 버튼 제공. autopilot 의 image_enqueue 단계가 이 패턴 재사용.

Acceptance:

- Final render report lists per-segment relevance status (PASS / STALE / OVERRIDE / MISSING).
- 회귀 시 preflight 가 즉시 차단.

## Phase 6. UI / Operator Debug — 분할

원본 plan 이 9 항목 + 5 metric + selected_reason 다 한 phase 에 묶음. UI 작업 무거움. 분할:

### Phase 6a. Status display (P0 — Phase 5 와 함께)

Step 2 image panel — sentence 별 1줄 표시:

- ✓ / ⚠ / ✗ icon (PASS / STALE / MISSING)
- sentence 첫 30자 + "..."
- selected image thumbnail (있으면)

### Phase 6b. Detail panel (P1)

각 sentence 클릭 시 expand:

- visual brief mode + must_show keywords
- 사용한 template / prompt compiler mode
- LoRA name/strength
- 모든 candidate 들 (썸네일 + score)
- selected candidate + selected_reason
- relevance status + action_hint

### Operator metrics

기존 dashboard 에 카드 1개 추가:
- 총 sentence / selected / stale / missing brief / low-confidence

Acceptance:

- 사용자가 한 화면에서 어떤 이미지가 stale 한지 즉시 인지

## Phase 7. Rebuild Korean Sample (capcut Phase 2 cross-link)

**의존성 명시**: 이 Phase 의 step 6 ("Run chunk/full-script TTS track separately if voice consistency work has landed") 는 [capcut-omnivoice-enhancement-plan.md](capcut-omnivoice-enhancement-plan.md) **Phase 2a/2b** (TTS 1455 mitigation) 가 완료되어야 신뢰 가능. 둘 다 `[Pending]` 인 상태에서 동시 진행 시 결과 해석 어려움.

Procedure:

1. UTF-8 Korean script from `storage/fixtures/korean_e2e_script.txt` 사용
2. Generate `VisualBrief` for all sentences (Phase 2)
3. Compile prompts from briefs (Phase 3)
4. Generate `1` candidate per sentence (default), hard sentences `3`
5. Select candidates (manual or auto-score)
6. Capcut Phase 2 (TTS chunk) 완료 후 full TTS run
7. Render final MP4

Acceptance:

- `image_prompts_manifest.json` sentence text matches `tts_run_manifest.json`
- All media mappings have matching `sentence_hash`
- Final video contains no images from unrelated projects

## 우선순위 (의존성 정렬)

1. **Phase 0** — stale media blocking (가장 긴급, 다른 phase 무관하게 가능)
2. **Phase 1** — keyword coverage 확장 + encoding regression lock
3. **Phase 2** — VisualBrief V1 (heuristic, no LLM)
4. **Phase 3** — Prompt Compiler V2 (Phase 2 산출물 사용)
5. **Phase 5** — Render preflight gate (Phase 0 + 2 + 3 후 의미 있음)
6. **Phase 6a** — Status display (Phase 5 와 함께)
7. **Phase 4** — Candidate generation (선택 — quality 모드 토글로 옵트인)
8. **Phase 6b** — Detail panel (Phase 4 후)
9. **Phase 7** — Korean sample 재생성 (capcut Phase 2 완료 후)

## Hard Lesson

LoRA is not the image planner. It can improve style only after the system has chosen the right subject, action, and prop. The next implementation round must make image generation accountable to the current sentence before it tries to improve visual polish.

## 본 plan 의 핵심 변경 (원본 대비)

1. **Encoding 진단 정정** — `image_prompting.py` / `run_stickman_lora_batch.py` 는 이미 clean UTF-8. 진짜 문제는 keyword **coverage** 부족.
2. **Sentence hash 정의 명시** — NFKC + strip + SHA256[:16].
3. **VisualBrief 가 기존 image_prompting.py 폐기 X, 흡수**.
4. **Mode 결정 로직 V1 단순화** — 모든 sentence default `keyword_image`, `primary_prop` 항상 필수. V2 (Ollama) 는 옵션.
5. **Candidate 비용 분석 + 토글** — default 1, hard sentence 3, quality 모드 옵트인.
6. **Preflight 는 신규 system 아님** — 기존 `app/services/preflight.py` 에 check 추가.
7. **Stale 마킹 메커니즘 분리** — `body_image_state` (TaskState) 와 충돌 방지, `mapping.stale: bool` 별도 필드.
8. **Manual override 필드 추가** — `user_accepted_at` ISO ts.
9. **LoRA 하드코딩 제거** — project config 에서 읽음.
10. **Phase 6 분할** — 6a (status, P0) / 6b (detail, P1).
11. **Phase 7 cross-link 명시** — capcut Phase 2 완료 dependency.
12. **Auto-recovery UI** — preflight 실패 시 `[stale 만 재생성]` 버튼.
13. **Action hint table 명시** — 사용자가 보는 한국어 텍스트 일관 관리.
14. **Korean keyword 확장 항목 8개 명시** — `연락`, `결심`, `깨달음`, `평온`, `회복`, `약속`, `갈림길`, `용서`.
15. **Migration 호환** — 기존 mapping 은 `origin="manual_import"` + `user_accepted_at=migration_ts` 자동 채움.
