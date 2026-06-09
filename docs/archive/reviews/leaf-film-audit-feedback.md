# Leaf Film Video Upgrade Plan — Code Review & Feedback

Project: `28ce3f120c69`

> [!NOTE]
> 이 문서는 `leaf-film-video-upgrade-plan.md` 계획서를 코드베이스 및 워크플로우와 상세 대조한 뒤, 발견된 문제점·보완사항·구현 의견을 정리한 것입니다. 원본 계획서는 수정하지 않습니다.

## Contact Sheet 확인

![Leaf Film Diagnostic Contact Sheet](C:\Users\petbl\.gemini\antigravity\brain\a3ac3b00-0346-4d90-a6f7-e97315973df6\artifacts\diagnostic_contact_sheet_leaf_film.jpg)

컨택트시트 확인 결과, 계획서의 Scene-by-Scene 진단이 정확합니다. 특히 Scene 03(미세플라스틱), Scene 07(분해 과정), Scene 10(폐기물+토양 보전 동시 해결)은 이미지가 문장의 핵심 개념과 시각적으로 연결되지 않는 것이 명백합니다.

---

## 1. 도메인 감지: `research`가 과잉 매칭되는 치명적 버그

### 코드 확인

[domain_detection.py](file:///c:/Users/petbl/newauto/app/services/domain_detection.py)의 `TECH_NEEDLES`에 `"research"`가 포함되어 있습니다:

```python
TECH_NEEDLES = (
    "ai", "artificial intelligence", "llm", "gpu", ...
    "research",   # ← 이 단어 하나로 모든 연구 기사가 tech 도메인으로 분류
    "agent", "agents", ...
)
```

### 문제의 심각도

- `research`는 KAIST 낙엽 필름 기사뿐 아니라, **모든 학술/과학/사회과학/의료 기사**에 등장하는 범용 단어입니다.
- `model`도 마찬가지: "예측 모델", "비즈니스 모델", "수학적 모델" 등 AI와 무관한 맥락에서 빈번히 등장합니다.
- `training`도 위험: "직원 교육(training)", "체력 훈련" 등.

### 보완 의견

계획서의 "broad terms 제거 또는 공동 등장 요구" 제안이 정확합니다. 구체적으로:

```
기존:  "research" → tech
개선:  "research" + ("ai"|"llm"|"gpu"|"model training"|"inference") → tech
       "research" + ("soil"|"crop"|"leaf"|"film"|"polymer") → agriculture_environment
       "research" 단독 → essay (기본)
```

> [!IMPORTANT]
> `is_tech_domain()`은 현재 **단일 needle 매칭**(`any(needle in joined for needle in TECH_NEEDLES)`)입니다. `model`, `training`, `research`를 남겨두면 과학 기사가 전부 tech으로 오분류됩니다. 단순 삭제가 아닌 **co-occurrence 조건** 또는 **needle 가중치** 방식이 필요합니다.

> [!WARNING]
> `_domain_for_project()`의 우선순위 체인([visual_planner.py:48-56](file:///c:/Users/petbl/newauto/app/services/visual_planner.py#L48-L56))이 `tech → news_explainer → essay` 순서입니다. `agriculture_environment`를 추가할 때 이 체인의 삽입 위치가 중요합니다. `tech`보다 먼저 검사하면 농업 기사 내 AI 언급을 놓치고, `essay` 바로 앞에 넣으면 정상 작동합니다.

---

## 2. 후보 점수 체계: 메타데이터 부재가 실질 품질 저하로 오인되는 구조

### 코드 확인

[comfyui_pipeline.py:184-263](file:///c:/Users/petbl/newauto/app/services/comfyui_pipeline.py#L184-L263)의 `_compute_candidate_score_details()`:

| 점수 항목 | 최대 배점 | 조건 |
|---|---|---|
| `coverage_pass` | 0.24 | `keyword_coverage.passed == True` |
| `must_show_coverage` | 0.22 | `must_show` 항목 매칭 비율 |
| `issue_free` | 0.18 | issue_codes 없음 |
| `literal_simile` | 0.08 | simile 우선순위 |
| `keyword_hits` | 0.08 | primary_keywords 매칭 |
| `non_fallback` | 0.08 / -0.08 | visual_plan 소스 |
| `generic_penalty` | -0.10 | 제네릭 키워드 패널티 |
| `negative_global_avoid` | 0.08 | avoid 항목 포함 여부 |
| `file_sanity` | 0.04 | 파일 크기 |

수동 프롬프트 시 `visual_plan`이 없어 `non_fallback = -0.08`, `keyword_coverage`가 불완전해 `coverage_pass = 0`, `issue_free = 0`이 됩니다. 최대 가능 점수가 이론적으로도 **약 0.42** 수준입니다.

### 보완 의견

계획서의 "도메인별 점수 프로파일" 제안에 동의하며, 추가 의견:

1. **수동 프롬프트 감지 로직 추가**: `visual_plan`이 없고 `prompt_item`에 `visual_brief`가 없는 경우를 "manual art-directed"로 분류하여 별도 점수 산식을 적용해야 합니다.
2. **Vision QA 비중 상향**: 현재 최종 점수는 `(prompt_score * 0.85) + (vision_qa * 0.15)`([comfyui_pipeline.py:374](file:///c:/Users/petbl/newauto/app/services/comfyui_pipeline.py#L374))입니다. 수동 프롬프트의 경우 프롬프트 메타데이터가 의미 없으므로 Vision QA 비중을 `0.50` 이상으로 올려야 합니다.
3. **도메인 특화 `file_sanity` 보정**: 농업/과학 이미지는 고해상도 사진 스타일이 많아 파일 크기가 클 수 있으므로, 도메인에 따라 정규화 기준을 조정하는 것이 좋습니다.

---

## 3. 리페어 리트라이: 수동 프롬프트를 망치는 자동 수정 루프

### 코드 확인

[image_worker.py:238-487](file:///c:/Users/petbl/newauto/app/workers/image_worker.py#L238-L487)의 메인 루프:

```
attempt 0: 원본 프롬프트로 생성 → import → 점수 확인
→ retry_recommended == True이면:
  attempt 1: repair_prompts()로 수정된 프롬프트로 재생성
```

[prompt_repair.py:42-111](file:///c:/Users/petbl/newauto/app/services/prompt_repair.py#L42-L111)의 `repair_prompts()`:

- issue_codes가 비어있어도 마지막 else 분기에서 **무조건** `must_show` + `"clear visual metaphor"` 를 prepend하고 `should_retry = True`를 반환합니다.
- 이는 수동으로 정교하게 작성된 "fallen leaves transforming into translucent biodegradable mulch film..." 같은 프롬프트 앞에 무관한 에세이 메타포 용어를 삽입하는 결과를 초래합니다.

### 보완 의견

> [!CAUTION]
> **`repair_prompts()`의 fallback else 분기가 위험합니다.** issue_codes가 비어있다는 것은 프롬프트 자체에는 구조적 문제가 없다는 뜻입니다. 그런데도 "generic_retry_reinforcement"로 수정을 시도합니다. 이 분기의 `should_retry`를 `False`로 바꾸거나, 최소한 수동 프롬프트일 때는 스킵하는 가드가 필요합니다.

계획서의 retry_reason 세분화(`metadata_score_low`, `vision_qa_failed`, `prompt_coverage_failed`, `manual_prompt_needs_review`) 제안에 추가로:

- **`manual_art_directed` 플래그가 있으면 auto-repair를 완전히 스킵**하고, 대신 "이 프롬프트는 수동 작성이므로 자동 수리를 하지 않음" 이유를 `candidate_reviews`에 기록하는 것이 안전합니다.
- 현재 `_is_heavy_retry_item()` 가드가 LoRA/Style Reference/Control Image 사용 시 리트라이를 스킵하는데, 동일한 패턴으로 `manual_art_directed` 가드를 추가하면 기존 아키텍처와 일관됩니다.

---

## 4. `allow_low_quality_generated_images` 바이패스: 현재 구현의 맹점

### 코드 확인

[visual_relevance.py:114-125](file:///c:/Users/petbl/newauto/app/services/visual_relevance.py#L114-L125):

```python
def _should_validate_generated_assets(project, mapping, prompt_item):
    if project["visual_source_mode"] == "comfyui_auto":
        return True
    if _as_bool(project["body_image_options"].get("allow_low_quality_generated_images")):
        return False  # ← 모든 검증을 건너뜀
    ...
```

이 플래그가 `True`이면 `validate_generated_image_mappings()`이 **빈 리스트를 반환**합니다. 즉:
- 문장 해시 불일치 → 무시
- 프롬프트 매니페스트 누락 → 무시
- must_show 누락 → 무시
- 후보 점수 0.01 → 무시

### 보완 의견

계획서의 "`manual_art_directed` 모드로 교체" 제안이 정확합니다. 구현 시:

```python
def _should_validate_generated_assets(project, mapping, prompt_item):
    if project["visual_source_mode"] == "comfyui_auto":
        return True
    if _as_bool(project["body_image_options"].get("manual_art_directed")):
        return "light"  # 새 반환 값: 경량 검증만 수행
    if _as_bool(project["body_image_options"].get("allow_low_quality_generated_images")):
        return False  # 점진적 마이그레이션을 위해 잠시 유지
    ...
```

경량 검증 체크리스트:
- ✅ 이미지 파일 존재
- ✅ 문장 해시 일치
- ✅ 유효한 이미지 dimensions
- ✅ Vision QA hard fail 없음 (`LOW_RESOLUTION`, `EXTREME_EXPOSURE`)
- ⬜ 메타데이터 기반 점수 (skip)
- ⬜ must_show coverage (skip)

---

## 5. 시각 어휘(Visual Vocabulary) 확장: 구조적 제안

### 현재 상태

| 파일 | 용도 |
|---|---|
| `diagram.json` | AI/GPU/브라우저/비교/일정/노력 |
| `essay.json` | 에세이 메타포 |
| `news_explainer.json` | 뉴스/댓글/선거/여론 |
| `tech.json` | 기술 다큐멘터리 |

### 보완 의견

`agriculture_environment.json`과 `science_materials.json` 추가 제안에 동의합니다. 다만 구조에 대해:

> [!TIP]
> 계획서의 시각 템플릿 목록(`WasteToMaterial`, `FieldMulchFunction`, `PollutionFragment` 등)은 매우 좋은 방향이지만, **기존 vocab JSON의 flat 구조**(concept → keywords/icon/support/relation)와 형식이 다릅니다. 새 도메인에서 `composition_template` 필드를 추가하려면, 기존 `_diagram_vocab_matches()` 함수([image_prompting.py:358-397](file:///c:/Users/petbl/newauto/app/services/image_prompting.py#L358-L397))도 확장해야 합니다.

제안하는 `agriculture_environment.json` 엔트리 예시:

```json
{
  "concept": "waste_to_material",
  "keywords": ["낙엽", "leaf", "leaves", "폐기물", "waste", "재활용", "upcycle", "대체재", "alternative"],
  "icon": "fallen leaves transforming into thin translucent film sheet",
  "support": "arrow from leaf pile to finished material roll",
  "relation": "discarded organic waste becoming a useful agricultural material",
  "composition_template": "WasteToMaterial",
  "layout": "left_to_right_before_after",
  "avoid": ["generic recycle symbol only", "abstract circular diagram without material"]
}
```

`layout` 필드가 추가되면 프롬프트 컴파일러가 "before → after" 또는 "split comparison" 같은 구도를 강제할 수 있습니다.

---

## 6. Motion 업그레이드: `micro_motion_locked` 구현 시 주의점

### 코드 확인

[render_plan.py:4-13](file:///c:/Users/petbl/newauto/app/services/render_plan.py#L4-L13):

```python
def _default_motion(region, duration_sec, *, lock_still=False):
    if lock_still:
        return "still_locked"
    if duration_sec <= 2.5:
        return "none"
    ...
    return "slow_zoom_in"
```

현재 `lock_still=bool(media_path)`([render_plan.py:48](file:///c:/Users/petbl/newauto/app/services/render_plan.py#L48))이므로, **이미지가 있는 모든 세그먼트가 무조건 `still_locked`** 입니다.

### 보완 의견

계획서의 "sub-2% slow push-in, integer-frame sampling" 사양이 적절합니다. 다만:

1. **`micro_motion_locked`는 `render.py`의 FFmpeg 필터 체인에 새 zoompan 파라미터를 추가해야 합니다.** 기존에 zoompan 드리프트 문제로 `still_locked`로 전환한 이력이 있으므로([fps-stable-frame-and-readable-subtitle-plan.md](file:///c:/Users/petbl/newauto/fps-stable-frame-and-readable-subtitle-plan.md) 참조), 새 모션은 **정수 프레임 기반**으로만 동작해야 합니다.
2. **도메인 조건부 활성화**: `simple_diagram` 스타일에서는 아이콘 위치가 중요하므로 `still_locked`를 유지하고, 농업/과학 사진 스타일에서만 `micro_motion_locked`를 허용하는 것이 안전합니다.

---

## 7. Vision QA 확장: 현재 image_quality.py의 한계

### 코드 확인

[image_quality.py](file:///c:/Users/petbl/newauto/app/services/image_quality.py)는 현재 5가지 메트릭만 측정합니다:

| 메트릭 | 측정 대상 | 한계 |
|---|---|---|
| `resolution` | 최소 변 ≥ 512 | 해상도만 체크 |
| `entropy` | 정보량 | 복잡한 대시보드도 높은 entropy |
| `contrast` | 밝기 편차 | 의미적 관련성 무관 |
| `edge_detail` | 엣지 밀도 | 높을수록 좋다고 판단 — 복잡한 대시보드에 유리 |
| `exposure` | 밝기 중앙값 | 극단적 노출만 감지 |

### 보완 의견

계획서의 "과학/농업 이슈 코드(`MISSING_DOMINANT_FILM_OBJECT`, `SOIL_WITHOUT_PLASTIC_FRAGMENT` 등)" 제안은 방향이 맞지만, 현재 Vision QA 인프라로는 **의미적 객체 감지가 불가능**합니다. 실현 가능한 단계적 접근:

**V1 (즉시 가능 — 텍스트 기반 휴리스틱)**:
- 프롬프트에 "film", "mulch", "leaf"가 있는데 생성된 이미지의 `edge_density`가 너무 높으면 → `DENSE_COMPOSITION_RISK`
- 프롬프트에 "comparison", "split"가 있는데 이미지의 좌우 밝기 분포가 균일하면 → `COMPARISON_NOT_VISIBLE`

**V2 (중기 — 경량 CLIP 기반)**:
- `openai/clip-vit-base-patch32` 같은 가벼운 모델로 이미지-프롬프트 유사도를 측정하면, 0.55 임계값 이하 이미지를 의미적으로 걸러낼 수 있습니다.
- 다만 현재 8GB VRAM 제약과 ComfyUI/OmniVoice의 GPU 점유를 고려하면, CLIP은 CPU에서 실행하거나 이미지 생성 완료 후 GPU 해제 뒤에 실행해야 합니다.

**V3 (장기 — Vision LLM)**:
- 계획서의 opt-in `quality_mode=exhaustive` + Vision LLM 리뷰가 가장 정확하지만, 지연 시간과 비용을 고려하여 선택된 후보에만 적용하는 설계가 올바릅니다.

---

## 8. 계획서에 추가하면 좋을 사항

### 8-1. `_domain_for_project()` 체인 우선순위 명시

현재:

```
bible_longform → tech → news_explainer → essay
```

제안:

```
bible_longform → news_explainer → agriculture_environment → science_materials → tech → essay
```

`tech`를 뒤로 보내는 이유: co-occurrence 조건이 구현될 때까지, 과학/농업 기사가 tech으로 빠지는 것을 방지합니다.

### 8-2. Prompt Compiler의 도메인별 shot/style 분기 추가

`compile_positive_prompt()`([prompt_compiler.py:279-341](file:///c:/Users/petbl/newauto/app/services/prompt_compiler.py#L279-L341))에 현재 4가지 분기가 있습니다:
- `simple_diagram`
- `tech`
- `essay`
- `default` (stickman)

`agriculture_environment`가 추가되면 **5번째 분기**가 필요합니다. 이 분기는:
- 카메라: `medium wide shot, natural daylight, editorial documentary photography`
- 네거티브: `abstract dashboard, circuit diagram, cartoon character, tiny icons`
- 스타일 앵커: `clean agricultural photography, soil texture, natural material closeup`

### 8-3. 컨택트시트 자동화의 구체적 트리거

계획서에 "route or script to regenerate" 언급이 있는데, 구체적으로:
- 이미지 워커 완료 시 자동 생성 (기존 `_refresh_project_plans()` 직후)
- 또는 `/api/projects/{pid}/contact-sheet` 엔드포인트 추가
- 시트에 포함할 정보: 문장 텍스트(첫 40자), candidate_score, issue_codes, selected_reason

### 8-4. 회귀 테스트 보완

계획서의 테스트 목록이 좋은데, 한 가지 누락:

```python
# tests/test_domain_detection.py
def test_research_alone_is_not_tech():
    """'research' 단독으로는 tech 도메인이 아님"""
    project = make_project(script="연구진은 낙엽에서 나노셀룰로오스를 추출했다.")
    assert not is_tech_domain(project, project["script"])

def test_research_with_ai_is_tech():
    """'research' + 'ai'는 tech 도메인"""
    project = make_project(script="AI research team trained a new model.")
    assert is_tech_domain(project, project["script"])
```

---

## 종합 평가

| 항목 | 계획서 평가 | 코드 대조 결과 |
|---|---|---|
| 도메인 감지 오류 진단 | ✅ 정확 | `research`/`model`/`training` 과잉 매칭 확인 |
| 후보 점수 구조 문제 | ✅ 정확 | 수동 프롬프트 시 이론적 최대 ~0.42 확인 |
| 리페어 리트라이 부작용 | ✅ 정확 | fallback else 분기의 무조건 수정 확인 |
| 바이패스 플래그 위험 | ✅ 정확 | 모든 검증 스킵 확인 |
| 시각 어휘 부재 | ✅ 정확 | vocab 4개 중 농업/과학 없음 확인 |
| 모션 개선 방향 | ✅ 적절 | 기존 jitter 이력 고려 필요 |
| Vision QA 한계 인식 | ✅ 적절 | 단계적 접근(V1/V2/V3) 권장 |

> [!IMPORTANT]
> 가장 시급한 3가지:
> 1. `TECH_NEEDLES`에서 `research`, `model`, `training`의 co-occurrence 조건 추가 (모든 과학 기사 오분류 방지)
> 2. `repair_prompts()` fallback else 분기에서 수동 프롬프트 가드 추가 (좋은 프롬프트 훼손 방지)
> 3. `allow_low_quality_generated_images` → `manual_art_directed` 전환 (안전한 경량 검증 유지)
