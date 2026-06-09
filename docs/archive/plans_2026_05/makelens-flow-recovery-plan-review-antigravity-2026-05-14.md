# MakeLens Flow vs Cline+Qwen 복구 계획서에 대한 Antigravity 검토 의견

작성일: 2026-05-14
대상 문서: `makelens-flow-vs-cline-qwen-recovery-plan-2026-05-14.md`
관련 자료: `research.md`, `timeline.md`, `.clinerules`, 워크플로우 관련 코드베이스

## 1. 총평

제안된 **"영상 workflow 한정 Cline/Qwen 역할 축소 및 MakeLens 방식의 Worker 이식"** 계획은 현재 newauto 시스템이 겪고 있는 고질적인 불안정성을 해결하기 위한 핵심적이고 정확한 진단입니다. 

LLM(Qwen)의 컨텍스트 창이 길어짐에 따라 발생하는 할루시네이션(예: 바이너리 파일인 `/output`을 JSON으로 파싱하려는 시도 등)이나 상태 판단 오류를 시스템적으로 원천 차단하겠다는 접근 방식은, 오퍼레이터(Operator) 중심의 자동화에서 매우 바람직한 방향입니다.

## 2. 세부 계획에 대한 검토 및 동의

### P0. 영상 workflow 한정 Cline/Qwen 역할 축소
- **의견:** 전적으로 동의합니다. `.clinerules`를 확인해보면 이미 `/output` 파싱 금지, 3회 실패 시 OpenRouter 호출 등 수많은 방어적 프롬프트가 존재합니다. 하지만 프롬프트에 의존하는 제어는 완벽할 수 없습니다. LLM을 '제어자'에서 '모니터링 및 요약자'로 격하시키는 것이 에이전트 파이프라인 안정화의 근본적인 해법입니다.

### P1 & P3. MakeLens Flow runner 이식 및 Worker job 승격
- **의견:** 현재 `newauto_stepwise_mcp.py`와 `flow_browser_automation.py`의 구조는 1문장 생성 후 LLM에게 상태를 반환하여 다음 행동을 결정하게 합니다. 이는 LLM을 매 단계 개입하게 만들어 타임아웃과 오판의 위험을 높입니다. Flow 이미지 생성을 Background Worker에 위임하여 "알아서 끝까지" 처리하도록 분리하는 P3 계획은 반드시 선행되어야 합니다.

### P2. Run-level Operator Summary 추가 (`operator_summary.json`)
- **의견:** 가장 훌륭한 개선 포인트 중 하나입니다. LLM이 `/status`, `/render-report` 등을 개별적으로 찔러보며 상태를 추론하는 것은 할루시네이션의 온상입니다. `operator_summary.json`이라는 단일 진실 공급원(Single Source of Truth)을 제공함으로써 LLM은 복잡한 추론 없이 명확한 상태를 읽어 사용자에게 전달하기만 하면 됩니다.

### P4, P5, P6. 정규화 계층 강화, Fallback, Health Guard
- **의견:** `timeline.md`를 보면 이미 시스템이 고도화되어 있으나, 브라우저 프로세스 락(lock)이나 포트 충돌 등의 인프라 이슈가 간헐적으로 발생합니다. 작업을 시작하기 전에 `check_flow_browser_health.py`를 통해 CDP 포트와 프로필을 선제 검사(Health Guard)하는 것은 실패 비용(시간 및 리소스 낭비)을 극적으로 줄여줄 것입니다.

## 3. 추가 개선 및 반영 제안

1. **`.clinerules` 및 MCP Tool의 대폭 간소화:**
   - `operator_summary.json` (P2)이 도입되면, LLM이 상태를 알기 위해 여러 엔드포인트를 호출할 필요가 없어집니다.
   - 복잡한 상태 확인용 툴들을 캡슐화하거나 MCP 노출을 줄이고, 오직 `get_operator_summary` 형태의 단일 상태 확인 툴만 노출하여 LLM의 고민 거리를 없애야 합니다. `.clinerules`의 장황한 예외 처리 조항들도 이로 인해 간소화될 수 있습니다.

2. **OpenRouter (Subagent) 개입 타이밍의 재조정:**
   - 현행 규칙상 3회 실패 시 무조건 OpenRouter를 호출하게 되어 있습니다.
   - P3(Worker 승격)와 P5(Fallback chain)가 도입되면, Worker 자체가 내장된 로직으로 재시도와 폴백을 처리하게 됩니다. 따라서 OpenRouter의 개입은 워크플로우 진행 중의 사소한 실패가 아니라, Worker 자체가 다운되거나 Health Guard가 심각한 인프라 문제를 보고했을 때 등 **"운영 장애(Operational Blocker)"** 레벨로 제한하는 것이 좋겠습니다.

3. **Stepwise 진행과 Worker의 조화:**
   - 사용자가 '다음' 혹은 '진행'을 지시했을 때, 단순히 1스텝만 이동하는 것이 아니라 **"다음 수동 개입이 필요한 구간(예: 렌더링 완료 또는 치명적 에러 발생)까지 논스톱(Non-stop)으로 전진"**하도록 `continue_video_workflow`의 역할을 변경하는 것을 권장합니다.

## 4. 결론

제안해주신 계획(`makelens-flow-vs-cline-qwen-recovery-plan-2026-05-14.md`)은 새로운 컴포넌트를 무리하게 추가하는 것이 아니라, MakeLens에서 이미 검증된 안정적인 워커(Worker) 패턴을 newauto로 가져와 LLM의 과부하를 덜어내는 훌륭한 아키텍처 리팩토링입니다. 우선순위대로 P0, P2, P3부터 진행하시면 즉각적인 안정성 향상을 체감하실 수 있을 것입니다.
