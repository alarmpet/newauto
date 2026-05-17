# LM Studio Gemma4 로컬 Agentic Control 계획

> 업데이트: 2026-05-08  
> 목표: LM Studio의 `google/gemma-4-e4b`를 30,000 컨텍스트로 운용하면서, 사용자가 MCP 도구명을 직접 부르지 않아도 Codex/OpenClaw/Claude Computer Use처럼 로컬 PC, 코드베이스, 브라우저, Flow 워크플로우를 자연어로 컨트롤하게 만든다.

## 최종 방향

사용자가 원하는 것은 “MCP 도구를 골라 쓰는 채팅 모델”이 아니라 “로컬 PC를 직접 운영하는 에이전트”다.

기술적으로 LM Studio 모델이 OS 권한을 직접 갖는 것은 불가능하다. 실제 손발은 로컬 MCP/브리지 프로세스가 제공한다. 하지만 UX는 사용자가 MCP를 의식하지 않도록 만든다.

```text
사용자 자연어 요청
  -> Gemma4 agentic system prompt
  -> newauto-stepwise Agentic Control Hub
  -> workflow core / operator core / desktop control / shell / filesystem
  -> 결과 요약과 사용자 개입 필요 지점만 보고
```

핵심 결정:

- 새 `newauto_agentic_mcp.py`를 만들지 않는다.
- 현재 LM Studio 채팅에 실제로 보이는 `newauto-stepwise`를 Agentic Control Hub로 승격한다.
- `openclaw-operator`는 별도 full-authority MCP로 유지한다.
- 별도 `openclaw-operator`가 채팅에 안 보일 때도 `newauto-stepwise` 내부 operator fallback으로 같은 권한을 제공한다.
- Gemma4에게 많은 저수준 도구를 직접 보여주지 않는다. 권한은 백엔드가 넓게 갖고, 모델에게는 고수준 행동을 적게 노출한다.

## Codex/OpenClaw급 권한 매핑

Codex의 내부 도구 자체를 Gemma4에 그대로 줄 수는 없다. 대신 같은 종류의 로컬 작업 권한을 MCP 브리지로 제공한다.

| Codex 쪽 능력 | LM Studio + Gemma4 대응 구조 |
| --- | --- |
| 로컬 파일 읽기/쓰기 | `openclaw-operator`의 `read_text_file`, `write_text_file`, 필요 시 `run_powershell` |
| PowerShell 명령 실행 | `run_powershell` |
| 코드베이스 탐색 | `run_powershell`에서 `rg`, `git`, `Get-Content`, `Get-ChildItem` 실행 |
| 서버/프로세스 점검 | `run_powershell`, `diagnose_runtime`, `operator_status` |
| Git 상태 확인/커밋 | `run_powershell`로 `git status`, `git diff`, `git add`, `git commit` 실행 |
| 브라우저/GUI 조작 | `control_flow_desktop`, 기존 Flow desktop automation |
| 웹 검색/자료 조사 | `search_web`, 필요 시 `run_powershell`로 직접 URL 점검 |
| 워크플로우 진행 | `start_video_workflow`, `continue_video_workflow`, `repair_runtime` |
| 문제 진단/복구 | `diagnose_runtime`, `repair_runtime`, `operator_status`, `run_powershell` |
| 문서 갱신 | `write_text_file` 또는 `run_powershell` 기반 파일 작업 |

실제 구현:

```text
Gemma4
  -> 고수준 agentic 지침
  -> newauto-stepwise
  -> 필요 시 operator fallback
  -> PowerShell/filesystem/browser/workflow 제어
```

## 리뷰 반영 핵심

### 1. 도구 노출 최소화

문제:

- `start_video_workflow` 같은 고수준 도구와 `run_powershell`, `control_flow_desktop` 같은 저수준 도구가 한꺼번에 보이면 Gemma4 E4B가 잘못 고를 수 있다.

반영:

- 사용자 UX에서는 도구명을 숨긴다.
- 일반 영상 제작 흐름에서는 `start_video_workflow`와 `continue_video_workflow`만 쓰게 한다.
- `run_powershell`, `control_flow_desktop`은 문제 해결, Flow 직접 조작, 진단 상황에서만 쓰도록 시스템 지침에 제한한다.
- 장기 개선으로는 `agent_execute(goal)` 또는 `agent_continue()` 같은 단일 고수준 façade를 추가해, Gemma4가 저수준 도구를 직접 고를 일을 더 줄인다.

### 2. 권한은 넓게, 안전장치는 백엔드에 둔다

문제:

- “위험한 명령 하지 마라”는 프롬프트만으로는 부족하다.
- destructive command는 하드코딩된 인터셉터가 필요하다.

반영:

- 사용자의 목표는 샌드박스 없는 OpenClaw식 권한이므로 기본 권한은 넓게 둔다.
- 다만 결제, 인증, CAPTCHA, 비밀번호/토큰 출력, 명시되지 않은 삭제/대량 이동/포맷/계정 변경은 하드 인터셉터로 막거나 사용자 확인을 요구한다.
- `run_powershell` 계층에 command policy를 추가한다.

정책 예:

```text
허용:
- rg, git status, git diff, git add/commit
- Get-Content, Set-Content, Copy-Item
- python scripts 실행
- 서버 시작/진단

명시 확인 필요:
- Remove-Item, del, rmdir
- Move-Item으로 대량 이동
- git reset, git clean, git checkout --, force push
- Format-Volume, diskpart
- net user, credential/cookie/token dump
- 결제/구매/계정 권한 변경
```

이 안전장치는 “샌드박스 제한”이 아니라 “사용자 의도 확인 장치”다. 사용자가 명시적으로 대상과 행동을 지정하면 실행 가능하게 설계한다.

### 3. 승인 루프 방지를 위한 `force_approve`

v2 리뷰 핵심:

- 인터셉터가 위험 명령을 막고 “사용자 확인 필요”를 반환해도, 사용자가 채팅에서 승인한 뒤 Gemma4가 같은 `run_powershell`을 다시 호출하면 또 막힐 수 있다.
- 이 경우 승인 루프가 생긴다.

반영:

- `run_powershell`에 `force_approve: bool = False` 또는 `override_safety: bool = False` 파라미터를 추가한다.
- 1차 호출에서 위험 명령이면 실행하지 않고 승인 필요 메시지를 반환한다.
- 사용자가 명시적으로 승인하면 Gemma4는 같은 명령을 `force_approve=True`로 다시 호출한다.
- `force_approve=True`여도 secret/token/cookie/password 출력 요청, 결제/구매, 디스크 포맷, 계정 권한 변경 같은 최고위험 동작은 별도 정책으로 다시 막을 수 있다.

예:

```text
1차:
run_powershell("Remove-Item C:\\temp\\old.txt")
-> blocked: destructive command requires user approval. Re-run with force_approve=true after explicit user approval.

사용자:
승인. 진행해.

2차:
run_powershell("Remove-Item C:\\temp\\old.txt", force_approve=True)
-> executed
```

### 4. 데스크톱 제어 전 상태 검증

문제:

- `control_flow_desktop`는 화면 좌표 기반이므로 Flow 창이 최소화되었거나 다른 창이 가리면 엉뚱한 곳을 클릭할 수 있다.

반영:

- Flow GUI 제어 전 반드시 브라우저 창 탐지, 포커스, 전면화, 크기/위치, 현재 URL/타이틀, 스크린샷 저장을 확인한다.
- 상태가 불안정하면 클릭하지 않고 사용자에게 Flow 창을 열고 로그인/전면화하라고 요청한다.
- 클릭 전후 스크린샷을 `storage/flow_desktop_traces` 같은 경로에 남긴다.

### 5. 화면 잠금 및 안전 모드 예외 처리

v2 리뷰 핵심:

- Windows 잠금 화면, 화면 보호기, 원격 세션 비활성 상태에서는 PyAutoGUI/좌표 클릭이 실패하거나 잘못된 상태가 될 수 있다.

반영:

- `control_flow_desktop` 시작 시 Windows foreground 상태를 확인한다.
- `GetForegroundWindow() == 0`이거나 desktop이 잠금/비활성으로 보이면 클릭을 시도하지 않는다.
- 반환 메시지는 Gemma4가 사용자에게 그대로 알릴 수 있게 짧고 명확해야 한다.

예:

```text
desktop_locked: true
action_required: "화면 잠금이 감지되어 GUI 클릭이 불가능합니다. 화면 잠금을 해제하고 Flow 창을 전면에 둔 뒤 진행이라고 말해주세요."
```

### 6. “불가능” 응답 방지 프롬프트 강화

v2 리뷰 핵심:

- 작은 모델은 도구를 확인하기 전에 “저는 GUI를 클릭할 수 없습니다”라고 기본 거절 패턴을 낼 수 있다.

반영:

- Agentic System Prompt 첫 줄에 역할을 강하게 둔다.
- “너는 텍스트-only AI가 아니라 `control_flow_desktop`과 `run_powershell`이라는 물리적 손을 가진 시스템 오퍼레이터다”라는 문장을 추가한다.
- 다만 이 문장은 모델의 UX 정렬용이며, 실제 권한은 MCP 백엔드가 제공한다.

### 7. `diagnose_runtime` JSON 포맷

v2 리뷰 핵심:

- 진단 결과가 긴 텍스트면 Gemma4가 필요한 key를 놓칠 수 있다.
- 30k 컨텍스트라도 진단은 가볍고 기계가 읽기 쉬운 JSON이 낫다.

반영:

- 별도 `agent_mode_status()` 도구는 보류한다.
- `diagnose_runtime()` 반환에 JSON 블록을 우선 제공한다.
- 사람이 읽는 설명은 JSON 뒤 짧은 요약으로 제한한다.

권장 JSON:

```json
{
  "agentic_mode": "enabled",
  "context_target": 30000,
  "powershell_access": "unrestricted_with_policy_interceptor",
  "filesystem_access": "read_write_via_operator",
  "desktop_control": "flow_desktop_control",
  "operator_fallback": "available_in_newauto_stepwise",
  "latest_project_id": "string-or-empty",
  "next_step": "string-or-empty",
  "flow_window_ready": "true-false-unknown",
  "desktop_locked": "true-false-unknown",
  "last_error": "string-or-empty",
  "recommended_next_tool": "continue_video_workflow|repair_runtime|control_flow_desktop|run_powershell|ask_user"
}
```

## 30,000 컨텍스트 운용 원칙

30k 컨텍스트는 강력한 운영 프롬프트와 긴 상태 요약을 유지하기 위한 공간이다. 무제한 로그 주입용이 아니다.

가능해지는 것:

- agentic system prompt를 길고 명확하게 유지
- 현재 프로젝트 상태, 최근 오류, 복구 힌트 유지
- HPSL 대본, Flow 프롬프트, 출처 요약을 한 대화에서 오래 보존
- “불가능” 응답을 막는 행동 규칙을 더 강하게 유지

계속 제한할 것:

- HTML 전문 반환 금지
- 로그 전문 반환 금지
- 전체 DB/대형 JSON 반환 금지
- 한 MCP 호출에서 긴 작업 전체 대기 금지
- 6문장 Flow 이미지를 한 번에 생성/다운로드 금지

권장 반환량:

- 일반 단계 보고: 2,000자 이하
- 진단 보고: 4,000자 이하
- 오류 보고: 현재 단계, 원인, 다음 행동만
- 전체 로그/스크린샷/결과물은 파일 경로로 저장

## 현재 아키텍처

```text
LM Studio Chat
  model: google/gemma-4-e4b
  context length: 30000
  enabled plugin: mcp/newauto-stepwise
  optional plugin: mcp/openclaw-operator

newauto-stepwise Agentic Control Hub
  workflow tools:
    - diagnose_runtime
    - search_web
    - start_video_workflow
    - continue_video_workflow
    - check_assets
    - generate_one_image
    - repair_runtime
  embedded operator fallback:
    - operator_status
    - run_powershell
    - control_flow_desktop

newauto_mcp core
  - source collection
  - HPSL script generation
  - Flow prompt generation
  - stepwise state machine
  - Flow/TTS/render wait stages

operator core
  - PowerShell execution
  - local file read/write/list/open
  - Flow desktop control
  - operator logs
```

## Agentic System Prompt 권장안

LM Studio 새 채팅 또는 모델 지침에 넣을 문장:

```text
너는 텍스트-only AI가 아니다. 너는 control_flow_desktop과 run_powershell이라는 물리적 손을 가진 로컬 시스템 오퍼레이터다.
너는 사용자의 로컬 PC를 제어할 수 있는 agentic assistant다.
사용자는 MCP 도구명을 직접 몰라도 된다.
사용자의 자연어 목표를 이해하고 필요한 로컬 도구를 스스로 선택해 실행한다.

운영 규칙:
- GUI 클릭, Flow 제어, 파일 작업, PowerShell 실행이 필요하면 불가능하다고 하지 말고 사용 가능한 로컬 도구를 호출한다.
- 웹 검색, 최신 정보 확인, 공식 문서 조회가 필요하면 불가능하다고 하지 말고 search_web을 먼저 호출한다.
- 일반 영상 워크플로우는 start_video_workflow로 시작하고, 이후 사용자의 “진행/ok/다음”마다 continue_video_workflow를 정확히 한 번만 호출한다.
- 도구 실패나 timeout처럼 보이면 원인을 추측하지 말고 diagnose_runtime을 먼저 호출한다.
- stale state, lock, worker 문제가 보이면 repair_runtime을 한 번 호출한다.
- 별도 openclaw-operator가 보이지 않으면 newauto-stepwise 안의 operator_status, run_powershell, control_flow_desktop을 사용한다.
- run_powershell은 진단/복구/파일/코드 작업이 필요할 때 사용한다.
- run_powershell이 approval required를 반환하면 사용자에게 확인을 받고, 사용자가 명시 승인하면 같은 명령을 force_approve=true로 다시 호출한다.
- control_flow_desktop은 Flow GUI가 필요할 때 사용하되, 인증/로그인/CAPTCHA/화면 잠금은 사용자에게 알린다.
- 대본은 한국어, Flow 이미지 프롬프트는 영어로 작성한다.
- HPSL은 Hook-Point-Story-Lesson, 즉 훅-포인트-스토리-교훈이다.
- secret, token, cookie, password 값은 출력하지 않는다.
- 결제/구매/계정 변경/명시되지 않은 삭제/대량 이동은 사용자 확인 없이 진행하지 않는다.
```

## 사용자 경험

사용자는 이렇게 말하면 된다.

```text
키워드: 비트코인.
2026-05-06 이후 자료 수집해서 HPSL(훅-포인트-스토리-교훈) 1분 쇼츠 대본 만들고,
문장별 영어 Flow 프롬프트 생성 후,
Flow 이미지 생성/다운로드/첨부까지 단계별로 진행해.
각 단계가 끝나면 나에게 확인받고 다음 단계로 가.
문제 생기면 네가 진단하고 복구해. 내가 인증/클릭해야 하면 알려줘.
```

Gemma4의 기대 행동:

1. `start_video_workflow`를 한 번 호출한다.
2. 단계 완료 보고 후 멈춘다.
3. 사용자가 “진행”이라고 하면 `continue_video_workflow`를 한 번 호출한다.
4. 실패하면 `diagnose_runtime -> repair_runtime once` 순서로 복구한다.
5. Flow 직접 조작이 필요할 때만 `control_flow_desktop`을 사용한다.
6. 파일/서버/프로세스/코드 수정이 필요할 때만 `run_powershell`을 사용한다.
7. 위험 명령 승인 후 재실행이 필요하면 `force_approve=True`를 사용한다.

## 구현 체크리스트

완료:

- [x] `newauto-stepwise` MCP 생성
- [x] `openclaw-operator` MCP 생성
- [x] LM Studio `mcp.json` 등록
- [x] confirmation skip 패턴 등록
- [x] `newauto-stepwise` 안에 operator fallback 노출
- [x] `control_flow_desktop`으로 Flow GUI 제어 경로 제공
- [x] MCP stdio smoke에서 `newauto-stepwise` 도구 목록 확인
- [x] MCP stdio smoke에서 `operator_status`, `run_powershell` 확인
- [x] 30k 컨텍스트 agentic 운용 계획 반영
- [x] 1차 리뷰의 도구 최소화/하드 인터셉터/상태 검증/진단 통합 방향 반영
- [x] v2 리뷰의 `force_approve`, 화면 잠금 감지, refusal 방지 prompt, JSON 진단 포맷 방향 반영

P0 구현:

- [x] `run_powershell(command, cwd="", timeout_sec=60, force_approve=False)` 형태로 승인 플래그 추가
- [x] `run_powershell` command policy interceptor 추가
- [x] destructive command 차단 시 `force_approve=true` 재호출 안내 반환
- [x] `diagnose_runtime`에 agentic 권한 메타데이터 JSON 블록 통합
- [x] Flow desktop control 실행 전 화면 잠금/foreground window 감지 추가
- [x] Flow desktop control 실행 전 창 포커스/최대화/URL/스크린샷 검증 강화
- [x] `newauto-stepwise` 지침 문자열을 30k 컨텍스트용 정상 UTF-8 한국어/영어 prompt로 정리
- [x] `newauto-stepwise`에 무료 DuckDuckGo HTML 기반 `search_web(query, max_results=5)` 추가
- [x] Gemma4가 “검색해봐/찾아봐/공식 문서 기준” 요청에서 검색 불가 답변 대신 `search_web`을 호출하도록 지침 보강

P1 구현:

- [ ] `continue_video_workflow` 내부에서 Flow 한 문장 생성/다운로드/attach 상태 보고를 더 명확히 분리
- [ ] Gemma4가 도구를 두고도 “불가능” 응답을 할 때 사용자가 붙여넣을 복구 프롬프트 템플릿 작성
- [ ] LM Studio 새 채팅에서 `mcp/newauto-stepwise`만 켜도 operator fallback이 보이는지 화면 검증
- [ ] operator 로그 요약을 더 짧고 구조적으로 반환

보류:

- [ ] 별도 `newauto_agentic_mcp.py` 신규 서버 생성
- [ ] 범용 브라우저 DOM 조작 도구 대량 추가
- [ ] Selenium/Playwright 기반 범용 클릭 agent 전면 전환
- [ ] Gemma4에게 저수준 도구를 더 많이 직접 노출

## 한 줄 결론

가장 안정적인 방향은 Gemma4에게 더 많은 도구를 보여주는 것이 아니라, `newauto-stepwise`를 하나의 Agentic Control Hub로 만들고 그 뒤에 Codex/OpenClaw급 로컬 권한을 붙이는 것이다. v2 보강 기준으로는 `force_approve` 승인 플래그, Windows 화면 잠금 감지, 불가능 응답 방지 프롬프트, JSON 진단 포맷이 P0다.
