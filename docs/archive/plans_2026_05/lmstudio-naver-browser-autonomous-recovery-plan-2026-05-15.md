# LM Studio Browser/Search Autonomous Recovery Plan

작성일: 2026-05-15 KST

## 목표

LM Studio의 로컬 LLM이 모든 웹검색/브라우저 작업에서 도구를 제대로 선택하고 실행하게 만든다. "Naver News 접속 -> 메인 뉴스 3개 링크 추출 -> 요약"은 대표 사례일 뿐이며, 실제 목표는 검색, 문서 확인, 동적 페이지 조작, GUI 상태 분석, 다운로드, 로그인/권한 대기 같은 모든 웹 작업에서 사용자에게 곧바로 "다른 방법을 알려달라"고 되묻지 않고, Codex/Claude Code처럼 로컬 상태를 진단하고, 대체 경로를 선택하고, 필요하면 OpenRouter 보조 에이전트까지 호출한 뒤 실행을 계속하게 만드는 것이다.

## Antigravity Review 반영 결정

검토 문서 `docs/archive/reviews/antigravity-plan-review-2026-05-15.md`의 결론을 반영한다. 기존 계획의 큰 방향은 유지하되, 구현 우선순위는 "새 전용 도구를 계속 늘리기"가 아니라 "검증된 공통 검색/브라우저 진단 기반을 단일화하고, 도구 반환값을 구조화해서 로컬 LLM이 무시하기 어렵게 만들기"로 조정한다.

반영 사항:

- `search_web` 로직은 `newauto_stepwise_mcp.py`와 `main_auto_producer.py`에 중복 구현하지 않는다.
- DuckDuckGo HTML parser, snippet 추출, `html.unescape`, dedupe 로직은 공통 모듈 `app/services/web_search.py`로 분리한다.
- `extract_news_headlines` 같은 사이트별 전용 도구는 P1/P2로 보류하거나 제거한다. 우선은 범용 `search_web`와 URL read helper를 강화한다.
- `ensure_browser_ready`는 유지한다. Playwright와 browser-use가 모두 CDP 9225에 의존하므로 MCP 내부 복구 도구로 가치가 크다.
- 실패 원인 class는 프롬프트 문장에만 두지 않고 MCP 도구 반환값의 JSON schema로 강제한다.
- "3회 실패 후 OpenRouter"는 instruction만 믿지 않고, 가능하면 도구 관리자/상태 파일에서 `error_count` 또는 `recovery_attempts`를 추적한다.

## 확인된 현재 원인

이번 실패의 직접 원인은 Naver 페이지 자체가 아니라 브라우저 MCP가 붙는 CDP endpoint가 준비되어 있지 않은 것이다.

근거:

- `.lmstudio/mcp.json`에서 `playwright`와 `browser-use` 모두 `http://127.0.0.1:9225` CDP에 붙도록 설정되어 있다.
- 실제 점검 결과 `Get-NetTCPConnection -LocalPort 9225`는 리스너를 찾지 못했다.
- `Invoke-RestMethod http://127.0.0.1:9225/json/version`은 timeout이었다.
- Chrome/Edge 프로세스는 떠 있었지만 원격 디버깅 포트 9225가 살아 있는 프로세스는 확인되지 않았다.
- 따라서 `browser_navigate`가 `ECONNREFUSED` 또는 연결 실패로 끝나는 것은 정상적인 증상이다.

이미 존재하는 복구 자산:

- `scripts/start_cline_browser.ps1`: 9225 포트의 Chrome DevTools endpoint를 띄우는 스크립트.
- `start-cline-browser.cmd`: 위 PowerShell 스크립트 실행용 래퍼.
- `scripts/newauto_stepwise_mcp.py`: `search_web`, `run_powershell`, `ask_openrouter_subagent`, `analyze_browser_screenshot` 등을 노출하는 단계형 MCP.
- `scripts/openrouter_subagent_harness.py`: OpenRouter API 직접 호출, free model fallback, budget guard, secret redaction, `--task-stdin` 지원.
- `timeline.md`: 이미 "없는 브라우저 도구 호출 금지", "DuckDuckGo HTML search fallback", "unknown action으로 죽지 않고 복구" 방향이 기록되어 있다.

## 실패한 기존 워크플로우의 문제

기존 응답은 다음 지점에서 끊겼다.

1. 브라우저 접속 실패를 네트워크/Naver 문제처럼 처리했다.
2. CDP endpoint, MCP 설정, 로컬 브라우저 프로세스 상태를 확인하지 않았다.
3. 이미 있는 `start-cline-browser.cmd` 또는 `run_powershell` 복구 경로를 쓰지 않았다.
4. 브라우저가 막혔을 때 `search_web` 같은 텍스트 우선 fallback으로 전환하지 않았다.
5. 반복 실패 시 `ask_openrouter_subagent`를 호출하는 규칙을 실제 작업에 적용하지 않았다.

더 큰 구조적 문제:

- 도구가 많을수록 로컬 LLM이 "무엇을 먼저 써야 하는지"가 아니라 "도구 이름을 맞히는 문제"로 착각한다.
- Playwright, browser-use, computer-use, search_web, run_powershell, OpenRouter가 역할별로 정렬되어 있지 않으면 실패 후 같은 도구만 반복하거나 곧바로 포기한다.
- 브라우저 오류를 페이지 오류, 네트워크 오류, 권한 오류, MCP 오류, CDP 오류로 분류하지 않는다.
- "도구 호출 실패"와 "목표 실패"를 구분하지 않는다. 브라우저가 실패해도 HTTP/search로 목표를 달성할 수 있는 경우가 많다.
- 로컬 LLM은 실패 원인을 추정 문장으로 채우려는 경향이 있어, 실제 상태 확인 명령을 강제해야 한다.
- OpenRouter 연결이 있어도 "언제, 어떤 패킷으로, 어떤 결과를 기대하며" 호출해야 하는지 명확하지 않아 활용하지 못한다.

Antigravity review에서 추가로 지적한 구현 위험:

- `main_auto_producer.py`에 이미 개선된 DuckDuckGo HTML 검색 로직이 있는데, `newauto_stepwise_mcp.py`에 별도 검색 로직을 두면 drift가 생긴다.
- Naver 전용 추출기는 DOM 구조 변경에 약하고, 이번 문제의 본질인 "범용 웹 도구 선택 실패"를 해결하지 못한다.
- 실패 분류를 instruction에만 적으면 로컬 LLM이 무시할 수 있으므로 도구 반환 schema에 `failure_class`, `next_action_suggestion`을 포함해야 한다.

## 목표 동작

웹검색/브라우저 요청을 받으면 로컬 LLM은 아래 순서로 움직여야 한다.

1. 최신 정보 요청으로 분류한다.
2. 브라우저가 꼭 필요한지 판단한다.
   - 단순 뉴스 링크/헤드라인/요약이면 `search_web` 또는 HTTP fetch 우선.
   - 로그인, 동적 UI, 캡처, 클릭이 필요하면 Playwright/browser-use 사용.
3. 브라우저 도구 사용 전 CDP 헬스체크를 한다.
4. 9225가 죽어 있으면 `start-cline-browser.cmd` 또는 `scripts/start_cline_browser.ps1`를 실행한다.
5. 그래도 브라우저가 안 되면 텍스트 fallback으로 뉴스 검색/추출을 진행한다.
6. 같은 blocker가 3회 유지되면 `ask_openrouter_subagent(mode="debug")`로 원인/다음 행동을 묻는다.
7. 사용자에게 질문하기 전에 최소 1개의 실행 가능한 대체 경로를 직접 시도한다.

## General Web Tool Hierarchy

로컬 LLM은 웹 작업을 아래 계층으로 처리해야 한다.

### Tier 0. Intent 분류

사용자 요청을 먼저 아래 중 하나로 분류한다.

- `search`: 최신 정보, 뉴스, 문서, 제품, 가격, 일정, 링크 찾기.
- `read`: 특정 URL/문서/기사/페이지 내용 추출.
- `interact`: 버튼 클릭, 폼 입력, 페이지 이동, 로그인 후 작업.
- `inspect_ui`: 스크린샷/차트/브라우저 화면 상태 해석.
- `download`: 파일 다운로드, artifact 확인.
- `workflow`: newauto/Flow/HPSL 같은 내부 작업 실행.

분류 결과는 내부 판단으로만 쓰고, 사용자에게 장황하게 노출하지 않는다.

### Tier 1. Text-first 도구

정적 정보나 링크 추출은 브라우저보다 텍스트 도구가 우선이다.

사용:

- `newauto-stepwise.search_web`
- 공통 모듈 `app/services/web_search.py`를 사용하는 검색 wrapper
- 직접 HTTP fetch가 가능한 경우 `run_powershell`의 `Invoke-WebRequest` 또는 Python 표준 라이브러리
- 사이트맵/RSS/API가 있으면 그 경로

적합한 작업:

- "오늘 주요 뉴스 찾아줘"
- "이 라이브러리 최신 문서 확인해줘"
- "이 URL 기사 요약해줘"
- "상위 3개 링크와 제목 뽑아줘"

규칙:

- 검색/기사 요약은 처음부터 GUI 클릭으로 가지 않는다.
- 검색 결과에는 제목, URL, snippet, 검색 시각을 남긴다.
- 결과가 부족하거나 동적 렌더링이 필요할 때만 Playwright로 올라간다.
- `search_web` 구현은 한 곳만 둔다. MCP, autonomous producer, 테스트는 같은 공통 서비스를 호출한다.

### Tier 2. Playwright MCP

DOM 추출, 페이지 이동, selector 기반 클릭에는 Playwright가 기본 브라우저 도구다.

사용:

- `browser_navigate`
- `browser_snapshot`
- `browser_evaluate`
- 기타 실제로 노출된 Playwright MCP 도구

적합한 작업:

- 페이지 DOM에서 기사 목록 추출
- 버튼/탭 클릭 후 결과 확인
- SPA 페이지의 렌더링 결과 확인
- 다운로드 버튼 클릭 전 상태 확인

규칙:

- Playwright 사용 전 CDP endpoint를 확인한다.
- `browser_extract_content`처럼 노출되지 않은 도구를 invent하지 않는다.
- `browser_snapshot`/`browser_evaluate`로 텍스트를 먼저 본다.
- 스크린샷은 DOM으로 판단할 수 없을 때만 쓴다.

### Tier 3. browser-use MCP

browser-use는 복잡한 다단계 탐색이나 selector가 불명확할 때 쓰는 보조 자동화다.

적합한 작업:

- 검색창 입력, 결과 클릭, 여러 페이지 탐색
- Playwright selector 방식이 2회 실패한 경우
- 페이지 구조가 자주 바뀌거나 사람이 하는 탐색에 가까운 작업

규칙:

- Playwright가 가능한 간단 작업에 browser-use를 먼저 쓰지 않는다.
- browser-use도 같은 CDP 9225에 의존하므로 CDP가 죽어 있으면 먼저 브라우저를 복구한다.
- browser-use 실패 결과는 "브라우저 목표 실패"가 아니라 "해당 자동화 경로 실패"로 기록하고, search/HTTP/Playwright fallback을 검토한다.

### Tier 4. Screenshot/Vision

화면의 시각 상태가 중요한 경우에만 screenshot 분석을 쓴다.

사용:

- `analyze_browser_screenshot`
- OpenRouter Vision fallback chain

적합한 작업:

- CAPTCHA, 팝업, 로그인 요구, 권한 화면, 비정상 UI
- DOM에는 없지만 화면에 보이는 오류
- 그래프/차트/이미지 중심 페이지

규칙:

- 전체 브라우저 프로필, 쿠키, 토큰은 OpenRouter로 보내지 않는다.
- screenshot은 필요한 범위만 사용한다.
- Vision 결과는 advisory로만 보고, 로컬 DOM/클릭/상태 확인으로 검증한다.

### Tier 5. run_powershell / Local Repair

도구 자체가 죽었거나 환경이 깨졌으면 shell 진단/복구가 우선이다.

사용 예:

```powershell
Invoke-RestMethod http://127.0.0.1:9225/json/version
powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\petbl\newauto\scripts\start_cline_browser.ps1
Get-NetTCPConnection -LocalPort 9225
```

규칙:

- ECONNREFUSED, timeout, CDP 연결 실패는 사이트 문제가 아니라 로컬 브라우저 런타임 문제로 먼저 본다.
- 복구 명령 실행 후 같은 헬스체크를 재실행한다.
- 복구가 실패해도 목표가 text/search로 가능하면 계속 진행한다.

### Tier 6. OpenRouter Advisory

OpenRouter는 실행자가 아니라 보조 진단가다.

사용 조건:

- 같은 blocker가 로컬에서 3회 이상 유지됨.
- 실패 원인이 browser/tool/runtime/site 중 어디인지 불명확함.
- 다음 행동 선택에 외부 추론이 도움이 됨.
- 로컬 LLM이 반복 루프에 빠짐.

규칙:

- OpenRouter에 full log/full repo/secrets를 보내지 않는다.
- 현재 목표, blocker, 로컬 facts, 시도한 3개 행동, 필요한 결정을 짧게 보낸다.
- 응답은 로컬 도구로 검증한 뒤 적용한다.

## Universal Failure Classifier

웹/브라우저 실패는 먼저 class로 나눈다.

```text
cdp_endpoint_unavailable:
  127.0.0.1:9225 /json/version 실패, TCP listener 없음.
  조치: start_cline_browser.ps1 실행 후 재검사.

mcp_tool_unavailable:
  도구 이름이 없거나 schema가 다름.
  조치: 실제 노출 도구 확인, 대체 도구 사용.

site_unreachable:
  HTTP DNS/TLS/timeout이 text fetch와 browser 모두에서 재현됨.
  조치: search fallback 또는 사용자에게 사이트 접근 문제 보고.

site_blocks_automation:
  브라우저는 살아 있으나 bot check, CAPTCHA, 로그인, 권한 화면.
  조치: screenshot/vision으로 상태 확인, 사용자 조치 필요 시 구체적으로 안내.

dom_extraction_failed:
  페이지는 열렸지만 selector/구조 문제로 추출 실패.
  조치: browser_snapshot, browser_evaluate, broader selectors, search fallback.

browser_use_navigation_failed:
  browser-use의 agentic 탐색 실패.
  조치: Playwright/HTTP/search로 역전환.

local_runtime_failed:
  Python/node/npx/uv/Chrome dependency 문제.
  조치: run_powershell로 버전/경로/프로세스 확인.

goal_completed_via_fallback:
  원래 도구는 실패했지만 검색/HTTP 등으로 목표 완료.
  조치: 사용한 fallback을 짧게 명시하고 결과 제공.
```

로컬 LLM은 실패 class를 정하지 못하면 `unknown_browser_failure`로 두고, 바로 사용자에게 질문하지 말고 `diagnose_runtime` 또는 OpenRouter debug packet으로 넘어간다.

도구 반환 schema는 가능한 한 아래 형태를 따른다.

```json
{
  "ok": false,
  "tool": "ensure_browser_ready",
  "failure_class": "cdp_endpoint_unavailable",
  "message": "CDP endpoint did not respond at http://127.0.0.1:9225/json/version",
  "attempted_actions": [
    "checked_cdp_json_version",
    "started_start_cline_browser_cmd",
    "rechecked_cdp_json_version"
  ],
  "recovery_attempt_count": 2,
  "next_action_suggestion": "use_search_web_or_http_request",
  "openrouter_escalation_recommended": false
}
```

3회 이상 같은 blocker가 유지되면:

```json
{
  "ok": false,
  "failure_class": "cdp_endpoint_unavailable",
  "recovery_attempt_count": 3,
  "next_action_suggestion": "ask_openrouter_subagent",
  "openrouter_escalation_recommended": true
}
```

## Agent Behavior Contract

로컬 LLM은 모든 웹 작업에서 아래 계약을 지킨다.

1. 도구 실패를 사용자 책임으로 넘기지 않는다.
2. 사용할 수 있는 도구가 있으면 먼저 실행한다.
3. 같은 도구를 같은 인자로 2회 이상 반복하지 않는다.
4. 실패 후에는 상태 확인 또는 다른 계층의 도구로 전환한다.
5. 브라우저가 실패해도 목표가 검색/HTTP로 가능하면 계속한다.
6. 도구 이름을 invent하지 않는다.
7. "접속이 안 됩니다"라고 말하기 전에 로컬 CDP, MCP, HTTP/search 중 최소 2개 경로를 확인한다.
8. 사용자의 원래 목표를 잊지 않는다. 목표는 "브라우저 열기"가 아니라 "정보 추출/요약/작업 완료"다.
9. 막히면 OpenRouter 연결을 실제로 활용한다.
10. 최종 답변에는 결과, 사용한 경로, 남은 한계만 짧게 말한다.

## Prompt/Instruction Patch

`.clinerules`, LM Studio custom instruction, 또는 `STEPWISE_INSTRUCTIONS`에 아래 블록을 추가한다.

```text
## Universal Web/Browser Tool Policy

You are an autonomous local web operator, not a text-only chatbot.

For every web/search/browser task:
1. Classify the task as search, read, interact, inspect_ui, download, or workflow.
2. Prefer text-first tools for search/read tasks: search_web, HTTP fetch, RSS/API.
3. Use Playwright MCP for DOM extraction, navigation, selector clicks, and page state.
4. Use browser-use MCP only for multi-step exploratory browsing or when Playwright fails twice.
5. Before blaming a website, check whether the local browser/CDP endpoint is alive.
6. If Playwright/browser-use fails with ECONNREFUSED, timeout, or connection refused, check http://127.0.0.1:9225/json/version and start C:\Users\petbl\newauto\start-cline-browser.cmd if needed.
7. If browser repair fails but the user goal can be completed through search_web or HTTP fetch, continue through that fallback.
8. Do not ask the user for an alternate source until local browser repair and text fallback both failed.
9. Do not invent unavailable tool names. Use only visible tools.
10. After 3 local recovery attempts against the same blocker, call ask_openrouter_subagent(mode="debug") with the goal, blocker, facts, attempts, and next decision needed.
11. OpenRouter is advisory only. Verify its recommendation locally before acting.
12. Never send secrets, cookies, tokens, full browser profiles, full logs, or full repo dumps to OpenRouter.
13. Keep the user's goal primary. Browser navigation is a means, not the goal.
```

## 구현 계획

### Phase 0. 공통 검색 모듈 분리

최우선 구현은 검색 로직 단일화다.

추가/정리할 파일:

```text
app/services/web_search.py
tests/test_web_search.py
```

공통 모듈 책임:

- DuckDuckGo HTML 검색 요청.
- `result__a`, `result__snippet` parser.
- redirect URL `uddg` 정규화.
- `html.unescape` 적용.
- 중복 URL 제거.
- 결과 schema 통일.

공통 반환 예:

```json
{
  "ok": true,
  "query": "site:news.naver.com 오늘 주요 뉴스",
  "source_method": "duckduckgo_html",
  "results": [
    {
      "title": "...",
      "url": "https://news.naver.com/...",
      "snippet": "..."
    }
  ]
}
```

적용 대상:

- `scripts/newauto_stepwise_mcp.py`의 `search_web`.
- `scripts/main_auto_producer.py`의 autonomous search.
- 향후 URL read/search helper.

이렇게 해야 검색 parser가 바뀔 때 한 곳만 수정하면 된다.

### Phase 1. Browser Readiness Tool 추가

`scripts/newauto_stepwise_mcp.py`에 브라우저 상태를 한 번에 점검/복구하는 도구를 추가한다. 다만 CDP 진단 자체는 향후 `app/services/browser_runtime.py` 같은 공통 모듈로 분리할 수 있게 작성한다.

권장 도구명:

```text
ensure_browser_ready(url="about:blank", cdp_url="http://127.0.0.1:9225")
```

동작:

- `GET /json/version`으로 CDP endpoint 확인.
- 실패하면 `start-cline-browser.cmd` 실행.
- 재시도 후 endpoint가 살아나면 ok 반환.
- 실패하면 `browser_unavailable`과 원인, 다음 fallback 제안 반환.

반환 예:

```json
{
  "ok": false,
  "cdp_url": "http://127.0.0.1:9225",
  "failure_class": "cdp_endpoint_unavailable",
  "attempted_repair": "start-cline-browser.cmd",
  "next_action": "use_search_web_or_http_request"
}
```

### Phase 2. 범용 URL Read/Search Helper 추가

Antigravity review 반영에 따라 Naver 전용 `extract_news_headlines`는 보류한다. 대신 범용 URL/read/search helper를 추가한다.

권장 도구명:

```text
read_url_or_search(query_or_url="", count=3, prefer_domain="")
```

우선순위:

1. URL이면 HTTP fetch/readability-style text extraction.
2. query면 공통 `web_search.search_web`.
3. `prefer_domain`이 있으면 해당 도메인 결과를 우선 정렬.
4. 브라우저가 준비된 경우에만 Playwright DOM 추출.

주의:

- 사이트별 DOM 구조를 하드코딩하지 않는다.
- Naver 뉴스도 `prefer_domain="news.naver.com"` 형태로 처리한다.
- 결과에는 `source_method`, `retrieved_at`, `url`, `title`, `snippet`을 포함한다.

Naver 전용 도구는 다음 조건이 충족될 때만 재검토한다.

- 범용 검색/URL helper로 목표 달성이 반복적으로 실패한다.
- Naver 뉴스 구조가 안정적으로 파악된다.
- 테스트 fixture와 fallback이 함께 준비된다.

### Phase 3. Instructions 강화

`STEPWISE_INSTRUCTIONS`에 아래 규칙을 추가한다.

```text
For web/news tasks:
- Do not assume browser_navigate failure means the target site is down.
- First check the CDP endpoint when Playwright/browser-use fails with ECONNREFUSED, timeout, or connection refused.
- If CDP is unavailable, call run_powershell to start C:\Users\petbl\newauto\start-cline-browser.cmd or use ensure_browser_ready when available.
- For headline/link/summary tasks, prefer search_web or HTTP text extraction before GUI clicking.
- If browser remains unavailable after repair, continue through search_web/HTTP fallback and cite that browser fallback was used.
- Do not ask the user for another source until browser repair and text fallback have both failed.
```

### Phase 4. OpenRouter Escalation 연결

같은 blocker가 3회 반복되면 로컬 trial-and-error를 멈추고 다음 형태로 호출한다.

```text
ask_openrouter_subagent(
  mode="debug",
  task="
CURRENT_GOAL: Naver News main page에서 top 3 headlines and links 추출 후 요약.
BLOCKER: Playwright/browser-use cannot connect to CDP endpoint http://127.0.0.1:9225.
LOCAL_FACTS:
- mcp.json points playwright/browser-use to 127.0.0.1:9225
- /json/version timed out
- no TCP listener found on local port 9225
- start_cline_browser.ps1 exists
ATTEMPTS:
1. browser_navigate failed
2. browser_get_state failed or stale
3. CDP health check failed
QUESTION: Which local repair or fallback should be executed next?
"
)
```

OpenRouter 호출 원칙:

- 긴 한국어 프롬프트는 shell `--task "..."`로 넘기지 않는다.
- MCP `ask_openrouter_subagent`를 우선 사용한다.
- shell fallback이 필요하면 `--task-stdin` 또는 `--task-file`만 사용한다.
- OpenRouter 응답은 advisory로만 쓰고, 실제 실행/검증은 로컬 도구로 한다.

구현 보강:

- `storage/agent_memory` 또는 MCP state에 최근 blocker별 `recovery_attempt_count`를 저장한다.
- key는 `task_kind + failure_class + normalized_target` 형태로 둔다.
- 성공 또는 다른 failure_class로 전환되면 count를 reset한다.
- count가 3 이상이면 도구 반환값에 `openrouter_escalation_recommended=true`를 넣는다.

### Phase 5. 검증

필수 smoke:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\petbl\newauto\scripts\start_cline_browser.ps1
Invoke-RestMethod http://127.0.0.1:9225/json/version
```

MCP smoke:

```powershell
C:\Users\petbl\local-rag\.venv\Scripts\python.exe -m py_compile scripts\newauto_stepwise_mcp.py scripts\openrouter_subagent_harness.py
C:\Users\petbl\local-rag\.venv\Scripts\python.exe scripts\openrouter_subagent_harness.py --budget-status --json-output
```

뉴스 작업 smoke:

```text
네이버 뉴스 메인에서 주요뉴스 3개 제목과 링크를 뽑고 각각 한 문장으로 요약해줘.
```

기대 결과:

- 브라우저가 살아 있으면 DOM 기반 추출.
- 브라우저가 죽어 있으면 자동으로 CDP 복구 시도.
- 복구가 안 되면 `search_web`/HTTP fallback으로 3개 링크와 요약 제공.
- 실패 원인 설명에는 CDP 상태, 시도한 복구, 사용한 fallback이 포함된다.

일반 웹 작업 smoke:

```text
1. "오늘 OpenAI API 최신 변경사항 찾아서 링크 3개로 요약해줘."
   기대: search_web/공식 문서 우선, 브라우저가 필요하면 Playwright.

2. "이 URL 본문에서 핵심 주장만 뽑아줘: <URL>"
   기대: HTTP fetch 우선, 실패 시 Playwright, 그래도 실패 시 search fallback.

3. "이 사이트에서 검색창에 bitcoin 입력하고 첫 결과 열어줘."
   기대: CDP 확인 -> Playwright -> 실패 2회 후 browser-use.

4. "브라우저 화면이 왜 막혔는지 봐줘."
   기대: DOM/snapshot 확인 -> 필요 시 screenshot/vision.

5. "브라우저 도구가 ECONNREFUSED로 실패했어."
   기대: Naver/사이트 문제가 아니라 9225 CDP 진단, start_cline_browser 실행, 재검사.
```

## 우선순위

P0:

- `app/services/web_search.py` 공통 모듈 추가.
- `newauto_stepwise_mcp.py`와 `main_auto_producer.py`가 같은 검색 서비스를 쓰도록 정리.
- `ensure_browser_ready` 추가.
- Naver/news 작업 instruction 추가.
- universal web/browser tool policy를 `STEPWISE_INSTRUCTIONS`와 `.clinerules`에 반영.
- 실패 class를 반환하는 browser diagnostic helper 추가.
- 도구 반환 schema에 `failure_class`, `next_action_suggestion`, `recovery_attempt_count`, `openrouter_escalation_recommended` 포함.
- CDP 실패 시 `start-cline-browser.cmd` 실행 경로를 LM Studio가 알도록 문서/프롬프트 반영.

P1:

- 범용 `read_url_or_search` helper 추가.
- 관련 단위 테스트 추가.
- Playwright 실패 2회 후 browser-use fallback을 상태 기반으로 강제.
- OpenRouter escalation용 blocker attempt counter 추가.

P2:

- Naver 전용 `extract_news_headlines` 필요성 재검토. 기본은 보류.
- `operator_status`에 CDP 9225 상태와 브라우저 프로세스 요약 포함.
- `timeline.md` 인코딩 복구 또는 UTF-8 정상 문서로 재작성.
- agent_eval_smoke에 웹 도구 선택 시나리오 추가.

## 성공 기준

- 로컬 LLM이 `browser_navigate` 실패 직후 사용자에게 대체 방법을 묻지 않는다.
- CDP endpoint 원인을 먼저 진단한다.
- 가능한 경우 스스로 브라우저를 띄운다.
- 브라우저가 안 되면 텍스트 검색/HTTP fallback으로 뉴스 요약 작업을 완료한다.
- 3회 이상 막히면 OpenRouter 보조 분석을 호출하고, 그 결과를 로컬 실행 계획으로 바꾼다.
- 모든 웹 작업에서 search/HTTP, Playwright, browser-use, screenshot/vision, shell repair, OpenRouter advisory의 계층을 지킨다.
- 목표가 달성 가능한 경우 특정 도구 실패만으로 작업을 포기하지 않는다.
- 검색 로직은 공통 모듈 한 곳에서 관리되어 autonomous producer와 MCP 결과가 서로 어긋나지 않는다.
- 실패 class와 다음 행동 제안은 자연어 추정이 아니라 구조화된 도구 반환값으로 전달된다.

## 구현 진행 상황

2026-05-15 반영 완료:

- `app/services/web_search.py` 추가: DuckDuckGo HTML 검색, snippet 추출, URL 정규화, dedupe, 구조화된 실패 응답.
- `app/services/web_read.py` 추가: URL이면 `source_fetch.analyze_source_url`, 검색어면 공통 `search_web`, `prefer_domain` 우선 정렬.
- `scripts/newauto_stepwise_mcp.py` 업데이트:
  - `search_web` 공통 모듈 연결.
  - `read_url_or_search` 도구 추가.
  - `ensure_browser_ready` 도구 추가.
  - CDP 9225 실패 class, recovery attempt count, OpenRouter escalation flag 반환.
  - universal web/browser tool policy instruction 추가.
- `scripts/main_auto_producer.py` 업데이트:
  - `search_web` 공통 모듈 연결.
  - 브라우저/CDP 실패 시 사이트 탓 전에 로컬 런타임을 진단하도록 instruction 보강.
- `app/services/source_research.py` 업데이트: 기존 DuckDuckGo regex parser를 공통 parser로 교체.
- `.clinerules` 업데이트: search/read/interact/inspect_ui/download/workflow 분류, text-first, CDP 9225 복구, browser-use fallback, text fallback 규칙 추가.
- `scripts/lmstudio_openclaw_operator_mcp.py` 업데이트: `operator_status`에 `cdp_9225` JSON 상태 포함.
- 테스트 추가:
  - `tests/test_web_search.py`
  - `tests/test_web_read.py`

검증 완료:

- `python -m pytest tests/test_web_search.py tests/test_web_read.py tests/test_source_research.py tests/test_source_fetch.py -q` -> 17 passed.
- `py_compile` 통과.
- `git diff --check` 통과.
- live `search_web`/`read_url_or_search` smoke 통과.
- operator status smoke 통과. 현재 실제 CDP 9225는 `cdp_endpoint_unavailable`로 보고되며, 다음 행동 제안은 `start-cline-browser.cmd` 또는 text/search fallback이다.

남은 후속 작업:

- LM Studio/Cline을 재시작하거나 MCP reconnect 후 새 도구 노출 확인.
- Playwright 실패 2회 후 browser-use fallback을 실제 MCP 호출 기록 기반으로 더 엄격히 자동화.
- 필요 시 `read_url_or_search`를 `main_auto_producer.py` JSON action에도 노출.
- 작업 완료 시 `timeline.md` 기록 및 git commit.
