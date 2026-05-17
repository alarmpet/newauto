# NewAuto Studio 이미지 맥락 품질 개선 계획

Updated: 2026-05-16 KST

## 2026-05-16 구현 반영

완료:

- `app/services/domain_detection.py`
  - `is_ev_battery_domain()` 추가.
  - `전기차`, `배터리`, `LFP`, `NCM`, `전고체`, `에너지 밀도`, `기술 주권` 등 EV/배터리 키워드 감지.
- `storage/visual_vocab/ev_battery.json`
  - LFP/NCM 비교, 가격 장벽, 안전/주행거리 tradeoff, 글로벌 완성차 선택, K-배터리 반격, 한국형 LFP, 전고체, 기술 주권, 중국 물량 공세 구도 추가.
- `app/services/visual_planner.py`
  - `_domain_for_project()`에서 `ev_battery` 도메인 선택.
  - fallback에서도 `ev_battery` vocab 토큰과 composition template을 사용.
  - EV vocab 매칭은 단일 긴 키워드보다 맞은 키워드 개수를 우선하도록 보정.
- `app/services/visual_brief.py`
  - `ev_battery` brief mode, primary prop, action, scene, avoid list 추가.
- `app/services/image_prompting.py`
  - `EV_BATTERY_EXPLAINER_TEMPLATE` 추가.
  - EV/배터리 문장은 기존 `editorial_symbolic` preset보다 EV explainer template을 우선 적용.
  - deterministic fallback에서도 EV 배터리 핵심 객체를 보존.
- `app/services/comfyui_pipeline.py`
  - `ev_battery` 후보는 0.72 미만이면 `strict_domain_low_candidate_score` retry 권고로 판정.
- `app/workers/image_worker.py`
  - `ev_battery`는 LoRA가 있어도 heavy path라는 이유만으로 repair retry를 건너뛰지 않게 조정.
- 테스트 추가/보강:
  - `tests/test_domain_detection.py`
  - `tests/test_visual_planner.py`
  - `tests/test_image_prompting.py`
  - `tests/test_comfyui_pipeline.py`

검증:

- `.\omnivoice_env\Scripts\python.exe -m pytest tests/test_domain_detection.py tests/test_visual_planner.py tests/test_image_prompting.py tests/test_comfyui_pipeline.py tests/test_lmstudio_runtime.py tests/test_comfyui_routes.py tests/test_feature_workflow.py -q`
- 결과: 112 passed, 2 warnings

샘플 확인:

- 기존 EV/LFP 대본 10문장에 대해 LLM planner를 끈 deterministic fallback 기준으로 모든 문장이 `domain=ev_battery`, `template=ev_battery_explainer`를 사용했다.
- 2번 이후에도 `price barrier`, `LFP safety shield`, `global automaker silhouettes`, `Korean LFP battery cross-section`, `solid-state battery structure`, `technology sovereignty shield`, `mass-produced battery packs`처럼 문장별 핵심 객체가 보존됐다.

## 대상 출력물

- Project ID: `324b2eff3737`
- Output: `storage/projects/324b2eff3737/output.mp4`
- Review contact sheets:
  - `storage/projects/324b2eff3737/review_frames/image_contact.jpg`
  - `storage/projects/324b2eff3737/review_frames/output_contact.jpg`
- 결론: TTS, 자막 싱크, 음성 일관성은 양호하다. 문제는 이미지가 문장별 맥락, 핵심 키워드, 배터리/전기차 주제와 충분히 매칭되지 않는 것이다.

## 실제 확인 결과

완성본 프레임과 원본 이미지 10장을 확인했다.

- 0번: 전기차 이미지는 대본 맥락과 어느 정도 맞음.
- 1번: 배터리 셀 이미지는 NCM 배터리 문장과 어느 정도 맞음.
- 2번 이후: 가격 장벽, 중국 LFP 장점, 글로벌 기업 선택, 한국 배터리 3사 반격, 한국형 LFP, 전고체 배터리, 기술 주권, 중국 물량 공세와 거의 맞지 않는 장면이 다수 생성됨.
- 실제 이미지에는 사람, 사막, 비행기, 도로, 정체불명 스틱 그림 등이 섞여 나왔다.
- 최종 `final_scene_review.json`도 8개 장면에 retry 권고를 표시했다.
- 후보 점수: `[0.89, 0.86, 0.59, 0.58, 0.44, 0.54, 0.48, 0.62, 0.53, 0.58]`

## 외부 계획서 검토 결과

검토 대상: `C:\Users\petbl\.lmstudio\image-context-quality-plan.md`

타당해서 반영할 항목:

- EV/배터리 전용 도메인 감지와 visual vocab 추가.
- Stickfigures LoRA가 이번 EV/배터리 해설 영상과 충돌할 수 있다는 판단.
- 낮은 candidate score가 최종 렌더까지 들어간 문제.
- 이미지 재생성 후 `body_image_mappings`, `media_order`, `scene_plan` 동기화 자동화.
- EV 도메인 회귀 테스트 추가.

수정해서 반영할 항목:

- 외부 문서의 `app/services/prompt_compiler.py` 수정 제안은 현재 실제 이미지 경로와 정확히 맞지 않는다. 이번 workflow의 핵심 경로는 `app/services/visual_planner.py`, `app/services/image_prompting.py`, `app/services/comfyui_pipeline.py`, `app/workers/image_worker.py`다.
- `0.72 strict image gate`는 현재 코드상 `STRONG_SCORE_THRESHOLD = 0.72`로 존재하지만 차단 게이트가 아니라 `borderline_candidate` 판정 기준이다. 실제 retry 권고 기준은 `RETRY_SCORE_THRESHOLD = 0.6`이며, 0.6~0.72는 렌더 차단 없이 borderline으로 통과한다. 따라서 “기존 strict gate가 동작하지 않았다”가 아니라 “현재 0.72가 차단 조건으로 쓰이지 않는다”가 정확하다.
- `storage/visual_vocab/ev_battery.json` 생성 제안은 현재 `app/services/visual_vocab.py`가 실제로 `storage/visual_vocab/{domain}.json`을 읽으므로 타당하다.

## 핵심 원인

### 1. 이미지 프롬프트 추출이 2문장 이후 fallback으로 무너짐

`scene_visual_plan.json` 기준:

- 0번, 1번: `source=llm_repair`
- 2번~9번: 대부분 `source=fallback`

fallback으로 떨어진 문장들은 `primary_keywords`가 아래처럼 너무 일반적이다.

- `concrete visual subject tied to the sentence`
- `grounded editorial scene with one dominant real-world subject`
- `medium or wide shot`
- 일부는 `lfp`, `테슬라`, `배터리` 정도만 남음

이 문구들이 그대로 `positive_prompt`의 핵심 주어가 되면서 SDXL이 문장 의미를 이해할 단서가 거의 없어졌다.

### 2. LLM planner 출력 길이/검증이 부족함

관련 코드:

- `app/services/visual_planner.py`
- `build_scene_visual_plan()`
- `num_predict=1800`
- 모델: `SCRIPT_LLM_MODEL`, 현재 `google/gemma-4-e4b` 또는 LM Studio 경로

10문장 전체 visual plan을 한 번에 JSON으로 받는데, 1800 token 예산이 부족하거나 JSON repair 과정에서 앞의 2개만 살아남고 나머지는 fallback으로 보정된 것으로 보인다.

문제는 fallback 발생 자체보다, fallback이 발생했을 때 “문장별 핵심 명사와 도메인 키워드”를 보존하지 못했다는 점이다.

### 3. 프롬프트 생성에 전문 스킬/MCP가 쓰이지 않음

현재 문장별 이미지 프롬프트 추출은 별도 이미지 프롬프트 전문 MCP나 스킬이 아니라 로컬 코드 경로를 사용한다.

- `app/services/visual_planner.py`: LM Studio/OllamaClient 기반 visual plan 생성
- `app/services/image_prompting.py`: visual brief와 template 조합으로 SDXL prompt 생성
- `app/services/visual_brief.py`: fallback visual brief 생성

즉, “전기차 배터리 해설 영상용 장면 기획”에 특화된 도구가 아니라, 일반 editorial/symbolic fallback 규칙에 크게 의존했다.

### 4. LoRA는 적용됐지만 목적에 맞지 않게 사용됨

워크플로우 확인:

- Template: `app/workflow_templates/comfyui/txt2img_sdxl_stickman_lora.json`
- Node: `LoraLoader`
- Checkpoint: `sd_xl_base_1.0.safetensors`
- LoRA: `Stickfigures-000005.safetensors`
- Strength: `0.65`
- 적용 대상: model + clip

LoRA는 기술적으로 적용되고 있다. 다만 이 LoRA는 전기차/배터리/산업 설명에 특화된 LoRA가 아니라 스틱피겨/드로잉 스타일 성향이 강하다. 프롬프트가 구체적이면 보조 스타일로 쓸 수 있지만, fallback 프롬프트처럼 일반적인 문구가 들어가면 이상한 사람/상징 장면으로 튈 가능성이 크다.

### 5. 품질 게이트가 낮은 후보를 통과시킴

`body_image_last_log`에는 낮은 점수 후보에 대해 retry 권고가 남았다. 하지만 heavy style/control path로 판단되어 repair retry를 건너뛰었다.

결과적으로 0.44~0.62 수준의 후보가 그대로 render에 들어갔다.

현재 코드 기준:

- `app/services/comfyui_pipeline.py`
- `RETRY_SCORE_THRESHOLD = 0.6`
- `STRONG_SCORE_THRESHOLD = 0.72`
- 0.6 미만: `low_candidate_score`
- 0.6~0.72 미만: `borderline_candidate`
- 둘 다 기본적으로 render 차단은 하지 않음

따라서 EV/배터리 도메인에서는 0.72 미만을 “재생성 필요”로 보고, 최종 render 자동 진입은 별도 확인 또는 재생성 성공 후로 제한하는 정책이 필요하다.

## 문장별 권장 이미지 방향

현재 대본에는 photo-realistic 장면보다 “간결한 배터리/전기차 설명형 일러스트”가 더 적합하다.

1. 가성비와 LFP 배터리
   - 전기차 실루엣, 가격표, LFP 배터리 셀, 균형 저울
2. 한국 기업의 NCM 집중
   - 프리미엄 배터리 셀, 고성능 지표, 한국 배터리 공정
3. 비싼 가격이 대중화 걸림돌
   - 전기차 앞에 높은 가격 장벽, 소비자와 가격표
4. 중국 주도 LFP 장점
   - LFP 배터리 셀, 낮은 비용, 안전 방패, 짧은 주행거리 아이콘
5. 테슬라/현대차 선택
   - 글로벌 완성차 기업들이 LFP 배터리를 선택하는 공급망 장면
6. 한국 배터리 3사 반격
   - 세 개의 한국 배터리 공장/기업 실루엣, 전략 테이블, 배터리 셀
7. 한국형 LFP와 에너지 밀도
   - LFP 배터리 단면, 에너지 밀도 상승 게이지, 한국 기술 강조
8. 전고체 배터리 차세대 기술
   - solid-state battery 구조, 차세대 연구소, 미래형 배터리
9. 기술 주권
   - 배터리 셀을 쥔 손, 기술 주권 방패, 공급망 지도
10. 중국 물량 공세와 K-배터리 경쟁
   - 대량 배터리 물결 앞에서 K-배터리 셀이 버티는 경쟁 구도

## 개선 계획

### A. Visual planner 안정화

1. 문장 전체를 한 번에 JSON으로 받지 말고 문장별 또는 3문장 단위로 visual plan을 생성한다.
2. `num_predict`를 1800에서 최소 4000 이상으로 늘리거나, 문장별 호출로 token 부족을 제거한다.
3. visual plan 검증 조건을 강화한다.
   - 모든 sentence_idx가 있어야 함
   - `primary_keywords`, `must_show`, `hero_subject`에 문장 핵심어가 최소 2개 이상 포함되어야 함
   - `grounded editorial scene...` 같은 generic fallback 문자열은 최종 prompt 주어로 금지
4. visual plan이 80% 이상 fallback이면 이미지 생성 큐 진입을 막고 사용자에게 재생성/스타일 변경을 요구한다.

### B. EV/배터리 도메인 룰 추가

1. `app/services/domain_detection.py`에 battery/EV/automotive supply chain 도메인을 추가한다.
   - 감지 키워드: `전기차`, `EV`, `배터리`, `LFP`, `NCM`, `전고체`, `K-배터리`, `충전`, `주행거리`, `에너지 밀도`, `화재 위험`, `기술 주권`
   - 반환 도메인 후보: `ev_battery`
2. `storage/visual_vocab/ev_battery.json`을 추가한다.
   - 비교 구도: `BatteryCellComparison`
   - 안정성 구도: `SafetyShield`
   - 가격 장벽 구도: `PriceBarrier`
   - 전고체/차세대 구도: `SolidStateStability`
   - 공급망/물량 공세 구도: `SupplyChainPressure`
3. `app/services/visual_planner.py`의 `_domain_for_project()`, `_load_vocab()`, `_domain_vocab_tokens()`가 `ev_battery`를 처리하게 한다.
4. `app/services/image_prompting.py`의 template 선택이 `ev_battery`에서 `tech_documentary` 또는 `simple_diagram` 쪽으로 흐르게 한다.
5. EV/LFP/NCM/전고체/에너지 밀도/화재 위험/주행거리/가격/기술 주권 키워드 사전을 만든다.
6. fallback에서도 최소한 아래 객체가 보존되게 한다.
   - electric vehicle
   - battery cell
   - LFP battery
   - NCM battery
   - solid-state battery
   - price barrier
   - safety shield
   - energy density gauge
   - supply chain pressure

### C. 이미지 스타일 전환

현재 `Stickfigures-000005.safetensors` LoRA는 이번 대본에 적합하지 않다.

권장:

1. EV/배터리 도메인의 기본은 LoRA 없는 `txt2img_sdxl_basic` 또는 기술 일러스트용 LoRA가 있을 때만 `txt2img_sdxl_lora` strength 0.25~0.4로 낮춘다.
2. 배터리 해설 영상은 `simple_diagram` 또는 `tech_documentary` 스타일을 우선한다.
3. 스틱피겨 LoRA는 사람 중심 교육/만화 설명 장면에만 사용하고, 배터리/산업/기술 키워드 영상에서는 기본 비활성화한다.
4. LoRA 사용 시 `negative_prompt`에 아래를 추가한다.
   - unrelated human, desert, aircraft, fantasy creature, random road scene, unrelated animal, warrior, medieval, monster
5. Stickfigures LoRA를 계속 쓸 경우에는 프롬프트를 “스틱맨이 배터리 셀을 가리키는 설명 장면”처럼 LoRA 스타일과 명시적으로 맞춘다. 일반 실사/산업 장면 프롬프트와 Stickfigures LoRA를 섞지 않는다.

### D. 후보 품질 게이트 강화

1. EV/배터리 도메인 후보 점수 0.72 미만은 자동 render plan에 들어가지 못하게 한다.
2. 일반 도메인은 기존 0.6 retry, 0.72 borderline 기준을 유지하되, EV/배터리처럼 키워드 매칭이 중요한 설명형 도메인은 0.72를 차단 기준으로 승격한다.
3. retry 권고가 있으면 heavy LoRA path라도 최소 1회 재생성한다.
4. `final_scene_review`에서 `visual_plan_source=fallback`이고 score가 낮으면 UI에 “장면 교체 필요”로 표시한다.
5. 문장 핵심어와 prompt 핵심어 coverage를 점수화한다.
   - LFP/NCM/전고체/가격/안전/중국/한국형 같은 키워드가 prompt에 없으면 실패 처리
6. 관련 구현 대상은 `app/services/comfyui_pipeline.py`와 `app/workers/image_worker.py`다.

### E. Mapping 동기화 자동화

1. 이미지 재생성 또는 후보 재선택 시 `body_image_mappings`의 selected path와 `media_order`가 항상 같은 후보를 가리키게 한다.
2. `scene_plan`과 `render_plan`은 mapping 변경 직후 자동 재빌드한다.
3. Preflight의 `visual_relevance` 실패를 render 직전까지 미루지 않고, 이미지 생성 완료 직후 에러/경고로 표시한다.
4. 이번 프로젝트에서 실제로 0번/1번 mapping이 이전 `ev_lfp_actual_*` 파일을 선택하고, `media_order`는 새 `ev_lfp_real_*` 파일을 가리키는 불일치가 발생했다.

### F. 프롬프트 전문화

1. “스크립트 문장 → 이미지 장면” 전용 프롬프트 템플릿을 만든다.
2. output schema:
   - sentence_idx
   - core_keywords
   - must_show_objects
   - forbidden_objects
   - scene_type
   - positive_prompt
   - negative_prompt
   - rationale
3. 일반 MCP/스킬을 무조건 추가하기보다, 현재 코드 내부에 EV/tech explainer용 deterministic fallback을 먼저 넣는 것이 안정적이다.
4. 이후 필요하면 이미지 프롬프트 평가용 별도 MCP/LLM judge를 붙인다.
5. 구현 대상은 `prompt_compiler.py`가 아니라 우선 `visual_planner.py`, `image_prompting.py`, `visual_brief.py`다.

## 우선순위

1. 완료: `ev_battery` 도메인 감지와 `storage/visual_vocab/ev_battery.json` 추가.
2. 완료: EV/battery 도메인을 `visual_planner.py`와 `image_prompting.py` template 선택에 연결.
3. 완료: fallback prompt에서 EV/배터리 generic 주어를 배터리 핵심 객체로 대체.
4. 완료: EV/배터리 도메인 후보 점수 0.72 미만 retry 기준 적용.
5. 완료: EV/배터리 도메인 테스트 추가.
    - `tests/test_domain_detection.py`: EV 키워드 도메인 감지
    - `tests/test_image_prompting.py`: EV 문장별 prompt에 핵심 객체 보존
    - `tests/test_visual_planner.py`: fallback에서도 battery 객체 보존
    - `tests/test_comfyui_pipeline.py` 또는 관련 테스트: EV 도메인 0.72 미만 차단 정책
6. 다음: Visual planner를 문장별/소규모 batch로 변경하고 token 부족 제거.
7. 다음: Stickfigures LoRA 기본 비활성화 또는 strength 하향을 UI/API 기본값까지 연결.
8. 다음: retry 권고 후보가 남아 있으면 render 자동 진입을 막는 작업 상태 게이트 추가.
9. 다음: 이미지 재생성 후 mapping/media_order/scene_plan/render_plan 동기화 자동화.
10. 다음: 이미지 생성 전 prompt manifest에서 fallback 비율과 keyword coverage를 UI에 표시.
11. 다음: 이 대본으로 실제 ComfyUI 이미지 재생성 후 contact sheet 기준 재검수.
## 2026-05-16 LM Studio/Gemma4 연결 안정화 반영

- NewAuto Studio의 이미지 프롬프트/visual planner LLM 경로는 LM Studio + `google/gemma-4-e4b`를 기본값으로 사용하도록 고정했다.
- 현재 설치/로드 모델 기준으로 `gemma4 e8b` 식별자는 확인되지 않았으므로, 실제 사용 가능한 `google/gemma-4-e4b`를 기준 모델로 검증했다.
- LM Studio ready 판단은 `/v1/models` 목록만 신뢰하지 않고 `lms ps` 기반 로드 모델을 우선 확인한다. 로드 모델이 있으면 `SCRIPT_LLM_MODEL`과 정확히 일치해야 ready로 처리한다.
- `/api/system/diagnostics`에서 `llm_provider`, `llm_model`, `llm_base_url`, `llm_ready`, `lmstudio_loaded_models`를 확인할 수 있게 했다.
- 연결 검증 결과: `OllamaClient` LM Studio 모드 직접 호출 `response OK`, NewAuto Studio API 진단 `llm_ready=true`, 로드 모델 `["google/gemma-4-e4b"]`.
- 회귀 검증: 131 passed, 2 warnings.
