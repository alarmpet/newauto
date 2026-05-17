# Sentence Context Image Generation Plan

작성일: 2026-04-28
목표: 대본의 각 문장과 맥락, 핵심 키워드가 이미지에서 자연스럽게 연상되도록 이미지 생성 워크플로우를 개선한다.

구현 상태(2026-04-28 업데이트):

- 완료: Phase 1, 2, 3, 4, 5, 6
- 완료: Phase 9의 1~9 단계 코드 작업 및 `147ab80b75e9` visual plan / scene plan / prompt manifest / prompt quality report 재생성
- 후속: Phase 7 vision QA V2
- 후속: Phase 9의 10단계 실이미지 재생성 후 최종 render report 재검토

## 1. 목표 재정의

이번 개선의 목표는 등장 인물의 얼굴과 의상을 모든 장면에서 완벽히 고정하는 것이 아니다.

중요한 기준은 다음이다.

- 문장을 보지 않고 이미지만 봐도 어떤 의미의 문장인지 대략 연상된다.
- 이미지가 문장의 표면 단어 하나에 과도하게 끌려가지 않는다.
- 이미지가 대본의 정서, 은유, 핵심 키워드를 함께 담는다.
- 각 문장 이미지가 서로 다른 정보를 전달한다.
- 기술 뉴스, 에세이, 라이프스타일, 성경 콘텐츠처럼 도메인별로 다른 시각 언어를 쓴다.

즉 “같은 사람처럼 보이는가”보다 “이 이미지가 이 문장의 핵심을 떠올리게 하는가”가 우선이다.

## 2. 가장 중요한 아키텍처 결정

`core_meaning`과 `visual_metaphor`는 rule-based 파이썬 코드가 만들면 안 된다.

현재 `visual_brief.py`는 `TECH_NEEDLES`, `LITERAL_NEEDLES` 같은 단어 매칭 중심 로직이다. 이 구조는 “browser -> browser window”, “GPU -> GPU rack”처럼 명사 기반 매핑에는 유용하지만, 아래와 같은 문맥 추론은 안정적으로 만들 수 없다.

예:

```json
{
  "core_meaning": "하루가 시작되자마자 알림과 할 일에 마음을 빼앗기는 압박감",
  "visual_metaphor": "작은 방 안에서 휴대폰 알림과 할 일 목록이 하루의 시작을 압박하는 장면"
}
```

이 수준의 해석은 단어장이 아니라 LLM planner가 맡아야 한다.

새 역할 분리:

- LLM planner: 문장별 `core_meaning`, `primary_keywords`, `visual_metaphor`, `must_show`, `avoid`, 후보 subject mode를 생성한다.
- `visual_vocab/*.json`: LLM에게 제공하는 도메인별 참고 어휘와 은유 가이드다. 강제 매칭 테이블이 아니다.
- `visual_brief.py`: LLM 결과가 없을 때의 fallback, 도메인 감지, 구조 정규화 역할을 맡는다.
- `prompt_compiler.py`: LLM이 만든 visual plan을 이미지 모델용 positive/negative prompt로 컴파일한다.
- `visual_relevance.py` 또는 신규 `prompt_quality.py`: coverage 검사, blocklist 검사, retry 조건 판단을 맡는다.

핵심 파이프라인:

```text
script
-> LLM visual planner
-> scene_visual_plan JSON
-> prompt compiler
-> prompt coverage gate
-> auto retry if needed
-> ComfyUI image generation
-> optional candidate selection
-> render
```

## 3. 현재 이미지 문제 분석

### 3.1 휴대폰/침대 이미지

해당 문장:

> 아침에 눈을 뜨자마자 휴대폰 화면을 넘기고, 해야 할 일의 개수에 마음을 빼앗기다 보면 하루는 늘 쫓기듯 시작됩니다.

현재 이미지 문제:

- 손과 휴대폰만 강조되어 문장의 핵심인 “쫓기듯 시작되는 하루”가 약하다.
- 침대 위 휴대폰 장면은 표면 키워드에는 맞지만 맥락에는 부족하다.
- 화면 속 이상한 물체가 시선을 빼앗는다.

진짜 핵심:

- 아침
- 휴대폰 알림
- 해야 할 일의 압박
- 마음이 빼앗김
- 쫓기는 하루의 시작

더 적절한 이미지 방향:

- 침대 옆 탁자 위 휴대폰 알림, 열린 노트, 어두운 아침빛
- 창가에 앉아 휴대폰을 내려다보는 사람의 뒷모습
- 휴대폰 알림과 할 일 목록이 시각적으로 압박감을 주는 아침 방

중요한 점:

- 손만 나와도 반드시 실패는 아니다.
- 다만 손만 나올 경우에도 “압박감”과 “아침의 시작”이 읽혀야 한다.

### 3.2 책상/필기 이미지

해당 문장:

> 방향이 선명한 사람은 같은 한 시간을 살아도 다르게 지칩니다.

현재 이미지 문제:

- 책상에서 글 쓰는 장면 자체는 자연스럽지만 “방향이 선명함”이 잘 보이지 않는다.
- 단순 공부 장면으로 보일 수 있다.
- 자막을 보지 않으면 문장의 핵심인 “같은 시간, 다른 피로”가 약하다.

진짜 핵심:

- 같은 시간
- 방향성
- 집중
- 다른 종류의 피로
- 의미 있는 노력

더 적절한 이미지 방향:

- 책상 위 시계와 명확한 목표 표시가 있는 노트
- 산만한 할 일 더미와 한 줄로 정리된 목표가 대비되는 구도
- 창가 빛 아래, 정리된 작업 공간과 하나의 방향을 가리키는 노트/지도/화살표

### 3.3 “속도보다 방향” 이미지

해당 문장:

> 속도보다 방향이 먼저라는 말을 우리는 자주 듣지만, 바쁜 날들 속에서는 그 말의 의미를 쉽게 잊곤 합니다.

현재 이미지 문제:

- 두 사람이 등장해 “속도와 방향”이라는 은유보다 대화/비교 장면처럼 보인다.
- 휴대폰과 책을 든 두 인물은 표면적으로는 방향/속도 느낌이 있을 수 있지만, 문장의 핵심 은유가 흐리다.
- “속도보다 방향”이라는 핵심이 시각적으로 바로 읽히지 않는다.

진짜 핵심:

- 속도
- 방향
- 바쁜 하루
- 잊힌 기준
- 삶의 나침반

더 적절한 이미지 방향:

- 빠르게 흐릿하게 지나가는 도시 속, 선명한 나침반이나 지도
- 여러 갈래 길 앞에서 멈춘 인물 또는 빈 길
- 시계와 나침반이 같은 책상 위에 놓인 상징적 장면

중요한 점:

- 사람이 없어도 된다.
- 나침반, 길, 지도, 시계, 신호등 같은 오브젝트 중심 이미지가 더 정확할 수 있다.

## 4. 근본 원인

### 4.1 문장을 바로 프롬프트로 바꾸는 구조

현재 이미지 프롬프트는 문장에서 눈에 띄는 단어를 바로 장면으로 바꾸는 경향이 있다.

예:

- 휴대폰 -> 손이 휴대폰을 든 클로즈업
- 필기 -> 책상에서 글 쓰는 사람
- 방향 -> 사람이 무언가를 들고 서 있음

이 방식은 표면 키워드는 잡지만 문맥은 놓친다.

필요한 중간 단계:

```text
문장 -> 핵심 의미 -> 시각 은유 -> 장면 오브젝트 -> 최종 프롬프트
```

### 4.2 핵심 키워드와 보조 키워드가 분리되지 않음

문장에는 여러 단어가 있지만 이미지에 반드시 들어가야 하는 단어는 일부뿐이다.

예:

문장:

> 휴대폰 화면을 넘기고, 해야 할 일의 개수에 마음을 빼앗기다 보면 하루는 쫓기듯 시작됩니다.

핵심 키워드:

- 압박감
- 알림
- 할 일
- 아침

보조 키워드:

- 침대
- 손
- 휴대폰

현재는 보조 키워드가 이미지의 주인공이 되어버린다.

### 4.3 단어장 강제 매칭의 한계

`essay.json`에 “길”, “선택”이 있다고 해서 모든 선택 문장에 나침반과 갈림길을 넣으면 어색해진다.

예:

> 그의 선택은 늘 틀렸지만, 이번만은 달랐다.

이 문장에는 갈림길이 맞을 수도 있지만, 맥락에 따라 후회, 변화, 표정, 오래된 편지, 다시 열린 문 같은 이미지가 더 적합할 수 있다.

따라서 단어장은 “강제 매칭”이 아니라 “LLM planner에게 주는 참고 자료”로 써야 한다.

## 5. 개선 설계

## Phase 1. LLM Visual Planner 도입 [완료]

대본 생성 또는 scene plan 생성 단계에서 LLM이 문장별 visual plan JSON을 만든다.

입력:

- 전체 대본
- 문장 배열
- 콘텐츠 도메인
- 톤
- `storage/visual_vocab/{domain}.json`에서 불러온 은유 가이드
- 이미지 모델 제약 조건

출력:

```json
[
  {
    "sentence_idx": 1,
    "sentence": "아침에 눈을 뜨자마자 휴대폰 화면을 넘기고...",
    "core_meaning": "하루가 시작되자마자 알림과 할 일에 마음을 빼앗기는 압박감",
    "primary_keywords": ["아침", "알림", "할 일", "압박감"],
    "secondary_keywords": ["휴대폰", "침대", "손"],
    "visual_metaphor": "작은 방 안에서 휴대폰 알림과 할 일 목록이 하루의 시작을 압박하는 장면",
    "subject_modes": ["environment", "object_metaphor"],
    "must_show": ["morning room", "smartphone notifications", "to-do list pressure"],
    "may_show": ["bed", "hand", "window light"],
    "avoid": ["phone screen closeup only", "strange object on phone", "generic smiling person"],
    "prompt_hint": "wide or medium shot, not a hand-only closeup"
  }
]
```

구현 위치 후보:

- `app/services/source_draft.py`: LLM이 대본을 만들 때 visual plan까지 함께 생성
- `app/services/scene_plan.py`: 대본과 timings가 준비된 뒤 visual plan 생성
- 신규 `app/services/visual_planner.py`: LLM 호출과 JSON 정규화를 전담

권장:

- 신규 `visual_planner.py`를 만들고, `scene_plan.py`가 이를 호출한다.
- 자동화 경로에서는 `source_draft -> compile_script -> tts -> visual_planner -> image_prompting` 순서로 사용한다.
- 수동 대본 입력도 visual planner를 동일하게 사용한다.

Acceptance:

- `scene_plan` 또는 별도 `visual_plan`에 `core_meaning`, `primary_keywords`, `visual_metaphor`가 저장된다.
- rule-based fallback은 LLM 실패 시에만 사용된다.
- LLM JSON parse 실패 시 최대 2회 repair prompt를 시도한다.

## Phase 2. Visual Vocabulary를 Context Injection으로 사용 [완료]

신규 파일:

`storage/visual_vocab/essay.json`

역할:

- 파이썬이 무조건 매칭하는 테이블이 아니다.
- LLM에게 “이런 추상어가 나오면 이런 시각 은유를 고려하라”고 주는 컨텍스트다.

예시:

```json
{
  "domain": "essay",
  "terms": [
    {
      "keywords": ["방향", "길", "선택"],
      "concept": "direction and life choice",
      "metaphor_examples": [
        "quiet road fork with a compass on a map",
        "single signpost in a blurred busy street",
        "desk with map, clock, and one marked route"
      ],
      "avoid": ["business meeting", "two similar people by default"]
    },
    {
      "keywords": ["속도", "바쁜", "쫓기듯"],
      "concept": "rushed daily life",
      "metaphor_examples": [
        "blurred city morning with a sharp alarm clock",
        "phone notifications beside an unfinished to-do notebook",
        "calendar pages and notification lights pressing into the morning"
      ],
      "avoid": ["sports running", "action chase scene"]
    }
  ]
}
```

Acceptance:

- planner prompt에 domain vocabulary summary가 포함된다.
- LLM은 vocabulary를 참고하되 문맥에 맞지 않으면 다른 은유를 선택할 수 있다.
- `visual_plan.json`에는 어떤 vocabulary item을 참고했는지 `vocab_refs`로 남길 수 있다.

## Phase 3. Prompt Compiler를 실행 전용으로 축소 [완료]

`prompt_compiler.py`는 의미 추론을 하지 않는다.

역할:

- LLM visual plan을 이미지 모델이 이해하기 쉬운 prompt로 바꾼다.
- 장면 구도, camera, lighting, mood, avoid list를 일관된 포맷으로 묶는다.
- 도메인별 style template을 적용한다.

Prompt plan:

```json
{
  "subject_mode": "object_metaphor",
  "camera": "medium wide shot",
  "main_objects": ["compass", "map", "alarm clock"],
  "background": "quiet dawn room",
  "mood": "reflective pressure",
  "color": "soft blue gray morning palette",
  "forbidden_focus": ["hands only", "phone screen closeup only"]
}
```

규칙:

- 추상 문장일수록 `object_metaphor` 또는 `environment`를 우선한다.
- 사람은 필요할 때만 등장시킨다.
- 클로즈업은 위험도가 높으므로 기본값은 medium/wide shot으로 둔다.
- positive prompt에는 `core_meaning` 자체를 길게 넣지 않고, 시각 오브젝트로 번역된 결과만 넣는다.

Acceptance:

- prompt compiler는 LLM 호출을 하지 않는다.
- prompt compiler는 `visual_plan`이 비어 있으면 fallback prompt를 만들되 report에 경고를 남긴다.

## Phase 4. Core Keyword Coverage Gate와 Auto Retry [완료]

현재 `visual_relevance.py`에는 `missing_must_show`와 blocklist 검사 기반이 있다.
이를 확장하되, 실패 시 바로 파이프라인을 멈추지 않는다.

검사 항목:

- `core_meaning`이 비어 있으면 실패
- `primary_keywords`가 0개면 실패
- positive prompt에 `must_show` 중 최소 1개가 없으면 실패
- negative prompt에 `avoid`가 반영되지 않으면 경고
- positive prompt가 스타일어만 있고 장면 명사가 부족하면 실패
- 같은 generic phrase가 여러 장면에 반복되면 경고

실패 처리:

1. 1차 실패: prompt compiler가 `must_show`를 더 강하게 재배치한다.
2. 2차 실패: `secondary_keywords`를 줄이고 `primary_keywords`와 `visual_metaphor`만 사용한다.
3. 3차 실패: LLM planner에 repair prompt를 보내 visual plan을 다시 만든다.
4. 그래도 실패하면 해당 장면을 `needs_manual_review`로 표시하고, autopilot은 pause 또는 fallback 정책에 따른다.

권장 retry 횟수:

- planner repair: 최대 2회
- prompt compile retry: 최대 2회

Acceptance:

- `image_prompts_manifest.json`에 `keyword_coverage`와 `retry_count`가 저장된다.
- coverage 실패 장면은 무조건 silent pass 하지 않는다.
- autopilot에서는 실패 시 즉시 전체 중단이 아니라 repair loop 후 pause/fallback 한다.

## Phase 5. Quality Mode로 후보 생성 비용 제어 [완료]

모든 장면에 후보 2~3장을 생성하면 품질은 좋아질 수 있지만, 8GB VRAM 환경에서는 비용과 안정성 문제가 커진다.

문제:

- 20문장 대본에서 3후보를 만들면 60장 이미지가 생성된다.
- ComfyUI와 OmniVoice가 같은 GPU를 쓰는 환경에서는 VRAM 압박과 지연이 커진다.
- 장시간 batch는 메모리 누수, 발열, timeout 가능성을 높인다.

따라서 후보 생성은 프로젝트 옵션으로 분리한다.

```json
{
  "quality_mode": "fast | balanced | exhaustive"
}
```

정책:

- `fast`: 장면당 1장, retry는 prompt repair만 수행
- `balanced`: 핵심/추상 문장만 2장, 나머지는 1장
- `exhaustive`: 모든 장면 2장, 핵심 문장 3장

추가 운영 정책:

- batch item N개마다 GPU/ComfyUI 상태를 기록한다.
- image worker는 장면 batch 사이에 짧은 cooldown을 둘 수 있다.
- ComfyUI 자체 캐시 비우기는 API/환경 지원 여부를 확인한 뒤 별도 구현한다.
- GPU guard는 TTS와 ComfyUI가 겹치지 않도록 유지한다.

Acceptance:

- autopilot options 또는 project feature settings에 `quality_mode`가 저장된다.
- 기본값은 `fast` 또는 `balanced`로 둔다.
- 8GB VRAM 환경에서는 `exhaustive`가 기본값이 아니다.

## Phase 6. Text-based QA V1 [완료]

Vision model 없이 우선 적용할 수 있는 QA다.

체크:

- prompt에 문장 핵심 명사/은유가 있는가
- prompt가 문장마다 충분히 다른가
- 같은 generic phrase가 3회 이상 반복되는가
- 클로즈업 위험어가 핵심 의미를 압도하는가
- `visual_plan.subject_mode`와 실제 prompt가 일치하는가

중복도 체크:

```text
if prompt_similarity(scene_i, scene_j) > 0.82:
    warn "Scenes may look too similar"
```

Acceptance:

- 이미지 생성 전 `prompt_quality_report.json` 생성
- 유사도가 높은 장면은 LLM repair 또는 alternate subject mode로 재생성
- QA 결과는 autopilot debug snapshot에 요약된다.

## Phase 7. Vision QA V2 [후속]

가능하면 이후 멀티모달 모델로 이미지 자체를 검사한다.

질문 예시:

- 이 이미지를 보면 어떤 키워드가 떠오르는가?
- 휴대폰/할 일/아침 압박감이 보이는가?
- “방향” 또는 “속도”를 떠올릴 수 있는가?
- 불필요한 이상 물체가 주 피사체인가?
- 문장 핵심과 무관한 장면인가?

Acceptance:

- 이미지 caption에서 primary keyword 1개 이상 회수
- 문장 핵심과 무관한 객체가 주된 피사체면 후보 탈락
- V2는 비용이 있으므로 기본 워크플로우가 아니라 선택 옵션으로 둔다.

## Phase 8. 이번 에세이 대본 재생성 기준 [기준 정리 완료]

기존 대본은 유지해도 된다.
다만 이미지 프롬프트는 아래 방향으로 재작성한다.

| 문장 핵심 | 기존 문제 | 새 이미지 방향 |
| --- | --- | --- |
| 속도보다 방향 | 두 사람 등장, 의미 흐림 | 나침반, 지도, 갈림길, 흐릿한 도시 |
| 휴대폰과 할 일 압박 | 손+휴대폰 클로즈업 | 아침 방, 알림, 할 일 노트, 압박감 |
| 어디로 가는지 모름 | 도시 인물 장면 평범 | 안개 낀 길, 목적지 없는 표지판 |
| 방향이 선명함 | 공부 장면으로 축소 | 정리된 책상, 시계, 목표 표시 |
| 노력과 모래 | 비교적 적합 | 발자국, 빈 해변, 흐린 수평선 |
| 가치 질문 | 노트/펜만 있음 | 열린 노트와 조용한 빛, 선택 키워드 |
| 작은 행동 | 손/책/문장/진심 | 책 한 페이지, 편지, 따뜻한 작은 행동 |
| 느린 걸음 | 계단/길 | 긴 길, 천천히 이어지는 발걸음 |

## Phase 9. 구현 순서

1. [완료] `storage/visual_vocab/essay.json` 작성
2. [완료] 신규 `app/services/visual_planner.py` 작성
3. [완료] LLM planner prompt에 대본, 문장 배열, domain vocab, output schema를 넣는다.
4. [완료] `scene_plan.py` 또는 autopilot image phase에서 visual planner 결과를 저장한다.
5. [완료] `prompt_compiler.py`는 visual plan 기반 prompt 생성만 담당하도록 정리한다.
6. [완료] `prompt_quality.py` 또는 `visual_relevance.py`에 coverage gate와 retry loop를 추가한다.
7. [완료] `quality_mode` 옵션을 autopilot/project settings에 추가한다.
8. [완료] `image_worker` batch generation이 quality mode에 따라 후보 수를 정하도록 수정한다.
9. [완료] 기존 에세이 프로젝트 `147ab80b75e9`에 대해 새 visual plan과 prompt manifest를 생성한다.
10. [후속] 이미지 재생성 후 render report와 prompt quality report를 함께 확인한다.

## 6. 최종 Acceptance Criteria

새 테스트 영상은 다음을 만족해야 한다.

- 모든 이미지 prompt에 LLM 생성 `core_meaning`이 있다.
- 모든 이미지 prompt에 `primary_keywords`가 있다.
- 모든 이미지 prompt에 `visual_metaphor` 또는 `subject_mode`가 있다.
- 이미지가 문장 표면 단어 하나에만 갇히지 않는다.
- 문장별 이미지가 서로 다른 핵심 오브젝트나 환경을 가진다.
- 휴대폰 장면은 휴대폰만이 아니라 “아침 압박감”을 보여준다.
- 방향 문장은 사람보다 나침반/길/지도 같은 은유를 우선 고려한다.
- prompt quality report에서 unrepaired coverage 실패가 0개다.
- `quality_mode=fast`에서도 8GB VRAM 환경에서 무리 없이 동작한다.
- 최종 render report의 duration guard가 통과한다.

## 7. 핵심 결론

이미지 생성 품질을 올리려면 “멋진 이미지 프롬프트”보다 먼저 “문장의 의미를 시각 개념으로 번역하는 단계”가 필요하다.

이 번역 단계는 rule-based 파이썬이 아니라 LLM planner가 맡아야 한다. 파이썬은 LLM에게 도메인 어휘를 제공하고, 결과 JSON을 검증하고, 실패 시 재시도하고, ComfyUI 실행을 안정적으로 관리하는 쪽이 맞다.

이 구조로 바꾸면 주인공이 나오든, 오브젝트만 나오든, 추상적인 장면이든 대본 맥락과 훨씬 잘 맞는 이미지가 나온다.
