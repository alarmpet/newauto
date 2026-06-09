# NewAuto Studio Media Image Generation Master Guide Plan

> Deprecated: this document has been superseded by `docs/media-prompt-operating-guide.md`. Use the new guide as the single active Media prompt reference. Keep this file only as legacy background until it is moved to `docs/archive/media_prompt_legacy/`.

Updated: 2026-05-16 KST

이 문서는 NewAuto Studio의 `Media` 단계에서 더 이상 여러 문서를 오가며 헷갈리지 않도록 만든 단일 기준 문서다. 목적은 분명하다.

- 대본 문장마다 맥락에 맞는 이미지 프롬프트를 안정적으로 만든다.
- ComfyUI, SDXL, LoRA를 목적에 맞게만 사용한다.
- 이미지 생성이 과도하게 오래 걸리거나 무한 재시도처럼 보이지 않게 한다.
- 렌더 직전까지 엉뚱한 이미지가 들어가는 일을 차단한다.

## 0. 문서 역할

이 문서는 **Media 내부 이미지 엔진 품질 기준**이다. 즉 visual planner, prompt coverage gate, ComfyUI workflow, LoRA 선택, 후보 점수, visual relevance, render 연결의 판단 기준을 정의한다.

사용자에게 보이는 기본 Media UI 기준은 `docs/media-simplification-plan-2026-05-15.md`를 따른다. 기본 UI에서는 candidate score, repair, mismatch report, Flow 같은 고급 용어를 숨기고, 업로드/프롬프트 생성/ComfyUI + LoRA 생성/선택 이미지 교체처럼 사용자가 직접 이해할 수 있는 동작만 노출한다.

전체 제품 로드맵과 Windows Studio 패키징 방향은 `docs/newauto-windows-studio-master-plan-2026-05-15.md`를 따른다. 따라서 이 문서의 고급 검증 항목은 기본 UI에 그대로 노출하지 않고, operator/debug/advanced view 또는 내부 preflight 기준으로 사용한다.

참고로 통합한 기존 문서:

- `comfyui.txt`
- `comfysdxl.txt`
- `image-context-quality-plan.md`
- `docs/archive/plans_2026_04/stickman-lora-rollout-plan.md`
- `docs/archive/plans_2026_04/sentence-context-image-generation-plan.md`
- `docs/archive/plans_2026_04/simple-diagrammatic-sdxl-image-plan.md`
- `docs/archive/plans_2026_04/visual-relevance-recovery-plan.md`
- `docs/archive/plans_2026_05/editorial-symbolic-image-upgrade-plan.md`

## 1. 최종 원칙

Media 단계의 성공 기준은 "이미지가 예쁜가"가 아니라 "대본의 현재 문장과 핵심 의미가 맞는가"다.

따라서 NewAuto Studio는 다음 순서를 지켜야 한다.

```text
script
-> sentence split
-> LLM visual planner
-> domain visual vocabulary
-> structured visual brief
-> SDXL/ComfyUI prompt compiler
-> prompt coverage gate
-> ComfyUI generation
-> candidate scoring and selection
-> visual relevance preflight
-> scene/render plan
-> render
```

이 순서를 건너뛰고 문장을 바로 SDXL 프롬프트로 넣으면 안 된다. 특히 추상어, 산업 설명, 정책/기술 해설은 문장 그대로 이미지 모델에 전달하면 generic drift가 쉽게 발생한다.

## 2. 담당 코드 경로

현재 NewAuto Studio에서 이미지 프롬프트 생성과 Media 워크플로를 담당하는 실제 경로는 아래다.

- `app/services/domain_detection.py`
  - 대본/문장의 도메인을 판정한다.
  - 예: `ev_battery`, `ai_policy_conflict`, `news_explainer`, `essay`

- `app/services/visual_planner.py`
  - LM Studio + `google/gemma-4-e4b`를 사용해 문장별 시각 기획을 만든다.
  - 산출물은 `scene_visual_plan.json`이다.

- `storage/visual_vocab/*.json`
  - 도메인별 시각 어휘 사전이다.
  - LLM이 문장 의미를 구체적 시각 객체로 바꾸는 데 사용한다.

- `app/services/visual_brief.py`
  - LLM 실패나 fallback 시에도 최소한의 구조화된 `VisualBrief`를 만든다.

- `app/services/image_prompting.py`
  - visual plan/brief를 SDXL용 positive/negative prompt로 바꾼다.

- `app/services/comfyui_pipeline.py`
  - ComfyUI 제출, 결과 import, 후보 점수, retry 판단을 담당한다.

- `app/workers/image_worker.py`
  - 실제 batch image job을 수행한다.
  - 재시도, plan regeneration, fallback downgrade, repair retry가 여기서 실행된다.

- `app/services/visual_relevance.py`
  - 생성 이미지가 현재 대본 문장과 맞는지 검사한다.
  - `sentence_hash`, prompt manifest, candidate score, issue code를 확인한다.

- `app/services/scene_plan.py`, `app/services/render_plan.py`
  - 최종 선택 이미지를 장면/렌더 계획에 연결한다.

중요: 과거 문서에 등장하는 `prompt_compiler.py`는 현재 일부 개념과 연결되지만, EV/배터리 Media 경로의 핵심 수정 지점은 `visual_planner.py`, `image_prompting.py`, `visual_brief.py`, `comfyui_pipeline.py`, `image_worker.py`다.

## 3. 프롬프트 생성 규칙

LLM visual planner는 문장마다 아래 schema를 반드시 채워야 한다.

```json
{
  "sentence_idx": 0,
  "core_meaning": "문장의 핵심 의미",
  "primary_keywords": ["핵심 키워드 1", "핵심 키워드 2"],
  "secondary_keywords": ["보조 키워드"],
  "visual_intent": "literal | metaphor | diagram | editorial_scene",
  "visual_mode": "editorial_scene | symbolic_concept | simple_explainer | data_diagram",
  "hero_subject": "이미지의 중심 객체",
  "must_show": ["반드시 보여야 하는 객체"],
  "avoid": ["절대 나오면 안 되는 객체"],
  "composition_template": "구도 템플릿",
  "rationale": "왜 이 이미지가 문장과 맞는지"
}
```

최종 positive prompt는 다음 슬롯 구조를 따른다.

```text
Subject + Action + Environment + Symbolic Object + Style + Camera/Composition
```

금지 사항:

- `concrete visual subject tied to the sentence` 같은 generic 문구를 최종 prompt의 중심 주어로 쓰지 않는다.
- `success`, `future`, `strategy`, `growth`, `competition`, `sovereignty` 같은 추상어를 그대로 쓰지 않는다.
- 자동차, 나침반, 체크리스트, 트로피, 그래프, 대시보드 같은 generic drift 객체를 무심코 쓰지 않는다.
- 이미지 안에 읽을 수 있는 문자를 넣으려 하지 않는다. 텍스트 정보는 자막/TTS가 담당한다.

## 4. 스타일 선택 기준

NewAuto Studio의 Media 스타일은 문장/도메인에 따라 다르게 골라야 한다.

### 4.1 `editorial_symbolic`

기본 권장 스타일이다.

사용 대상:

- 뉴스 해설
- 산업/정책/기술 설명
- 추상 개념이 있지만 실제 공간/사물로 표현 가능한 문장

프롬프트 원칙:

```text
one high-quality editorial scene,
one clear subject,
one or two symbolic objects only,
real place or product-like setting,
cinematic but clean composition,
no text, no dashboard, no tiny icons
```

### 4.2 `simple_explainer` 또는 `simple_diagram`

정보 구조를 단순히 보여줘야 할 때만 사용한다.

사용 대상:

- LFP vs NCM 비교
- 가격 장벽
- 안전성/화재 위험
- 에너지 밀도
- 공급망 압박

주의:

- 슬라이드처럼 보이면 실패다.
- 작은 아이콘이 많이 흩어지면 실패다.
- 1개 중심 객체 + 1~2개 보조 상징만 사용한다.

### 4.3 `data_diagram`

수치/비교 구조가 문장의 핵심일 때만 사용한다.

사용 대상:

- 가격 차이
- 에너지 밀도 차이
- 주행거리 tradeoff
- 공급량/물량 공세

주의:

- 실제 숫자나 글자는 이미지에 넣지 않는다.
- 자막이 정보를 설명하고 이미지는 구조만 보여준다.

### 4.4 Stickfigures LoRA

기본값으로 쓰면 안 된다.

사용 대상:

- 사람 중심 교육/만화 설명
- 스틱맨이 명확한 행동을 해야 하는 장면
- "스틱맨이 배터리 셀을 가리키는 설명 장면"처럼 LoRA 스타일과 문장 의도가 일치하는 경우

사용 금지 대상:

- EV/배터리 산업 해설 기본 장면
- 기술 제품 단면도
- 공급망/공장/기업 전략 장면
- 실사형 editorial scene

현재 Stickfigures LoRA:

- 파일: `C:\Users\petbl\autotube\ComfyUI\models\loras\Stickfigures-000005.safetensors`
- trigger hints:
  - `Flipchartvisu`
  - `Stick figure`

핵심 결론:

LoRA는 스타일만 바꾼다. 문장에 맞는 subject/action/prop을 골라주지 않는다. 따라서 이미지가 이상한 원인을 LoRA strength만으로 해결하려 하면 안 된다.

## 5. EV/배터리 도메인 기준

EV/배터리 대본은 `ev_battery` 도메인으로 처리한다.

기본 설정:

- 기본 workflow: `txt2img_sdxl_basic`
- 기본 LoRA: 없음
- 선택 LoRA: 기술 일러스트/인포그래픽 LoRA가 있을 때만 `txt2img_sdxl_lora`
- LoRA strength: `0.25~0.4`
- Stickfigures LoRA: 기본 비활성화

문장별 권장 시각 객체:

1. 가성비/LFP 배터리
   - electric vehicle silhouette
   - price tag
   - LFP battery cell
   - balanced comparison structure

2. 한국 배터리 기업의 NCM 집중
   - premium NCM battery pack
   - Korean battery factory
   - high-performance cell stack

3. 비싼 가격과 대중화 장벽
   - battery pack behind a price barrier
   - consumer separated from EV by cost wall

4. 중국 주도 LFP 장점
   - LFP battery cell
   - safety shield
   - lower cost marker
   - shorter range icon as secondary object

5. Tesla/Hyundai/global automakers 선택
   - global automaker silhouettes
   - supply chain table
   - LFP pack as central object

6. 한국 배터리 3사 반격
   - three Korean battery factory silhouettes
   - strategy table
   - battery pack in foreground

7. 한국형 LFP/에너지 밀도
   - Korean LFP battery cross-section
   - energy density gauge
   - improved cell structure

8. 전고체 배터리
   - solid-state battery layer structure
   - clean lab bench
   - next-generation cell prototype

9. 기술 주권
   - battery technology shield
   - supply chain map without readable text
   - control/ownership symbol

10. 중국 물량 공세와 K-배터리 경쟁
   - mass-produced battery packs
   - K-battery pack holding position
   - supply pressure wave as abstract background

EV/배터리 negative prompt에는 아래를 강하게 포함한다.

```text
unrelated human, stick figure, desert, aircraft, fantasy creature,
random road scene, medieval, warrior, monster, animal, crowded office,
dashboard-only scene, readable text, letters, logo, watermark,
car showroom glamour shot, generic highway, random compass, checklist
```

## 6. ComfyUI 생성 시간 제한

Media 단계가 오래 걸리는 주원인은 다음이다.

- 고해상도 SDXL
- 장면당 후보 2~3장 생성
- 낮은 점수 후보의 plan retry
- fallback downgrade
- repair retry
- ComfyUI history 대기 중 worker heartbeat 오판

운영 기준:

- 기본 빠른 모드:
  - 장면당 후보 `1`
  - retry `0~1`
  - SDXL basic `1024x576` 또는 `1024x768`
  - steps `12~16`

- 품질 모드:
  - 장면당 후보 `2`
  - retry 최대 `1`
  - 한 문장당 총 생성 상한 `2`

- exhaustive 모드:
  - 수동 검수용으로만 사용
  - 자동 렌더까지 이어지면 안 된다.

NewAuto Studio 기본값은 "완주 가능한 품질"이어야 한다. 좋은 이미지 하나를 오래 기다리다가 전체 영상이 멈추는 것보다, 빠르게 후보를 만들고 relevance gate에서 확실히 막는 편이 낫다.

필수 구현 정책:

- 한 프로젝트의 이미지 생성 전체 시간 상한을 둔다.
- 한 문장당 생성 시도 상한을 둔다.
- ComfyUI history 대기 중에도 heartbeat가 끊기지 않게 한다.
- timeout/interrupt 후에는 ComfyUI queue 상태를 확인하고 사용자에게 "재시도/현재 후보로 렌더/중단" 중 하나를 명확히 제시한다.

현재 반영:

- `app/main.py`
  - `BODY_IMAGE_STALE_AFTER_SEC = 1200`
  - `BODY_IMAGE_MAX_RUNTIME_SEC = 7200`

추가 필요:

- `image_worker.py`에서 긴 ComfyUI poll 중 heartbeat DB update가 실제로 유지되는지 로그로 증명한다.
- image job 진행률이 `1/10 attempt 3/4`처럼 장면/시도/남은 시간을 UI에 표시한다.
- 기본 `quality_mode=fast`에서는 EV/배터리 도메인 retry를 과하게 돌리지 않는다.

## 7. 후보 선택과 차단 기준

이미지 후보는 점수로만 통과시키면 안 된다. 도메인별 핵심 객체 coverage를 함께 본다.

공통 차단:

- sentence_hash 없음
- manifest_sentence_hash 불일치
- visual_brief 없음
- must_show 누락
- selected image가 다른 프로젝트/다른 문장 산출물
- readable text가 중심이 됨
- candidate score가 너무 낮음

EV/배터리 차단:

- prompt에 battery/LFP/NCM/solid-state/price/safety/supply chain 중 해당 문장 핵심 객체가 없음
- Stickfigures LoRA가 자동으로 선택됨
- score `< 0.72`인데 render plan에 자동 진입함
- fallback source가 50% 이상인데 사용자 확인 없이 ComfyUI 생성에 들어감

권장 기준:

- 일반 도메인:
  - `< 0.6`: retry
  - `0.6~0.72`: borderline
  - `>= 0.72`: pass

- EV/배터리/기술 설명 도메인:
  - `< 0.72`: 자동 렌더 진입 금지
  - 단, 사용자가 "현재 후보로 렌더"를 명시하면 override 가능

## 8. Render 연결 규칙

렌더는 Media 품질 문제가 숨어 들어가는 마지막 통로다.

필수 규칙:

- `body_image_mappings`와 `media_order`가 같은 선택 이미지를 가리켜야 한다.
- mapping 변경 직후 `scene_plan`과 `render_plan`을 자동 재생성해야 한다.
- 렌더 직전 `visual_relevance`가 실패하면 FFmpeg를 시작하지 않는다.
- 복구 렌더는 일반 성공으로 표시하지 않고 `recovery_existing_images`처럼 명확한 phase를 남긴다.

절대 금지:

- 이전 프로젝트 이미지를 자동 재사용
- sentence_hash 없는 mapping으로 render
- fallback prompt가 절반 이상인데 사용자 확인 없이 render
- 이미지 1~2장만 생성됐는데 10개 문장에 반복 매핑하고 정상 Media 성공으로 표시

## 9. UI/로그 표시 기준

기본 Media UI와 operator/debug UI를 분리한다.

기본 사용자 UI는 `media-simplification-plan`을 따른다. 기본 화면에는 문장 preview, 이미지 프롬프트, 선택 이미지, 생성 상태, 실패/차단 이유, 다시 생성/이미지 교체/프롬프트 복사 같은 직접 행동만 보여준다.

아래 정보는 기본 UI가 아니라 operator/debug/advanced view 또는 내부 로그에 표시한다.

문장별 표시:

- sentence index
- sentence preview
- visual domain
- style mode
- workflow template
- LoRA name/strength
- candidate score
- retry reason
- selected image
- PASS / BORDERLINE / BLOCKED / NEEDS_REVIEW

프로젝트 전체 표시:

- total sentences
- generated images
- pending images
- fallback visual plan count
- blocked candidate count
- estimated remaining time
- current ComfyUI prompt id
- current queue state

## 10. 구현 우선순위

### P0. 기준 문서 정착

- 이 문서를 Media 단계의 단일 기준 문서로 삼는다.
- `issue.md`에서 이 문서를 연결한다.
- 기존 `comfyui.txt`, `comfysdxl.txt`, archive 문서는 참고 자료로만 둔다.

### P1. 기본값 정리

- EV/배터리 도메인에서 Stickfigures LoRA 자동 선택 금지.
- 기본 `quality_mode=fast`에서는 장면당 후보 1장, retry 최대 1회.
- SDXL 기본 해상도/steps를 빠른 완주 기준으로 낮춘다.
- timeout 시 무한 대기하지 않고 사용자 선택 상태로 전환한다.

### P2. Visual planner 안정화

관련 코드/테스트:

- `app/services/visual_planner.py`
- `app/services/domain_detection.py`
- `storage/visual_vocab/*.json`
- `tests/test_visual_planner.py`
- `tests/test_domain_detection.py`

- 10문장을 한 번에 긴 JSON으로 받지 말고 문장별 또는 3문장 batch로 나눈다.
- LLM 결과가 누락되면 전체 fallback으로 조용히 진행하지 않는다.
- fallback 비율이 높으면 Media 생성을 중단하고 planner 재시도 또는 스타일 변경을 요구한다.

### P3. Prompt coverage gate

관련 코드/테스트:

- `app/services/image_prompting.py`
- `app/services/prompt_quality.py`
- `app/services/visual_relevance.py`
- `app/services/prompt_repair.py`
- `tests/test_image_prompting.py`
- `tests/test_prompt_quality.py`
- `tests/test_visual_relevance.py`
- `tests/test_prompt_repair.py`

- positive prompt에 `must_show`가 모두 들어갔는지 검사한다.
- EV/배터리 핵심 객체 coverage를 별도 검사한다.
- generic filler 문구가 중심 주어로 들어가면 실패 처리한다.

### P4. Candidate/retry 정책 정리

- 도메인별 점수 기준을 분리한다.
- EV/배터리는 0.72 미만 자동 렌더 금지.
- retry는 문장당 상한을 둔다.
- heavy LoRA path가 retry를 무조건 skip하지 않게 하되, 전체 시간 상한을 넘지 않게 한다.

### P5. Scene/render sync 자동화

- 후보 선택 변경 시 mapping/media_order/scene_plan/render_plan을 한 번에 갱신한다.
- preflight와 render worker가 같은 visual relevance 정책을 사용하게 한다.

### P6. Operator review flow

- 차단된 문장은 "다시 생성", "스타일 변경", "현재 후보로 강제 렌더", "업로드 이미지 사용" 중 하나를 선택하게 한다.
- 강제 렌더는 report에 `operator_override=true`를 남긴다.

## 11. EV/배터리 영상에 바로 적용할 결론

현재 EV/LFP 대본에는 아래 설정이 맞다.

```json
{
  "visual_source_mode": "comfyui_auto",
  "domain": "ev_battery",
  "style_preset": "ev_battery_explainer",
  "quality_mode": "fast",
  "workflow_template": "txt2img_sdxl_basic",
  "lora_name": "",
  "candidate_per_sentence": 1,
  "max_retry_per_sentence": 1,
  "render_gate_score": 0.72,
  "fallback_ratio_block_threshold": 0.3
}
```

Stickfigures LoRA는 이 대본의 기본 선택이 아니다.

가장 중요한 개선은 더 많은 이미지를 무작정 생성하는 것이 아니라, 생성 전에 문장별 visual plan이 배터리/EV 핵심 객체를 제대로 포함하는지 막는 것이다.

## 12. 구현 상태와 검증 방법

현재 구현됨:

- LM Studio provider와 기본 모델은 `app/config.py` 기준 `lmstudio` + `google/gemma-4-e4b`로 고정되어 있다.
- `app/services/domain_detection.py`와 `storage/visual_vocab/ev_battery.json`에 EV/배터리 도메인 기반이 있다.
- `sentence_hash`, prompt manifest, candidate score, visual relevance 기반 검사는 `app/services/visual_relevance.py`와 관련 테스트에 있다.
- ComfyUI 긴 대기 중 worker stale timeout은 2026-05-16 기준 완화되어 있다.
- 2026-05-16 추가 구현: `app/services/visual_planner.py`는 4문장 이상 대본을 3문장 batch로 나누어 LM Studio에 요청한다. 긴 전체 JSON 응답 하나가 깨져 모든 이미지 프롬프트가 fallback으로 몰리는 위험을 줄인다.
- 2026-05-16 추가 구현: EV/배터리 도메인은 `app/services/prompt_quality.py`에서 battery/EV/LFP/NCM/solid-state 등 핵심 시각 객체가 빠진 prompt와 Stickfigures 계열 스타일을 issue code로 차단한다.
- 2026-05-16 검증: `tests/test_visual_planner.py`, `tests/test_prompt_quality.py`, `tests/test_image_prompting.py`, `tests/test_comfyui_pipeline.py` 대상 49개 테스트 통과.
- 2026-05-16 추가 구현: `app/routers/image_gen.py`는 ComfyUI batch queue 등록 전에 prompt quality report를 검사한다. EV/배터리 등 strict 도메인에서 fallback 비율 초과, EV 핵심 객체 누락, Stickfigures 스타일 차단 issue가 있으면 `body_image_state=blocked`로 중단한다.
- 2026-05-16 추가 구현: `app/workers/image_worker.py`는 우회 진입한 job item의 blocking prompt issue를 ComfyUI submit 직전에 다시 검사하고, ComfyUI history poll 중 prompt id/attempt/남은 timeout을 주기적으로 `body_image_last_log`와 heartbeat에 남긴다.
- 2026-05-16 검증: `tests/test_comfyui_routes.py`, `tests/test_image_worker.py`, `tests/test_prompt_quality.py`, `tests/test_image_prompting.py` 대상 79개 테스트 통과.
- 2026-05-16 smoke: EV/LFP 대본 10문장으로 prompt manifest를 생성했다. 결과는 10개 모두 `ev_battery`, `txt2img_sdxl_basic`, LoRA 없음, Stickfigures trigger 0개, prompt coverage issue 0개다.
- 2026-05-16 smoke 수정: EV prompt가 Stickfigures template으로 흐르던 원인을 수정했다. EV 도메인은 `prompt_compiler.py`에서 `Flipchartvisu`/`Stick figure`를 넣지 않고, `image_prompting.py`에서 `txt2img_sdxl_basic`/LoRA 없음으로 고정한다.
- 2026-05-16 smoke 수정: EV prompt repair가 4번째 이후 `must_show`를 놓칠 수 있어 최대 5개까지 prompt에 보강하도록 수정했다.
- 2026-05-16 smoke 수정: 첫 ComfyUI smoke 이미지가 3D 배터리 단품으로 흐르는 경향이 있어 EV template을 flat 2d explainer diagram, EV silhouette, comparison icon 중심으로 강화하고 3D cylinder battery only를 negative에 추가했다.
- 2026-05-16 검증: `tests/test_image_prompting.py`, `tests/test_prompt_quality.py`, `tests/test_comfyui_routes.py`, `tests/test_image_worker.py` 대상 81개 테스트 통과.
- 2026-05-16 full smoke: EV/LFP 대본 10장 ComfyUI 생성 완료. `body_image_mappings=10`, `scene_plan/render_plan` 생성, contact sheet와 visual mismatch report 생성 확인.
- 2026-05-16 full smoke 수정: `image_worker.py`의 progress가 100을 초과하던 문제를 0~100 clamp로 수정했다.
- 2026-05-16 full smoke 수정: 전체 재생성 시 이전 후보가 다시 선택되지 않도록 `image_gen.py`에서 선택 범위의 기존 mappings/candidate_groups/candidate_reviews를 queue 등록 시 초기화한다.
- 2026-05-16 full smoke 수정: EV strict 도메인에서 `IMAGE_SEMANTIC_MATCH_TOO_LOW`가 있으면 후보 점수와 무관하게 retry 권고로 처리한다.
- 2026-05-16 검증: `tests/test_comfyui_routes.py`, `tests/test_image_worker.py`, `tests/test_comfyui_pipeline.py` 대상 53개 테스트 통과.

아직 계획/보강 대상:

- 강화된 retry 정책을 반영한 상태로 EV/LFP 10장 재생성을 다시 실행하고 semantic mismatch가 실제로 줄었는지 확인한다.
- EV 이미지가 여전히 자동차 전시장/서버룸/단품 배터리로 흐르는 장면은 domain vocabulary와 negative prompt를 더 세분화한다.
- `image_worker.py`가 ComfyUI history 대기 중에도 heartbeat를 유지한다는 로그/테스트 증명.
- 기본 사용자 UI와 operator/debug UI의 표시 항목 분리.
- LM Studio와 ComfyUI 사이 VRAM handoff. 현재 코드는 LM Studio 모델 로드 여부를 감지하지만, LM Studio 모델 unload를 항상 보장하지는 않는다. 기본 정책은 `lms.exe` CLI 또는 사용자 안내를 기준으로 한다.
- EV/LFP 대본용 automated smoke. 목표는 같은 대본으로 visual plan 10개, prompt 10개, 이미지 10개 매핑, render preflight 통과를 확인하는 것이다.

검증 기준:

- 단위 테스트: `python -m pytest tests/test_visual_planner.py tests/test_image_prompting.py tests/test_prompt_quality.py tests/test_visual_relevance.py tests/test_comfyui_pipeline.py`
- 수동 smoke: EV/LFP 대본을 넣고 `scene_visual_plan.json`, prompt manifest, image mapping, render report를 확인한다.
- 실패 케이스 smoke: LM Studio 꺼짐, ComfyUI queue timeout, fallback 비율 초과, Stickfigures LoRA 자동 선택 시 차단 메시지가 나오는지 확인한다.

## 13. 완료 기준

이 문서 기준의 Media 개선이 완료되었다고 볼 수 있는 조건:

- 같은 EV/LFP 대본 10문장에서 문장별 visual plan이 10개 모두 생성된다.
- 각 문장 prompt에 EV/배터리 핵심 객체가 최소 1개 이상 들어간다.
- Stickfigures LoRA가 자동으로 선택되지 않는다.
- 이미지 생성이 10문장 기준 합리적인 시간 안에 끝난다.
- retry/timeout 시 사용자가 현재 상태를 이해할 수 있다.
- 렌더 직전 visual relevance가 실패 이미지를 차단한다.
- 최종 render report에 어떤 이미지가 어떤 문장에 왜 선택됐는지 남는다.
