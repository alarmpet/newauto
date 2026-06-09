# LM Studio 마이그레이션 실행안

이 문서는 Ollama 기반 운영에서 LM Studio 기반 운영으로의 마이그레이션 방향을 정리한 운영 노트입니다.

## 1. 설계 핵심
- 우선순위 P0: `OllamaClient`에서 provider 분기(`ollama` / `lmstudio`)를 우선 반영.
  - Ollama: `/api/generate`
  - LM Studio: `/v1/chat/completions`
- 매핑 규칙
  - `num_predict` -> `max_tokens`
  - `keep_alive`는 LM Studio 호출에서 제외
  - `system`, `prompt` -> `messages` (`role=system`, `role=user`)
- `keep_alive`/LM Studio 전용 동작은 no-op/무시로 통일
- `unload`, `warm`는 LM Studio에서 API 호출하지 않고 no-op 처리

## 2. 적용 대상(우선순위)
### P0 (최우선)
- `app/services/llm_ollama.py`
  - provider 분기 추가 (`ollama`면 기존 `/api/generate`, `lmstudio`면 `/v1/chat/completions`)
  - `num_predict`->`max_tokens` 변환
  - `keep_alive` 무시 규칙
  - LM Studio 응답 파싱(`choices[].message.content`) 적용
- `app/workers/source_draft_worker.py`
  - `gpu_guard.acquire("ollama")` -> `gpu_guard.acquire("lmstudio")`
  - deadlock 회피용 legacy 리소스(`ollama`) fallback 동시 고려
- `app/services/visual_planner.py`
  - readiness check 분기: `/api/tags`(Ollama) / `/v1/models`(LM Studio)

### P1
- `app/config.py`
  - `LLM_PROVIDER` 및 `LMSTUDIO_BASE_URL` 지원
  - 기존 `OLLAMA_BASE_URL`를 하위호환 fallback으로 유지 + warning
- 문서/사용자 기본값 정리
  - README에서 `LLM_PROVIDER=lmstudio`, `LMSTUDIO_BASE_URL`, `SCRIPT_LLM_MODEL` 기본값 가이드 반영
- 모델/도구 표기 일관성
  - tool status / usage registry에서 provider 표현을 `lmstudio`로 반영

### P2
- TTS/연계 모듈의 unload/warm 경로 no-op 방어
- 테스트 보강 및 문서 체크리스트 정리
  - `tests/test_llm_ollama.py`
  - `tests/test_visual_planner.py`
  - `tests/test_system_operator.py`
  - `tests/test_feature_workflow.py`
  - `tests/test_config.py`

## 3. 환경변수 하위호환 규칙
- 우선순위: `LMSTUDIO_BASE_URL` > `OLLAMA_BASE_URL` > 기본값(`http://127.0.0.1:1234`)
- `OLLAMA_BASE_URL`만 있을 경우 warning을 1회 기록하고 fallback 사용
- `LLM_PROVIDER`가 유효하지 않은 값이면 `ollama`로 fallback (warning)

## 4. API 동작 차이 정리
- `OllamaClient.generate`
  - Ollama payload: `prompt`, `system`, `num_predict`, `keep_alive`
  - LM Studio payload: `messages`, `max_tokens`
  - `keep_alive`는 LM Studio로 전달되지 않음
- `OllamaClient.unload` / `warm`
  - Ollama: 기존 동작 유지
  - LM Studio: no-op

## 5. 빠른 검증 체크리스트
- [x] P0: provider 분기형 API 어댑터 설계 반영
- [x] P0: `num_predict -> max_tokens`, `keep_alive` LM Studio 무시
- [x] P0: `source_draft_worker` gpu_guard 리소스 `lmstudio` 반영
- [x] P0: readiness endpoint를 `/api/tags` / `/v1/models`로 분기
- [x] P1: `LLM_PROVIDER`, `LMSTUDIO_BASE_URL`, `OLLAMA_BASE_URL` fallback & 경고 정책 반영
- [x] P1: model/tool/usage provider 텍스트 동적 반영
- [x] P2: 테스트 보강 (`llm_ollama`, `visual_planner`, `system_operator`, `feature_workflow`, `config`)
- [x] P2: README 체크리스트/마이그레이션 가이드 반영

## 6. 현재 상태
- 핵심 P0 항목은 코어 코드와 테스트에서 반영 완료 기준으로 진행.
- 문서는 다음 단계로 바로 실행 가능한 상태로 정렬되어 있음.
