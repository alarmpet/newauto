# Cline + Qwen3.5 Final Render Recovery Plan Review (Antigravity)

## 1. 개요 (Overview)

본 문서는 `cline-qwen35-render-recovery-plan-2026-05-13.md`, `research.md`, `timeline.md` 및 프로젝트 코드베이스(FastAPI 기반)의 검토 결과를 바탕으로 작성되었습니다. Qwen3.5 에이전트가 HPSL shorts 워크플로우의 마지막 렌더링 단계에서 실패한 원인을 진단하고, 제안된 복구 계획에 대한 개선 의견 및 코드베이스 반영 방향을 제시합니다.

## 2. 문제점 분석 (Problem Analysis)

1. **에이전트 판단 오류 (`final_verification.ps1` 실행)**
   - 워크플로우의 상태가 `next_step = "render"`임에도 불구하고, 에이전트가 렌더링 API를 호출하는 대신 저장소 전체 건전성 검사 스크립트인 `scripts/final_verification.ps1`을 실행했습니다.
   - 무관한 Python 타입 체크(mypy) 오류를 렌더링 실패의 원인으로 오판하여 파이프라인이 조기 종료되었습니다. 이는 에이전트의 역할과 워크플로우 진행 조건이 명확하게 분리되지 않았음을 의미합니다.

2. **미디어 경로 저장 불일치 (Path Normalization Issue)**
   - 렌더러(`app/services/render.py`)는 `media_dir / media["path"]` 방식으로 경로를 해석하여 미디어를 찾습니다.
   - 데이터베이스의 `media_order`, `body_image_mappings`, `scene_plan`, `render_plan` 등에 파일의 베어 네임(예: `flow_sentence_001.jpeg`) 대신 상대 경로(`media/...`)나 절대 경로가 저장되면, 렌더러 단계에서 존재하지 않는 중첩된 경로를 탐색하다가 실패하게 됩니다.
   - `app/routers/flow.py` 등을 확인한 결과, 내부 함수들은 기본적으로 베어 네임을 생성하고 있으나, 수동 업로드나 우회 경로를 통해 전체 경로가 삽입될 위험이 여전히 존재합니다.

## 3. 개선사항 및 코드 반영 의견 (Improvements & Code Recommendations)

제안된 Recovery Plan의 조치 사항들은 매우 타당하며, 추가적인 강건성(Robustness) 확보를 위해 다음과 같은 세부 개선을 권장합니다.

### 3.1. Path Normalizer의 전면 도입 (코드베이스 하드닝)
- `render_plan`, `scene_plan`, `media_order`를 읽거나 쓸 때 입력값이 무엇이든 베어 네임으로 정규화하는 헬퍼 함수를 추가해야 합니다.
- **적용 방안**:
  - `pathlib.Path(media_path).name`을 이용해 디렉토리 구조를 안전하게 제거하는 유틸리티 함수(예: `normalize_media_filename`)를 생성합니다.
  - `app/services/render.py`의 `_resolve_visual_segments` 부분에서 `media["path"]`를 사용할 때 `Path(media["path"]).name`으로 한 번 더 정규화하여 방어적으로 코딩합니다.
  - `app/routers/flow.py` 및 `app/routers/image_gen.py`에서 DB에 저장하기 전 필터링 로직을 추가합니다.

### 3.2. Render Preflight 검증 추가
- Recovery Plan에서 제안한 것처럼, 렌더링 대기열에 들어가기 직전에 미디어 경로와 파일 존재 여부를 명확히 체크하는 로직이 필요합니다.
- `app/services/render.py`의 메인 렌더 함수나 `app/services/preflight.py`에 다음 검증을 추가합니다:
  - 파일명이 `/`나 `\`를 포함하는지 확인하여 예외 발생.
  - 해당 파일이 `storage/projects/{pid}/media/` 하위에 실제로 존재하는지 확인, 누락 시 `Missing media for render: [filename]` 형태로 Fail Fast.

### 3.3. 에이전트 가드레일 강화 (`.clinerules` 및 워크플로우)
- `.clinerules` 또는 `newauto_stepwise_mcp` 시스템 프롬프트에 명시적인 행동 제약(Constraints)을 추가해야 합니다.
  - **제약 예시**: "단계가 `render`일 때는 절대 `final_verification.ps1`이나 타입 체크를 실행하지 마십시오. 즉시 렌더링 API(`/api/projects/{pid}/render`)를 호출하거나 해당되는 MCP 렌더 명령만 실행하고, `output.mp4`가 생성될 때까지 폴링하십시오."
- 타입 에러를 런타임/렌더 블로커로 인식하지 않도록 에이전트의 지침을 개선해야 합니다.

## 4. 결론 (Conclusion & Next Steps)

작성된 `cline-qwen35-render-recovery-plan-2026-05-13.md` 문서는 실패 원인을 정확히 짚어냈으며, 제시된 복구 절차도 올바릅니다.

1. **단기 조치**: 해당 프로젝트(`bf39e524191b`)의 DB 상태를 수동으로 수정하고 PowerShell 스크립트를 통해 렌더링을 큐잉하여 산출물(`output.mp4`)을 성공적으로 얻는 것이 최우선입니다.
2. **장기 조치 (코드 변경)**: 이후 자동화의 완결성을 위해 `app/services/render.py`와 `app/services/render_plan.py` 등에 Path Normalization을 구현하고 조기 실패(Fail Fast)를 위한 Preflight 로직을 반영해야 합니다.

해당 의견이 반영된 이 문서는 향후 코드 수정의 기획 지침으로 활용될 수 있습니다.
