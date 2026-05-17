# Cline + Qwen3.5 툴 협력/자체복구 실행 계획서

작성일: 2026-05-13
업데이트: Antigravity 리뷰 반영

## 목표

사용자가 Cline + Qwen3.5에게 명령했을 때, 모델이 말로만 답하지 않고 실제 도구를 사용해 끝까지 실행하게 만든다. 막히면 같은 행동을 반복하지 않고, 기존 newauto 진단/복구 인프라와 OpenRouter 보조 모델을 사용해 원인을 좁힌 뒤 다시 실행한다.

추가 원칙: 이미지/Flow 문제만이 아니라 모든 작업에서 같은 blocker를 로컬에서 3회 해결하지 못하면 4번째 로컬 재시도 전에 OpenRouter에 협력 요청한다.

핵심 역할:

- Qwen3.5: 로컬 실행자
- `newauto-stepwise`: 진단/복구/검색/워크플로우 MCP 허브
- `playwright`: 기본 브라우저 조작
- `browser-use`: Playwright가 막힌 복잡한 웹 탐색 보조
- `computer-use`: 브라우저 밖 PC 조작, 기본 비활성
- OpenRouter Gemma 4: 막혔을 때만 쓰는 보조 분석가

중요한 수정:

이 계획서는 더 이상 새 PowerShell OpenRouter 호출기를 만드는 방향이 아니다. 이미 구현된 `scripts/openrouter_subagent_harness.py`와 `newauto-stepwise`의 `ask_openrouter_subagent`를 표준 경로로 사용한다.

## 반영한 리뷰 결론

반영:

- OpenRouter 직접 API 호출 대신 기존 harness 재사용
- 텍스트 모델 체인을 `31B free -> 26B free -> gpt-oss free`로 수정
- Vision 모델 체인을 `Gemma 4 free -> NVIDIA VL free -> OCR free -> openrouter/free`까지 확장
- 유료 OpenRouter 모델 사용 제거
- 상태 캡슐을 `forensic_diagnose` / redacted forensic facts packet 중심으로 통합
- secret redaction, boundary, budget guard를 기존 구현에 위임
- `computer-use`는 설치 완료 상태지만 기본 비활성 유지
- `.clinerules`와 충돌하지 않도록 새 Custom Instructions를 통째로 덮어쓰지 않음

보류:

- `research.md` 분리, `timeline.md` 인코딩 복구는 이 계획서 범위 밖의 장기 과제로 둔다.
- `browser-use` 실제 성공률 측정은 별도 P1 검증 과제로 둔다.
- `computer-use` 클릭/입력 실사용 테스트는 사용자가 명시적으로 켤 때만 진행한다.

## 현재 인프라

이미 존재하고 사용해야 하는 자산:

| 용도 | 표준 경로 |
| --- | --- |
| OpenRouter 보조 호출 | `newauto-stepwise` MCP `ask_openrouter_subagent` |
| Shell fallback OpenRouter 호출 | `scripts/openrouter_subagent_harness.py` |
| OpenRouter budget 확인 | `scripts/openrouter_subagent_harness.py --budget-status --json-output` |
| 모델 fallback | harness 내부 기본 체인 |
| 로컬 상태 진단 | `diagnose_runtime` |
| 정밀 진단 | `forensic_diagnose` / `scripts/forensic_doctor.py` |
| 상태 캡슐 | `ask_openrouter_subagent`가 붙이는 redacted forensic facts packet |
| screenshot 분석 | `analyze_browser_screenshot` |
| 로컬 웹 검색 | `search_web` |
| 브라우저 직접 조작 | `playwright` MCP |
| 복잡한 웹 자동화 | `browser-use` MCP |
| PC 조작 | `computer-use`, Cline 설정상 `disabled: true` |

확인된 보안 상태:

- `.gitignore`에 `openrouter.txt` 포함
- `.gitignore`에 `.env` 포함
- harness에 `SECRET_RE`/redaction 구현 존재
- `.clinerules`에 `openrouter.txt`를 읽거나 전송하지 말라는 규칙 존재

검증 상태:

- `agent_eval_smoke.py --skip-web --skip-openrouter` 통과
- Cline MCP 설정에 `playwright`, `browser-use`, `computer-use`, `newauto-stepwise` 존재 확인
- `computer-use`는 `disabled: true` 확인
- Chrome CDP endpoint `http://127.0.0.1:9225/json/version` 정상
- Browser-Use doctor 5/5 통과
- `cloudflared` 설치 완료
- `profile-use` 설치 완료
- Flow desktop 실패 wrapper는 `AUTO_OPENROUTER_VISION_ANALYSIS`를 자동으로 붙이도록 보강
- 실제 OpenRouter Vision 호출 확인: `google/gemma-4-31b-it:free` 성공 사례 확인
- 실제 rate-limit 대응 확인: Gemma 31B/26B text debug rate-limit 시 `openai/gpt-oss-20b:free` fallback 성공

## 모델 전략

OpenRouter는 무료 모델만 사용한다. 유료 모델은 이 계획에서 제외한다.

표준 체인:

1. `google/gemma-4-31b-it:free`
2. `google/gemma-4-26b-a4b-it:free`
3. `openai/gpt-oss-20b:free`

Vision 체인:

1. `google/gemma-4-31b-it:free`
2. `google/gemma-4-26b-a4b-it:free`
3. `nvidia/nemotron-nano-12b-v2-vl:free`
4. `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`
5. `baidu/qianfan-ocr-fast:free`
6. `openrouter/free`

근거:

- `scripts/openrouter_subagent_harness.py` 기본값과 일치
- `.clinerules` OpenRouter Subagent 규칙과 일치
- `prompts/model_profiles.md`의 `openrouter-reviewer` 정책과 일치

운영 원칙:

- OpenRouter는 trivial 작업에 쓰지 않는다.
- OpenRouter는 로컬 실행을 대신하지 않는다.
- OpenRouter 답변은 조언이며, 로컬 도구로 검증한 뒤 적용한다.
- full log, full repo, browser profile, cookie, token, API key, credential 파일은 보내지 않는다.

## 도구 계층

### 1. 일반 웹 작업

기본:

- `newauto-stepwise`의 `search_web`
- `playwright` MCP

사용할 때:

- 최신 정보 검색
- URL 열기
- 뉴스/문서/깃허브 확인
- 페이지 텍스트 추출
- 로그인/차단/캡차 여부 확인

규칙:

- 최신 정보는 추측하지 않는다.
- HTML/DOM 텍스트로 충분하면 screenshot을 OpenRouter에 보내지 않는다.
- GUI 상태나 클릭 대상이 불명확할 때만 screenshot 분석을 쓴다.

### 2. 복잡한 웹 자동화

보조:

- `browser-use` MCP

사용할 때:

- Playwright가 같은 지점에서 2회 실패
- 여러 페이지를 탐색해야 함
- 폼 입력, 검색, 클릭, 결과 확인이 섞임
- DOM selector만으로 클릭 대상이 불분명함

주의:

- Qwen3.5가 도구 선택을 헷갈릴 수 있으므로 기본 도구로 남발하지 않는다.
- `search_web + playwright`가 먼저다.
- 실제 Cline MCP 호출 성공률은 별도 테스트로 측정한다.

### 3. PC 전체 조작

도구:

- `computer-use`

상태:

- 설치/빌드 완료
- Cline 설정 등록 완료
- 기본값 `disabled: true`

사용 조건:

- 사용자가 명시적으로 PC 화면 조작을 요청
- 사용자가 `computer-use` 활성화를 허용
- 첫 행동은 screenshot 확인만 수행
- 클릭/입력은 별도 사용자 승인 후 수행

금지:

- 결제, 구매, 삭제, 권한 변경, 파일 업로드, 외부 전송을 사용자 확인 없이 수행
- OpenRouter에 browser profile, cookie, credential, 전체 screenshot dump를 전달

## 복구 루프

### 1단계: 명령 분류

Qwen3.5는 사용자 요청을 다음 중 하나로 분류한다.

- 웹 검색/URL/페이지 확인: `search_web` 또는 `playwright`
- 복잡한 웹 탐색: `browser-use`
- 브라우저 밖 조작: `computer-use`
- newauto 영상 워크플로우: `start_video_workflow` / `continue_video_workflow`
- workflow 실패/대기 반복: `diagnose_runtime` → `forensic_diagnose`
- 코드/파일 작업: 파일 도구 + `git`
- 라이브러리 사용법: `context7` 또는 공식 웹 문서

### 2단계: 로컬 실행 우선

먼저 로컬 도구로 실제 상태를 확인한다.

예:

- 웹이면 `search_web` 또는 `playwright`
- Flow/영상이면 `diagnose_runtime`
- 반복 대기면 `forensic_diagnose`
- screenshot 필요 시 `analyze_browser_screenshot`

### 3단계: 실패 감지

아래 조건이면 같은 행동을 반복하지 않는다.

- 같은 도구/같은 step 2회 실패
- 같은 blocker에 대한 로컬 복구 시도 3회 실패
- `tts_wait` 반복
- stale worker, expired heartbeat, missing subprocess
- render artifact 누락
- 클릭 대상 불명확
- browser/Flow timeout
- 테스트 실패 원인 불명

로컬 복구 시도에 포함되는 것:

- 실패한 tool retry
- 대체 로컬 tool 실행
- diagnosis/forensic/repair 명령
- browser DOM/screenshot 확인
- blocker 해결을 위한 코드 수정
- dependency/config/server 수정

### 4단계: deterministic diagnosis

workflow/server/state 실패:

1. `diagnose_runtime`
2. 원인이 불명확하면 `forensic_diagnose`
3. stale worker / heartbeat / missing artifact면 `repair_runtime` 또는 `repair_tts`
4. repair 성공 후 사용자에게 묻지 말고 `continue_video_workflow` 1회

웹/브라우저 실패:

1. DOM/text 확인
2. Playwright page/tab 확인
3. Playwright Flow 실패 결과에 `AUTO_OPENROUTER_VISION_ANALYSIS`가 있으면 해당 결과를 advisory facts packet으로 확인
4. 자동 Vision 분석이 없거나 실패/rate-limit/inconclusive이면 `analyze_browser_screenshot`
5. Gemma 4 Vision이 rate-limit이면 NVIDIA VL/OCR/`openrouter/free` 비전 fallback으로 이어간다.
6. 모든 Vision fallback이 실패하면 text-only fallback의 좌표 클릭 제안을 맹신하지 말고 Playwright/browser-use/DOM 확인 또는 사용자 확인
6. Playwright가 같은 지점에서 2회 실패하면 `browser-use`

### 5단계: OpenRouter escalaton

OpenRouter는 아래 조건에서만 사용한다.

- 같은 blocker를 로컬에서 3회 해결하려고 시도했지만 실패
- `diagnose_runtime` / `forensic_diagnose` / repair 이후에도 실패 원인이 불명확
- Qwen3.5가 다음 행동을 확신하지 못함
- 코드/설계/복구 판단이 복잡함
- 리뷰/계획/디버그 보조가 필요함

3회 실패 후 escalation은 이미지 분석 전용이 아니다. workflow, browser, Flow, shell, Python, server, dependency, test, configuration, code/debug 실패에 모두 적용한다.

표준 호출:

```text
ask_openrouter_subagent(mode="debug", task="<구체 실패 질문>", project_id="<PROJECT_ID>")
```

MCP 도구가 보이지 않을 때만 shell fallback:

```powershell
Get-Content <task.txt> -Raw | C:\Users\petbl\local-rag\.venv\Scripts\python.exe C:\Users\petbl\newauto\scripts\openrouter_subagent_harness.py --mode debug --task-stdin --json-output
```

호출 전:

```powershell
C:\Users\petbl\local-rag\.venv\Scripts\python.exe C:\Users\petbl\newauto\scripts\openrouter_subagent_harness.py --budget-status --json-output
```

주의:

- 긴 한국어/멀티라인/JSON prompt는 `--task "..."`로 넘기지 않는다.
- `--task-stdin` 또는 `--task-file`만 사용한다.
- OpenRouter 응답은 boundary 안의 JSON action packet만 참고한다.
- 응답은 advisory로 취급하고 로컬 검증 후 실행한다.

## 상태 캡슐

새 포맷을 따로 만들지 않는다. 표준은 `forensic_diagnose`와 `ask_openrouter_subagent`의 redacted forensic facts packet이다.

보조 task에 포함할 최소 정보:

```text
TASK:
사용자의 원 요청

CURRENT_GOAL:
지금 막힌 작은 목표

BLOCKER:
현재 해결되지 않은 문제

LOCAL_FACTS:
diagnose_runtime 또는 forensic_diagnose에서 확인한 사실

TOOLS_TRIED:
도구명, 결과, 오류. 3회 escalation일 때는 1차/2차/3차 시도를 명시한다.

QUESTION:
다음 한 단계로 어떤 로컬 도구/행동을 해야 하는가?
```

금지:

- full logs
- full files
- `openrouter.txt`
- `.env`
- cookies
- browser profile path 세부 내용
- API key, token, password

## Custom Instructions 적용 방식

기존 `.clinerules`를 통째로 덮어쓰지 않는다. 이미 더 상세한 규칙이 있다.

추가해야 하는 최소 델타:

```text
## Browser Tool Hierarchy
- Default web actions: use search_web or playwright MCP.
- If playwright fails twice or multi-step exploration is needed, use browser-use MCP when available.
- computer-use MCP is disabled by default. Enable only when the user explicitly asks for PC screen control.
- Before using computer-use, take a screenshot first without clicking.
- Click/input with computer-use requires explicit user approval.
```

## 실제 병목 대응

이 계획은 웹 도구 계층화만 다루지 않는다. newauto에서 반복된 실제 실패 패턴은 아래 기존 복구 루프로 처리한다.

### `tts_wait` 반복

순서:

1. `diagnose_runtime`
2. `forensic_diagnose`
3. heartbeat expired / worker missing이면 `repair_tts`
4. repair 성공 후 `continue_video_workflow` 1회

금지:

- OpenRouter 설정 변경으로 TTS 문제를 해결하려 하지 않는다.

### render 단계 누락/오판

순서:

1. `diagnose_runtime`
2. `forensic_diagnose`
3. artifact와 project state 비교
4. 필요한 repair 또는 render step 재진입

주의:

- workflow 실행 중 `final_verification.ps1`를 리포지터리 건전성 검사처럼 남용하지 않는다.
- workflow 완료 여부는 API state, artifact path, project state로 확인한다.

### 브라우저/Flow 실패

순서:

1. 기존 Playwright/CDP page list 확인
2. Flow 탭 재사용
3. DOM/text 확인
4. 실패 screenshot은 `analyze_browser_screenshot`
5. 그래도 막히면 OpenRouter advisory

## 검증 계획

P0:

- 이 문서와 `.clinerules`의 충돌 제거
- OpenRouter 텍스트 모델 정책을 `31B free -> 26B free -> gpt-oss free`로 통일
- OpenRouter Vision 모델 정책을 `Gemma 4 free -> NVIDIA VL free -> OCR free -> openrouter/free`로 통일
- `computer-use` 기본 비활성 정책 명시
- PowerShell 직접 API 호출 접근 폐기

P1:

- Cline에서 `browser-use` MCP가 실제로 호출되는지 확인
- `playwright` 실패 후 `browser-use` fallback 테스트
- `ask_openrouter_subagent`가 redacted forensic facts packet을 붙이는지 smoke 확인
- `agent_eval_smoke.py --skip-web` 또는 관련 smoke로 redaction 확인

P2:

- `research.md` 아카이빙
- `timeline.md` 인코딩 손상 항목 복구
- `computer-use` screenshot-only 테스트
- `browser-use` LLM 기반 기능 평가

## 성공 기준

성공한 상태:

- Qwen3.5가 웹 요청에 로컬 지식으로 답하지 않고 `search_web`/`playwright`를 호출한다.
- Playwright 반복 실패 시 `browser-use` 또는 screenshot analysis로 전환한다.
- workflow 실패 시 `diagnose_runtime`/`forensic_diagnose`를 먼저 호출한다.
- OpenRouter는 기존 harness/MCP로만 호출하고, 무료 모델 체인을 사용한다.
- OpenRouter에는 redacted facts packet만 전달된다.
- `computer-use`는 사용자 명시 전까지 비활성이다.
- Flow GUI 실패 시 OpenRouter Vision 자동 분석 또는 명시적 `analyze_browser_screenshot` 경로가 작동한다.

## 참고 문서

- 리뷰: `cline-qwen-tool-cooperation-recovery-plan-review-antigravity-2026-05-13.md`
- 설치 상태: `docs/cline-qwen-browser-computer-use-plan.md`
- OpenRouter harness: `scripts/openrouter_subagent_harness.py`
- Stepwise MCP: `scripts/newauto_stepwise_mcp.py`
- Forensic doctor: `scripts/forensic_doctor.py`
- Agent smoke: `scripts/agent_eval_smoke.py`
- Model profiles: `prompts/model_profiles.md`
- Agent rules: `.clinerules`
- OpenRouter Chat Completions API: https://openrouter.ai/docs/api-reference/chat-completion
- OpenRouter Google models: https://openrouter.ai/google
