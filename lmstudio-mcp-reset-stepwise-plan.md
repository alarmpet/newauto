# LM Studio MCP Reset And Minimal Stepwise Reconnect Plan

> 작성일: 2026-05-07 18:25 KST  
> 목적: LM Studio에 연결된 MCP를 초기화하고, HPSL/Flow 작업에 필요한 최소 도구만 단계형으로 다시 연결한다.  
> 원칙: 외부 유료 API 없음, 로컬 newauto + LM Studio + Ui.Vision/Flow 인증 기반, 사용자 승인 단위로 한 단계씩 진행.

## 1. 현재 문제 요약

최근 `ddfa3647f80b` 워크플로우에서 다음 현상이 반복됐다.

- LM Studio 채팅창은 `Tool call failed`, `MCP error -32001`, `Request timed out`를 표시했다.
- 하지만 로컬 상태 파일과 직접 MCP 함수 호출 결과는 실제 작업이 완료됐거나 다음 단계로 이동한 상태였다.
- LM Studio는 timeout 후 실제 MCP 반환문이 아니라 자체 추론 문장으로 "이미지/영상 생성 과부하" 같은 부정확한 원인을 말했다.
- 기존 MCP에는 호환 도구와 실험 도구가 많다.
  - `start_hpsl_flow_workflow`
  - `finish_hpsl_flow_workflow`
  - `make_hpsl_flow_short_video`
  - `open_flow`
  - `attach_latest_flow_downloads`
  - Flow smoke/debug tools
- Gemma4 E4B는 작은 모델이라 도구가 많으면 잘못된 도구를 고를 가능성이 높다.

핵심 결론:

```text
현재 문제는 워크플로우 로직만의 문제가 아니라,
LM Studio MCP 연결 상태 + 과다한 도구 노출 + stale/timeout 후 Gemma4의 임의 해석이 섞인 문제다.
```

## 2. 목표 구조

LM Studio에는 새 MCP 서버 하나만 연결한다.

```text
LM Studio
  -> MCP: newauto-stepwise
       -> scripts/newauto_stepwise_mcp.py
       -> 내부에서 scripts.newauto_mcp의 검증된 구현만 재사용
       -> 노출 도구 4~5개만 허용
```

노출할 도구:

```text
1. diagnose_newauto_runtime(project_id="")
2. start_stepwise_hpsl_video_workflow(keyword_or_url, title="", target_minutes=1, tone="설명형")
3. continue_stepwise_hpsl_video_workflow(project_id="")
4. flow_asset_coverage(project_id)
5. optional: flow_generate_one_sentence(project_id, sentence_number)
```

노출하지 않을 도구:

```text
- start_hpsl_flow_workflow
- finish_hpsl_flow_workflow
- make_hpsl_flow_short_video
- continue_after_flow_assets
- open_flow / open_flow_for_auth
- attach_latest_flow_downloads
- attach_renamed_flow_downloads
- automate_flow_generation
- download_flow_results_from_browser
- prepare_uivision_flow_batch
- 모든 legacy/compatibility wrapper
```

## 3. 구현 계획

### Phase 1. 최소 MCP 엔트리포인트 생성

파일 추가:

```text
C:\Users\petbl\newauto\scripts\newauto_stepwise_mcp.py
C:\Users\petbl\newauto\run-newauto-stepwise-mcp.cmd
```

`newauto_stepwise_mcp.py` 설계:

- `FastMCP(name="newauto-stepwise")` 사용
- 기존 `scripts.newauto_mcp`에서 검증된 함수만 import해서 wrapper로 노출
- wrapper는 모두 짧게 반환해야 한다.
- tool docstring은 Gemma4가 헷갈리지 않게 아주 명확하게 쓴다.
- instructions에는 다음을 강제한다.

```text
- Always call diagnose_newauto_runtime first after MCP reconnect.
- For a new video workflow, call start_stepwise_hpsl_video_workflow once.
- For every user approval such as 진행/ok/다음, call continue_stepwise_hpsl_video_workflow exactly once.
- Never call legacy workflow names because they are not available in this MCP.
- Never explain tool timeout as image generation overload; use diagnose_newauto_runtime or project state.
```

### Phase 2. 실행 CMD 생성

`run-newauto-stepwise-mcp.cmd` 내용:

```bat
@echo off
setlocal
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"
set "LLM_PROVIDER=lmstudio"
set "LMSTUDIO_BASE_URL=http://127.0.0.1:1234"
set "SCRIPT_LLM_MODEL=google/gemma-4-e4b"
"C:\Users\petbl\local-rag\.venv\Scripts\python.exe" "%~dp0scripts\newauto_stepwise_mcp.py"
```

이 CMD만 LM Studio에 등록한다.

### Phase 3. LM Studio MCP 초기화 절차

사용자 수동 작업이 필요한 부분:

1. LM Studio 종료
2. LM Studio 재실행
3. MCP 설정 화면으로 이동
4. 기존 MCP 서버 전부 disable/remove
   - `newauto-hpsl-flow`
   - `local-gemma4-browser`
   - 기타 테스트 MCP
5. 새 서버 추가
   - name: `newauto-stepwise`
   - command: `C:\Users\petbl\newauto\run-newauto-stepwise-mcp.cmd`
6. 저장 후 새 채팅 시작
7. 첫 메시지:

```text
diagnose_newauto_runtime 실행해서 현재 MCP 커밋, PID, 프로젝트 상태 확인해줘
```

Codex가 도와줄 수 있는 부분:

- CMD/스크립트 생성
- LM Studio 설정 경로 후보 탐색
- 수동 입력용 설정값 출력
- MCP 직접 smoke test
- LM Studio가 아닌 로컬에서 동일 함수 호출 검증

### Phase 4. 검증 시나리오

#### Smoke 1: MCP identity

LM Studio 채팅에서:

```text
diagnose_newauto_runtime
```

기대 결과:

```text
mcp_script: ...\scripts\newauto_stepwise_mcp.py 또는 wrapper identity
underlying_commit: 최신 git commit
api_server_ok: True
stepwise_next_step: 현재 프로젝트 단계 또는 none
```

#### Smoke 2: 기존 프로젝트 복구

현재 프로젝트:

```text
project_id: ddfa3647f80b
expected next_step: flow_generate
asset coverage: 0/6
```

LM Studio 채팅에서:

```text
flow_asset_coverage project_id=ddfa3647f80b
```

기대 결과:

```text
coverage: 0/6
missing: [1,2,3,4,5,6]
```

#### Smoke 3: 단계 진행

LM Studio 채팅에서:

```text
continue_stepwise_hpsl_video_workflow project_id=ddfa3647f80b
```

기대 결과:

- 한 단계만 진행
- timeout이 나면 임의 원인 설명 대신 debug footer 또는 diagnose를 요구
- 다음 단계가 state file에 저장됨

## 4. 실패 처리 규칙

새 MCP에서는 실패 메시지 원칙을 단순화한다.

```text
- tool call timeout 발생 시 "이미지 생성 과부하"라고 추정하지 않는다.
- 반드시 diagnose_newauto_runtime을 다시 실행한다.
- project_id가 있으면 state file과 /api/projects/{pid}/status를 확인한다.
- 실제 state가 이동했으면 사용자에게 "LM Studio는 실패로 보였지만 상태는 이동했다"고 알린다.
- 같은 단계 재호출은 continue_stepwise_hpsl_video_workflow 한 번만 허용한다.
```

## 5. 보안/운영 원칙

- 외부 유료 API 사용 없음.
- Flow는 사용자가 로그인/권한 승인한다.
- 개인 브라우저 기본 프로필 자동 제어는 피한다.
- Ui.Vision/Flow 자동화는 한 문장 단위로 진행한다.
- 각 단계는 사용자 `진행`, `ok`, `다음` 승인 후 한 번만 실행한다.

## 6. 작업 체크리스트

- [ ] `scripts/newauto_stepwise_mcp.py` 생성
- [ ] `run-newauto-stepwise-mcp.cmd` 생성
- [ ] 최소 MCP wrapper 4개 구현
- [ ] instructions에서 legacy 도구 미노출/미사용 강제
- [ ] 직접 Python smoke: diagnose/start/continue import 호출
- [ ] `py_compile` 실행
- [ ] `mypy` 실행, `Any`/`unknown` 추가 금지
- [ ] `research.md`에 아키텍처 변경 기록
- [ ] `timeline.md`에 커밋 시간과 요약 기록
- [ ] git commit

## 7. 사용자 안내 문구 초안

LM Studio MCP 설정에 입력할 값:

```text
Name:
newauto-stepwise

Command:
C:\Users\petbl\newauto\run-newauto-stepwise-mcp.cmd
```

초기화 후 첫 채팅:

```text
먼저 diagnose_newauto_runtime 실행해서 MCP 연결 상태 확인해줘.
```

새 워크플로우 시작:

```text
키워드: 비트코인, 2026-05-06 이후 자료 수집해서 HPSL(훅-포인트-스토리-교훈) 1분 쇼츠 대본 만들고 Flow 프롬프트 생성 후 이미지 생성까지 단계별로 진행해줘. 각 단계 완료 후 나한테 확인받고 다음 단계로 가.
```

진행 방식:

```text
진행
진행
진행
```

각 `진행`은 반드시 `continue_stepwise_hpsl_video_workflow` 한 번만 호출해야 한다.
