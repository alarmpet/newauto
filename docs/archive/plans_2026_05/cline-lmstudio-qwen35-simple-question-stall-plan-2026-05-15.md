# Cline + LM Studio + Qwen3.5 Simple Question Stall Diagnosis Plan

작성 시각: 2026-05-15 01:20 KST

## 결론

`넌 어떤 llm 모델이야?` 같은 단순 질문에도 Cline이 몇 분 동안 답하지 못한 직접 원인은 Qwen3.5의 지식 부족이 아니라, **LM Studio가 이미 거대한 Cline 프롬프트를 처리 중인 `PROCESSINGPROMPT` 상태에 묶여 새 요청을 처리하지 못하는 것**이다.

현재 확인된 상태:

- Cline provider: `lmstudio`
- Cline model: `qwen/qwen3.5-9b`
- LM Studio loaded context: `131072`
- LM Studio max context: `262144`
- LM Studio status: `PROCESSINGPROMPT`
- 직접 `/v1/chat/completions` 단순 질문 테스트: 45초 timeout
- 최근 Cline task `1778775024857`: 질문은 짧지만 Cline이 repo 파일 목록, 열린 탭, 환경 정보, task progress 권장문까지 붙여 큰 프롬프트로 전송

즉 문제는 "모델 이름을 모름"이 아니라 **Cline이 짧은 질문도 거대한 환경 프롬프트로 감싸서 보내고, LM Studio/Qwen이 그 프롬프트 처리를 끝내지 못해 응답이 멈추는 구조**다.

## 확인한 증거

### 1. LM Studio health

실행:

```powershell
C:\Users\petbl\local-rag\.venv\Scripts\python.exe scripts\check_cline_lmstudio_health.py --json-output
```

핵심 결과:

```json
{
  "ok": true,
  "loaded": true,
  "loaded_context_length": 131072,
  "context_target_met": true,
  "lms_ps": "qwen/qwen3.5-9b ... PROCESSINGPROMPT ... CONTEXT 131072 PARALLEL 1"
}
```

해석:

- 이전에 있던 `72000 < 131072` 컨텍스트 부족 문제는 현재는 해결되어 있다.
- 그런데 모델 상태가 `PROCESSINGPROMPT`로 계속 묶여 있다.
- 따라서 지금 병목은 "컨텍스트 길이 부족"보다 "긴 프롬프트 처리/큐 고착"이다.

### 2. 단순 질문 직접 호출 재현

실행:

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:1234/v1/chat/completions' `
  -Method Post `
  -ContentType 'application/json' `
  -Body '{"model":"qwen/qwen3.5-9b","messages":[{"role":"user","content":"너는 어떤 모델이야? 한 문장으로 답해."}],"max_tokens":64,"temperature":0}' `
  -TimeoutSec 45
```

결과:

```text
ERROR: WebException: The request was aborted: The operation has timed out.
```

해석:

- Cline을 거치지 않은 직접 API 호출도 timeout이다.
- LM Studio 서버 또는 모델 런타임이 이미 이전 요청 처리에 잡혀 있거나 큐가 막힌 상태다.

### 3. Cline task payload 확인

최근 task:

```text
C:\Users\petbl\AppData\Roaming\Code\User\globalStorage\saoudrizwan.claude-dev\tasks\1778775024857
```

파일:

- `api_conversation_history.json`: 9,791 bytes
- `ui_messages.json`: 10,807 bytes
- `task_metadata.json`: 448 bytes

짧은 사용자 질문:

```text
뭐 어떤 llm 모델이야?
```

하지만 Cline이 LM Studio에 보낸 요청에는 다음이 같이 포함됨:

- `task_progress RECOMMENDED`
- VS Code visible files
- Open tabs 전체
- Current time
- Current working directory file list
- Workspace configuration
- Detected CLI tools
- Context Window Usage
- Current Mode

문제 포인트:

- 질문 자체는 10토큰 수준인데 실제 프롬프트는 수천~수만 토큰이 된다.
- repo 루트에 계획서 markdown이 매우 많고 열린 탭도 많아 환경 정보가 비대하다.
- 이전 더 큰 task들에는 6.3MB, 4.75MB, 3.17MB task가 남아 있다.

### 4. 기존 코드와 규칙의 현재 상태

이미 구현된 방어:

- `.clinerules`에는 131072 context 요구, Retry 금지, fresh compact task 사용, base64 screenshot 금지 규칙이 있다.
- `scripts/check_cline_lmstudio_health.py`는 LM Studio API, loaded context, 큰 Cline task를 진단한다.
- `scripts/ensure_lmstudio_context.ps1`는 모델을 131072 context로 로드한다.
- `scripts/newauto_stepwise_mcp.py`의 `continue_video_workflow()`는 `_lmstudio_continue_block_message()`로 context 부족 시 workflow 진입을 막는다.

부족한 방어:

- 모델이 `PROCESSINGPROMPT`로 장시간 묶인 상태를 hard fail로 판단하지 않는다.
- 직접 API ping이 timeout인 상태를 "Cline이 답을 못함"으로만 보게 되어 있다.
- Cline의 단순 질문까지 task progress/environment dump가 붙는 것을 repo 측에서 줄일 수 없다.
- `.clineignore`가 `storage/`, `data/`, `research.md`, `browser_use_quickstart.html`은 막지만, 루트의 대량 계획서 markdown과 garbled `issue.md`는 계속 환경 후보에 남는다.
- `prompts/model_profiles.md`는 아직 `Current context target: 65536`이라고 적혀 있어 `.clinerules`의 131072와 충돌한다.

## 근본 원인

### 원인 A. LM Studio 런타임 고착

`lms ps`가 `PROCESSINGPROMPT`인 동안 새 요청이 45초 안에 처리되지 않는다. `parallel=1`이므로 이전 요청 하나가 길게 물리면 이후 단순 질문도 대기한다.

### 원인 B. Cline의 기본 요청 포장 비용

Cline은 짧은 질문에도 environment details와 task progress 권장문을 붙인다. 로컬 9B Q4 모델에는 이 프롬프트 라우팅 비용이 크다.

### 원인 C. repo 표면적이 너무 넓음

루트에 계획서/진단서 markdown이 많다. Cline 환경 프롬프트의 file list가 길어지고, 열린 탭까지 많으면 매 요청의 입력 토큰이 불필요하게 증가한다.

### 원인 D. 인코딩 손상 문서

`issue.md`, 일부 계획서, `STEPWISE_INSTRUCTIONS`의 한국어가 mojibake로 깨져 있다. 로컬 Qwen은 깨진 한글을 의미 있는 지침으로 해석하려고 하면서 토큰과 판단력을 낭비할 수 있다.

### 원인 E. 규칙 간 충돌

`prompts/model_profiles.md`는 65536, `.clinerules`와 health script는 131072를 기준으로 한다. 운영 기준이 여러 문서에서 다르면 Cline/Qwen이 상황을 잘못 판단할 수 있다.

## 즉시 복구 절차

### 1. 현재 LM Studio 요청 고착 해제

가장 빠른 복구:

```powershell
C:\Users\petbl\.lmstudio\bin\lms.exe unload qwen/qwen3.5-9b
C:\Users\petbl\.lmstudio\bin\lms.exe load qwen/qwen3.5-9b --context-length 131072 --parallel 1 --gpu max --identifier qwen/qwen3.5-9b -y
```

또는 repo wrapper:

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\petbl\newauto\scripts\ensure_lmstudio_context.ps1
```

검증:

```powershell
C:\Users\petbl\local-rag\.venv\Scripts\python.exe C:\Users\petbl\newauto\scripts\check_cline_lmstudio_health.py --json-output
```

성공 기준:

- `ok=true`
- `context_target_met=true`
- `lms_ps`가 장시간 `PROCESSINGPROMPT`에 머물지 않음

### 2. 실패한 Cline task에서 Retry 금지

`Please check the LM Studio developer logs`, `Auto-Retry Failed`, timeout이 나온 task는 같은 창에서 Retry하지 않는다.

새 Cline task에는 최소 문장만 넣는다:

```text
LM Studio qwen/qwen3.5-9b 131072 context 재로드 완료.
먼저 "너는 어떤 모델이야?"에 한 문장으로만 답해.
도구 호출/계획서/파일 탐색 금지.
```

예상 답:

```text
나는 LM Studio에서 실행 중인 qwen/qwen3.5-9b 모델입니다.
```

### 3. VS Code 열린 탭 줄이기

Cline prompt에 열린 탭 목록이 들어간다. 단순 질문/복구 전에는 탭을 최소화한다.

권장:

- `issue.md` 하나만 열기
- 대형 계획서, `research.md`, `timeline.md`, generated prompt 파일 탭 닫기
- Cline 실패 task는 새 compact task로 교체

## 코드/설정 개선 계획

### P0. health script에 `PROCESSINGPROMPT` hard warning 추가

대상:

- `scripts/check_cline_lmstudio_health.py`

현재는 context만 보고 `ok=true`가 된다. 하지만 지금처럼 `PROCESSINGPROMPT`로 새 요청이 timeout이면 `ok=true`가 오해를 만든다.

수정:

- `lms ps` output에서 status를 parse
- status가 `PROCESSINGPROMPT`이고 smoke chat이 timeout이면 `ok=false`
- advice에 `unload/load` 또는 `server restart`를 제시

추가 smoke:

```powershell
C:\Users\petbl\local-rag\.venv\Scripts\python.exe scripts\check_cline_lmstudio_health.py --json-output --smoke-chat
```

성공 기준:

- 단순 chat completion이 10~15초 안에 응답
- timeout이면 `ok=false`

### P1. emergency reset script 추가

대상:

- 새 파일: `scripts/reset_lmstudio_qwen.ps1`

역할:

1. `lms ps` 출력
2. `qwen/qwen3.5-9b` unload
3. 필요하면 `lms server stop/start`
4. 131072 context로 load
5. 단순 chat smoke 실행

이유:

- 사용자가 매번 unload/load 명령을 기억할 필요가 없다.
- `PROCESSINGPROMPT` 고착과 context 부족을 한 번에 복구한다.

### P2. `.clineignore` 확장

현재 제외:

- `storage/`, `data/`, `node_modules/`, `research.md`, `browser_use_quickstart.html`

추가 권장:

```gitignore
# Historical planning docs that should not inflate Cline context by default
*-plan.md
*-review.md
timeline.md

# Temporary prompt scratch files
temp_prompts/

# Large/encoding-damaged operational log unless explicitly opened
issue.md
```

주의:

- `issue.md`를 Cline 워크플로우 지침으로 계속 쓸 거면 제외하지 말고, 먼저 UTF-8 정상 문서로 복구해야 한다.
- 제외 후에도 명시적으로 파일을 열면 Cline이 볼 수 있다.

### P3. `issue.md` 인코딩 복구 또는 폐기

현재 `issue.md`는 터미널에서 mojibake로 보인다. Cline/Qwen이 이 파일을 지침으로 읽으면 성능과 판단 모두 나빠진다.

조치:

1. 원본 정상 한글이 있으면 UTF-8로 재저장
2. 원본이 없으면 핵심 운영 규칙만 새 문서로 재작성
3. 손상된 기존 파일은 `docs/archive/issue.mojibake.md`로 옮김
4. `.clinerules`에는 새 정상 문서만 참조

### P4. model profile 기준 통일

대상:

- `prompts/model_profiles.md`

현재:

```text
Current context target: 65536
```

수정:

```text
Current context target: 131072
```

또는 더 정확히:

```text
Current context target: 131072 for workflow recovery; use shorter fresh tasks for simple Q&A.
```

### P5. Cline simple question profile 추가

문제:

- 단순 질문에도 Cline이 도구/계획/환경 전체를 붙인다.

운영 규칙 추가:

```text
If the user asks a simple identity/config question such as "넌 어떤 모델이야?", answer directly from visible provider/model metadata. Do not inspect files, create todos, call MCP, or read issue.md.
```

이 규칙은 `.clinerules` 상단에 있어야 한다. 아래쪽 workflow 규칙보다 우선 적용되어야 한다.

### P6. workflow MCP는 context뿐 아니라 runtime busy도 차단

대상:

- `scripts/newauto_stepwise_mcp.py`

현재:

- `context_target_met=false`면 `continue_video_workflow` 차단

추가:

- LM Studio가 busy이고 smoke ping이 timeout이면 workflow 도구 진입 전 차단
- 메시지:

```text
LM Studio is busy processing a previous prompt. This is not a Flow/workflow failure.
Do not retry this Cline task. Reset LM Studio or start a fresh compact task.
```

## 검증 체크리스트

1. `lms ps`
   - `qwen/qwen3.5-9b`
   - `CONTEXT 131072`
   - 장시간 `PROCESSINGPROMPT` 고착 없음
2. 직접 LM Studio smoke:
   - `너는 어떤 모델이야?`
   - 10~15초 안에 한 문장 응답
3. 새 Cline task:
   - 도구 호출 없이 모델명 질문에 즉답
4. `check_cline_lmstudio_health.py --json-output`
   - context OK뿐 아니라 runtime busy 여부를 표시
5. `.clineignore`
   - 큰 히스토리 문서와 temp/generated 파일이 기본 file list를 부풀리지 않음
6. `issue.md`
   - 정상 UTF-8이거나 workflow 기본 참조에서 제외

## 사용자에게 바로 줄 입력값

LM Studio가 멈췄을 때:

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\petbl\newauto\scripts\ensure_lmstudio_context.ps1
```

그 다음 새 Cline task:

```text
도구 쓰지 말고 한 문장으로만 답해. 넌 어떤 모델이야?
```

정상 답:

```text
나는 LM Studio에서 실행 중인 qwen/qwen3.5-9b 모델입니다.
```

## 우선순위

1. 즉시: LM Studio unload/load로 `PROCESSINGPROMPT` 해제
2. 즉시: 실패한 Cline task Retry 금지, 새 compact task 사용
3. P0: health script에 smoke chat 및 busy 판정 추가
4. P2/P3: `.clineignore`와 `issue.md` 정리로 프롬프트 비대화 차단
5. P4/P5: 문서와 규칙 충돌 제거, 단순 질문 direct-answer 규칙 추가
6. P6: workflow MCP에도 busy hard block 추가

