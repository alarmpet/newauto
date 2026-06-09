# Essay Image Context Recovery Plan (Revised)

작성일: 2026-04-28
대상 프로젝트: `147ab80b75e9`
목표: 에세이 영상 이미지가 문장 문맥, 직유, 핵심 키워드와 더 직접적으로 맞도록 visual planner / prompt compiler / QA 흐름을 개선한다.

상태: `[Pending]`

본 plan 은 [visual-relevance-recovery-plan.md](visual-relevance-recovery-plan.md) (sentence_hash 검증 + relevance gate 완료) + [autopilot-video-quality-diagnosis-plan.md](autopilot-video-quality-diagnosis-plan.md) (TTS/visual 진단) 위에 쌓인다 — **새 시스템이 아니라 essay 도메인의 vocab/policy 보강**.

## 1. 문제 요약

최근 생성 영상의 이미지에는 자동차가 반복적으로 등장했다. 대본은 "속도보다 방향", "왜 이 길을 걷는지", "방향을 잃지 않는 걸음" 같은 표현을 쓰지만, 핵심은 자동차 이동이나 드라이브가 아니라 삶의 방향, 피로, 막막함, 노력의 감각, 느린 걸음이다.

자동차 이미지는 일부 "길" 은유에는 들어갈 수 있어도, 반복 등장 시 영상 의미를 잘못 장악한다.

## 2. 코드 검증 (현재 상태)

| 영역 | 이미 있음 (검증) | 추가/수정할 것 |
|---|---|---|
| Visual vocab | [storage/visual_vocab/essay.json](storage/visual_vocab/essay.json) — `terms[]` 4개, 각 term 에 `keywords/concept/metaphor_examples/avoid` | **`global_avoid` 신규 + `metaphor_examples` 자체 정리 (vehicle 표현 제거)** |
| Visual planner | [app/services/visual_planner.py:213-240](app/services/visual_planner.py#L213-L240) `_fallback_entry()` 존재. fallback 시 `source="fallback"` 마킹 | LLM prompt 강화 + fallback 의 sentence-specific 요소 추가 |
| Visual brief | [app/services/visual_brief.py](app/services/visual_brief.py) `build_visual_brief()` 존재 | 기존 활용 |
| Prompt compiler | [app/services/prompt_compiler.py](app/services/prompt_compiler.py) 별도 서비스 존재 | domain global_avoid 자동 negative 주입 |
| Prompt quality | [app/services/prompt_quality.py:77](app/services/prompt_quality.py#L77) `repeated_primary_terms` **이미 구현됨** | 신규 check code 추가 (vehicle, simile, generic) |
| Visual relevance | [app/services/visual_relevance.py](app/services/visual_relevance.py) sentence_hash gate 완료 | 변경 없음 — 본 plan 과 직교 |
| Candidate score | [app/services/comfyui_pipeline.py:103](app/services/comfyui_pipeline.py#L103) `candidate_score = float(source_path.stat().st_size)` — **파일 크기 기반** | score 함수 교체, candidate_score 필드는 유지 |
| Types | `VisualBrief.avoid: list[str]`, `VisualPlanEntry.avoid: list[str]` 모두 존재 ([types.py:91-122](app/types.py#L91-L122)) | **별도 `forbidden_objects` 신설 X** — 기존 `avoid` 확장 |

## 3. 실제 원인 진단 (정정 + 추가)

### 3.1 essay.json 의 metaphor_examples 자체가 자동차 유발 (원본 plan 누락)

[essay.json](storage/visual_vocab/essay.json) 의 첫 term ("방향, 길, 선택") `metaphor_examples`:

```json
[
  "quiet road fork with a compass on a folded map",   ← "road fork"
  "single signpost in a blurred busy street",          ← "busy street"
  "desk with a map, clock, and one marked route"
]
```

두번째 term ("속도, 바쁜") 의 examples:

```json
[
  "blurred city morning with one sharp alarm clock"    ← "city morning"
]
```

**vocab 자체가 vehicle-rich 영어 표현을 포함**. planner 가 이걸 그대로 prompt 로 사용 → SDXL 이 도로 + 차 그림. plan 의 §2.1 은 결과만 진단하고 **vocab 원본의 문제**를 짚지 못함.

### 3.2 Road / path 은유가 자동차로 새는 것 (원본 plan 정확)

`crossroads path`, `quiet road fork`, `blurred city background` 같은 표현 → SDXL "차 있는 도로" 로 해석.

negative prompt 에 `car`, `vehicle`, `truck`, `bus`, `parked car`, `road traffic` 부재 → 모델이 자유롭게 자동차 추가.

### 3.3 LLM visual planner 실패 후 fallback이 너무 generic (원본 plan 정확 + 코드 위치 확인)

[visual_planner.py:213-240](app/services/visual_planner.py#L213-L240) `_fallback_entry()`:
- `must_show = list(brief["must_show"])` — VisualBrief 의 must_show 그대로
- VisualBrief 가 흔히 `"large checklist with three bold check marks"` 또는 `"compass on a folded map"` 반환

→ 14개 문장 중 fallback 처리분이 모두 같은 이미지로 뭉개짐.

### 3.4 직유와 은유를 구분하지 못함 (원본 plan 정확)

"반대로 방향이 흐릴 때의 노력은 모래 위를 달리는 일과 비슷합니다." → 직유 "모래 위를 달리는 일" 을 그대로 시각화 가능. 하지만 planner 가 "방향" 키워드에 끌려 `compass on a folded map` 으로 처리.

**한국어 직유 패턴 미언급** (원본 plan 누락):
- `~과/와 비슷` (예: "비슷합니다")
- `~같은/같이`
- `~처럼`
- `~듯`
- `마치 ~`

### 3.5 Text-based QA 가 이미지 내용 검증 못 함 (원본 plan 정확)

`prompt_quality.py` 가 prompt 문자열만 검사. 이미지 안 자동차 등장 여부 미검증.

### 3.6 후보 선택 기준이 파일 크기 (원본 plan 정확)

[comfyui_pipeline.py:103](app/services/comfyui_pipeline.py#L103):

```python
candidate_score = float(source_path.stat().st_size)
```

자동차가 디테일하게 잘 그려진 큰 파일이 오히려 우선 선택될 위험.

## 4. 데이터 모델 변경

### 4.1 essay.json 구조 — 기존 + 추가 (호환 유지)

**기존**:
```json
{ "domain": "essay", "terms": [...] }
```

**추가**:
```json
{
  "domain": "essay",
  "global_avoid": [
    "car", "vehicle", "truck", "bus", "traffic", "parked car",
    "driveway", "garage", "luxury house exterior",
    "highway", "intersection", "tail lights"
  ],
  "path_vocab": {
    "footpath": ["walking trail", "narrow footpath", "forest path", "stone path", "dirt trail"],
    "road_with_no_vehicles": ["empty road at dawn, no vehicles, no traffic"],
    "vehicle_required": false
  },
  "literal_simile_examples": [
    {
      "pattern": "모래 위를 달리는",
      "must_show": ["person running on sand", "shallow footprints", "soft sand resistance"]
    }
  ],
  "terms": [
    /* 기존 — 단, metaphor_examples 정리 (아래 §4.2) */
  ]
}
```

→ visual_planner 가 essay.json 로드 시 `vocab.get("global_avoid", [])` 로 안전 기본값. 기존 tech.json 등은 영향 없음.

### 4.2 metaphor_examples 자체 정리 (원본 plan 누락 — 가장 중요)

기존 first term 의 examples 중 vehicle 표현 제거·교체:

| 기존 | 교체 후 |
|---|---|
| `quiet road fork with a compass on a folded map` | `quiet walking trail fork with a compass on a folded map` |
| `single signpost in a blurred busy street` | `single signpost on a quiet stone path with blurred crowd backdrop` |
| `desk with a map, clock, and one marked route` | (그대로 — desk 가 핵심) |
| `blurred city morning with one sharp alarm clock` | `blurred indoor morning with one sharp alarm clock` |

**vocab 정리 없이 global_avoid 만 추가하면**: positive `quiet road fork` + negative `car, vehicle` → 모델이 충돌 → 인공적인 결과 가능. 양쪽 동시 정리 필요.

### 4.3 VisualPlanEntry 필드 확장 — 기존 `avoid` 와 충돌 회피

**원본 plan 의 문제**: `forbidden_objects: list[str]` 신규 — 기존 `avoid: list[str]` ([types.py:122](app/types.py#L122)) 와 의미 중복.

**갱신**: 기존 `avoid` 를 그대로 사용 + 신규 메타데이터만 추가:

```python
class VisualPlanEntry(TypedDict):
    # 기존 필드 유지
    sentence_idx: int
    sentence: str
    ...
    avoid: list[str]               # 그대로 — domain global_avoid + sentence-specific 모두 여기로 합쳐 저장
    ...
    # 신규
    visual_priority: NotRequired[Literal["literal_simile", "core_metaphor", "concrete_action", "object_symbol"]]
    literal_simile: NotRequired[str]    # 추출된 직유 텍스트
    allow_objects: NotRequired[list[str]]  # global_avoid 를 override 하는 화이트리스트
```

**3-tier avoid 우선순위 (신규 명시)**:

```
[1] term[].avoid       (기존, vocab 안)         → 가장 specific
[2] sentence allow_objects (신규)                → global_avoid override
[3] domain global_avoid    (신규)                → domain 기본
[4] VisualPlanEntry.avoid  (기존)                → planner 가 [1]+[3] 합쳐서 저장
```

compiler 는 `avoid` 만 읽음 — 호출자가 layered merge 책임.

### 4.4 `prompt_quality_report.json` 메트릭 확장

기존:
- `repeated_primary_terms` ✓ (이미 있음)
- `keyword_coverage` ✓

추가:
```python
class EssayQualityReport(TypedDict):
    # 기존
    keyword_coverage: dict
    repeated_primary_terms: list[str]
    # 신규
    fallback_rate: float                    # source=="fallback" 비율
    forbidden_in_negative_count: int        # 정상: 누락된 forbidden = 0
    road_without_vehicle_ban_count: int     # ESSAY_ROAD_WITHOUT_VEHICLE_BAN
    literal_simile_ignored_count: int       # LITERAL_SIMILE_IGNORED
    generic_must_show_count: int            # "checklist", "compass" 등 generic 반복
```

## 5. 구현 계획

### Phase 1. essay.json 재정비 (P0)

1. **vocab 정리** (§4.2) — first term metaphor_examples 의 vehicle 표현 제거
2. `global_avoid` 추가 (§4.1) — 차량·교통 계열
3. `path_vocab` 추가 — `footpath` 우선, `road_with_no_vehicles` 양식
4. `literal_simile_examples` 추가 — "모래 위를 달리는" 같은 패턴

회귀 테스트:
- `tests/test_visual_vocab_essay.py::test_no_vehicle_terms_in_essay_examples` — examples 안에 `road`, `street`, `traffic` 어휘 부재 검증
- `test_global_avoid_includes_vehicle_set` — 핵심 차량 어휘 포함

### Phase 2. visual_planner 개선 (P0)

#### 2.1 LLM prompt 강화

[visual_planner.py](app/services/visual_planner.py) 의 prompt 에 추가:
- "문장에 concrete action 또는 physical scene 이 있으면 우선 시각화"
- "`길`/`방향` 이라고 자동으로 나침반/도로 쓰지 마라"
- "road scene 사용 시 vehicle 이 핵심이 아니면 must_show 에 vehicle 넣지 마라"
- "각 문장 must_show 가 서로 달라야 한다 (3회 이상 동일 금지)"
- "fallback 시에도 sentence-specific object 1개 이상 포함"

#### 2.2 한국어 literal_simile 추출기 (원본 plan 미명시)

```python
# app/services/literal_simile.py (신규)
import re

_SIMILE_PATTERNS = [
    re.compile(r"마치\s+(.+?)(?:과|와|처럼|같이|듯)"),
    re.compile(r"(.+?)(?:과|와)\s*비슷"),
    re.compile(r"(.+?)\s*같은\s"),
    re.compile(r"(.+?)\s*처럼"),
    re.compile(r"(.+?)\s*듯"),
]


def extract_literal_simile(sentence: str) -> str:
    for pattern in _SIMILE_PATTERNS:
        match = pattern.search(sentence)
        if match:
            phrase = match.group(1).strip()
            if 2 <= len(phrase) <= 30:   # 너무 짧/길면 false positive
                return phrase
    return ""
```

planner 가 sentence 처리 전 simile 추출 → 있으면 `visual_priority="literal_simile"` + `literal_simile=phrase` 저장 + must_show 에 phrase-derived 객체 우선.

회귀 테스트:
- `test_extract_simile_from_korean_bisut` — "비슷합니다" 케이스
- `test_extract_simile_from_cheoreom` — "처럼" 케이스
- `test_extract_simile_skips_unrelated` — false positive 방지

#### 2.3 fallback 의 sentence-specific 강화

[visual_planner.py:225-240](app/services/visual_planner.py#L225-L240) `_fallback_entry()` 에 sentence 기반 명사 추출 추가:

```python
def _fallback_entry(project, sentence_idx, sentence, domain) -> VisualPlanEntry:
    # 기존 visual_tokens
    visual_tokens = _extract_visual_tokens(project, sentence, is_tech=is_tech)
    # 신규: sentence 의 구체 명사 추출 (한국어 명사형 어미 휴리스틱)
    sentence_nouns = _extract_concrete_nouns(sentence)  # 신규 helper
    # primary_keywords 에 sentence-specific 명사 강제 포함
    primary_keywords = list(dict.fromkeys(sentence_nouns[:1] + visual_tokens[:2]))
    ...
```

→ fallback 도 문장에서 적어도 1개 단어 가져옴 → "checklist" / "compass" 만 반복 차단.

### Phase 3. prompt_compiler 에 forbidden + simile 정책 (P0)

[prompt_compiler.py](app/services/prompt_compiler.py) 변경:

#### 3.1 domain global_avoid 자동 negative 주입

```python
def compile_prompt(brief: VisualBrief, *, domain_vocab: dict | None = None) -> tuple[str, str]:
    positive = ...
    negative_parts = list(brief["avoid"])
    if domain_vocab and "global_avoid" in domain_vocab:
        negative_parts.extend(domain_vocab["global_avoid"])
    # allow_objects override
    allow = brief.get("allow_objects", [])
    negative_parts = [item for item in negative_parts if item not in allow]
    negative = ", ".join(dict.fromkeys(negative_parts))   # dedupe
    return positive, negative
```

#### 3.2 literal_simile 우선 배치

```python
if brief.get("visual_priority") == "literal_simile" and brief.get("literal_simile"):
    # positive prompt 앞부분에 simile 장면 배치
    positive = f"{simile_to_visual(brief['literal_simile'])}, {positive}"
```

#### 3.3 road/path 자동 보강

positive prompt 에 `road`, `street`, `path`, `crossroads` 가 있으면 negative 에 자동으로 `car, vehicle, traffic` 추가 (allow_objects 에 명시 없는 한):

```python
ROAD_TERMS = {"road", "street", "path", "crossroads", "highway", "intersection"}
if any(term in positive.lower() for term in ROAD_TERMS):
    if "car" not in allow:
        negative_parts.extend(["car", "vehicle", "traffic"])
```

### Phase 4. prompt_quality.py 확장 (P0)

[prompt_quality.py](app/services/prompt_quality.py) 에 신규 check code:

| Code | 조건 | 메시지 |
|---|---|---|
| `ESSAY_ROAD_WITHOUT_VEHICLE_BAN` | positive 에 road/path + negative 에 car/vehicle 부재 + allow_objects 에 car 부재 | "Road/path prompt must explicitly ban vehicles unless allowed." |
| `LITERAL_SIMILE_IGNORED` | sentence 에 simile 추출 가능 + prompt 에 simile-derived must_show 부재 | "Literal simile in sentence not reflected in prompt." |
| `FORBIDDEN_OBJECT_IN_NEGATIVE_MISSING` | domain global_avoid 항목이 negative prompt 에 없음 | "Domain forbidden object missing in negative prompt." |
| `FALLBACK_RATE_HIGH` | source="fallback" 비율 > 20% | "Fallback rate exceeds 20%." (project-level, sentence-level X) |
| `GENERIC_MUST_SHOW_REPEATED` | "checklist" / "compass" / "signpost" 등이 3회 이상 must_show 에 등장 | "Generic visual repeated across sentences." |

기존 `repeated_primary_terms` 와 함께 사용 — 중복 X.

### Phase 5. candidate selection 개선 (P1)

[comfyui_pipeline.py:103](app/services/comfyui_pipeline.py#L103) score 함수 교체:

#### V1 (text-based, 비용 0)

```python
def compute_candidate_score(
    source_path: Path,
    prompt: str,
    brief: VisualBrief,
    domain_vocab: dict,
) -> float:
    score = 0.0
    # 1. prompt compliance (must_show 포함율)
    must_show = brief["must_show"]
    hit = sum(1 for item in must_show if item.lower() in prompt.lower())
    score += (hit / max(1, len(must_show))) * 0.5
    # 2. forbidden absence (global_avoid 가 negative 에 있는지 — bonus)
    if all(forb in negative_prompt for forb in domain_vocab.get("global_avoid", [])):
        score += 0.3
    # 3. file size (tie-breaker only)
    size_norm = min(1.0, source_path.stat().st_size / 5_000_000)
    score += size_norm * 0.2
    return score
```

기존 `candidate_score` 필드 그대로 사용 — score 함수만 교체.

#### V2 (vision LLM, 비용 큼 — 별도 toggle)

gemma4:e4b multimodal 호출. 30 scenes × 60-300s = 30분~2.5시간. **autopilot 옵션 `vision_qa: bool = False` (default off)** 로 명시적 opt-in.

질문 패턴:
- "Is a car/vehicle the dominant subject? yes/no"
- "Does this image show {must_show[0]}? yes/no"

→ JSON 응답으로 score 보정.

### Phase 6. 회귀 테스트 (P0)

```python
# tests/test_visual_vocab_essay.py
def test_essay_vocab_has_global_avoid()
def test_no_vehicle_terms_in_essay_metaphor_examples()
def test_literal_simile_examples_present()

# tests/test_literal_simile.py
def test_extract_bisut_pattern()      # 비슷합니다
def test_extract_cheoreom_pattern()   # 처럼
def test_extract_gateun_pattern()     # 같은
def test_extract_deut_pattern()       # 듯
def test_extract_macheo_pattern()     # 마치 ~
def test_skip_unrelated_short()       # false positive
def test_skip_unrelated_long()        # 30자 초과

# tests/test_visual_planner.py
def test_fallback_entry_includes_sentence_noun()
def test_planner_outputs_visual_priority_when_simile()

# tests/test_prompt_compiler.py
def test_compiler_adds_global_avoid_to_negative()
def test_compiler_skips_avoid_in_allow_objects()
def test_road_in_positive_auto_adds_vehicle_negative()
def test_simile_priority_places_simile_first()

# tests/test_prompt_quality.py
def test_essay_road_without_vehicle_ban_detected()
def test_literal_simile_ignored_detected()
def test_fallback_rate_above_20pct_flagged()

# tests/test_candidate_selection.py
def test_score_includes_must_show_compliance()
def test_score_does_not_only_use_file_size()
```

### Phase 7. 에세이 재생성 acceptance (P1)

`147ab80b75e9` 재생성 후 검증 — **Phase 8 의 강제 보정 표를 test fixture 화** (코드 hardcode X):

`tests/fixtures/essay_visual_acceptance.json`:

```json
{
  "project_template": "essay_direction",
  "expectations": [
    {"sentence_idx": 0, "must_include_any": ["walking trail", "footpath", "signpost", "guiding light"], "must_avoid": ["car", "vehicle"]},
    {"sentence_idx": 5, "must_include_any": ["sand", "running on sand", "footprints"], "must_avoid": ["car", "compass", "checklist"]},
    {"sentence_idx": 10, "must_include_any": ["book", "pen", "letter", "notebook"], "must_avoid": ["car", "checklist"]}
    /* 등 */
  ]
}
```

수동 영상 검토 + 자동 fixture 검증 둘 다.

## 6. 우선순위 + 의존성

| 등급 | Phase | 이유 | 의존성 |
|---|---|---|---|
| **P0** | Phase 1 (vocab 정리 + global_avoid) | metaphor_examples 자체가 vehicle 유발 — 가장 큰 root | 없음 |
| **P0** | Phase 2 (planner + simile 추출) | fallback 의 generic 반복 차단 | Phase 1 |
| **P0** | Phase 3 (compiler forbidden 주입) | domain global_avoid 가 실제로 작동 | Phase 1, 2 |
| **P0** | Phase 4 (quality gate) | 회귀 차단 | Phase 1-3 |
| **P0** | Phase 6 (회귀 테스트) | TDD — Phase 1-4 와 함께 | (Phase 1-4 잠금용) |
| **P1** | Phase 5 V1 (text-based score) | candidate selection 개선 | Phase 4 |
| **P2** | Phase 5 V2 (vision LLM) | 옵트인, 비용 큼 | Phase 5 V1 |
| **P1** | Phase 7 (essay 재생성) | 최종 검증 | Phase 1-5 |

## 7. 위험과 대응

| 위험 | 대응 |
|---|---|
| vocab 정리 시 기존 좋은 examples 도 버려짐 | 1개씩 검토, vehicle 키워드만 정확히 교체 |
| global_avoid 가 너무 광범위 → essay 다양성 감소 | 차량·건물 외관 한정. 인물·풍경·실내는 영향 X |
| road/path 자동 negative 가 의도된 자동차 영상 차단 | `allow_objects=["car"]` override 메커니즘 |
| literal_simile 한국어 패턴 false positive | min/max length 가드 + 회귀 테스트 |
| 한국어 명사 추출 (Phase 2.3) 가 KSS/konlpy 의존 | 단순 휴리스틱 (어미 분리) — 의존성 0 |
| Phase 8 표를 코드 hardcode 시 다른 essay 깨짐 | test fixture 로만 사용, 코드 정책 X |
| candidate score V1 이 must_show 만 체크 → 시각 자체 평가 X | V2 (vision LLM) 가 최종 답이지만 비용 큼 — opt-in |
| essay.json 신규 키 (`global_avoid` 등) 미존재 환경 | `vocab.get("global_avoid", [])` 안전 fallback |

## 8. 본 plan 의 핵심 변경 (원본 대비)

1. **vocab 자체가 vehicle 유발** — 원본은 결과만 진단, 본 plan 은 essay.json metaphor_examples 직접 정리 명시
2. **3-tier avoid 우선순위 표** — term/global/sentence + allow_objects override 메커니즘
3. **`forbidden_objects` 신규 필드 X** — 기존 `VisualPlanEntry.avoid` 활용 (중복 방지)
4. **한국어 simile 정규식 5종 명시** — `비슷/같은/처럼/듯/마치` 패턴
5. **prompt_quality.py 가 이미 `repeated_primary_terms` 보유** — 신규 check code 추가만
6. **candidate_score 필드 유지, 함수만 교체** — comfyui_pipeline.py:103 의 정확한 위치
7. **Phase 8 강제 보정 표를 test fixture 화** — 코드 hardcode X
8. **Vision LLM QA (Phase 5 V2) 의 비용 명시** — 30분~2.5시간, opt-in
9. **fallback 의 sentence-specific 강화** — `_extract_concrete_nouns()` 한국어 휴리스틱 추가
10. **fallback rate 메트릭 신설** — `prompt_quality_report.fallback_rate`
11. **road in positive → vehicle negative 자동 주입** — compiler 측 정책
12. **essay.json 호환 — `vocab.get("global_avoid", [])` 안전 기본값**
13. **cross-link 명시** — visual-relevance-recovery (sentence_hash gate 완료) + autopilot-video-quality-diagnosis (TTS/visual 분리)
14. **회귀 테스트 25+ 케이스 명시** — 원본은 추상적
15. **vocab 정리 + global_avoid 동시 진행 필수** — 한쪽만 하면 prompt 충돌 (positive `road` + negative `car` = 어색한 결과)
## 9. Implementation Update (2026-04-28)

Status snapshot:
- `P0` complete: Phase 1 vocab cleanup, Phase 2 planner+simile, Phase 3 compiler, Phase 4 quality, Phase 6 tests
- `P1` V1 complete: text-based candidate score now prefers prompt compliance and essay safety over file size
- `P1` regeneration pending: project `147ab80b75e9` should be rerun under the new essay guard rails
- `P2` pending: vision LLM candidate QA remains opt-in

Implemented in code:
- `app/services/visual_vocab.py`
- `app/services/literal_simile.py`
- `app/services/visual_planner.py`
- `app/services/prompt_compiler.py`
- `app/services/prompt_quality.py`
- `app/services/comfyui_pipeline.py`
- `app/services/image_prompting.py`
- `app/types.py`
- `storage/visual_vocab/essay.json`

Key outcomes:
- essay prompts now inject domain-level vehicle bans through `global_avoid`
- literal similes are extracted and carried through `visual_priority` / `literal_simile`
- fallback planner output now includes sentence-specific concrete tokens instead of only generic compass/checklist symbols
- prompt QA now flags missing forbidden negatives, road/path prompts without vehicle bans, ignored literal similes, high fallback rate, and repeated generic primary terms
- candidate scoring now uses prompt compliance, issue-code cleanliness, literal-simile preference, and fallback penalties before small file-size tie-breaking

Verification completed:
- `powershell -ExecutionPolicy Bypass -File scripts/typecheck.ps1`
- `omnivoice_env\Scripts\python.exe -m pytest tests/test_visual_vocab_essay.py tests/test_literal_simile.py tests/test_visual_planner.py tests/test_prompt_compiler.py tests/test_prompt_quality.py tests/test_candidate_selection.py tests/test_image_prompting.py tests/test_comfyui_routes.py -q`
