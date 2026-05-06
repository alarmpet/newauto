# LM Studio + Flow 생성 실패 원인 분석 및 해결 계획

작성일: 2026-05-07

## 결론

현재 문제는 Flow 로그인/인증 문제가 아니다.

핵심 원인은 다음 5가지다.

1. LM Studio MCP 호출이 Flow 이미지 생성을 동기식으로 오래 기다리다가 timeout에 걸린다.
2. Ui.Vision/Flow 단계 문구가 "준비 완료"와 "실제 생성 완료"를 섞어서 말해 사용자가 어디서 멈췄는지 알기 어렵다.
3. 기존 데스크톱 제어 스크립트가 Flow의 현재 그리드 화면을 고려하지 않고, 결과 상세 화면 기준으로 바로 다운로드 버튼을 눌렀다.
4. 새 다운로드 파일이 없을 때 예전 다운로드 파일을 fallback으로 붙이는 위험한 로직이 있었다.
5. 대본은 한국어여야 하지만 Flow 이미지 프롬프트에는 한국어 narration이 그대로 들어가 이미지 생성 prompt 품질이 흔들렸다.

## 현재 확인된 상태

- 프로젝트 `cb505a7a5358`는 존재한다.
- 단계 상태는 `flow_generate`이다.
- `uivision` 폴더와 `prompt_001.txt` ~ `prompt_006.txt`가 생성되어 있다.
- Flow 브라우저는 로그인된 상태로 열린다.
- 실제 Flow 이미지는 생성된다.
- 문제는 생성 후 다운로드/attach까지 한 MCP 호출 안에서 안정적으로 끝내지 못하는 것이다.

## 이미 반영한 긴급 수정

- Flow 프롬프트 생성 로직 변경:
  - 대본/narration은 한국어로 보존.
  - Flow에 붙여넣는 이미지 프롬프트는 영어 장면 설명만 포함.
  - `Narration context: 한국어 문장`을 제거하고 `Narration language: Korean. Do not render Korean text in the image.`로 대체.
- `/api/flow/prompts/{pid}/uivision/prepare`는 기존 깨진 프롬프트를 재사용하지 않고 항상 현재 로직으로 재생성하도록 변경.
- `scripts/flow_desktop_control.py` 수정:
  - 시작 시 `Esc`로 열린 Flow 메뉴를 닫는다.
  - 올바른 생성 화살표 좌표를 누른다.
  - 생성 후 결과 카드를 먼저 열고 다운로드 메뉴를 누른다.
  - 새 다운로드가 없으면 예전 파일을 fallback으로 붙이지 않고 실패한다.
- `scripts/newauto_mcp.py` 수정:
  - `flow_generate` 단계에서 Ui.Vision 안내만 하지 않고, 빠진 문장 1개를 데스크톱 제어 스크립트로 생성/다운로드/attach 시도한다.

## 남은 구조 문제

### 1. MCP timeout

Flow 이미지 1장 생성은 보통 45~80초가 걸릴 수 있다.

LM Studio의 tool call은 이 시간을 기다리다가 timeout으로 실패할 수 있다. 따라서 MCP가 "생성 완료까지 기다리는 구조"이면 계속 불안정하다.

### 2. 단계명이 부정확함

현재 LM Studio 응답이 "5단계 최종 작업 지시 완료"처럼 말하지만 실제 상태는 `flow_generate`이다.

이 때문에 사용자는 인증 문제가 남았다고 오해한다.

### 3. 실행 주체 혼선

Ui.Vision 매크로, 데스크톱 제어 스크립트, Playwright/CDP가 섞여 있다.

당장 안정적인 경로는 다음 하나로 고정해야 한다.

```text
LM Studio continue
  -> MCP
  -> scripts/flow_desktop_control.py
  -> 인증된 Flow Chrome 창
  -> 프롬프트 1개 입력
  -> 생성 클릭
  -> 별도 완료 확인/다운로드/attach
```

## 권장 해결 구조

### Phase 1: 1문장 2단계 방식으로 변경

한 번의 MCP 호출에서 생성 완료까지 기다리지 않는다.

```text
continue 1회차:
  - 빠진 문장 1개 프롬프트 입력
  - Generate 클릭
  - state를 flow_wait_sentence로 저장
  - 즉시 응답: "1번 문장 생성 시작. 완료되면 진행이라고 말해."

continue 2회차:
  - 방금 생성된 결과 카드 열기
  - 다운로드
  - 새 파일만 감지
  - 해당 문장에 attach
  - 다음 문장으로 이동
```

이렇게 하면 LM Studio tool timeout을 피할 수 있다.

### Phase 2: 상태 파일 추가

`storage/stepwise_workflows/{project_id}.json`에 다음 필드를 추가한다.

```json
{
  "next_step": "flow_wait_sentence",
  "active_sentence_number": 2,
  "flow_generate_started_at": "2026-05-07T02:10:00",
  "downloads_before": ["..."]
}
```

이 상태를 기준으로 다음 `진행`에서 다운로드/attach만 수행한다.

### Phase 3: Flow 화면 상태별 복구

Flow 화면은 최소 3가지 상태가 있다.

- 빈 입력 화면
- 생성 결과가 그리드에 있는 화면
- 결과 상세 화면

스크립트는 상태를 강하게 가정하지 말고 다음 순서로 복구해야 한다.

```text
1. 열린 메뉴 닫기: Esc
2. 입력창이 있으면 prompt 입력
3. 생성 클릭
4. 다운로드 단계에서는 결과 카드 후보 클릭
5. 상세 화면에서 다운로드 아이콘 클릭
6. 1K 원본 크기 클릭
```

### Phase 4: LM Studio 안내문 수정

Gemma4가 "로그인 필요"라고 반복하지 않게 MCP 응답 문구를 고친다.

권장 문구:

```text
Flow 로그인은 완료된 것으로 보입니다.
현재 필요한 작업은 인증이 아니라 문장 N번 이미지 생성/다운로드입니다.
이번 호출에서는 생성 클릭만 했고, Flow 생성이 끝나면 `진행`이라고 말해주세요.
```

### Phase 5: 최종 batch는 나중에

6문장 batch 생성은 v2로 둔다.

현재는 1문장씩:

```text
문장 1 생성 시작 -> 진행 -> 다운로드/attach
문장 2 생성 시작 -> 진행 -> 다운로드/attach
...
문장 6 완료 -> TTS 단계
```

이 구조가 어디서 실패했는지 가장 잘 보인다.

## 즉시 다음 작업

- [완료] 한글 대본/영문 Flow 프롬프트 분리.
- [완료] stale download fallback 제거.
- [완료] Flow 그리드 결과 카드 열기 후 다운로드 순서 반영.
- [필요] MCP `flow_generate`를 "생성 클릭만 하고 즉시 반환"으로 바꾸기.
- [필요] 새 단계 `flow_wait_sentence` 추가.
- [필요] `flow_wait_sentence`에서 다운로드/attach만 수행.
- [필요] LM Studio 응답 문구에서 "로그인 필요" 반복 제거.
- [필요] `cb505a7a5358` 프로젝트로 1문장 시작/완료 왕복 테스트.
- [필요] 6문장 전체 생성 후 TTS 단계 진입 확인.

## 테스트 기준

```text
1. continue: "문장 1 생성 시작"을 30초 안에 반환해야 한다.
2. Flow에서 이미지가 보인 뒤 continue: 다운로드/attach 완료를 반환해야 한다.
3. 같은 문장에 예전 다운로드 파일이 붙으면 실패로 간주한다.
4. Flow prompt TXT에는 한글 문장이 직접 들어가지 않아야 한다.
5. script.txt와 hpsl_script.json의 narration은 한국어여야 한다.
6. 6문장 attach 후 next_step이 tts로 이동해야 한다.
```

## 운영 원칙

- 로그인/권한 승인만 사용자가 한다.
- 이미지 생성 클릭, 결과 카드 열기, 다운로드, attach는 자동화가 한다.
- 한 번에 6장을 만들지 않고, LM Studio에서 `진행`을 누를 때마다 한 단계만 간다.
- timeout이 나면 같은 단계에서 멈추고, 다음 호출로 복구 가능해야 한다.
