# Antigravity Review: LM Studio Browser Autonomous Recovery Plan (2026-05-15)

## 📌 문서 개요
이 문서는 `lmstudio-naver-browser-autonomous-recovery-plan-2026-05-15.md` 계획서를 최신 `timeline.md` 및 `main_auto_producer.py` 작업 내역, 그리고 기존 `research.md`의 아키텍처 맥락과 교차 검증하여 도출한 **문제점 및 개선 제안**입니다.

---

## 🔍 현황 분석 (Current State vs Plan)

최근(`timeline.md` 기준) `main_auto_producer.py` 오케스트레이터의 자율성을 고도화하면서, 계획서에서 지적한 "웹 검색/브라우저 실패의 무한 루프" 문제를 일부 직접적으로 해결했습니다.
1. **검색 엔진 개편:** 구글 검색 파싱 실패 문제를 **DuckDuckGo HTML 스니펫 추출** 방식으로 변경하여, 자바스크립트나 CDP(9225 포트) 없이도 뉴스 요약이 성공하도록 만들었습니다.
2. **크래시 방지:** 존재하지 않는 도구(환각) 호출 시 크래시가 나지 않고 에이전트가 스스로 복구하도록 조치했습니다.
3. **프롬프트 강화:** 시스템 프롬프트 레벨에서 없는 브라우저 도구 사용을 억제했습니다.

즉, 계획서의 궁극적 목표인 **"포기하지 않고 텍스트 기반 폴백으로 우회하여 임무 완수"**는 오케스트레이터(`main_auto_producer.py`) 측면에서는 이미 성공적으로 작동 중입니다. 

---

## 💡 문제점 및 아키텍처 개선 제안

하지만 계획서 원안을 그대로 `scripts/newauto_stepwise_mcp.py`에 적용할 경우 다음과 같은 아키텍처 파편화 및 비효율이 발생할 수 있습니다.

### 1. 코드 파편화 (Code Duplication) 방지
- **문제점:** 현재 `main_auto_producer.py`가 내장한 `search_web` 기능(최신 DDG 스니펫 파서 적용 완료)과 `newauto_stepwise_mcp.py`가 제공하는 `search_web` 도구 사이에 로직 파편화가 발생할 우려가 있습니다.
- **개선안:** `search_web` 도구 로직을 `app/services/web_search.py`와 같은 공통 모듈로 추출해야 합니다. 오케스트레이터와 MCP 서버 양쪽 모두 이 단일 진실 공급원(Single Source of Truth)을 사용하게 하여, 향후 검색 로직이 깨질 때 한 곳만 수정하면 되도록 만들어야 합니다.

### 2. `extract_news_headlines` 전용 도구 신설의 불필요성 (Phase 2)
- **문제점:** 계획서의 Phase 2는 네이버 전용 `extract_news_headlines` 도구를 만들 것을 제안합니다. 하지만 타겟 사이트(Naver)의 DOM 구조에 하드코딩으로 의존하는 파서는 사이트 개편 시 쉽게 깨지는(Fragile) 단점이 있습니다.
- **개선안:** 최근 테스트에서 증명되었듯, 강화된 `search_web` (DDG 스니펫 추출 + html.unescape)만으로도 주요 뉴스 3개를 완벽하게 긁어오고 요약할 수 있습니다. 따라서 **특정 사이트 전용 도구(Phase 2)는 폐기하거나 후순위로 미루고, 범용 텍스트 검색 폴백의 성능을 유지하는 데 집중**하는 것이 장기적으로 훨씬 유리합니다.

### 3. `ensure_browser_ready` (CDP 복구 로직) 적용의 이원화 (Phase 1)
- **문제점:** 계획서는 MCP 클라이언트(Cline/Claude)를 위해 `newauto_stepwise_mcp.py`에 `ensure_browser_ready` 도구를 추가하려 합니다. 
- **개선안:** 전적으로 동의합니다. Playwright와 Browser-use가 모두 9225 포트 CDP에 의존하므로, MCP 서버 단에서 `start-cline-browser.cmd`를 통해 리스너를 살려내는 도구는 훌륭한 자율 복구 수단입니다. 단, 이를 오케스트레이터(`main_auto_producer.py`)가 브라우저 작업으로 확장을 시도할 때도 동일하게 호출할 수 있도록 설계해야 합니다.

### 4. 계층적 실패 분류기(Universal Failure Classifier)의 구현 방식
- **개선안:** 계획서에 제시된 `cdp_endpoint_unavailable`, `dom_extraction_failed` 등의 실패 클래스는 에이전트의 인지 능력을 크게 높일 것입니다. 이를 프롬프트에 글로만 적을 것이 아니라, MCP 도구의 실제 반환값(Return Schema)을 JSON 구조화하여 `{"status": "error", "failure_class": "...", "next_action_suggestion": "..."}` 형태로 반환하도록 도구 래퍼를 수정하는 것이 가장 확실한 방법입니다.

### 5. OpenRouter 에스컬레이션 조건 명확화
- **개선안:** 3회 반복 실패 시 OpenRouter로 넘기는 조건은 매우 합리적입니다. 이를 강제하기 위해 에이전트 루프나 도구 관리자 측에 `error_count` 상태를 추적하는 경량 데코레이터를 붙이는 방안을 검토해야 합니다. 단순히 `.clinerules`나 지시문(Instructions)에 의존하면 로컬 LLM이 이를 무시하고 무한 루프에 빠질 위험이 여전히 존재합니다.

---

## 🎯 결론 및 Next Action

계획서의 근본적인 진단과 방향성(로컬 진단 -> 브라우저 수리 -> 텍스트 폴백 -> OpenRouter 헬프)은 매우 정확하며 훌륭합니다. 

다만, 구현 단계에서 **"새로운 도구를 계속 늘리기보다는, 이미 입증된 강력한 범용 폴백(최신 `search_web`)을 오케스트레이터와 MCP 서버 간에 공통화"**하는 방향으로 선회하는 것을 제안합니다.

1. **최우선 진행 (P0):** `newauto_stepwise_mcp.py`의 `search_web` 로직을 최근 수리한 DuckDuckGo 스니펫 파서 로직으로 동기화(또는 모듈 분리).
2. **진행 (P0):** `ensure_browser_ready` 도구를 MCP 서버에 추가 및 프롬프트 패치.
3. **취소/보류 (Phase 2):** `extract_news_headlines` 도구는 불필요하므로 제거.
4. **구조화 (P1):** 실패 원인을 문자열 대신 정형화된 JSON 에러 클래스로 반환하도록 도구 인터페이스 정비.
