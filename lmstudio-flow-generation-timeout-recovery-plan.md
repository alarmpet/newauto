# LM Studio + Flow Timeout Recovery Plan

작성일: 2026-05-07  
리뷰 반영: `lmstudio-flow-timeout-recovery-plan-review.md`

## 결론

Flow 로그인/인증은 핵심 문제가 아니다. 현재 반복 실패의 본질은 **LM Studio MCP tool call 안에서 Flow 이미지 생성, 대기, 다운로드, attach를 한 번에 처리하려고 해서 timeout이 나는 구조**다.

따라서 해결 방향은 Ui.Vision이나 Flow 로그인을 다시 건드리는 것이 아니라, 워크플로우를 **1문장 2단계**로 분리하는 것이다.

```text
진행 1회: 문장 N 프롬프트 입력 + Generate 클릭 + 즉시 반환
진행 2회: 생성 완료된 결과 카드 다운로드 + attach + 다음 문장으로 이동
```

이렇게 해야 LM Studio tool call이 30초 안팎으로 끝나고, 실패 위치도 명확해진다.

## 현재 확인된 사실

- 프로젝트 `cb505a7a5358`는 존재한다.
- 현재 저장 상태는 `next_step = flow_generate`다.
- Flow 브라우저는 로그인된 상태로 열려 있다.
- `uivision/prompt_001.txt` ~ `prompt_006.txt`는 생성되어 있다.
- Flow 이미지 생성 자체는 실제로 성공한다.
- 실패는 생성 후 기다림, 결과 카드 열기, 다운로드, attach를 한 번의 MCP 호출에 묶으면서 발생한다.

## 이미 반영된 수정

- [완료] `FLOW_AUTOMATION_BACKEND=uivision` 기본 분기.
- [완료] `FLOW_MODE=uivision` MCP instructions 분기.
- [완료] `/api/flow/assets/{pid}/attach-renamed`와 `flow_sNNN_` 파일명 기반 attach.
- [완료] 한글 대본과 영어 Flow 이미지 프롬프트 분리.
- [완료] `/api/flow/prompts/{pid}/uivision/prepare`가 기존 깨진 prompt를 재사용하지 않고 재생성하도록 변경.
- [완료] 기존 다운로드 파일을 fallback으로 붙이는 위험한 경로 제거.
- [완료] Flow 그리드 화면에서 결과 카드를 먼저 열고 다운로드하는 순서 반영.
- [완료] `flow_generate`와 `flow_wait_sentence`를 분리해 LM Studio tool call timeout을 피하는 1문장 2단계 구조로 변경.
- [완료] `flow_desktop_control.py`를 `click-generate`와 `download-attach` 모드로 분리.
- [완료] 새 다운로드 파일 polling에서 `.crdownload`를 제외하고 파일 크기 안정화를 확인하도록 변경.
- [완료] attach 실패 시 `pending_attach_{sentence_number}.json`을 저장하고 다음 호출에서 attach만 재시도하도록 변경.
- [완료] Flow 창 탐지에 Chrome, Edge, Chromium title을 허용하도록 변경.
- [완료] Generate/Download 클릭 전후 스크린샷을 저장하고 결과/오류 응답에 경로를 남기도록 변경.
- [완료] Ui.Vision 모드의 `open_flow()`와 `open_flow_for_auth()`가 CDP/Playwright 연결을 기다리지 않고 Flow URL만 열고 즉시 반환하도록 변경.

## 구현 완료된 핵심 항목

### 1. `flow_wait_sentence` 단계 추가

`continue_stepwise_hpsl_video_workflow()`의 `flow_generate` 단계는 더 이상 `generate + wait + download + attach`를 한 번에 시도하지 않는다.

구현된 흐름:

```text
flow_generate
  -> prompt 입력
  -> Generate 클릭
  -> downloads_before 저장
  -> active_sentence_number 저장
  -> next_step = flow_wait_sentence
  -> 즉시 반환

flow_wait_sentence
  -> 결과 카드 열기
  -> 다운로드
  -> 새 다운로드 파일만 감지
  -> attach
  -> missing이 남으면 next_step = flow_generate
  -> 모두 완료되면 next_step = tts
```

### 2. `flow_desktop_control.py` 함수 분리

단일 `generate_one()` 경로 대신 CLI `--mode`로 실행 경로를 분리했다.

```text
click_generate(project_id, sentence_number)
  - Flow 창 활성화
  - Esc로 열린 메뉴 닫기
  - prompt_NNN.txt 복사
  - 입력창 클릭
  - Ctrl+A / Ctrl+V
  - Generate 클릭
  - 10초 안에 반환

download_and_attach(project_id, sentence_number, downloads_before)
  - Flow 창 활성화
  - 결과 카드 열기
  - 다운로드 메뉴 클릭
  - 1K 원본 크기 클릭
  - 새 파일 다운로드 완료까지 polling
  - attach-local 호출
```

### 3. `.crdownload` 감시와 다운로드 완료 polling

고정 `sleep(8)` 의존을 제거하고 새 다운로드 파일 polling을 추가했다.

구현 조건:

- 새 파일명만 허용한다.
- `.crdownload` 파일은 무시한다.
- 같은 이름의 `.crdownload`가 사라질 때까지 기다린다.
- timeout 안에 새 완성 파일이 없으면 실패한다.

권장 로직:

```text
deadline = now + 45초
while now < deadline:
  새 이미지/영상 파일 찾기
  .crdownload 제외
  파일 크기가 2회 연속 동일하면 완료로 판단
  완료 파일 반환
실패 처리
```

### 4. attach 실패 시 pending 저장

다운로드는 성공했지만 attach API가 실패하면 같은 이미지를 다시 생성하면 안 된다.

구현 변경:

```text
storage/projects/{pid}/uivision/pending_attach_{sentence_number}.json
```

저장 내용:

```json
{
  "sentence_number": 2,
  "asset_path": "C:/Users/petbl/Downloads/...",
  "created_at": "2026-05-07T02:20:00"
}
```

다음 `flow_wait_sentence` 호출은 pending 파일이 있으면 Flow를 다시 누르지 않고 attach만 재시도한다.

### 5. Flow 창 탐지 개선

Flow 창 탐지는 Chrome, Edge, Chromium title을 허용한다.

```text
Flow + Chrome
Flow + Edge
Flow + Chromium
labs.google URL 또는 Flow title
```

구현:

```python
if "Flow" in title and ("Chrome" in title or "Edge" in title or "Chromium" in title):
```

### 6. 좌표 클릭 전후 상태 확인

좌표 클릭은 당장은 가장 실용적이지만, 상태 검증이 없으면 엉뚱한 곳을 누른다.

구현 보강:

- 클릭 전 스크린샷 저장.
- 클릭 후 스크린샷 저장.
- 새 다운로드가 없으면 실패로 반환.
- 실패 메시지에 스크린샷 경로 포함.

추후 개선:

- `pyautogui.locateOnScreen()` 이미지 매칭 fallback.
- 입력창/다운로드 아이콘/1K 메뉴 버튼 template 이미지 저장.

## 수정할 워크플로우 상세

### `flow_generate`

목표: 생성 클릭만 하고 빠르게 반환한다.

```text
1. project 상태 조회
2. missing sentence 중 첫 번째 선택
3. pending attach가 있으면 flow_wait_sentence로 넘김
4. downloads_before 목록 저장
5. click_generate 실행
6. next_step = flow_wait_sentence
7. active_sentence_number = N
8. "문장 N 생성 시작. Flow에서 이미지가 보이면 진행이라고 말해줘." 반환
```

성공 응답 예:

```text
Flow 로그인은 완료된 것으로 보입니다.
현재 필요한 작업은 인증이 아니라 문장 2번 이미지 생성입니다.
이번 호출에서는 Generate 클릭만 했습니다.
Flow에서 이미지가 보이면 `진행`이라고 말해주세요.
```

### `flow_wait_sentence`

목표: 다운로드와 attach만 수행한다.

```text
1. active_sentence_number 읽기
2. pending attach 파일이 있으면 attach만 재시도
3. pending이 없으면 결과 카드 열기
4. 1K 다운로드 클릭
5. downloads_before에 없던 새 파일 감지
6. attach-local 호출
7. 성공 시 pending 삭제
8. missing이 남으면 next_step = flow_generate
9. 모두 끝나면 next_step = tts
```

성공 응답 예:

```text
문장 2번 이미지 다운로드/연결 완료.
coverage: 2/6
다음 문장을 생성하려면 `진행`이라고 말해주세요.
```

## 테스트 기준

- [완료] `flow_generate` 호출은 30초 안에 반환하도록 `click-generate`만 실행한다.
- [완료] `flow_generate`는 다운로드나 attach를 하지 않는다.
- [완료] `flow_wait_sentence`는 prompt를 다시 입력하지 않고 다운로드/attach만 수행한다.
- [완료] 새 다운로드 파일이 없으면 예전 파일을 붙이지 않는다.
- [완료] `.crdownload` 파일은 완료 파일로 취급하지 않는다.
- [완료] attach 실패 시 pending attach 파일이 생성된다.
- [완료] 다음 호출에서 pending attach를 우선 처리한다.
- [완료] Edge/Chromium Flow 창도 탐지한다.
- [필요] 6문장 attach 완료 후 `next_step`이 `tts`로 이동해야 한다.

## 우선순위

1. [완료] `flow_generate`와 `flow_wait_sentence` 분리.
2. [완료] `flow_desktop_control.py`를 `click_generate` / `download_and_attach` 모드로 분리.
3. [완료] `.crdownload` polling 추가.
4. [완료] attach 실패 pending 저장.
5. [완료] Flow 창 탐지에 Edge/Chromium 지원.
6. [완료] 클릭 전후 스크린샷 경로를 실패 응답에 포함.
7. [필요] `cb505a7a5358`로 1문장 시작/완료 왕복 테스트.
8. [필요] 6문장 전체 attach 후 TTS 단계 진입 확인.

## 운영 원칙

- 사용자는 로그인/권한 승인만 한다.
- 이미지 생성 클릭, 결과 카드 열기, 다운로드, attach는 자동화가 한다.
- LM Studio에서는 `진행`을 누를 때마다 하나의 짧은 단계만 실행한다.
- timeout이 나면 같은 단계에서 복구 가능해야 한다.
- batch 생성은 v2로 미루고, v1은 1문장씩 안정화한다.
- Ui.Vision 모드에서 `open_flow`는 인증 페이지를 열기만 해야 하며, 브라우저 자동화 연결을 기다리면 안 된다.
