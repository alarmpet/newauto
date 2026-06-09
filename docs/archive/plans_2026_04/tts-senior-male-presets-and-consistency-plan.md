# TTS Senior Male Presets And Consistency Plan

상태: `[완료]`

## 목표

- Step 3에 60대 남성 프리셋 4종을 추가한다.
  - `60대 남성 저음`
  - `60대 남성 목사`
  - `60대 남성 낭독`
  - `60대 남성 아나운서`
- 기존 `샘플 듣기` 경로로 즉시 비교 청취가 가능해야 한다.
- preview와 full TTS가 실제로 같은 보이스 설정으로 생성되었는지 검증 가능한 구조를 만든다.
- 사용자가 체감한 음성 일관성 부족 문제를 앱 전달 문제와 모델 특성으로 분리해서 확인할 수 있게 만든다.

## 반영한 핵심 수정

### 1. `seed`를 preview/full TTS 일관성의 최우선 요소로 반영 `[완료]`

- `TtsProfile`에 `seed`를 추가했다.
- preview 생성 시 seed가 없으면 서버가 새 seed를 만들고, 응답에 그대로 반환한다.
- full TTS 시작 시 preview lock이 오면 같은 seed를 재사용한다.
- OmniVoice 호출 직전에 `fix_random_seed()`로 `random`, `numpy`, `torch` RNG를 함께 고정한다.

### 2. 문장별 effective profile manifest 구조 추가 `[완료]`

- 프로젝트 전체 단일 profile만 저장하는 대신, 문장별 실제 주입값을 `tts_run_manifest.json`에 남기도록 변경했다.
- 각 항목에는 아래가 포함된다.
  - `idx`
  - `text`
  - `voice_preset`
  - `effective_profile`
  - `kwargs`
  - `seed`
- 현재는 문장별 seed를 `base_seed + idx`로 기록해 추적 가능하게 만들었다.
- 이후 Bible 구간처럼 region별 `speed`가 달라져도 같은 구조로 확장 가능하다.

### 3. preview artifact를 서버 파일 대신 lock 응답 기반으로 정리 `[완료]`

- preview API는 이제 아래를 응답한다.
  - `voice_preset`
  - `tts_profile`
  - `preview_lock`
- 브라우저는 마지막 preview lock을 메모리에 보관하고, `TTS 시작` 때 다시 서버로 전달한다.
- 서버는 full TTS 시작 시 현재 form 값과 preview lock의 canonical preset/profile/signature를 검증한다.
- preview 이후 tuning을 바꾸면 `generate a new sample first`로 막아 일관성 깨짐을 조기에 드러낸다.

### 4. 60대 프리셋 4종 추가와 A/B 준비 `[완료]`

- `male-60s-low`
- `male-pastor-60s`
- `male-narration-60s`
- `male-announcer-60s`

초기 설계는 아래처럼 넣었다.

- `male-60s-low`
  - `instruct="male, elderly, low pitch"`
  - `speed=0.90`
- `male-pastor-60s`
  - `instruct="male, elderly, low pitch"`
  - `speed=0.87`
- `male-narration-60s`
  - `instruct="male, elderly, moderate pitch"`
  - `speed=0.92`
- `male-announcer-60s`
  - `instruct="male, elderly, moderate pitch"`
  - `speed=0.96`

추가로 샘플 생성 스크립트도 preview와 같은 경로를 타도록 바꿔서, preset 비교 샘플에 실제 effective profile이 반영되게 했다.

## 코드 반영 범위

- [app/types.py](/C:/Users/petbl/newauto/app/types.py)
- [app/tts_profiles.py](/C:/Users/petbl/newauto/app/tts_profiles.py)
- [app/services/tts.py](/C:/Users/petbl/newauto/app/services/tts.py)
- [app/routers/render.py](/C:/Users/petbl/newauto/app/routers/render.py)
- [app/static/app.js](/C:/Users/petbl/newauto/app/static/app.js)
- [scripts/generate_voice_samples.py](/C:/Users/petbl/newauto/scripts/generate_voice_samples.py)
- [tests/test_tts_presets.py](/C:/Users/petbl/newauto/tests/test_tts_presets.py)
- [tests/test_tts_pipeline.py](/C:/Users/petbl/newauto/tests/test_tts_pipeline.py)

## 검증

- `scripts/typecheck.ps1` 통과
- `node --check app/static/app.js` 통과
- `omnivoice_env\Scripts\python.exe -m unittest discover -s tests -v` 통과

## 후속 메모

- 이번 작업으로 “preview와 full TTS가 다른 설정으로 생성되는 앱 측 문제”는 추적 가능하게 정리했다.
- 그래도 한국어 OmniVoice design mode 자체의 음색 차이가 약하게 들리면, 그때는 clone mode 또는 reference voice 전략으로 넘어가는 게 맞다.
