# Stickman LoRA + HyperFrames Visual Plan 리뷰

> 작성일: 2026-05-16  
> 대상: `docs/stickman-comfyui-lora-hyperframes-visual-plan-2026-05-16.md`  
> 검증: 코드베이스 전수 검색 + Superpowers systematic-debugging 원칙 적용

---

## 1. 종합 평가

이 문서는 **프로젝트에서 가장 야심적이고 상세한 비전 문서**입니다. 11개 레퍼런스 이미지를 개별 분석하고, Style DNA를 체계화하며, ComfyUI + LoRA + HyperFrames + ControlNet의 4계층 분업 아키텍처를 제안합니다.

그러나 **현재 코드베이스와의 괴리가 매우 큼**니다. 문서가 제안하는 기능의 약 80%가 미구현 상태이며, 기존 시스템과 충돌하는 설계 결정도 있습니다.

### Superpowers 평가 기준 적용

| 원칙 | 평가 |
|------|------|
| Spec Before Fix | ✅ 문서 자체가 상세한 spec 역할 |
| Systematic Debugging | ⚠️ "왜 현재 이미지가 실패하는가"를 잘 진단하지만, 실패 데이터 기반이 아닌 시각적 추론에 의존 |
| TDD | ❌ 테스트 계획 없이 6개 Phase 구현 계획만 제시 |
| Verification Before Completion | ⚠️ Phase별 Acceptance criteria 존재하나, 자동화 검증 방법 부재 |
| Writing Plans | ✅ 매우 상세한 구현 계획 |

---

## 2. 코드 검증: 현재 상태 vs 문서 제안

### 2.1 기존 Stickman 시스템 (이미 구현됨)

문서가 "새로 만들어야 한다"고 제안하는 기능 중 상당수가 **이미 존재**합니다:

| 기능 | 기존 구현 | 위치 |
|------|----------|------|
| Stickman LoRA 감지/로딩 | `_find_stickfigures_lora()` | [model_registry.py](file:///c:/Users/petbl/newauto/app/services/model_registry.py) L33-40 |
| Stickman 템플릿 라이브러리 (9개) | `STICKMAN_TEMPLATES` | [stickman_reference_library.py](file:///c:/Users/petbl/newauto/app/services/stickman_reference_library.py) L60-168 |
| 도메인별 차단 로직 | `_stickman_lora_blocked_for_prompt()` | [autopilot.py](file:///c:/Users/petbl/newauto/app/services/autopilot.py) L592-611 |
| trigger 용어 제거 | `_strip_stickman_trigger_terms()` | [autopilot.py](file:///c:/Users/petbl/newauto/app/services/autopilot.py) L614-618 |
| `txt2img_sdxl_stickman_lora` 워크플로우 | 템플릿 ID 참조 존재 | [image_prompting.py](file:///c:/Users/petbl/newauto/app/services/image_prompting.py) L1191 |
| EV_BATTERY_STICKFIGURE_STYLE_BLOCKED | blocking code | [image_worker.py](file:///c:/Users/petbl/newauto/app/workers/image_worker.py) L32 |
| LoRA 자동 fallback (차단 → basic) | 코드 분기 | [autopilot.py](file:///c:/Users/petbl/newauto/app/services/autopilot.py) L651-664 |
| LoRA strength 기본값 0.8 | `DEFAULT_STICKMAN_LORA_STRENGTH` | [autopilot.py](file:///c:/Users/petbl/newauto/app/services/autopilot.py) L43 |

### 2.2 기존 HyperFrames 시스템 (이미 구현됨)

| 기능 | 기존 구현 | 위치 |
|------|----------|------|
| overlay_plan.json 생성 | `build_overlay_plan()` | [hyperframes_overlay.py](file:///c:/Users/petbl/newauto/app/services/hyperframes_overlay.py) L31-50 |
| index.html 생성 (Noto Sans KR) | `_render_html()` | [hyperframes_overlay.py](file:///c:/Users/petbl/newauto/app/services/hyperframes_overlay.py) L73-129 |
| Korean 폰트 자동 복사 | `_copy_local_korean_font()` | [hyperframes_overlay.py](file:///c:/Users/petbl/newauto/app/services/hyperframes_overlay.py) L53-59 |
| overlay 렌더링 (npx HyperFrames) | `render_hyperframes_overlay()` | [render_hyperframes_overlay.py](file:///c:/Users/petbl/newauto/scripts/render_hyperframes_overlay.py) |
| overlay MOV/WebM 탐색 | `_hyperframes_overlay_path()` | [render.py](file:///c:/Users/petbl/newauto/app/services/render.py) L834-853 |
| render_report에 overlay 상태 기록 | `_hyperframes_overlay_output_fields()` | [render_report.py](file:///c:/Users/petbl/newauto/app/services/render_report.py) L151-175 |
| pix_fmt 검증 (yuva444p12le) | ffprobe → pix_fmt 확인 | [render_report.py](file:///c:/Users/petbl/newauto/app/services/render_report.py) L170-175 |
| system_health에 HyperFrames 상태 | `probe_hyperframes_runtime()` | [system_health.py](file:///c:/Users/petbl/newauto/app/services/system_health.py) L59-81 |

### 2.3 문서가 제안하지만 미구현인 기능 (진짜 신규 작업)

| 기능 | 상태 | 난이도 |
|------|------|--------|
| `na_stickbiz_style` trigger token | ❌ 미구현 (기존: `Stick figure`, `Flipchartvisu`) | 낮음 |
| 비즈니스 메타포 씬 템플릿 6종 | ❌ 완전 미구현 | **높음** |
| ControlNet scribble 기반 레이아웃 잠금 | ❌ ControlNet depth만 존재 | 높음 |
| blank_label 좌표 + HyperFrames 라벨 매핑 | ❌ 완전 미구현 | **매우 높음** |
| HyperFrames 다이어그램 효과 10종 | ❌ `lower_third_keyword`만 존재 | 높음 |
| LoRA 훈련 데이터셋 | ❌ `datasets/` 디렉토리 없음 | 높음 |
| `stickman_overlay_plan.py` | ❌ 미구현 | 중간 |
| `hyperframes_stickman_templates.py` | ❌ 미구현 | 중간 |
| 비즈니스 캐릭터 디자인 (navy suit, red tie) | ❌ 기존은 generic stickman | LoRA 의존 |

---

## 3. 핵심 문제점

### 3.1 🔴 Critical: 기존 Stickman 시스템과의 이중 설계

문서가 제안하는 `na_stickbiz_style` 시스템과 기존 `Stick figure` / `Flipchartvisu` 시스템이 **완전히 별개**입니다:

| 항목 | 기존 시스템 | 문서 제안 |
|------|-----------|----------|
| Trigger 토큰 | `Stick figure`, `Flipchartvisu` | `na_stickbiz_style` |
| 캐릭터 | 범용 stickman | navy suit, red tie 비즈니스맨 |
| 배경 | 흰 배경, 미니멀 | beige/gray, 메타포 오브젝트 |
| 용도 | 성경/교육 설명 | 비즈니스/투자/AI 설명 |
| 템플릿 | 9개 (prayer, battle...) | 7개 (machine_pipeline, bottleneck...) |
| LoRA 파일 | `Stickfigures-000005.safetensors` | 새 LoRA 훈련 필요 |

> [!WARNING]
> 이 두 시스템을 병합할지, 별도 운영할지 결정이 필요합니다. 병합하면 기존 성경 콘텐츠의 스타일이 변할 수 있고, 별도 운영하면 유지보수 부담이 두 배가 됩니다.

### 3.2 🔴 Critical: HyperFrames 오버레이 확장의 실현 가능성

현재 `hyperframes_overlay.py`는 **단 하나의 오버레이 유형** (`lower_third_keyword`)만 지원합니다. 문서가 제안하는 10가지 효과 템플릿(`label_plate`, `money_flow`, `network_glow` 등)은 각각 고유한 HTML/CSS/JS 렌더링 로직이 필요합니다.

**현재 아키텍처의 한계**:
```python
# 현재: 모든 아이템이 동일한 오버레이 구조
"overlay_type": "lower_third_keyword"
```

문서가 요구하는 수준:
```json
{
  "overlay_type": "label_plate",
  "box": [720, 60, 480, 110],
  "text": "메타 전략",
  "effects": [{"type": "money_flow"}, {"type": "network_glow"}]
}
```

→ 이 변환은 `hyperframes_overlay.py`의 **전면 재설계**를 의미합니다.

### 3.3 🟡 Major: LoRA 훈련 데이터의 부재

- `datasets/` 디렉토리가 존재하지 않음
- 문서가 요구하는 최소 40-60장의 curated 이미지 데이터셋이 없음
- YouTube 스크린샷에서 UI 제거/크롭하는 전처리 파이프라인이 없음
- LoRA 훈련 환경(kohya_ss 등)이 프로젝트에 통합되어 있지 않음

### 3.4 🟡 Major: ComfyUI 워크플로우 JSON 누락

`txt2img_sdxl_stickman_lora` 템플릿 ID는 코드에 존재하지만, 문서가 제안하는 `stickman_business_explainer_sdxl.json` 워크플로우 파일은 **존재하지 않음**. 기존 LoRA 워크플로우와 비즈니스 설명 워크플로우가 동일한 JSON을 공유할지 결정 필요.

### 3.5 🟡 Major: blank_label 좌표의 ComfyUI → HyperFrames 전달 경로 없음

문서의 핵심 혁신인 "ComfyUI가 blank sign을 생성하고 HyperFrames가 라벨을 채운다"는 전략을 실현하려면:

1. Visual planner가 `blank_labels` 좌표를 출력해야 하고
2. 그 좌표가 ComfyUI 생성 이미지의 실제 blank 영역과 일치해야 하며
3. HyperFrames가 해당 좌표에 정확히 텍스트를 배치해야 합니다

이 3단계 파이프라인은 **어떤 코드에도 구현되어 있지 않으며**, 특히 "생성된 이미지의 blank 영역 좌표"를 자동으로 감지하는 것은 CV 수준의 후처리가 필요합니다.

---

## 4. Superpowers 관점 개선 제안

### 4.1 Systematic Debugging: 실패 사례 먼저

문서가 §"Why Current Simple Generated Images Fail" 섹션에서 실패 원인을 열거하지만, **실제 실패 데이터를 참조하지 않습니다**.

**개선**: Phase 1 이전에 "Evidence Bundle" 단계 추가:
```
Phase 0: 기존 generic 이미지 5개를 수집 → 실패 분류 →
         실제 blank_label 감지 가능성 테스트 → LoRA 필요성 정량 검증
```

### 4.2 TDD: Phase별 테스트 선행

각 Phase에 **failing test 먼저** 작성:

| Phase | 선행 테스트 |
|-------|-----------|
| Phase 1 | `test_stickman_business_template_outputs_blank_signs()` |
| Phase 2 | `test_visual_planner_maps_sentence_to_metaphor_template()` |
| Phase 3 | `test_comfyui_workflow_accepts_stickman_business_placeholders()` |
| Phase 4 | `test_lora_checkpoint_preserves_blank_panels()` |
| Phase 5 | `test_hyperframes_label_plate_renders_korean_in_box()` |
| Phase 6 | `test_quality_gate_rejects_generated_text_in_label_area()` |

### 4.3 Verification Before Completion: 자동 검증 도구

Phase 6의 Quality Gate를 코드로 구체화:

```python
# app/services/stickman_quality.py (제안)
def check_stickman_frame_quality(image_path: Path) -> dict:
    """
    1. edge_density: 2D vector art 특성 확인
    2. palette_conformance: beige background 검증
    3. text_artifact_score: OCR로 gibberish text 감지
    4. blank_panel_detection: blank sign 영역 좌표 추출
    """
```

---

## 5. 실현 가능한 단계적 접근법 (수정 로드맵)

### Phase 0: Evidence Bundle (1일)

기존 시스템으로 비즈니스 설명 이미지 4장 생성 → 실패 유형 분류 → 개선 방향 정량화

### Phase 1A: 기존 시스템 확장 (3일)

새 LoRA를 훈련하기 **전에**, 기존 `Stickfigures` LoRA + 프롬프트 개선으로 달성 가능한 수준 측정:

- `stickman_reference_library.py`에 비즈니스 메타포 템플릿 3개 추가 (`machine_pipeline`, `bottleneck`, `scale_comparison`)
- 기존 LoRA 강도/프롬프트 조합 grid 테스트
- 결과가 문서의 "Target Style"에 근접하면 LoRA 훈련 불요

### Phase 1B: HyperFrames lower-third 확장 (2일)

현재 `lower_third_keyword`를 확장하여 `label_plate` 지원:

```python
# 기존 overlay_type에 label_plate 추가
if item["overlay_type"] == "label_plate":
    # box 좌표 기반 절대 배치
    # auto-fit 폰트 크기
```

### Phase 2: LoRA 훈련 결정 게이트 (Phase 1 결과에 따라)

기존 LoRA로 부족하면:
- 데이터셋 수집 (최소 60장)
- 캡션 작성 (`na_stickbiz_style` trigger)
- kohya_ss SDXL LoRA 훈련
- 고정 프롬프트 grid 비교

### Phase 3: 2-Layer Rendering 통합 (Phase 1B + Phase 2 이후)

- visual planner에 `overlay_labels` 필드 추가
- ComfyUI → base image → HyperFrames → label overlay → 최종 합성
- render.py에 2-layer 합성 경로 추가

---

## 6. 문서와 코드의 용어 통일 필요

| 문서 용어 | 현재 코드 용어 | 권장 |
|----------|-------------|------|
| `na_stickbiz_style` | `Stick figure`, `Flipchartvisu` | 새 LoRA면 `na_stickbiz_style`, 기존이면 유지 |
| `stickman_business_explainer` | (없음) | `stickman_business` (domain_detection에 추가) |
| `machine_pipeline` | (없음) | visual_planner의 `scene_template` 필드에 추가 |
| `blank_labels` | (없음) | visual_plan 스키마에 추가 |
| `overlay_text` | (없음) | overlay_plan의 items에 추가 |

---

## 7. 코드 참조 맵

| 기능 | 파일 | 핵심 위치 |
|------|------|----------|
| Stickman 템플릿 | [stickman_reference_library.py](file:///c:/Users/petbl/newauto/app/services/stickman_reference_library.py) | `STICKMAN_TEMPLATES` |
| LoRA 감지 | [model_registry.py](file:///c:/Users/petbl/newauto/app/services/model_registry.py#L33-L40) | `_find_stickfigures_lora()` |
| LoRA 차단 로직 | [autopilot.py](file:///c:/Users/petbl/newauto/app/services/autopilot.py#L592-L611) | `_stickman_lora_blocked_for_prompt()` |
| HyperFrames overlay | [hyperframes_overlay.py](file:///c:/Users/petbl/newauto/app/services/hyperframes_overlay.py) | `build_overlay_plan()` |
| HyperFrames 렌더링 | [render.py](file:///c:/Users/petbl/newauto/app/services/render.py#L864-L894) | `_prepare_hyperframes_overlay()` |
| overlay report | [render_report.py](file:///c:/Users/petbl/newauto/app/services/render_report.py#L151-L175) | `_hyperframes_overlay_output_fields()` |
| 런타임 상태 | [system_health.py](file:///c:/Users/petbl/newauto/app/services/system_health.py#L59-L81) | `probe_hyperframes_runtime()` |
| image_prompting 템플릿 | [image_prompting.py](file:///c:/Users/petbl/newauto/app/services/image_prompting.py#L93-L217) | 도메인별 `StickmanTemplate` |
| ComfyUI 워크플로우 | [comfyui_workflows.py](file:///c:/Users/petbl/newauto/app/services/comfyui_workflows.py) | 템플릿 로딩 |

---

## 8. 결론

### 문서의 강점
- 시각 언어 분석이 매우 정밀하고, Style DNA가 잘 정의됨
- ComfyUI + LoRA + HyperFrames + ControlNet의 4계층 분업 구상이 아키텍처적으로 올바름
- 씬 템플릿 라이브러리 구상이 재사용성 높음

### 문서의 약점
1. **기존 시스템과의 관계가 불명확** → 기존 9개 stickman 템플릿 + LoRA 인프라를 무시하고 새로 설계
2. **구현 규모 과소평가** → 6 Phase 중 Phase 2-5는 각각 1-2주 소요 예상 (문서는 암묵적으로 며칠 단위)
3. **LoRA 훈련 전 검증 부재** → 기존 LoRA로 프롬프트만 개선해도 80% 달성 가능한지 먼저 테스트해야 함
4. **blank_label 좌표 자동 감지의 기술적 난이도 누락** → 이것이 전체 파이프라인의 가장 큰 기술적 위험
5. **TDD 계획 없음** → Superpowers 원칙 위반

### 권장 우선순위

```
1. 기존 LoRA + 프롬프트 개선으로 비즈니스 메타포 이미지 테스트 (1일)
2. HyperFrames label_plate 오버레이 타입 추가 (2일)
3. LoRA 필요 여부 결정 게이트 (1의 결과 기반)
4. 나머지 Phase는 3의 결과에 따라 진행
```

---

*이 문서는 `c:\Users\petbl\newauto\docs\stickman-lora-hyperframes-plan-review-2026-05-16.md`에 저장되었습니다.*
