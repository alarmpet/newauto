# Render Visual Track Root Cause Plan

상태: `[완료]`

## 문제 요약

- 렌더가 `가로형 영상 구성` 단계에서 `ffmpeg failed with no stderr output` 으로 멈추고 있었다.
- 실제 원인은 두 겹이었다.
  - Windows 기본 `cp949` 디코딩 때문에 FFmpeg stderr 자체가 깨져 진짜 에러가 안 보였다.
  - `Ken Burns On` 상태에서 이미지 분기 `zoompan` 출력 크기와 비디오 분기 출력 크기가 달라 `concat` 이 실패했다.

## 실제 확인된 원인

### Phase 1. cp949 stderr 디코딩 문제 `[완료]`

- `_run()` 과 ffprobe 호출을 바이트 기반 수집으로 바꾸고 UTF-8 `errors="replace"` 로 디코딩했다.
- 한글 파일명이 포함된 미디어에서도 `UnicodeDecodeError` 없이 실제 FFmpeg stderr 가 남도록 수정했다.

완료 기준:

- 한글 파일명 입력에서도 실제 FFmpeg 에러가 `render_last_log` 에 남는다.

### Phase 2. zoompan 출력 크기 불일치 `[완료]`

- `_zoompan_filter()` 에 `s={width}x{height}` 를 명시해서 FFmpeg default `1280x720` 로 떨어지지 않게 수정했다.
- zoom 용 원본 여유를 위해 입력 쪽 scale/crop 을 `2x` 캔버스로 넓힌 뒤 최종 출력만 목표 해상도로 고정했다.
- 결과적으로 mixed media 환경에서도 모든 `[vN]` 스트림이 같은 해상도로 concat 되게 맞췄다.

완료 기준:

- `mp4 + png/jpeg` 혼합 프로젝트에서 `Ken Burns On` 이어도 `build_visual_landscape` 가 깨지지 않는다.
- 이미지 전용 프로젝트도 조용히 720p 로 떨어지지 않는다.

### Phase 4. 회귀 테스트 추가 `[완료]`

- `tests/test_render_visual_track.py` 추가
- 검증 항목:
  - `zoompan` 이 landscape/shorts 모두 명시적 `s=` 를 포함하는지
  - mixed media + Ken Burns 시 필터가 공통 landscape 크기를 유지하는지
  - UTF-8 한글 stderr 가 `_run()` 예외 메시지에 보존되는지
  - pre-flight 가 invalid media metadata 를 보고하는지

완료 기준:

- 이번 원인이 다시 들어오면 테스트에서 즉시 실패한다.

### Phase 3. pre-flight 미디어 검사 `[완료]`

- `find_invalid_media_files()` 와 `probe_media_dimensions()` 를 추가했다.
- pre-flight 에 `media_metadata` 체크를 넣어 ffprobe 로 영상 크기를 읽지 못하는 미디어를 미리 경고한다.
- 렌더 시작 시에도 같은 검사를 먼저 수행해서 concat 단계까지 늦게 실패하지 않도록 했다.

완료 기준:

- 손상되었거나 영상 스트림 메타데이터를 읽지 못하는 미디어는 더 이른 단계에서 드러난다.

### Phase 5. UX 개선 `[완료]`

- Step 4에서 `validate_media` phase 라벨을 추가했다.
- 렌더 로그 표시에 요약 문구를 넣어 `Parsed_concat`, `Invalid data found`, `No such file or directory` 같은 FFmpeg 에러를 바로 읽기 쉽게 바꿨다.
- 백엔드는 traceback 전체 대신 사용자에게 필요한 핵심 원인과 FFmpeg tail 위주로 `render_last_log` 를 저장하게 정리했다.

완료 기준:

- 사용자가 `stderr 없음` 같은 모호한 메시지 대신 실제 실패 이유를 읽을 수 있다.

## 구현 순서

1. Phase 1 `cp949` 디코딩 안정화
2. Phase 2 `zoompan` 출력 크기 고정
3. Phase 4 회귀 테스트 추가
4. Phase 3 pre-flight 미디어 검사
5. Phase 5 Step 4 UX 개선

## 검증

- `scripts/typecheck.ps1`
- `node --check app/static/app.js`
- `omnivoice_env\Scripts\python.exe -m unittest discover -s tests -v`

## 기대 효과

- 한글 파일명이 있어도 실제 FFmpeg 오류가 숨지지 않는다.
- `Ken Burns On + mixed media` 조합이 안정적으로 렌더된다.
- 손상된 미디어는 pre-flight 와 초기 렌더 단계에서 더 빨리 드러난다.
- Step 4 에서 실패 이유를 바로 읽을 수 있다.
