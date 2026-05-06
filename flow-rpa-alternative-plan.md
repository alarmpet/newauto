# Flow 자동화 대체 구조 계획: Ui.Vision RPA 중심

작성일: 2026-05-06  
업데이트: 2026-05-06  
반영 문서: `flow-rpa-alternative-plan-review.md`

## 결론

현재 Flow 자동화는 Playwright/CDP 방식에서 계속 흔들리고 있다.

주요 원인:

- Flow UI가 동적 React UI라 버튼/입력창 선택자가 자주 바뀐다.
- Google 인증 프로필과 자동화 전용 브라우저 프로필이 갈라진다.
- Flow는 실제 로그인 세션, 팝업, 새 프로젝트 버튼, 더보기 메뉴, 다운로드 메뉴처럼 화면 상태 의존성이 크다.
- Gemma4 E4B가 매번 브라우저 상태를 보고 안정적으로 판단하기에는 작고, 컨텍스트도 쉽게 낭비된다.
- 현재 코드도 이미 입력창/생성 버튼/새 프로젝트 버튼을 여러 단계로 탐색하고 있는데, 이 상태에서도 실패가 반복된다면 DOM 자동화 접근 자체를 바꾸는 편이 맞다.

따라서 최종 권장 구조는 다음이다.

```text
LM Studio + Gemma4 = 기획 / 자료수집 / HPSL 대본 / Flow 프롬프트 / 단계 진행 판단
newauto MCP = 프로젝트 상태 관리 / 프롬프트 CSV-TXT 제공 / 결과 파일 첨부 / TTS / 렌더
Ui.Vision RPA = Flow 화면 클릭 / 입력 / 생성 / 다운로드 반복 실행
사용자 = 최초 로그인 / 권한승인 / 단계별 OK
```

즉, Flow 조작은 AI 에이전트가 매번 새로 판단하지 않고, 사용자가 한 번 성공시킨 화면 조작을 Ui.Vision 매크로로 반복한다.

## 최종 추천

### 1순위: Ui.Vision RPA + newauto MCP

이유:

- 비용 0원 방향을 유지할 수 있다.
- 사용자가 직접 인증한 실제 브라우저 화면을 그대로 자동화한다.
- Flow의 `+ 새 프로젝트`, 입력창, 생성 버튼, 결과 카드 `...`, `다운로드`, `2K 업스케일` 같은 화면 작업에 적합하다.
- 실패 위치가 눈에 보이므로 디버깅이 쉽다.
- Gemma4가 브라우저를 직접 조작하지 않아도 되므로 컨텍스트 초과와 도구 선택 오류가 줄어든다.

### 2순위: Browser MCP

이유:

- 실제 로그인된 Chrome 프로필을 쓸 수 있다는 장점이 있다.
- 다만 확장 연결 유지, repo 빌드 상태, MCP 서버 연결 안정성이 변수다.
- Flow 반복 제작의 주력보다는 보조안으로 둔다.

### 3순위: Browser Use + MCP

이유:

- AI 에이전트 방식으로는 가장 현대적이다.
- 하지만 무료 로컬 Gemma4만으로 Flow 전체 조작을 안정적으로 맡기기에는 리스크가 크다.
- 외부 API 키 없이 autonomous agent를 쓰려면 별도 어댑터와 장시간 테스트가 필요하다.

## 권장 운영 구조

```text
LM Studio 채팅
  -> newauto-hpsl-flow MCP
  -> 자료 수집 / HPSL 대본 / Flow 프롬프트 생성
  -> flow_prompts.json + CSV/TXT 저장
  -> Ui.Vision RPA 매크로 실행 안내 또는 트리거
  -> Ui.Vision이 Flow에 프롬프트 입력 / 생성 / 다운로드
  -> 다운로드 직후 파일명 rename
  -> newauto가 파일명 기반으로 문장별 asset attach
  -> OmniVoice TTS
  -> 싱크 / 자막 / 렌더
  -> 최종 mp4
```

사용자 경험은 계속 단계형으로 유지한다.

```text
1단계 자료 수집 완료 -> 사용자 ok
2단계 HPSL 대본 완료 -> 사용자 ok
3단계 Flow 프롬프트 생성 완료 -> 사용자 ok
4단계 Ui.Vision으로 Flow 생성/다운로드 -> 사용자 인증 또는 확인
5단계 다운로드 감지/첨부 완료 -> 사용자 ok
6단계 OmniVoice TTS 완료 -> 사용자 ok
7단계 최종 렌더 완료
```

## 중요한 설계 변경점

### 1. Playwright 코드는 삭제하지 않고 backend 선택으로 보존

Ui.Vision으로 전환하더라도 기존 Playwright/CDP 코드는 즉시 삭제하지 않는다.

`FLOW_AUTOMATION_BACKEND` 환경 변수를 추가한다.

```text
FLOW_AUTOMATION_BACKEND=uivision
FLOW_AUTOMATION_BACKEND=playwright
FLOW_AUTOMATION_BACKEND=assisted
```

동작:

- `uivision`: 기본값. Ui.Vision 매크로 안내/트리거 사용.
- `playwright`: 기존 `flow_browser_automation.py` 경로 유지. 롤백용.
- `assisted`: 사용자가 직접 복사/붙여넣기/다운로드하는 수동 보조 모드.

`continue_stepwise_hpsl_video_workflow()`는 `flow_auth`, `flow_generate`, `flow_download` 단계에서 backend에 따라 분기한다.

```text
flow_auth:
  uivision   -> Flow 로그인/권한승인 확인 및 Ui.Vision 준비 안내
  playwright -> 기존 open_flow 실행
  assisted   -> 수동 Flow 접속 안내

flow_generate:
  uivision   -> Ui.Vision 프롬프트 생성 매크로 안내/트리거
  playwright -> 기존 generate 실행
  assisted   -> 프롬프트 TXT/CSV 위치 안내

flow_download:
  uivision   -> Ui.Vision 다운로드 매크로 안내/트리거
  playwright -> 기존 download 실행
  assisted   -> 다운로드 후 attach 안내
```

### 2. 다운로드 파일은 시간순이 아니라 파일명으로 문장 매핑

현재처럼 “다운로드 폴더의 최신 파일 N개”를 문장 순서대로 붙이면 실패/재시도 시 이미지가 다른 문장에 붙을 수 있다.

반드시 파일명 기반 매핑으로 바꾼다.

권장 파일명:

```text
flow_s001_20260506T230101.png
flow_s002_20260506T230215.png
flow_s003_20260506T230330.png
```

원칙:

- Ui.Vision은 다운로드 직후 XRun으로 최신 다운로드 파일을 문장 번호가 들어간 이름으로 rename한다.
- newauto는 파일명 `flow_sNNN_` 패턴을 읽어 정확한 sentence index에 attach한다.
- batch 중 3번이 실패하고 4번이 성공해도 4번 파일은 4번 문장에 붙는다.

대안:

- 안정화 전에는 “매크로 1회 실행 = 프롬프트 1개 생성 + 다운로드 1개 + 즉시 attach” 방식으로 간다.
- 1문장 단건 E2E가 통과한 뒤에만 6문장 batch를 켠다.

### 3. Ui.Vision XRun marker 파일로 완료/실패를 전달

Python이 Ui.Vision 매크로의 종료 코드를 직접 안정적으로 받을 수 있다고 가정하지 않는다.

Ui.Vision 매크로 마지막 단계에서 XRun으로 marker 파일을 생성한다.

성공 marker 예:

```powershell
powershell.exe -NoProfile -Command "@{status='done'; completed_at=(Get-Date -Format o)} | ConvertTo-Json | Set-Content 'C:\Users\petbl\newauto\storage\projects\PROJECT_ID\uivision\run_done.json' -Encoding UTF8"
```

실패 marker 예:

```powershell
powershell.exe -NoProfile -Command "@{status='error'; message='Ui.Vision macro failed'} | ConvertTo-Json | Set-Content 'C:\Users\petbl\newauto\storage\projects\PROJECT_ID\uivision\run_done.json' -Encoding UTF8"
```

newauto는 이 파일을 감시해서 LM Studio에 다음 메시지를 돌려준다.

```text
Flow 이미지 1번 생성/다운로드 완료. 다음 단계 진행?
```

또는:

```text
Flow 이미지 3번 생성 실패. Flow 화면 확인 또는 3번만 재시도 필요.
```

### 4. 기존 flow.py 라우터를 확장하고 중복 API를 만들지 않음

새로운 `/api/flow/uivision/...` 라우터를 따로 만들기보다, 기존 Flow 라우터에 CSV/TXT 출력만 추가한다.

추가 후보:

```text
GET /api/flow/prompts/{pid}/csv
GET /api/flow/prompts/{pid}/sentence/{sentence_number}
POST /api/flow/assets/{pid}/attach-renamed
```

역할:

- `/csv`: Ui.Vision CSVRead용 프롬프트 목록 제공.
- `/sentence/{n}`: 1문장 단위 테스트용 프롬프트 TXT 제공.
- `/attach-renamed`: `flow_sNNN_` 파일명을 파싱해서 문장별 asset attach.

### 5. MCP instructions를 모드별로 줄인다

Gemma4 E4B는 작은 모델이므로 긴 MCP instructions와 많은 도구가 있으면 도구 선택 오류가 난다.

전환 후 기본 모드는 `uivision`으로 한다.

```text
FLOW_MODE=uivision
```

`uivision` 모드에서 LM Studio에 우선 노출할 도구:

```text
start_stepwise_hpsl_video_workflow
continue_stepwise_hpsl_video_workflow
prepare_uivision_flow_batch
attach_latest_flow_downloads
attach_renamed_flow_downloads
```

Playwright 직접 도구는 deprecated 처리하거나 `FLOW_MODE=playwright`일 때만 등록한다.

## Ui.Vision 매크로 설계

### Macro 1: Flow 프로젝트 생성

목표:

- Flow 홈 화면에서 `+ 새 프로젝트` 클릭.
- 이미지 모드 선택.
- 9:16 선택.
- 1x 또는 사용자가 지정한 생성 수 선택.
- 무료 사용 가능한 현재 기본 모델 유지.

실패 시:

- 로그인 화면이면 사용자에게 “Flow 로그인/권한승인 필요” 알림.
- 버튼 이미지가 다르면 새 스크린샷으로 매크로 이미지 갱신.

### Macro 2: 프롬프트 1개 생성

목표:

- newauto가 제공한 프롬프트 1개를 Flow 입력창에 붙여넣기.
- 오른쪽 화살표/만들기 버튼 클릭.
- 생성 완료까지 대기.

완료 대기:

- 고정 대기만 쓰지 않는다.
- `XWaitForVisible` 또는 이미지 매칭으로 결과 카드가 나타나는지 확인한다.
- timeout 기본값은 3분, 필요하면 5분까지 늘린다.
- 결과 카드 앵커 이미지는 이미지 결과용/비디오 결과용 최소 2개를 준비한다.

### Macro 3: 결과 다운로드 + rename

목표:

- 최신 결과 카드 클릭.
- `...` 더보기 클릭.
- `다운로드` 클릭.
- `2K 업스케일` 클릭.
- 다운로드 완료 대기.
- 다운로드 직후 파일명을 `flow_sNNN_timestamp.ext`로 변경.

fallback:

- `2K`가 유료/업그레이드 요구로 막히면 `1K 원본 크기`로 fallback.
- `4K 업그레이드`, 결제, 구독, 유료 크레딧 구매 버튼은 자동 클릭 금지.

### Macro 4: 6문장 batch

단건 안정화 후에만 활성화한다.

```text
for each sentence:
  read prompt
  paste prompt
  click generate
  wait result
  download
  rename to flow_sNNN_timestamp.ext
  write marker
```

초기 운영은 반드시 1문장 단위로 검증한다.

## Ui.Vision 이미지/OCR 운영 기준

Flow UI가 한글이고 다크 테마라서 OCR/이미지 매칭이 깨질 수 있다.

대응:

- 좌표 클릭 단독 의존 금지.
- 이미지 매칭 + OCR/텍스트 확인 병행.
- confidence threshold는 0.7 이상으로 시작.
- Windows DPI/브라우저 확대율은 고정한다.
- 가능하면 Flow를 항상 같은 테마와 같은 창 크기로 실행한다.
- `uivision/images/`에 다크/라이트 앵커 이미지를 모두 보관한다.

권장 고정값:

```text
browser zoom: 100%
Windows display scaling: 현재 사용자 설정 고정
Flow window size: 1440x900 이상
Flow theme: 가능한 한 동일하게 유지
```

## newauto 변경 계획

### Phase 0: Ui.Vision 전제 조건 확인

확인:

- Chrome 또는 Edge Ui.Vision RPA 확장 설치.
- Ui.Vision XModules 설치.
- Hard-Drive Storage 활성화.
- XRun 무료 사용 가능 여부 확인.
- 매크로 실행 횟수 제한 여부 확인.

이 단계에서 XRun이 무료로 불가능하면 계획을 수정한다.

### Phase 1: CSV/TXT 내보내기

기존 `app/routers/flow.py`에 추가:

```text
GET /api/flow/prompts/{pid}/csv
GET /api/flow/prompts/{pid}/sentence/{sentence_number}
```

생성 파일:

```text
storage/projects/{project_id}/uivision/
  flow_prompts.csv
  prompt_001.txt
  prompt_002.txt
  ...
  expected_downloads.json
```

CSV 컬럼:

```text
sentence_number,prompt,negative_prompt,section,narration
```

### Phase 2: 단건 매크로 녹화

사용자가 Flow에서 1회 성공 동작을 녹화한다.

녹화 범위:

- 새 프로젝트 클릭
- 프롬프트 입력
- 생성
- 결과 더보기
- 다운로드
- 2K 또는 1K 선택
- 다운로드 파일 rename marker 작성

저장 위치:

```text
C:\Users\petbl\newauto\uivision\
  macros\
  images\
  csv\
  logs\
```

### Phase 3: 파일명 기반 attach

추가:

```text
attach_renamed_flow_downloads(project_id)
```

동작:

- Downloads 또는 지정 폴더에서 `flow_sNNN_` 파일 검색.
- NNN을 sentence index로 파싱.
- 이미 attach된 문장은 건너뜀.
- 누락 문장만 보고.

### Phase 4: MCP instructions 정리

`FLOW_MODE=uivision` 기본 모드에서는 Playwright 직접 자동화 도구를 LM Studio가 우선 선택하지 않도록 한다.

권장 안내:

```text
Flow 조작은 Ui.Vision RPA가 담당한다.
Gemma4는 자료수집, HPSL 대본, 프롬프트 생성, 단계 진행만 판단한다.
사용자가 ok/진행을 보내면 한 단계만 진행한다.
문제가 생기면 현재 단계, 프로젝트 ID, 필요한 사용자 행동만 짧게 알린다.
```

### Phase 5: 1문장 E2E 검증

1문장만 끝까지 통과해야 한다.

검증 순서:

```text
프롬프트 생성
Ui.Vision 입력
Flow 생성
다운로드
rename
attach
OmniVoice TTS
자막
렌더
최종 mp4
```

### Phase 6: 6문장 batch 확장

단건 성공 후에만:

- 6문장 batch.
- 실패 문장만 재시도.
- 누락 파일만 attach.
- TTS/렌더 자동 진행.

## 동시 실행 방지

Ui.Vision은 브라우저 포커스를 점유한다.

운영 원칙:

- 매크로 실행 중에는 사용자가 Flow 브라우저를 건드리지 않는다.
- newauto UI 또는 LM Studio 응답에 “Flow 생성 중 - 브라우저 사용 금지”를 표시한다.
- 실패 시 해당 문장 번호만 재시도한다.

## 비용 정책

허용:

- LM Studio 로컬 모델.
- Ui.Vision 무료 확장.
- Ui.Vision XModules 무료 범위.
- Google Flow 현재 무료 크레딧/무료 생성.
- 로컬 PowerShell/Python/FFmpeg/OmniVoice.

금지:

- OpenAI API.
- Anthropic API.
- Browser Use Cloud API.
- 유료 Search API.
- Flow 유료 업그레이드 자동 클릭.

주의:

- `2K 업스케일`은 무료일 때만 클릭.
- `4K 업그레이드`, 결제, 구독, 유료 크레딧 구매 버튼은 자동화 금지.

## 구현 순서

1. [사용자 확인 필요] Ui.Vision 확장, XModules, Hard-Drive Storage 설치 여부와 무료 범위 확인.
2. [완료] 기존 `flow.py`에 CSV/TXT 엔드포인트 추가.
3. [완료] `FLOW_AUTOMATION_BACKEND`와 `FLOW_MODE` 분기 추가.
4. [사용자 확인 필요] 1문장 단위 Ui.Vision 매크로 녹화.
5. [완료] XRun marker 파일 패턴 확정.
6. [사용자 확인 필요] 다운로드 직후 rename 매크로 추가.
7. [완료] `attach_renamed_flow_downloads` 추가.
8. [완료] MCP instructions를 Ui.Vision 중심으로 축소.
9. [대기] 1문장 E2E smoke test.
10. [대기] 6문장 batch test.
11. [대기] 다운로드 attach -> OmniVoice -> render까지 전체 테스트.

## 참고 링크

- Ui.Vision RPA: https://ui.vision/rpa
- Ui.Vision GitHub/A9T9: https://github.com/a9t9
- Ui.Vision XRun: https://ui.vision/rpa/docs/xrun
- Ui.Vision macro storage: https://forum.ui.vision/t/where-does-ui-vision-store-the-macros/93
- Ui.Vision Windows Task Scheduler/command line: https://ui.vision/howto/taskscheduler
- Browser Use MCP: https://docs.browser-use.com/open-source/customize/integrations/mcp-server
- Browser Use GitHub: https://github.com/browser-use/browser-use
- Browser MCP GitHub: https://github.com/BrowserMCP/mcp
- Browser MCP troubleshooting: https://docs.browsermcp.io/troubleshooting
## 2026-05-07 실행 체크포인트

- [완료] Ui.Vision Chrome 확장 설치 확인: `gcbalfbdmfieckjlnblleoemohcganoc`, version `9.5.9`.
- [완료] Ui.Vision XModules 설치 확인: `UI.Vision RPA XModules for Windows version 3.2.3`.
- [완료] 하드드라이브 저장소 확인: `C:\Users\petbl\Desktop\uivision\macros`.
- [완료] Flow 인증 후 단건 생성 조작 확인: Flow 프로젝트 `3d5d0440-9b88-47c2-9dae-1de89780a959`에서 prompt 1개 생성 성공.
- [완료] Flow 1K 다운로드 확인: `Create_a_cinematic_9_16_image_202605070102.jpeg`.
- [완료] 6문장 Flow 이미지 반복 생성/다운로드/프로젝트 연결 확인: project `fc7439ddbb12`, `flow_sentence_001.jpeg` ~ `flow_sentence_006.jpeg`.
- [완료] 반복 조작 보조 스크립트 추가: `scripts/flow_desktop_control.py`.
- [진행 예정] 위 좌표/절차를 Ui.Vision 녹화 매크로 또는 JSON 매크로로 고정하여 LM Studio 대화에서 재사용.
