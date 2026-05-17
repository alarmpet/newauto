# Cline Flow 인증 루프 실패 원인 분석 및 복구 계획

작성 시각: 2026-05-14

## 결론

이번 실패의 1차 원인은 Google Flow 로그인이 아니다. Flow는 이미 브라우저에서 열렸고, stepwise 상태도 `flow_auth`에서 `flow_generate`로 넘어갔다. 실제로 멈춘 지점은 Cline의 로컬 모델 실행층이다.

Cline 콘솔 오류는 다음을 가리킨다.

- provider: `lmstudio`
- model: `qwen/qwen3.5-9b`
- 증상: `Please check the LM Studio developer logs`, `load the model with a larger context length`, `Auto-Retry Failed`

즉, 사용자가 브라우저에서 이미 로그인했더라도, "진행" 이후 도구를 호출해야 하는 Cline/Qwen 쪽이 응답을 만들지 못해 같은 인증 대기 화면으로 되돌아오는 것처럼 보인다.

## 확인된 증거

### 1. stepwise 상태

파일: `storage/stepwise_workflows/0cd26b0c8746.json`

- `project_id`: `0cd26b0c8746`
- `next_step`: `flow_generate`
- `updated_at`: `2026-05-14T12:01:25`

이 값은 인증 대기 단계가 이미 지나갔다는 뜻이다. 로그인 자체가 계속 실패했다면 `flow_auth`에 남아 있어야 한다.

### 2. Flow 브라우저 로그

파일: `storage/logs/flow_browser_0cd26b0c8746.log`

- `Clicked Flow new project button via DOM text.`
- `Opened Flow browser for user authentication.`

여기에는 Generate 입력/클릭 실패 로그가 없다. 즉, 브라우저 자동화가 Generate까지 가서 실패한 것이 아니라, 인증 이후 Cline이 다음 도구 호출을 안정적으로 이어가지 못한 상태다.

### 3. LM Studio 건강 체크

명령:

```powershell
C:\Users\petbl\local-rag\.venv\Scripts\python.exe scripts\check_cline_lmstudio_health.py --json-output
```

결과 핵심:

- `loaded`: `true`
- `loaded_context_length`: `72000`
- `context_target`: `131072`
- `context_target_met`: `false`
- 대형 Cline task 존재: `6.3MB`, `4.75MB`, `3.17MB` 등

현재 Qwen은 켜져 있지만 이 워크플로우가 요구하는 컨텍스트 설정보다 작게 로드되어 있다. 게다가 실패한 Cline 태스크에는 거대한 브라우저 스크린샷/base64/로그가 섞여 있어, Retry를 누를수록 같은 모델 응답 실패가 반복될 가능성이 높다.

## 왜 계속 같은 작업에서 실패하는가

1. 사용자는 Flow 로그인/권한 승인을 끝냈다.
2. newauto stepwise는 상태를 `flow_generate`로 바꿨다.
3. 그런데 Cline의 현재 태스크 컨텍스트가 이미 너무 커졌고, LM Studio Qwen은 72k 컨텍스트로 떠 있다.
4. Cline이 `continue_video_workflow` 같은 다음 MCP 도구 호출을 구성하기 전에 LM Studio 응답이 깨진다.
5. Cline UI에는 마지막 정상 안내였던 "Flow 인증 필요, 진행이라고 말해줘"만 남아 사용자에게 로그인 루프처럼 보인다.

따라서 여기서 Retry를 누르는 것은 해결책이 아니다. 같은 비대한 태스크와 같은 72k 컨텍스트로 다시 시도하기 때문에 같은 실패가 반복된다.

## 즉시 복구 절차

### 1. 실패한 Cline 태스크에서 Retry 금지

현재 실패한 Cline 대화에는 대형 screenshot/base64와 긴 로그가 들어가 있다. 같은 태스크에서 Retry하지 말고, 새 Cline 태스크를 열어 최소 정보만 넘긴다.

새 태스크에 넣을 최소 문장:

```text
project_id=0cd26b0c8746
현재 stepwise next_step=flow_generate
Flow 로그인은 완료됨. 같은 실패 태스크를 retry하지 말고 continue_video_workflow를 정확히 1회 호출해줘.
먼저 check_cline_lmstudio_health.py 결과에서 context_target_met를 확인하고, false면 모델을 131072 context로 다시 로드해줘.
```

### 2. Qwen 모델을 목표 컨텍스트로 다시 로드

현재 상태:

- context: `72000`
- target: `131072`

권장 명령:

```powershell
C:\Users\petbl\.lmstudio\bin\lms.exe unload qwen/qwen3.5-9b
C:\Users\petbl\.lmstudio\bin\lms.exe load qwen/qwen3.5-9b --context-length 131072 --parallel 1 --gpu max --identifier qwen/qwen3.5-9b -y
```

그 다음 확인:

```powershell
C:\Users\petbl\local-rag\.venv\Scripts\python.exe C:\Users\petbl\newauto\scripts\check_cline_lmstudio_health.py --json-output
```

통과 기준:

- `ok=true`
- `context_target_met=true`
- `loaded_context_length >= 131072`

### 3. 새 compact 태스크에서 workflow만 이어가기

성공 조건이 확인되면 다음 중 하나만 실행한다.

MCP 도구가 보이면:

```text
continue_video_workflow(project_id="0cd26b0c8746")
```

MCP가 불안정하면 one-shot CLI:

```powershell
C:\Users\petbl\local-rag\.venv\Scripts\python.exe C:\Users\petbl\newauto\scripts\newauto_stepwise_mcp.py --action continue_video_workflow --project-id 0cd26b0c8746
```

주의: 한 번에 여러 번 반복 호출하지 않는다. Flow Generate는 한 단계씩 상태와 산출물을 확인해야 한다.

## 재발 방지 계획

### P0. Cline 실패 태스크 재시도 차단

`.clinerules`에는 이미 다음 원칙이 있다.

- `Please check the LM Studio developer logs`
- `load the model with a larger context length`
- `Auto-Retry Failed`

이 메시지가 나오면 Retry를 누르지 않고 `check_cline_lmstudio_health.py --json-output`를 먼저 실행한다.

보완할 점:

- Cline 사용자 안내에 "Retry 금지, 새 compact task 시작"을 더 강하게 표시한다.
- 대형 screenshot/base64가 포함된 태스크는 workflow continuation에 재사용하지 않는다.

### P1. stepwise wrapper에 LM Studio preflight 강화

`continue_video_workflow` 진입 전에 다음을 검사한다.

- LM Studio API 접근 가능 여부
- `qwen/qwen3.5-9b` loaded 여부
- `loaded_context_length >= 131072` 여부
- Cline task size가 큰 경우 경고

`context_target_met=false`이면 Flow 인증 안내 대신 다음처럼 명확히 중단한다.

```text
Flow 로그인 문제가 아닙니다.
LM Studio qwen/qwen3.5-9b가 72000 context로 로드되어 있어 Cline 도구 호출이 실패할 수 있습니다.
모델을 131072 context로 다시 로드한 뒤 새 compact task에서 continue_video_workflow를 호출하세요.
```

### P2. Flow 인증 상태와 Cline 실행 상태를 분리해서 보고

현재 안내는 "Flow 인증 완료 후 진행"만 강조해서, Cline 모델 실패도 로그인 문제처럼 보인다.

개선 보고 형식:

- Flow browser state: opened/auth required/auth likely complete/generate attempted
- stepwise state: `flow_auth` 또는 `flow_generate`
- Cline/LM Studio state: model loaded/context target/tool response ok
- next action: user login 필요 또는 local model reload 필요 또는 continue 가능

### P3. 대형 브라우저 이미지 컨텍스트 차단

이번 Cline 태스크에는 거대한 browser screenshot payload가 들어갔다. 이는 로컬 Qwen에게 특히 치명적이다.

운영 규칙:

- Flow UI 확인은 가능하면 DOM/status/log로 한다.
- 스크린샷 분석이 필요하면 local Qwen에 넣지 않고 `analyze_browser_screenshot` 또는 OpenRouter vision path를 쓴다.
- Cline 채팅에는 base64 이미지를 붙이지 않는다.

## 검증 체크리스트

1. `check_cline_lmstudio_health.py --json-output`
   - `context_target_met=true`
2. `storage/stepwise_workflows/0cd26b0c8746.json`
   - `next_step=flow_generate`
3. `continue_video_workflow` 1회 호출
4. `storage/projects/0cd26b0c8746/flow_generated` 또는 media asset 증가 확인
5. 실패 시 `diagnose_runtime` -> `forensic_diagnose` 순서로 확인
6. 같은 blocker가 3회 반복되면 `ask_openrouter_subagent(mode="debug")`

## 핵심 운영 문장

이번 건은 "Flow 로그인이 안 됨"이 아니라 "Flow 인증 이후 Cline/Qwen 실행 컨텍스트가 무너져 다음 도구 호출을 못 함"이다. 해결은 브라우저 재로그인이 아니라 LM Studio 컨텍스트 재로드와 새 compact Cline 태스크에서의 단일 `continue_video_workflow` 호출이다.

---

## Antigravity 의견 검토 반영

검토 대상: `cline-flow-auth-loop-opinion-antigravity.md`

### 반영 판단 요약

Antigravity 의견의 핵심 판단은 기존 계획서와 일치한다. 특히 "Flow 인증 실패"가 아니라 "이전 단계에서 누적된 비대한 Cline 컨텍스트와 72k로 로드된 Qwen 모델이 만나 LM Studio 응답 실패가 난 것"이라는 분석은 채택한다.

추가로 채택할 내용은 다음 네 가지다.

1. `continue_video_workflow` 실행 전 LM Studio context hard block
2. local Qwen으로 base64 screenshot을 직접 넘기지 않는 규칙 강화
3. 실패한 Cline task 격리와 fresh compact task 절차를 운영 표준으로 승격
4. Flow 인증 상태, workflow 상태, LLM runtime 상태를 분리해서 보고

보류할 내용은 없다. 다만 OpenRouter Vision 사용은 "모든 screenshot은 무조건 외부 분석"이 아니라, DOM/status/log로 확인이 불가능한 GUI 상태에만 제한해서 쓴다. 비용과 rate limit이 있고, 현재 문제의 1차 복구는 LM Studio context 재로드이기 때문이다.

## 업데이트된 실행 계획

### P0. `continue_video_workflow` 진입 전 LM Studio hard block

현재 `scripts/newauto_stepwise_mcp.py`에는 `_lmstudio_context_metadata()`가 있고, `diagnose_runtime`에서는 관련 metadata를 보여준다. 하지만 `continue_video_workflow` 자체는 `context_target_met=false`여도 계속 진행할 수 있다.

이 부분을 hard block으로 바꾼다.

구현 위치:

- `scripts/newauto_stepwise_mcp.py`
- `continue_video_workflow(project_id="")` 최상단

동작:

1. `_lmstudio_context_metadata()` 호출
2. `lmstudio_api_ok=false`이면 workflow 진행 중단
3. `loaded_model`이 비어 있거나 `qwen/qwen3.5-9b`가 아니면 진행 중단
4. `loaded_context_length < LMSTUDIO_CONTEXT_TARGET`이면 진행 중단
5. 반환 메시지에 "Flow 로그인 문제가 아님"을 명시

권장 반환 메시지:

```text
Flow 로그인 문제가 아닙니다.
LM Studio qwen/qwen3.5-9b가 현재 72000 context로 로드되어 있고, 요구값은 131072입니다.
이 상태에서는 Cline이 다음 MCP 도구 호출을 만들기 전에 응답 실패/Retry 루프가 재발할 수 있어 continue_video_workflow를 중단했습니다.

다음 명령으로 모델을 다시 로드한 뒤 새 compact Cline task에서 다시 진행하세요.
C:\Users\petbl\.lmstudio\bin\lms.exe unload qwen/qwen3.5-9b
C:\Users\petbl\.lmstudio\bin\lms.exe load qwen/qwen3.5-9b --context-length 131072 --parallel 1 --gpu max --identifier qwen/qwen3.5-9b -y
```

검증:

```powershell
C:\Users\petbl\local-rag\.venv\Scripts\python.exe scripts\check_cline_lmstudio_health.py --json-output
```

통과 기준:

- `ok=true`
- `model.context_target_met=true`
- `model.loaded_context_length >= 131072`

### P1. 상태 리포트 3분리

`diagnose_runtime`과 향후 workflow 안내는 다음 세 상태를 분리해서 보여줘야 한다.

```text
Workflow State:
- project_id
- next_step
- asset_coverage

Browser/Flow State:
- Flow browser opened/auth required/auth likely complete/ready_for_generation/generate attempted
- latest Flow log excerpt

LLM Runtime State:
- lmstudio_api_ok
- loaded_model
- loaded_context_length
- context_target
- context_target_met
```

목표는 사용자가 "또 로그인하라는 건가?"로 이해하지 않게 만드는 것이다. `next_step=flow_generate`인데 `context_target_met=false`라면 메시지의 주어는 Flow가 아니라 LM Studio여야 한다.

### P2. base64 screenshot 차단 규칙 강화

이번 실패 태스크에는 대형 browser screenshot/base64 payload가 들어갔다. local Qwen에게는 이 자체가 failure amplifier다.

운영 규칙:

- Cline 채팅에 `data:image/...;base64` payload를 붙이지 않는다.
- Flow GUI 상태 확인은 우선 `storage/logs/flow_browser_<project_id>.log`, stepwise JSON, DOM/status 결과로 한다.
- 화면 판단이 꼭 필요하면 screenshot 파일 경로만 넘기고 `analyze_browser_screenshot`을 사용한다.
- OpenRouter Vision 결과도 원문 이미지가 아니라 짧은 text facts packet으로 local Qwen에 전달한다.

계획서 기준 문장:

```text
브라우저 screenshot은 local Qwen의 직접 입력이 아니라 외부 vision 분석 또는 파일 경로 기반 진단의 대상이다. Cline 대화에는 base64 이미지를 남기지 않는다.
```

### P3. 실패 task 격리와 compact task 표준화

다음 오류가 나오면 같은 Cline task에서 Retry하지 않는다.

- `Please check the LM Studio developer logs`
- `load the model with a larger context length`
- `Auto-Retry Failed`
- `Invalid API Response`
- assistant message 없음 또는 tool call 생성 전 중단

표준 복구 절차:

1. 실패한 task에서 멈춘다.
2. `check_cline_lmstudio_health.py --json-output`를 실행한다.
3. `context_target_met=false`이면 모델을 131072로 재로드한다.
4. 새 Cline task를 만든다.
5. 새 task에는 project id, next step, 마지막 concise error만 넣는다.
6. `continue_video_workflow`를 정확히 1회만 호출한다.

새 task 템플릿:

```text
project_id=0cd26b0c8746
next_step=flow_generate
Flow 로그인/권한 승인은 완료된 상태다.
이전 Cline task는 LM Studio context failure로 중단됐으니 retry하지 않는다.
먼저 check_cline_lmstudio_health.py 결과를 확인하고 context_target_met=true일 때 continue_video_workflow를 정확히 1회 호출해줘.
```

### P4. `.clinerules` 및 wrapper instruction 반영 후보

계획서 반영 이후 실제 코드/규칙 업데이트 후보:

- `.clinerules`
  - LM Studio context failure 발생 시 Retry 금지 문구를 더 앞쪽으로 승격
  - base64 screenshot 금지 문구를 "권장"이 아니라 "금지"로 강화
  - fresh compact task 템플릿 추가

- `scripts/newauto_stepwise_mcp.py`
  - `continue_video_workflow` hard block
  - `diagnose_runtime`의 agentic metadata를 user-facing summary로도 분리 출력
  - `STEPWISE_INSTRUCTIONS`에 "context_target_met=false면 Flow 인증 안내를 반복하지 말 것" 추가

- `scripts/check_cline_lmstudio_health.py`
  - 현재 기능은 충분하다.
  - 향후 선택 사항: `--fail-fast-message` 같은 사람이 읽기 쉬운 Korean summary 모드 추가

## 업데이트된 우선순위

1. 즉시: LM Studio `qwen/qwen3.5-9b`를 131072 context로 재로드하고 새 compact task에서 진행
2. P0 코드: `continue_video_workflow`에 context hard block 추가
3. P1 운영: 상태 리포트를 Workflow/Browser/LLM Runtime으로 분리
4. P2 규칙: base64 screenshot local Qwen 직접 전달 금지
5. P3 문서: `.clinerules`와 wrapper instruction에 Retry 금지 및 compact task 템플릿 추가

## 업데이트된 성공 기준

이 문제가 해결됐다고 보려면 다음이 모두 충족되어야 한다.

- `check_cline_lmstudio_health.py --json-output`에서 `ok=true`
- `continue_video_workflow`가 `context_target_met=false` 상태에서 Flow 인증 안내를 반복하지 않고 명확히 중단
- `next_step=flow_generate`일 때 사용자가 재로그인 요구를 받지 않음
- 실패한 Cline task를 Retry하지 않고 새 compact task로 이어가는 절차가 문서와 규칙에 반영됨
- Cline 대화에 base64 screenshot이 남지 않음

## 2026-05-14 구현 반영 상태

반영 완료:

- `scripts/newauto_stepwise_mcp.py`
  - `continue_video_workflow` 진입 전 LM Studio context hard block 추가
  - `context_target_met=false`일 때 Flow 인증 안내를 반복하지 않고 LM Studio context 문제로 명확히 중단
  - Workflow/Browser/LLM Runtime 상태를 `separated_state_summary`로 분리 출력
  - browser screenshot base64를 local Qwen에 직접 전달하지 말라는 wrapper instruction 추가

- `.clinerules`
  - `context_target_met=false`를 Flow 로그인 실패로 해석하지 말라는 규칙 추가
  - 실패한 Cline task Retry 금지와 fresh compact task 템플릿 추가
  - `data:image/...;base64` screenshot을 local Qwen/Cline chat에 붙이지 말라는 규칙 추가

검증 완료:

```powershell
C:\Users\petbl\local-rag\.venv\Scripts\python.exe -m py_compile scripts\newauto_stepwise_mcp.py
```

현재 LM Studio가 의도적으로 `loaded_context_length=72000` 상태이므로, hard block 검증도 통과했다.

```text
Flow login is not the blocker.
LM Studio model context is insufficient, so continue_video_workflow was blocked before retrying Flow.
loaded_model: qwen/qwen3.5-9b
loaded_context_length: 72000
required_context_length: 131072
```

추가 확인:

- `Workflow State`: `next_step=flow_generate`, `asset_coverage=0/6`
- `Browser/Flow State`: Flow 창 감지됨, 최근 Flow 로그 포함
- `LLM Runtime State`: `context_target_met=false`

다음 실제 진행 조건:

1. LM Studio에서 `qwen/qwen3.5-9b`를 131072 context로 재로드
2. `check_cline_lmstudio_health.py --json-output`에서 `ok=true` 확인
3. 새 compact Cline task에서 `project_id=0cd26b0c8746`, `next_step=flow_generate`만 넘겨 `continue_video_workflow` 1회 호출
