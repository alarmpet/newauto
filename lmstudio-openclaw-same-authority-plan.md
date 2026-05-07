# LM Studio + Gemma4 OpenClaw 동일 권한 부여 계획

## 목표

LM Studio 채팅창의 `google/gemma-4-e4b`가 OpenClaw의 `sandbox.mode=off` + `tools.profile=full`에 최대한 가까운 로컬 작업 권한을 갖게 한다.

중요한 현실 조건:

- LM Studio 모델 자체는 OS 권한을 직접 갖지 않는다.
- 권한은 MCP 서버가 제공하는 도구를 통해 주어진다.
- 따라서 “OpenClaw와 같은 권한”은 `Gemma4 -> MCP tool -> 로컬 Python/PowerShell/파일/프로세스` 구조로 구현한다.

## OpenClaw 권한 모델 확인

확인 경로:

- `C:\Users\petbl\.openclaw\openclaw.json`
- `C:\Users\petbl\.openclaw\exec-approvals.json`
- `C:\Users\petbl\.openclaw\gateway.cmd`
- `C:\Users\petbl\.openclaw\sandboxes\agent-main-f331f052`
- `C:\Users\petbl\.openclaw\skills\sonol-multi-agent`

확인된 권한 구조:

- Agent `main`: `sandbox.mode = off`
- Agent `music-auto-bot`: `sandbox.mode = off`
- Agent tools: `profile = full`
- 기본 workspace: `C:\Users\petbl\music-auto`
- gateway: loopback local gateway, token auth
- commands: native/nativeSkills auto, restart enabled
- channel: Telegram allowlist 기반 원격 입력
- plugins: local capabilities, phone-control, talk-voice, telegram, memory-core 등 허용
- Sonol skill: dashboard 승인, run manifest, subagent prompt, runtime report, SQLite event 기반 orchestration

보안 메모:

- OpenClaw 설정에는 토큰류가 평문으로 존재한다.
- 계획서와 MCP 출력에는 토큰 원문을 복사하지 않는다.
- 이미 화면/로그에 노출된 토큰은 교체하는 것이 안전하다.

## LM Studio 적용 구조

기존 서버:

```text
newauto-stepwise
  - start_video_workflow
  - continue_video_workflow
  - diagnose_runtime
  - repair_runtime
  - check_assets
  - generate_one_image
```

추가 서버:

```text
openclaw-operator
  - operator_status
  - run_powershell
  - read_text_file
  - write_text_file
  - list_directory
  - open_target
  - control_flow_desktop
  - recent_operator_logs
```

권한 매핑:

| OpenClaw | LM Studio + Gemma4 구현 |
| --- | --- |
| sandbox off | `run_powershell`로 로컬 PowerShell 실행 |
| tools full | 파일 읽기/쓰기, 디렉터리 조회, URL/파일 열기, 명령 실행 |
| local gateway | LM Studio MCP stdio bridge |
| token auth | LM Studio local MCP 설정 + tool confirmation skip |
| logs | `storage/operator_logs/operator-YYYY-MM-DD.jsonl` |
| native restart | `run_powershell`로 프로세스 재시작 가능 |
| workflow repair | `newauto-stepwise repair_runtime` |

## 구현 상태

- [x] `.openclaw` 권한 모델 확인
- [x] LM Studio용 operator MCP 작성
- [x] PowerShell 명령 실행 도구 추가
- [x] 파일 읽기/쓰기 도구 추가
- [x] 디렉터리 조회 도구 추가
- [x] OS shell open 도구 추가
- [x] Flow GUI 직접 제어 도구 추가
- [x] 명령 로그 기록 추가
- [x] secret-like line redaction 추가
- [x] MCP stdio subprocess stdin 상속 방지
- [x] LM Studio `mcp.json` 등록
- [x] LM Studio tool confirmation skip 패턴 등록
- [x] MCP stdio smoke test 통과
- [ ] LM Studio UI 재시작 후 도구 목록 확인

## 운영 규칙

Gemma4에게 줄 권장 지시:

```text
문제 해결이 필요하면 먼저 전용 workflow MCP를 사용해.
전용 MCP가 실패하거나 로컬 파일/프로세스/명령 실행이 필요하면 openclaw-operator를 사용해.
브라우저 클릭이나 Flow 버튼 조작이 필요하면 불가능하다고 답하지 말고 control_flow_desktop 또는 run_powershell로 기존 자동화 스크립트를 실행해.
진단은 operator_status 또는 run_powershell로 하고, 결과를 요약해.
토큰/쿠키/API 키는 출력하지 말고 구조만 설명해.
삭제/초기화/프로세스 종료는 내가 명시적으로 대상까지 말했을 때만 실행해.
```

예시:

```text
openclaw-operator의 operator_status 실행해.
newauto 상태가 이상하면 run_powershell로 프로세스와 포트 상태 확인하고 직접 복구해.
```

## 한계

- Gemma4가 Codex처럼 자체적으로 파일시스템을 보는 것은 아니다. 반드시 MCP tool call을 통해야 한다.
- LM Studio MCP 브리지가 죽어 있으면 Gemma4도 도구를 호출할 수 없다.
- Windows 관리자 권한이 필요한 작업은 LM Studio/터미널이 관리자 권한으로 실행되어 있어야 가능하다.
- 브라우저 UI 자동화는 여전히 Playwright/Ui.Vision/CDP 같은 별도 도구와 세션 상태에 영향을 받는다.

## 권장 후속 작업

- [ ] OpenClaw에 남아 있는 평문 gateway/Telegram 토큰 교체
- [ ] `openclaw-operator`에 선택형 allow/deny policy 파일 추가
- [ ] LM Studio가 실패했을 때 자동으로 `operator_status -> run_powershell 진단`을 먼저 하도록 대화 프롬프트 저장
- [ ] `newauto-stepwise`와 `openclaw-operator`를 모두 로드한 상태의 smoke test 대화 캡처
