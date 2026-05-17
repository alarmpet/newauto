# Cline + Qwen3.5 툴 협력/자체복구 계획서 종합 리뷰

> 작성자: Antigravity (Claude Opus 4.6 Thinking)
> 작성일: 2026-05-13
> 대상 문서: `docs/cline-qwen-tool-cooperation-recovery-plan.md`
> 교차 검증 문서: `docs/cline-qwen-browser-computer-use-plan.md`, `.clinerules`, `research.md`, `timeline.md`, 코드베이스
> 이전 리뷰: `openrouter-subagent-plan-review-antigravity-2026-05-12.md`, `cline-qwen35-render-recovery-plan-review-antigravity-2026-05-13.md`, `cline-agentic-performance-recovery-plan-2026-05-12.md`

---

## 0. 전체 평가 요약

이 계획서의 **핵심 방향은 올바르다**. 특히 다음 세 가지 판단이 좋다:

1. **Qwen3.5 = 실행자, Gemma 4 = 보조 분석가** 역할 분리가 명확하다
2. **실패 시 같은 행동 반복 금지** 원칙이 코드로 강제되는 구조를 지향한다
3. **상태 캡슐 → 외부 조언 → 로컬 검증** 3단계 복구 루프가 논리적으로 타당하다

그러나 **기존 코드베이스에 이미 구현된 인프라를 충분히 활용하지 못하고 있으며**, 보안/운영/통합 측면에서 보강이 필요하다.

| 영역 | 평가 | 점수 |
|------|------|------|
| 전체 아키텍처 방향 | Qwen3.5 실행자 + Gemma 4 보조 분리는 정확하다 | ★★★★★ |
| 기존 자산 활용 | 이미 구현된 harness, forensic, MCP 도구와의 연동이 빠져 있다 | ★★☆☆☆ |
| 보안 설계 | OpenRouter 키 보호는 있지만 content redaction, prompt injection 방어가 부족하다 | ★★★☆☆ |
| 모델 전략 | Gemma 4 후보는 합리적이지만 실제 운영 결과와의 정합성이 미흡하다 | ★★★☆☆ |
| 실행 구체성 | Custom Instructions가 명확하지만 코드 수준 강제가 부족하다 | ★★★☆☆ |
| 기존 문제 해결 기여도 | 현재 반복되는 실패 패턴(tts_wait, render 누락)에 대한 직접적 해법이 없다 | ★★☆☆☆ |

---

## 1. 기존 인프라와의 중복/충돌 분석

### 1.1 OpenRouter Harness가 이미 존재한다

계획서 §OpenRouter 호출 도구 구현안에서 PowerShell 스크립트와 별도 MCP 서버(`openrouter-gemma-helper`)를 새로 만들겠다고 했다. 그러나 **이미 다음이 운영 중이다**:

| 기존 자산 | 위치 | 상태 |
|-----------|------|------|
| OpenRouter subagent harness | `scripts/openrouter_subagent_harness.py` (35KB) | 운영 중, Gemma 31B/26B free chain 구현 완료 |
| MCP 내장 `ask_openrouter_subagent` | `scripts/newauto_stepwise_mcp.py` | 운영 중, in-process 호출 |
| Budget 관리 | harness `--budget-status`, 일일 1000회 제한 | 구현 완료 |
| Model fallback chain | Gemma 31B → Gemma 26B → gpt-oss-20b | timeline 2026-05-12에 검증 완료 |
| Context packer/redaction | `SECRET_RE` in `agent_eval_smoke.py` | 구현 완료 |
| `.clinerules` OpenRouter 규칙 | `.clinerules` §OpenRouter Subagent | 24줄 상세 규칙 존재 |

> [!IMPORTANT]
> 계획서의 PowerShell 스크립트 접근은 **기존 harness와 중복**이다. 새로 만들지 말고 `scripts/openrouter_subagent_harness.py`를 재사용해야 한다. 특히 shell에서 JSON 이스케이프가 깨지는 문제는 이미 `--task-stdin`과 `--task-file`로 해결되어 있다.

### 1.2 복구 루프가 이미 더 정교하게 구현되어 있다

계획서의 7단계 실행 루프(명령 분류 → 실행 → 실패 감지 → 상태 캡슐 → Gemma 4 호출 → 재실행 → 반복 제한)는 개념적으로 올바르지만, **`cline-agentic-performance-recovery-plan-2026-05-12.md`에서 이미 더 구체적인 구현이 되어 있다**:

| 계획서 제안 | 이미 구현된 대응물 |
|------------|-------------------|
| 같은 도구 2회 실패 → Gemma 4 호출 | `.clinerules` Mandatory Escalation: 2회 반복 시 `diagnose_runtime` 먼저 |
| 상태 캡슐 작성 | `forensic_diagnose`의 `critical_findings` + `recommended_actions` |
| Gemma 4 보조 호출 | `ask_openrouter_subagent(mode="debug")` |
| 반복 제한 | `continue_video_workflow` wait repeat guard (P2에서 상태 카운터로 구현 예정) |

> [!WARNING]
> 계획서가 기존 `.clinerules`의 `Mandatory Escalation` 섹션과 `Recovery Loop` 섹션을 참조하지 않고 독립적으로 Custom Instructions를 설계했기 때문에 **규칙 충돌**이 발생할 수 있다. 예: 계획서는 "Gemma 4 호출 3회 제한"이지만, `.clinerules`는 "같은 step 2회 반복 시 diagnose → forensic → repair → OpenRouter 순서"로 4단계 escalation을 정의하고 있다.

### 1.3 모델 식별자 불일치

| 계획서 추천 | 실제 운영 (timeline 기준) |
|------------|--------------------------|
| `google/gemma-4-26b-a4b-it:free` (기본) | `google/gemma-4-31b-it:free` (기본, 2026-05-12 확정) |
| `google/gemma-4-31b-it` (복잡한 추론용) | `google/gemma-4-26b-a4b-it:free` (fallback) |
| 유료 모델 사용 가능 | `:free` 모델만 사용 (`.clinerules` 강제) |

> [!TIP]
> Timeline 2026-05-12 기록에 따르면 실제 검증에서 Gemma 31B가 rate-limit될 때 Gemma 26B로 fallback하여 성공했다. **계획서의 기본 모델을 31B로 맞추고**, 유료 모델 언급을 제거해야 한다.

---

## 2. 현재 프로젝트의 진짜 병목과의 정합성

### 2.1 계획서가 해결하지 못하는 핵심 문제들

`timeline.md`, `research.md`, 그리고 이전 리뷰들을 교차 분석하면, 현재 newauto 파이프라인의 **실제 반복 실패 패턴**은 다음과 같다:

| 실패 패턴 | 빈도 | 계획서 해당 여부 |
|----------|------|-----------------|
| `tts_wait` 반복 (OmniVoice worker 정지) | 매우 높음 | ❌ 미해당 |
| `render` 단계 도달 후 typecheck 오판으로 중단 | 높음 | ❌ 미해당 |
| 미디어 경로 정규화 오류로 렌더 실패 | 중간 | ❌ 미해당 |
| Flow 브라우저 자동화 실패/타임아웃 | 중간 | ⚠️ 부분 해당 (playwright/browser-use) |
| OpenRouter rate limit → 에이전트 혼란 | 낮음 | ✅ 해당 |
| 웹 정보 검색 시 모델이 추측으로 답변 | 낮음 | ✅ 해당 |

> [!CAUTION]
> 계획서의 주요 가치(웹 검색 실행 강제, 브라우저 도구 계층화)는 **실제 운영에서 가장 빈번한 실패 패턴(TTS worker 정지, render 누락, 경로 오류)을 다루지 않는다**. 이 부분은 `cline-agentic-performance-recovery-plan-2026-05-12.md`와 `cline-qwen35-render-recovery-plan-2026-05-13.md`가 훨씬 정확하게 다루고 있다.

### 2.2 browser-use MCP의 현실적 리스크

계획서는 `playwright` → `browser-use` → `computer-use` 3단계를 제안한다. 그러나:

- **Browser-Use의 LLM 기반 추출/자율 에이전트 기능은 API 키가 필요**하다 (계획서 자체가 인정)
- Qwen3.5 9B Q4_K_M은 browser-use의 복잡한 multi-step 웹 탐색 지시를 정확히 생성하기 어려울 수 있다
- 현재 `newauto-stepwise` MCP에는 이미 `search_web`(DuckDuckGo HTML 기반, 무료)이 구현되어 있고, Playwright MCP가 별도로 등록되어 있다
- browser-use를 추가하면 Qwen3.5가 선택해야 할 도구 수가 증가하여 오히려 **도구 선택 정확도가 떨어질 수 있다**

> [!TIP]
> 현재 Qwen3.5 9B의 한계를 고려하면, browser-use를 즉시 추가하기보다 **기존 Playwright MCP + `search_web` 조합을 먼저 안정화**하는 것이 실용적이다. browser-use는 Qwen3.5가 기존 도구를 안정적으로 사용하게 된 후 P2로 추가하는 것을 권장한다.

---

## 3. 보안 분석

### 3.1 강점

- OpenRouter API 키를 MCP 서버 환경변수에만 두라는 지침은 올바르다
- `computer-use` 비활성화 정책과 점진적 활성화 프로토콜이 합리적이다
- 로그인/결제/삭제 시 사용자 확인 의무가 명시되어 있다

### 3.2 누락된 보안 항목

| 항목 | 현황 | 권장 |
|------|------|------|
| 상태 캡슐 내 secret redaction | 미언급 | `SECRET_RE` 패턴 적용 필수 (이미 `agent_eval_smoke.py`에 구현) |
| OpenRouter 응답 prompt injection | 미언급 | 응답을 `=== openrouter subagent response begin/end ===` boundary로 감싸야 함 (이미 `.clinerules`에 규칙 있음) |
| `openrouter.txt` fallback 읽기 | 계획서에서 자체 PowerShell 스크립트 제안 | `.gitignore` 포함 확인 필수. 현재 harness가 이미 안전하게 처리 중 |
| 브라우저 쿠키/세션 노출 | 미언급 | Playwright CDP 프로필 경로를 OpenRouter에 전달하면 안 됨 |

### 3.3 `openrouter.txt` 파일 확인

계획서에서 OpenRouter API 키가 필요하다고 했지만, 이미 `openrouter.txt`가 프로젝트 루트에 존재한다 (557 bytes). `.clinerules`에는 "Never read or send `openrouter.txt`"가 명시되어 있다. `.gitignore` 포함 여부를 반드시 확인해야 한다.

---

## 4. Cline Custom Instructions 개선 의견

### 4.1 계획서 원본 대비 기존 `.clinerules`와의 비교

계획서의 Custom Instructions(§Cline Custom Instructions 권장문)를 현재 `.clinerules`(274줄)와 비교하면:

| 계획서 제안 규칙 | `.clinerules` 대응 | 상태 |
|-----------------|-------------------|------|
| 웹 관련은 playwright 먼저 | §Source Collection & Article Reading | ✅ 이미 더 상세 |
| 2회 실패 시 browser-use 전환 | §Recovery Loop "2회 실패 시 접근 변경" | ⚠️ browser-use 아닌 escalation 기반 |
| 실패 상태 캡슐 작성 | §Mandatory Escalation + forensic_diagnose | ✅ 이미 코드 수준 구현 |
| OpenRouter 호출 3회 제한 | §OpenRouter Subagent "trivial 금지" + budget | ✅ 이미 budget 기반 |
| 로그인/결제 사용자 확인 | §Safety + §Flow/Browser Automation | ✅ 이미 존재 |
| computer-use 비활성화 | 계획서만 존재 | ⚠️ `.clinerules`에 미반영 |
| 최종 답변에 도구/결과/위험 보고 | §Completion Gate | ✅ 이미 더 상세 |

> [!IMPORTANT]
> 계획서의 Custom Instructions를 `.clinerules`에 **그대로 추가하면 기존 규칙과 중복/충돌**이 발생한다. 대신 기존 `.clinerules`에 **아직 없는 항목만 선별 추가**해야 한다:
> - `computer-use` 비활성화 정책 (§Computer-Use 활성화 정책)
> - browser-use fallback 규칙 (필요 시)

### 4.2 권장 `.clinerules` 추가 내용

```text
## Browser Tool Hierarchy
- Default web actions: use playwright MCP.
- If playwright fails twice or multi-step exploration is needed: use browser-use MCP (when available).
- computer-use MCP is disabled by default. Enable only when the user explicitly asks for PC screen control.
- Before using computer-use, always take a screenshot first without clicking.
- Click/input with computer-use requires explicit user approval.
```

---

## 5. 아키텍처 개선 권장사항

### 5.1 실행 루프를 코드 수준에서 강제해야 한다

계획서의 7단계 실행 루프는 훌륭한 설계이지만, **Cline의 Custom Instructions/System Prompt에만 의존하면 Qwen3.5가 무시할 수 있다**. `cline-agentic-performance-recovery-plan-2026-05-12.md`가 이 문제를 정확히 짚었다:

> "이 guard는 Cline의 지능에 맡기지 말고 MCP/core 코드에 상태 카운터로 넣어야 한다."

현재 `continue_video_workflow`에 wait repeat guard가 P2로 계획되어 있다. 이것이 계획서의 "반복 제한" 개념을 **코드로 실현하는 유일한 방법**이다.

### 5.2 상태 캡슐을 `forensic_diagnose`와 통합해야 한다

계획서의 상태 캡슐(TASK/CURRENT_GOAL/OBSERVED_STATE/TOOLS_TRIED/ERROR_OR_BLOCKER/CONSTRAINTS/QUESTION)은 좋은 구조이지만, `scripts/forensic_doctor.py`(22KB)가 이미 다음을 자동 생성한다:

- `critical_findings` (오류 코드형 진단)
- `recommended_actions` (다음 행동 추천)
- worker/process/artifact 상태 요약
- heartbeat age 계산

> [!TIP]
> 별도 상태 캡슐 포맷을 만들지 말고, `forensic_diagnose`의 JSON 출력을 **OpenRouter에 보낼 "local facts packet"으로 그대로 사용**하면 된다. `cline-agentic-performance-recovery-plan-2026-05-12.md` §P3에서 이미 이 패킷 구조를 정의했다.

### 5.3 모델 전략 통합

현재 프로젝트에는 3개의 모델 전략 문서가 존재한다:

1. `docs/cline-qwen-tool-cooperation-recovery-plan.md` → Gemma 4 26B 기본
2. `cline-agentic-performance-recovery-plan-2026-05-12.md` → Gemma 4 31B 기본
3. `prompts/model_profiles.md` → operator-fast / fallback-cloud 분리

**이 3개를 하나로 통합해야 한다.** 권장 최종 체인:

```text
1차: google/gemma-4-31b-it:free  (가장 강한 추론)
2차: google/gemma-4-26b-a4b-it:free  (31B rate limit 시)
3차: openai/gpt-oss-20b:free  (Google 전체 불안정 시)
```

유료 모델은 사용하지 않는다 (`.clinerules` 강제).

---

## 6. `docs/cline-qwen-browser-computer-use-plan.md`와의 관계

이 문서는 같은 날짜(2026-05-13)에 작성된 **자매 문서**로, 브라우저 도구 설치/검증 상태를 정리한 것이다. 좋은 점:

- 구체적인 설치 경로와 검증 명령이 있다
- computer-use의 비활성화 이유와 활성화 조건이 합리적이다
- uv/browser-use 경로가 명시되어 있다

개선이 필요한 점:

- **계획서 본문과 설치 상태 문서가 분리**되어 있어, 두 문서 사이에 불일치가 생길 수 있다
- browser-use CLI 실행은 확인했지만 **실제 Cline MCP로의 등록과 Qwen3.5의 도구 호출 성공 여부**는 미검증이다

---

## 7. `research.md`와 `timeline.md`에서 발견한 추가 이슈

### 7.1 인코딩 손상 항목

`timeline.md`의 다수 항목이 한글 인코딩 손상(mojibake) 상태이다 (예: line 25~50 대부분). `.clinerules`에 이미 다음 규칙이 있다:

> "Do not rely on encoding-damaged timeline/research entries as primary evidence."

이 규칙은 올바르지만, **손상된 항목 자체를 정리하거나 UTF-8로 복구하는 작업**이 장기 과제로 남아 있다.

### 7.2 research.md 크기 문제

`research.md`는 현재 **222KB, 3605줄**이다. 이는 Qwen3.5 9B의 72K context에서 전체를 참조하기 불가능한 크기이다. 계획서에서도 이 문제를 다루지 않았다.

> [!TIP]
> `research.md`를 연도/월별로 분리하거나, 최근 2주 항목만 active research로 유지하고 나머지를 archive로 이동하는 것을 권장한다.

### 7.3 `final_verification.ps1` 오용 패턴

`cline-qwen35-render-recovery-plan-2026-05-13.md`와 `cline-qwen35-render-recovery-plan-review-antigravity-2026-05-13.md`에서 이미 진단했듯이, **에이전트가 워크플로우 실행 단계에서 리포지터리 건전성 검사 스크립트를 호출하는 패턴**이 반복되고 있다. 이 계획서에서도 이 문제에 대한 가드레일이 빠져 있다.

---

## 8. 종합 권장 조치

### 즉시 조치 (P0)

1. **계획서의 PowerShell 스크립트 구현을 중단**하고, 기존 `scripts/openrouter_subagent_harness.py`를 재사용한다
2. **모델 체인을 통합**: 31B → 26B → gpt-oss, `:free` 전용
3. **`.clinerules`에 computer-use 비활성화 정책**만 선별 추가한다 (나머지는 이미 존재)
4. 계획서의 상태 캡슐을 `forensic_diagnose` JSON 출력과 통합한다

### 단기 조치 (P1)

5. `docs/` 아래의 계획서 두 문서를 **하나로 통합**하거나, 역할을 명확히 분리한다 (설치 상태 vs. 운영 정책)
6. browser-use MCP 등록 후 **Qwen3.5의 실제 도구 호출 성공률을 측정**한다
7. 상태 캡슐 / OpenRouter 호출 시 `SECRET_RE` redaction과 response boundary를 적용한다
8. 기존 `cline-agentic-performance-recovery-plan-2026-05-12.md`의 P0~P4 진행 상태를 확인하고, 이 계획서와의 우선순위를 조정한다

### 장기 조치 (P2)

9. `research.md` 분리/아카이빙
10. `timeline.md` 인코딩 손상 항목 복구
11. browser-use LLM 기반 기능 평가 (API 키 필요)
12. computer-use 안전한 활성화 프로토콜 실제 테스트

---

## 9. 결론

이 계획서는 **Qwen3.5가 웹 작업에서 도구를 실제로 사용하게 만드는 방법론**으로서 가치가 있다. 특히 "역할을 좁히는 게 낫다"는 최종 원칙은 정확하다.

그러나 이 계획서가 독립적으로 기능하려면, **이미 약 3주간 구축된 인프라**(OpenRouter harness, forensic doctor, mandatory escalation, wait repeat guard)와의 통합이 필수적이다. 현재 상태로는 기존 시스템과 병행 운영 시 규칙 충돌과 중복 구현이 발생할 위험이 높다.

**가장 효과적인 다음 단계**는 이 계획서의 좋은 원칙(도구 계층화, 반복 금지, computer-use 비활성화)을 기존 `.clinerules`와 `cline-agentic-performance-recovery-plan-2026-05-12.md`에 **선별적으로 병합**하는 것이다. 별도의 새 시스템을 만드는 것이 아니라, 기존 시스템에 아직 없는 부분만 추가하는 접근이 실용적이다.

---

## 부록: 기존 인프라 빠른 참조

| 도구/파일 | 용도 | 경로 |
|-----------|------|------|
| OpenRouter harness | CLI/in-process OpenRouter 호출 | `scripts/openrouter_subagent_harness.py` |
| Forensic doctor | 자동 상태 진단/critical finding | `scripts/forensic_doctor.py` |
| Agent eval smoke | 에이전트 자체 점검 | `scripts/agent_eval_smoke.py` |
| MCP stepwise | LM Studio/Cline 워크플로우 허브 | `scripts/newauto_stepwise_mcp.py` |
| Agentic recovery plan | TTS/render/worker 복구 정책 | `cline-agentic-performance-recovery-plan-2026-05-12.md` |
| Render recovery plan | render 누락 복구 절차 | `cline-qwen35-render-recovery-plan-2026-05-13.md` |
| `.clinerules` | 에이전트 행동 규칙 (274줄) | `.clinerules` |
| Model profiles | 모델 역할 분리 정의 | `prompts/model_profiles.md` |
