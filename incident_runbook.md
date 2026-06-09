# Video Workflow Incident Runbook

반복되는 HPSL/Flow/shorts 영상 워크플로우 장애를 증상별로 정리한 문서다.

## 1. Shorts 대신 Landscape로 렌더됨

- 증상: Flow 이미지는 768x1376 세로인데 최종 영상이 1920x1080 `output.mp4`로 생성된다.
- 원인: project `render_formats` 또는 scene/render plan이 `landscape` 기준으로 남아 있다.
- 조치:
  - HPSL 쇼츠 작업은 `render_formats=["shorts"]`를 강제한다.
  - scene plan은 `build_scene_plan(project, render_format="shorts")` 기준으로 만든다.
  - 최종 성공 artifact는 `output_shorts.mp4`로 판정한다.
- 재발 방지:
  - preflight에 `render_format_for_shorts` 체크를 둔다.
  - `output.mp4`만 있으면 쇼츠 PASS로 기록하지 않는다.

## 2. Hook 중복 또는 대본 길이 과다

- 증상: 첫 문장에 기사 제목이 반복되거나 80자 이상으로 길어져 TTS와 자막이 무너진다.
- 원인: HPSL 생성/정규화 단계에서 title 중복, copy-risk, 문장 길이 검증이 약하다.
- 조치:
  - hook은 기사 제목 직접 반복을 제거한다.
  - 첫 문장은 45자 이하, 일반 문장은 55자 이하로 재작성한다.
  - 원문 15자 이상 연속 복사가 과하면 facts 기반 rewrite fallback을 적용한다.
- 구현 위치:
  - `app/services/hpsl_script.py`
  - `app/services/script_safety.py`
  - 관련 테스트: `tests/test_hpsl_script.py`, `tests/test_script_safety.py`

## 3. 자막 Cue 과밀 또는 줄바꿈 실패

- 증상: 한 cue가 10초 이상 유지되거나 한 줄에 긴 한국어 문장이 몰린다.
- 원인: sentence 단위 cue split과 `_smart_wrap()` 기준이 쇼츠 화면에 맞지 않는다.
- 조치:
  - 쇼츠 기본은 `cue_split_mode="readable"`로 둔다.
  - `max_cue_sec`는 2.0~2.8초 범위로 제한한다.
  - 한 cue 2줄 초과 예상 또는 한 줄 18자 초과 예상이면 분할한다.
- 구현 위치:
  - `app/services/subtitle.py`
  - 관련 테스트: `tests/test_subtitle_rendering.py`

## 4. Source Title과 Project Title 불일치

- 증상: 영상 내용은 A 기사인데 project title/render report title은 B 기사처럼 보인다.
- 원인: source draft 확정 후 project metadata가 동기화되지 않았다.
- 조치:
  - source draft가 확정되면 project title을 source title 또는 HPSL topic으로 동기화한다.
  - render 전 preflight에서 source title/project title mismatch를 경고 또는 실패 처리한다.
- 구현 위치:
  - `app/services/source_draft.py`
  - `app/services/preflight.py`

## 5. Flow 이미지가 의미 검증 없이 통과

- 증상: 이미지 파일은 존재하지만 문장 의미와 맞지 않는다.
- 원인: `validation_policy=upload_only`가 파일 존재만 확인한다.
- 조치:
  - Flow assisted에서는 최소한 prompt/sentence keyword 검증을 수행한다.
  - `semantic_match_score=0` 또는 `missing_expected_keywords`가 많으면 render 전 operator review 또는 hard fail로 처리한다.
- 구현 위치:
  - `app/services/visual_relevance.py`
  - `app/services/preflight.py`

## 6. 실패 Asset 잔존

- 증상: 100KB 미만 또는 19x18 같은 비정상 이미지가 `media`에 남아 후속 재사용 위험이 생긴다.
- 원인: attach-local 또는 repair 이후 이전 실패 파일을 제외하지 않았다.
- 조치:
  - 100KB 미만, 비정상 해상도, decode 실패 이미지는 quarantine으로 이동한다.
  - 같은 sentence에 새 asset을 붙이면 이전 실패 asset은 media order에서 제외한다.
- 구현 위치:
  - `app/routers/flow.py`
  - `app/services/image_quality.py`
  - `app/services/preflight.py`

## 7. OpenRouter Free Model Rate Limit

- 증상: `google/gemma-* free` 또는 `openai/gpt-oss-* free`가 HTTP 429로 실패한다.
- 원인: upstream free model rate limit.
- 조치:
  - OpenRouter는 advisory 전용으로만 사용한다.
  - 429가 나오면 같은 모델 반복 호출을 줄이고 fallback 결과만 기록한다.
  - 핵심 workflow 진행은 local/Flow/TTS/render 상태 검증으로 계속한다.

## 8. Scene-plan Build Timeout

- 증상: render enqueue 단계에서 `/scene-plan/build`가 60초 이상 timeout 된다.
- 원인: 이미 mappings가 완성됐는데 scene/render plan rebuild를 강제한다.
- 조치:
  - preflight가 OK이고 current mappings가 완전하면 rebuild를 건너뛰고 render endpoint를 호출한다.
  - preflight가 OK가 아닐 때만 scene/render plan을 rebuild한다.
- 구현 위치:
  - `scripts/newauto_mcp.py`
  - `app/services/scene_plan.py`
  - `app/services/render_plan.py`

## 9. 잘못된 수동 운영: DB 상태 강제 변경

- 증상: Codex/Cline이 DB를 수동으로 `queued` 처리해 렌더를 완료시킨다.
- 판단: 운영상 잘못된 방식이다. QA gate를 통과하지 않은 상태를 성공처럼 만들 수 있다.
- 조치:
  - DB 수동 상태 변경으로 workflow를 진행하지 않는다.
  - 필요한 경우 API/tool 경로의 preflight 실패 원인을 수정한다.
  - 수동 개입이 발생했다면 project result는 최소 `PARTIAL`로 기록한다.
