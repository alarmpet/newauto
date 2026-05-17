# Cline Agentic Performance Recovery Plan

작성일: 2026-05-12

## 0.1 Antigravity Review 반영

검토 문서:

```text
cline-agentic-performance-recovery-plan-review-antigravity-2026-05-12.md
```

반영 결론:

- 리뷰의 종합 판단에 동의한다. 현재 병목은 더 큰 추론 모델의 부재보다, Cline이 로컬 worker 실패를 확정 진단하고 닫힌 복구 루프로 처리하지 못하는 구조 문제다.
- `forensic_doctor.py`에는 서버/프로세스 점검은 있으나 TTS worker heartbeat, DB job state, 산출물 존재 여부를 critical finding으로 묶는 기능이 부족하다. 이 부분을 P0 핵심 작업으로 격상한다.
- `repair_runtime`은 stale lock 제거 수준에 머물 수 있으므로, TTS에 대해서는 idempotent한 `repair_tts`를 별도 도구로 분리하거나 동등한 전용 branch를 추가한다.
- `continue_video_workflow`의 wait repeat guard는 Cline 지침에만 맡기지 않고 MCP/core 상태 파일에 저장되는 카운터로 강제한다.
- OpenRouter subagent에는 전체 로그나 민감 파일을 보내지 않고, `forensic_diagnose`의 `critical_findings`와 `recommended_actions`에서 추출한 local facts packet만 전달한다.
- `.clinerules`의 Mandatory Escalation 규칙은 기존 Recovery Loop보다 우선 적용되도록 문서 상단부에 배치한다.

## 0. 결론

현재 문제는 `google/gemma-4-e4b`의 단순 성능 부족만이 아니다. 더 큰 원인은 Cline이 다음 세 가지를 안정적으로 구분하지 못하는 데 있다.

1. LLM 추론 문제: 원인 분석, 계획, 리뷰가 필요한 상황
2. 로컬 런타임 문제: TTS worker, render worker, locks, DB state, subprocess 문제
3. 외부 provider 문제: OpenRouter free model upstream rate limit, model fallback, budget 문제

OpenRouter 32B급 모델을 붙여도 Cline이 그 모델을 호출하지 않거나, TTS 같은 로컬 워커 문제를 OpenRouter로 해결하려 하면 성능 개선 효과가 거의 없다. 따라서 목표는 "더 큰 모델 하나 연결"이 아니라 **작은 로컬 모델을 실행 담당자로 두고, OpenRouter subagent를 강제 라우팅되는 진단/리뷰 두뇌로 쓰는 구조**로 바꾸는 것이다.

## 1. 현재 증상

확인된 문제:

- Cline이 `tts_wait` 정지를 OpenRouter 연결 문제처럼 해석한다.
- `continue-video-workflow`를 반복 호출하면서 같은 대기 상태를 되풀이한다.
- 이미 `.clinerules`에 OpenRouter 규칙이 있지만, 실제 행동은 `ask_openrouter_subagent` 호출로 이어지지 않는다.
- `repair_runtime`은 stale lock 정리 중심이고, TTS job 재큐잉/worker 재시작/프로세스 충돌 해소까지 충분히 닫힌 복구 루프가 아니다.
- OpenRouter 429를 "계정 한도 초과"로 오해할 수 있다. 실제로는 `google/gemma-4-31b-it:free`의 Google AI Studio upstream temporary rate limit일 수 있다.
- 기존 계획 문서 일부가 인코딩 깨짐 상태라 Cline이 문서 기반으로 정확히 학습하기 어렵다.

핵심 판단:

- OpenRouter는 Cline의 판단 보조 도구다.
- OmniVoice TTS는 로컬 worker/subprocess 문제다.
- TTS worker가 멈춘 상태에서는 OpenRouter 연결만으로 workflow가 진척되지 않는다.

## 2. 목표 상태

최종 목표:

- Cline이 반복 실패 1회 후에는 반드시 deterministic diagnosis를 먼저 실행한다.
- 같은 상태가 2회 반복되면 반드시 OpenRouter subagent에 원인 리뷰를 요청한다.
- `tts_wait`, `image_wait`, `render_wait`, `source_wait`는 각각 전용 복구 루프를 가진다.
- OpenRouter model fallback chain이 실제 호출 결과에 따라 작동한다.
- 사용자가 "왜 안 돼?"라고 물었을 때 Cline이 옵션 질문을 던지기 전에 상태, 원인, 복구 명령을 제시한다.

성공 기준:

- `tts_wait`가 2회 반복되면 Cline은 `diagnose_runtime -> forensic_diagnose -> repair_runtime` 순서로 움직인다.
- TTS heartbeat 만료 시 Cline은 "기다리기"를 제안하지 않고 worker/process/DB 상태를 복구한다.
- OpenRouter 429가 발생하면 provider upstream limit인지, 계정 budget limit인지 구분해서 보고한다.
- Cline 응답에 "1/2/3 중 선택" 같은 넓은 질문이 줄어들고, 검증된 다음 조치가 먼저 나온다.

## 3. 모델 라우팅 정책

### 3.1 역할 분리

| 역할 | 기본 모델/도구 | 책임 |
|---|---|---|
| Local operator | LM Studio `google/gemma-4-e4b` | 짧은 상태 확인, MCP tool 선택, 파일/명령 실행 |
| OpenRouter reviewer | `google/gemma-4-31b-it:free` | 반복 실패 원인 분석, 계획 리뷰, 위험 판단 |
| OpenRouter fallback | `google/gemma-4-26b-a4b-it:free` | 31B upstream rate limit 시 대체 |
| OpenRouter last resort | `openai/gpt-oss-20b:free` | Google free endpoint 불안정 시 대체 |
| Deterministic tools | `diagnose_runtime`, `forensic_diagnose`, DB/status scripts | 실제 상태 확인, worker/process/asset 검증 |

### 3.2 OpenRouter 호출 트리거

반드시 OpenRouter subagent를 호출해야 하는 경우:

- 같은 workflow step이 2번 연속 반복됨
- Cline이 "워커 지연", "리소스 충돌", "가능성 높음" 같은 추정만 하고 원인을 확정하지 못함
- `repair_runtime` 실행 후에도 상태가 그대로임
- HTTP 429/500, provider unavailable, model unavailable이 발생함
- TTS/render/image/source worker 중 하나가 `running`인데 heartbeat가 만료되었거나 progress가 정지됨
- 사용자가 "OpenRouter 붙였는데 왜 안 쓰냐"라고 지적함

호출하지 말아야 하는 경우:

- 단순 파일 읽기
- 단일 명령 실행
- 이미 DB/process/log로 원인이 확정된 로컬 worker 문제
- secret, cookie, browser profile, API key를 포함해야만 이해 가능한 문제

중요 규칙:

OpenRouter subagent는 advisory다. OpenRouter가 답한 내용을 바로 믿지 말고, 로컬 DB/process/log로 검증한 뒤 적용한다.

## 4. Workflow 상태 진단 정책

### 4.1 `tts_wait` 전용 판단

Cline은 `tts_wait`에서 다음 순서로 판단해야 한다.

1. 프로젝트 DB 확인
   - `tts_state`
   - `tts_progress`
   - `tts_error`
   - `tts_job_id`
   - `tts_started_at`
   - `tts_heartbeat_at`

2. 프로세스 확인
   - `app.workers.tts_worker`
   - `scripts/run_tts_job.py`
   - `omnivoice_env\Scripts\python.exe`
   - 중복 `uvicorn app.main:app --port 9002`

3. 산출물 확인
   - `storage/projects/<pid>/tts/timings.json`
   - `tts_run_manifest.json`
   - audio files
   - `omnivoice_runtime_probe.json`
   - `tts_error.json`

4. 판정
   - `queued` + worker 없음: worker start
   - `running` + heartbeat fresh + subprocess 있음: 기다림
   - `running` + heartbeat expired: stale job 복구
   - `error` + heartbeat expired: 재큐잉 또는 job reset
   - runtime probe 실패: OmniVoice environment 복구
   - subprocess 없음 + worker만 있음: job failed/abandoned로 보고 재큐잉

### 4.2 옵션 질문 금지 조건

다음 상황에서는 Cline이 사용자에게 "1/2/3 중 선택"을 물으면 안 된다.

- heartbeat expired가 이미 확인됨
- worker process가 없음
- stale lock이 확인됨
- output artifact가 없음
- 같은 `continue-video-workflow` 결과가 두 번 반복됨

이 경우 기본 행동은:

```text
diagnose_runtime -> forensic_diagnose -> repair_runtime -> status 재확인 -> continue_video_workflow 1회
```

## 5. 복구 루프 개선

### P0. 관찰성 강화

추가할 것:

- `diagnose_runtime` 출력에 worker별 상태 요약 추가
  - live/dead
  - lock pid
  - DB running jobs
  - heartbeat age seconds
  - last artifact timestamp
- `forensic_diagnose`에 TTS 전용 critical finding 추가
  - `TTS_WORKER_MISSING`
  - `TTS_HEARTBEAT_EXPIRED`
  - `TTS_SUBPROCESS_MISSING`
  - `TTS_OUTPUT_MISSING`
  - `DUPLICATE_API_SERVER`
  - `OMNIVOICE_RUNTIME_OK_BUT_JOB_ABORTED`

완료 기준:

```powershell
C:\Users\petbl\local-rag\.venv\Scripts\python.exe scripts\forensic_doctor.py --project-id <pid> --json
```

위 명령이 TTS 정지 원인을 코드형 finding으로 반환해야 한다.

### P1. TTS 복구 명령 추가

`newauto-stepwise` MCP에 전용 도구를 추가한다.

제안 도구:

```text
repair_tts(project_id="")
```

동작:

1. stale `tts_worker.lock` 제거
2. 죽은 `run_tts_job.py` 프로세스 정리
3. 중복 API 서버가 있으면 포트 owner 기준으로 상태 보고
4. `tts_state in ('running','error')`이고 산출물이 없으면 `queued`로 재설정
5. `tts_error`, `tts_job_id`, `tts_started_at`, `tts_heartbeat_at` 초기화
6. `app.workers.tts_worker` 재시작
7. 10초 후 DB 상태 재확인

주의:

- 이미 `timings.json`과 audio가 존재하면 재큐잉하지 않는다.
- 진행 중인 실제 `run_tts_job.py`가 살아 있고 heartbeat가 fresh면 죽이지 않는다.
- 무조건 삭제/초기화하지 말고 산출물 존재 여부를 먼저 확인한다.

안전성/멱등성 규칙:

- `repair_tts`는 여러 번 실행되어도 이미 완료된 TTS 결과를 훼손하지 않아야 한다.
- 산출물 검사는 최소 `timings.json`, `tts_run_manifest.json`, audio 파일의 존재와 nonzero size를 확인한다.
- `timings.json`이 존재하지만 오래된 파일일 수 있으므로 `LastWriteTime`과 현재 project `updated_at`/`tts_started_at`의 관계를 함께 기록한다.
- `tts_state='done'`이고 산출물이 유효하면 DB를 건드리지 않고 "already complete"로 종료한다.
- `tts_state='running'`이더라도 heartbeat가 fresh이고 `run_tts_job.py`가 살아 있으면 재시작하지 않고 "active job"으로 종료한다.
- `tts_state in ('running','error')`이고 heartbeat expired, subprocess missing, output missing이 동시에 확인될 때만 재큐잉한다.
- 프로세스 종료가 필요한 경우에도 PID와 command line이 `run_tts_job.py --project-id <pid>`에 해당하는지 확인한 뒤 해당 project 범위에서만 처리한다.

### P2. `continue_video_workflow` guard 추가

`continue_video_workflow`가 `tts_wait`에서 같은 상태를 반복하면 자동으로 다음을 실행하도록 한다.

1회 반복:

```text
diagnose_runtime
```

2회 반복:

```text
forensic_diagnose
```

3회 반복:

```text
repair_tts 또는 repair_runtime
```

4회 반복:

```text
ask_openrouter_subagent(mode="debug")
```

이 guard는 Cline의 지능에 맡기지 말고 MCP/core 코드에 상태 카운터로 넣어야 한다.

상태 저장 위치:

```text
storage/stepwise_workflows/<project_id>.json
```

추가 필드:

```json
{
  "last_wait_step": "tts_wait",
  "wait_repeat_count": 2,
  "last_wait_snapshot": {
    "tts_state": "running",
    "tts_progress": 0,
    "tts_heartbeat_age_sec": 120
  }
}
```

### P3. OpenRouter 강제 사용 경로 보강

현재 `ask_openrouter_subagent` 도구는 존재하지만 Cline이 자발적으로 쓰지 않는다. 따라서 wrapper instructions와 `.clinerules`만 믿지 말고 코드 경로에 넣는다.

추가 정책:

- `forensic_diagnose`가 `status=uncertain`을 반환하면 `ask_openrouter_subagent`를 자동 권장
- 같은 critical finding이 2회 반복되면 OpenRouter prompt packet을 자동 생성
- prompt는 shell `--task "..."`가 아니라 in-process harness 또는 stdin/file 기반으로 전달

OpenRouter task packet 예:

```json
{
  "mode": "debug",
  "problem": "tts_wait repeats despite continue_video_workflow",
  "project_id": "<pid>",
  "local_facts": {
    "tts_state": "error",
    "tts_error": "TTS worker heartbeat expired. Start TTS again.",
    "worker_process": "missing or stale",
    "artifact_status": "timings.json missing"
  },
  "question": "Recommend the next deterministic repair action. Do not suggest waiting unless heartbeat is fresh."
}
```

OpenRouter context diet:

- OpenRouter에는 raw log 전체를 보내지 않는다.
- `forensic_diagnose` JSON에서 다음 필드만 추출한다.
  - `critical_findings`
  - `recommended_actions`
  - project state 요약
  - worker/process 요약
  - artifact 요약
  - 최근 error message 1-3개
- log tail이 필요하면 50줄 이하 또는 6000자 이하로 제한하고 secret redaction을 적용한다.
- `openrouter.txt`, API key, cookies, browser profile, 전체 DB dump, 전체 project JSON은 절대 포함하지 않는다.
- OpenRouter 응답은 "외부 조언"이며, 실행 전 DB/process/artifact로 재검증한다.

권장 local facts packet:

```json
{
  "problem": "workflow wait step repeated",
  "wait_step": "tts_wait",
  "repeat_count": 3,
  "project": {
    "id": "<pid>",
    "tts_state": "error",
    "tts_progress": 0,
    "tts_error": "TTS worker heartbeat expired. Start TTS again.",
    "heartbeat_age_sec": null
  },
  "processes": {
    "tts_worker": "live|missing",
    "run_tts_job": "live|missing",
    "duplicate_api_server": true
  },
  "artifacts": {
    "timings_json": "missing|present",
    "audio_files": 0,
    "runtime_probe": "present"
  },
  "critical_findings": [
    "TTS_HEARTBEAT_EXPIRED",
    "TTS_OUTPUT_MISSING"
  ],
  "already_tried": [
    "continue_video_workflow",
    "repair_runtime"
  ]
}
```

### P4. OpenRouter provider/rate-limit 구분

OpenRouter 429 처리 규칙:

- `metadata.raw`에 `temporarily rate-limited upstream`이 있으면 provider upstream limit
- local budget file이 800/950/1000에 걸리면 local budget limit
- HTTP 401/403이면 key/auth 문제
- `No endpoints found`이면 model availability 문제

Cline 보고 형식:

```text
OpenRouter 연결은 살아 있음.
실패 원인: provider upstream temporary rate limit.
조치: fallback model로 재시도.
```

잘못된 보고:

```text
요청을 많이 해서 계정 리밋입니다.
```

## 6. `.clinerules` 업데이트 계획

배치 원칙:

- `Mandatory Escalation`은 `.clinerules`의 상단부, `Recovery Loop`보다 앞에 둔다.
- 기존 `TTS Rules`, `Recovery Loop`, `OpenRouter Subagent` 규칙보다 우선되는 행동 규칙으로 작성한다.
- Cline이 프롬프트 인젝션이나 오래된 문서 지침에 끌려가지 않도록 "이 섹션이 workflow failure handling의 우선 정책"임을 명시한다.

추가할 규칙:

```md
## Mandatory Escalation

- This section overrides lower recovery heuristics for workflow wait failures.
- If the same workflow wait step repeats twice, call diagnose_runtime before asking the user.
- If diagnose_runtime does not identify the cause, call forensic_diagnose.
- If forensic_diagnose reports stale worker, expired heartbeat, missing subprocess, or missing artifact, run repair_runtime or the specific repair tool once.
- If the same local failure remains after repair, call ask_openrouter_subagent(mode="debug").
- Never solve tts_wait by changing OpenRouter settings. OpenRouter is for reasoning; OmniVoice TTS is a local worker/subprocess path.
- Do not ask option-style questions when heartbeat expired, worker missing, stale lock, or missing output artifact is confirmed.
- Before sending anything to OpenRouter, compress local state into a redacted facts packet from forensic_diagnose. Do not send full logs or full project dumps.
```

## 7. Implementation 순서

### Step 1. 문서/규칙 정리

- 이 계획서를 기준 문서로 사용한다.
- 깨진 인코딩 계획서는 참조용으로만 두고, 새 작업은 이 문서를 기준으로 한다.
- `.clinerules`에 mandatory escalation을 추가한다.

검증:

```powershell
Select-String -Path .\.clinerules -Pattern "Mandatory Escalation|Never solve tts_wait"
```

### Step 2. Forensic doctor 강화

대상:

- `scripts/forensic_doctor.py`

작업:

- TTS DB 상태 조회 추가
- worker/subprocess 조회 추가
- heartbeat age 계산 추가
- artifact existence check 추가
- critical finding code 추가

검증:

```powershell
C:\Users\petbl\local-rag\.venv\Scripts\python.exe scripts\forensic_doctor.py --project-id <pid> --json
```

### Step 3. TTS 복구 도구 추가

대상:

- `scripts/newauto_stepwise_mcp.py`
- 필요 시 `scripts/newauto_mcp.py`

작업:

- `repair_tts(project_id="")` MCP tool 추가
- stale lock cleanup
- dead running job reset
- worker restart
- post-repair status check

검증:

```powershell
C:\Users\petbl\local-rag\.venv\Scripts\python.exe scripts\newauto_stepwise_mcp.py --action repair_runtime --project-id <pid>
```

추가 CLI action이 필요하면:

```powershell
C:\Users\petbl\local-rag\.venv\Scripts\python.exe scripts\newauto_stepwise_mcp.py --action repair_tts --project-id <pid>
```

### Step 4. Wait repeat guard 추가

대상:

- `scripts/newauto_mcp.py`
- `scripts/newauto_stepwise_mcp.py`

작업:

- `continue_stepwise_hpsl_video_workflow`에서 이전 step/snapshot과 현재 step/snapshot 비교
- 반복 횟수 저장
- 반복 횟수에 따라 diagnosis/repair/OpenRouter escalation 수행

검증:

- 의도적으로 TTS worker를 끄고 `continue_video_workflow` 실행
- 같은 `tts_wait`가 2회 반복될 때 Cline이 옵션 질문 대신 진단/복구 경로로 이동하는지 확인

### Step 5. OpenRouter fallback smoke

대상:

- `scripts/openrouter_subagent_harness.py`

작업:

- 429 raw metadata 출력은 redacted 상태로 보존
- provider upstream limit과 local budget limit 구분
- fallback attempt를 `last_attempts`에 기록

검증:

```powershell
C:\Users\petbl\local-rag\.venv\Scripts\python.exe scripts\openrouter_subagent_harness.py --mode debug --task "Return one JSON diagnosis for a stale TTS worker." --json-output
C:\Users\petbl\local-rag\.venv\Scripts\python.exe scripts\openrouter_subagent_harness.py --budget-status
```

## 8. 운영 Playbook

### Cline이 `tts_wait`에서 멈추면

정답 행동:

```text
diagnose_runtime
forensic_diagnose
repair_tts 또는 repair_runtime
continue_video_workflow 1회
```

오답 행동:

```text
OpenRouter 연결 확인만 반복
사용자에게 1/2/3 선택 질문
continue_video_workflow 무한 반복
TTS worker 상태 확인 없이 기다리기 제안
```

### OpenRouter 429가 나오면

정답 행동:

```text
에러 본문 확인
provider upstream limit인지 local budget limit인지 구분
fallback model로 재시도
local worker 문제와 혼동하지 않음
```

### Cline이 판단을 못 하면

정답 행동:

```text
ask_openrouter_subagent(mode="debug", task=<local facts only>)
```

task에는 다음만 보낸다:

- 상태 요약
- 에러 코드
- 로그 tail 일부
- 이미 시도한 명령
- 원하는 출력 schema

보내지 말 것:

- `openrouter.txt`
- API key
- cookies
- browser profile
- 전체 DB dump
- 전체 로그

## 9. 평가 항목

### 평가 1. TTS stale worker

조건:

- `tts_state=running`
- heartbeat 60초 이상 갱신 없음
- `run_tts_job.py` 없음

기대 결과:

- Cline이 `repair_tts`를 실행한다.
- "기다리기"를 제안하지 않는다.
- OpenRouter를 호출하더라도 "로컬 TTS worker 문제"라고 결론낸다.

### 평가 2. OpenRouter upstream limit

조건:

- OpenRouter 응답 `429`
- metadata raw에 `temporarily rate-limited upstream`

기대 결과:

- Cline이 "계정 사용량 초과"라고 말하지 않는다.
- fallback model을 시도한다.
- 로컬 TTS 문제와 분리해서 설명한다.

### 평가 3. 같은 step 반복

조건:

- `continue_video_workflow` 결과가 같은 `next_step`으로 2회 반복

기대 결과:

- 자동으로 diagnosis/escalation이 시작된다.
- 사용자에게 broad option question을 던지지 않는다.

## 10. 우선순위

즉시 해야 할 것:

1. `.clinerules` mandatory escalation 추가
2. `forensic_doctor.py` TTS finding 강화
3. `repair_tts` 추가
4. `continue_video_workflow` wait repeat guard 추가

그 다음:

5. `repair_tts` idempotency/safety test 추가
6. OpenRouter facts packet/context diet 적용
7. OpenRouter fallback/error classification smoke 강화
8. 깨진 인코딩 계획서 정리 또는 archive
9. Cline 평가 fixture 추가

보류:

- 모델을 유료 API로 전환
- Flow 자동화 전체 재작성
- TTS 모델 교체

현재 병목은 모델 크기보다 **Cline의 라우팅/진단/복구 정책 부재**다. 이 계획의 1차 성공은 더 똑똑한 답변이 아니라, 같은 실패를 반복하지 않는 실행 루프를 만드는 것이다.
