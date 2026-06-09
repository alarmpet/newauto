# FPS Stable Frame and Readable Subtitle Upgrade Plan

작성일: 2026-04-28
상태: 계획서 작성 완료, 구현 미착수

## 1. 목표

현재 1장 또는 소수 이미지로 영상을 만들 때 줌/팬 효과가 들어가면 이미지가 흔들려 보인다. 이 계획의 목표는 다음 세 가지다.

1. 정지 이미지 기반 영상은 FPS에 맞춰 동일 프레임을 안정적으로 복제해 흔들림 없는 결과를 만든다.
2. 자막은 한 문장 전체를 한 번에 띄우지 않고, 사람이 읽기 좋은 문장/구 단위로 분할한다.
3. 렌더 결과가 TTS 길이, 자막 타이밍, 이미지 타임라인과 실제 출력 영상 길이까지 일치하는지 자동 검증한다.

## 2. 현재 구조에서 확인한 사실

### 2.1 이미지 흔들림의 직접 원인

`app/services/render.py`의 `_zoompan_filter()`는 이미지 입력에 `zoompan` 필터를 사용한다.

현재 필터 특징:

- 이미지 입력을 `-loop 1 -framerate 1`로 받고, `zoompan` 내부에서 `d=duration * FPS` 프레임을 만든다.
- 줌 좌표는 `iw/2-(iw/zoom/2)`, `ih/2-(ih/zoom/2)`처럼 매 프레임 계산된다.
- `scale -> crop -> zoompan -> fps -> trim -> setpts` 순서로 처리된다.
- `render_plan.py`의 `_default_motion()`은 2.5초 초과 구간 대부분에 `slow_zoom_in`을 기본으로 준다.

이 구조는 한 이미지가 긴 시간 유지되는 영상에서 특히 불리하다. `zoompan`은 매 프레임 소수점 확대/중심 좌표를 다시 계산하고, ffmpeg 내부 반올림 때문에 1픽셀 단위 미세 이동이 발생할 수 있다. 시청자는 이것을 부드러운 줌이 아니라 흔들림으로 느낀다.

### 2.2 현재 정지 이미지 처리의 한계

모션이 없는 경우에는 `scale -> pad -> fps -> trim`으로 정지 영상을 만들지만, 현재 기본 렌더 플랜이 긴 이미지 구간에 모션을 자동 부여한다. 즉 사용자가 명시적으로 끄지 않으면 1장 이미지 테스트에서도 흔들릴 가능성이 높다.

### 2.3 자막 출력 문제

`app/services/subtitle.py`는 현재 `_smart_wrap()`으로 긴 문장을 최대 2줄 비슷하게 감싸지만, 타이밍 큐 자체를 분할하지는 않는다.

현재 구조:

- `timings.json`의 문장 단위 타이밍을 그대로 ASS/SRT 이벤트로 사용한다.
- 긴 문장은 줄바꿈만 되고 화면에는 같은 큐가 오래 남는다.
- `min_display_sec` 보정은 있지만 `max_display_sec`, `max_chars_per_cue`, `phrase split` 정책은 없다.

그래서 긴 뉴스 문장은 한 화면에 정보가 너무 많이 올라오고, TTS 리듬과 시각적 읽기 리듬이 맞지 않는다.

### 2.4 렌더 길이 검증의 빈틈

최근 테스트 프로젝트에서 `timings.json`과 렌더 리포트의 오디오 기준 길이는 약 118초였지만, 실제 `output.mp4`는 약 47초로 확인됐다. 현재 `_validate_audio_duration_alignment()`는 raw/normalized 오디오끼리만 비교한다. 최종 영상 길이가 오디오/타이밍과 같은지는 렌더 완료 후 강하게 막지 않는다.

이 문제는 흔들림과 별개지만, 1~2분 테스트 영상 품질 검증에서는 반드시 같이 막아야 한다.

## 3. 설계 원칙

1. 기본값은 안정 우선이다. 1장 이미지 또는 반복 이미지 구간은 줌/팬을 기본으로 쓰지 않는다.
2. 움직임이 필요한 경우에도 `zoompan`을 바로 쓰지 않고, 안정 모션 모드로 분리한다.
3. 프레임 수는 시간에서 대충 자르는 방식이 아니라 `round(duration_sec * FPS)` 기준으로 확정한다.
4. 자막은 TTS 문장을 보존하되 화면 표시 단위만 더 작게 나눈다.
5. 렌더 후 실제 파일을 `ffprobe`로 검사해 실패를 조기에 드러낸다.

## 4. 이미지 안정화 계획

### Phase 1. 렌더 플랜에 안정 정지 모드 추가

대상 파일:

- `app/types.py`
- `app/services/render_plan.py`
- `app/services/render.py`
- `tests/test_render_plan.py`
- `tests/test_render_visual_track.py`

작업:

- `RenderPlanSegment.motion`에 `"still_locked"` 값을 허용한다.
- `_default_motion()` 정책을 변경한다.
  - 동일 이미지가 여러 문장에 반복 매핑된 경우: `still_locked`
  - 한 프로젝트에 사용 가능한 이미지가 1장뿐인 경우: `still_locked`
  - 뉴스/기술/설명형 콘텐츠 기본값: `still_locked`
  - 짧은 인트로 또는 사용자가 명시한 경우에만 안정 모션 허용
- 기존 `"none"`은 모션 없음이라는 의미로 유지하되, 렌더 플랜 기본값은 의도를 드러내기 위해 `"still_locked"`를 사용한다.
- `kenburns_enabled` 글로벌 플래그보다 segment motion을 우선한다.
  - 현재 `_build_visual_track()`의 모션 조건은 `is_image and (kenburns_enabled or segment.motion != "none")`이므로, 프로젝트 설정이 켜져 있으면 segment plan과 무관하게 `zoompan`이 걸릴 수 있다.
  - 수정 후 우선순위는 `still_locked` > explicit segment motion > `kenburns_enabled` fallback 순서로 둔다.
  - `segment.motion == "still_locked"`이면 `kenburns_enabled=True`여도 반드시 정지 프레임 복제 경로를 탄다.
  - `segment.motion in {"slow_zoom_in", "slow_zoom_out", "stable_zoom_in", "stable_zoom_out"}`이면 해당 segment의 명시 모션을 따른다.
  - render plan이 없고 media fallback만 쓰는 legacy 경로에서만 `kenburns_enabled`를 fallback motion으로 해석한다.

완료 기준:

- 1장 이미지 프로젝트의 render_plan segment가 기본적으로 `still_locked`가 된다.
- `kenburns_enabled=True`인 프로젝트라도 `still_locked` segment에는 `zoompan`이 포함되지 않는다.
- 기존 테스트에서 기대하던 무조건 `slow_zoom_in` 정책은 새 정책에 맞게 갱신된다.

### Phase 2. FPS 기준 프레임 복제 필터 추가

대상 파일:

- `app/services/render.py`
- `tests/test_render_visual_track.py`

작업:

- `_stable_still_filter(index, duration_sec, width, height)`를 추가한다.
- 프레임 수 계산 헬퍼를 둔다. 단일 segment에서는 다음 방식을 기본으로 한다.

```python
frame_count = max(1, round(duration_sec * FPS))
segment_duration = frame_count / FPS
```

- 여러 segment를 합칠 때는 전체 target frame을 먼저 고정한다.

```python
total_target_frames = max(1, round(total_duration_sec * FPS))
segment_frames = []
for segment in segments[:-1]:
    segment_frames.append(max(1, round(segment.duration_sec * FPS)))
last_frame_count = max(1, total_target_frames - sum(segment_frames))
segment_frames.append(last_frame_count)
```

- 마지막 segment가 누적 반올림 오차를 흡수한다.
- 마지막 segment 보정 후에도 전체 프레임 수가 `total_target_frames`와 다르면 렌더 전 preflight/report 단계에서 실패시킨다.
- 필터는 정지 이미지를 정확한 CFR 영상으로 만든다.

예상 필터 방향:

```text
scale=WIDTH:HEIGHT:force_original_aspect_ratio=decrease,
pad=WIDTH:HEIGHT:(ow-iw)/2:(oh-ih)/2:black,
fps=FPS,
trim=end_frame=FRAME_COUNT,
setpts=N/(FPS*TB),
setsar=1,
format=yuv420p
```

- 이미지 입력은 `-loop 1 -framerate FPS -i image`만 사용하고, 입력단 `-t`는 쓰지 않는다.
- 길이 절단은 필터그래프 내부의 `trim=end_frame=FRAME_COUNT`로만 수행한다.
- `-loop 1`과 `-t`를 입력단에서 조합하면 ffmpeg 버전에 따라 마지막 프레임이 잘리거나 더미 프레임이 생길 수 있으므로 금지한다.
- `still_locked`에서는 `_zoompan_filter()`를 호출하지 않는다.

완료 기준:

- `still_locked` 구간의 filter graph에 `zoompan`이 포함되지 않는다.
- 같은 이미지 120초 렌더의 시작/중간/끝 프레임을 비교했을 때 원본 영상 레이어의 픽셀 차이가 허용 오차 이내다.
- segment별 `frame_count / FPS` 기준으로 길이가 계산되고, 마지막 segment가 전체 target frame 오차를 흡수한다.
- 전체 visual track frame count가 `round(total_duration_sec * FPS)`와 일치한다.

### Phase 3. 안정 모션은 별도 옵션으로 격리

대상 파일:

- `app/services/render.py`
- `app/services/render_plan.py`

작업:

- `"stable_zoom_in"`, `"stable_zoom_out"`은 V2 옵션으로 분리한다.
- V1에서는 영상 품질 안정화를 위해 autopilot 기본값을 `still_locked`로 둔다.
- 사용자가 명시적으로 Ken Burns/줌 효과를 켠 경우에만 안정 모션을 사용한다.
- 안정 모션을 구현할 때도 소수점 중심 좌표가 매 프레임 흔들리지 않도록 정수 픽셀 좌표 또는 사전 계산된 transform table을 사용한다.

완료 기준:

- 기본 테스트 영상은 흔들림 없는 정지 이미지 복제 방식으로 생성된다.
- 줌 효과는 명시 옵션으로만 활성화된다.

## 5. 자막 분할 계획

### Phase 4. 표시용 subtitle cue splitter 추가

대상 파일:

- `app/services/subtitle.py`
- `app/types.py`
- `tests/test_subtitle_rendering.py`

작업:

- `split_readable_subtitle_cues()`를 추가한다.
- 입력은 기존 `TimingEntry` 목록이고, 출력은 렌더링 전용 cue 목록이다.
- 원본 `timings.json`은 TTS/오디오 기준 데이터로 유지한다.
- ASS/SRT 출력 직전에만 표시용 cue로 분할한다.
- `word_timings`가 없는 경우에만 텍스트 우선 분할을 사용한다.

분할 기준 V1:

- 최대 2줄
- 한 줄 기준 한국어 14~20자 권장, 상한은 스타일의 `max_line_chars`와 화면 폭으로 재계산
- cue 하나의 권장 표시 시간: 1.2~3.5초
- cue 하나의 최대 표시 시간: 4.0초
- 쉼표, 마침표, 물음표, 느낌표, 한국어 접속 표현 기준으로 우선 분할
- 너무 긴 구는 어절 단위로 재분할
- 너무 짧은 cue는 앞뒤 cue와 병합

완료 기준:

- 긴 한국어 문장 1개가 화면에 한 번에 모두 출력되지 않는다.
- 1~2분 뉴스 대본에서 자막 cue 수가 문장 수보다 충분히 늘어난다.
- 각 cue는 최대 2줄, cue당 글자 수와 표시 시간이 정책 안에 들어온다.

### Phase 5. 단어 타이밍 기반 분할 보정

대상 파일:

- `app/services/subtitle.py`
- `app/services/transcribe.py`
- `tests/test_subtitle_rendering.py`

작업:

- `timings_words.json`이 있으면 텍스트를 먼저 자르지 않고 word-first 방식으로 분할한다.
- word-first splitter는 단어를 순서대로 누적하다가 다음 조건 중 하나를 만족하면 cue를 닫는다.
  - 누적 글자 수가 `max_chars_per_cue`에 도달
  - 쉼표, 마침표, 물음표, 느낌표 등 자연스러운 휴지점 도달
  - cue duration이 `max_cue_sec`에 도달
  - 두 줄 표시 한계를 넘기기 직전
- word-first cue의 `start`는 첫 단어의 `start`, `end`는 마지막 단어의 `end`로 둔다.
- karaoke 효과는 분할된 cue가 소유한 word list를 그대로 사용하므로 기존 `cue_idx` 매핑을 억지로 재계산하지 않는다.
- word timing이 없을 때만 Phase 4의 텍스트 분할과 글자 수 비율 기반 시간 배분으로 fallback한다.
- 분할된 sub-cue에는 기존 문장 단위 `_apply_min_display_time()`을 그대로 적용하지 않는다.
  - readable split mode의 `min_display_sec` 기본값은 0.3초로 낮춘다.
  - cue 사이 overlap을 만들지 않는 선에서만 최소 표시 시간을 보정한다.
  - 뒤 cue의 start를 밀어내는 방식은 금지한다.
  - 너무 짧은 cue는 시간을 강제로 늘리기보다 앞뒤 cue와 병합한다.

완료 기준:

- 자막이 TTS 발화보다 지나치게 앞서거나 늦게 사라지지 않는다.
- karaoke 효과를 켜도 분할 cue가 깨지지 않는다.
- readable split mode에서 `min_display_sec` 때문에 cue가 겹치거나 도미노처럼 뒤로 밀리지 않는다.

### Phase 6. 자막 스타일 옵션 확장

대상 파일:

- `app/types.py`
- `app/services/subtitle.py`
- `app/db.py`
- 필요 시 프론트엔드 subtitle settings

추가 후보 필드:

- `cue_split_mode`: `"sentence"` | `"readable"` | `"off"`
- `max_chars_per_cue`
- `max_cue_sec`
- `min_cue_sec`
- `max_lines`

기본값:

- autopilot: `cue_split_mode="readable"`
- manual legacy project: 기존 동작을 최대한 유지하되 신규 프로젝트는 readable 기본

완료 기준:

- 기존 프로젝트가 로드 실패하지 않는다.
- UI/API 저장 시 알 수 없는 값이 들어와도 안전한 기본값으로 정규화된다.

## 6. 렌더 길이와 품질 검증 강화

### Phase 7. 최종 output duration guard 추가

대상 파일:

- `app/services/render.py`
- `app/services/render_report.py`
- `app/types.py`
- `tests/test_render_visual_track.py`
- `tests/test_render_report.py`

작업:

- mux 완료 후 `output.mp4`를 `_probe_duration()`으로 검사한다.
- 비교 기준:
  - `timings[-1]["end"]`
  - normalized audio duration
  - render plan total duration
  - actual output duration
- 허용 오차:
  - 60초 미만: 0.5초
  - 60초 이상: 1.0초 또는 전체 길이의 1%, 더 작은 값
- 허용 오차를 넘으면 렌더를 실패 처리하고 report에 원인 값을 남긴다.
- duration guard 실패 시 불완전한 `output.mp4`는 삭제한다.
  - `out_mp4.exists()`이면 `unlink()`한다.
  - 삭제 실패는 별도 warning으로 report/log에 남기되, 원래 duration guard 실패 원인을 가리지 않는다.
  - 사용자가 실패 상태에서 잘린 영상을 정상 산출물로 착각하지 않게 한다.

완료 기준:

- 118초 오디오인데 47초 영상이 생성되는 상황은 성공 처리되지 않는다.
- duration guard에 실패한 비정상 output 파일이 최종 산출물 경로에 남지 않는다.
- render_report에 `output_duration_sec`, `duration_drift_sec`, `duration_guard_passed`가 기록된다.

### Phase 8. 프레임 타임라인 리포트 추가

대상 파일:

- `app/services/render.py`
- `app/services/render_report.py`

작업:

- 각 visual segment에 다음 값을 기록한다.
  - `duration_sec`
  - `frame_count`
  - `frame_duration_sec`
  - `target_frame_count`
  - `drift_frames`
  - `motion`
  - `source_image`
- 합산 프레임 수와 전체 FPS 기반 길이를 report에 남긴다.
- `drift_frames`는 segment 원래 duration을 반올림한 예상 프레임과 실제 할당 프레임의 차이로 기록한다.
  - 대부분 segment는 0 또는 작은 값이어야 한다.
  - 마지막 segment는 누적 보정 때문에 의도적으로 drift를 흡수할 수 있다.
  - report에서 마지막 segment의 `drift_frames`를 보면 전체 오차가 어디서 정산됐는지 즉시 확인할 수 있다.

완료 기준:

- 영상이 짧거나 길어진 경우 어느 segment에서 드리프트가 생겼는지 추적 가능하다.
- 마지막 segment가 누적 오차를 흡수했는지 report만으로 확인 가능하다.

## 7. 이미지 매칭과 프롬프트 품질 보강

이번 요청의 핵심은 렌더 안정화와 자막이지만, 테스트 영상 품질을 기준으로 보면 다음 보강도 같이 필요하다.

### Phase 9. 기술/뉴스 콘텐츠 기본 이미지 정책 정리

대상 파일:

- `app/services/image_prompting.py`
- `app/services/visual_brief.py`
- `storage/visual_vocab/tech.json`
- `app/services/autopilot.py`

작업:

- 최신 AI 뉴스, 기술, 브라우저, API, 모델, 칩, 데이터센터 같은 한국어 키워드를 tech vocab에 추가한다.
- 기술/뉴스 콘텐츠는 Stickfigures LoRA 기본 사용을 끄고, 일반 체크포인트 또는 diagram-friendly 설정으로 분기한다.
- 이미지가 부족한 경우 기존 이미지를 문맥상 가까운 문장에 반복 배치하되, 반복 배치 segment는 `still_locked`로 처리한다.

완료 기준:

- “최신 AI 뉴스” 계열 대본에서 `running fast`, `heavy rain` 같은 일반 fallback 프롬프트가 나오지 않는다.
- 같은 이미지 반복 사용 시 흔들림 없이 유지된다.

### Phase 10. 프리플라이트 품질 게이트 강화

대상 파일:

- `app/services/preflight.py`
- `tests/test_feature_workflow.py`

추가 체크:

- 이미지 매핑이 없는 문장 수
- `still_locked` 대상인데 `zoompan` 필터가 예정된 segment 수
- subtitle readable split 예상 cue 수
- render_plan total duration과 TTS timing duration 차이
- voice/TTS manifest 일관성은 기존 체크와 연결

완료 기준:

- 렌더 버튼을 누르기 전에 “영상은 만들어지지만 품질이 낮을 가능성”을 구조적으로 잡는다.

## 8. 권장 구현 순서

1. `still_locked` motion 타입과 렌더 플랜 기본 정책 변경
2. `still_locked`가 `kenburns_enabled`보다 우선하도록 모션 평가 로직 변경
3. `_stable_still_filter()`와 FPS 기반 frame count helper 추가
4. 마지막 segment가 누적 frame drift를 흡수하는 timeline allocator 추가
5. 정지 이미지 1장/반복 이미지 렌더 테스트 추가
6. word-first `split_readable_subtitle_cues()` 추가
7. word timing이 없는 경우의 text fallback splitter 추가
8. ASS/SRT writer가 표시용 cue를 사용하도록 연결
9. 최종 output duration guard와 실패 output cleanup 추가
10. render_report에 프레임/길이/자막 품질 정보를 기록
11. autopilot 기본값을 안정 모드와 readable subtitle로 연결
12. 최신 AI 뉴스 샘플로 60~120초 회귀 테스트 생성

## 9. 자동 테스트 계획

### Unit tests

- `test_still_locked_filter_does_not_use_zoompan`
- `test_still_locked_overrides_global_kenburns_enabled`
- `test_still_locked_filter_uses_frame_count_duration`
- `test_last_segment_absorbs_frame_rounding_drift`
- `test_render_plan_defaults_single_image_to_still_locked`
- `test_subtitle_word_first_splitter_splits_long_korean_sentence`
- `test_subtitle_splitter_falls_back_without_word_timings`
- `test_subtitle_splitter_preserves_total_timing`
- `test_readable_subtitle_min_display_does_not_overlap`
- `test_output_duration_guard_rejects_large_drift`
- `test_output_duration_guard_removes_failed_output_file`

### Integration tests

- 이미지 1장, 120초 타이밍, `still_locked` 렌더 명령 생성 검증
- 이미지 1장, 10개 문장, readable subtitle cue 수 증가 검증
- render_report에 `output_duration_sec`와 `duration_guard_passed` 기록 검증

### Manual E2E

키워드: `최신 ai 뉴스`

검증 항목:

- BraveSearch 자료 수집 성공
- Gemma 계열 대본 생성 성공
- OmniVoice 음성 일관성 유지
- ComfyUI 이미지 생성 또는 반복 매핑 성공
- 60~120초 최종 영상 생성
- 정지 이미지 구간 흔들림 없음
- 자막이 한 번에 과도하게 뜨지 않음
- 실제 output duration이 TTS duration과 1초 이내 일치

## 10. 수용 기준

이 계획의 구현은 아래 조건을 모두 만족해야 완료로 본다.

1. 1장 이미지로 60~120초 영상을 만들어도 정지 구간이 흔들리지 않는다.
2. `still_locked` segment는 `kenburns_enabled=True`여도 `zoompan`을 사용하지 않는다.
3. 기본 autopilot 렌더에서 `zoompan`은 사용자가 모션을 켠 경우에만 사용된다.
4. 전체 visual frame count는 target frame count와 일치하고, 마지막 segment가 반올림 오차를 흡수한다.
5. 자막은 긴 문장을 화면에 한 번에 띄우지 않고 읽기 좋은 cue로 나뉜다.
6. word timing이 있으면 word-first splitter를 사용해 karaoke 매핑이 깨지지 않는다.
7. readable split mode에서 `min_display_sec` 보정 때문에 cue overlap이 생기지 않는다.
8. 최종 영상 길이와 TTS/타이밍 길이 차이가 허용 오차를 넘으면 성공 처리하지 않는다.
9. duration guard 실패 시 비정상 output 파일이 산출물 경로에 남지 않는다.
10. render_report만 봐도 영상 길이, 프레임 수, `drift_frames`, subtitle cue 수, fallback 사용 여부를 진단할 수 있다.
11. 신규 테스트가 통과하고, 기존 render/subtitle 테스트도 갱신된 정책에 맞게 통과한다.

## 11. 구현 시 주의사항

- 기존 `zoompan` 코드를 삭제하지 말고 명시 모션 옵션으로 격리한다.
- `timings.json`은 TTS 원본 기준으로 유지하고, 표시용 cue는 렌더 단계에서 파생한다.
- frame count를 `int(duration * FPS)`로 버림 처리하지 않는다. `round()`와 누적 보정으로 전체 길이를 맞춘다.
- 최종 segment는 누적 오차를 흡수하도록 조정한다.
- 입력단 `-loop 1`에는 `-t`를 붙이지 않고, 필터그래프 `trim=end_frame=...`에서만 프레임 수를 확정한다.
- word timing이 있으면 텍스트 분할보다 word-first 분할을 우선한다.
- readable split mode에서는 기존 문장 단위 `min_display_sec` 정책을 그대로 적용하지 않는다.
- duration guard 실패 시 불완전한 output 파일을 정리한다.
- 문서 작업만으로는 `timeline.md`, `research.md`를 수정하지 않는다.
- 실제 구현 단계에서는 타입 체크와 관련 테스트를 반드시 실행한다.

## 12. 구현 상태 업데이트

완료:

- Phase 1 ~ Phase 2: `still_locked` motion, global `kenburns_enabled` override, CFR still-frame 복제, 마지막 segment frame drift 흡수 로직 구현
- Phase 4 ~ Phase 5: readable subtitle split, word-first cue 분할, text fallback, readable split overlap 방지 구현
- Phase 7 ~ Phase 8: final output duration guard, failed output cleanup, render report frame/duration metadata 구현
- autopilot 경로에서 legacy `sentence` cue mode를 `readable`로 승격하는 기본 동작 구현

미구현 또는 후속 보강:

- Phase 3: `stable_zoom_in` / `stable_zoom_out`를 사용자 선택형 연출 옵션으로 노출하는 작업
- Phase 9: 기술/뉴스 전용 이미지 정책 추가 미세조정
