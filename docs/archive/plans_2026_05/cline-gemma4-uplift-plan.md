# Cline + LM Studio + Gemma-4-e4b 88K 운용 개선 계획

작성일: 2026-05-08  
대상 환경: RTX 4060 Laptop 8GB / i7-14700HX / 32GB RAM / Cline 3.82 / LM Studio / `google/gemma-4-e4b`

## 0. 결론

현재 병목은 Gemma4 모델 스펙이 아니라 **LM Studio 로드 컨텍스트와 Cline/MCP 사용 방식**이다.

- 모델 스펙상 최대 컨텍스트: `131,072`
- 현재 로드 상태: `29,829`, `parallel=4`
- 목표 운용값: **약 88K tokens**, `parallel=1`
- 88K estimate: `10.85 GiB`
- 핵심 전략: 컨텍스트를 늘리되, 긴 로그/전체 파일/전체 프롬프트를 모델에 던지지 않고 범용 MCP는 작고 선명하게, `newauto-stepwise`는 프로젝트 특화 고수준 도구로 유지한다.

88K는 "아무거나 많이 넣기"가 아니라, Cline/Gemma4가 중간에 흐려지지 않도록 **상태 요약, 파일 필터링, 단계형 실행, 자동 진단/복구, 범용 작업 도구 선택**을 더 안정적으로 담기 위한 여유 공간으로 쓴다.

## 1. 현재 코드베이스와 MCP 구성 기준 핵심 사실

최근 `research.md`, `timeline.md`, 코드 확인 결과 현재 구조는 과거 계획보다 많이 진화했다.

- `scripts/newauto_stepwise_mcp.py`
  - LM Studio에 보이는 핵심 Agentic Control Hub.
  - `diagnose_runtime`, `start_video_workflow`, `continue_video_workflow`, `check_assets`, `generate_one_image`, `repair_runtime`, `search_web` 제공.
  - 별도 `openclaw-operator`가 안 보이는 채팅에서도 `operator_status`, `run_powershell`, `control_flow_desktop` fallback을 직접 노출.
- `scripts/newauto_mcp.py`
  - 실제 HPSL/Flow/TTS/render 상태 머신의 단일 원천.
  - 긴 작업은 `source_collect_wait`, `script_generate_wait`, `flow_wait_sentence`, `tts_wait`, `render_wait`로 분리되어 MCP timeout을 피한다.
- `scripts/lmstudio_openclaw_operator_mcp.py`
  - PowerShell, 파일 작업, OS open, Flow desktop control 제공.
  - `force_approve`와 command policy interceptor가 있어 승인 루프와 위험 명령 차단을 처리한다.
- `scripts/flow_desktop_control.py`
  - 인증된 Flow 창을 직접 제어한다.
  - foreground/lock/URL preflight, screenshot trace, `click-generate`, `download-attach`, `generate-one` 모드가 있다.
- `search_web`
  - DuckDuckGo HTML 기반 무료 검색 도구.
  - Gemma4가 "실시간 검색 불가"라고 멈추는 실패를 줄이는 고수준 도구다.
- 범용 MCP 1차 세트
  - `sequential-thinking`: 복잡한 범용 계획/추론용.
  - `memory`: 세션 간 짧은 지식/선호/작업 메모리용.
  - `filesystem`: `C:/Users/petbl` 범위의 일반 파일 접근용.
  - `context7`: 라이브러리/프레임워크 공식 문서 조회용.
  - LM Studio 설정: `C:/Users/petbl/.lmstudio/mcp.json`
  - Cline 설정: `C:/Users/petbl/AppData/Roaming/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`

따라서 방향은 두 갈래다. 범용 작업에는 위 4개 MCP를 쓰고, newauto 영상 파이프라인에는 이미 검증된 `newauto-stepwise` 표면을 더 단단하게 만든다.

## 2. 발견된 문제점

### 2.1 컨텍스트 설정 불일치

- Cline UI는 이전 세션에서 `24K`로 보였고, LM Studio 실제 로드는 `29,829`였다.
- `newauto_stepwise_mcp.py`의 `agentic_metadata_json.context_target`은 `88000`으로 갱신했다.
- `.clinerules`의 24K 문구도 88K 운용 기준으로 갱신했다.

개선:
- LM Studio 로드 목표를 88K로 바꾼다.
- 코드/문서의 context target을 `88000`으로 맞춘다.
- 실제 검증은 Cline UI가 아니라 `lms ps`와 `/api/v0/models.loaded_context_length`로 한다.

### 2.2 88K를 과신할 위험

88K estimate는 `10.85 GiB`다. RTX 4060 Laptop 8GB 환경에서는 시스템 공유 메모리 또는 부분 offload에 의존할 수 있다.

개선:
- 기본 목표는 88K.
- 불안정하면 72K, 64K 순서로 fallback.
- `parallel=1`을 고정한다.
- Cline 작업 중에는 LM Studio unload/reload를 피하고, 대기 상태에서만 바꾼다.

### 2.3 도구 표면이 넓어질수록 Gemma4가 헷갈림

과거 계획은 외부 MCP를 많이 추가하는 방향이었지만, 실제 실패는 도구 부족보다 "어떤 도구를 써야 하는지 못 고름", "timeout 원인 환각", "GUI 불가 선언"이었다.

개선:
- LM Studio 활성 채팅에는 `newauto-stepwise`를 1순위로 둔다.
- `openclaw-operator`는 별도 MCP로 유지하되, 실제 사용은 `newauto-stepwise` fallback 도구로도 가능하게 둔다.
- 범용 작업용 MCP는 `sequential-thinking`, `memory`, `filesystem`, `context7`까지만 1차로 연다.
- `fetch`/`time`은 현재 확인한 npm 패키지명으로는 존재하지 않아 제외한다.
- `git-mcp-server`는 실행 시 stdout 로그가 많고 destructive git 도구가 넓어서 제외한다. Git은 `run_powershell` 또는 Cline/Codex 기본 명령으로 처리한다.

### 2.4 긴 출력이 컨텍스트를 다시 태움

88K로 늘려도 전체 `research.md`, 전체 prompt manifest, 전체 로그, 전체 DB dump를 매번 넣으면 금방 찬다.

개선:
- `get_flow_prompt_queue`처럼 요약 반환을 기본으로 유지한다.
- 전체 Flow prompt는 `get_single_flow_prompt` 또는 UI/파일 경로로 접근한다.
- `run_powershell` 결과는 stdout/stderr tail 중심으로 제한한다.
- `diagnose_runtime`은 JSON metadata + 핵심 상태만 유지한다.

### 2.5 현재 문서와 코드가 어긋남

기존 계획서에는 24K 전제, MCP 대량 추가, 새 memory bank 중심 내용이 남아 있었다. 하지만 현재는:

- stepwise MCP가 이미 구현됨
- operator fallback이 이미 stepwise에 내장됨
- Flow desktop control이 이미 검증됨
- source/script/TTS/render long wait split이 이미 구현됨
- `search_web`이 이미 구현됨

개선:
- 계획서는 "새로 많이 붙이기"가 아니라 "현재 검증 구조를 88K에 맞게 안정화"로 재작성한다.

## 3. 88K LM Studio 로드 계획

### 3.1 권장 명령

Cline/Gemma4가 작업 중이 아닐 때 실행한다.

```powershell
lms unload google/gemma-4-e4b
lms load google/gemma-4-e4b --context-length 88000 --parallel 1 --gpu max -y
```

확인:

```powershell
lms ps
Invoke-RestMethod http://127.0.0.1:1234/api/v0/models | ConvertTo-Json -Depth 6
```

성공 기준:

- `CONTEXT`가 `88000` 근처
- `loaded_context_length`가 `88000` 근처
- `PARALLEL`이 `1`

### 3.2 fallback 값

88K 로드 후 응답 지연, OOM, LM Studio unload, Flow/ComfyUI/TTS 동시 사용 중 GPU 불안정이 생기면 아래 순서로 낮춘다.

```powershell
lms unload google/gemma-4-e4b
lms load google/gemma-4-e4b --context-length 72000 --parallel 1 --gpu max -y
```

그래도 불안정하면:

```powershell
lms unload google/gemma-4-e4b
lms load google/gemma-4-e4b --context-length 65536 --parallel 1 --gpu max -y
```

## 4. P0 반영 사항

### P0-1. context metadata 정합화

대상:

- `scripts/newauto_stepwise_mcp.py`
- `.clinerules`
- `cline-gemma4-uplift-plan.md`

변경:

- `agentic_metadata_json.context_target`: `30000` -> `88000`
- `.clinerules`의 24K 문구를 88K 운용 기준으로 갱신
- Cline 응답 규칙은 "긴 출력 금지"를 유지

검증:

```powershell
python -m py_compile scripts\newauto_stepwise_mcp.py
```

### P0-2. LM Studio 88K 로드 검증 루틴 추가

`diagnose_runtime` 또는 운영 문서에 다음 항목을 명확히 둔다.

- LM Studio model id
- `max_context_length`
- `loaded_context_length`
- `parallel`
- 권장값과 현재값의 mismatch

현재 `diagnose_runtime`은 agentic metadata를 제공하지만 LM Studio `/api/v0/models`의 loaded context까지 직접 포함하지는 않는다. 88K 운용에서는 이 값이 매우 중요하므로 P0로 추가한다.

### P0-3. Cline checkpoint/context 압박 줄이기

현재 `.clineignore`가 `storage/`, `data/`, `omnivoice_env/`, `node_modules/`, cache/log/model 파일을 제외하는 방향은 맞다.

추가 권장:

- `data/flow-browser-profile/`는 계속 제외
- `storage/projects/`는 기본 제외
- 필요 시 특정 프로젝트 산출물만 파일 경로로 지정
- 대용량 `research.md`는 전체 주입 대신 `rg`로 필요한 section만 읽기

### P0-4. 신규 작업의 기본 진행 규칙 고정

Gemma4가 사용자를 피곤하게 만들지 않게 다음 규칙을 고정한다.

- 새 영상 요청: `start_video_workflow` 정확히 1회
- 사용자가 `진행`, `ok`, `다음`: `continue_video_workflow` 정확히 1회
- 실패/timeout처럼 보임: 설명 전에 `diagnose_runtime`
- stale/lock/worker mismatch: `repair_runtime` 1회
- 웹 최신 정보: `search_web` 먼저
- Flow GUI: `control_flow_desktop`
- shell/file/git/server 조사: `run_powershell`
- 일반 파일 읽기/쓰기/탐색: `filesystem`
- 복잡한 계획/분해: `sequential-thinking`
- 장기 기억이 필요한 선호/반복 절차: `memory`
- 최신 라이브러리 공식 문서: `context7`

### P0-5. 범용 MCP 1차 등록

LM Studio와 Cline 양쪽에 다음 MCP를 등록했다.

| MCP | 목적 | 비고 |
|---|---|---|
| `sequential-thinking` | 범용 계획, 문제 분해, 자기검토 | 소형 모델의 성급한 단정 완화 |
| `memory` | 반복 작업/선호/프로젝트 메모리 | LM Studio와 Cline memory 파일 분리 |
| `filesystem` | 일반 파일 접근 | 허용 루트: `C:/Users/petbl` |
| `context7` | 라이브러리 공식 문서 조회 | 코딩/설정 질문에서 우선 사용 |

실제 설정:

- LM Studio: `C:/Users/petbl/.lmstudio/mcp.json`
- Cline: `C:/Users/petbl/AppData/Roaming/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`

의도적으로 제외:

- `@modelcontextprotocol/server-fetch`: 현재 npm registry에서 확인 불가.
- `@modelcontextprotocol/server-time`: 현재 npm registry에서 확인 불가.
- `@cyanheads/git-mcp-server`: stdout 로그/넓은 git write surface 때문에 1차 제외.

## 5. P1 성능 향상

### P1-1. `diagnose_runtime`을 machine-readable 우선으로 강화

현재 `agentic_metadata_json`은 좋은 방향이다. 다음 키를 추가하면 Gemma4가 덜 헷갈린다.

- `lmstudio_loaded_context_length`
- `lmstudio_max_context_length`
- `lmstudio_parallel`
- `context_target_met`
- `active_mcp_server`
- `latest_runtime_snapshot_path`

텍스트 설명은 JSON 뒤에 짧게 붙인다.

### P1-2. 고수준 상태 요약 파일 유지

88K에서도 전체 `research.md`를 매번 읽으면 손해다.

추가 파일 제안:

- `storage/runtime_diagnostics/latest.json`: 이미 존재하는 방향 유지
- `.cline/current-state.md`: Cline 전용 짧은 작업 상태
- `.cline/known-pitfalls.md`: MCP timeout, Flow 창, pyautogui runtime, source collect fallback 같은 실패 패턴만 요약

단, 새 memory bank를 크게 만들기보다 1~3개 파일로 작게 시작한다.

### P1-3. `run_powershell` 출력 제한

`run_powershell`은 강력하지만 출력이 길면 컨텍스트를 태운다.

권장:

- 기본 stdout/stderr는 마지막 200~300줄
- 전체 로그는 파일 경로만 반환
- `rg`, `Select-String`, `Get-Content -Tail` 사용을 instruction에 강조

### P1-4. Flow desktop 실패 코드 표준화

현재 `flow_desktop_control.py`는 preflight와 screenshot trace가 있다. 계획상 다음 failure code를 더 명확히 유지한다.

- `desktop_locked`
- `flow_window_not_found`
- `flow_url_mismatch`
- `prompt_input_not_ready`
- `download_not_ready`
- `attach_failed`
- `subprocess_timeout`

Gemma4는 failure code별 다음 행동만 말하게 한다.

## 6. P2 확장

### P2-1. 코드베이스 검색 MCP는 "필요하면" 추가

`nomic-embed-text-v1.5`가 있으므로 semantic search MCP를 만들 수 있다. 하지만 현재 P0 병목은 검색이 아니라 도구 선택/timeout/Flow GUI다.

추가 시 원칙:

- 모델에게 전체 파일을 주지 않는다.
- `search_codebase(query, top_k=5)`는 파일 경로, line range, 짧은 snippet만 반환한다.
- write 권한은 주지 않는다.

### P2-2. 외부 MCP 추가 원칙

1차로 이미 추가한 것:

- `sequential-thinking`
- `memory`
- `filesystem`
- `context7`

아직 권장하지 않는 것:

- Fetch/Brave/Tavily를 중복으로 붙이기
- stdout 로그가 많은 Git MCP를 바로 붙이기
- 너무 많은 검색/브라우저/문서 MCP를 동시에 붙이기

이유:

- 이미 `search_web`이 있음
- 도구 설명이 늘수록 Gemma4 E4B가 선택을 헷갈릴 수 있음
- 88K라도 tool schema와 장문 반환은 비용이다

필요해지면 web fetch 전용 MCP는 패키지명과 stdio 동작을 먼저 검증한 뒤 1개만 추가한다.

## 7. 운영 체크리스트

- [x] LM Studio를 `context-length 88000`, `parallel 1`로 reload
- [x] `lms ps`에서 `CONTEXT` 확인
- [x] `/api/v0/models`에서 `loaded_context_length` 확인
- [x] `scripts/newauto_stepwise_mcp.py`의 `context_target`을 `88000`으로 갱신
- [x] `.clinerules`의 24K 문구를 88K 기준으로 갱신
- [ ] `diagnose_runtime`에 LM Studio loaded context metadata 추가
- [x] LM Studio 범용 MCP 1차 등록: `sequential-thinking`, `memory`, `filesystem`, `context7`
- [x] Cline 범용 MCP 1차 등록: `sequential-thinking`, `memory`, `filesystem`, `context7`
- [x] `python -m py_compile scripts\newauto_stepwise_mcp.py scripts\newauto_mcp.py scripts\lmstudio_openclaw_operator_mcp.py`
- [ ] `mypy --follow-imports=skip`로 MCP 파일 검증
- [ ] MCP stdio smoke: `tools/list`, `diagnose_runtime`, `search_web`, safe `run_powershell`
- [ ] Flow smoke: `control_flow_desktop(..., mode="click-generate")`는 실제 Flow 창이 준비된 상태에서만 수행

## 8. 성공 기준

88K 전환이 성공한 상태는 다음과 같다.

- Cline UI가 80K 이상 컨텍스트를 인식하거나, 최소한 LM Studio API의 `loaded_context_length`가 88K 근처다.
- Gemma4가 긴 작업에서 "불가능", "실시간 검색 불가", "GUI 클릭 불가"라고 멈추지 않고 도구를 호출한다.
- MCP timeout처럼 보이는 상황에서 먼저 `diagnose_runtime`을 호출한다.
- Flow 작업은 한 문장당 `click-generate`와 `download-attach`로 나뉘어 진행된다.
- 전체 로그/전체 prompt manifest를 채팅에 쏟지 않는다.
- 문제가 생기면 `repair_runtime` 또는 failure code 기반 사용자 조치로 복구된다.

## 9. 한 줄 방향

**88K로 컨텍스트 방을 넓히되, 모델에게 더 많은 원시 자료를 먹이는 방식이 아니라 `newauto-stepwise` 중심의 짧고 강한 도구 선택, 요약형 진단, 단계별 실행을 더 안정화한다.**
