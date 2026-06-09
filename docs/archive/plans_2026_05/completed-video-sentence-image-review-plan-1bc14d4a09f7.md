# 완성본 문장-이미지 점검 및 개선 계획서

대상 프로젝트: `1bc14d4a09f7`  
최종 영상: `C:\Users\petbl\newauto\storage\projects\1bc14d4a09f7\output.mp4`  
검토 기준: 최종 선택 이미지, 대본 문장 15개, `scene_visual_plan.json`, `image_prompts_manifest.json`, 진단 컨택트시트

## 1. 요약

이번 완성본은 예전처럼 완전히 엉뚱한 풍경이나 무의미한 체크리스트로 무너지는 문제는 줄었지만, 아직 두 가지 큰 문제가 남아 있습니다.

1. 상류 의미 계획이 2번 문장 이후 다수 구간에서 같은 fallback 의미 묶음으로 붕괴됩니다.
2. 하류 프롬프트와 후보 선택이 그 fallback을 반복 강화하면서, 서로 다른 문장도 비슷한 사무실/모니터/보드 장면 또는 얇은 아이콘 장면으로 수렴합니다.

즉 지금 결과는 "아무 이미지나 랜덤 생성"은 아니고, "잘못 압축된 의미를 일관되게 반복 생성"하는 쪽에 가깝습니다.

## 1.1 진행 상태

- 완료: P0 1차
  - `VisualPlanEntry`, `VisualBrief`에 `semantic_anchor_type`, `semantic_anchor_tokens` 필드 추가
  - planner fallback과 LLM 정규화 경로에서 문장별 의미 앵커를 저장하도록 반영
  - planner 출력 스키마와 프롬프트 규칙에 의미 앵커 요구사항 추가
- 완료: P2 1차
  - 기사/뉴스 해설 계열 도메인에서 `prompt_compiler` 기본 스틱 피겨 슬롯 주입 차단
  - `Flipchartvisu`, `Stick figure`가 기본값으로 역류하는 하류 경로 1차 차단
- 완료: P1 1차
  - `semantic_anchor_type` 기반으로 essay 도메인의 `visual_mode` 우선순위 재분류
  - `future_outlook`, `market_structure`, `technical_barrier`, `institutional_decision`에 따라 `scene_anchor`가 달라지도록 반영
  - 같은 네 가지 모드 안에서도 장면 성격이 더 분기되도록 planner 쪽 scene field 계산 보강
- 완료: P3 1차
  - `candidate_score`에 `scene_family_repeat_penalty` 추가
  - 이전 manifest 장면의 `visual_mode`, `scene_anchor`, `hero_subject`, `composition_template`, `semantic_anchor_type`, `semantic_anchor_tokens`와 현재 후보를 비교해 반복 감점
- 완료: 검증
  - 관련 회귀 테스트 `104 passed`
- 완료: P4 1차
  - `image_worker`에 `MAX_PLAN_RETRIES = 1` 상한을 둔 bounded scene-plan regeneration 루프 추가
  - `low_candidate_score`, `borderline_candidate` 저신뢰 장면은 heavy/manual 케이스가 아니면 prompt repair 전에 visual mode 재계획 우선 수행
  - regenerated prompt item이 `visual_plan`, `scene_anchor`, `semantic_anchor_type` 메타를 유지한 채 candidate import와 점수 계산까지 전달되도록 override 경로 연결
- 완료: P5 1차
  - 렌더 완료 시점에 `candidate_reviews`, 최종 mapping, manifest plan 메타를 묶은 `final_scene_review.json` 스냅샷 저장
  - `selection_reason`, `retry_reason`, `visual_mode`, `scene_anchor`, `semantic_anchor_type`, `vision_qa_issue_codes`를 문장별 고정 산출물로 보존
  - `render_report.json`에 `final_scene_review_path`, `final_scene_review_exists`를 노출해 후속 UI/운영 화면에서 같은 파일을 재사용할 수 있도록 연결
- 완료: P6 1차
  - scene-plan regeneration 이후에도 저신뢰 판정이 반복되면 `safe fallback visual_mode`로 한 번 더 강등하는 bounded fallback downgrade 루프 추가
  - fallback downgrade 이후에도 `retry_recommended`가 남으면 `operator_intervention_required`, `operator_intervention_reason`을 candidate review와 최종 스냅샷에 고정 저장
  - 이미지 워커 종료 phase에 `done_with_operator_warning`를 추가해, 자동 파이프라인 완료와 운영자 확인 필요 상태를 분리
- 완료: UI/operator 노출 1차
  - `render-report` 화면에서 `final_scene_review.json` 존재 여부, fallback 강등 수, operator warning 수, 문장별 preview를 함께 표시
  - 이미지 매핑 카드에서 `fallback_downgrade_applied`, `operator_intervention_required` 상태를 직접 노출
  - `/api/projects/{pid}/final-scene-review` read endpoint 추가로 UI와 운영 화면이 동일 스냅샷을 재사용하도록 연결
- 완료: 테스트 격리 안정화
  - 이미지 워커 테스트는 전역 `claim_next_queued_body_image()` 의존을 줄이고, 각 테스트가 자체 프로젝트를 직접 `running` 상태로 올려 aggregate run에서도 queue 간섭이 없도록 정리
  - operator 테스트는 실제 워크스페이스의 누적 프로젝트 히스토리에 덜 민감하도록 검증 조건을 조정
  - aggregate regression 기준 `104 passed`로 재확인

## 2. 전체 진단

좋았던 점:

- 문장 1, 2는 단순 설명형 이미지로 방향을 바꾼 뒤 이전보다 훨씬 직관적이 되었습니다.
- 문장 3, 5, 8, 10, 13은 금융 기사 톤과 맞는 편집적 장면으로 어느 정도 안정적입니다.
- 컨택트시트 기준으로 최소한 장면 타입이 한 가지로만 고정되지는 않았습니다.

남은 문제:

- 문장 3, 4, 5, 7, 8, 10, 13이 사실상 같은 `analyst desk + quantum barrier + risk board` 계열 프롬프트를 공유합니다.
- 문장 6, 9, 11, 12, 14는 의미를 충분히 압축하지 못한 상태에서 아이콘형 fallback으로 내려가, 대본 대비 설명력이 약합니다.
- 저점수 장면 상당수가 `only_candidate` 또는 `retry_recommended` 상태로 최종 채택되어, 선택 단계의 신뢰도도 낮습니다.
- 완성본은 통과했지만 "프리플라이트 통과"와 "의미적으로 충분히 좋은 장면"은 아직 같은 뜻이 아닙니다.

## 3. 문장별 점검

### 문장 0

대본:
"과거에는 미래 금융 시장의 판도를 바꿀 핵심 기술로 큰 기대를 모았던 '양자 컴퓨팅'."

선택 이미지:
`autopilot_scene_000_00015_.png`

판정:
보완 필요

문제점:

- 이미지 자체는 고급스럽지만, 금융 기사 도입부라기보다 추상 SF 비주얼에 더 가깝습니다.
- "금융 시장의 판도"와 "큰 기대"는 보이지만 "기사형 맥락"은 약합니다.
- 스코어도 `0.43`으로 낮고 `retry_recommended` 상태였습니다.

개선 방향:

- 도입부는 `symbolic_concept`를 유지하되 `시장 재편`, `금융 기대`, `전략적 잠재력` 같은 경제 맥락 앵커를 더 강하게 넣어야 합니다.
- 추상 회로만이 아니라 `graph field`, `market topology`, `institutional horizon` 같은 보조 시각 표지를 허용해야 합니다.

### 문장 1

대본:
"투자 포트폴리오 최적화나 복잡한 시장 변동성 예측 같은 실제 금융 과제에 이 기술을 적용하려는 시도가 이어져 왔습니다."

선택 이미지:
`manualfix_scene_001b_00001_.png`

판정:
양호

문제점:

- 수동 보정본이라 자동 파이프라인이 스스로 도달한 결과는 아닙니다.
- 기어 중심 설명형 구성은 직관적이지만, `포트폴리오 최적화`와 `변동성 예측`이 한 장면에서 충분히 분리되지는 않습니다.

개선 방향:

- `simple_explainer` 모드의 기본 템플릿으로 승격할 만한 방향입니다.
- 다만 `gear` 하나로 모든 최적화 문장을 퉁치지 않도록 `balance / branching / volatility wave` 같은 보조 아이콘 세트를 문장별로 바꿔야 합니다.

### 문장 2

대본:
"하지만 최근, 이 기술의 상용화 시점에 대한 불확실성이 커지면서 업계의 반응이 엇갈리고 있습니다."

선택 이미지:
`manualfix_scene_002_00001_.png`

판정:
보완 필요

문제점:

- 찬반 계수기 같은 구도는 "반응이 엇갈린다"는 뜻은 잡았지만, "상용화 시점의 불확실성"이 약합니다.
- 기사 문장에 비해 시각 언어가 지나치게 단순해, 산업 판단의 무게감이 떨어집니다.

개선 방향:

- `data_diagram` 계열로 유지하되 `time uncertainty`, `delayed adoption`, `split institutional stance`를 함께 보여주는 템플릿이 필요합니다.
- "찬성/반대"보다 "시점 불확실성 때문에 평가가 갈림"이 먼저 읽히는 구성이 더 적합합니다.

### 문장 3

대본:
"과거에는 금융권에서 가장 선도적으로 양자 컴퓨팅 기술 개발에 앞장서던 곳들이 많았습니다."

선택 이미지:
`autopilot_scene_003_00013_.png`

판정:
양호

문제점:

- 편집적 분위기와 금융권 톤은 괜찮지만, 이후 여러 문장과 너무 비슷한 계열로 재사용됩니다.

개선 방향:

- 이 장면은 기준점으로 괜찮습니다.
- 다만 이후 문장에는 같은 장면을 반복하지 말고 `research lab`, `strategy meeting`, `capital allocation board` 등으로 분화해야 합니다.

### 문장 4

대본:
"실제로 일부 거대 투자은행들은 이 기술을 활용해 수익률을 극대화할 방안을 연구하며 큰 기대를 걸었습니다."

선택 이미지:
`autopilot_scene_004_00013_.png`

판정:
보완 필요

문제점:

- 문장 3, 5와 거의 같은 시각 문법입니다.
- "거대 투자은행", "수익률 극대화", "큰 기대" 중 어떤 의미도 장면 차별화에 충분히 반영되지 않았습니다.
- 스코어도 `0.39`로 낮고 `retry_recommended`였습니다.

개선 방향:

- 기관 서사 문장은 `editorial_scene` 안에서도 역할을 나눠야 합니다.
- `institutional ambition`, `capital allocation`, `profit optimization research`를 드러내는 다른 장면 레시피가 필요합니다.

### 문장 5

대본:
"양자 알고리즘이 여러 변수를 동시에 계산하여 기존 방식보다 효율적인 투자 전략을 제시할 것이라는 기대가 컸기 때문입니다."

선택 이미지:
`autopilot_scene_005_00013_.png`

판정:
양호

문제점:

- 기사 문장과는 맞는 편이지만, 결과가 다시 모니터/데스크형 비주얼로 쏠려 있습니다.
- "여러 변수 동시 계산"이라는 핵심 개념은 실제로 더 도식적인 이미지가 적합할 수 있습니다.

개선 방향:

- 이 문장은 `data_diagram` 또는 `symbolic_concept`로도 충분히 풀 수 있습니다.
- 같은 사무실 계열보다 `multi-path optimization`을 명확히 드러내는 장면이 더 강합니다.

### 문장 6

대본:
"하지만 실제 현장의 과제에 이 기술을 적용하는 과정에서 기술적인 한계점들이 드러나면서 상황이 달라지고 있습니다."

선택 이미지:
`autopilot_scene_006_00014_.png`

판정:
재설계 필요

문제점:

- 현재 이미지는 경로 아이콘 수준이라 "현장 적용 과정에서 드러난 기술적 한계"라는 핵심을 거의 설명하지 못합니다.
- 이 문장은 실제론 기사 전체의 전환점인데, 장면은 너무 가볍고 추상적입니다.

개선 방향:

- `symbolic_concept`로 재설계해 `실험실 수준 기술`과 `현장 적용 장벽`의 충돌을 보여줘야 합니다.
- 단순 갈림길보다 `prototype vs production`, `lab promise vs market friction` 구조가 필요합니다.

### 문장 7

대본:
"이로 인해 일부 금융기관들은 개발 속도를 조절하는 모습을 보이기도 했습니다."

선택 이미지:
`autopilot_scene_007_repair_1_00004_.png`

판정:
보완 필요

문제점:

- 사무실 장면은 안전하지만, "속도 조절"이라는 행위가 장면 안에서 거의 읽히지 않습니다.
- 의미는 맞는 듯 보이나 실제로는 문장 4, 8, 10과 구분이 약합니다.

개선 방향:

- `speed moderation`은 `timeline`, `throttle`, `staged rollout` 같은 개념 시각화가 필요합니다.
- 기관 서사 장면이라도 "연구는 계속하지만 페이스는 늦춘다"가 읽혀야 합니다.

### 문장 8

대본:
"실제로 한 주요 투자은행의 경우, 과거 적극적으로 관련 기술을 연구하던 조직을 최근 정리했다는 소식이 전해지면서 업계의 관심이 쏠리고 있습니다."

선택 이미지:
`autopilot_scene_008_00011_.png`

판정:
양호

문제점:

- 분위기와 톤은 좋지만, "조직 정리"와 "업계 관심 집중"이라는 사건성이 더 분명해질 여지가 있습니다.

개선 방향:

- `editorial_scene` 안에서 `empty desks`, `archived lab`, `restructured team board` 같은 사건 표지를 도입하면 더 좋아집니다.

### 문장 9

대본:
"반면, 모든 기관이 같은 방향을 보고 있는 것은 아닙니다."

선택 이미지:
`autopilot_scene_009_00009_.png`

판정:
재설계 필요

문제점:

- 스틱 피겨와 보드는 현재 기사 톤과 너무 멉니다.
- "기관마다 방향이 다르다"는 문장을 지나치게 저가형 설명 컷으로 처리해 영상 밀도가 크게 떨어집니다.
- 스코어도 `0.26`으로 최저권입니다.

개선 방향:

- 이 문장은 `branching institutional strategy`를 보여주는 깔끔한 설명형 다이어그램이 맞습니다.
- 다만 `Flipchartvisu, Stick figure`는 이 기사군에서 기본 금지에 가깝게 다뤄야 합니다.

### 문장 10

대본:
"일부 선도적인 금융사들은 여전히 양자 컴퓨팅을 미래 성장의 중요한 동력으로 판단하며, 막대한 투자를 지속하고 있는 모습입니다."

선택 이미지:
`autopilot_scene_010_00008_.png`

판정:
양호

문제점:

- 문장 8의 축소 변형처럼 보일 여지가 있습니다.
- "막대한 투자 지속"이라는 메시지는 더 강한 자본 배치 장면으로 살릴 수 있습니다.

개선 방향:

- `capital commitment`, `ongoing program`, `long-horizon investment` 시각 언어를 분리해줘야 합니다.

### 문장 11

대본:
"이처럼 기술의 발전 속도와 실용화 가능성에 대한 평가가 업계 전반에 걸쳐 다양한 양상으로 나타나고 있습니다."

선택 이미지:
`manualfix_scene_011_00001_.png`

판정:
보완 필요

문제점:

- 경고 배지, 화살표, 은행 아이콘 조합은 설명형으론 무난하지만 문장이 가진 넓은 업계 평가 스펙트럼을 충분히 담지 못합니다.
- "속도"와 "실용화 가능성"이 각각 무엇인지 직관적으로 분해되지 않습니다.

개선 방향:

- `two-axis explainer`가 더 적합합니다.
- 예를 들면 `발전 속도`와 `실용화 가능성`을 두 축으로 둔 간단한 포지셔닝형 다이어그램이 더 직접적입니다.

### 문장 12

대본:
"한때 '게임 체인저'로 불렸던 양자 컴퓨팅 기술."

선택 이미지:
`manualfix_scene_012_00001_.png`

판정:
보완 필요

- 갈림길+도착점 조합은 "전환점"에는 맞을 수 있지만, "게임 체인저"라는 과거 평가 자체를 직접 보여주진 못합니다.
- 단독 문장으로 보면 상징이 너무 약하고 기억점이 적습니다.

개선 방향:

- `symbolic_concept`로 재구성해 `spotlighted breakthrough promise`나 `industry game-board shift`처럼 더 강한 상징이 필요합니다.

### 문장 13

대본:
"이제는 기술적 난제와 상용화 시점이라는 현실적인 벽에 부딪히며, 금융 산업의 미래 전략을 재정비하는 중요한 변곡점에 서 있는 것으로 보입니다."

선택 이미지:
`autopilot_scene_013_00004_.png`

판정:
양호

문제점:

- 문장 자체는 잘 받았지만 역시 이전 사무실 계열과 가까워서 피로감이 있습니다.

개선 방향:

- `barrier / pivot / strategy reset`를 더 전면화한 상징 장면이면 훨씬 강해집니다.

### 문장 14

대본:
"앞으로 어떤 방향으로 기술 개발과 투자가 이루어질지 귀추가 주목됩니다."

선택 이미지:
`autopilot_scene_014_00001_.png`

판정:
재설계 필요

문제점:

- 결론 문장인데도 스틱 피겨 기반이라 마무리 힘이 거의 없습니다.
- "앞으로의 방향"은 중요한 엔딩 훅인데, 현재 이미지는 기사 마감 컷으로 약합니다.
- 스코어도 `0.29`로 매우 낮습니다.

개선 방향:

- 엔딩 문장은 `future paths`, `capital direction`, `technology roadmap` 중 하나로 정리된 고급 설명 컷이 필요합니다.
- 마지막 장면은 영상 전체의 신뢰감을 올리므로 별도 엔딩 전용 템플릿을 두는 편이 맞습니다.

## 4. 구조적 원인

### 4.1 상류 의미 계획의 fallback 붕괴

`scene_visual_plan.json`을 보면 문장 0, 1만 비교적 구체적이고, 2번 이후 다수 문장이 사실상 같은 fallback 축으로 내려갑니다.  
이 현상은 주로 [visual_planner.py](C:/Users/petbl/newauto/app/services/visual_planner.py) 내부의 `_extract_concrete_tokens`, `_fallback_entry`, `_repair_generic_essay_entry`, `_choose_visual_mode`, `_apply_adjacent_visual_diversity` 흐름에서 발생합니다.

핵심 문제:

- 문장별 의미 차이를 살릴 만한 명사구 추출이 충분하지 않습니다.
- planner가 실패하면 여러 문장이 같은 `financial analyst desk + quantum barrier + risk board` 계열로 수렴합니다.
- 다양성 로직은 "모드"는 바꾸지만, 실제 `core meaning anchor`가 같아지면 결과도 비슷해집니다.

보강 포인트:

- 현재 [types.py](C:/Users/petbl/newauto/app/types.py)의 `VisualPlanEntry`에는 `semantic_anchor_type`, `semantic_anchor_tokens` 같은 강제 의미 앵커 필드가 없습니다.
- 그래서 planner가 문장 고유의 경제/전략 의미를 잃어도 하류가 그 손실을 구조적으로 감지하기 어렵습니다.
- 이 문제는 단순 휴리스틱 보강만으로는 부족하고, planner의 LLM 출력 계약 자체를 바꿔 "fallback으로 내려가기 전 반드시 문장 고유 의미 앵커를 JSON에 남긴다"는 규칙이 필요합니다.

### 4.2 프롬프트 다양화는 들어갔지만 의미 다양화는 아직 부족

[image_prompting.py](C:/Users/petbl/newauto/app/services/image_prompting.py)에는 `ESSAY_SYMBOLIC_TEMPLATE`, `ESSAY_EXPLAINER_TEMPLATE`, `ESSAY_DATA_DIAGRAM_TEMPLATE`가 있고, 모드별 템플릿 분기는 작동합니다.

하지만 문제는:

- planner가 같은 의미 앵커를 넘기면 템플릿만 달라져도 내용은 비슷해집니다.
- 결과적으로 "사무실 장면의 변주" 또는 "아이콘 장면의 변주" 수준에서 멈춥니다.

보강 포인트:

- 템플릿 분기와 별개로 [prompt_compiler.py](C:/Users/petbl/newauto/app/services/prompt_compiler.py)의 `_default_positive_slots()`에는 `Flipchartvisu`, `Stick figure`가 기본값으로 하드코딩되어 있습니다.
- 따라서 단순 blocklist만으로는 부족하고, 금융/뉴스 해설 계열 도메인에서는 아예 이 기본 슬롯 주입 경로를 타지 않도록 컴파일 단계에서 분기해야 합니다.
- 그렇지 않으면 상위에서 막으려 해도 하위 컴파일러가 다시 스틱 피겨 계열을 주입하는 역류가 생깁니다.

### 4.3 후보 선택이 의미 적합성보다 프롬프트 자기일치를 더 많이 본다

[comfyui_pipeline.py](C:/Users/petbl/newauto/app/services/comfyui_pipeline.py)의 `_compute_candidate_score_details`와 `_select_best_candidate`는 이미 `scene_variety_penalty`를 갖고 있습니다.

하지만 실제 결과를 보면:

- 문장 4, 7, 14 같은 저점수 장면도 대체 후보가 약하면 그대로 채택됩니다.
- "문장에 맞는가"보다 "현재 프롬프트를 그럴듯하게 따랐는가"가 여전히 강합니다.

보강 포인트:

- 현재 [comfyui_pipeline.py](C:/Users/petbl/newauto/app/services/comfyui_pipeline.py)의 `scene_variety_penalty`는 `office`, `desk` 같은 표면 키워드 반복을 감점하는 수준입니다.
- 하지만 실제 반복은 단어보다 `hero_subject`, `scene_anchor`, `composition_template`, `visual_mode`의 조합에서 발생합니다.
- 따라서 장면 가족 반복 감지는 문자열 히트 수가 아니라, 이전 2~3장면의 `VisualBrief` 또는 `VisualPlanEntry` 메타 비교 기반으로 강화하는 편이 맞습니다.

### 4.4 repair 루프가 의미 재설계보다 표면 보정에 가깝다

[image_worker.py](C:/Users/petbl/newauto/app/workers/image_worker.py)의 `_build_repair_suggestion` 경로는 품질 이슈 보정에는 유용하지만, 의미가 약한 장면을 근본적으로 다시 설계하는 루트는 아닙니다.

그래서 발생하는 일:

- 약한 계획으로 생성된 장면이 품질만 조금 수정된 채 남습니다.
- `retry_recommended`가 떠도 장면 개념 자체가 뒤집히지는 않습니다.

보강 포인트:

- [image_worker.py](C:/Users/petbl/newauto/app/workers/image_worker.py) 쪽 repair 루프는 "프롬프트 보정"에는 적합하지만 "scene plan 재생성"은 아직 예외 경로에 가깝습니다.
- 저신뢰 장면은 재생성으로 보내는 것이 맞지만, 이 루프에는 `MAX_PLAN_RETRIES = 1` 같은 상한이 반드시 필요합니다.
- 상한 없이 scene regeneration을 넣으면 Autopilot이 무한 재시도하거나 긴 체인 대기 상태에 빠질 위험이 있습니다.

### 4.5 수동 복구와 최종 산출물 사이의 추적성도 약하다

[image_gen.py](C:/Users/petbl/newauto/app/routers/image_gen.py)의 수동 작업 경로는 이전보다 나아졌지만, 최종 렌더 리포트와 실제 선택 이미지 사이의 스냅샷 일치성은 아직 점검이 더 필요합니다.

즉 운영상으로도:

- "무엇이 선택되었는가"
- "무엇이 렌더에 반영되었는가"
- "왜 그 장면이 최종 통과했는가"

이 세 가지를 한 번에 추적하기 어렵습니다.

보강 포인트:

- 렌더 완료 시점에 문장별 채택 사유, 후보 수, 점수, QA 결과, 수동 개입 여부를 한 번에 고정하는 `final_scene_review.json`이 필요합니다.
- 이 파일은 백엔드 진단용으로만 끝내지 말고, 이후 UI에서 "왜 이 장면이 선택됐는가"를 바로 보여주는 근거 데이터로도 쓰는 것이 운영상 효과적입니다.

## 5. 우선순위별 개선 계획

### P0. 문장 의미 앵커를 문장별로 강제 보존

목표:

- 서로 다른 문장이 같은 fallback 의미로 합쳐지지 않게 막기

작업:

- `visual_planner`에서 각 문장별 `semantic_anchor_type`과 `semantic_anchor_tokens`를 별도 필드로 저장
- 기관 판단, 속도 조절, 투자 지속, 전략 재정비 같은 기사형 추상 개념에 대해 도메인 사전을 추가
- fallback이어도 최소 1개는 문장 고유 의미를 보존하도록 강제
- planner LLM 출력 스키마와 시스템 프롬프트를 수정해, `capital allocation`, `strategy reset`, `institution split`, `commercialization timing` 같은 경제/산업 앵커를 JSON으로 명시하게 만들기

### P1. 기사형 문장 전용 visual-mode 세분화

목표:

- `editorial_scene`와 `symbolic_concept` 내부의 과도한 한 방향 쏠림 완화

작업:

- `editorial_scene`를 `research_scene`, `institution_scene`, `capital_scene`, `strategy_reset_scene`로 내부 분기
- `simple_explainer`를 `comparison_explainer`, `timeline_explainer`, `axis_diagram`으로 세분화
- 엔딩 문장용 `closing_outlook_scene` 템플릿 추가

### P2. 스틱 피겨와 플립차트 계열을 기사 도메인 기본 금지로 전환

목표:

- 문장 9, 14 같은 장면 재발 방지

작업:

- 금융/산업 기사 도메인에서는 `Flipchartvisu`, `Stick figure` 계열을 기본 blocklist로 이동
- 정말 필요한 경우에만 명시적 opt-in으로 허용
- [prompt_compiler.py](C:/Users/petbl/newauto/app/services/prompt_compiler.py)의 `_default_positive_slots()`가 해당 트리거를 기본 주입하지 않도록 도메인 조건 분기 추가
- `finance`, `news_explainer`, `essay` 계열에서는 스틱 피겨 기본 프롬프트 경로를 타지 않도록 컴파일 단계에서 차단

### P3. 장면 반복 감지 기준을 "단어"가 아니라 "장면 의미"로 강화

목표:

- 사무실+보드 계열 반복을 더 강하게 줄이기

작업:

- 후보 점수에 `scene_family_repeat_penalty` 추가
- 직전 2~3장면과 `hero_subject`, `scene_anchor`, `composition_template`가 유사하면 감점
- 같은 문단 안에서 동일 장면 가족이 2회 이상 반복되면 자동 재계획
- 단순 `office_hits` 계수 대신, 이전 장면들의 `VisualBrief` 메타 또는 해시를 함께 넘겨 장면 가족 중복을 비교
- `visual_mode`가 달라도 실제 앵커 조합이 같으면 반복으로 판단하는 보정 추가

### P4. 저신뢰 장면은 후보 선택 대신 재계획으로 보내기

목표:

- `0.25 ~ 0.40`대 약한 장면이 억지 통과되는 구조 줄이기

작업:

- `only_candidate`이면서 스코어가 낮은 경우 자동 통과 금지
- `retry_recommended`가 두 번 누적되면 prompt repair 대신 scene-plan regeneration 수행
- 엔딩 문장, 전환 문장, 핵심 주장 문장은 임계값을 더 높게 설정
- scene-plan regeneration에는 `MAX_PLAN_RETRIES = 1` 같은 상한을 두고, 실패 시 안전한 fallback 모드로 강등
- regeneration 실패 후에도 같은 이유가 반복되면 무한 루프 대신 운영자 개입 필요 상태로 명시

### P5. 설명형 장면용 아이콘 문법 확장

목표:

- 기어, 갈림길, 경고 배지 같은 몇 개 심볼에 과의존하지 않기

작업:

- `visual_vocab`에 금융 기사용 단순 심볼 세트 추가
- 예시: `allocation grid`, `staged timeline`, `probability field`, `institution split`, `lab-to-market barrier`, `capital runway`
- 문장 의미별 추천 심볼 묶음을 planner가 고르도록 수정

### P6. 리뷰/리포트 추적성 보강

목표:

- 최종 영상 검수와 자동 개선 루프 연결

작업:

- 문장별 최종 채택 이유, 점수, 후보 수, 수동 개입 여부를 별도 `final_scene_review.json`으로 저장
- 렌더 시점 스냅샷과 현재 선택 상태를 함께 기록해 불일치 탐지
- Vision QA 이슈 코드와 최종 해소 여부도 함께 고정해, "왜 통과했는가"를 나중에 추적 가능하게 만들기
- 이후 UI에서 문장별 장면 배지와 선택 사유를 바로 보여줄 수 있게 필드 구조를 미리 설계

## 6. 다음 구현 순서

1. `visual_planner`의 출력 계약을 확장해 `semantic_anchor_type`, `semantic_anchor_tokens`를 추가하고 LLM 프롬프트까지 함께 수정
2. 금융 기사 도메인에서 스틱 피겨/플립차트 기본 차단
3. [prompt_compiler.py](C:/Users/petbl/newauto/app/services/prompt_compiler.py) 기본 슬롯 주입 경로를 도메인별로 분기
4. 설명형 모드 세분화와 엔딩 전용 템플릿 추가
5. 후보 선택에 `scene_family_repeat_penalty`와 저신뢰 재계획 규칙 추가
6. regeneration 루프 상한과 fallback 강등 규칙 추가
7. 최종 검수 리포트 포맷 분리 및 `final_scene_review.json` 저장

## 7. 결론

이번 완성본은 "완전히 틀린 그림" 단계는 지나왔지만, 아직 "문장마다 다른 의미를 갖는 기사형 영상"으로 보긴 어렵습니다.  
핵심 병목은 이미지 모델 자체보다, 서로 다른 문장이 중간 단계에서 같은 의미 묶음으로 압축되고 그 상태가 하류에서 반복 강화된다는 점입니다.

따라서 다음 수정의 목표는 단순 품질 향상이 아니라 아래 세 가지를 동시에 만족하는 것입니다.

- 문장별 의미 차이 보존
- 장면 타입 다양화
- 기사 톤에 맞는 일관된 미감 유지
