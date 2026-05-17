# Flow RPA 대체 구조 계획서 분석 의견

> 분석 기준일: 2026-05-06  
> 대상 문서: `flow-rpa-alternative-plan.md`  
> 분석 범위: 계획서 + 현재 코드베이스(`newauto_mcp.py`, `flow_browser_automation.py`, `flow_prompting.py`, `flow.py` 라우터) 교차 검증

---

## 1. 전체 평가

계획서의 핵심 판단인 **"Playwright/CDP 방식의 불안정성을 인정하고 Ui.Vision RPA로 대체한다"**는 올바른 현실 인식이다. 특히 현재 `flow_browser_automation.py`의 코드를 보면 이 판단이 정확함을 확인할 수 있다:

- `_find_prompt_input()`는 `textarea`, `contenteditable`, `textbox`, `input[type=text]` 4가지를 순회 탐색
- `_find_generate_button()`는 6개 라벨 + 5개 aria-label + 마지막 visible button fallback으로 **17단계 탐색**
- `_open_new_project_if_present()`는 DOM evaluate + 3가지 locator 패턴으로 총 4단계 시도

이 코드가 이미 존재함에도 계속 흔들리고 있다면, 접근법 자체를 바꾸는 것이 맞다.

그러나 **계획서가 간과한 현실적 문제와 이미 구현된 코드와의 충돌이 다수 존재**한다.

---

## 2. 주요 문제점

### 2.1 이미 구현된 Playwright 워크플로우와의 공존 전략 부재

현재 `newauto_mcp.py`의 stepwise 워크플로우는 **Playwright 기반 자동화를 전제**로 설계되어 있다:

```
step flow_auth   → _run_flow_browser_script(["open", ...])
step flow_generate → _run_flow_browser_script(["generate", ...])
step flow_download → _run_flow_browser_script(["download", ...])
```

계획서는 이 3단계를 Ui.Vision으로 대체한다고 하면서도, **기존 stepwise 워크플로우 코드를 어떻게 수정/분기할지** 명시하지 않았다.

> [!WARNING]
> 현재 MCP instructions에 `automate_flow_generation`, `download_flow_results_from_browser` 등의 도구가 명시적으로 안내되어 있다. Ui.Vision으로 전환하면 이 MCP instructions 전체를 재작성해야 하고, 기존 도구들은 deprecated 처리가 필요하다. 계획서 리스크 4에서 "MCP 설명에서 Browser/Flow 직접 자동화 도구를 숨기거나 deprecated 처리"라고 한 줄만 언급했지만, 실제 수정 범위가 훨씬 크다.

**개선안**: `continue_stepwise_hpsl_video_workflow()`에서 `flow_auth`, `flow_generate`, `flow_download` 단계를 `visual_source_mode` 설정에 따라 분기하는 구조로 변경:
- `flow_playwright` → 기존 `_run_flow_browser_script()` 경로 유지
- `flow_uivision` → Ui.Vision 매크로 트리거 또는 안내 메시지
- `flow_assisted` → 사용자 수동 복사/붙여넣기 안내

---

### 2.2 다운로드 파일 ↔ 문장 매핑의 근본적 취약점

계획서의 Macro 4(6문장 일괄 반복)와 Phase 3(다운로드 감지/첨부)에서 가장 큰 위험은 **다운로드 파일이 어떤 문장의 결과인지 확신할 수 없다**는 것이다.

현재 `_latest_flow_asset_paths()`는 단순히 **수정 시각 기준 최신 파일 N개**를 가져온다:

```python
# newauto_mcp.py:266-281
candidates = [
    path for path in downloads_dir.iterdir()
    if path.is_file()
    and path.suffix.lower() in FLOW_ASSET_EXTENSIONS
    and path.stat().st_mtime >= cutoff
    and not path.name.endswith(".crdownload")
]
candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
```

그리고 `attach-local` API는 파일들을 **순서대로** sentence_idx에 매핑한다:

```python
# flow.py:142-143
for offset, raw_path in enumerate(payload.paths):
    sentence_idx = start_idx + offset
```

> [!CAUTION]
> 문제 시나리오: 사용자가 Ui.Vision batch 중 3번째 생성에서 실패 → 4,5,6번을 다시 시도 → Downloads에는 1,2,4,5,6번 결과가 시간순으로 있음 → `attach-local`은 이것을 1,2,3,4,5번으로 매핑 → **3번 문장에 4번 이미지가 붙음**

계획서의 리스크 3("다운로드 순서가 꼬임")에서 "timestamp 이후 최신 파일만 attach"라고 했지만, 이것만으로는 **생성 실패/재시도 시 순서 보장이 불가능**하다.

**개선안**:
1. Ui.Vision 매크로에서 **문장별로 다운로드 직후 파일명을 rename**하는 단계 추가 (`XRun`으로 PowerShell 호출)
2. 파일명 패턴: `flow_s{sentence_number:03d}_{timestamp}.{ext}`
3. `attach-local` API에 파일명 패턴 기반 sentence 매핑 모드 추가
4. 또는 Ui.Vision 매크로 1회 실행 = 1개 프롬프트 생성 + 1개 다운로드 + 즉시 attach API 호출 (일괄이 아닌 개별 처리)

---

### 2.3 Ui.Vision XRun ↔ newauto API 연동의 구체성 부족

계획서 Phase 2에서 `run_uivision_flow_macro(project_id, macro_name)` 함수를 추가한다고 했지만, **Ui.Vision XRun의 실제 동작 방식과의 갭**이 있다:

1. **XRun은 브라우저 확장 기반**이라 — Python에서 직접 호출하려면 `ui.vision://` 프로토콜 URL을 열거나 HTML autorun 파일을 여는 방식이 필요하다. 단순 subprocess 호출이 아니다.
2. **매크로 완료 감지** — XRun은 종료 코드를 반환하지 않는다. 계획서의 `run_done.json` marker 파일 방식이 유일한 현실적 방법이지만, **누가 이 marker를 생성하는지**가 불명확. Ui.Vision 매크로 내에서 `XRun` 으로 `echo done > run_done.json`을 실행해야 한다.
3. **에러 전파** — 매크로 실패 시 에러 정보를 어떻게 newauto에 전달할지.

**개선안**:
```text
Ui.Vision 매크로 마지막 단계:
  XRun | powershell.exe -NoProfile -Command "
    @{status='done'; completed_at=(Get-Date -Format o)} | ConvertTo-Json |
    Set-Content 'C:\Users\petbl\newauto\storage\projects\{pid}\uivision\run_done.json'
  "

Ui.Vision 매크로 에러 시:
  XRun | powershell.exe -NoProfile -Command "
    @{status='error'; message='${!LastError}'} | ConvertTo-Json |
    Set-Content 'C:\Users\petbl\newauto\storage\projects\{pid}\uivision\run_done.json'
  "
```

이 구체적인 XRun 명령 패턴을 계획서에 포함해야 한다.

---

### 2.4 계획서의 API 엔드포인트가 기존 구현과 중복

계획서 Phase 1에서 추가할 엔드포인트:
```
GET /api/flow/uivision/{project_id}/prompts.csv
GET /api/flow/uivision/{project_id}/prompt/{sentence_number}.txt
POST /api/flow/uivision/{project_id}/prepare
```

그런데 현재 이미 존재하는 엔드포인트:
```python
# flow.py 라우터
POST /api/flow/prompts/{pid}        # 프롬프트 생성
GET  /api/flow/prompts/{pid}        # 프롬프트 조회 (JSON)
GET  /api/flow/manifest/{pid}       # manifest 조회
POST /api/flow/assets/{pid}/attach-local  # 로컬 파일 첨부
POST /api/flow/assets/{pid}/{idx}   # 개별 파일 업로드
```

> [!IMPORTANT]
> `GET /api/flow/prompts/{pid}`가 이미 전체 manifest를 JSON으로 반환한다. CSV 변환은 이 JSON을 래핑하면 되므로 새 서비스가 아닌 **기존 라우터에 `Accept: text/csv` 헤더 분기 또는 query parameter `?format=csv`**로 추가하는 것이 깔끔하다.

**개선안**:
```python
# flow.py에 추가
@router.get("/prompts/{pid}/csv")
def get_flow_prompts_csv(pid: str) -> Response:
    manifest = get_flow_prompts(pid)
    # CSV 변환 로직
    return Response(content=csv_content, media_type="text/csv")

@router.get("/prompts/{pid}/sentence/{sentence_number}")
def get_single_prompt_text(pid: str, sentence_number: int) -> PlainTextResponse:
    manifest = get_flow_prompts(pid)
    # 해당 문장 프롬프트 텍스트 반환
```

별도의 `/uivision/` 경로를 만들기보다 기존 `/flow/` 하위에 포맷 옵션을 추가하는 것이 유지보수에 유리하다.

---

### 2.5 MCP instructions 비대화 위험

현재 MCP instructions가 이미 **20줄 이상의 복잡한 행동 규칙**을 포함하고 있다:

```python
# newauto_mcp.py:37-58
instructions=(
    "Use these tools when..."
    "HPSL always means Hook-Point-Story-Lesson..."
    "prefer start_stepwise_hpsl_video_workflow first..."
    "When the user says Flow downloads are done..."
    "If the user wants LM Studio/Gemma4 to operate Flow..."
    ...
)
```

계획서의 리스크 4 대응으로 "Ui.Vision 관련 도구만 우선 노출"이라고 했지만, 실제로는 **기존 Playwright 도구(6개)를 숨기고 Ui.Vision 도구(3~4개)를 추가하면서 instructions도 전면 재작성**해야 한다. Gemma4-e4b의 작은 컨텍스트에서 이 instructions가 길어지면 도구 선택 정확도가 떨어진다.

**개선안**: MCP instructions를 두 가지 프로필로 분리:
- `FLOW_MODE=playwright` → 기존 instructions
- `FLOW_MODE=uivision` → Ui.Vision 중심 instructions (Playwright 도구 미등록)

환경 변수로 선택하되, 전환 시 MCP 서버를 재시작.

---

### 2.6 Ui.Vision 이미지 OCR 의존의 한계

계획서 리스크 1 대응에서 "주변 텍스트와 함께 저장"과 "OCR 기반도 같이 사용"이라고 했지만, Ui.Vision의 OCR은:
- **한글 인식 정확도가 영어보다 낮다** — Flow UI의 "새 프로젝트", "다운로드" 등 한글 버튼
- **다크 모드/테마 변경 시 이미지 매칭 실패** — Flow가 다크 모드를 적용하면 버튼 이미지 전체 교체 필요
- **해상도/스케일링 의존** — Windows DPI 설정이 바뀌면 이미지 매칭이 깨짐

**개선안**:
1. 초기 매크로는 **좌표 기반이 아닌 이미지 매칭 + OCR 병행**으로 녹화
2. 매크로에 **confidence threshold**를 `0.7` 이상으로 설정하여 오탐 방지
3. Flow 테마는 **항상 라이트 모드**를 강제 (`?theme=light` URL 파라미터 또는 브라우저 설정)
4. 이미지 앵커를 `uivision/images/` 에 저장할 때 **다크/라이트 2벌**을 준비

---

## 3. 누락된 고려사항

### 3.1 Ui.Vision 무료 제한

Ui.Vision 무료 버전은:
- **매크로 실행 횟수 제한 없음** (오픈소스)
- 그러나 **XModules 무료 버전은 일부 기능 제한**이 있을 수 있음
- Hard-Drive Storage는 XModules가 필요하고, XModules는 별도 설치

계획서에 "무료 XModules"라고 적었지만, XModules의 **정확한 무료 범위**를 확인하고 명시해야 한다. 특히 `XRun`이 무료인지, 횟수 제한이 있는지.

### 3.2 Playwright 코드 유지보수 비용

Ui.Vision으로 전환하더라도, `flow_browser_automation.py` (476줄)과 `newauto_mcp.py`의 Playwright 관련 코드(약 200줄)를 **즉시 삭제할 것인지, 보존할 것인지** 결정이 필요하다.

**권장**: 삭제하지 말고 `FLOW_AUTOMATION_BACKEND` 환경 변수로 `playwright` / `uivision` / `assisted`를 선택하게 하여, Ui.Vision이 불안정할 때 Playwright로 롤백할 수 있도록 유지.

### 3.3 동시 실행 방지

현재 `gpu_guard.py`가 ComfyUI/TTS 간 GPU 점유를 관리하지만, Ui.Vision 매크로는 **브라우저 포커스를 점유**한다. 매크로 실행 중에 사용자가 브라우저를 사용하면 매크로가 깨진다.

계획서에 이에 대한 언급이 없다.

**개선안**: 
- Ui.Vision 매크로 실행 시 newauto UI에 "Flow 생성 중 — 브라우저 사용 금지" 배너 표시
- 또는 Ui.Vision의 `!statusOK` 명령으로 실패 감지 후 자동 재시도

### 3.4 Flow 생성 완료 대기 전략

계획서 Macro 2에서 "생성 완료까지 대기"라고만 적혀 있는데, **어떻게 완료를 감지하는지**가 핵심이다:

- Ui.Vision `WaitForVisible` + 결과 이미지 앵커?
- 타이머 기반 고정 대기?
- OCR로 "완료" 텍스트 감지?

Flow의 이미지 생성은 **10초~2분** 사이로 편차가 크다. 고정 타이머는 너무 짧으면 실패하고 너무 길면 낭비다.

**개선안**: Ui.Vision에서 `XWaitForVisible` + 결과 카드 이미지 앵커를 사용하되, timeout을 3분으로 설정. 결과 카드 앵커 이미지는 최소 2가지 (이미지 결과 / 비디오 결과) 준비.

---

## 4. 구현 순서 조정 제안

| 순서 | 계획서 원본 | 조정 제안 | 이유 |
|------|------------|-----------|------|
| 0 | - | **Ui.Vision + XModules 설치 및 무료 범위 확인** | 전제 조건 검증 |
| 1 | CSV/TXT 내보내기 | **기존 flow.py에 CSV/TXT 엔드포인트 추가** | 별도 서비스 불필요 |
| 2 | Ui.Vision 실행 안내 | **1문장 단위 매크로 녹화 + XRun marker 패턴 확립** | 일괄보다 단건이 먼저 |
| 3 | 다운로드 감지/첨부 | **파일명 rename + 문장 매핑 로직 추가** | 순서 꼬임 방지 핵심 |
| 4 | LM Studio UX | **MCP instructions 재작성 + Playwright deprecated 처리** | 도구 선택 혼란 방지 |
| 5 | 일괄 반복 | **6문장 batch는 단건 안정화 후에만** | 계획서와 동일 |

---

## 5. 긍정적 평가

1. **Playwright 집착을 버린 판단이 정확하다** — `flow_browser_automation.py`의 17단계 버튼 탐색 코드가 이미 한계를 증명한다.
2. **3가지 대안(Ui.Vision, Browser Use, Browser MCP) 비교가 체계적이다** — 각각의 근거와 한계를 명확히 정리했다.
3. **비용 0원 원칙 고수가 현실적이다** — Browser Use의 외부 API 의존성을 정확히 짚었다.
4. **단계형 UX(1개씩 수동 → 6개 일괄) 점진적 전환이 안전하다.**
5. **기존 `flow_prompting.py`와 `flow.py` 라우터가 이미 잘 구축되어 있다** — CSV/클립보드 내보내기만 추가하면 Ui.Vision 연동 기반이 완성된다.

---

## 6. 최종 권장 사항

1. **파일명 기반 문장 매핑** — 다운로드 순서 의존을 제거하라. Ui.Vision XRun으로 다운로드 즉시 rename 하는 것이 전체 파이프라인의 가장 취약한 지점을 해결한다.
2. **기존 Playwright 코드를 삭제하지 말라** — 환경 변수 기반 backend 선택으로 롤백 가능성을 유지하라.
3. **MCP instructions를 모드별로 분리하라** — Gemma4-e4b의 작은 컨텍스트에서 도구 17개와 긴 instructions는 판단 오류를 유발한다.
4. **Ui.Vision XModules 무료 범위를 설치 전에 확인하라** — XRun이 무료가 아니면 계획 전체가 흔들린다.
5. **1문장 단건 E2E를 먼저 증명하라** — 매크로 녹화 → 프롬프트 입력 → 생성 대기 → 다운로드 → rename → attach → TTS → render 전체를 1회 통과시킨 후에만 batch로 확장하라.
