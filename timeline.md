# Timeline

- `[2026-04-23-11-39] agent 작업 지침 문서 추가`
- `[2026-04-23-11-56] 썸네일 기능 업데이트: 별도 업로드/조회/삭제 API, Media 단계 UI, YouTube thumbnails.set 연동 추가`
- `[2026-04-23-11-56] 자막 기능 업데이트: 프로젝트별 자막 스타일 UI/API, ASS 자막 생성, 렌더링 반영 추가`
- `[2026-04-23-17-00] 자막 표시 개선 계획서 업데이트: 자동 2줄 분할, 5단계 위치, margin_h, min_display_sec, 프리셋, 테스트 구현 순서 보강`
- `[2026-04-23-17-33] 자막 표시 개선 구현: 자동 2줄 분할, 최소 표시 시간, 5단계 위치, margin_h, 프리셋 UI, ASS/SRT 반영`
- `[2026-04-23-18-20] 기능 추천 P0~P2 구현: preflight, loudnorm, Ken Burns, BGM+ducking, clone, shorts, YouTube 예약/통계, karaoke, stock search`
- `[2026-04-23-20-05] OmniVoice 튜닝 P0 구현: tts_profile 저장, language/generation_config 전달, 한국어 중심 신규 프리셋/UI 재설계`
- `[2026-04-23-22-27] 렌더/자막 수정: render_phase 로그, 26자 기본 자막 정책, width-aware 줄바꿈, lower 위치 보정, UTF-8 UI 정리, 인코딩 검사 추가`
- `[2026-04-23-22-38] TTS 샘플 미리듣기 추가: Step 3 샘플 생성 API, 오디오 플레이어, 프로젝트별 tts_preview.wav, 기본 샘플 문구 정리`
- `[2026-04-23-22-45] TTS 샘플 오류 수정: OmniVoice 지원 토큰으로 instruct 교체, 미리듣기 500을 400/정상 응답으로 보정`
- `[2026-04-24-00-29] TTS 성별 불일치 수정: /api/tts/presets 단일 소스 추가, legacy male preset 정규화, Step 3 dirty-state/실효 프로필 표시, 샘플 재생성 스크립트 기준 통일`
- `[2026-04-24-01-26] TTS 남성 프리셋 추가: 40~50대 남성 중저음, 40~50대 남성 아나운서, 40~50대 남성 목사 스타일과 샘플 미리듣기 경로 연동`
- `[2026-04-24-01-59] 렌더 stderr None 오류 수정: _tail_lines/_run null-safe 처리, FFmpeg stderr 없음 회귀 테스트 추가`
- `[2026-04-24-02-11] Step 4 도움말 UI 추가: Render Readiness, 렌더 옵션, 자막 스타일 항목별 인라인 설명 툴팁 적용`
- `[2026-04-24-02-33] 렌더 visual track 안정화: UTF-8 stderr 디코딩, zoompan 출력 해상도 고정, media_metadata pre-flight, FFmpeg 오류 요약 UI, 회귀 테스트 추가`
- `[2026-04-24-03-35] 렌더 진행률 가시화: FFmpeg progress 파싱, phase 세부 진행률/ETA 저장, Step 4 실시간 진행 표시, 회귀 테스트 추가`
