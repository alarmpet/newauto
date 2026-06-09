# newauto Studio Media Simplification Plan

작성일: 2026-05-15

## 1. 결정

`2. Media` 단계는 복잡한 자동화/검증/Flow/다중 fallback 중심에서 벗어나, 사용자가 바로 이해하고 통제할 수 있는 간단한 구조로 재설계한다.

새 Media 단계의 핵심은 두 가지다.

1. 사용자가 사용할 이미지를 직접 업로드한다.
2. 대본을 문장 단위로 나누고, 로컬 LLM(LM Studio + Gemma4 e8b API)로 모든 문장의 이미지 프롬프트를 일괄 생성한다. 프롬프트 생성이 끝나면 LM Studio 모델을 unload/종료해 VRAM을 비우고, 이후 별도의 `이미지 생성` 버튼으로 ComfyUI + LoRA 생성을 실행한다. 사용자는 이미지 생성 대신 프롬프트만 복사할 수도 있다.

기존의 Flow 자동화, visual relevance 자동 검증, 복잡한 visual planner, 자동 fallback, 다중 후보 평가, 자동 repair, ControlNet/IPAdapter 고급 경로는 기본 UI에서 모두 비활성화한다. 코드는 즉시 삭제하지 않고 Advanced/Legacy 영역으로 숨기거나 feature flag 뒤로 보낸다.

2026-05-15 외부 리뷰 검토 반영:

- VRAM handoff는 타당하다. LM Studio에서 8B급 모델을 올린 직후 ComfyUI/SDXL + LoRA를 실행하면 8-12GB VRAM 환경에서 OOM 위험이 크다. ComfyUI 생성 전에는 LM Studio 모델 unload 안내 또는 자동 unload 시도를 Media 흐름에 포함한다.
- SQLite WAL 제안은 이미 반영되어 있다. `app/db.py`는 `PRAGMA journal_mode=WAL`과 `PRAGMA busy_timeout=5000`을 설정한다. 따라서 신규 계획 항목이 아니라 회귀 테스트/확인 항목으로 둔다.
- 사용자-facing 용어에서 `Flow`는 제거한다. 기본 UI에서는 `AI 이미지 생성`, `문장 이미지`, `ComfyUI + LoRA`처럼 직접적인 용어만 사용한다.

## 2. 목표 UX

Media 화면은 다음 요소만 남긴다.

- 미디어 업로드: 본문 영상에 사용할 이미지 업로드
- 썸네일 업로드: YouTube/Shorts 썸네일용 이미지 업로드
- 출력 비율 설정: `9:16`, `16:9`, `1:1`
- 줌 + 패닝 효과 강도: `없음`, `약함`, `보통`, `강함`
- 이미지 소스 토글:
  - `업로드 이미지 사용`
  - `대본 기반 프롬프트 생성`
- 문장별 프롬프트 테이블:
  - 문장 번호
  - 원문 문장
  - 핵심 키워드
  - 이미지 프롬프트
  - `복사`
  - 생성 결과 이미지 선택/교체
- 작업 버튼:
  - `전체 이미지 프롬프트 생성`
  - `LM Studio 종료`
  - `전체 프롬프트 복사`
  - `이미지 생성`
  - `선택 문장 이미지 생성`

사용자가 처음 보는 화면에서는 “자동 에이전트”, “Flow”, “semantic score”, “mismatch report”, “repair”, “candidate scoring” 같은 개념을 보이지 않게 한다.

사용자-facing 용어 정책:

- `Flow` -> 사용하지 않음. 내부/Legacy 문서에서만 허용.
- `visual relevance` -> `이미지 검토` 또는 숨김.
- `mismatch report` -> 기본 UI에서 숨김.
- `prompt repair` -> 기본 UI에서 숨김.
- `candidate scoring` -> 기본 UI에서 숨김.
- `ComfyUI`는 고유 실행 도구명으로 유지하되, 버튼은 `ComfyUI + LoRA 생성`처럼 행동 중심으로 쓴다.

## 3. 비활성화 대상

기본 Media UI에서 비활성화할 기능:

- Flow browser automation
- Flow assisted/auto generation
- visual relevance report
- visual mismatch report
- image quality 자동 fail/pass
- prompt repair 자동 루프
- visual vocabulary 고급 설정
- visual metaphor/subject mode 고급 설정
- ControlNet/IPAdapter/스타일 레퍼런스 자동 분기
- 다중 이미지 후보 자동 scoring
- autopilot이 media를 자동 결정하는 경로

유지하되 숨길 기능:

- 기존 ComfyUI client
- 기존 image generation profile
- 기존 render plan의 media path 연결
- 기존 업로드 API
- 기존 render의 zoom/pan 필터

원칙: “복잡한 엔진은 내부에 보존, 사용자 표면은 단순화.”

## 4. 새 Media 모드

### 4.1 업로드 이미지 사용

사용 흐름:

1. 사용자가 이미지 여러 장을 업로드한다.
2. 앱이 대본 문장 수와 이미지 수를 보여준다.
3. 기본 매핑은 순서대로 배치한다.
4. 이미지가 문장 수보다 적으면 반복 사용 또는 마지막 이미지 유지 옵션을 제공한다.
5. 이미지가 문장 수보다 많으면 남는 이미지는 미사용 목록에 둔다.
6. 사용자는 문장별 이미지를 드래그/선택으로 교체할 수 있다.

필수 옵션:

- 출력 비율: `9:16`, `16:9`, `1:1`
- 이미지 맞춤: `cover`, `contain`
- 줌+패닝 강도: `none`, `low`, `medium`, `high`

### 4.2 대본 기반 프롬프트 생성

사용 흐름:

1. 대본을 문장 단위로 나눈다.
2. 각 문장을 LM Studio API로 보낸다.
3. Gemma4 e8b가 문맥과 핵심 키워드를 뽑는다.
4. 앱이 문장별 이미지 프롬프트를 생성한다.
5. 모든 문장의 프롬프트 생성이 끝나면 앱이 LM Studio 모델 unload 또는 LM Studio 종료를 수행한다.
6. 사용자는 프롬프트를 복사하거나, 별도의 `이미지 생성` 버튼으로 ComfyUI + LoRA 생성을 실행한다.
7. 생성된 이미지는 해당 문장 media로 자동 연결된다.

토글:

- `프롬프트만 만들기`
- `프롬프트 생성 후 이미지 생성 준비`

버튼:

- `전체 이미지 프롬프트 생성`
- `선택 문장 프롬프트 생성`
- `LM Studio 종료`
- `전체 복사`
- `선택 프롬프트 복사`
- `이미지 생성`
- `선택 문장 이미지 생성`

## 5. LM Studio 프롬프트 생성 정책

대상 API:

- Base URL: `http://127.0.0.1:1234/v1`
- Model: `gemma4-e8b` 또는 사용자가 LM Studio에서 로드한 모델명
- 호출 방식: OpenAI-compatible chat completions

문장별 LLM 출력 JSON:

```json
{
  "sentence_idx": 0,
  "core_context": "one short Korean summary",
  "keywords": ["keyword1", "keyword2", "keyword3"],
  "image_prompt_ko": "Korean prompt",
  "image_prompt_en": "English prompt for SDXL/LoRA",
  "negative_prompt": "low quality, blurry, extra fingers, text, watermark",
  "style_hint": "documentary, cinematic, realistic, illustration, etc"
}
```

프롬프트 원칙:

- 문장 하나만 보지 않고 앞뒤 문맥을 함께 제공한다.
- 이미지에 꼭 보여야 할 대상 1-2개만 고른다.
- 추상적인 문장은 상징적 장면으로 변환한다.
- 텍스트, 로고, 워터마크 생성은 피한다.
- 기본 프롬프트는 ComfyUI/SDXL/LoRA에 바로 넣을 수 있게 영어로 만든다.

## 6. ComfyUI + LoRA 생성 정책

Media 화면에서는 ComfyUI 설정을 최소화한다.

보이는 옵션:

- LoRA 선택
- 이미지 비율
- 생성 수: `1`, `2`, `4`
- seed: `random` 또는 수동 입력
- `생성` 버튼

숨기는 옵션:

- workflow JSON 직접 선택
- ControlNet
- IPAdapter
- advanced sampler
- scheduler
- CFG/steps 고급 설정
- 자동 repair
- relevance scoring

기본값:

- workflow: SDXL + selected LoRA 기본 워크플로우
- steps: 20-30
- CFG: 5-7
- sampler/scheduler: 기존 안정값 사용
- output: 해당 문장 media slot에 저장

### 6.1 VRAM handoff 정책

LM Studio와 ComfyUI를 같은 GPU에서 연속 사용하면 VRAM 충돌이 날 수 있다. 특히 Gemma4 e8b 같은 8B급 LLM을 LM Studio에 올린 상태에서 SDXL + LoRA를 ComfyUI로 실행하면 OOM 가능성이 높다.

ComfyUI 생성 버튼을 누를 때의 정책:

1. 이미지 프롬프트 생성 단계가 끝났는지 확인한다.
2. LM Studio 모델 unload/종료가 완료되었는지 확인한다.
3. LM Studio가 아직 모델을 들고 있으면 `이미지 생성` 버튼을 잠그고 `LM Studio 종료` 버튼을 먼저 안내한다.
4. 가능한 경우 `lms.exe unload <model>` 방식의 로컬 CLI unload를 실행한다.
5. unload가 실패하거나 모델명을 알 수 없으면 “LM Studio에서 모델을 언로드/종료한 뒤 다시 시도” 안내를 보여준다.
6. 사용자가 강제로 계속 진행할 수 있는 옵션은 Advanced에만 둔다.

주의:

- LM Studio OpenAI-compatible API의 `/v1/models`는 모델 조회에는 쓸 수 있지만, 현재 코드 기준으로 unload API는 구현되어 있지 않다.
- 기존 `OllamaClient.unload()`는 `provider="lmstudio"`에서 no-op이다. 따라서 계획은 HTTP unload가 아니라 `lms.exe` CLI 또는 명시적 사용자 안내를 기준으로 한다.
- ComfyUI 생성 작업은 기존 `gpu_guard`/`worker_lock`와 연결해 동시에 여러 이미지 job이 GPU를 점유하지 않게 한다.

권장 기본 UX:

1. `전체 이미지 프롬프트 생성`
2. 모든 문장의 프롬프트 생성 완료
3. 앱이 자동으로 `lms.exe unload <model>` 시도
4. unload 성공 시 `이미지 생성` 버튼 활성화
5. unload 실패 시 `LM Studio 종료` 안내와 재확인 버튼 표시
6. `이미지 생성` 클릭
7. ComfyUI + LoRA queue 실행

## 7. 데이터 모델 단순화

기존 `ScenePlanScene`, `RenderPlanSegment`를 새로 크게 바꾸지 않는다. Media UI용 lightweight 상태를 추가한다.

권장 필드:

```json
{
  "media_mode": "upload" | "prompt" | "comfyui",
  "output_aspect_ratio": "9:16" | "16:9" | "1:1",
  "motion_strength": "none" | "low" | "medium" | "high",
  "thumbnail_path": "string | null",
  "sentence_media": [
    {
      "sentence_idx": 0,
      "text": "string",
      "media_path": "string | null",
      "keywords": ["string"],
      "prompt": "string",
      "negative_prompt": "string",
      "locked": false
    }
  ]
}
```

기존 필드 매핑:

- `sentence_media[].media_path` -> 기존 `media_order` 또는 `RenderPlanSegment.media_path`
- `sentence_media[].prompt` -> 기존 `ScenePlanScene.prompt`
- `motion_strength` -> render 단계에서 zoom/pan preset으로 변환
- `output_aspect_ratio` -> render format/aspect config로 변환

## 8. 구현 단계

### Phase 1: UI 간소화

- Media 탭에서 기존 고급 자동화 UI를 숨긴다.
- 업로드 이미지, 썸네일 업로드, 출력 비율, zoom/pan 강도만 1차 노출한다.
- 이미지 소스 토글을 추가한다.
- 기존 프로젝트에서도 업로드 이미지 경로는 그대로 유지한다.

완료 기준:

- Media 화면에서 사용자가 봐야 할 옵션이 10개 이하로 줄어든다.
- Flow/visual relevance/repair 관련 텍스트가 기본 화면에서 보이지 않는다.
- 사용자-facing label에는 `Flow`가 남지 않는다. 필요하면 Advanced/Legacy 표시 안에서만 쓴다.

### Phase 2: 문장별 프롬프트 생성

- 대본을 문장 단위로 분리하는 API를 재사용한다.
- LM Studio 상태 확인 버튼을 추가한다.
- Gemma4 e8b 호출로 모든 문장의 JSON 프롬프트를 일괄 생성한다.
- 결과를 테이블에 표시하고 복사 버튼을 제공한다.
- 일괄 생성이 끝나면 LM Studio 모델 unload/종료 절차를 실행한다.

완료 기준:

- LM Studio가 켜져 있으면 `전체 이미지 프롬프트 생성`이 모든 문장에 대해 동작한다.
- 모든 문장 프롬프트 생성 후 앱이 LM Studio unload를 시도하고 결과를 표시한다.
- LM Studio가 꺼져 있으면 명확한 안내만 표시하고 다른 Media 기능은 사용 가능하다.

### Phase 3: ComfyUI + LoRA 버튼 연결

- `이미지 생성` 버튼을 추가한다.
- `선택 문장 이미지 생성` 버튼을 추가한다.
- 생성 전 VRAM handoff 상태를 검사한다: LM Studio unload/종료가 끝나기 전에는 기본 `이미지 생성` 버튼을 비활성화한다.
- 전체 생성은 queue 방식으로 처리한다.
- 생성 완료 이미지는 해당 문장 media slot에 자동 연결한다.
- 실패 시 프롬프트는 유지하고 사용자가 복사/재시도할 수 있게 한다.

완료 기준:

- 전체 문장 프롬프트 생성 -> LM Studio unload/종료 -> 이미지 생성 -> media slot 연결이 한 화면에서 끝난다.
- LM Studio 모델이 로드된 상태에서는 기본 `이미지 생성` 버튼이 활성화되지 않는다.

### Phase 4: 렌더 연결

- 업로드 이미지 또는 생성 이미지가 `media_order`/render plan에 안정적으로 들어가게 한다.
- `motion_strength`를 render zoom/pan preset으로 변환한다.
- 썸네일 업로드 파일은 최종 output metadata에 포함한다.

완료 기준:

- 업로드 이미지만으로 최종 mp4 렌더가 가능하다.
- 문장별 생성 이미지로 최종 mp4 렌더가 가능하다.
- 이미지가 없어도 어떤 문장이 비어 있는지 명확히 보인다.

## 9. Feature Flag

새 기본값:

```env
NEWAUTO_MEDIA_SIMPLE=1
NEWAUTO_ENABLE_FLOW_UI=0
NEWAUTO_ENABLE_VISUAL_QA_UI=0
NEWAUTO_ENABLE_PROMPT_REPAIR_UI=0
NEWAUTO_ENABLE_ADVANCED_COMFYUI_UI=0
```

개발자/고급 사용자용으로만 legacy 기능을 다시 열 수 있게 한다.

```env
NEWAUTO_MEDIA_SIMPLE=0
NEWAUTO_ENABLE_FLOW_UI=1
NEWAUTO_ENABLE_VISUAL_QA_UI=1
```

## 10. 첫 작업 목록

1. Media 화면 현재 노출 기능 목록 작성.
2. 숨길 DOM 영역/상태/버튼을 `simple media mode` 기준으로 분류.
3. `NEWAUTO_MEDIA_SIMPLE` config 추가.
4. Media UI를 업로드/썸네일/비율/모션강도/소스토글 중심으로 재배치.
5. 문장 분할 결과를 Media 테이블에 표시.
6. LM Studio `/v1/chat/completions` client 추가 또는 기존 client 재사용.
7. Gemma4 e8b 프롬프트 JSON schema와 parser 추가.
8. `전체 이미지 프롬프트 생성`, `선택 문장 프롬프트 생성`, `복사` 버튼 구현.
9. 사용자-facing `Flow` 용어를 기본 Media UI에서 제거하고 `AI 이미지 생성`/`문장 이미지`로 치환.
10. 프롬프트 일괄 생성 완료 후 LM Studio unload/종료 절차 구현.
11. `LM Studio 종료` 버튼 구현.
12. unload 성공 후에만 `이미지 생성` 버튼이 활성화되도록 상태 모델 추가.
13. ComfyUI + LoRA 전체 이미지 생성 버튼 구현.
14. ComfyUI + LoRA 선택 문장 이미지 생성 버튼 구현.
15. 생성 결과를 sentence media slot에 연결.
16. 업로드 이미지와 생성 이미지가 같은 sentence media 모델을 쓰도록 통합.
17. render plan fallback에서 sentence media 기반 segment 시간을 안정적으로 계산.
18. 기존 Flow/visual relevance/repair UI는 Advanced/Legacy로 이동.
19. SQLite WAL/busy_timeout이 유지되는지 회귀 테스트 또는 config smoke에 포함.
20. 업로드-only, prompt-only, comfyui-generate 세 가지 smoke 테스트 추가.

## 11. 성공 기준

사용자는 Media 단계에서 다음만 결정하면 된다.

- 이미지를 직접 쓸 것인가?
- 대본으로 프롬프트를 만들 것인가?
- 만든 프롬프트를 복사할 것인가?
- LM Studio를 종료한 뒤 ComfyUI + LoRA로 이미지를 생성할 것인가?
- 출력 비율은 무엇인가?
- 줌/패닝 움직임은 어느 정도인가?
- 썸네일은 어떤 이미지인가?

이 기준을 벗어나는 자동화는 기본 화면에서 숨긴다.

## 12. 보류 항목

아래 기능은 삭제하지 않고 보류한다.

- Flow 자동 이미지 생성
- visual relevance 점수화
- visual mismatch report
- prompt repair loop
- ControlNet/IPAdapter 고급 워크플로우
- 자동 후보 scoring
- autopilot media 결정

보류 이유: 기능 자체는 유용하지만 지금 제품의 첫 사용 경험을 복잡하게 만든다. MVP에서는 “내가 올린 이미지” 또는 “내 대본에서 만든 프롬프트/이미지”만 명확히 동작하게 하는 것이 우선이다.

## 13. 검증된 리뷰 반영/보류

`C:\Users\petbl\.lmstudio\antigravity-review-media-master-plans.md` 검토 결과:

반영:

- Media UI 간소화 방향은 타당하다.
- LM Studio는 프롬프트 생성에 집중시키고, 브라우저 제어나 자동 생성 판단은 줄이는 방향이 타당하다.
- LM Studio + ComfyUI 연속 사용 시 VRAM 충돌 위험은 타당하다. ComfyUI 생성 전 unload 안내/실행 동선을 추가한다.
- 사용자-facing `Flow` 용어 제거는 타당하다. 기본 UI에서는 `AI 이미지 생성`, `문장 이미지`, `ComfyUI + LoRA 생성`을 쓴다.

이미 반영되어 신규 작업으로 넣지 않음:

- SQLite WAL: `app/db.py`에 `PRAGMA journal_mode=WAL`과 `PRAGMA busy_timeout=5000`이 이미 있다.
- Tauri + FastAPI sidecar 전략: `docs/windows-app-architecture.md`와 현재 Tauri scaffold에 이미 반영되어 있다.

보류/수정 반영:

- LM Studio unload를 `/v1/models/unload` API로 호출한다는 전제는 현재 코드 기준으로 검증되지 않았다. 대신 `lms.exe unload <model>` CLI 또는 사용자 안내를 기준으로 계획한다.
> Deprecated for Media prompt guidance: use `docs/media-prompt-operating-guide.md` as the single active Media prompt reference. Keep this file only as legacy UI/simplification background until it is moved to `docs/archive/media_prompt_legacy/`.
