# Ui.Vision Flow Automation Notes

이 폴더는 Google Flow 생성/다운로드를 Ui.Vision RPA로 반복하기 위한 로컬 작업 공간이다.

## 폴더 구조

```text
uivision/
  macros/   Ui.Vision macro JSON export 저장
  images/   이미지/OCR 앵커 저장
  csv/      필요 시 CSVRead용 복사본 저장
  logs/     수동 로그 또는 marker 백업 저장
```

newauto가 프로젝트별로 생성하는 실제 프롬프트 파일은 아래에 저장된다.

```text
storage/projects/{project_id}/uivision/
  flow_prompts.csv
  prompt_001.txt
  prompt_002.txt
  run_done.json
```

## 다운로드 파일명 규칙

Ui.Vision 매크로는 Flow 결과를 다운로드한 직후 파일명을 다음 형식으로 바꿔야 한다.

```text
flow_s001_20260507T010000.png
flow_s002_20260507T010130.png
```

`s001`은 1번 문장, `s002`는 2번 문장이다. newauto의 `attach_renamed_flow_downloads` 도구가 이 번호를 읽어 정확한 문장에 연결한다.

## XRun 성공 marker 예시

```powershell
powershell.exe -NoProfile -Command "@{status='done'; completed_at=(Get-Date -Format o)} | ConvertTo-Json | Set-Content 'C:\Users\petbl\newauto\storage\projects\PROJECT_ID\uivision\run_done.json' -Encoding UTF8"
```

## XRun 실패 marker 예시

```powershell
powershell.exe -NoProfile -Command "@{status='error'; message='Ui.Vision macro failed'} | ConvertTo-Json | Set-Content 'C:\Users\petbl\newauto\storage\projects\PROJECT_ID\uivision\run_done.json' -Encoding UTF8"
```

## 운영 원칙

- 처음에는 `Flow_Generate_One` 단건 매크로로 1문장만 검증한다.
- 1문장 생성, 다운로드, rename, attach, TTS, render가 통과한 뒤 `Flow_Generate_Batch`를 만든다.
- 매크로 실행 중에는 Flow 브라우저를 건드리지 않는다.
- 결제, 구독, 유료 크레딧 구매, 4K 업그레이드 버튼은 자동 클릭하지 않는다.
