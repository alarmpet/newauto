# HPSL Shorts Workflow Ops Checklist

URL 또는 키워드로 HPSL 쇼츠 영상을 생성할 때 적용하는 최신 운영 기준이다.

## 실행 전 체크

- 입력이 URL이면 기사 제목, 본문, source title, project title이 서로 같은 주제인지 확인한다.
- 입력이 키워드이면 영상 주제, HPSL topic, 최종 제목이 같은 방향인지 확인한다.
- 쇼츠 워크플로우 기본 렌더 포맷은 `shorts`다.
- 기존 프로젝트를 이어서 실행하는 경우 이미 생성된 정상 asset/TTS/render 결과를 불필요하게 다시 만들지 않는다.
- 실패 asset, 100KB 미만 이미지, 비정상 해상도 이미지는 렌더 전에 제외하거나 quarantine 처리한다.

## 대본 기준

- 기사를 그대로 읽는 영상이 아니라 HPSL 문법으로 재구성된 쇼츠 대본을 만든다.
- hook은 기사 제목을 그대로 반복하지 않는다.
- 첫 문장은 45자 이하, 일반 문장은 55자 이하를 목표로 한다.
- 기사 원문 15자 이상 연속 복사가 과하면 재작성한다.
- copy risk가 높으면 LLM 결과를 그대로 쓰지 말고 facts 기반 deterministic rewrite fallback을 적용한다.
- TTS 전에 긴 문장, 같은 단어 반복, 괄호/영문/숫자 과다를 점검한다.

## 이미지 프롬프트 기준

- 문장마다 `main_subject`, `action`, `context`, `must_show`, `must_avoid`를 구분해 만든다.
- `AI workflow`, `technology scene`, `futuristic interface` 같은 generic phrase 반복은 실패 신호로 본다.
- 연속 프롬프트가 너무 비슷하면 subject/action/context를 바꿔 장면 차이를 만든다.
- 이미지 프롬프트에는 읽을 수 있는 텍스트, 로고, 실제 UI 캡처 의존을 피한다.

## 렌더 기준

- 쇼츠 최종 산출물은 `output_shorts.mp4`를 기준으로 한다.
- `output.mp4`가 landscape로 생성되었다면 쇼츠 성공으로 판정하지 않는다.
- render report에서 `status=done`, `duration_guard_passed=true`, `missing_render_plan_media_count=0`, `fallback_used=false`를 확인한다.
- 자막은 readable split을 우선하고, 화면에 2줄을 초과하거나 긴 cue가 오래 유지되면 실패로 본다.

## 완료 판정

- `PASS`: 요청한 포맷의 실제 영상 artifact가 있고 QA 기준을 통과했다.
- `PARTIAL`: artifact는 있으나 우회/수동개입/QA 리스크가 남아 있다.
- `FAIL`: artifact가 없거나, 포맷/자막/이미지/메타데이터가 요청과 다르다.

## 문제 발생 시 순서

1. 최신 project id, 입력 URL/키워드, 실패 단계, 로그 경로를 확인한다.
2. `incident_runbook.md`에서 같은 증상과 기존 해결책을 찾는다.
3. 기존 해결책이 있으면 먼저 적용하고 결과를 기록한다.
4. 기존 해결책으로 안 되면 원인을 새 항목으로 정리하고 최소 수정으로 해결한다.
5. 관련 pytest, `py_compile`, 가능한 실제 워크플로우 재실행으로 검증한다.
6. 최종 산출물 경로, 렌더 포맷, 제외/quarantine asset, 잔여 리스크를 `project_log.md`에 기록한다.
