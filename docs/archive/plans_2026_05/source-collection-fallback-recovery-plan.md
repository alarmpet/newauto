# Source Collection Fallback Recovery Plan

작성일: 2026-05-07

## 문제

LM Studio에서 `make_hpsl_flow_short_video`가 자료 수집 단계에서 `HTTP 500 Internal Server Error`로 실패했다.

원인은 두 갈래다.

- 키워드 자료 수집이 Brave API에 강하게 의존해, API 키가 없거나 검색 API가 실패하면 워크플로우가 앞단에서 멈출 수 있다.
- MCP compatibility wrapper가 `NewautoError`를 사용자 메시지로 회수하지 못하면 LM Studio에서는 tool call failed로만 보인다.

## 완료한 수정

- [완료] `collect_sources_from_keyword()`에 DuckDuckGo HTML 검색 fallback을 추가했다.
- [완료] Brave API 키가 없으면 무료 DuckDuckGo HTML 검색으로 검색 결과를 가져온다.
- [완료] Brave HTTP/네트워크 오류가 나도 DuckDuckGo HTML 검색으로 fallback한다.
- [완료] fallback 결과도 기존 keyword cache에 저장해 반복 호출 비용과 시간을 줄인다.
- [완료] `start_stepwise_hpsl_video_workflow()`가 자료 수집 실패를 tool failure로 터뜨리지 않고 `source_collect` 재시도 상태를 저장한다.
- [완료] `continue_stepwise_hpsl_video_workflow()`가 `source_collect` 상태에서 자료 수집을 재시도할 수 있게 했다.

## 운영 방식

```text
make_hpsl_flow_short_video
  -> project 생성
  -> source keyword/url collect
  -> 실패하면 next_step = source_collect 저장 후 사용자에게 원인 반환
  -> 사용자가 진행
  -> source_collect 재시도
  -> 성공하면 next_step = script_generate
```

## 테스트

- [완료] Brave API 키가 없을 때 DuckDuckGo HTML fallback이 검색 결과를 반환하는 단위 테스트 추가.
- [완료] `python -m pytest tests\test_source_research.py tests\test_flow_uivision.py`
- [완료] `python -m mypy app\services\source_research.py app\routers\projects.py scripts\newauto_mcp.py scripts\flow_desktop_control.py tests\test_source_research.py tests\test_flow_uivision.py`

## 남은 주의점

- 이미 실행 중인 newauto 서버와 LM Studio MCP 서버는 재시작해야 새 fallback 로직을 사용한다.
- `tests/test_feature_workflow.py`에는 이번 변경과 무관한 기존 들여쓰기 오류가 있어 전체 feature workflow 테스트 수집이 막힌다.
