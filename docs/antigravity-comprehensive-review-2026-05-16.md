# NewAuto Studio 종합 리뷰 및 개선 의견서

> 작성: Antigravity (Claude Opus 4.6)  
> 작성일: 2026-05-16  
> 검토 대상: `media-image-generation-master-guide-plan.md`, 코드베이스(52개 서비스, 6개 워커, 43개 스크립트), 워크플로우, DB, `research.md`, `timeline.md`, `issue.md`, `.clinerules`, `ops_checklist.md`, `incident_runbook.md`, `media-simplification-plan-2026-05-15.md`, `newauto-windows-studio-master-plan-2026-05-15.md`, `gemma4-operator-plan-audit-2026-05-14.md`

---

## 1. 전체 프로젝트 현황 요약

NewAuto Studio는 **대본 → 이미지 → TTS → 자막 → 렌더 → YouTube 업로드**를 자동화하는 FastAPI 기반 영상 제작 파이프라인이다. 2026-04-22부터 약 25일간 매우 빠른 속도로 개발되었으며, 현재 코드베이스는 다음 규모다:

| 항목 | 수량 |
|------|------|
| 서비스 모듈 (`app/services/`) | 52개 |
| 워커 프로세스 (`app/workers/`) | 6개 |
| 스크립트 (`scripts/`) | 43개 |
| 문서 (docs + 루트) | 30개+ |
| 테스트 파일 | 131 passed (최근 기준) |

**핵심 강점**: 엔진 자체는 상당히 완성도가 높다. autopilot, GPU guard, worker lock, preflight, operator summary, visual relevance, 도메인 감지, ComfyUI pipeline, Flow 자동화, MCP stepwise 워크플로우까지 거의 모든 핵심 기능이 구현되어 있다.

---

## 2. 문서 간 모순 및 불일치

### 2.1 🔴 Media 단계 문서 3개가 서로 충돌

현재 Media 관련 문서가 3개 존재하며, 방향이 상충한다:

| 문서 | 방향 |
|------|------|
| `media-image-generation-master-guide-plan.md` | visual planner → prompt coverage gate → 후보 scoring → visual relevance 등 **고급 자동화 강화** |
| `media-simplification-plan-2026-05-15.md` | Flow/visual relevance/repair 등 **고급 기능 전체 비활성화**, 단순 업로드+프롬프트 복사 중심 |
| `newauto-windows-studio-master-plan-2026-05-15.md` §1 | Media 단계는 `media-simplification-plan`을 **우선 기준**으로 한다고 명시 |

**문제**: master-guide-plan은 P0~P6까지 정교한 구현 우선순위를 제시하지만, simplification-plan은 이 기능들을 전부 "기본 UI에서 비활성화"한다. 두 문서가 공존하면 **어느 쪽을 따라야 하는지 혼란**이 생긴다.

**의견**: 
- `media-simplification-plan`을 **MVP/사용자 UI 기준**으로 확정
- `master-guide-plan`은 **내부 엔진 품질 기준 문서**로 재포지셔닝
- 두 문서 상단에 상호 참조와 역할 구분을 명시해야 한다

### 2.2 🟡 research.md 유지보수 한계

`research.md`는 **3,605줄, 222KB**로, 프로젝트 전체 개발 히스토리가 단일 파일에 누적되어 있다. 4/22~5/15까지의 모든 구현 메모가 시간순으로 쌓여 있어:

- 검색이 어렵고, 현재 유효한 정보와 과거 정보가 섞여 있다
- timeline.md의 후반부는 깨진 한글(mojibake)이 다수 존재한다 (라인 25~46)
- 문서 경로가 `docs/archive/legacy_logs/`로 이동됐지만, 여러 문서에서 여전히 루트 경로로 참조한다

**의견**: 
- research.md는 **아카이브로 동결**하고, 향후 구현 메모는 PR/커밋 메시지 또는 날짜별 분리 문서로 관리
- timeline.md의 mojibake 라인(25~46)을 정리하거나 "[legacy encoded entry]"로 표시

### 2.3 🟡 issue.md에서 참조하는 파일 경로 오류

`issue.md` 라인 23, 62에서 `image-context-quality-plan.md`를 `file:///c:/Users/petbl/.lmstudio/image-context-quality-plan.md`로 링크하고 있으나, 실제 파일은 **프로젝트 루트** `c:\Users\petbl\newauto\image-context-quality-plan.md`에 존재한다. `.lmstudio` 경로는 Cline/LM Studio 작업 중 잘못 생성된 경로다.

---

## 3. 코드베이스 구조적 문제

### 3.1 🔴 거대 파일 집중 위험

| 파일 | 크기 | 위험도 |
|------|------|--------|
| `scripts/newauto_mcp.py` | 107,948 bytes | 🔴 |
| `scripts/newauto_stepwise_mcp.py` | 72,586 bytes | 🔴 |
| `app/services/visual_planner.py` | 70,224 bytes | 🔴 |
| `app/services/image_prompting.py` | 61,665 bytes | 🟡 |
| `scripts/flow_browser_automation.py` | 53,207 bytes | 🟡 |
| `app/services/visual_relevance.py` | 49,412 bytes | 🟡 |
| `app/workers/image_worker.py` | 47,112 bytes | 🟡 |
| `app/services/autopilot.py` | 45,594 bytes | 🟡 |

이 파일들은 각각 **1,500~3,000줄** 수준이며, 단일 모듈이 너무 많은 책임을 지고 있다. 특히 `newauto_mcp.py`(108KB)는 유지보수와 LLM 컨텍스트 양쪽에서 심각한 병목이다.

**의견**: 
- `newauto_mcp.py`와 `newauto_stepwise_mcp.py`는 도구별로 분리 (예: `mcp_tools/workflow.py`, `mcp_tools/diagnostics.py`)
- `visual_planner.py`는 도메인별 플래너로 분리 (예: `visual_planner_ev.py`, `visual_planner_food.py`)

### 3.2 🟡 3개 Python 환경 분리 운용

`gemma4-operator-plan-audit`에서도 지적했듯이, 3개 Python 환경이 혼재한다:

1. `local-rag\.venv` — Gemma4 직접 오퍼레이터
2. `omnivoice_env` — OmniVoice TTS 전용
3. 시스템 Python / run-newauto 환경 — FastAPI + MCP

이로 인해 `port_9001_runtime_mismatch` 경고가 반복되고, 의존성 불일치 위험이 상존한다.

**의견**: 최소한 `local-rag\.venv`와 FastAPI 서버 환경을 통합하거나, `scripts/master_setup.ps1`에서 **환경 간 의존성 동기화 검증**을 필수로 추가

### 3.3 🟡 `.clinerules`와 실제 코드의 불일치

`.clinerules` 라인 15: `Primary local model: qwen/qwen3.5-9b`  
`app/config.py`: `SCRIPT_LLM_MODEL` 기본값이 `google/gemma-4-e4b`로 변경됨 (`issue.md` §2026-05-16 참조)

`.clinerules`가 Cline 에이전트의 행동을 결정하는 핵심 문서인데, 모델 정보가 실제 설정과 다르면 에이전트가 잘못된 가정으로 동작할 수 있다.

---

## 4. Media Image Generation Master Guide Plan 세부 리뷰

### 4.1 ✅ 잘 된 점

- **단일 기준 문서** 선언이 명확하다. 기존 8개 분산 문서를 통합한 점은 매우 좋다
- **generic drift** 방지 원칙이 구체적이다 (§3 금지 사항)
- **EV/배터리 도메인** 시각 객체 목록(§5)이 실용적이다
- **후보 선택 차단 기준**(§7)의 도메인별 점수 분리가 합리적이다
- **렌더 연결 규칙**(§8)의 절대 금지 항목이 실제 사고를 방지한다

### 4.2 🔴 master-guide-plan 문제점

**P2 "10문장 한 번에 긴 JSON 금지"와 현재 코드 불일치**:  
- `visual_planner.py`(70KB)는 여전히 전체 문장을 한 번에 LLM에 전달하는 경로가 존재한다
- 문장별/3문장 batch 분할은 **계획만 있고 구현이 미완성**
- LLM 응답이 길어질수록 JSON 파싱 실패율이 높아지는 문제가 `parse_utils.py`의 bracket 보정으로만 대응 중

**P3 "Prompt coverage gate" 미구현**:
- `prompt_quality.py`에 일부 issue code가 있지만, `must_show` 전수 검사와 generic filler 중심 주어 차단은 **아직 완전히 구현되지 않았다**
- master-guide-plan이 "필수"라고 명시한 기능이 코드에 없으면 문서의 신뢰도가 떨어진다

**§6 시간 제한 정책의 "추가 필요" 항목이 장기간 미해결**:
- `image_worker.py`의 heartbeat DB update 검증 로그 — 미구현
- image job 진행률 `1/10 attempt 3/4` 형식 UI 표시 — 미구현
- 이 항목들이 issue.md에도 없어 추적이 안 되고 있다

### 4.3 🟡 개선 제안

1. **§11 EV/배터리 설정 JSON에 `quality_mode` 누락**: `"quality_mode": "fast"`를 명시해야 §6의 기본 빠른 모드와 일관성이 맞다
2. **§9 UI 표시 기준이 simplification-plan과 충돌**: simplification-plan은 candidate score, retry reason, PASS/BORDERLINE/BLOCKED 등을 **기본 UI에서 숨기라**고 하는데, master-guide-plan은 **필수 표시**라고 한다. 역할 분리가 필요하다
3. **§12 완료 기준에 자동화 검증 방법이 없다**: "10문장에서 visual plan 10개 생성"을 확인하는 pytest나 smoke 스크립트가 없다

---

## 5. 워크플로우/운영 문제

### 5.1 🔴 02:00 스케줄 작업 반복 실패

최근 대화 기록에서 **02:00 예약 작업이 반복 실패**하고 있다. 원인은:
- 중복 `browser_worker_resident.py` 프로세스
- 고아 프로세스(orphaned process) 정리 미흡
- `scheduled_autopilot.py`의 preflight에서 기존 프로세스 확인이 불완전

`incident_runbook.md`에 이 패턴이 **아직 등재되지 않았다**. 가장 빈번하게 발생하는 장애인데 런북에 없으면 대응이 매번 ad-hoc이 된다.

### 5.2 🟡 LM Studio ↔ ComfyUI VRAM 충돌 체계화 부족

`media-simplification-plan` §6.1에서 VRAM handoff 정책을 상세히 기술했지만:
- 실제 코드에서 `lms.exe unload` 호출이 구현되지 않았다
- `OllamaClient.unload()`가 LM Studio에서 no-op인 점이 문서에만 기록되고 코드에 guard가 없다
- GPU guard(`gpu_guard.py`)는 LM Studio와 ComfyUI 간의 VRAM 전환을 인식하지 못한다

### 5.3 🟡 테스트 커버리지 공백

- `tests/test_flow_uivision.py` — 삭제됨, 대체 테스트 미작성
- `tests/test_visual_planner.py` — master-guide-plan의 P2(문장별 batch) 관련 테스트 없음
- `tests/test_autopilot_e2e.py` — autopilot 전체 흐름 통합 테스트 없음
- 현재 131개 테스트 중 **대부분이 단위 테스트**이고, 실제 워크플로우 E2E 테스트는 `scripts/agent_eval_smoke.py`에 의존

---

## 6. DB/상태 관리

### 6.1 🟡 SQLite 단일 파일의 한계 접근

`app/db.py`에 WAL 모드와 busy_timeout이 설정되어 있지만:
- 5개 워커 + FastAPI + watchdog이 동시에 같은 `app.db`에 접근
- 자동 마이그레이션(`_ensure_columns`)이 ALTER TABLE을 반복 — 큰 문제는 아니지만 startup이 느려질 수 있다
- 프로젝트 메타데이터가 **단일 JSON 컬럼**(`body_image_options`, `scene_plan`, `render_plan` 등)에 직렬화되어 있어, 부분 업데이트 시 **전체 JSON을 읽고-수정하고-쓰는** 패턴이 경합을 유발할 수 있다

### 6.2 🟢 개선 제안

- 워커 간 DB 경합이 실제 문제로 나타나면, `body_image_options` 같은 큰 JSON 블롭을 **별도 파일**(프로젝트 디렉토리 내 `metadata.json`)로 분리하는 것을 고려
- 당장은 WAL + busy_timeout으로 충분하나, Windows Studio 패키징 후 동시 사용자가 늘면 재검토 필요

---

## 7. 우선순위별 개선 로드맵 제안

### P0: 즉시 (1-2일)

| # | 항목 | 이유 |
|---|------|------|
| 1 | Media 문서 3개의 역할 구분 명시 | 개발 방향 혼란 제거 |
| 2 | `.clinerules` 모델명을 실제 config와 동기화 | 에이전트 오동작 방지 |
| 3 | `incident_runbook.md`에 02:00 스케줄 실패 패턴 추가 | 반복 장애 대응 체계화 |
| 4 | `issue.md`의 `.lmstudio` 경로 참조 수정 | 문서 신뢰도 |

### P1: 단기 (3-5일)

| # | 항목 | 이유 |
|---|------|------|
| 5 | `visual_planner.py` 문장별 batch 분할 실제 구현 | master-guide P2 이행 |
| 6 | Prompt coverage gate 구현 (`must_show` 전수 검사) | master-guide P3 이행 |
| 7 | VRAM handoff guard 코드 구현 (`lms.exe unload` 또는 `/v1/models` 체크) | VRAM 충돌 방지 |
| 8 | `tests/test_flow_playwright_direct.py` 작성 | 삭제된 테스트 대체 |

### P2: 중기 (1-2주)

| # | 항목 | 이유 |
|---|------|------|
| 9 | `newauto_mcp.py`(108KB) 모듈 분리 | 유지보수성 |
| 10 | research.md 동결 + 향후 기록 체계 전환 | 문서 관리 |
| 11 | image_worker heartbeat/진행률 UI 표시 | master-guide §6 미완성 |
| 12 | master-guide §12 완료 기준용 자동화 smoke 테스트 | 검증 자동화 |

### P3: 장기

| # | 항목 | 이유 |
|---|------|------|
| 13 | Python 환경 통합 또는 동기화 검증 자동화 | 런타임 안정성 |
| 14 | timeline.md mojibake 정리 | 아카이브 품질 |
| 15 | autopilot E2E 통합 테스트 | 워크플로우 회귀 방지 |

---

## 8. 종합 의견

### 잘 되고 있는 점

1. **엔진 완성도가 높다** — 52개 서비스, 6개 워커, GPU guard, worker lock, preflight, operator summary 등 프로덕션급 인프라가 이미 갖춰져 있다
2. **테스트 문화가 자리잡았다** — 131개 테스트가 통과하고 있고, typecheck/mypy도 활용 중
3. **문서화 의지가 강하다** — issue.md, ops_checklist, incident_runbook, master plan 등 운영 문서가 풍부하다
4. **simplification-plan의 방향이 올바르다** — 복잡한 자동화를 MVP에서 숨기고 사용자 경험을 단순화하는 결정은 제품화에 필수적이다

### 주의해야 할 점

1. **문서 과잉이 문서 부재보다 위험할 수 있다** — 같은 주제에 대해 3개 문서가 다른 방향을 제시하면 아무 문서도 따르지 않게 된다. **단일 기준 문서 원칙**을 Media뿐 아니라 전체에 적용해야 한다
2. **"계획 문서에 적었으니 구현된 것"이라는 착각 경계** — master-guide의 P2/P3가 대표적이다. 계획과 구현 상태를 명확히 구분하는 표기(✅ 구현됨 / ⬜ 미구현)를 모든 계획 문서에 적용해야 한다
3. **빠른 개발 속도의 부채** — 25일간의 집중 개발로 코드가 빠르게 성장했지만, 단일 파일이 70-108KB까지 커진 것은 향후 유지보수 비용을 크게 높인다
4. **에이전트(Cline/LM Studio) 의존도 관리** — 워크플로우의 상당 부분이 LM Studio MCP에 의존하는데, LM Studio가 없어도 핵심 기능이 동작해야 한다. `media-simplification-plan`과 `master-plan` §13의 "레이어 A/B 분리"가 이를 올바르게 다루고 있으므로 반드시 이행해야 한다

---

## 9. 문서별 구체적 수정 제안 요약

### `media-image-generation-master-guide-plan.md`
- 상단에 "이 문서는 **내부 엔진 품질 기준**이다. 사용자 UI 기준은 `media-simplification-plan`을 따른다" 추가
- §11 JSON에 `"quality_mode": "fast"` 추가
- §12 완료 기준마다 ✅/⬜ 구현 상태 표기 추가
- P2/P3 항목에 관련 코드 파일과 테스트 파일 경로 명시

### `issue.md`
- `.lmstudio` 경로 참조를 실제 경로로 수정
- §6 "추가 필요" 항목들의 현재 상태 업데이트

### `.clinerules`
- 라인 15 모델명을 실제 config와 동기화하거나 "config.py 기본값을 따른다"로 변경

### `incident_runbook.md`
- §10으로 "02:00 예약 작업 실패 (중복 browser_worker)" 패턴 추가
- §11로 "LM Studio/ComfyUI VRAM 충돌" 패턴 추가

### `ops_checklist.md`
- "LM Studio 모델 unload 확인" 항목 추가 (ComfyUI 생성 전)

---

*이 문서는 `c:\Users\petbl\newauto\docs\antigravity-comprehensive-review-2026-05-16.md`에 저장되었다.*
