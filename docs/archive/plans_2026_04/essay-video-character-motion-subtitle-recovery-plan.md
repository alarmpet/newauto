# Essay Test Video Quality Recovery Plan

작성일: 2026-04-28
대상 프로젝트: `147ab80b75e9`
대상 영상: `storage/projects/147ab80b75e9/output.mp4`

## 1. 현재 진단

이번 테스트 영상은 렌더 안정성은 확보했지만, 최종 시청 품질 기준에서는 실패로 봐야 한다.

확인된 현재 상태:

- 영상 길이: `94.133333s`
- 렌더 결과: `duration_guard_passed=true`
- 렌더 모션: 전 구간 `still_locked`
- 자막 스타일: `font_size=48`, `max_line_chars=16`, `max_cue_sec=2.2`
- 음성: `male-announcer-40s-50s`, `seed=424242`, `seed_mode=fixed`
- 이미지: 14장 생성, 문장별 1장 매핑

즉 문제는 TTS seed나 duration guard가 아니라, 이미지 기획/생성 정책과 화면 연출 정책에 있다.

## 2. 스크린샷별 문제

### 2.1 침대 위 휴대폰 이미지

문제:

- 주인공이 보이지 않고 손만 나온다.
- 침대 장면이 대본의 핵심인 “방향을 잃은 하루의 시작”보다 “누워서 휴대폰 하는 장면”으로 좁게 해석된다.
- 화면 안 휴대폰에 이상한 물체가 보여 시선이 엉뚱한 곳으로 간다.

직접 원인:

- 프롬프트가 `close view of a hand scrolling a smartphone beside an unmade bed`로 되어 있어 모델에게 손/휴대폰 클로즈업을 지시했다.
- `same reflective male protagonist`가 manifest의 `visual_brief.main_subject`에는 있지만 실제 positive prompt에는 강하게 들어가지 않았다.
- negative prompt에 `hands only`, `missing face`, `disembodied hands`, `phone screen object` 같은 금지어가 없다.

### 2.2 책상에서 필기하는 남자 이미지

문제:

- 이미지 자체는 비교적 자연스럽지만 다른 장면과 동일 인물로 보이지 않는다.
- 의상, 나이, 헤어, 얼굴형이 앞뒤 장면과 연결되지 않는다.
- 자막이 화면 하단에 작고 얇게 붙어 있어 영상 톤 대비 정보 전달력이 약하다.

직접 원인:

- 캐릭터 identity를 모델에 고정할 방법이 없다.
- “Korean man in his forties”, “same man” 같은 자연어만으로는 장면 간 얼굴/복장/체형 유지가 어렵다.
- 자막 기본값 `48px`는 1080p에서는 무난하지만, 실제 영상 캡처/플레이어 크기에서는 작아 보인다.

### 2.3 비슷한 남자 두 명 이미지

문제:

- 비슷한 생김새와 비슷한 옷의 두 인물이 나온다.
- 대본은 한 사람의 내면 에세이인데, 화면은 두 사람이 대화하거나 비교되는 장면처럼 보인다.
- “같은 인물” 지시가 오히려 비슷한 두 사람을 만들었다.

직접 원인:

- positive prompt 또는 briefing에 `same reflective male protagonist`가 있지만 `single person only`가 강하지 않다.
- negative prompt에 `two men`, `duplicate person`, `twin`, `clone`, `second person`, `multiple people`을 일관되게 넣지 않았다.
- “same man”은 이미지 생성 모델에서 identity lock이 아니라 중복 인물 힌트로 작동할 수 있다.

## 3. 근본 원인

### 3.1 캐릭터 일관성 장치 부재

현재는 “같은 남자”를 텍스트 프롬프트로만 요청한다. 이 방식은 테스트 영상에서는 실패 확률이 높다.

필요한 정책:

- 주인공 캐릭터 시트를 먼저 생성한다.
- 이후 모든 장면은 그 캐릭터 이미지를 참조한다.
- ComfyUI에서는 IPAdapter, FaceID, reference image, ControlNet 중 현재 설치 상태에 맞는 방식으로 캐릭터 고정을 적용한다.
- 참조 기능이 준비되지 않은 경우에도 최소한 고정 캐릭터 서술을 모든 prompt 앞부분에 강제 삽입한다.

### 3.2 장면 프롬프트가 핵심 키워드보다 표면 행동에 치우침

“휴대폰을 넘긴다” 같은 표면 행동만 잡으면 침대에서 손만 나오는 장면이 된다. 에세이 영상은 표면 행동보다 감정/핵심 은유가 중요하다.

필요한 정책:

- 문장별로 `core_meaning`, `visual_metaphor`, `must_show`, `must_not_show`를 분리한다.
- positive prompt는 장면 전체 구도부터 작성한다.
- 클로즈업은 기본 금지하고, 필요한 경우에만 허용한다.

### 3.3 Still locked만으로는 영상 연출이 죽음

흔들림을 없애기 위해 전 구간 `still_locked`로 바꾼 것은 안정성 측면에서는 맞았지만, 영상 체감은 정지화면 슬라이드가 되었다.

필요한 정책:

- 기본값은 `still_locked`가 아니라 `stable_motion`이어야 한다.
- `stable_motion`은 기존 `zoompan`처럼 subpixel jitter가 생기면 안 된다.
- 이미지 입력은 FPS 기준으로 안정화하되, 움직임은 integer crop/pan 또는 scale+crop 방식으로 부드럽게 줘야 한다.

### 3.4 자막 크기와 위치가 테스트 영상용으로 약함

현재 `font_size=48`은 데스크톱 전체화면 기준으로는 볼 수 있지만, 리뷰 캡처와 일반 플레이어에서는 작다.

필요한 정책:

- landscape 테스트 영상 기본 자막은 `font_size=64~72`로 올린다.
- outline은 `3~4`, shadow는 `2`, 하단 margin은 `90~120`으로 조정한다.
- 한 cue는 1~2줄, 줄당 12~16자 정도로 유지한다.

## 4. 해결 계획

## Phase 1. Essay visual spec 도입

신규 파일:

- `storage/visual_vocab/essay.json`
- 또는 서비스 코드 내 `essay` visual strategy

장면 생성 전, 각 문장을 아래 구조로 변환한다.

```json
{
  "sentence_idx": 1,
  "core_meaning": "하루가 휴대폰과 할 일 목록에 끌려 시작됨",
  "visual_metaphor": "침대 끝에 앉아 휴대폰을 내려놓고 멍하니 창밖을 보는 한 사람",
  "must_show": ["single protagonist", "visible face", "smartphone", "morning room"],
  "must_not_show": ["hands only", "second person", "phone screen closeup", "strange object on screen"]
}
```

Acceptance:

- 모든 essay scene에 `core_meaning`과 `must_not_show`가 존재한다.
- `hands only`, `two men`, `duplicate person` 같은 금지어가 prompt에 자동 반영된다.

## Phase 2. 캐릭터 시트 먼저 생성

테스트 영상 시작 전에 주인공 reference 이미지를 1장 만든다.

권장 캐릭터:

- Korean man, early 40s
- short black hair, clean-shaven
- warm gray cardigan over white shirt
- calm reflective expression
- average build
- no tie, no suit, no duplicate person

산출물:

- `storage/projects/{pid}/character/hero_reference.png`
- `storage/projects/{pid}/character/hero_reference.json`

Acceptance:

- reference 이미지에 인물이 1명만 있다.
- 얼굴, 상반신, 의상이 명확하다.
- 이후 scene prompt에 hero description이 자동 prepend 된다.

## Phase 3. ComfyUI reference workflow 분기

가능하면 우선순위대로 적용한다.

1. IPAdapter FaceID 또는 IPAdapter reference image
2. ControlNet reference-only 또는 canny/depth 보조
3. 설치 상태가 부족하면 prompt-only identity lock

필요 작업:

- 모델 레지스트리에 IPAdapter/ControlNet 설치 여부 표시
- `image_worker` batch item에 `reference_image_path` 옵션 추가
- workflow template에 reference 입력 placeholder 추가

Acceptance:

- `body_image_options.batch_items[*].reference_image_path`가 저장된다.
- reference workflow가 없으면 명확히 fallback 로그를 남긴다.
- fallback 상태에서도 prompt에 고정 캐릭터 서술과 duplicate-person negative가 들어간다.

## Phase 4. 프롬프트 정책 수정

Essay 영상용 positive prompt 기본 골격:

```text
cinematic editorial still, single Korean man in his early forties, short black hair,
clean-shaven, warm gray cardigan over white shirt, visible face, one person only,
[scene-specific action], [core metaphor], cohesive dawn-to-sunrise palette,
medium shot, natural lens, realistic proportions, no text, widescreen
```

Essay 영상용 negative prompt 기본 골격:

```text
two people, twin, clone, duplicate person, second person, crowd,
hands only, missing face, face cropped out, phone screen closeup,
deformed hands, extra fingers, text, logo, watermark, blurry, cartoon
```

장면별 보정:

- 휴대폰 장면: 침대 클로즈업 금지, 주인공 얼굴 포함
- 책상 장면: 의상 고정, 나이 고정, 책/노트는 보조 요소
- 방향/길 장면: 한 사람만, 길/창/노트/걸음 같은 은유 우선

Acceptance:

- 생성 manifest의 모든 positive prompt에 `single`, `visible face`, 고정 의상 설명이 포함된다.
- 모든 negative prompt에 `two people`, `duplicate person`, `hands only`, `missing face`가 포함된다.

## Phase 5. Stable motion 도입

현재:

- `still_locked`: 흔들림 없음, 그러나 정지화면 느낌
- `slow_zoom_in`: 움직임 있음, 그러나 jitter 가능

추가할 motion:

- `stable_zoom_in`
- `stable_zoom_out`
- `stable_pan_left`
- `stable_pan_right`

렌더 정책:

- 이미지 입력은 기존처럼 FPS 기준으로 안정화한다.
- 모션은 `zoompan` 대신 고해상도 scale 후 integer crop 이동으로 처리한다.
- 이동량은 전체 duration 동안 2~4% 이내로 제한한다.
- 마지막 프레임 수 보정은 기존 frame planner를 유지한다.

Acceptance:

- render report에 `motion=stable_zoom_in` 또는 `stable_pan_*`가 기록된다.
- 같은 이미지 구간에서 subpixel 흔들림 없이 부드러운 이동이 있다.
- duration guard가 통과한다.

## Phase 6. 자막 기본값 강화

Essay 테스트 영상 기본 자막:

```json
{
  "font_size": 68,
  "outline_width": 4,
  "shadow": 2,
  "position": "bottom",
  "margin_v": 100,
  "max_line_chars": 14,
  "max_lines": 2,
  "max_cue_sec": 2.0,
  "min_display_sec": 0.35,
  "cue_split_mode": "readable"
}
```

Acceptance:

- 1024px 캡처에서도 자막이 한눈에 읽힌다.
- 한 cue가 화면을 과도하게 덮지 않는다.
- `subtitle_cue_count`는 실제 display cue 수와 일치한다.

## Phase 7. 이미지 QA 게이트

V1은 vision model 없이 text/metadata 기반으로 처리한다.

자동 실패 조건:

- prompt positive에 `single`이 없는데 essay/person scene인 경우
- negative에 `duplicate person` 또는 `two people`이 없는 경우
- scene prompt에 `close view of a hand` 또는 `hands only` 계열이 있는 경우
- render report에 motion이 전부 `still_locked`인데 사용자가 motion을 요구한 경우

V2는 vision LLM으로 확장한다.

검출 목표:

- 사람 수
- 얼굴 보임 여부
- 손만 나온 이미지 여부
- 주인공 의상/헤어 유사도
- 자막 가독성

## Phase 8. 재생성 절차

1. 기존 project `147ab80b75e9`는 보존한다.
2. 새 프로젝트를 만든다.
3. 동일 대본을 사용한다.
4. 캐릭터 reference 1장을 먼저 생성한다.
5. reference 기반으로 14장 scene 이미지를 생성한다.
6. 자막 스타일을 크게 조정한다.
7. `stable_motion`을 적용해 렌더한다.
8. 최소 3개 프레임을 캡처해 QA한다.

최종 acceptance:

- 영상 길이 60~120초
- TTS seed 전 문장 동일
- 한 명의 주인공만 등장
- 얼굴이 보이지 않는 손-only 장면 없음
- 의상/나이/헤어가 장면 간 크게 바뀌지 않음
- 자막이 현재보다 명확히 큼
- 이미지에 안정적인 움직임이 있음
- duration guard 통과

## 5. 우선순위

가장 먼저 해야 할 일:

1. Essay prompt compiler에 protagonist identity + negative guard 추가
2. 자막 기본값을 테스트 영상 기준으로 키우기
3. `stable_motion`을 still image 기본 motion으로 추가
4. reference image workflow는 설치 상태 확인 후 적용

이번 실패의 핵심은 “모델이 못해서”가 아니라, 우리가 모델에게 너무 느슨하게 맡긴 것이다. 주인공, 금지 조건, 장면 구도, 모션 정책을 시스템이 강제해야 테스트 영상 품질이 안정된다.
