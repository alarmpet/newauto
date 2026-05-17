# ChatGPT Image 2.0 Article Visual Quality Recovery Plan - 코드베이스 검토 및 의견

제공해주신 `chatgpt-image2-visual-quality-recovery-plan.md` 문서와 현재 코드베이스(`app/services/image_prompting.py`, `app/services/visual_planner.py`, `storage/visual_vocab/tech.json` 등)를 대조하여 분석한 결과 및 제 의견입니다.

## 1. 전반적인 평가
**문서의 진단은 현재 코드베이스의 결함과 파이프라인의 구조적 한계를 매우 정확하게 짚어내고 있습니다.** 특히 `disable_llm_visual_planner`의 잘못된 동작 방식으로 인해 `tech.json`에 이미 정의된 훌륭한 시각 어휘들이 완전히 무시되고 있는 현상을 찾아낸 것은 파이프라인 품질 저하의 가장 핵심적인 원인을 식별한 것입니다.

제시된 복구 계획(P0~P2)은 모두 기술적으로 타당하며, 워크플로우 안정성을 크게 높일 수 있는 방향입니다.

## 2. 세부 검토 및 의견

### [P0] Planner 우회 버그 수정 (가장 시급하고 정확한 진단)
- **코드베이스 확인 결과:** 문서의 지적대로 `app/services/image_prompting.py`의 `suggest_image_prompt_batch()` 함수 948라인에서 `if project["body_image_options"].get("disable_llm_visual_planner") is not True:` 조건으로 인해 `build_scene_visual_plan()` 호출 자체가 스킵되고 있습니다.
- **문제점:** 정작 `app/services/visual_planner.py`의 `build_scene_visual_plan()` 함수 984라인을 보면, 해당 옵션이 `True`일 때 `_normalize_entries(project, [], domain=_domain_for_project(project), source="fallback")`를 호출하여 안전하게 Fallback Plan을 만들도록 훌륭하게 구현되어 있습니다. 호출 자체를 막아버려서 이 방어 로직이 전혀 작동하지 못했습니다.
- **동의 및 제언:** 문서에 작성된 해결책에 100% 동의합니다. `suggest_image_prompt_batch`에서의 단락(short-circuit) 로직을 제거하여, 옵션이 켜져 있더라도 Fallback 플래너가 작동하여 `tech.json`의 어휘가 적용되게 해야 합니다.

### [P0] AI 이미지 제품 전용 tech vocab/template 추가
- **코드베이스 확인 결과:** `storage/visual_vocab/tech.json`을 확인해 본 결과, 놀랍게도 `AI image style transformation from one photo`, `AI product user growth metrics` 등의 어휘가 이미 **추가되어 있는 상태**입니다.
- **의견:** 플래너 우회 버그만 수정된다면, 이미 작성된 이 어휘들이 즉시 활성화되어 "browser window" 같은 일반적인 이미지로 빠지는 현상이 크게 줄어들 것입니다. 추가로 문서에서 언급한 대로 `visual_brief` 단계에서의 fallback 우선순위를 세밀하게 조정하는 작업만 병행하면 충분할 것으로 보입니다.

### [P0] 의미 점수 게이트 강화
- **의견:** 우베 기사 사례(v2 계획서)에서도 드러났듯, 0.65대 생성 이미지를 무분별하게 통과시키는 것은 치명적입니다. 0.72 미만 이미지를 차단하고 `borderline` 재시도를 명시적으로 요구하도록 `visual_relevance.py`를 수정하는 방향은 전체 품질의 하한선을 높이는 데 반드시 필요합니다.

### [P1] 인코딩 방어 (Mojibake)
- **코드베이스 확인 결과:** 현재 코드베이스 전체를 검색해본 결과, `mojibake`나 인코딩 깨짐을 방어하는 명시적인 검열/차단 로직이 존재하지 않습니다.
- **의견:** 깨진 문자가 파이프라인 초기에 유입되면 도메인 감지나 LLM 프롬프트가 오염되어 예측 불가능한 결과를 낳습니다. 저장 단계에서 한글 문자열의 정합성을 검증하는 방어막을 추가하는 것은 파이프라인 견고함을 위해 매우 좋은 제안입니다.

### [P1] Diagram style generator를 자동화 & ComfyUI timeout 복구 정책
- **의견:** 수동 PIL 보정에 의존하는 것은 자동화 파이프라인의 목적에 맞지 않으며 스타일의 이질감을 줍니다. `diagram_assets.py` 등을 통한 확정적(deterministic) 생성기로 fallback을 돌리는 것은 뛰어난 아이디어입니다.
- **제언:** 다만 이 작업은 신규 에셋 템플릿과 텍스트 레이아웃 계산 로직을 다수 작성해야 하므로 P0 버그들을 먼저 배포한 후, 별도의 개발 사이클로 집중해서 구현하는 것을 추천합니다.

## 3. 결론 및 향후 진행 추천
작성해주신 복구 계획서는 코드베이스의 맹점을 완벽히 꿰뚫고 있습니다.

가장 즉각적이고 극적인 품질 향상을 위해 다음 **두 가지 로직 수정(P0)을 최우선으로 즉시 실행**하는 것을 추천합니다.
1. `image_prompting.py`에서 `disable_llm_visual_planner` 체크 로직 수정 (스킵 방지)
2. `visual_relevance.py`의 통과 기준 점수를 `0.72`로 상향 조정 및 정책 구체화

해당 의견서를 저장했습니다.
