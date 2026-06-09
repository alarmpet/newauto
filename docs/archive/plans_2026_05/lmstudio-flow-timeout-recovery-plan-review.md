# Flow 생성 실패 원인 분석 및 해결 계획서 — 코드베이스 기반 검증 의견

> 분석 기준일: 2026-05-07  
> 대상 문서: `lmstudio-flow-generation-timeout-recovery-plan.md`  
> 분석 범위: 계획서 + `newauto_mcp.py`, `flow_desktop_control.py`, `flow.py` 라우터, `flow_browser_automation.py` 교차 검증

---

## 1. 전체 평가

계획서의 원인 분석 5가지는 **모두 코드에서 실제로 확인된다**. 특히 이미 반영된 수정들(한글/영문 프롬프트 분리, stale fallback 제거, 그리드 결과 카드 클릭 순서, `attach-renamed` 엔드포인트 추가)이 코드에 구현되어 있음을 확인했다.

그러나 **계획서가 "남은 구조 문제"로 분류한 항목들이 아직 코드에 반영되지 않았고**, 그 중 일부는 계획서의 설계 자체에도 추가 문제가 있다.

---

## 2. 이미 반영된 수정 항목 — 검증 결과

### ✅ 반영 확인: 환경 변수 기반 backend 분기

```python
# newauto_mcp.py:38-42
def _flow_backend() -> FlowAutomationBackend:
    raw_backend = os.environ.get("FLOW_AUTOMATION_BACKEND", "uivision").strip().lower()
    if raw_backend in {"uivision", "playwright", "assisted"}:
        return cast(FlowAutomationBackend, raw_backend)
    return "uivision"
```

기본값이 `"uivision"`으로 설정되어 있다. 계획서의 backend 분리 권장이 반영된 상태다.

### ✅ 반영 확인: `attach-renamed` 엔드포인트

`flow.py`에 `POST /api/flow/assets/{pid}/attach-renamed`가 구현되어 있고, `flow_sNNN_` 파일명 패턴 파싱이 정확하게 동작한다:

```python
# flow.py:368
sentence_idx = _renamed_sentence_idx(source_path.name)
```

파일명 기반 매핑이 실제로 구현되어 있으므로, **이전 분석 의견서에서 제기했던 "다운로드 순서 꼬임" 위험은 이미 해결된 상태**다.

### ✅ 반영 확인: MCP instructions 모드별 분기

```python
# newauto_mcp.py:52-70
def _mcp_instructions() -> str:
    mode = _flow_mode()
```

`FLOW_MODE` 환경 변수로 instructions를 다르게 생성하는 구조가 이미 구현되어 있다.

### ✅ 반영 확인: `_run_flow_desktop_control()` — 하지만 timeout 문제 그대로

```python
# newauto_mcp.py:407-434
def _run_flow_desktop_control(project_id, sentence_number, *, wait_seconds=62):
    ...
    completed = subprocess.run(
        command,
        timeout=max(90, wait_seconds + 35),  # ← 최대 97초
        ...
    )
```

`wait_seconds=62` 기본값으로 timeout은 최대 `62 + 35 = 97초`. MCP tool call의 기본 timeout이 보통 60~120초이므로, **LM Studio client에서 먼저 timeout이 날 수 있는 구간**이다.

---

## 3. 미구현 항목 — 코드 검증

### ❌ 미구현: `flow_wait_sentence` 상태

계획서 Phase 1과 2의 핵심인 "생성 클릭만 하고 즉시 반환 → 다음 `진행`에서 다운로드/attach"가 **현재 코드에 없다**.

현재 `flow_generate` 단계의 실제 흐름:

```python
# newauto_mcp.py:750-782
sentence_number = missing[0]
try:
    output = _run_flow_desktop_control(pid, sentence_number)  # ← 생성+다운로드+attach를 한 번에!
except NewautoError as exc:
    return "4단계 중단..."
```

`_run_flow_desktop_control()`은 `flow_desktop_control.py`의 `generate_one()`을 호출하며, 이 함수가 **프롬프트 입력 → Generate 클릭 → `wait_seconds`초 대기 → 다운로드 감지 → attach API 호출**을 모두 한 번에 수행한다. 즉, 계획서가 요구하는 2단계 분리가 전혀 되어 있지 않다.

> [!WARNING]
> 계획서의 `flow_wait_sentence` 상태는 구현이 안 된 상태다. `continue_stepwise_hpsl_video_workflow()`에서 `next_step == "flow_wait_sentence"` 분기가 없다. 이것이 현재 timeout의 직접 원인이다.

---

## 4. 추가 발견된 코드 문제

### 4.1 `flow_desktop_control.py`의 좌표 하드코딩 — 가장 취약한 지점

```python
# flow_desktop_control.py:86-99
pyautogui.click(360, 815)   # 입력창 클릭
pyautogui.hotkey("ctrl", "a")
pyautogui.hotkey("ctrl", "v")
pyautogui.click(895, 854)   # Generate 버튼
time.sleep(wait_seconds)    # 62초 고정 대기
pyautogui.press("esc")
pyautogui.click(225, 420)   # 결과 카드 클릭
pyautogui.click(987, 181)   # 더보기 메뉴
pyautogui.click(874, 223)   # 다운로드
time.sleep(8)               # 8초 대기
```

이 좌표들은 특정 모니터 해상도/DPI/Flow 화면 레이아웃을 가정한다. 계획서는 이 취약성을 인식하고 있으나, 해결 방안이 "올바른 좌표를 누른다"고만 되어 있다.

> [!CAUTION]
> 현재 코드에는 클릭 전 **화면 상태 확인 로직이 전혀 없다**. `_flow_window_title()`로 Chrome 창을 찾은 뒤 바로 좌표를 클릭한다. 계획서 Phase 3에서 "화면 상태별 복구"를 권장하지만 구현되지 않았다.
>
> 실제 실패 시나리오: Flow 창이 다른 화면에 있거나, 이미 메뉴가 열려있거나, 생성 중 팝업이 뜬 경우에도 좌표 클릭이 그대로 진행되어 **엉뚱한 위치를 클릭**한다.

**구체적 개선 필요 사항**:

1. **클릭 전 스크린샷 기반 상태 확인**: `pyautogui.screenshot()`으로 Flow 입력창 영역을 확인
2. **클릭 성공 여부 확인**: 클릭 후 `time.sleep(0.5)` → 해당 영역 색상/이미지 검증
3. **생성 완료 감지**: 62초 고정 대기 → 결과 카드 영역의 변화를 폴링으로 감지 (0.5초 간격)

---

### 4.2 `_newest_generated_download()`의 잠재적 경쟁 조건

```python
# flow_desktop_control.py:53-59
def _newest_generated_download(previous_names: set[str]) -> Path:
    allowed_suffixes = {".jpeg", ".jpg", ".png", ".webp", ".mp4"}
    recent = sorted(DOWNLOADS.glob("*"), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in recent:
        if path.name not in previous_names and path.is_file() and path.suffix.lower() in allowed_suffixes:
            return path
    raise RuntimeError("No generated Flow download was found.")
```

이 함수는 **다운로드 완료 여부를 확인하지 않는다**. `.crdownload` 확장자 필터링이 없어, Chrome이 아직 다운로드 중인 파일(`xxx.crdownload`의 실제 대상 파일)이 완료 전에 감지될 수 있다.

또한 8초 `time.sleep(8)` 이후 호출되는데, 네트워크 속도에 따라 8초 안에 다운로드가 완료되지 않을 수 있다.

> [!WARNING]
> `_latest_flow_asset_paths()`(`newauto_mcp.py`)에는 `.crdownload` 필터가 있는데, `_newest_generated_download()`(`flow_desktop_control.py`)에는 없다. 일관성 부재다.

**개선 코드**:
```python
def _newest_generated_download(previous_names: set[str], *, timeout: int = 30) -> Path:
    allowed_suffixes = {".jpeg", ".jpg", ".png", ".webp", ".mp4"}
    deadline = time.time() + timeout
    while time.time() < deadline:
        recent = sorted(DOWNLOADS.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
        for path in recent:
            if (path.name not in previous_names
                and path.is_file()
                and path.suffix.lower() in allowed_suffixes
                and not path.name.endswith(".crdownload")
                and not (DOWNLOADS / (path.name + ".crdownload")).exists()):
                return path
        time.sleep(1.0)
    raise RuntimeError("No generated Flow download was found within timeout.")
```

---

### 4.3 `generate_one()`의 attach API 실패 시 예외 미처리

```python
# flow_desktop_control.py:101-103
asset_path = _newest_generated_download(previous_names)
attached = _attach_asset(api_base, project_id, sentence_number, asset_path)
print(f"sentence={sentence_number} downloaded={asset_path} attached={attached}")
```

`_attach_asset()`이 실패하면 (`urllib.error.URLError`, `json.JSONDecodeError` 등) 예외가 그대로 전파되어 `_run_flow_desktop_control()`이 `NewautoError`를 발생시킨다. 이때 **이미 다운로드된 파일은 사라지지 않지만**, stepwise 상태는 여전히 `flow_generate`로 남아 있어 다음 `진행`에서 **같은 문장을 다시 생성하려 시도**한다.

즉, 다운로드는 성공했지만 attach만 실패했을 때, 이미 존재하는 다운로드 파일을 재사용하지 못하고 Flow 이미지를 다시 생성한다. 불필요한 크레딧 소모다.

**개선 방향**: attach 실패 시 `storage/projects/{pid}/uivision/pending_attach_{sentence_number}.json`에 `asset_path`를 저장하고, 다음 호출에서 이 파일이 있으면 생성 없이 attach만 재시도.

---

### 4.4 MCP `flow_generate` → 데스크톱 제어 timeout 계산 오류

```python
# newauto_mcp.py:425
timeout=max(90, wait_seconds + 35),  # wait_seconds=62이면 timeout=97초
```

이 timeout은 MCP tool call의 timeout보다 길 수 있다. LM Studio의 MCP tool call timeout이 기본 60초이면, Python subprocess가 실행되는 도중 LM Studio가 먼저 포기하고 error를 반환한다. 이때 `subprocess.run()`은 백그라운드에서 계속 실행 중인데 MCP는 이미 실패로 보고한다.

> [!CAUTION]
> Python subprocess가 독립 프로세스로 실행되는 동안 MCP client가 timeout되면, **desktop_control 프로세스는 Flow 화면을 조작하면서 MCP는 "실패"를 반환하는 경쟁 상태**가 발생한다. 다음 `진행`에서 MCP가 다시 `_run_flow_desktop_control()`을 호출하면 Flow 창에 두 번 클릭하는 상황이 된다.

**구조적 해결책** (계획서 Phase 1 구현 필수):

```python
# newauto_mcp.py의 flow_generate 단계에서
if next_step == "flow_generate":
    # 1. 프롬프트 입력 + Generate 클릭만 (30초 이내)
    output = _click_generate_only(pid, sentence_number)  # NEW: 클릭만 하고 즉시 반환
    updated = dict(state)
    updated["next_step"] = "flow_wait_sentence"
    updated["active_sentence_number"] = sentence_number
    updated["flow_generate_started_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    updated["downloads_before"] = list(_recent_download_names())
    _save_stepwise_state(updated)
    return f"문장 {sentence_number}번 생성 시작했어. Flow에서 이미지가 보이면 `진행`이라고 말해줘."

if next_step == "flow_wait_sentence":
    # 2. 다운로드 + attach만 (30초 이내)
    sentence_number = int(state.get("active_sentence_number") or 1)
    downloads_before = set(state.get("downloads_before") or [])
    ...
```

이렇게 하면 각 MCP 호출이 최대 30초 내에 반환되므로 timeout을 회피할 수 있다.

---

### 4.5 `_flow_window_title()` — "Flow"와 "Chrome" 동시 요구

```python
# flow_desktop_control.py:20-28
def _flow_window_title() -> str:
    for window in gw.getAllWindows():
        title = str(window.title)
        if "Flow" in title and "Chrome" in title:
```

Flow URL을 Edge에서 열면 "Chrome"이 제목에 포함되지 않아 탐지 실패한다. 계획서의 기존 수정에서 "Chrome" 창을 기준으로 바꿨다고 언급하지만, Edge 사용자나 Chrome 탭 제목이 변경된 경우에는 실패한다.

**개선 코드**:
```python
if "Flow" in title and ("Chrome" in title or "Edge" in title or "Chromium" in title):
```

또는 더 안전하게:
```python
if "labs.google" in title.lower() or ("flow" in title.lower() and any(b in title for b in ["Chrome", "Edge", "Chromium"])):
```

---

## 5. 계획서 Phase 설계 보완 의견

### Phase 1 설계 — "클릭만 하고 즉시 반환"의 분리 범위

계획서는 `flow_desktop_control.py`를 2개의 함수로 분리하도록 암시하지만, 명시하지 않았다. 구체적으로:

| 함수 | 책임 | 최대 실행 시간 |
|------|------|--------------|
| `click_generate(pid, sentence_number)` | 프롬프트 복사 → 입력창 클릭 → Ctrl+V → Generate 클릭 → 즉시 반환 | ~10초 |
| `download_and_attach(pid, sentence_number, downloads_before, timeout)` | 새 파일 폴링 → 다운로드 완료 확인 → attach API 호출 | ~30초 |

이렇게 분리하면 `_run_flow_desktop_control()`도 두 가지 `mode` 파라미터를 받도록 수정:
```python
_run_flow_desktop_control(pid, sentence_number, mode="click")    # 클릭만
_run_flow_desktop_control(pid, sentence_number, mode="download") # 다운로드+attach
```

### Phase 2 설계 — 상태 파일 필드 추가

계획서의 `downloads_before` 필드 개념은 올바르다. 실제 구현 시 `set` → JSON `list` 변환에 주의:

```json
{
  "next_step": "flow_wait_sentence",
  "active_sentence_number": 2,
  "flow_generate_started_at": "2026-05-07T02:10:00",
  "downloads_before": ["file1.jpg", "file2.png"]
}
```

`_save_stepwise_state()`는 이미 `json.dumps()`를 사용하므로, `set`을 직접 넣으면 직렬화 오류가 난다. 반드시 `list()`로 변환 후 저장.

### Phase 3 설계 — 화면 상태별 복구

계획서의 복구 순서(Esc → 입력 → 클릭 → 카드 열기 → 다운로드 → 1K)는 방향이 맞다. 그러나 실제 구현에서는:

1. **Esc 이후 화면이 여전히 상세 화면이면** 다시 Esc를 눌러야 함 → 단순 `press("esc"); sleep(0.3)`만으로 부족
2. **결과 카드 좌표 `(225, 420)`은 첫 번째 카드가 항상 그 위치에 있다고 가정** → Flow에서 이전 결과가 많으면 그리드 위치가 달라짐

**개선**: 좌표 대신 화면 최상단에서 아래로 스캔하며 결과 카드 이미지를 `pyautogui.locateOnScreen()`으로 찾는 방식을 `pyautogui.click(225, 420)` 폴백과 병행해야 한다.

---

## 6. 테스트 기준 보완

계획서의 테스트 기준 6가지에 다음을 추가한다:

| 추가 기준 | 검증 방법 |
|-----------|---------|
| 7. MCP tool call이 30초 이내에 반환되어야 함 | LM Studio logs에서 tool call duration 확인 |
| 8. `flow_wait_sentence` 상태에서 `진행` 시 프롬프트 재입력 없이 다운로드만 수행 | `flow_desktop_control.py` 호출 로그 확인 |
| 9. 다운로드 완료 전 파일 감지 방지 | `.crdownload` 동반 파일 존재 여부 검사 |
| 10. attach API 실패 시 pending 파일 저장 및 재시도 | `pending_attach_{N}.json` 존재 여부 확인 |
| 11. Edge 브라우저에서도 Flow 창 탐지 성공 | `gw.getAllWindows()` 결과 출력 확인 |

---

## 7. 즉시 작업 우선순위 재정렬

계획서의 즉시 작업 목록을 코드 상태 기반으로 재정렬한다:

| 우선순위 | 항목 | 이유 |
|---------|------|------|
| 🔴 1 | `flow_generate` 단계를 "클릭만" → `flow_wait_sentence`로 분리 | timeout의 직접 원인. 미구현 |
| 🔴 2 | `_newest_generated_download()`에 `.crdownload` 필터 + 폴링 추가 | 잘못된 파일 첨부 방지 |
| 🟡 3 | attach 실패 시 `pending_attach_{N}.json` 저장 | 크레딧 낭비 방지 |
| 🟡 4 | `_flow_window_title()`에 Edge/Chromium 지원 추가 | Edge 사용 시 즉시 실패 방지 |
| 🟢 5 | 좌표 클릭에 `pyautogui.locateOnScreen()` fallback 추가 | Flow UI 변경 대응 |
| 🟢 6 | `cb505a7a5358` 프로젝트로 1문장 왕복 테스트 | 계획서와 동일. Phase 1 완료 후 수행 |

---

## 8. 최종 권장 사항

1. **Phase 1을 가장 먼저 구현하라.** `flow_wait_sentence` 상태 분기 없이는 timeout 문제가 반복된다. 다른 개선들은 모두 이것 이후에 의미가 있다.
2. **`flow_desktop_control.py`를 두 함수(`click_generate` / `download_and_attach`)로 분리하라.** 단순히 state를 나누는 것만으로는 부족하다. 실제 subprocess 실행도 분리되어야 MCP call 단위가 안전해진다.
3. **`.crdownload` 필터와 폴링을 추가하라.** 8초 고정 대기는 언제든 실패할 수 있다.
4. **1문장 E2E를 계획서대로 `cb505a7a5358`로 먼저 검증하라.** Phase 1 구현 완료 즉시 테스트 기준 1~3번을 통과시키는 것이 최우선 목표다.

---

## 9. 2026-05-07 Direct Control Update Completed

- [x] Flow window selection now chooses the largest visible Flow Chrome/Edge/Chromium window, so stale loading windows are ignored.
- [x] Prompt input, Generate, download, and `1K` menu clicks now use coordinates relative to the active Flow window size.
- [x] Generate now returns from Flow detail URLs (`/edit/`, `/scene/`) to the project prompt view before typing the next prompt.
- [x] ASCII Flow prompts are typed directly; clipboard paste remains only as a non-ASCII fallback.
- [x] Download detection now baselines current Downloads files at the start of every wait step, preventing stale or mojibake filenames from being attached as new assets.
- [x] Verified on project `ad246c22458f` through the same function path LM Studio MCP uses:
  - sentence 1 download/attach succeeded;
  - sentence 2 initially exposed stale-file attachment, then succeeded after the baseline fix with a fresh Flow download.
- [x] Verification passed:
  - `python -m py_compile scripts\flow_desktop_control.py`
  - `python -m mypy scripts\flow_desktop_control.py`
  - `python -m pytest tests\test_flow_uivision.py`
