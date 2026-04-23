# 자막 표시 개선 계획서

## 목적

현재 자막 기능은 프로젝트별 스타일 저장, ASS 렌더링, 색상/크기/위치 설정까지 구현되어 있다. 다음 개선 목표는 실제 영상에서 자막이 더 자연스럽게 보이도록 “한 문장 = 한 cue” 구조를 유지하면서, 너무 긴 문장은 최대 2줄로 보기 좋게 자동 분할하고, 자막 위치를 기존 3단계에서 5단계로 확장하는 것이다.

추가로 현재 코드베이스를 점검한 결과, 자막 폭과 표시 시간이 실제 가독성에 직접 영향을 주므로 `margin_h`, `min_display_sec`, 프리셋 버튼도 함께 계획에 포함한다.

## 현재 코드베이스 점검 결과

### 현재 구현 상태

- 자막 스타일 타입은 [app/types.py](app/types.py)에 `SubtitleStyle` 로 정의되어 있다.
- 현재 `SubtitlePosition` 은 `top | middle | bottom` 3단계만 허용한다.
- 자막 기본값과 ASS 생성은 [app/services/subtitle.py](app/services/subtitle.py)에 있다.
- 렌더링은 [app/services/render.py](app/services/render.py)에서 `subtitles.ass` 를 생성한 뒤 FFmpeg `ass=` 필터로 입힌다.
- UI 설정 패널은 [app/static/index.html](app/static/index.html), 상태/저장 로직은 [app/static/app.js](app/static/app.js)에 있다.
- 자막 스타일 저장 API는 [app/routers/projects.py](app/routers/projects.py)의 `PUT /api/projects/{pid}/subtitle-style` 이 담당한다.
- `scripts/typecheck.ps1` 가 프런트 `tsc` 와 백엔드 `mypy`를 함께 실행한다.

### 발견한 문제점

- [app/services/subtitle.py](app/services/subtitle.py)의 `_wrap_long()` 은 긴 문장을 최대 2줄로 나누지만, 분할 후보가 한쪽으로 치우친 경우를 충분히 막지 못한다.
- 현재 줄바꿈은 구두점 우선만 강해서 한국어 어절 경계와 공백 경계를 제대로 활용하지 못한다.
- 두 줄로도 `max_line_chars` 안에 들어가지 않는 긴 문장에 대한 정책이 명확하지 않다.
- ASS `MarginL`, `MarginR` 이 `120` 으로 고정되어 있어 좌우 안전 영역을 프로젝트별로 조정할 수 없다.
- 짧은 문장 cue가 너무 빨리 지나갈 때 최소 표시 시간을 보장하는 로직이 없다.
- position 이 `top/middle/bottom` 3단계라 상단 로고, 하단 워터마크, 쇼츠 UI 요소를 피하기 어렵다.
- UI 미리보기는 현재 3단계 위치만 시뮬레이션하므로 5단계 확장 시 같이 갱신해야 한다.

## 개선 범위

이번 계획은 아래 기능을 포함한다.

- 스마트 줄바꿈: 긴 문장을 최대 2줄로 자동 분할
- 자막 위치 5단계: `top`, `upper`, `middle`, `lower`, `bottom`
- 가로 여백 설정: `margin_h`
- 최소 표시 시간 설정: `min_display_sec`
- UI 프리셋 4종: 기본, 큰 글씨, 미니멀, 강조
- 기존 프로젝트와 DB 호환 유지
- 타입체크와 단위 테스트 보강

## 설계 원칙

- 한 문장은 하나의 subtitle cue 로 유지한다.
- 한 cue 안에서만 최대 2줄로 나눈다.
- 3줄 이상 자동 분할은 하지 않는다.
- 너무 긴 문장은 두 줄 중 일부가 `max_line_chars` 를 넘더라도 2줄 정책을 우선한다.
- 구두점보다 “균형 잡힌 줄 길이”를 우선한다.
- 한국어/영어 모두 공백과 구두점 경계를 우선 사용한다.
- `any` 와 `unknown` 타입은 사용하지 않는다.

## 데이터 모델 변경

### 타입 확장

[app/types.py](app/types.py)

```python
SubtitlePosition = Literal["top", "upper", "middle", "lower", "bottom"]
```

`SubtitleStyle` 에 필드 추가:

```python
margin_h: int
min_display_sec: float
```

기존 필드:

```python
margin_v: int
max_line_chars: int
position: SubtitlePosition
```

### 기본값

[app/services/subtitle.py](app/services/subtitle.py)의 `DEFAULT_SUBTITLE_STYLE` 에 추가:

```python
"margin_h": 120,
"min_display_sec": 1.0,
```

권장 범위:

- `margin_h`: `0~400`
- `min_display_sec`: `0.5~3.0`

### 기존 프로젝트 호환성

기존 DB의 `subtitle_style` JSON에는 새 필드가 없을 수 있다. `normalize_subtitle_style()` 이 기본값으로 merge 하므로 DB migration 없이 자연스럽게 호환된다.

## 스마트 줄바꿈 설계

### 기존 문제

현재 `_wrap_long(text, max_len)` 은 다음 한계가 있다.

- 구두점이 문장 초반에 있으면 첫 줄이 너무 짧아질 수 있다.
- 둘째 줄 길이가 지나치게 길어져도 검증하지 않는다.
- 공백/어절 경계를 충분히 우선하지 않는다.

### 새 함수

`_wrap_long()` 을 바로 삭제하지 말고 내부 구현을 `_smart_wrap()` 로 위임하거나, 호출처를 모두 `_smart_wrap()` 로 교체한다.

```python
def _smart_wrap(text: str, max_line_chars: int) -> str:
    ...
```

### 분할 알고리즘

1. 앞뒤 공백 제거
2. 길이가 `max_line_chars` 이하이면 그대로 반환
3. 두 줄이 모두 `max_line_chars` 이하가 될 수 있는 후보 범위 계산
4. 후보 범위 안에서 중앙에 가장 가까운 분할 지점을 찾음
5. 우선순위는 문장 종결 구두점, 약한 구두점, 공백, 강제 분할 순서
6. 후보 범위가 성립하지 않을 만큼 긴 문장은 중앙 50% 주변에서 가장 자연스러운 지점을 찾음
7. 결과는 항상 1줄 또는 2줄만 반환

우선순위:

1. `.?!。？！`
2. `,;:，、`
3. 공백
4. 강제 중앙 분할

한국어 특성상 공백이 있으면 어절 경계를 우선하고, 공백이 없는 긴 문자열은 중앙 분할을 허용한다.

### 테스트 케이스

- 짧은 문장은 줄바꿈하지 않는다.
- 한국어 긴 문장은 공백 근처에서 2줄로 나뉜다.
- 문장 중간 근처의 마침표 또는 쉼표를 우선한다.
- 문장 초반 구두점은 무시하거나 낮은 점수로 처리해 5/95 같은 분할을 피한다.
- 공백 없는 긴 문자열은 중앙 근처에서 강제 분할한다.
- 두 줄로도 `max_line_chars` 안에 못 들어가는 문장은 2줄 오버플로를 허용한다.
- `write_srt()` 와 `write_ass()` 모두 같은 줄바꿈 결과를 사용한다.

## 자막 위치 5단계 설계

### 새 position 값

- `top`: 상단
- `upper`: 상중
- `middle`: 중앙
- `lower`: 하중
- `bottom`: 하단

### ASS 매핑

ASS alignment 와 `MarginV` 조합으로 구현한다.

| position | ASS Alignment | MarginV |
|---|---:|---:|
| `top` | 8 | 사용자 `margin_v` |
| `upper` | 8 | `int(1080 * 0.25)` |
| `middle` | 5 | 0 |
| `lower` | 2 | `int(1080 * 0.25)` |
| `bottom` | 2 | 사용자 `margin_v` |

추가 함수:

```python
def _ass_alignment(position: SubtitlePosition) -> int:
    ...

def _ass_margin_v(position: SubtitlePosition, user_margin_v: int) -> int:
    ...
```

주의:

- `upper`, `middle`, `lower` 에서는 `margin_v` 의미가 약하므로 UI에서 안내 문구를 표시한다.
- `top`, `bottom` 에서는 기존처럼 `margin_v` 를 사용한다.

## 가로 여백 `margin_h`

현재 ASS Style 라인의 `MarginL`, `MarginR` 은 `120` 으로 고정되어 있다. 이를 `SubtitleStyle.margin_h` 로 제어한다.

변경 위치:

- [app/types.py](app/types.py): `SubtitleStyle.margin_h`
- [app/services/subtitle.py](app/services/subtitle.py): 기본값, normalize, `write_ass()` Style 라인
- [app/routers/projects.py](app/routers/projects.py): `SubtitleStylePayload.margin_h`
- [app/static/index.html](app/static/index.html): slider 또는 number input
- [app/static/app.js](app/static/app.js): 타입 주석, form read/write, preview 반영

ASS 출력:

```python
f"{normalized['margin_h']},{normalized['margin_h']},"
```

## 최소 표시 시간 `min_display_sec`

짧은 cue가 너무 빨리 사라지는 문제를 줄이기 위해 `min_display_sec` 을 추가한다.

정책:

- cue 길이가 `min_display_sec` 보다 짧으면 end 시간을 늘린다.
- 다음 cue 시작 시간을 침범하지 않는다.
- 다음 cue와 최소 `0.05s` 간격을 유지한다.
- 이미 충분히 긴 cue는 변경하지 않는다.

적용 대상:

- `write_ass()`
- 가능하면 `write_srt()` 도 동일 보정 적용

예시:

```python
desired_end = max(end, start + min_display_sec)
if next_start is not None:
    desired_end = min(desired_end, max(end, next_start - 0.05))
```

## UI 개선

### 위치 선택

[app/static/index.html](app/static/index.html)의 position select 를 5개로 확장한다.

```html
<option value="top">Top</option>
<option value="upper">Upper</option>
<option value="middle">Middle</option>
<option value="lower">Lower</option>
<option value="bottom">Bottom</option>
```

### 새 입력 필드

- `margin_h`: 가로 여백
- `min_display_sec`: 최소 표시 시간

### position 안내

`position` 이 `upper`, `middle`, `lower` 일 때:

- `margin_v` 입력을 비활성화하거나
- “이 위치에서는 세로 여백이 고정 위치 계산에 의해 제한됩니다.” 안내 표시

1차 구현은 비활성화보다 안내 표시를 추천한다. 비활성화하면 기존 저장값과 UI 상태가 헷갈릴 수 있다.

### 프리셋 4종

UI only 기능으로 구현한다. 프리셋 버튼은 입력값만 바꾸고, 저장은 기존 `Save subtitle style` 버튼으로 한다.

| 프리셋 | 적용값 |
|---|---|
| 기본 | `DEFAULT_SUBTITLE_STYLE` |
| 큰 글씨 | `font_size=64`, `outline_width=3`, `shadow=2` |
| 미니멀 | `shadow=0`, `outline_width=1`, `primary_color="#DDDDDD"`, `effect="none"` |
| 강조 | `primary_color="#FFE066"`, `outline_width=4`, `effect="pop"` |

## API 변경

### `PUT /api/projects/{pid}/subtitle-style`

[app/routers/projects.py](app/routers/projects.py)의 `SubtitleStylePayload` 에 필드 추가:

```python
margin_h: int | None = Field(default=None, ge=0, le=400)
min_display_sec: float | None = Field(default=None, ge=0.5, le=3.0)
position: SubtitlePosition | None = None
```

`to_patch()` 대상 필드에도 `margin_h`, `min_display_sec` 를 포함한다.

## 테스트 계획

### 백엔드 테스트

기존 [tests/test_subtitle_rendering.py](tests/test_subtitle_rendering.py)를 확장하거나 `tests/test_subtitle_display.py` 를 추가한다.

테스트 항목:

- `_smart_wrap()` 이 짧은 문장을 그대로 반환
- `_smart_wrap()` 이 긴 문장을 최대 2줄로 반환
- 초반 구두점 때문에 한 줄이 지나치게 짧아지지 않음
- 공백 없는 긴 문자열도 2줄로 분할
- `SubtitlePosition` 5개가 모두 normalize 통과
- `upper/lower/middle` 의 ASS alignment/margin 결과 확인
- `margin_h` 가 ASS Style MarginL/MarginR 에 반영
- `min_display_sec` 이 짧은 cue end 시간을 늘림
- `min_display_sec` 이 다음 cue 시작 시간을 침범하지 않음
- 기존 subtitle style JSON에 새 필드가 없어도 기본값 merge

### 프런트엔드 타입체크

`app/static/app.js`의 JSDoc 타입을 확장한 뒤 아래를 통과해야 한다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1
```

### 전체 테스트

```powershell
.\omnivoice_env\Scripts\python.exe -m unittest discover -s tests -v
```

## 구현 순서

### Phase 1. [대기] 타입과 기본값 확장

- `SubtitlePosition` 을 5단계로 확장
- `SubtitleStyle` 에 `margin_h`, `min_display_sec` 추가
- `DEFAULT_SUBTITLE_STYLE` 과 `normalize_subtitle_style()` 확장
- `SubtitleStylePayload` 검증 필드 확장
- typecheck 실행

### Phase 2. [대기] 스마트 줄바꿈 구현

- `_smart_wrap()` 추가
- `_wrap_long()` 호출처를 새 로직으로 교체 또는 내부 위임
- SRT/ASS가 같은 줄바꿈 정책을 사용하게 정리
- 단위 테스트 추가
- typecheck 및 unittest 실행

### Phase 3. [대기] 5단계 position 렌더링 구현

- `_POSITION_VALUES` 확장
- `_ass_alignment()` 갱신
- `_ass_margin_v()` 추가
- `write_ass()` 에 적용
- position별 ASS 출력 테스트 추가
- typecheck 및 unittest 실행

### Phase 4. [대기] `margin_h`, `min_display_sec` 렌더 반영

- ASS MarginL/MarginR 을 `margin_h` 로 변경
- cue end time 보정 함수 추가
- `write_ass()` 와 `write_srt()` 에 적용
- 테스트 추가
- typecheck 및 unittest 실행

### Phase 5. [대기] UI 확장

- position select 를 5단계로 확장
- `margin_h`, `min_display_sec` 입력 추가
- 프리셋 버튼 4개 추가
- app.js 타입/상태/저장/미리보기 로직 확장
- margin_v 안내 문구 추가
- typecheck 실행

### Phase 6. [대기] 문서와 검증 마무리

- 계획서에서 완료된 Phase를 `[완료]`로 표시
- 아키텍처/워크플로우 변경 시 `research.md` 업데이트
- `timeline.md` 에 커밋 시간과 작업 요약 추가
- Git 커밋 및 푸시

## 리스크와 대응

- 긴 문장을 무조건 2줄로 제한하면 일부 문장은 한 줄이 `max_line_chars` 를 넘을 수 있다.
- 대응: 2줄 정책을 우선하되 `margin_h`, `max_line_chars` 조정으로 사용자가 보정 가능하게 한다.
- `upper/lower` 위치가 모든 영상 레이아웃에 맞지는 않을 수 있다.
- 대응: 1차는 25% 고정, 추후 position별 offset 비율을 별도 필드로 확장 가능하게 설계한다.
- `min_display_sec` 이 연속된 짧은 cue에서는 체감 효과가 작을 수 있다.
- 대응: 다음 cue 침범 방지를 우선하고, 필요하면 TTS timing 단계에서 병합 옵션을 별도 계획으로 분리한다.
- UI 프리셋이 저장 버튼 없이 즉시 저장되면 실수 가능성이 있다.
- 대응: 프리셋은 입력값만 변경하고 저장은 명시 버튼으로 유지한다.

## 완료 기준

- 긴 자막이 최대 2줄로 자연스럽게 분할된다.
- 초반 구두점 때문에 한 글자 또는 매우 짧은 줄이 생기지 않는다.
- position 5단계가 타입, API, UI, ASS 렌더링에 모두 반영된다.
- `margin_h` 가 ASS MarginL/MarginR 에 반영된다.
- `min_display_sec` 이 짧은 cue 표시 시간을 보정하되 다음 cue를 침범하지 않는다.
- 프리셋 4종이 UI에서 입력값과 미리보기를 즉시 갱신한다.
- 기존 프로젝트는 새 필드 없이도 정상 작동한다.
- `scripts/typecheck.ps1` 통과
- `python -m unittest discover -s tests -v` 통과
