# LM Studio MCP Reset And Minimal Stepwise Reconnect Plan - 검토 및 개선 의견

작성된 `lmstudio-mcp-reset-stepwise-plan.md`와 최신 코드베이스, `research.md`, `timeline.md`를 종합적으로 분석한 결과, **현재 발생하고 있는 "Gemma4의 도구 선택 혼란 및 타임아웃 임의 해석" 문제를 해결하기 위한 매우 적절하고 강력한 조치**입니다.

기존 `newauto-hpsl-flow` MCP에는 구형 도구(`make_hpsl_flow_short_video` 등)와 신형 도구가 혼재되어 있어, 파라미터가 적은 Gemma4-E4B 모델이 엉뚱한 도구를 호출하거나 문맥을 잃는 빈도가 높았습니다. 새 MCP 서버로 도구를 격리하고 노출을 최소화하는 접근은 모델의 환각(Hallucination)을 줄이는 가장 확실한 방법입니다.

다음은 계획서에 대한 추가 개선 의견과 구체적인 반영 사항입니다.

## 1. 개선 의견 및 반영 사항

### A. 도구 이름의 단순화 (Gemma4 인지 최적화)
Gemma4-E4B와 같은 소형 모델은 도구 이름이 지나치게 길거나 복잡하면 인지 오류를 일으킬 수 있습니다. 기존 `start_stepwise_hpsl_video_workflow` 대신, 새 MCP 서버에서는 도구 이름을 **직관적이고 짧게** 래핑(Wrapping)하는 것을 제안합니다.
* `start_stepwise_hpsl_video_workflow` -> `start_video_workflow`
* `continue_stepwise_hpsl_video_workflow` -> `continue_video_workflow`
* 이렇게 하면 모델이 도구를 호출할 때 오타나 Syntax Error를 낼 확률이 현저히 줄어듭니다.

### B. `diagnose_newauto_runtime`의 자동 복구 기능 강화
`diagnose_newauto_runtime` 호출 시, 파라미터로 `project_id`를 주지 않더라도 **자동으로 `storage/stepwise_workflows/latest.json`을 읽어 가장 최근 프로젝트의 ID와 상태를 반환**하도록 구현되어야 합니다.
이를 통해 LM Studio 채팅 컨텍스트가 초기화되거나 모델이 `project_id`를 잊어버린 경우에도 즉시 작업 문맥을 복구할 수 있습니다. (기존 로직이 이를 지원하므로, Docstring에 명시만 잘 해주면 됩니다.)

### C. MCP System Instructions (지시문) 보강
Gemma4가 사용자에게 반환하는 메시지 형식을 강제하기 위해 지시문에 다음 항목을 강조해야 합니다.
* "도구 호출 결과를 받으면, 절대 실패 원인을 지어내지(hallucinate) 마라."
* "응답은 항상 짧고 명확한 한국어로 요약하며, 다음 단계를 위해 사용자에게 `진행`이라고 입력하라고 안내하라."

### D. 이전 타임아웃 수정 사항과의 연계
바로 이전 작업(2026-05-07T16:40:07)에서 서버 `/health` 엔드포인트의 성능을 대폭 개선(응답 시간 10ms 이하로 캐싱)했습니다. 따라서 새 MCP(`newauto_stepwise_mcp.py`)에서 기존 모듈의 `_ensure_server()`를 그대로 재사용하더라도, 이전에 발생하던 구조적 타임아웃 문제는 더 이상 발생하지 않을 것입니다.

## 2. 세부 구현 가이드 (newauto_stepwise_mcp.py)

새로운 MCP 스크립트는 로직을 새로 작성하지 않고 기존 `scripts.newauto_mcp` 모듈을 Import하여 데코레이터만 붙이는 래퍼(Wrapper) 형태가 되어야 안정성이 보장됩니다.

```python
from mcp.server.fastmcp import FastMCP
import scripts.newauto_mcp as legacy_mcp

mcp = FastMCP(
    name="newauto-stepwise",
    instructions="[강화된 지시문 내용...]"
)

@mcp.tool()
def diagnose_runtime(project_id: str = "") -> str:
    return legacy_mcp.diagnose_newauto_runtime(project_id)

@mcp.tool()
def start_video_workflow(keyword_or_url: str, title: str = "", target_minutes: int = 1, tone: str = "설명형") -> str:
    return legacy_mcp.start_stepwise_hpsl_video_workflow(keyword_or_url, title, target_minutes, tone)

@mcp.tool()
def continue_video_workflow(project_id: str = "") -> str:
    return legacy_mcp.continue_stepwise_hpsl_video_workflow(project_id)
```

## 3. 결론

제안해주신 `lmstudio-mcp-reset-stepwise-plan.md`는 현재 상황에 대한 완벽한 처방입니다. 위에 제시한 **도구명 단순화** 및 **최근 프로젝트 자동 로드 명시** 등의 디테일만 추가 반영한다면, Gemma4 모델의 오작동을 원천 차단하고 안정적인 단계별 자동화 파이프라인을 구축할 수 있을 것입니다.
