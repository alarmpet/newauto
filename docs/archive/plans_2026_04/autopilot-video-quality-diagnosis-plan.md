# Autopilot 영상 품질 문제 진단 및 수정 계획서

작성일: 2026-04-28

대상 테스트 영상:

`C:\Users\petbl\newauto\storage\projects\289fe64eae1a\output.mp4`

참조해야 하는 기존 계획:

- `visual-relevance-recovery-plan.md`
- `tts-gender-mismatch-fix-plan.md`
- `capcut-omnivoice-enhancement-plan.md`
- `source-research-and-script-generation-plan.md`

## 2026-04-28 Implementation Update

- `Phase 1` 일부 완료:
  - autopilot 경로에서 `voice_preset=auto` / `mode=auto` / empty `instruct` 조합을 그대로 두지 않도록 보정 로직 추가
  - fallback preset은 `male-announcer-40s-50s`
  - autopilot default 적용 시 `mode=design`, non-empty `instruct`, `seed_mode=fixed`로 강제
  - manual TTS 경로의 기본 정책은 그대로 두고, autopilot 경로만 보정

- `Phase 2` 완료:
  - `app/services/source_draft.py`에 `sanitize_source_draft_script()` 추가
  - source draft 생성 직후 heading, label, bullet, leading stage direction cleanup 적용
  - source draft가 cleanup 후 비면 실패 처리

- `Phase 3` 일부 완료:
  - `ScenePlanScene`에 `key_concept`, `visual_metaphor`, `subject`, `props`, `background`, `avoid` optional field 추가
  - `build_scene_plan()`이 prompt suggestion의 `visual_brief` 정보를 scene plan에 보존하도록 확장
  - `scene_plan.version`을 `2`로 상향

- `Phase 4` 일부 완료:
  - `storage/visual_vocab/tech.json` 추가
  - browser, headless, JavaScript, V8, CDP, fingerprint, automation, scraping, security 계열 tech vocabulary 초기 세트 추가
  - `image_prompting.py`가 tech domain 문장에서 위 vocabulary를 우선 visual token으로 사용

- `Phase 5` 일부 완료:
  - `visual_brief.py`를 tech-aware하게 재정리
  - tech domain에서는 `clean software workspace`, `single centered stick figure engineer`, explainer-diagram action을 기본값으로 사용
  - `prompt_compiler.py`에 generic phrase blocklist 추가
  - `visual_relevance.py`가 `BLOCKLIST:` 기반 prompt violation을 `IMAGE_PROMPT_BLOCKLIST`로 감지

- 검증 완료:
  - `python -m pytest tests\\test_source_draft.py tests\\test_scene_plan.py tests\\test_autopilot_worker.py -q`
  - `python -m pytest tests\\test_tts_presets.py -q`
  - `python -m pytest tests\\test_visual_brief.py tests\\test_prompt_compiler.py tests\\test_image_prompting.py tests\\test_visual_relevance.py -q`
  - `powershell -ExecutionPolicy Bypass -File .\\scripts\\typecheck.ps1`

## 1. 정정된 결론

이번 영상의 문제는 두 갈래다.

1. 이미지 문제
   - 원인은 "키워드 테이블 인코딩 깨짐"이 아니다.
   - `visual-relevance-recovery-plan.md`에서 이미 정정된 것처럼, 진짜 원인은 keyword coverage 부족, 기술 도메인 어휘 부재, 그리고 generic fallback 문구다.
   - `visual_brief.py`, `prompt_compiler.py`, `scene_plan.py`, preflight relevance gate는 이미 존재한다. 따라서 새 visual planning 시스템을 만들면 안 되고, 기존 구조를 확장해야 한다.

2. 음성 문제
   - 원인은 seed_mode 하나가 아니다.
   - 핵심 원인은 autopilot 실행에서 `voice_preset=auto`, `mode=auto`, 빈 `instruct` 조합이 쓰인 것이다.
   - `seed_mode=fixed`는 보조 안정화 옵션일 뿐, 성별/음색 일관성의 핵심 해결책이 아니다.
   - 진짜 fix는 명시적 voice preset, `mode=design`, 비어 있지 않은 `instruct`를 autopilot 기본값으로 강제하는 것이다.

최종 방향:

- 이미지: 기존 `ScenePlan` / `VisualBrief` / `prompt_compiler` / relevance gate 위에 기술 도메인 확장을 추가한다.
- 음성: autopilot 기본 TTS 정책을 명시적 design preset으로 바꾸고, auto voice를 기본 경로에서 차단한다.
- 대본: source draft 직후 cleanup해서 자막, 음성, 미리보기가 같은 깨끗한 문장을 쓰게 한다.

## 2. 확인된 증거

### 2.1 이미지 프롬프트

확인 파일:

`storage\projects\289fe64eae1a\image_prompts_manifest.json`

확인된 문제:

- 기술 브라우저 설명 문장에 대해 `running fast`, `inside a simple room`, `under heavy rain`, `standing in front of a large door` 같은 무관한 fallback 장면이 생성됐다.
- 일부 프롬프트가 `holding one large clear symbol that represents the sentence keyword`처럼 핵심 개념이 비어 있는 일반 문구로 생성됐다.
- QA 프레임 기준으로 V8/JavaScript 브라우저 환경 설명 자막에 달리는 스틱맨 이미지가 매칭됐다.

판단:

ComfyUI가 문장을 잘못 이해한 것이 아니라, ComfyUI에 들어간 prompt 자체가 문장 핵심 개념과 맞지 않았다.

### 2.2 TTS 매니페스트

확인 파일:

`storage\projects\289fe64eae1a\tts\tts_run_manifest.json`

확인된 문제:

- `voice_preset`: `auto`
- `mode`: `auto`
- `instruct`: 비어 있음
- `seed_mode`: `per_sentence`
- 문장별 effective profile seed가 증가함

판단:

화자 성별과 음색이 흔들린 가장 큰 이유는 `auto` 모드와 빈 `instruct`다. `per_sentence` seed는 자연스러움/재현성에 영향을 주는 보조 원인이지만, 성별 일관성을 보장하거나 깨뜨리는 1순위 원인은 아니다.

## 3. 기존 구현 상태 반영

다음 기능은 이미 존재하거나 구현 완료 상태로 기록되어 있으므로 재구현하지 않는다.

- `app/services/visual_brief.py`
  - `VisualBrief` 생성
  - `mode`, `main_subject`, `action`, `primary_prop`, `scene`, `emotion`, `must_show`, `avoid`, `rationale` 구조

- `app/services/prompt_compiler.py`
  - `compile_positive_prompt()`
  - `compile_negative_prompt()`
  - `check_prompt_compliance()`

- `app/services/scene_plan.py`
  - `build_scene_plan()`
  - 기존 `ScenePlan` / `ScenePlanScene`

- render preflight relevance gate
  - prompt manifest와 sentence hash 기반 검증
  - `IMAGE_PROMPT_MUST_SHOW_MISSING` 류의 검증

따라서 이번 수정 계획은 신규 `visual_scene_plan.json`이나 별도 planner 시스템을 만들지 않는다. 기존 `scene_plan`을 확장한다.

## 4. 원인 분류

### 4.1 알고리즘/구조 문제

- 기술 도메인 문장에 대해 브라우저, V8, CDP, fingerprint, automation, data extraction 같은 핵심 개념을 visual prop으로 바꾸는 사전/규칙이 부족하다.
- keyword coverage가 낮아 fallback이 자주 발생한다.
- fallback 문구가 너무 일반적이라 문장 의미와 무관한 장면을 만든다.
- `ScenePlanScene`이 sentence의 핵심 개념, visual metaphor, subject, props, background, avoid를 구조적으로 보존하지 않는다.

### 4.2 기본값/policy 문제

- autopilot 기본 TTS가 `auto` voice로 흘러갈 수 있다.
- auto mode에서는 `instruct`가 비워져 OmniVoice가 기본 음성으로 생성할 수 있다.
- manual 모드와 autopilot 모드의 TTS 정책이 분리되어 있지 않다.
- 기술 콘텐츠에서도 Stickfigures LoRA를 무조건 쓰는 흐름이면 인터페이스/다이어그램 중심 장면과 충돌할 수 있다.

### 4.3 외부 의존성/운영 문제

- 60~120초 TTS는 `capcut-omnivoice-enhancement-plan.md`의 Windows `os error 1455` mitigation 상태와 연결된다.
- Brave 무료 사용량 숫자는 문서 간 1000/2000으로 충돌한다. 공식 한도와 현재 계정 플랜 기준으로 한 곳에서 통일해야 한다.
- Vision LLM 기반 QA는 비용과 시간이 크므로 V1 범위에 넣으면 전체 생성 시간이 과도하게 늘 수 있다.

## 5. 수정 계획

### Phase 1. Autopilot TTS 기본 정책 수정

목표:

영상 전체에서 같은 성별, 같은 화자 톤, 같은 voice design을 유지한다.

수정 방향:

- autopilot 기본 voice preset을 `auto`가 아닌 명시적 design preset으로 바꾼다.
- 기본 후보:
  - `male-announcer-40s-50s`
  - 또는 현재 canonical preset catalog에서 가장 안정적인 한국어 남성 design preset
- autopilot 기본 profile은 다음 조건을 만족해야 한다.
  - `voice_preset != "auto"`
  - `mode == "design"`
  - `instruct`가 비어 있지 않음
- `seed_mode`는 다음처럼 분리한다.
  - autopilot 기본: `fixed` 또는 안정화 preset의 권장값
  - manual 고급 설정: `per_sentence` 유지 가능
  - 사용자가 자연스러운 문장별 변화를 원할 때는 명시적으로 선택 가능
- preflight 또는 autopilot enqueue 단계에서 다음을 차단하거나 강한 경고로 표시한다.
  - `voice_preset=auto`
  - `mode=auto`
  - `instruct=""`

중요 정정:

- `seed_mode=fixed`만으로 성별/음색 일관성이 보장된다고 쓰지 않는다.
- 핵심은 preset + design mode + non-empty instruct다.

자동 검증:

- TTS manifest에서 `voice_preset != "auto"` 검증
- effective profile의 `mode == "design"` 검증
- effective profile의 `instruct`가 비어 있지 않은지 검증
- autopilot 경로에서는 seed 정책이 의도대로 적용됐는지 검증

대상 파일:

- `app/tts_profiles.py`
- `app/services/autopilot.py`
- `app/workers/tts_worker.py` 또는 manifest 생성부
- `tests/test_tts_presets.py`
- `tests/test_tts_pipeline.py`
- autopilot 관련 테스트

### Phase 2. Source draft 직후 대본 cleanup

목표:

자막, 음성, 이미지 프롬프트가 모두 같은 정제된 문장을 기준으로 작동하게 한다.

위치:

`app/services/source_draft.py`의 `generate_script_draft` 결과 직후.

이 위치를 선택하는 이유:

- source draft 직후에 정리하면 `user_script`, 미리보기, 자막, TTS, scene planning이 모두 같은 clean script를 쓴다.
- compile 직후에만 정리하면 `user_script`에는 마크다운이 남을 수 있다.
- TTS 입력 직전에만 정리하면 자막과 음성이 불일치할 수 있다.

제거 대상:

- `**내레이션:**`
- `#`, `##` 같은 heading
- bullet marker
- 괄호 속 제작 지시
- `장면:`, `이미지:`, `효과음:`, `화면:` 같은 제작 라벨

권장 구현:

- `sanitize_source_draft_script(text: str) -> str` 추가
- source draft 저장 전에 적용
- 사용자가 직접 입력한 script에는 자동 적용하지 않거나, autopilot source mode에서만 적용

자동 검증:

- clean script에 markdown heading이 없어야 한다.
- clean script에 제작 라벨이 없어야 한다.
- TTS timings와 subtitles가 같은 clean sentence를 써야 한다.

대상 파일:

- `app/services/source_draft.py`
- `app/services/script_compile.py`
- `tests/test_source_draft.py`
- `tests/test_script_compile.py`

### Phase 3. 기존 ScenePlanScene 확장

목표:

별도 `visual_scene_plan.json`을 만들지 않고, 기존 `scene_plan` 안에 장면 의미 정보를 보존한다.

수정 방향:

`app/types.py`의 `ScenePlanScene`에 다음 optional 필드를 추가한다.

```python
key_concept: NotRequired[str]
visual_metaphor: NotRequired[str]
subject: NotRequired[str]
props: NotRequired[list[str]]
background: NotRequired[str]
avoid: NotRequired[list[str]]
visual_domain: NotRequired[str]
```

`app/services/scene_plan.py`의 `build_scene_plan()`은 기존 prompt만 넣지 말고, `visual_brief` 또는 prompt suggestion 결과에서 위 필드를 채운다.

중요:

- 신규 `visual_scene_plan.json` 금지
- 신규 planner 서비스는 V1에서 금지
- 기존 `ScenePlan`의 version을 올려 확장한다.

자동 검증:

- Obscura 테스트 scene plan에서 각 scene이 `key_concept` 또는 `props`를 하나 이상 가진다.
- generic fallback scene은 `avoid` 또는 issue code에 기록된다.

대상 파일:

- `app/types.py`
- `app/services/scene_plan.py`
- `tests/test_scene_plan.py`

### Phase 4. 기술 도메인 visual vocabulary 추가

목표:

Obscura 같은 기술 설명 영상에서 핵심 개념이 이미지 prop으로 변환되게 한다.

저장 위치:

`storage/visual_vocab/tech.json`

추후 확장 후보:

- `storage/visual_vocab/news.json`
- `storage/visual_vocab/lifestyle.json`
- `storage/visual_vocab/bible.json`

권장 구조:

```json
{
  "domain": "tech",
  "terms": [
    {
      "keywords": ["headless browser", "headless", "browser automation"],
      "key_concept": "headless browser automation",
      "subject": "browser window controlled by an automation agent",
      "props": ["browser window", "terminal panel", "automation cursor"],
      "background": "clean software workspace",
      "avoid": ["running fast", "rain", "random door"]
    }
  ]
}
```

초기 tech vocabulary 항목:

- Obscura
- browser
- headless browser
- JavaScript
- V8
- CDP
- browser automation
- fingerprint
- scraping
- data extraction
- open source
- security
- ethical use

연결 방식:

- autopilot의 content topic 또는 source domain을 기준으로 `tech` vocab 선택
- 명확하지 않으면 `generic` 또는 기존 keyword map 사용
- 사용자 확장 가능하도록 storage JSON 우선, 코드 fallback 보조

대상 파일:

- `app/services/visual_brief.py`
- `app/services/image_prompting.py`
- 신규 vocab loader
- `storage/visual_vocab/tech.json`
- `tests/test_visual_brief.py`
- `tests/test_image_prompting.py`

### Phase 5. visual_brief / prompt_compiler 확장

목표:

기존 구현을 유지하면서 기술 도메인 coverage와 fallback 품질을 올린다.

수정 방향:

- `visual_brief.py`
  - `_MODE_INSTRUCTIONS` 또는 동등한 mode/brief instruction 영역에 기술 도메인 어휘를 추가한다.
  - fallback 시 `single important object` 같은 일반 prop 대신 domain-safe prop을 사용한다.
  - `must_show`에 기술 핵심 prop을 반드시 포함한다.

- `prompt_compiler.py`
  - generic phrase blocklist를 강화한다.
  - 차단 후보:
    - `running fast`
    - `under heavy rain`
    - `standing in front of a large door`
    - `inside a simple room`
    - `symbol that represents the sentence keyword`
  - `check_prompt_compliance()`가 blocklist 위반도 반환하도록 확장한다.

- `image_prompting.py`
  - 기존 keyword matching은 폐기하지 않는다.
  - tech vocab 결과를 visual token 후보로 병합한다.
  - keyword miss 시에도 기술 도메인 안전 fallback을 선택한다.

자동 검증:

- Obscura 문장 fixture에서 prompt가 browser/headless/V8/CDP/fingerprint/automation/data extraction/security 중 최소 하나를 포함한다.
- blocklist 문구가 prompt에 있으면 테스트 실패.
- `must_show` 누락 시 preflight 실패.

대상 파일:

- `app/services/visual_brief.py`
- `app/services/prompt_compiler.py`
- `app/services/image_prompting.py`
- `tests/test_visual_brief.py`
- `tests/test_prompt_compiler.py`
- `tests/test_visual_relevance.py`

### Phase 6. 기술 콘텐츠 이미지 스타일 분기

목표:

Stickfigures LoRA가 기술 다이어그램/인터페이스 장면에 부적합한 경우를 줄인다.

수정 방향:

- autopilot image phase에서 content domain이 `tech`이면 다음 중 하나를 선택한다.
  - Stickfigures LoRA off
  - LoRA strength 낮춤
  - diagram-friendly checkpoint/workflow 사용
  - template system으로 기술 설명형 layout 선택
- `capcut-omnivoice-enhancement-plan.md`의 template system Phase와 cross-link한다.

중요:

- prompt만으로 Stickfigures LoRA의 인물 중심 편향을 완전히 해결한다고 가정하지 않는다.
- 기술 콘텐츠는 인터페이스, 데이터 흐름, 다이어그램이 우선이다.

대상 파일:

- `app/services/autopilot.py`
- `app/workers/image_worker.py`
- `app/services/comfyui_workflows.py`
- workflow template 관련 파일

### Phase 7. Visual QA V1은 text-based만 적용

목표:

QA 비용을 폭증시키지 않고 잘못된 prompt를 먼저 차단한다.

V1 범위:

- 기존 `check_prompt_compliance()` 재사용
- prompt에 `must_show`가 있는지 확인
- blocklist 문구 확인
- sentence hash / manifest freshness 확인
- scene plan의 `key_concept` 또는 `props` 존재 확인

V1 제외:

- 이미지 caption 모델
- vision LLM
- scene별 multimodal QA

V2 후보:

- gemma4 multimodal 또는 별도 caption model로 post-generation caption 비교
- 단, 30 scenes 기준 30분~2.5시간까지 늘어날 수 있으므로 기본 autopilot 경로에는 넣지 않는다.

대상 파일:

- `app/services/prompt_compiler.py`
- `app/services/visual_relevance.py`
- `app/services/preflight.py`
- `tests/test_visual_relevance.py`

### Phase 8. Brave 사용량 숫자 통일

목표:

문서와 코드의 Brave 무료 한도 숫자를 하나로 맞춘다.

현재 충돌:

- 사용자 확인: 월 1000건 무료
- `source-research-and-script-generation-plan.md`: 월 2000건으로 기재
- 코드 일부는 1000 기준으로 수정됨

수정 방향:

- Brave 공식 문서 또는 현재 계정 플랜 기준으로 한도를 재확인한다.
- `BRAVE_FREE_MONTHLY_LIMIT` 기본값과 모든 plan 문서를 같은 숫자로 통일한다.
- 한도는 env override 가능하게 유지한다.

대상 파일:

- `app/config.py`
- `app/services/usage_registry.py`
- `app/services/source_research.py`
- `source-research-and-script-generation-plan.md`
- 관련 테스트

### Phase 9. 60~120초 재생성 전 dependency 확인

목표:

수정 후 영상 생성 실패를 환경 문제와 품질 문제로 혼동하지 않는다.

필수 확인:

- `capcut-omnivoice-enhancement-plan.md` Phase 2a/2b의 1455 mitigation 상태
- OmniVoice 60초/90초 실제 대본 TTS 안정성
- ComfyUI workflow 선택이 tech domain에 맞는지
- render preflight relevance gate 통과 여부

최종 승인 기준:

- 영상 길이 60~120초
- `voice_preset != "auto"`
- `mode == "design"`
- `instruct` non-empty
- autopilot 경로의 seed policy가 의도대로 적용
- prompt에 generic blocklist 문구 없음
- 각 scene의 `must_show`가 prompt에 포함
- tech scene에 browser/headless/V8/CDP/fingerprint/automation/data extraction/security 중 관련 prop 포함
- 자막, 음성, 이미지 순서 일치
- 최종 output path 명확히 출력

## 6. 작업 우선순위

1. Autopilot TTS 기본값을 design preset + non-empty instruct로 고정
2. source draft 직후 cleanup 추가
3. 기존 `ScenePlanScene` 확장
4. `storage/visual_vocab/tech.json` 추가
5. `visual_brief.py`와 `prompt_compiler.py` 확장
6. text-based visual QA 강화
7. tech content 이미지 workflow/LoRA 분기
8. Brave 한도 문서/코드 통일
9. 60~120초 영상 재생성

## 7. 재구현 방지 원칙

- `visual_scene_plan.json` 신규 생성 금지
- 기존 `scene_plan` 확장 우선
- 기존 `visual_brief.py` 폐기 금지
- 기존 `prompt_compiler.py` 폐기 금지
- 기존 `check_prompt_compliance()` 재사용 우선
- Vision LLM QA는 V2로 보류
- encoding 재정리 작업을 핵심 과제로 잡지 않음

## 8. 최종 판단

이전 계획서의 가장 큰 오류는 이미 정정된 "키워드 테이블 깨짐"을 다시 핵심 원인처럼 쓴 것이다. 이번 정정판에서는 그 진단을 제거한다.

현재 진짜 문제는 다음이다.

- 이미지: coverage 부족, 기술 도메인 어휘 부재, generic fallback, Stickfigures LoRA와 기술 다이어그램의 부조화
- 음성: auto voice, auto mode, empty instruct가 autopilot 기본 경로에 들어간 것
- 운영: 기존 plan과 코드 상태를 무시하고 신규 구조를 만들면 중복 시스템이 생길 위험

따라서 해결은 새 파이프라인 구축이 아니라, 이미 존재하는 `ScenePlan` / `VisualBrief` / `prompt_compiler` / preflight gate / TTS preset catalog 위에 정확히 확장하는 방식으로 진행한다.
