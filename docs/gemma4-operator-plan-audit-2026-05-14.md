# Gemma4 Direct Operator Plan 감사 보고서

> 작성일: 2026-05-14  
> 대상 문서: `docs/lmstudio-gemma4-direct-operator-plan.md`  
> 코드베이스 기준: `C:\Users\petbl\newauto` (2026-05-14 HEAD)  
> 참조 아카이브: `docs/archive/legacy_logs/research.md`, `docs/archive/legacy_logs/timeline.md`

---

## 1. 개요 및 목적

이 문서는 `docs/lmstudio-gemma4-direct-operator-plan.md`에 기술된 LM Studio Gemma4 직접 오퍼레이터 하니스 계획을 현재 `newauto` 코드베이스와 비교 분석한 결과다. 계획서의 정확성, 누락된 사항, 개선 가능 영역을 식별하고 실행 가능한 권고안을 제시한다.

---

## 2. 현재 코드베이스 상태 (사실 확인)

### 2.1 실제로 존재하는 핵심 파일

| 파일 | 상태 | 비고 |
|------|------|------|
| `scripts/lmstudio_direct_operator.py` | ✅ 존재 | 205줄, Gemma4 직접 루프 |
| `scripts/lmstudio_openclaw_operator_mcp.py` | ✅ 존재 | 473줄, run_powershell/read_text_file/write_text_file/list_directory/open_target |
| `run-lmstudio-direct-gemma4.cmd` | ✅ 존재 | `local-rag\.venv` Python 사용, `SCRIPT_LLM_MODEL=google/gemma-4-e4b` |
| `scripts/newauto_stepwise_mcp.py` | ✅ 존재 | 1530줄, FastMCP 래퍼, 14개 도구 |
| `app/services/operator_summary.py` | ✅ 존재 | `build_operator_summary()` 완전 구현 |
| `app/services/preflight.py` | ✅ 존재 | 19개 preflight 체크 항목 |
| `app/services/preflight.py` | ✅ 존재 | `oauth`, `ffmpeg`, `disk_space`, `visual_relevance` 포함 |
| `scripts/check_cline_lmstudio_health.py` | ✅ 존재 | 헬스체크 스크립트 |
| `scripts/check_omnivoice_health.py` | ✅ 존재 | OmniVoice 헬스체크 |
| `scripts/check_comfyui_smoke.py` | ✅ 존재 | ComfyUI 연기 테스트 |
| `scripts/forensic_doctor.py` | ✅ 존재 | 딥 포렌식 진단 |
| `main_auto_producer.py` | ❌ 미존재 | 계획서 언급, 아직 미구현 |
| `.env` | ❌ 미존재 | 환경 변수 파일 없음 |
| `research.md` (루트) | ❌ 미존재 | `docs/archive/legacy_logs/research.md`로 이동됨 |
| `timeline.md` (루트) | ❌ 미존재 | `docs/archive/legacy_logs/timeline.md`로 이동됨 |

### 2.2 실제 CMD 런처 분석

```bat
@echo off
setlocal
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"
set "LLM_PROVIDER=lmstudio"
set "LMSTUDIO_BASE_URL=http://127.0.0.1:1234"
set "SCRIPT_LLM_MODEL=google/gemma-4-e4b"
set "NEWAUTO_USE_EXISTING_LMSTUDIO_MODEL=1"
"C:\Users\petbl\local-rag\.venv\Scripts\python.exe" "%~dp0scripts\lmstudio_direct_operator.py" %*
```

**중요 발견**: CMD 런처는 `local-rag\.venv` 환경을 사용하지만, `newauto` FastAPI 서버는 별도의 `omnivoice_env` 또는 `run-newauto-9002` 환경에서 실행된다. 두 Python 환경이 분리되어 있어 `operator_core` 임포트가 런타임에 실패할 수 있다.

### 2.3 operator_summary 실제 스펙

`app/services/operator_summary.py`는 이미 완전히 구현되어 있다:

```python
# build_operator_summary() 반환 필드 (실제)
{
  "version": 1,
  "generated_at": ...,
  "project_id": ...,
  "current_stage": "script|flow|tts|render|complete|blocked",
  "recommended_next_tool": "continue_video_workflow|ask_openrouter_subagent|...",
  "asset_coverage": {"attached": N, "total": N, "missing": [...], "ratio": 0.xx},
  "failure_class": "flow_error|tts_error|render_error|...",
  "human_intervention_required": bool,
  "next_autonomous_action": "..."
}
```

API 엔드포인트 `/api/projects/{pid}/operator-summary`가 이미 존재한다.

---

## 3. 계획서 문제점 분석

### 3.1 🔴 Critical: `main_auto_producer.py` 미존재

**계획서 주장**: `main_auto_producer.py`를 중심으로 한 오케스트레이션 진입점이 필요하다고 언급.  
**실제 상태**: 이 파일이 존재하지 않는다. 현재 오케스트레이션은 `scripts/newauto_stepwise_mcp.py`와 `continue_stepwise_hpsl_video_workflow()` 함수가 담당하며, `app/services/autopilot.py` 서비스가 백그라운드 워커 패턴으로 동작한다.

**권고**: `main_auto_producer.py`를 새로 만들기보다는, 기존 `newauto_stepwise_mcp.py`를 활용하는 방향이 중복을 줄인다. 꼭 필요하다면 `main_auto_producer.py`는 `newauto_mcp.py`의 `continue_stepwise_hpsl_video_workflow()`를 직접 호출하는 얇은 스크립트로 구현해야 한다.

### 3.2 🔴 Critical: Python 런타임 환경 혼선

**계획서 주장**: 단일 setup 절차로 환경을 준비한다.  
**실제 상태**: 세 개의 Python 환경이 분리 운용 중:

| 환경 | 경로 | 역할 |
|------|------|------|
| local-rag venv | `C:\Users\petbl\local-rag\.venv` | Gemma4 직접 오퍼레이터 (`run-lmstudio-direct-gemma4.cmd`) |
| omnivoice_env | `C:\Users\petbl\newauto\omnivoice_env` | OmniVoice TTS 전용 |
| newauto main env | `run-newauto-stepwise-mcp.cmd` 참조 환경 | FastAPI + MCP 서버 |

`lmstudio_direct_operator.py`가 `lmstudio_openclaw_operator_mcp`를 임포트하는데, 이 모듈이 `local-rag\.venv`에 설치된 `mcp` 패키지에 의존한다. 이 의존성이 없으면 임포트 자체가 실패한다.

**권고**: Phase 0 진단에 `python -c "from scripts import lmstudio_openclaw_operator_mcp"` 검증을 추가해야 한다.

### 3.3 🟡 Major: 헬스체크 스크립트 목록 불완전

**계획서 주장**: 특정 헬스체크 스크립트들을 Phase 진단에 사용하라고 명시.  
**실제 상태**: `scripts/` 디렉터리에는 계획서보다 더 많은 진단 도구가 있다:

```
check_assets/          (디렉터리)
check_browser_smoke.py
check_cline_lmstudio_health.py  ← 계획서 미언급
check_comfyui_smoke.py
check_encoding.py               ← 계획서 미언급
check_omnivoice_health.py       ← 계획서 미언급
check_playwright_mcp_tools.py   ← 계획서 미언급
diagnose_runtime/      (디렉터리)
forensic_doctor.py              ← 가장 강력한 진단, 계획서 활용도 낮음
```

`forensic_doctor.py`는 `newauto_stepwise_mcp.py`의 `forensic_diagnose()` 도구에서 이미 호출되고 있으며, 서버 헬스/venv 상태/브라우저 상태/TTS 아티팩트를 한 번에 점검하는 가장 포괄적인 진단 도구다. 계획서는 이를 충분히 활용하지 않는다.

### 3.4 🟡 Major: operator_summary와 preflight의 중복 설계

**계획서 주장**: 새로운 "상태 검증" 레이어를 만든다.  
**실제 상태**: 이미 두 개의 완성된 검증 레이어가 있다:

1. **`build_preflight_report()`** (`app/services/preflight.py`) - 렌더 전 19개 체크:
   - `script`, `tts_state`, `timings`, `subtitle_cues`, `subtitle_layout`
   - `tts_consistency`, `tts_manifest_text`, `media`, `media_files`, `media_metadata`
   - `media_aspect`, `plan_sync`, `render_plan_media`, `visual_relevance`
   - `ffmpeg`, `disk_space`, `oauth`

2. **`build_operator_summary()`** (`app/services/operator_summary.py`) - 에이전트 결정용:
   - `current_stage`, `recommended_next_tool`, `asset_coverage`
   - `failure_class`, `human_intervention_required`, `next_autonomous_action`

**권고**: 계획서의 "상태 검증" 절차는 이 두 API를 순서대로 호출하는 것으로 충분하다. 새로운 레이어를 만들면 유지보수 부담만 늘어난다.

### 3.5 🟡 Major: 보안 정책 불완전 기술

**계획서 주장**: API 키와 비밀값 보호를 강조.  
**실제 상태**: `lmstudio_openclaw_operator_mcp.py`에 이미 구체적인 보안 레이어가 존재:

```python
# _command_policy()의 차단 규칙 (실제 구현)
secret_markers = ("get-credential", "credential", "cookie", "authorization", 
                  "bearer", "password", "token", "secret", "apikey", "api_key")
high_risk_markers = ("format-volume", "diskpart", "cipher /w", "net user", ...)
payment_markers = ("checkout", "purchase", "payment", "billing")
destructive_patterns = (r"\bremove-item\b", r"\bdel\b", r"\bgit\s+push\b.*\s--force\b", ...)
```

또한 `read_text_file(redact_secrets=True)` 기본값으로 비밀값 라인을 `[redacted secret-like line]`으로 치환한다.

**권고**: 계획서가 이 기존 보안 메커니즘을 명시적으로 참조하고, 추가로 필요한 보안 항목(예: `.env` 파일 생성 시 `api_key` 라인 자동 redact 확인)만 언급해야 한다.

### 3.6 🟢 Minor: research.md / timeline.md 경로 오류

**계획서 주장**: 루트의 `research.md`, `timeline.md`를 참조 문서로 사용.  
**실제 상태**: 두 파일 모두 `docs/archive/legacy_logs/`로 이동됨. 루트에 존재하지 않는다.

**권고**: 계획서에서 이 파일들을 참조할 경우 전체 경로를 명시하거나, 아카이브된 레거시 기록임을 주석으로 표시해야 한다.

---

## 4. 현재 아키텍처의 강점 (계획서가 간과한 부분)

### 4.1 완성도 높은 서비스 레이어

`app/services/` 디렉터리에는 이미 48개 서비스 모듈이 존재하며, 계획서가 "새로 구현 필요"라고 암시한 많은 기능들이 이미 완성되어 있다:

| 계획서 언급 기능 | 실제 구현 위치 |
|----------------|--------------|
| 비주얼 QA | `visual_relevance.py`, `image_quality.py` |
| 프롬프트 최적화 | `prompt_compiler.py`, `prompt_repair.py`, `prompt_quality.py` |
| 씬 계획 | `scene_plan.py`, `render_plan.py` |
| 오퍼레이터 상태 | `operator_summary.py` |
| TTS 프로파일 | `tts.py`, `tts_profile.py` |
| 도메인 감지 | `domain_detection.py` |
| LLM 연동 | `llm_ollama.py`, `parse_utils.py` |

### 4.2 견고한 워커 패턴

`app/workers/`의 5개 워커 (`autopilot_worker.py`, `image_worker.py`, `render_worker.py`, `source_draft_worker.py`, `tts_worker.py`)는 모두 잠금 파일 기반의 데드-워커 감지와 `recover_interrupted_tasks()` 시작 시 자동 복구를 구현하고 있다. 계획서의 "결정론적 실행" 목표는 이미 이 패턴으로 달성되어 있다.

### 4.3 MCP 도구 표면

`newauto_stepwise_mcp.py`가 노출하는 14개 도구는 Gemma4 직접 오퍼레이터가 필요로 하는 모든 기능을 커버한다:
- `diagnose_runtime`, `forensic_diagnose` (진단)
- `start_video_workflow`, `continue_video_workflow` (워크플로우)
- `check_assets`, `generate_one_image` (에셋)
- `repair_runtime`, `repair_tts` (복구)
- `ask_openrouter_subagent`, `analyze_browser_screenshot` (에스컬레이션)
- `run_powershell`, `operator_status` (시스템)

---

## 5. 계획서 개선 권고 (우선순위 순)

### P0: 즉시 수정 필요

1. **런타임 환경 일치 검증 추가**  
   Phase 0에 다음 명령 삽입:
   ```powershell
   # local-rag venv에서 필수 임포트 확인
   & "C:\Users\petbl\local-rag\.venv\Scripts\python.exe" -c "from scripts import lmstudio_openclaw_operator_mcp; print('ok')"
   ```

2. **`main_auto_producer.py` 계획 명확화**  
   이 파일을 "신규 오케스트레이터"로 설계할 경우, `newauto_mcp.py`의 `start_stepwise_hpsl_video_workflow()` / `continue_stepwise_hpsl_video_workflow()`를 직접 임포트해야 한다. 별도 오케스트레이션 로직을 복제하면 안 된다.

3. **research.md / timeline.md 경로 수정**  
   계획서 내 참조를 `docs/archive/legacy_logs/research.md`, `docs/archive/legacy_logs/timeline.md`로 업데이트.

### P1: 계획서 다음 개정 시 반영

4. **Phase 진단에 `forensic_diagnose` 우선 사용 명시**  
   `forensic_doctor.py`는 서버 포트/venv/브라우저/TTS 아티팩트를 한 번에 점검한다. Phase 2 이후 모든 진단은 이 도구를 먼저 실행해야 한다.

5. **기존 preflight + operator_summary 활용 명시**  
   "상태 검증" 절차를 다음 두 API 호출로 표준화:
   - `GET /api/projects/{pid}/preflight` → 렌더 가능 여부
   - `GET /api/projects/{pid}/operator-summary` → 다음 에이전트 액션

6. **보안 정책 문서화 강화**  
   `_command_policy()`와 `_redact()`가 처리하는 항목을 계획서에 명시. 특히 `token`, `api_key`, `secret` 키워드가 포함된 PowerShell 명령은 자동 차단된다는 점을 운영자가 알아야 한다.

### P2: 장기 개선

7. **Shorts 품질 강화**  
   `render_formats=["shorts"]` 강제 시 `preflight.py`의 `media_aspect` 체크가 vertical media를 요구한다. 이 게이트를 에이전트가 자동으로 처리하도록 `continue_video_workflow` 내부에 shorts-aware preflight 분기 추가.

8. **QA Hard Fail 도입**  
   현재 `visual_mismatch_report.json`의 `semantic_match_score=0` 케이스가 `pass`로 처리된다. `build_preflight_report()`의 `visual_relevance` 체크에서 score 0을 Hard Fail로 처리하고, `operator_summary`의 `failure_class`를 `visual_qa_zero_score`로 설정하는 정책이 필요하다.

---

## 6. 결론

`docs/lmstudio-gemma4-direct-operator-plan.md`는 방향성은 올바르지만, 현재 코드베이스가 이미 구현한 기능들을 "미구현"으로 잘못 분류하는 경향이 있다. 계획의 실행 가치를 높이려면:

1. 기존 서비스/워커/MCP 레이어를 재발견하여 활용하는 것이 중복 구현보다 우선
2. `main_auto_producer.py`는 얇은 진입점으로만 설계하고 로직은 `newauto_mcp.py`에 위임
3. Phase 0 진단을 `forensic_diagnose` 중심으로 재구성하면 5~7분의 수동 점검을 1분 이하로 단축 가능

이 보고서 자체는 `docs/gemma4-operator-plan-audit-2026-05-14.md`에 저장됐다.
