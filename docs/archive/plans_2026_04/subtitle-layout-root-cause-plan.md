# Subtitle Layout Root Cause Plan

상태: `[완료]`

## 권장 진행 순서

1. Phase 7 테스트 먼저
2. Phase 1 `_smart_wrap`
3. Phase 2 `_effective_max_line_chars`
4. Phase 3 `_ass_margin_v`
5. Phase 4 preview 정합성
6. Phase 6 WrapStyle 안전장치
7. Phase 5 line count 보정

## 완료 내역

### Phase 7 `[완료]`

- 회귀 테스트를 먼저 추가했습니다.
- 추가된 테스트 범위:
  - 큰 폰트에서 effective line length 축소
  - 첫 줄 길이 제한
  - `lower` 위치의 lower-third 중심 계산
  - `top` 위치의 `margin_v` fine-tune
  - 스크린샷에 가까운 긴 문장 케이스

### Phase 1 `[완료]`

- [app/services/subtitle.py](C:/Users/petbl/newauto/app/services/subtitle.py)
- `_smart_wrap()` 를 한 번만 어색하게 나누는 방식에서, 첫 줄을 `max_len` 안에 맞추는 backward break 방식으로 바꿨습니다.
- 결과는 최대 2줄을 유지합니다.

### Phase 2 `[완료]`

- `_effective_max_line_chars()` 의 과한 floor를 완화했습니다.
- 큰 글꼴일수록 실제 화면 폭 기준으로 더 짧게 줄어들도록 조정했습니다.
- 문자 폭 추정도 `font_size * 1.35` 에서 더 현실적인 값으로 낮췄습니다.

### Phase 3 `[완료]`

- `lower` 가 더 이상 고정 `140` 만 쓰지 않도록 변경했습니다.
- `_ass_margin_v()` 에서:
  - position별 목표 center ratio
  - 폰트 크기
  - 줄 수
  - outline
를 반영해 margin을 계산합니다.

### Phase 4 `[완료]`

- [app/static/app.js](C:/Users/petbl/newauto/app/static/app.js)
- preview 도 backend 와 같은 `top/upper/middle/lower/bottom` center ratio를 쓰도록 바꿨습니다.
- 특히 `lower` preview 가 이제 lower-third 쪽 중심 anchor를 따라갑니다.

### Phase 6 `[완료]`

- ASS `WrapStyle` 을 `0` 으로 바꿔서 backend wrap 이 못 막는 극단 케이스에도 libass 가 추가 보호를 할 수 있게 했습니다.

### Phase 5 `[완료]`

- event 단위 실제 줄 수를 계산해 Dialogue `MarginV` override에 반영했습니다.
- 그래서 1줄 cue 와 2줄 cue 의 세로 위치가 더 일관되게 유지됩니다.

## 검증

- `scripts/typecheck.ps1`
- `node --check app/static/app.js`
- `.\omnivoice_env\Scripts\python.exe -m unittest discover -s tests -v`

## 기대 효과

- `Line Length=20`, `Font Size=96` 같은 설정에서도 이전처럼 한 줄이 과도하게 길어지지 않습니다.
- `Lower` 위치가 실제 렌더에서 더 안정적으로 lower-third 근처에 배치됩니다.
- Step 4 preview 와 실제 ASS 렌더 위치 차이가 줄어듭니다.
