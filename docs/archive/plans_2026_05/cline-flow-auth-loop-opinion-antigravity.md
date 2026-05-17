# Cline Flow 인증 루프 실패 분석 및 개선 의견 (Antigravity)

작성일시: 2026-05-14
참조 문서: cline-flow-auth-loop-root-cause-plan-2026-05-14.md, timeline.md, research.md, codebase (newauto_stepwise_mcp.py 등)

## 1. 근본 원인 분석에 대한 동의 및 평가

제공해주신 `cline-flow-auth-loop-root-cause-plan-2026-05-14.md`의 분석은 매우 정확합니다. 
문제의 본질은 "Flow 로그인 실패"가 아니라, **"이전 단계에서 누적된 방대한 컨텍스트(Base64 스크린샷, 긴 로그 등)를 로컬 Qwen3.5 모델(72k 로드)이 처리하지 못해 발생하는 LM Studio의 응답 실패 및 Retry 루프"**입니다. 
사용자 UI상에는 마지막 정상 메시지인 "Flow 인증 필요"만 남아 있어 마치 인증 루프처럼 보이는 착시 현상입니다. 실제로 Stepwise 상태는 `flow_generate`로 정상적으로 진입한 상태였습니다.

## 2. 코드베이스 및 워크플로우를 반영한 추가 문제점 및 개선 사항

현재 `newauto_stepwise_mcp.py` 및 전체 워크플로우 구현(`research.md`, `timeline.md` 참조)을 바탕으로 분석한 추가적인 개선점은 다음과 같습니다.

### A. Preflight (사전 검사) 하드 블록 및 자동화
*   **현재 상태:** `scripts/newauto_stepwise_mcp.py`의 `_lmstudio_context_metadata()` 함수에서 `context_target_met` 여부를 체크하고 있으며, `diagnose_runtime` 호출 시 이 정보를 제공합니다.
*   **문제점:** `continue_video_workflow`를 실행할 때, `context_target_met`가 `False`임에도 불구하고 도구 실행을 시도하여 또다시 모델 실패를 유발할 위험이 남아있습니다.
*   **개선 방안 (Preflight 강화):** `newauto_stepwise_mcp.py`의 `continue_video_workflow` 도구 내부의 최상단(또는 내부 핵심 코어 로직)에서 `context_target_met`를 강제로 체크하여, 목표 컨텍스트(131072)에 도달하지 못했다면 도구 실행을 즉시 중단(Fail-fast)하고 아래와 같은 명확한 메시지를 반환하도록 코드를 수정해야 합니다.
    > "오류: LM Studio의 모델 컨텍스트가 부족합니다 (현재 72000, 요구 131072). Flow 로그인 문제가 아닙니다. 도구를 실행하기 전에 LM Studio에서 모델을 131072 컨텍스트로 다시 로드해주세요."

### B. 컨텍스트 비대화(Base64 이미지) 원천 차단 및 OpenRouter 활용
*   **현재 상태:** Cline이 브라우저 자동화 과정에서 생성된 거대한 스크린샷 페이로드를 로컬 Qwen에게 그대로 전달하여 컨텍스트 오버플로우를 유발했습니다.
*   **개선 방안:**
    1.  `newauto_stepwise_mcp.py`의 `STEPWISE_INSTRUCTIONS` 및 `.clinerules`에 **"로컬 Qwen 모델로 Base64 이미지를 절대 직접 전송하지 말 것"**이라는 규칙을 더욱 강력하게 명시해야 합니다.
    2.  `timeline.md`에 따르면 `analyze_browser_screenshot` 도구를 통해 OpenRouter Gemma 4 Vision 기반으로 이미지를 분석하는 경로가 이미 훌륭하게 구축되어 있습니다. 브라우저 스크린샷 확인이나 Flow GUI 상태 파악이 필요한 경우 **반드시 `analyze_browser_screenshot` 도구를 사용해 텍스트 형태의 분석 결과만 로컬 컨텍스트에 포함**시키도록 강제해야 합니다.

### C. 실패한 태스크의 격리 및 Compact Task 활용 프로세스화
*   **현재 상태:** 실패가 발생한 동일 태스크(대화창)에서 계속 Retry를 누르면 비대한 컨텍스트와 함께 동일한 실패가 반복됩니다.
*   **개선 방안:** 계획서에 작성된 대로, 모델 컨텍스트 부족 오류(`Please check the LM Studio developer logs`, `load the model with a larger context length`)가 감지되면 해당 대화 창에서의 진행을 즉시 포기하고 새로운 대화 창(Compact Task)을 열어야 합니다. 운영 지침에 "이러한 오류 발생 시 Retry 금지 및 새 채팅창 생성"을 최우선 수칙으로 반영해야 합니다.

### D. Stepwise 상태와 Flow 인증 상태의 명확한 분리 리포팅
*   **현재 상태:** 워크플로우 진행 상태(`flow_generate`)와 LM Studio 인프라 상태(Context 부족)가 겹쳐서 사용자에게 모호하게 전달됩니다.
*   **개선 방안:** `diagnose_runtime` 및 `forensic_diagnose`의 반환 포맷을 개선하여, 상태를 다음과 같이 직관적으로 분리해서 명확히 리포팅하도록 합니다.
    *   **Workflow State:** `flow_generate` (Flow 로그인은 이미 완료됨)
    *   **Browser/Flow State:** `ready_for_generation`
    *   **LLM Runtime State:** `context_insufficient` (현재 72k, 목표 131k)
    이를 통해 사용자와 Agent 모두가 "인증" 문제가 아닌 "시스템(LLM) 자원" 문제임을 직관적으로 파악할 수 있습니다.

## 3. 종합 결론 및 향후 적용 계획 제안

1.  **즉각적 조치:** 계획서의 권장 명령대로 LM Studio에서 `qwen3.5-9b`를 언로드한 후, 131072 컨텍스트 파라미터(`--context-length 131072`)를 명시하여 재로드합니다. 이후 새로운 Cline 창에서 `continue_video_workflow`를 실행하여 중단된 단계부터 재개합니다.
2.  **코드 수정(가장 중요):** `scripts/newauto_stepwise_mcp.py` 파일의 `continue_video_workflow` 함수 내부에 LM Studio Context 검증 로직을 추가하여 하드 블록(Hard Block)을 구현할 것을 강력히 권장합니다.
3.  **지침 업데이트:** `.clinerules` 및 시스템 지시어에 로컬 모델로의 Base64 스크린샷 전송을 엄격히 금지하고, 비전 분석은 전적으로 OpenRouter(`analyze_browser_screenshot`)에 위임하도록 명문화합니다.

위 분석과 개선 사항이 향후 자동화 파이프라인의 견고함을 높이는 데 실질적인 도움이 되기를 바랍니다.
