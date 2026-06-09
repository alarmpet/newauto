# Cline + Qwen3.5 브라우저/컴퓨터 유즈 실행 계획서

작성일: 2026-05-13

## 왜 다시 잡는가

현재 문제는 "도구는 있는데 Qwen3.5가 제대로 안 쓴다"에 가깝다. Qwen3.5는 강한 에이전트 모델처럼 도구를 스스로 잘 고르지 못할 수 있으므로, Cline 설정과 사용자 지시문을 더 단순하고 강제적으로 만들어야 한다.

목표는 다음 세 가지다.

- 웹 탐색은 무조건 브라우저 MCP로 실행하게 만들기
- 복잡한 웹 자동화는 Browser-Use로 넘기기
- PC 전체 조작은 위험하므로 꺼둔 상태에서 필요할 때만 켜기

## 현재 설치/검증 상태

### 정상

- Node/npm/npx 사용 가능
- Chrome 설치됨
- `playwright` MCP 설정 있음
- Chrome DevTools endpoint 정상: `http://127.0.0.1:9225/json/version`
- 브라우저 시작 스크립트 있음: `start-cline-browser.cmd`
- `uv` 설치 완료
- Browser-Use CLI 실행 확인 완료
- `cloudflared` 설치 완료
- `profile-use` 설치 완료
- Browser-Use doctor 5/5 통과
- Go 설치 완료
- MSYS2 + MinGW gcc 설치 완료
- `go_computer_use_mcp_server` 로컬 빌드 완료
- Cline 설정에 `computer-use` 추가 완료, 단 `disabled: true`

검증한 `uv` 경로:

```text
C:\Users\petbl\AppData\Local\Microsoft\WinGet\Packages\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe\uv.exe
```

검증 명령:

```powershell
& "C:\Users\petbl\AppData\Local\Microsoft\WinGet\Packages\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe\uv.exe" --version
& "C:\Users\petbl\AppData\Local\Microsoft\WinGet\Packages\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe\uv.exe" tool run --from "browser-use[cli]" browser-use --help
```

### 아직 문제 있음

- 현재 PowerShell 세션에서는 PATH에 `uv`/`uvx`가 바로 안 잡힐 수 있음. VS Code나 터미널 재시작 후 해결될 가능성이 높다.
- Browser-Use의 LLM 기반 추출/자율 에이전트 기능은 API 키가 필요할 수 있다.
- `computer-use`는 의도적으로 비활성화 상태다. 사용할 때만 수동으로 켠다.

## 1단계: Cline MCP 설정 권장안

현재 `playwright`는 유지한다. 여기에 `browser-use`를 추가한다.

설정 파일:

```text
C:\Users\petbl\AppData\Roaming\Code\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json
```

추가할 서버:

```json
"browser-use": {
  "command": "C:\\Users\\petbl\\AppData\\Local\\Microsoft\\WinGet\\Packages\\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe\\uv.exe",
  "args": [
    "tool",
    "run",
    "--from",
    "browser-use[cli]",
    "browser-use",
    "--mcp",
    "--headed",
    "--cdp-url",
    "http://127.0.0.1:9225"
  ],
  "env": {
    "BROWSER_USE_HEADLESS": "false",
    "PYTHONIOENCODING": "utf-8",
    "Path": "C:\\Users\\petbl\\AppData\\Local\\Microsoft\\WinGet\\Packages\\Cloudflare.cloudflared_Microsoft.Winget.Source_8wekyb3d8bbwe;C:\\Users\\petbl\\.browser-use\\bin;C:\\msys64\\usr\\bin;C:\\Windows\\System32;C:\\Windows;C:\\Windows\\System32\\Wbem"
  },
  "disabled": false,
  "autoApprove": []
}
```

주의:

- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY` 중 하나가 시스템 환경변수에 있으면 Browser-Use의 LLM 기반 기능이 더 잘 작동한다.
- 키를 JSON에 직접 적는 것은 추천하지 않는다. 가능하면 Windows 사용자 환경변수로 넣는다.
- Windows 콘솔에서 Browser-Use가 특수문자 출력 때문에 실패할 수 있어 `PYTHONIOENCODING=utf-8`을 넣는다.
- `autoApprove`는 비워둔다. Qwen3.5가 이상한 클릭을 할 수 있기 때문이다.

## 2단계: 도구 역할을 강제로 나누기

Qwen3.5에게는 아래처럼 단순한 규칙이 필요하다.

### Playwright MCP

기본 웹 브라우저다.

사용할 때:

- 최신 글 가져오기
- 검색 결과 읽기
- 특정 URL 열기
- 버튼 클릭
- 페이지 텍스트 추출
- 스크린샷 확인

예시:

```text
playwright MCP로 https://news.hada.io 를 열고 최신글 5개를 가져와.
브라우저 도구를 반드시 호출하고, 로컬 지식으로 답하지 마.
```

### Browser-Use MCP

Playwright가 실패하거나, 여러 단계를 스스로 탐색해야 할 때만 쓴다.

사용할 때:

- 검색해서 사이트를 찾아 들어가기
- 여러 링크를 따라가며 비교하기
- 폼 입력과 결과 확인이 섞인 작업
- Playwright로 클릭 대상 파악이 어려운 페이지

예시:

```text
browser-use MCP를 사용해서 GitHub에서 browser-use/browser-use 저장소를 찾아 README의 설치 명령을 확인해.
반드시 browser-use 도구를 호출하고, 결과에는 출처 URL을 포함해.
```

### Computer-Use MCP

설치와 빌드는 완료했지만 기본 비활성화 상태다.

이유:

- PC 전체 마우스/키보드 제어라 위험도가 높다.
- Qwen3.5가 실수하면 엉뚱한 앱을 클릭할 수 있다.

현재 Cline 설정:

```json
"computer-use": {
  "command": "C:\\Users\\petbl\\MCP\\go_computer_use_mcp_server\\native\\windows-amd64\\go_computer_use_mcp_server-windows-amd64.exe",
  "args": [
    "-t",
    "stdio"
  ],
  "env": {
    "Path": "C:\\msys64\\mingw64\\bin;C:\\Windows\\System32;C:\\Windows;C:\\Windows\\System32\\Wbem"
  },
  "disabled": true,
  "autoApprove": []
}
```

사용 조건:

- 별도 VM 또는 테스트 계정
- 수동 승인 필수
- 스크린샷 읽기부터 테스트
- 클릭/입력은 마지막 단계

## 3단계: Cline Custom Instructions

Cline의 커스텀 지시문에 아래 내용을 그대로 넣는다.

```text
도구 사용 강제 규칙:

1. 사용자가 최신 정보, 웹 검색, 사이트 확인, URL 열기, 뉴스 가져오기, GitHub 확인을 요청하면 반드시 브라우저 MCP 도구를 호출한다.
2. 기본 웹 작업은 playwright MCP를 먼저 사용한다.
3. playwright로 실패했거나 사용자가 browser-use를 명시하면 browser-use MCP를 사용한다.
4. 브라우저 도구를 쓰지 못한 경우, 답변을 만들지 말고 "브라우저 도구 호출 실패"와 실패 원인을 먼저 보고한다.
5. 웹에서 가져온 답에는 출처 URL을 포함한다.
6. 추측으로 최신 정보나 웹페이지 내용을 답하지 않는다.
7. computer-use는 사용자가 명시적으로 요청한 경우에만 사용한다.
8. 로그인, 결제, 구매, 삭제, 파일 업로드, 계정 설정 변경, 외부 전송은 실행 전 사용자 확인을 받는다.
9. 같은 실패를 2번 반복하지 않는다. 실패하면 playwright -> browser-use 순서로 전환한다.
10. 작업 완료 전에는 최소 한 번 실제 페이지 상태나 추출 결과를 확인한다.
```

## 4단계: 사용자가 줄 명령 템플릿

Qwen3.5에는 짧고 직접적인 명령이 더 잘 먹힌다.

### 최신 뉴스

```text
playwright MCP를 반드시 사용해.
https://news.hada.io 를 열고 최신글 5개의 제목, 링크, 시간, 댓글 수를 가져와.
브라우저 도구를 쓰지 못하면 답하지 말고 실패 원인을 말해.
```

### GitHub 조사

```text
브라우저 MCP를 반드시 사용해.
GitHub에서 browser-use/browser-use 저장소를 열고 README의 MCP 실행 명령을 찾아 요약해.
출처 URL을 포함해.
```

### Browser-Use 강제

```text
browser-use MCP를 반드시 사용해.
Google 또는 GitHub에서 browser-use MCP 설정법을 찾아 Cline 설정 예시를 만들어줘.
추측하지 말고 페이지에서 확인한 내용만 써.
```

## 5단계: 테스트 순서

1. `start-cline-browser.cmd` 실행
2. VS Code 완전 재시작
3. Cline MCP 서버 목록에서 `playwright` 확인
4. Cline MCP 서버 목록에서 `browser-use` 확인
5. Playwright 테스트 명령 실행
6. Browser-Use 테스트 명령 실행
7. 실패하면 Cline MCP 로그 확인

## 6단계: Computer-Use 운영 계획

현재 `go-computer-use-mcp-server`는 설치와 빌드는 완료했고, Cline에는 비활성화 상태로 등록했다.

설치 위치:

```text
C:\Users\petbl\MCP\go_computer_use_mcp_server
```

빌드 결과:

```text
C:\Users\petbl\MCP\go_computer_use_mcp_server\native\windows-amd64\go_computer_use_mcp_server-windows-amd64.exe
```

빌드에 사용한 구성:

- Go: `GoLang.Go`
- MSYS2: `MSYS2.MSYS2`
- GCC: `mingw-w64-x86_64-gcc`

재빌드가 필요하면:

```powershell
cd C:\Users\petbl\MCP\go_computer_use_mcp_server
$env:Path = "C:\msys64\mingw64\bin;C:\Program Files\Go\bin;" + $env:Path
$env:CGO_ENABLED = "1"
$env:GOOS = "windows"
$env:GOARCH = "amd64"
go build -ldflags "-s -w -X main.ServerVersion=1.1.4" -o "native\windows-amd64\go_computer_use_mcp_server-windows-amd64.exe" .
```

켤 때는 `disabled`를 `false`로 바꾸되, `autoApprove`는 계속 비워둔다.

## 최종 운영 원칙

Qwen3.5가 말을 잘 안 들을 때는 도구를 많이 주는 것보다 역할을 좁히는 게 낫다.

- 일상 웹 작업: `playwright`
- Playwright 실패/복잡한 탐색: `browser-use`
- PC 전체 조작: `computer-use`, 기본 비활성화

이 순서로 고정하면 "명령은 했는데 모델이 대충 답하는 문제"를 줄일 수 있다.
