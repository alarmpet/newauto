# 기능 추천 계획서

## 구현 상태

- `[완료]` P0: Pre-flight 검사, loudnorm 정규화, Ken Burns, 시스템 상태 진단
- `[완료]` P1: BGM+ducking, 프로젝트 복제, Shorts 선택 렌더, YouTube 예약/통계
- `[완료]` P2: word timing 저장, karaoke 자막 렌더, 스톡 검색 API
- `[대기]` P3: Ollama, 로컬 이미지 생성, 배경 제거, MCP/Skill 연동

## 이번 반영 내용

### P0

- `GET /api/projects/{pid}/preflight` 추가
- `GET /api/system/health` 추가
- 렌더 오디오 loudnorm 정규화 추가
- 이미지 입력에 Ken Burns / zoompan 옵션 추가

### P1

- 프로젝트 필드 추가:
  - `kenburns_enabled`
  - `bgm_file`
  - `bgm_volume_db`
  - `bgm_ducking_enabled`
  - `render_formats`
  - `youtube_schedule_at`
- BGM 업로드/조회/삭제 API 추가
- 프로젝트 복제 API 추가
- landscape / shorts 선택 렌더 지원
- YouTube 예약 업로드 입력과 통계 조회 API 추가

### P2

- `timings_words.json` 저장 추가
- karaoke ASS 자막 렌더 지원
- Pexels / Pixabay 스톡 검색 API 추가

## 현재 코드 기준 정리

- 렌더 파이프라인은 이제 오디오 후처리와 다중 출력 분기를 가진다.
- 프로젝트 스키마는 P0~P2 기능을 담을 수 있도록 확장됐다.
- 프런트는 최소 진입 UI를 추가해 주요 기능을 바로 테스트할 수 있다.
- 스톡 검색은 백엔드 API 기준으로 우선 제공되며, 실제 결과 품질은 API 키 설정에 따라 달라진다.
- word timing 은 faster-whisper 의존성이 없을 때도 기본 분할 fallback 으로 저장되도록 구성했다.

## 남은 리스크

- `app/static/index.html`, `app/static/app.js`, `agent.md`, `app/config.py` 일부 기존 한글 문자열은 인코딩이 완전히 정리되지 않았다.
- BGM, Shorts, 예약 업로드는 동작하지만 세부 UX는 더 다듬을 여지가 있다.
- faster-whisper 미설치 환경에서는 정밀 단어 타이밍 대신 fallback 분할이 사용된다.
- 스톡 검색은 `PEXELS_API_KEY`, `PIXABAY_API_KEY` 설정이 있어야 실제 외부 검색 결과가 나온다.

## 다음 우선순위

### P3

- Ollama 기반 로컬 LLM 보조
- 로컬 이미지 생성
- 배경 제거
- MCP 서버 / Claude Skill 연동
