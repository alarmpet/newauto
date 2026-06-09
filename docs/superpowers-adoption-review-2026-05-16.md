# Superpowers Adoption Plan 리뷰 및 개선 의견

> 작성일: 2026-05-16  
> 대상: `docs/superpowers-adoption-plan-2026-05-16.md`  
> 검증 방법: 코드베이스 전수 검색 + 실제 구현 대조

---

## 1. 종합 평가

Superpowers adoption plan은 **프로젝트의 핵심 문제를 정확히 진단**하고 있습니다. "워크플로우 규율 실패가 모델 능력 부족보다 더 큰 문제"라는 결론은 코드 분석 결과와 완전히 일치합니다.

다만, 문서의 일부 주장이 **실제 구현과 다르거나**, 제안된 워크플로우가 **기존 시스템과 중복**되는 부분이 있습니다. 아래에 항목별로 검증 결과와 개선안을 제시합니다.

---

## 2. 코드 검증 결과: 사실 확인

### 2.1 ✅ 정확한 주장

| 주장 | 코드 검증 |
|------|----------|
| Stickfigures LoRA 오염 문제 발생 | `image_worker.py` L30-35: `_BLOCKING_PROMPT_QUALITY_CODES`에 `EV_BATTERY_STICKFIGURE_STYLE_BLOCKED` 존재 |
| Generic fallback 이미지 프롬프트 문제 | `prompt_quality.py` L155-157: `GENERIC_FALLBACK_IN_MUST_SHOW/PROMPT` issue code 발생 |
| `operator_intervention_required` 플래그 존재 | `image_worker.py` L173, 778-781, 921: retry 한도 초과 시 설정 |
| `render_report.json` 생성 | `render_report.py` L60: `build_render_report()` 구현 완료 |
| `final_scene_review.json` 생성 | `visual_relevance.py` L924-926: `write_final_scene_review()` 구현 완료 |
| `diagnostic_contact_sheet.jpg` 생성 | `visual_relevance.py` L972-977: `write_visual_contact_sheet()` 구현 완료 |
| ffprobe 기반 검증 존재 | `render_report.py` L25-30, `render.py` L359-382: `_probe_duration()` 구현 |

### 2.2 ⚠️ 부정확하거나 누락된 주장

#### (A) 오디오 포맷: "48kHz stereo AAC" 주장 vs 실제 "24kHz mono"

> 문서 주장: "Audio must render as 48kHz stereo AAC" (§2, §3, Task 3-5)

**실제 코드 (render.py L32-33)**:
```python
AUDIO_SAMPLE_RATE = 24000
AUDIO_CHANNELS = 1
```

`_normalize_audio()` (L486-489):
```python
"-ar", str(AUDIO_SAMPLE_RATE),  # 24000
"-ac", str(AUDIO_CHANNELS),     # 1
```

`_mux()` (L844-847):
```python
"-c:a", "aac",
"-b:a", "192k",
```

→ **최종 mux는 AAC 192kbps이지만, `-ar`과 `-ac` 미지정** → ffmpeg이 입력 오디오의 24kHz mono를 그대로 유지할 가능성 높음.

> [!WARNING]
> 문서가 "48kHz stereo"를 요구하지만, 실제 코드는 **24kHz mono PCM → AAC mux**입니다. 문서의 요구사항이 올바르다면 `_mux()`에 `-ar 48000 -ac 2`를 추가해야 합니다. 반대로 24kHz mono가 의도적이라면 문서를 수정해야 합니다.

#### (B) `docs/superpowers/` 디렉토리 미생성

문서가 계획/스펙 파일 경로로 `docs/superpowers/plans/`, `docs/superpowers/specs/`를 제안하지만:
- 해당 디렉토리가 **존재하지 않음** (파일시스템 검증 완료)
- 어떤 코드도 이 경로를 참조하지 않음
- 기존 프로젝트 문서 구조(`docs/`, `docs/archive/`)와 **별도의 네임스페이스 생성**

#### (C) `collect_project_diagnostics.py` 미구현

문서 Task 2가 `scripts/collect_project_diagnostics.py`를 제안하지만:
- 해당 스크립트가 **존재하지 않음**
- 기존에 유사 기능을 수행하는 코드가 **이미 분산 구현**됨:
  - `render_report.py`: ffprobe + render 결과
  - `visual_relevance.py`: contact sheet + mismatch report + final_scene_review
  - `operator_summary.py`: 프로젝트 상태 종합

#### (D) Codex CLI plugin install 한계

문서가 "Codex App Plugins sidebar에서 설치"를 제안하지만:
- 현재 프로젝트의 주 개발 환경은 **VS Code + Antigravity/Gemini** (이 대화 자체가 증거)
- Codex CLI/App 환경이 실제로 활성화되어 있는지 검증 불가
- Superpowers의 실제 가치는 **플러그인 자체보다 워크플로우 규율**에 있으므로, 플러그인 설치에 의존하지 않는 접근이 필요

---

## 3. 아키텍처 관점 문제점

### 3.1 🔴 기존 시스템과의 중복/충돌

Superpowers가 제안하는 게이트 중 상당수는 **이미 코드에 구현**되어 있습니다:

| Superpowers 제안 | 기존 구현 | 상태 |
|-----------------|----------|------|
| "root cause before fixes" | `prompt_repair.py` + `_build_repair_suggestion()` | ⚠️ 부분 구현 |
| "verification before completion" | `preflight.py` + `render_report.py` | ✅ 구현됨 |
| "separate review of visual output" | `visual_relevance.py` + `comfyui_pipeline.py` candidate scoring | ✅ 구현됨 |
| "artifact evidence" | `diagnostic_contact_sheet.jpg` + `final_scene_review.json` + `render_report.json` | ✅ 구현됨 |
| "blocking render when visual relevance fails" | `image_worker.py` L488-500: `_BLOCKING_PROMPT_QUALITY_CODES` | ✅ 구현됨 |

**문제**: 문서가 이미 구현된 게이트를 "새로 추가해야 할 것"으로 기술하고 있어, 실제 구현자가 혼란을 겪을 수 있습니다.

### 3.2 🟡 operator_intervention_required의 불완전한 활용

`image_worker.py` L921에서 `operator_intervention_required`를 설정하지만:

```python
if operator_intervention_required:
    # 단순히 로그 메시지만 남기고 계속 진행
```

→ 렌더 파이프라인(`render.py`)에서 이 플래그를 **확인하지 않음**. 즉, operator intervention이 필요하다고 판정되어도 렌더가 **그대로 진행**됩니다.

> [!IMPORTANT]
> Superpowers의 "verification before completion" 원칙을 실질적으로 적용하려면, `render.py`의 렌더 시작 전 `operator_intervention_required` 체크를 추가해야 합니다.

### 3.3 🟡 Post-Render 오디오 검증 부재

`render_report.py`의 `build_render_report()`는 ffprobe로 최종 MP4의 스트림 정보를 수집하지만:
- **sample rate 검증** (48kHz vs 24kHz) 없음
- **채널 수 검증** (mono vs stereo) 없음
- **volume 검증** (volumedetect) 없음

문서가 제안하는 `ffmpeg volumedetect` 기반 검증은 **아직 코드에 없으며**, 이 부분은 실제로 추가가 필요합니다.

---

## 4. 개선 제안

### P0: 문서 정정 (즉시)

1. **오디오 포맷 명확화**: "48kHz stereo AAC" → 실제 의도 확인 후 코드 또는 문서 수정
2. **이미 구현된 기능 인정**: `_BLOCKING_PROMPT_QUALITY_CODES`, `preflight.py`, `visual_relevance.py`의 기존 게이트를 문서에서 인정
3. **존재하지 않는 리소스 표기**: `docs/superpowers/`, `collect_project_diagnostics.py`를 "미구현, 생성 필요"로 명시

### P1: Superpowers 원칙의 코드 레벨 적용 (3일)

기존 시스템에 없는 핵심 게이트만 추가:

| # | 작업 | 파일 | 근거 |
|---|------|------|------|
| 1 | `_mux()`에 `-ar 48000 -ac 2` 추가 (또는 24kHz mono 유지 결정) | `render.py` L825-848 | 오디오 호환성 |
| 2 | `render.py` 렌더 시작 전 `operator_intervention_required` 체크 | `render.py` | verification gate |
| 3 | `build_render_report()`에 audio sample_rate/channels 검증 추가 | `render_report.py` | post-render evidence |
| 4 | `ffmpeg volumedetect` 기반 무음 감지 추가 | `render_report.py` | artifact evidence |

### P2: 진단 번들 통합 (2일)

`collect_project_diagnostics.py` 신규 생성 대신, **기존 함수를 하나의 엔드포인트로 통합**:

```python
# app/services/diagnostics.py (신규)
def collect_project_diagnostics(project: ProjectRecord) -> dict:
    """기존 분산된 진단 함수를 하나로 통합"""
    return {
        "render_report": load_render_report(project["id"]),
        "final_scene_review": load_final_scene_review(project["id"]),
        "operator_summary": build_operator_summary(project),
        "preflight": check_preflight(project),
        # contact sheet path만 반환 (이미지 자체는 별도)
        "contact_sheet_path": str(project_dir / "diagnostic_contact_sheet.jpg"),
    }
```

→ 별도 스크립트보다 **API 엔드포인트**로 제공하는 것이 자동화에 유리.

### P3: Defect Report 템플릿 구조화 (1일)

`operator_defect_report.md`를 수동 작성 대신, **자동 생성 템플릿**으로:

```python
# app/services/defect_report.py (신규)
def generate_defect_report(
    project: ProjectRecord,
    symptom: str,
    suspected_subsystem: str,
) -> Path:
    """Superpowers 스타일 defect report 자동 생성"""
    diagnostics = collect_project_diagnostics(project)
    report = {
        "project_id": project["id"],
        "title": project["title"],
        "symptom": symptom,
        "suspected_subsystem": suspected_subsystem,
        "evidence": diagnostics,
        "root_cause_status": "investigating",
        "created_at": datetime.now().isoformat(),
    }
    # storage/projects/<pid>/operator_defect_report.json
    ...
```

### P4: Superpowers 디렉토리 정리 (즉시)

`docs/superpowers/` 디렉토리를 별도로 만들지 않고, 기존 `docs/` 구조에 통합:

```
docs/
├── superpowers-adoption-plan-2026-05-16.md     # 현재 문서
├── superpowers-adoption-review-2026-05-16.md   # 이 리뷰
├── media-prompt-operating-guide.md             # 최종 통합 가이드 (예정)
└── archive/                                     # 이전 계획 문서
```

→ `docs/superpowers/plans/`, `docs/superpowers/specs/` 는 이미 `docs/`에 날짜 기반 이름으로 관리 중인 패턴과 **충돌**합니다.

### P5: TDD 강화 (3일)

문서가 올바르게 식별한 테스트 누락 항목:

| # | 테스트 | 파일 | 현재 상태 |
|---|--------|------|----------|
| 1 | 최종 mux의 AAC sample_rate/channels 검증 | `tests/test_render_visual_track.py` | ❌ 없음 |
| 2 | volumedetect 기반 무음 감지 | `tests/test_render_report.py` | ❌ 없음 |
| 3 | `operator_intervention_required` 시 렌더 차단 | `tests/test_render_worker.py` | ❌ 없음 |
| 4 | EV battery 도메인에서 stickman LoRA 차단 | `tests/test_image_worker.py` 또는 신규 | ⚠️ 간접적 |
| 5 | business delegation 뉴스의 max-person 제약 | 신규 | ❌ 없음 |

기존 테스트 중 관련 항목:
- `test_normalize_audio_forces_pcm_24k_mono`: 24kHz mono 강제 테스트 존재 → 48kHz 전환 시 수정 필요
- `test_validate_audio_duration_alignment_raises_on_large_drift`: drift 검증 존재

---

## 5. Superpowers 플러그인 vs 워크플로우 규율

### 권장 접근법

Superpowers 플러그인의 **설치 자체에 집중하지 말고**, 핵심 원칙을 **코드 레벨 게이트**로 구현:

| Superpowers 원칙 | 코드 구현 방법 |
|-----------------|--------------|
| Systematic Debugging | `diagnostics.py` 통합 → defect report 자동 생성 |
| Verification Before Completion | `render.py`에 pre-render 검증 게이트 추가 |
| Spec Before Fix | `docs/` 날짜 기반 계획 문서 관행 유지 |
| TDD | `tests/` 누락 테스트 보강 |
| Code Review | `operator_intervention_required` → 렌더 차단 |

> [!TIP]
> Superpowers의 가치는 **플러그인 설치**가 아니라 **개발 규율의 체계화**입니다. 현재 newauto 시스템에는 이미 상당 부분의 자동 검증 인프라가 구축되어 있으므로, 부족한 **3개 게이트**(audio 검증, operator_intervention 렌더 차단, volumedetect)만 추가하면 Superpowers의 핵심 가치를 달성할 수 있습니다.

---

## 6. 코드 참조 맵

| 기능 | 파일 | 핵심 위치 |
|------|------|----------|
| 오디오 mux | [render.py](file:///c:/Users/petbl/newauto/app/services/render.py#L816-L858) | `_mux()` |
| 오디오 정규화 | [render.py](file:///c:/Users/petbl/newauto/app/services/render.py#L473-L502) | `_normalize_audio()` |
| 렌더 리포트 | [render_report.py](file:///c:/Users/petbl/newauto/app/services/render_report.py#L60) | `build_render_report()` |
| Contact Sheet | [visual_relevance.py](file:///c:/Users/petbl/newauto/app/services/visual_relevance.py#L972) | `write_visual_contact_sheet()` |
| Prompt 차단 게이트 | [image_worker.py](file:///c:/Users/petbl/newauto/app/workers/image_worker.py#L30-L89) | `_BLOCKING_PROMPT_QUALITY_CODES` |
| Operator Summary | [operator_summary.py](file:///c:/Users/petbl/newauto/app/services/operator_summary.py) | `build_operator_summary()` |
| Preflight 검사 | [preflight.py](file:///c:/Users/petbl/newauto/app/services/preflight.py) | `check_preflight()` |
| 오디오 테스트 | [test_render_visual_track.py](file:///c:/Users/petbl/newauto/tests/test_render_visual_track.py#L276) | `test_normalize_audio_forces_pcm_24k_mono` |

---

## 7. 결론

Superpowers adoption plan의 **방향성은 올바릅니다**. 다만:

1. **이미 구현된 기능**(prompt quality gate, visual relevance, preflight, contact sheet 등)을 인정하고 중복 제안을 제거해야 합니다.
2. **실제로 누락된 3개 핵심 게이트**(audio format 검증, operator_intervention 렌더 차단, volumedetect 무음 감지)에 집중해야 합니다.
3. **플러그인 설치보다 코드 레벨 게이트 구현**이 우선입니다.
4. **48kHz stereo vs 24kHz mono 결정**이 가장 긴급한 확인 사항입니다.
5. 별도 `docs/superpowers/` 네임스페이스 생성보다 기존 `docs/` 구조 활용이 유지보수에 유리합니다.

---

*이 문서는 `c:\Users\petbl\newauto\docs\superpowers-adoption-review-2026-05-16.md`에 저장되었습니다.*
