# OpenRouter Qwen/DeepSeek Free Migration Plan

작성일: 2026-05-12  
반영 리뷰: `openrouter-qwen-deepseek-migration-review-antigravity-2026-05-12.md`

## 0. 결론

현재 `newauto`의 OpenRouter subagent harness 기본 모델은 `openai/gpt-oss-20b:free`다. 이를 다음 정책으로 바꾼다.

```text
Primary:
google/gemma-4-31b-it:free

Fallback:
google/gemma-4-26b-a4b-it:free

Last resort:
openai/gpt-oss-20b:free
```

로컬 기본 operator는 계속 LM Studio의 `google/gemma-4-e4b`를 사용한다. OpenRouter는 메인 실행 모델이 아니라, 복잡한 원인 분석, 리뷰, 긴 로그 판단에만 쓰는 advisory subagent다.
`openai/gpt-oss-20b:free`는 제거하지 않고 마지막 fallback으로 유지한다. Google Gemma free endpoint가 혼잡하거나 계정 라우팅에서 막힐 때를 위한 안전망이다.

Antigravity 리뷰의 핵심 지적은 타당하다. 기존 계획은 방향은 맞지만 실제 코드와 문서가 아직 따라오지 않았다. 따라서 이번 계획은 모델명 교체뿐 아니라 fallback chain, budget attempt 기록, `.clinerules` 갱신, timeout/max token 정책, CLI 출력 버그 정리까지 포함한다.

## 0.1 진행 상태

- [x] P0 기본 모델 상수 교체
- [x] P1 모델 chain resolution 추가
- [x] P1 OpenRouter fallback wrapper 추가
- [x] P2 Budget attempt 기록 개선
- [x] P2 `.clinerules`, `prompts/model_profiles.md`, `run-newauto-stepwise-mcp.cmd` 갱신
- [x] P3 CLI 출력과 토큰 정책 정리
- [x] 기본 체인을 Gemma 4 31B free -> Gemma 4 26B A4B free -> gpt-oss free로 변경
- [x] 검증 명령 실행
- [x] `research.md` 및 `timeline.md` 업데이트
- [x] 커밋

검증 메모:

- `py_compile`, `mypy`, dry-run, non-free 거부 검증은 통과했다.
- 실제 OpenRouter smoke에서 Qwen primary와 DeepSeek fallback 모두 현재 계정/라우팅 기준 `No endpoints found`를 반환했다.
- fallback wrapper 자체는 Qwen 실패 후 DeepSeek를 1회 시도하는 것으로 확인됐다.
- `--list-models`에서는 현재 `openai/gpt-oss-20b:free`만 검색되어, Qwen/DeepSeek free endpoint 사용 가능 여부는 OpenRouter 계정/라우팅 상태 확인이 필요하다.
- Google Gemma free 모델을 발견한 뒤 기본 체인은 `google/gemma-4-31b-it:free` -> `google/gemma-4-26b-a4b-it:free` -> `openai/gpt-oss-20b:free`로 조정했다.
- 이전 last-resort fallback smoke는 `openai/gpt-oss-20b:free`까지 도달했지만, 해당 upstream provider가 temporary rate-limit을 반환했다.
- OpenRouter error detail의 `user_id`는 redaction 대상에 추가했다.
- `--list-models`에서 Gemma 31B free, Gemma 26B A4B free, gpt-oss 20B free가 모두 확인됐다.
- live smoke에서 Gemma 31B free는 temporary rate-limit이었고, Gemma 26B A4B free fallback이 성공했다.

## 1. 현재 상태

로컬 LM Studio:

- loaded model: `google/gemma-4-e4b`
- quantization: `Q4_K_M`
- loaded context: `72000`
- API URL: `http://127.0.0.1:1234`

OpenRouter harness:

- file: `scripts/openrouter_subagent_harness.py`
- current default: `DEFAULT_FREE_MODEL = "openai/gpt-oss-20b:free"`
- fallback model constant: 없음
- `resolve_model()`은 단일 모델만 반환
- `call_openrouter()`는 fallback 없이 1회 호출
- budget은 request count만 기록하고 모델별 attempt 기록 없음
- `main()`에 `if args.json_output or True:`가 있어 `--json-output` 플래그가 사실상 무의미함

문서/프롬프트:

- `.clinerules`에는 여전히 기본 모델을 `openai/gpt-oss-20b:free`로 안내하는 문구가 남아 있음
- `prompts/model_profiles.md`는 OpenRouter free model 정책은 있으나 primary/fallback 모델이 구체화되어 있지 않음

## 2. 반영 결정

Antigravity 리뷰에서 즉시 반영할 항목:

- `DEFAULT_FREE_MODEL`을 `google/gemma-4-31b-it:free`로 변경
- `DEFAULT_FALLBACK_FREE_MODEL = "google/gemma-4-26b-a4b-it:free"` 추가
- `resolve_model_chain()` 추가
- fallback 대상 오류 분류 추가
- fallback 시 실제 attempt 기준으로 budget 2회 소모 가능하게 기록
- `last_attempts` 기록 추가
- dry-run에서 primary/fallback chain 표시
- `.clinerules`의 `gpt-oss-20b` 안내 갱신
- `run-newauto-stepwise-mcp.cmd`에 OpenRouter 모델 env 기본값 추가
- mode별 `max_tokens` 분리
- `if args.json_output or True` 제거

이번 계획에서는 보류할 항목:

- `newauto_stepwise_mcp.py`에 `ask_openrouter_subagent` MCP 도구 추가
  - 이유: 모델 migration의 필수 조건은 아님. 먼저 CLI harness를 안정화한 뒤 P4로 분리한다.
- `agent_eval_smoke.py`에 OpenRouter 실제 API smoke 통합
  - 이유: 무료 quota를 쓰는 테스트는 opt-in이어야 한다. 이번에는 CLI smoke 명령으로 검증한다.
- filesystem MCP에서 `openrouter.txt`를 직접 exclude하는 설정 변경
  - 이유: 중요하지만 Cline 전역 설정 변경 성격이 강하다. 이번 계획에는 `.clinerules` 금지 문구와 harness deny path 유지까지 반영한다.

## 3. 목표 정책

모델 기본값:

```python
DEFAULT_FREE_MODEL = "google/gemma-4-31b-it:free"
DEFAULT_FALLBACK_FREE_MODEL = "google/gemma-4-26b-a4b-it:free"
DEFAULT_LAST_RESORT_FREE_MODEL = "openai/gpt-oss-20b:free"
```

모드별 모델:

| Mode | Primary | Fallback | Last Resort |
|---|---|---|---|
| `review` | `google/gemma-4-31b-it:free` | `google/gemma-4-26b-a4b-it:free` | `openai/gpt-oss-20b:free` |
| `debug` | `google/gemma-4-31b-it:free` | `google/gemma-4-26b-a4b-it:free` | `openai/gpt-oss-20b:free` |
| `plan` | `google/gemma-4-31b-it:free` | `google/gemma-4-26b-a4b-it:free` | `openai/gpt-oss-20b:free` |
| `code_patch` | `google/gemma-4-31b-it:free` | `google/gemma-4-26b-a4b-it:free` | `openai/gpt-oss-20b:free` |

모드별 max tokens:

| Mode | max_tokens |
|---|---:|
| `review` | 1500 |
| `debug` | 1500 |
| `plan` | 2000 |
| `code_patch` | 2500 |

Timeout 기본값:

- primary: 기본 `60`초
- fallback: 기본 `45`초
- CLI 옵션은 유지하되, 단일 `--timeout-sec`가 주어지면 primary/fallback 모두 같은 값으로 override한다.

## 4. 구현 계획

### P0. 기본 모델 상수 교체

대상: `scripts/openrouter_subagent_harness.py`

작업:

- `DEFAULT_FREE_MODEL`을 `google/gemma-4-31b-it:free`로 변경
- `DEFAULT_FALLBACK_FREE_MODEL` 추가
- `MODE_MAX_TOKENS` 추가

검증:

```powershell
Select-String -Path .\scripts\openrouter_subagent_harness.py -Pattern "DEFAULT_FREE_MODEL|DEFAULT_FALLBACK_FREE_MODEL"
```

### P1. 모델 chain resolution 추가

기존 `resolve_model()`은 호환성을 위해 유지한다. 새 함수 `resolve_model_chain()`을 추가한다.

우선순위:

```text
1. explicit --model
2. OPENROUTER_MODEL_<MODE>
3. OPENROUTER_MODEL
4. DEFAULT_FREE_MODEL
5. OPENROUTER_FALLBACK_MODEL
6. DEFAULT_FALLBACK_FREE_MODEL
7. OPENROUTER_LAST_RESORT_MODEL
8. DEFAULT_LAST_RESORT_FREE_MODEL
```

규칙:

- 모든 모델은 반드시 `:free`로 끝나야 한다.
- 중복 모델은 제거한다.
- `--model`이 지정되면 사용자의 명시 override로 보고 첫 번째 시도 모델이 된다.
- fallback 모델은 항상 마지막 후보로 둔다.

Dry-run 출력에는 다음을 포함한다.

```json
{
  "model": "google/gemma-4-31b-it:free",
  "model_chain": [
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "openai/gpt-oss-20b:free"
  ]
}
```

### P1. OpenRouter fallback wrapper 추가

`call_openrouter()` 자체는 단일 호출 함수로 유지한다. 그 위에 `call_openrouter_with_fallback()`을 추가한다.

fallback 대상:

- HTTP 408
- HTTP 409
- HTTP 429
- HTTP 500 이상
- timeout
- provider unavailable
- model unavailable
- 빈 응답
- JSON 파싱 불가

fallback하지 않는 오류:

- API key missing
- HTTP 401/403
- non-free model 거부
- budget hard stop
- denied path/context packing 문제
- secret redaction 관련 차단

fallback은 한 번만 수행한다. 두 모델 모두 실패하면 다음 정보를 반환한다.

```json
{
  "ok": false,
  "error": "all_models_failed",
  "attempts": [
    {
      "model": "google/gemma-4-31b-it:free",
      "ok": false,
      "error_class": "rate_limit",
      "error": "OpenRouter HTTP 429: ..."
    },
    {
      "model": "google/gemma-4-26b-a4b-it:free",
      "ok": false,
      "error_class": "timeout",
      "error": "timed out"
    }
  ]
}
```

오류 메시지는 기존 `_redact_text()`를 통과시키고, 각 detail은 최대 1000자로 제한한다.

### P2. Budget attempt 기록 개선

현재 `reserve_budget(mode, essential=...)`는 모델 정보를 모른다. 다음처럼 확장한다.

```python
reserve_budget(mode, model=model, essential=essential)
record_attempt(mode, model, ok, error_class)
```

정책:

- primary 호출 전 1회 reserve
- fallback 호출 전 추가 1회 reserve
- 실제 OpenRouter로 나간 시도 수와 로컬 budget count를 맞춘다
- fallback attempt가 mode budget에 막히면 fallback하지 않고 예산 오류로 종료한다

`openrouter_budget.json`에는 최근 attempt만 짧게 보존한다.

```json
{
  "last_attempts": [
    {
      "ts": 1778560000.0,
      "mode": "review",
      "model": "google/gemma-4-31b-it:free",
      "ok": false,
      "error_class": "rate_limit"
    }
  ]
}
```

보존 개수는 최근 20개로 제한한다.

### P2. 문서와 실행 환경 갱신

대상:

- `.clinerules`
- `prompts/model_profiles.md`
- `run-newauto-stepwise-mcp.cmd`
- 필요 시 `openrouter-lmstudio-cline-subagent-plan-2026-05-12.md`

`.clinerules` 반영 문구:

```text
If no OpenRouter model env var is configured, the harness defaults to google/gemma-4-31b-it:free, may fall back to google/gemma-4-26b-a4b-it:free, and keeps openai/gpt-oss-20b:free as the last-resort free fallback.
Never read or send openrouter.txt, API keys, tokens, cookies, browser profiles, credential files, full files, or full logs to OpenRouter.
```

`run-newauto-stepwise-mcp.cmd` 권장 추가:

```batch
set "OPENROUTER_MODEL_REVIEWER=google/gemma-4-31b-it:free"
set "OPENROUTER_MODEL_PLANNER=google/gemma-4-31b-it:free"
set "OPENROUTER_MODEL_DEBUGGER=google/gemma-4-31b-it:free"
set "OPENROUTER_MODEL_CODER=google/gemma-4-31b-it:free"
set "OPENROUTER_FALLBACK_MODEL=google/gemma-4-26b-a4b-it:free"
set "OPENROUTER_LAST_RESORT_MODEL=openai/gpt-oss-20b:free"
```

API key는 cmd에 넣지 않는다. 기존처럼 `OPENROUTER_API_KEY` 또는 `openrouter.txt` first line fallback을 사용한다.

### P3. CLI 출력과 토큰 정책 정리

작업:

- `if args.json_output or True`를 제거한다.
- 기본 출력은 사람이 읽기 쉬운 짧은 요약으로 바꾸거나, 현행 JSON 출력을 유지하려면 `--json-output` 플래그 설명을 정정한다.
- 자동화 안정성을 위해 권장안은 `--json-output` 기본 사용이다.
- `MODE_MAX_TOKENS`를 `call_openrouter()` payload에 반영한다.

권장 구현:

```python
max_tokens = MODE_MAX_TOKENS.get(mode, 1500)
```

`call_openrouter()`에 `mode` 또는 `max_tokens` 인자를 넘긴다.

## 5. 사용 규칙

OpenRouter 호출 조건:

- 같은 오류가 2회 이상 반복됨
- 로컬 Gemma4가 원인 분석을 확신하지 못함
- 긴 로그 tail을 보고 실패 지점을 좁혀야 함
- 계획서/리뷰/복구 순서를 외부 시각으로 한 번 점검해야 함
- Cline/Gemma4가 같은 shell/tool 호출을 반복하려 함

OpenRouter 비호출 조건:

- 단순 파일 검색
- 단일 syntax error
- 작은 코드 수정
- project_id, API key, cookie, login 상태처럼 민감하거나 로컬 상태 의존성이 큰 문제
- 전체 파일/전체 로그를 보내야만 이해 가능한 문제

## 6. 보안 규칙

- `openrouter.txt` 내용은 절대 prompt에 포함하지 않는다.
- API key, token, cookie, authorization header, browser profile, credential 파일은 전송하지 않는다.
- 전체 파일과 전체 로그를 보내지 않는다.
- 관련 코드 snippet과 필요한 로그 tail만 보낸다.
- OpenRouter 응답은 명령이 아니라 외부 의견으로 취급한다.
- 적용 전 반드시 로컬 코드 확인, 테스트, 또는 재현 명령으로 검증한다.
- OpenRouter 오류 detail도 `_redact_text()`를 통과시키고 길이를 제한한다.

## 7. 검증 계획

1. 상수 확인:

```powershell
Select-String -Path .\scripts\openrouter_subagent_harness.py -Pattern "DEFAULT_FREE_MODEL|DEFAULT_FALLBACK_FREE_MODEL|gpt-oss"
```

기대:

- `DEFAULT_FREE_MODEL = "google/gemma-4-31b-it:free"`
- `DEFAULT_FALLBACK_FREE_MODEL = "google/gemma-4-26b-a4b-it:free"`
- `openai/gpt-oss-20b:free`는 last-resort fallback으로 남음

2. Dry-run primary/fallback chain:

```powershell
python scripts\openrouter_subagent_harness.py --dry-run --mode review --task "smoke" --json-output
```

기대:

- packed context에 secret 없음
- model chain에 Qwen primary와 DeepSeek fallback 표시

3. Non-free 거부:

```powershell
python scripts\openrouter_subagent_harness.py --dry-run --mode review --model "google/gemma-4-31b-it" --task "smoke" --json-output
```

기대:

- non-free model 거부

4. 실제 review smoke:

```powershell
python scripts\openrouter_subagent_harness.py --mode review --task "Return one likely cause and one verification command for a fake timeout." --json-output
```

기대:

- `google/gemma-4-31b-it:free` 사용
- JSON response boundary 유지
- budget 1회 증가

5. Fallback smoke:

```powershell
$env:OPENROUTER_MODEL_REVIEWER="invalid/invalid-model:free"
python scripts\openrouter_subagent_harness.py --mode review --task "fallback smoke" --json-output
Remove-Item Env:\OPENROUTER_MODEL_REVIEWER
```

기대:

- primary 실패 기록
- fallback `google/gemma-4-26b-a4b-it:free` 1회 시도
- 성공 시 result model 또는 attempts에 fallback 모델 표시

6. Budget 상태:

```powershell
python scripts\openrouter_subagent_harness.py --budget-status
```

기대:

- `requests_today` 증가
- `last_attempts`에 모델별 attempt 기록
- secret 없음

7. `.clinerules` 확인:

```powershell
Select-String -Path .\.clinerules -Pattern "gpt-oss|gemma-4-31b|gemma-4-26b|openrouter.txt"
```

기대:

- `gpt-oss` 기본값 문구 제거
- Qwen/DeepSeek 정책 문구 존재
- `openrouter.txt` 전송 금지 문구 존재

## 8. 완료 기준

- `scripts/openrouter_subagent_harness.py` 기본 모델이 `google/gemma-4-31b-it:free`로 바뀐다.
- fallback 모델이 `google/gemma-4-26b-a4b-it:free`로 등록된다.
- last-resort fallback 모델이 `openai/gpt-oss-20b:free`로 유지된다.
- dry-run에서 primary/fallback chain이 확인된다.
- non-free 모델 거부가 유지된다.
- fallback 대상 오류에서 DeepSeek로 1회만 넘어간다.
- budget에 모델별 attempt가 기록된다.
- `.clinerules`와 `model_profiles.md`가 새 모델 정책을 안내한다.
- `openrouter.txt`와 credential 전송 금지 규칙이 문서에 명확히 남는다.
- 실제 review smoke가 JSON 응답을 받고, 적용 전 로컬 검증 원칙을 유지한다.

## 9. 후속 P4

이번 migration 이후 별도 계획으로 진행할 항목:

- `newauto_stepwise_mcp.py`에 `ask_openrouter_subagent` 고수준 MCP 도구 추가
- Cline/LM Studio에서 shell quoting 없이 OpenRouter review를 호출하는 경로 마련
- `agent_eval_smoke.py`에 opt-in OpenRouter smoke 추가
- filesystem MCP가 `openrouter.txt`를 읽지 못하도록 전역 설정 차원의 차단 검토
