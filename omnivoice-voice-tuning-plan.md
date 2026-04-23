# OmniVoice Voice Tuning Plan

## 목적

현재 프로젝트의 TTS에서 프리셋을 바꿔도 목소리 차이가 약하게 들리는 문제를 줄이고, OmniVoice의 `language`와 generation 설정을 실제 워크플로우에 연결한다.

상태: `[진행 중]`

## 진단 요약

1. 기존 구조는 `voice_preset` 문자열만 저장하고, 실제 `generate()` 호출에는 약한 프롬프트 차이만 전달하고 있었다.
2. 한국어 스크립트에서도 `language`를 명시하지 않아 언어 조건이 모델 자동 판단에만 의존했다.
3. 기존 프리셋은 서로 비슷한 남성 저음 계열에 몰려 있어 체감 차이가 작았다.
4. 한국어에서는 영어 accent 계열 문구가 실효성이 약해 보였고, 실제로 프리셋 간 간격도 좁았다.

## 구현 상태

### Phase 1. TTS 조건 전달 구조 확장 `[완료]`

완료 내용:

1. 프로젝트 DB에 `tts_profile` JSON 컬럼 추가
2. `ProjectRecord`에 `tts_profile` 타입 추가
3. `voice_preset`는 shortcut으로 유지하고, 내부적으로는 `tts_profile`을 정규화해서 사용
4. TTS 실행 API가 `voice_preset + tts_profile` JSON payload를 받도록 변경
5. `app/services/tts.py`에서 실제 `language`와 `OmniVoiceGenerationConfig`를 `generate()`에 전달하도록 연결

검증 포인트:

- 저장된 `tts_profile`이 프로젝트 조회 응답에 그대로 포함된다
- `run_tts_job()`가 `language`, `speed`, `num_step`, `guidance_scale`를 반영한다

### Phase 2. 한국어 중심 voice design 프리셋 재설계 `[완료]`

완료 내용:

1. 한국어 중심 신규 프리셋 세트 추가
   - `male-deep-calm`
   - `male-mid-clear`
   - `female-bright-clear`
   - `female-low-calm`
   - `elder-narration`
   - `whisper-story`
   - `english-bright`
2. 기존 레거시 프리셋 ID는 새 프리셋으로 alias 매핑해서 하위 호환 유지
3. `korean accent` 기반 문구 대신 한국어 TTS에서 더 벌어진 스타일 설명으로 교체
4. Step 3 UI에 mode, language, speed, duration, num_step, guidance_scale, denoise, postprocess, instruct 입력 추가
5. 새 샘플 생성 스크립트 기본 프리셋도 새 세트로 교체

검증 포인트:

- 새 프리셋 옵션이 UI에 노출된다
- 새 프리셋 메타데이터와 샘플 스크립트 테스트가 통과한다

### Phase 3. Voice Cloning 워크플로우 추가 `[대기]`

예정 작업:

1. reference audio 업로드 경로 설계
2. `ref_audio` / `ref_text` 기반 clone 모드 추가
3. TTS step에 `Auto / Design / Clone` 완전 분리 UI 추가

### Phase 4. 고급 generation tuning 확장 `[대기]`

예정 작업:

1. preset 기반 tuning 묶음 제공
2. `duration`, `num_step`, `guidance_scale` 실험용 A/B 비교 강화
3. 품질 우선 / 속도 우선 preset 추가

### Phase 5. A/B 샘플 비교 도구 `[대기]`

예정 작업:

1. 여러 프리셋 동시 샘플 생성
2. 샘플 비교용 카드 UI
3. 선택한 샘플을 프로젝트 기본값으로 반영하는 버튼

### Phase 6. 자동 추천 로직 `[대기]`

예정 작업:

1. 스크립트 언어 감지 기반 기본값 추천
2. 한국어는 `ko`, 영어는 `en` 기본 추천
3. 브랜딩 목적이면 clone 모드 우선 추천

## 이번 구현으로 바뀐 점

1. 한국어 프로젝트는 이제 OmniVoice에 언어 힌트를 명시적으로 넘긴다.
2. 프리셋 선택이 단순 라벨 교체가 아니라 실제 generation 설정 차이로 연결된다.
3. 프로젝트마다 TTS 튜닝값이 저장되어 재실행 시 그대로 재현된다.
4. 기존 프로젝트의 옛 프리셋 값도 새 canonical preset으로 자동 정규화된다.

## 검증

완료:

1. `scripts/typecheck.ps1`
2. `node --check app/static/app.js`
3. `omnivoice_env\\Scripts\\python.exe -m unittest discover -s tests -v`

## 다음 우선순위

1. Phase 3 clone 모드
2. Phase 5 A/B 비교 도구
3. Phase 4 품질 preset 확장

## 참고 소스

- OmniVoice 공식 README: https://github.com/k2-fsa/OmniVoice/blob/master/README.md
- OmniVoice voice design 문서: https://raw.githubusercontent.com/k2-fsa/OmniVoice/master/docs/voice-design.md
- OmniVoice generation parameters 문서: https://raw.githubusercontent.com/k2-fsa/OmniVoice/master/docs/generation-parameters.md
- OmniVoice tips 문서: https://raw.githubusercontent.com/k2-fsa/OmniVoice/master/docs/tips.md
