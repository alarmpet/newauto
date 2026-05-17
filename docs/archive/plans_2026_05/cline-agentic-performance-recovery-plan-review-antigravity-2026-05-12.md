# Cline Agentic Performance Recovery Plan: Antigravity Review

**작성일**: 2026-05-12
**대상 문서**: `cline-agentic-performance-recovery-plan-2026-05-12.md`
**작성자**: Antigravity (AI)

## 1. 종합 평가 (Overall Assessment)
제시해주신 "Cline Agentic Performance Recovery Plan"은 현재 `newauto` 파이프라인이 겪고 있는 고착 상태(Stuck loop)의 근본 원인을 정확하게 짚어냈습니다. 
가장 중요한 통찰은 **"로컬 워커(TTS/Render 등)의 상태 불량을 외부 OpenRouter 모델의 추론 능력으로 해결하려는 것은 논리적 오류"**라는 점입니다. OpenRouter 32B/GPT-OSS 모델을 추가하더라도, 로컬에서 죽어있는 프로세스를 강제로 재시작하거나 락(Lock)을 해제하는 물리적 액션이 동반되지 않으면 무한 대기(Wait Repeat)에 빠질 수밖에 없습니다.

따라서 Cline이 **"추정 전에 확정적 진단(forensic)을 하고, OpenRouter에 묻기 전에 로컬 복구를 시도한다"**는 강제 에스컬레이션(Mandatory Escalation) 구조를 제안하신 점은 시스템 안정성 향상에 결정적인 역할을 할 것입니다.

## 2. 코드베이스 상태 점검 결과 (Codebase Review)

작업 디렉토리(`C:\Users\petbl\newauto`) 내의 관련 파일과 최근 `timeline.md`를 분석한 결과, 계획서에서 지적한 문제들이 실제 코드상에도 그대로 존재함을 확인했습니다.

### 2.1 `scripts/forensic_doctor.py`
- **현상**: 현재 `check_servers()`, `check_processes()`, `project_state()` 등을 통해 `newauto_api`, `lmstudio`, `comfyui`, 프로세스 상태(kantu, chrome)를 확인하고 있습니다.
- **문제점**: 하지만 TTS, Source, Image, Render 등 실제 백그라운드 Worker들의 생존 여부나 Heartbeat, Job State를 조회하는 로직이 **전혀 없습니다**.
- **개선 방향**: 계획서 Step 2에 명시된 대로 SQLite DB 연동 또는 API 조회를 통해 `tts_state`, `tts_heartbeat_at`, `tts_job_id`를 확인하고, `TTS_WORKER_MISSING` 등의 Critical Finding을 반환하도록 기능 추가가 시급합니다.

### 2.2 `scripts/newauto_stepwise_mcp.py`
- **현상**: `repair_runtime` 도구가 존재하며, `_cleanup_worker_lock`을 통해 `tts_worker.lock`, `render_worker.lock` 등의 stale lock을 제거하는 기능은 있습니다.
- **문제점**: 락만 지울 뿐, 실제로 죽어있는 `run_tts_job.py`나 `app.workers.tts_worker` 프로세스를 재시작하거나, DB의 `tts_state = running` 상태를 `queued`로 초기화하여 재시도를 유도하는 "Closed-loop Recovery"가 부족합니다.
- **개선 방향**: 계획서 Step 3의 제안처럼, 아예 `repair_tts(project_id="")` 라는 전용 도구를 분리하거나, 기존 `repair_runtime` 안에 **"DB 초기화 + 워커 재시작 + 산출물(`timings.json` 등) 검증"** 로직을 캡슐화해야 합니다.

### 2.3 Workflow Wait Repeat Guard (`newauto_mcp.py`)
- **현상**: 현재 `continue_video_workflow`가 호출될 때 이전 상태와 현재 상태를 비교하여 반복 횟수를 카운팅하는 방어 로직(Guard)이 없습니다.
- **문제점**: `tts_wait`가 계속 반환되어도 프롬프트 지시에 의존하여 Cline 스스로가 판단해야 하므로, LLM의 변덕에 따라 무한 반복이나 엉뚱한 옵션 질문(1/2/3 선택)이 발생합니다.
- **개선 방향**: `storage/stepwise_workflows/<project_id>.json` 파일에 `last_wait_step` 및 `wait_repeat_count` 필드를 추가하여, 하네스 자체에서 반복이 2회를 넘어가면 무조건 `forensic_diagnose` 결과나 OpenRouter 호출 가이드를 반환하도록 MCP 서버 레벨에서 강제하는 것이 바람직합니다.

### 2.4 OpenRouter Rate Limit 및 Timeline
- **현상**: `timeline.md`에 따르면 최근 `google/gemma-4-31b-it:free`에서 Upstream rate limit이 발생하여 `google/gemma-4-26b-a4b-it:free` -> `openai/gpt-oss-20b:free`로 폴백(Fallback)하는 작업이 구현되었습니다.
- **확인**: 계획서의 Step 5(Provider limit과 Budget limit의 분리)는 매우 시의적절합니다. LLM이 429 에러를 단순히 "내 계정 한도 초과"로 오인하여 포기하지 않도록, `openrouter_subagent_harness.py`의 메타데이터 파싱 로직에서 이를 명확히 분리하여 반환해야 합니다.

## 3. 의견 및 추가 제안사항 (Recommendations)

계획서의 Implementation 순서(Step 1 ~ Step 5)에 100% 동의하며, 구현 시 다음 사항들을 추가로 고려하시기를 권장합니다.

1. **복구 도구의 파괴적 특성 방어**
   `repair_tts`나 `repair_runtime`이 섣불리 정상 작동 중인 작업을 날리지 않도록, 반드시 `storage/projects/<pid>/tts/timings.json` 파일의 존재 여부와 최근 수정 시간(LastWriteTime)을 먼저 체크하도록 안전장치를 마련해야 합니다.
2. **.clinerules Mandatory Escalation 규칙 최상단 배치**
   현재 `.clinerules` 파일의 "Recovery Loop"나 "TTS Rules" 섹션 사이에 로직이 분산될 수 있습니다. 제안하신 `Mandatory Escalation` 규칙은 Cline의 행동을 강제하는 가장 강력한 조건이므로, 문서 최상단(또는 별도 명확한 헤딩)에 배치하여 프롬프트 인젝션이나 우선순위 밀림을 방지해야 합니다.
3. **OpenRouter 프롬프트의 컨텍스트 다이어트**
   OpenRouter Subagent 호출 시, 429 Rate Limit 방어와 토큰 절약을 위해 전체 로컬 에러 로그를 보내지 않고, `forensic_diagnose`의 `critical_findings`와 `recommended_actions` JSON 결과만 정제하여(Local facts only) 전달하도록 `ask_openrouter_subagent` 툴의 Payload를 규격화하는 것이 좋습니다.

## 4. 실행 결론
이 계획은 즉시 실행 가능(Actionable)하며 기술적 타당성이 매우 높습니다. 제안하신 **우선순위(1. `.clinerules` 업데이트 -> 2. `forensic_doctor` 강화 -> 3. `repair_tts` 추가 -> 4. Guard 로직)** 대로 작업을 시작하실 수 있습니다.

---
문서가 성공적으로 저장되었습니다. 추가 작업이나 실제 코드 구현 단계로 넘어가시겠습니까?
