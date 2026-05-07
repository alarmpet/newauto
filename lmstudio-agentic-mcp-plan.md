# LM Studio Gemma4 로컬 Agentic Control 계획

> 업데이트: 2026-05-08  
> 목표: LM Studio의 `google/gemma-4-e4b`를 30,000 컨텍스트로 운용하면서, 사용자가 MCP 도구명을 직접 부르지 않아도 Codex/OpenClaw/Claude Computer Use처럼 로컬 PC와 브라우저/Flow 워크플로우를 자연어로 컨트롤하는 구조를 만든다.

## 결론

새로운 `newauto_agentic_mcp.py`를 또 만드는 방향은 보류한다.

현재 코드베이스에는 이미 다음 구조가 있다.

- `newauto-stepwise`: LM Studio 채팅에 실제로 노출되는 최소 워크플로우 MCP
- `openclaw-operator`: OpenClaw식 로컬 실행 권한 MCP
- `newauto-stepwise` 내장 operator fallback: LM Studio가 별도 `openclaw-operator`를 못 볼 때도 `operator_status`, `run_powershell`, `control_flow_desktop` 사용 가능
- `flow_desktop_control.py`: 인증된 Flow 창을 실제 데스크톱 좌표 기반으로 제어
- start/wait 분리 워크플로우: 자료수집, HPSL 대본, Flow 프롬프트, 이미지 생성, TTS, 렌더링을 긴 단일 호출이 아니라 짧은 단계로 진행

따라서 개선 방향은 “새 MCP 추가”가 아니라, 이미 보이는 `newauto-stepwise`를 **Agentic Control Hub**로 승격시키는 것이다.

## 사용자가 원하는 UX

사용자는 LM Studio 채팅에서 이렇게 말하고 싶다.

```text
키워드: 비트코인.
2026-05-06 이후 자료 수집해서 HPSL 1분 쇼츠 대본 만들고,
문장별 영어 Flow 프롬프트 생성하고,
Flow에서 이미지 생성해서 다운로드/첨부하고,
OmniVoice로 음성 만들고 자막 싱크 맞춰 최종 영상 렌더링해.
문제 생기면 네가 진단하고 고치고, 내가 클릭/인증해야 하면 알려줘.
```

Gemma4는 사용자에게 MCP 도구명을 요구하지 않아야 한다.

나쁜 응답:

```text
저는 GUI를 클릭할 수 없습니다.
openclaw-operator/control_flow_desktop은 표준 함수가 아닙니다.
사용자님이 직접 버튼을 눌러주세요.
```

좋은 응답:

```text
1단계 자료 수집을 시작합니다.
완료 후 다음 단계 진행 여부를 확인하겠습니다.
```

그리고 내부적으로는 `start_video_workflow`, `continue_video_workflow`, `control_flow_desktop`, `run_powershell`, `repair_runtime` 등을 호출한다.

## 30,000 컨텍스트 운용 원칙

사용자는 LM Studio 컨텍스트 길이를 30,000으로 늘려 사용할 예정이다.

30k 컨텍스트에서 가능한 개선:

- 긴 시스템 프롬프트와 운영 규칙을 더 안정적으로 유지한다.
- 최근 프로젝트 상태, 단계별 결과, 오류 로그 요약을 더 많이 넣을 수 있다.
- HPSL 대본, Flow 프롬프트, 출처 요약을 한 대화 안에서 더 오래 보존할 수 있다.
- 도구 호출 후 반환되는 진단 결과를 더 풍부하게 읽을 수 있다.

그래도 피해야 할 것:

- 웹페이지 전문, 대량 로그, 긴 HTML, 전체 JSON DB를 그대로 모델에 주입하지 않는다.
- 한 번의 MCP 호출에서 이미지 생성/TTS/렌더링까지 길게 기다리지 않는다.
- Gemma4가 30k 컨텍스트를 갖더라도 작은 로컬 모델이라는 점은 변하지 않는다. 도구 선택은 단순해야 한다.

권장 반환량:

- 일반 진단: 4,000자 이하
- 단계 완료 보고: 2,000자 이하
- 오류 보고: 원인, 현재 단계, 다음 행동만 반환
- 전체 로그는 파일로 저장하고, 채팅에는 요약만 반환

## “툴을 쓰는 느낌” 제거 전략

기술적으로 LM Studio 모델은 OS 권한을 직접 갖지 않는다. 로컬 PC 제어는 반드시 로컬 프로세스가 제공하는 실행 인터페이스를 통해 일어난다.

하지만 사용자는 도구를 직접 부르지 않아도 된다. 목표는 다음과 같다.

```text
사용자 자연어
  -> Gemma4 agentic system prompt
  -> newauto-stepwise Agentic Control Hub
  -> workflow tools / operator fallback / desktop control
  -> 결과 요약만 사용자에게 보고
```

즉, MCP는 내부 손발이고, 사용자 UX는 “로컬 에이전트에게 말한다”에 가깝게 만든다.

## 샌드박스 없는 권한 방향

사용자는 OpenClaw처럼 샌드박스 규제 없이 쓰는 방향을 원한다.

현재 반영된 권한:

- `C:\Users\petbl\.lmstudio\mcp.json`에 `newauto-stepwise`, `openclaw-operator` 등록 완료
- `C:\Users\petbl\.lmstudio\settings.json`에 다음 confirmation skip 등록 완료
  - `mcp/newauto-stepwise:*`
  - `mcp/openclaw-operator:*`
- `openclaw-operator`는 PowerShell, 파일 읽기/쓰기, 디렉터리 조회, OS open, Flow 데스크톱 제어를 제공
- `newauto-stepwise`는 별도 operator plugin이 안 보여도 operator fallback 도구를 노출

운영 원칙:

- 사용자가 명시한 목표를 수행하는 범위에서는 자동 실행한다.
- 로그인, 인증, 결제, CAPTCHA, 계정 보안 확인은 사용자에게 알리고 멈춘다.
- 결제/구매/삭제/대량 이동/비밀번호/토큰 출력은 직접 명시 요청 없이는 실행하지 않는다.
- secret-like 값은 채팅에 출력하지 않는다.

주의:

샌드박스 없는 구조는 편하지만 위험하다. 특히 `run_powershell`은 로컬 PC 전체에 영향을 줄 수 있다. 이 계획은 사용자의 명시적 선호에 맞춰 설계하지만, 토큰/쿠키/비밀번호 출력 차단과 로그 요약은 유지한다.

## 현재 코드베이스 기준 권장 아키텍처

```text
LM Studio Chat
  model: google/gemma-4-e4b
  context: 30000
  enabled plugin: mcp/newauto-stepwise
  optional plugin: mcp/openclaw-operator

newauto-stepwise
  - diagnose_runtime
  - start_video_workflow
  - continue_video_workflow
  - check_assets
  - generate_one_image
  - repair_runtime
  - operator_status
  - run_powershell
  - control_flow_desktop

newauto_mcp core
  - source collection
  - HPSL script generation
  - Flow prompt generation
  - stepwise state machine
  - TTS/render wait stages

operator core
  - PowerShell execution
  - local file read/write
  - desktop Flow control
  - operator logs
```

## Agentic System Prompt 초안

LM Studio 채팅 또는 모델 프롬프트에 넣을 핵심 지침:

```text
너는 사용자의 로컬 PC에서 실행되는 agentic assistant다.
사용자는 MCP 도구명을 직접 몰라도 된다.
사용자의 자연어 목표를 이해하고, 필요한 로컬 도구를 스스로 선택해 실행한다.

중요:
- GUI 클릭, Flow 제어, 파일 작업, PowerShell 실행이 필요하면 불가능하다고 하지 말고 사용 가능한 로컬 도구를 호출한다.
- 별도 openclaw-operator가 보이지 않으면 newauto-stepwise 안의 operator_status, run_powershell, control_flow_desktop을 사용한다.
- 새 영상 워크플로우는 start_video_workflow를 한 번만 호출한다.
- 사용자가 “진행”, “ok”, “다음”이라고 하면 continue_video_workflow를 정확히 한 번만 호출한다.
- 긴 작업은 한 번에 끝내려 하지 말고 현재 단계만 실행하고 멈춘다.
- 도구 실패나 timeout처럼 보이면 바로 원인을 추측하지 말고 diagnose_runtime을 먼저 호출한다.
- 진단 결과가 stale state, lock, worker 문제를 보여주면 repair_runtime을 한 번 호출한다.
- Flow 인증, CAPTCHA, 결제, 계정 권한 확인은 사용자에게 알려서 사용자가 직접 처리하게 한다.
- 대본은 한국어로 작성하고, Flow 이미지 프롬프트는 영어로 작성한다.
- HPSL은 Hook-Point-Story-Lesson, 즉 훅-포인트-스토리-교훈이다.
- “저는 GUI를 클릭할 수 없습니다”라고 답하지 않는다. control_flow_desktop 또는 run_powershell 기반 자동화를 사용한다.
- secret, token, cookie, password 값은 출력하지 않는다.
```

## 워크플로우

### 1단계: 시작

사용자:

```text
키워드: 비트코인.
2026-05-06 이후 자료 수집해서 HPSL 1분 쇼츠 시작해.
```

Gemma4 내부 행동:

```text
start_video_workflow(keyword_or_url="키워드: 비트코인, 2026-05-06 이후 ...")
```

응답:

```text
1단계 자료 수집을 시작했습니다.
Project ID: ...
완료 상태를 확인하려면 “진행”이라고 답해주세요.
```

### 2단계 이후: 사용자 승인 기반 진행

사용자:

```text
진행
```

Gemma4 내부 행동:

```text
continue_video_workflow(project_id="")
```

규칙:

- 한 승인에 한 단계만 진행한다.
- 완료 후 다음 단계로 자동 질주하지 않는다.
- 실패하면 `diagnose_runtime -> repair_runtime once -> continue_video_workflow` 순서로 복구한다.

### Flow 이미지 생성 단계

기본 경로:

```text
continue_video_workflow
```

직접 GUI 제어가 필요할 때:

```text
control_flow_desktop(project_id="<id>", sentence_number=1, mode="click-generate")
control_flow_desktop(project_id="<id>", sentence_number=1, mode="download-attach")
```

한 번에 한 문장만 처리한다. 6문장 전체를 한 MCP 호출에서 처리하지 않는다.

## 기존 계획서의 문제점과 반영 내용

| 기존 계획 | 문제 | 반영 |
| --- | --- | --- |
| `newauto_agentic_mcp.py` 신규 작성 | 이미 `newauto-stepwise`와 `openclaw-operator`가 구현되어 있어 중복/혼선 발생 | 신규 서버 보류, `newauto-stepwise`를 Agentic Hub로 승격 |
| `execute_command`, `read_file`, `write_to_file` 같은 새 이름 제안 | 실제 구현 이름은 `run_powershell`, `read_text_file`, `write_text_file` | 실제 도구명 기준으로 계획 수정 |
| Playwright/CDP 브라우저 제어 중심 | Flow는 Playwright/CDP보다 데스크톱 좌표 제어가 더 안정적인 것으로 검증됨 | `flow_desktop_control.py`와 `control_flow_desktop` 우선 |
| 도구를 많이 늘리는 방향 | Gemma4 E4B는 도구가 많으면 선택이 흔들림 | 사용자는 자연어, 내부 도구는 `newauto-stepwise` 중심으로 제한 |
| 일반 웹 브라우징 agent 계획 | 현재 병목은 웹브라우징보다 Flow GUI/단계 timeout/도구 노출 문제 | 영상 워크플로우 안정화를 우선 |
| 컨텍스트 부족 전제 | 사용자가 30,000 컨텍스트로 운용 예정 | 긴 운영 프롬프트 가능, 하지만 반환량 제한은 유지 |

## 구현 체크리스트

이미 완료:

- [x] `newauto-stepwise` MCP 생성
- [x] `openclaw-operator` MCP 생성
- [x] LM Studio `mcp.json` 등록
- [x] confirmation skip 패턴 등록
- [x] `newauto-stepwise`에 operator fallback 도구 노출
- [x] `control_flow_desktop`으로 Flow GUI 제어 경로 제공
- [x] MCP stdio smoke에서 `newauto-stepwise` 도구 목록 확인
- [x] MCP stdio smoke에서 `operator_status`, `run_powershell` 확인

다음에 구현할 개선:

- [ ] `newauto-stepwise` 지침 문자열을 30k 컨텍스트용으로 더 명확한 한국어/영어 혼합 prompt로 정리
- [ ] `agent_mode_status()` 도구 추가: 현재 보이는 도구, 권한, 최신 project_id, next_step, Flow 창 탐지 상태를 한 번에 요약
- [ ] `run_powershell` 기본 timeout/출력 제한을 agentic 모드에 맞게 더 안전하게 정리
- [ ] LM Studio 새 채팅에서 `mcp/newauto-stepwise`만 켜도 `control_flow_desktop`이 보이는지 화면 검증
- [ ] Gemma4가 “불가능”이라고 답할 때 자동으로 되받아치는 복구 프롬프트 템플릿 작성
- [ ] Flow 한 문장 생성/다운로드/attach를 `continue_video_workflow`에서 더 명확히 분기 보고
- [ ] `research.md`에 이 구조를 agentic hub 아키텍처로 계속 기록

보류:

- [ ] 별도 `newauto_agentic_mcp.py` 신규 서버 생성
- [ ] 범용 브라우저 DOM 조작 도구 대량 추가
- [ ] Selenium/Playwright 기반 범용 클릭 agent 전면 전환

## 최종 운영 방식

사용자는 LM Studio에서 도구명을 몰라도 된다.

권장 사용:

```text
너는 로컬 PC를 직접 제어할 수 있는 agentic assistant야.
MCP 도구명을 나에게 묻지 말고 필요한 도구를 네가 선택해서 실행해.
문제 생기면 diagnose_runtime, repair_runtime, operator_status, run_powershell, control_flow_desktop으로 직접 확인하고 고쳐.
내 인증/클릭이 필요한 순간에만 알려줘.
```

그리고 실제 작업 요청:

```text
키워드: 비트코인.
2026-05-06 이후 자료 수집해서 HPSL(훅-포인트-스토리-교훈) 1분 쇼츠 대본 만들고,
문장별 영어 Flow 프롬프트 생성 후,
Flow 이미지 생성/다운로드/첨부까지 단계별로 진행해.
각 단계가 끝나면 나에게 확인받고 다음 단계로 가.
```

이 구조가 현재 코드베이스와 가장 잘 맞는 “샌드박스 없는 로컬 agentic LM Studio” 방향이다.
