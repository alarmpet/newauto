# CapCut Editing + OmniVoice Enhancement Plan (Revised)

작성일: 2026-04-27
상태: `[Pending]`

## 1. 목표

CapCut의 편집 방식과 OmniVoice의 공식 사용법을 참고해, 우리 자동화 프로그램을 더 "편집자가 만진 것처럼 보이는" 영상 제작 도구로 고도화한다.

핵심 방향:

- CapCut식 타임라인/키프레임/캡션/쇼츠 제작 감각을 `render_plan`과 UI에 반영
- OmniVoice의 `voice design`, `generation parameters`, `voice cloning`, CLI/batch 사용 방식을 우리 TTS worker 구조에 반영
- 1~2분 이상 TTS에서 확인된 Windows `os error 1455` (ERROR_COMMITMENT_LIMIT — 페이지 파일 부족) 를 줄이기 위해 **점진적 mitigation 전략** 적용
- 자동화는 유지하되, 결과물이 단순 슬라이드쇼처럼 보이지 않도록 motion, caption, beat, cut 정책을 강화

본 plan 은 [autopilot-end-to-end-render-plan.md](autopilot-end-to-end-render-plan.md) + [automation-advancement-master-plan.md](automation-advancement-master-plan.md) 위에 쌓인다 — 새 worker 만들지 않고 **기존 자산 위에 정책 + 데이터 모델 확장**.

## 2. 참고한 자료

공식/1차 자료 우선:

- CapCut Keyframe Animation: https://www.capcut.com/tools/keyframe-animation
- CapCut Auto Captions help: https://www.capcut.com/help/auto-captions
- CapCut Recognise Subtitles help: https://www.capcut.com/help/how-to-recognise-subtitles
- CapCut Auto Video Editor: https://www.capcut.com/tools/auto-video-editor/
- CapCut Auto Caption Generator: https://www.capcut.com/tools/auto-caption-generator/
- OmniVoice GitHub: https://github.com/k2-fsa/OmniVoice  *(공식 README 의 instruct/ref_audio/CLI 사용 예시 우선 참고)*

> Note: 이전 draft 에 있던 arxiv 링크는 검증 불가 (연도 오류) — 제거. OmniVoice paper 를 인용하려면 GitHub README 에서 정확한 링크를 다시 확인.

## 3. 분석 요약

### 3.1 CapCut에서 가져올 편집 원리

| CapCut 방식 | 우리 프로그램에 반영할 것 |
|---|---|
| Keyframe으로 position, scale, rotation, opacity를 시간에 따라 조정 | `render_plan.segment.motion`을 단순 문자열이 아니라 keyframe preset으로 확장 |
| Speed curve/easing으로 움직임을 자연스럽게 만듦 | Ken Burns zoom을 linear가 아닌 ease-in/ease-out로 전환 |
| Auto captions 생성 후 타이밍, 텍스트, 스타일 수정 | `timings.json`, `timings_words.json`, ASS subtitle style editor를 더 강하게 연결 |
| 잘못 분절된 caption은 split/edit/regenerate | 긴 자막 자동 split, 문장별 재타이밍, caption QA report 추가 |
| Long video to shorts에서 길이와 caption template 선택 | `render_formats=["shorts"]` 자동 파생, hook/highlight segment 추천 |
| 템플릿/효과/음악 싱크로 초보자도 빠른 결과 제작 | 우리 앱의 style preset을 "렌더 템플릿"으로 승격 |

### 3.2 OmniVoice에서 가져올 TTS 원리

| OmniVoice 기능 | 우리 프로그램에 반영할 것 |
|---|---|
| `OmniVoice.from_pretrained("k2-fsa/OmniVoice", device_map="cuda:0", dtype=torch.float16)` | 현재 방식 유지 — `system_health` 가 이미 resolved Python/import/CUDA 노출 |
| `model.generate(text=..., instruct=...)` voice design | TTS preset을 단순 음색 목록이 아니라 `성별/연령/피치/스타일` 조합 UI로 확장 |
| `speed`, `duration`, `num_step` 등 generation parameter | 문장별 profile override를 region, hook, quote에 따라 자동 적용 (이미 `_effective_sentence_profile` 존재) |
| `ref_audio`, `ref_text` voice cloning | Phase 4에서 reference voice upload/lock 기능 추가, **`ref_text` 누락 시 기존 `transcribe.py` (faster-whisper) 로 자동 채움** |
| CLI `omnivoice-infer`, `omnivoice-infer-batch` | **단일 subprocess 안에서 점진적 메모리 정리 우선**, 그래도 1455 가 남으면 batch subprocess 로 escalate |
| non-verbal tag `[laughter]`, `[sigh]` | script_compile 단계에서 감정 cue를 안전하게 삽입하는 옵션 추가 |

## 4. 현재 코드 자산과 갭 (검증 완료)

| 영역 | 이미 있음 (검증) | 추가할 것 |
|---|---|---|
| Render plan | `RenderPlanSegment` 의 `motion`, `effect`, `caption_style` 필드 ([types.py:112-120](app/types.py#L112-L120)) | keyframe array, easing, transition duration, beat sync 필드 |
| Render engine | Ken Burns, fade, ASS subtitle, render report ([render.py](app/services/render.py), [render_report.py](app/services/render_report.py)) | CapCut식 motion preset → 키프레임 expander, caption animation, per-word highlight 강화 |
| Subtitle | `timings.json`, `timings_words.json`, `SubtitleStyle` ([subtitle.py](app/services/subtitle.py)) | caption QA report, split/reflow, style preset 저장 |
| TTS | preset, preview lock, seed lock, `_effective_sentence_profile` region speed override, **subprocess worker (`tts_worker.py` + `scripts/run_tts_job.py`) — 단일 subprocess 가 전체 문장 처리** | 1455 mitigation (점진), voice design builder, cloning upload |
| Autopilot | script/url/keyword → TTS → image → render 흐름 ([autopilot.py](app/services/autopilot.py), [autopilot_worker.py](app/workers/autopilot_worker.py)) | template 선택 hook, 쇼츠 자동 파생 후 다중 render trigger, 단계별 retry |
| Operator | queue/GPU/tool/usage/render metrics ([system_health.py](app/services/system_health.py)) | TTS batch metrics, caption QA metrics |

## 5. 구현 계획

### Phase 0. CapCut식 편집 모델 정의 — keyframe vs motion 통합

목표: 기존 `motion: str` 만으로는 CapCut식 미세 조정 불가. **`motion` 은 preset alias 로 유지**, 내부적으로 `keyframes` array 로 expand 하는 구조 도입.

추가 타입 (`app/types.py`):

```python
class RenderKeyframe(TypedDict):
    t: float                # segment 내 0.0~1.0 (또는 절대 sec)
    scale: NotRequired[float]
    x: NotRequired[float]   # -0.5~0.5 (캔버스 중심 기준 비율)
    y: NotRequired[float]
    opacity: NotRequired[float]


class RenderPlanSegment(TypedDict):
    # 기존 필드 유지
    motion: str             # 'slow_zoom_in' 같은 alias — 호환 유지
    effect: str
    caption_style: str
    # 신규 (모두 NotRequired, 없으면 motion alias 로 expand)
    keyframes: NotRequired[list[RenderKeyframe]]
    easing: NotRequired[Literal["linear", "ease_in", "ease_out", "ease_in_out"]]
    transition: NotRequired[Literal["none", "fade", "push", "zoom_blur"]]
    transition_duration_sec: NotRequired[float]
    beat_sync: NotRequired[bool]
```

**Motion → keyframes 변환 (단일 source of truth)**:

```python
# app/services/render_motion.py (신규)
def expand_motion_preset(motion: str, easing: str = "ease_out", duration_sec: float = 3.0) -> list[RenderKeyframe]:
    """motion alias 를 keyframe array 로 확장. 두 시스템 공존이 아닌 'keyframe 이 진실' 패턴."""
    if motion == "slow_zoom_in":
        return [{"t": 0.0, "scale": 1.0}, {"t": 1.0, "scale": 1.10}]
    if motion == "punch_zoom":
        return [{"t": 0.0, "scale": 1.0}, {"t": 0.15, "scale": 1.18}, {"t": 1.0, "scale": 1.0}]
    if motion == "slow_pan_right":
        return [{"t": 0.0, "x": -0.05}, {"t": 1.0, "x": 0.05}]
    # ... 등
```

**렌더 시 결정 순서**:
1. `segment.keyframes` 명시 → 그대로 사용
2. 없으면 `expand_motion_preset(segment.motion, segment.easing or "ease_out")` 호출
3. 결과를 FFmpeg `zoompan`/`scale`/filter graph 로 변환

→ **두 필드가 공존해도 keyframes 가 항상 ground truth**, motion 은 사람이 읽기 쉬운 별명.

새 preset 예시 (`render_motion.py` 안의 dict):

- `documentary_slow_push`
- `news_caption_focus`
- `shorts_punch_zoom`
- `quote_reveal`
- `bible_reverent_pan`

변경 대상: `app/types.py`, `app/services/render_plan.py`, `app/services/render_motion.py` (신규), `app/services/render.py` (filter graph 생성에서 keyframes 사용), `tests/test_render_motion.py` (신규).

완료 기준:
- 기존 `motion="slow_zoom_in"` 만 있는 render_plan 도 동일한 시각 결과
- 명시적 `keyframes` 가 있으면 그것이 우선
- 회귀 테스트: 모든 motion alias → expand → 같은 종료 scale/x/y 값 검증

### Phase 1. Caption QA — 3 sub-phase 로 분할 (원본의 단일 phase 가 너무 광범위)

원본 plan 의 Phase 1 은 caption split/merge + style enum + preset save + render_report + preflight + UI 까지 포괄 → 2~3주 작업. 분할:

#### Phase 1a. Caption QA report 만 (P0)

`app/services/render_report.py` 확장:

```python
class CaptionQaReport(TypedDict):
    long_caption_count: int           # max_line_chars × 1.3 초과한 cue
    short_caption_count: int          # 0.6 초 미만 cue
    missing_word_timing_count: int    # word timings 가 cue 단위 sentence count 와 불일치
    overflow_caption_indices: list[int]
    short_caption_indices: list[int]
```

UI: render 완료 후 report 패널에 카운트만 표시. 수정 도구는 Phase 1b 이후.

#### Phase 1b. caption_style enum 확장 + render mapping (P1)

현재 `subtitle_style.effect = none|fade|pop|karaoke` (per-cue inline). 신규 `caption_style` 은 **per-segment 의 style template** (다른 축).

→ 이름 충돌 방지 위해 `caption_template` 으로 rename 권장:

```python
CaptionTemplate = Literal["plain", "emphasis", "quote", "hook", "lesson"]
# RenderPlanSegment.caption_style 을 CaptionTemplate 로 type 화
```

ASS rendering 시 `caption_template` → `subtitle_style` override (예: `quote` → italic + center, `emphasis` → bold + bigger).

#### Phase 1c. caption split/merge editor + preset save (P2)

긴 caption 자동 split, 짧은 caption merge 후보 표시, style preset 저장/불러오기. **Phase 6 (template system) 와 함께 묶어서 진행** — 따로 진행하면 UI 이중 작업.

변경 대상 (전체): `app/services/subtitle.py`, `app/services/preflight.py`, `app/services/render_report.py`, `app/static/app.js`, `app/static/style.css`.

### Phase 2. OmniVoice 긴 대본 안정화 — 점진적 mitigation (가장 큰 변경)

**원본 plan 의 결함**: 곧바로 multi-subprocess batch 로 점프. 하지만:
- 각 batch subprocess 가 OmniVoice 모델 cold load (30~60s) → 5 batch 면 +2.5~5분
- 단순 메모리 정리 (`torch.cuda.empty_cache() + gc.collect()`) 만으로 1455 가 해소될 가능성 큼
- 실패해도 더 무거운 옵션이 남으니 **저비용부터 escalate**

#### Phase 2a. 단일 subprocess 내 점진 메모리 정리 (먼저 시도)

상태: `[완료 - 2026-04-27 실측 통과]`

구현 반영:
- `app/services/tts.py` sentence loop에서 5문장마다 `gc.collect()`, `torch.cuda.empty_cache()`, 가능 시 `torch.cuda.synchronize()` 실행.
- `_cleanup_generation_memory()`를 별도 함수로 분리해 테스트 가능하게 유지.
- `tests/test_tts_pipeline.py`에 10문장 입력 시 cleanup 2회 호출 회귀 테스트 추가.

실측 결과:
- 테스트 프로젝트: `7ee7587d99ca`
- 조건: 18문장, `omnivoice_env\Scripts\python.exe`, `male-deep-calm`, speed `0.8`
- 결과: `tts_state=done`, `tts_progress=100`
- 산출물: `storage/projects/7ee7587d99ca/tts/0000.wav` ~ `0017.wav`
- 총 TTS 길이: 약 `84.58초`
- 이번 측정에서는 Windows `os error 1455` 재발 없음.

판단:
- Phase 2a만으로 1~2분급 TTS 차단은 우선 해소된 것으로 본다.
- 180초 이상 장문에서 1455가 다시 나오면 Phase 2b/2c로 escalate한다.
- 한글 실측은 PowerShell inline script 인코딩 경로에서 문장 필터가 먼저 막힌 케이스가 있었으므로, 브라우저/API 실제 입력 경로에서 별도 재검증한다.

[app/services/tts.py:389-424](app/services/tts.py#L389-L424) `run_tts_job` 의 sentence loop 에 cleanup 추가:

```python
import gc
import torch

CLEANUP_EVERY_N_SENTENCES = 5

for index, text in enumerate(sentences):
    # ... 기존 synth ...
    if (index + 1) % CLEANUP_EVERY_N_SENTENCES == 0:
        del audio  # 명시적 release
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
```

**완료 기준 (먼저)**:
- 60초/90초 실제 대본에서 1455 발생 빈도 측정
- 발생 안 하면 Phase 2b 불필요 — 종료
- 여전히 발생하면 Phase 2b 진행

#### Phase 2b. Pipe-based 장기 subprocess (Phase 2a 실패 시)

batch subprocess 가 매번 모델 cold load 하는 것을 피하기 위해 **장기 subprocess + stdin/stdout 프로토콜**:

```text
parent (tts_worker)
  → spawn subprocess: scripts/run_tts_server.py --project-id PID
     ← model load 1회
     ← loop: parent 가 stdin 으로 "synthesize <idx> <text>" → child 가 wav 저장 후 stdout 으로 "done <idx> <duration>"
     ← N 문장마다 child 자체적으로 gc + empty_cache
     ← 모든 문장 끝나면 parent 가 "exit" → child cleanup + 종료
```

장점:
- 모델 cold load 1회 (현재와 동일)
- parent 가 child 메모리 사용량 모니터링 가능 (psutil)
- N MB 초과 감지 시 child 재시작 — fault isolation

단점:
- 프로토콜 디자인 + 구현 복잡도

#### Phase 2c. Multi-batch subprocess (Phase 2b 도 실패 시)

**여기서 비로소** 원본 plan 의 batch subprocess 도입. 기준:
- batch 크기 환경별 자동 산정 (3~5 sentence)
- partial timings 합치기
- 실패 batch 만 retry

action_hint 구체화 (사용자가 보는 텍스트):

```text
TTS_MODEL_LOAD_PAGEFILE_1455:
  Windows 페이지 파일이 부족합니다 (32GB+ 권장).
  설정 → 시스템 → 정보 → 고급 시스템 설정 → 성능 → 가상 메모리 에서 페이지 파일 크기를 조정하세요.
  임시 우회: 대본을 60초 미만으로 짧게 나눠서 생성.
```

변경 대상: `app/services/tts.py` (Phase 2a), `scripts/run_tts_server.py` (Phase 2b 신규), `app/workers/tts_worker.py`, `app/types.py`, `tests/test_tts_pipeline.py`, `tests/test_tts_worker.py`.

### Phase 3. OmniVoice Voice Design Builder

목표: 사용자가 프리셋만 고르는 구조에서 벗어나, 영상 장르에 맞는 음색 설계를 쉽게 선택.

UI:
- 성별: 남성/여성/자동
- 연령대: 청년/중년/장년/노년
- 톤: 차분함/뉴스/다큐/목회/긴장감/따뜻함
- 피치: 낮음/중간/높음
- 속도: 느림/표준/빠름

builder → `tts_profile.instruct` 변환 함수:

```python
def build_instruct(gender: str, age: str, pitch: str, tone: str) -> str:
    parts = [gender, age, f"{pitch} pitch", tone]
    return ", ".join(p for p in parts if p)
```

저장 시:
- `tts_profile.instruct` 에 결과 문자열 저장 (현재 schema 그대로)
- 추가로 `tts_profile.builder` JSON (gender/age/pitch/tone 원본) 저장 → 재편집 시 UI 복원

변경 대상: `app/tts_profiles.py`, `app/routers/render.py`, `app/static/app.js`, `app/static/index.html`, `tests/test_tts_presets.py`.

완료 기준:
- builder 값이 `instruct` + `builder` JSON 양쪽 저장
- preview lock / seed lock 유지
- region별 profile override 가 manifest 에 기록

### Phase 4. Voice Cloning 옵션

목표: OmniVoice의 `ref_audio` 기반 voice cloning을 선택 기능으로.

작업:
- reference audio upload (`storage/projects/{pid}/voice_ref/ref.wav`)
- **`ref_text` 누락 시 기존 `transcribe.py` (faster-whisper) 로 자동 채움** — 이미 통합된 자산 활용
- reference audio 3~10초 권장 검증 (preflight 단계)
- preview 생성 후 lock
- full TTS 에 `ref_audio`, `ref_text` 전달

DB 추가 필드:
- `voice_ref_file: str` (default `''`)
- `voice_ref_text: str` (default `''`, faster-whisper 결과 캐시)
- `voice_ref_duration_sec: float` (default `0.0`)

변경 대상: `app/routers/render.py`, `app/services/tts.py`, `app/types.py`, `app/static/app.js`, `app/static/index.html`.

완료 기준:
- reference audio 없으면 기존 voice design 흐름 유지
- cloning 사용 시 manifest 에 reference metadata 기록
- ref_audio 가 너무 길면 (≥ 30s) preflight 경고
- ref_text 자동 transcription 결과 보여주고 사용자 편집 허용

### Phase 5. CapCut식 쇼츠 자동 파생

**Hook 탐지 방식 결정 (원본 plan 미명시)**:

V1 — heuristic (LLM 비용 0):
- 첫 N 문장 기본 후보
- "?" / "!" / 숫자 / 따옴표 가 있는 문장 가산
- 길이 8~25자 우선 (너무 짧으면 낚시, 너무 길면 caption 안 들어감)

V2 — Ollama 기반 (선택):
- gemma4:e4b 가 sentence list 입력 → score (0~1) 출력
- VRAM 경합 정책 따라 source_draft worker 와 직렬화

변경 대상: `app/services/shorts_plan.py` (신규), `app/services/render_plan.py`, `app/services/render.py`, `app/static/app.js`, `tests/test_shorts_plan.py`.

완료 기준:
- 하나의 longform 프로젝트에서 3개 shorts 후보 생성
- 후보별 preflight/report 분리
- output path: `output_shorts_01.mp4`, `output_shorts_02.mp4`
- autopilot 통합 (Phase 6 의 template 옵션이 shorts 자동 파생 토글 포함)

### Phase 6. Template System (Phase 1c 의 caption preset 흡수)

Template 구성:

```json
{
  "id": "documentary_youtube",
  "render_format": "landscape",
  "motion_preset": "documentary_slow_push",
  "caption_template": "plain",        // Phase 1b 의 enum
  "transition_preset": "soft_fade",
  "voice_preset": "male-deep-calm",
  "voice_builder": null,              // 또는 builder dict
  "image_style": "documentary still frame",
  "bgm_policy": "ducked_low",
  "shorts_auto_derive": false
}
```

저장 위치 결정:
- 시스템 템플릿: `app/services/template_registry.py` 의 상수 dict (코드 일부)
- 사용자 템플릿: `storage/templates/{id}.json` 파일 (사용자 데이터)
- 양쪽 통합 조회 함수가 시스템 + 사용자 합쳐서 반환

우선 시스템 템플릿 5종:
- `documentary_youtube`
- `news_explainer`
- `shorts_fast_caption`
- `bible_reverent`
- `story_lesson`

**Autopilot 통합** (cross-link to [autopilot-end-to-end-render-plan.md](autopilot-end-to-end-render-plan.md)):
- `autopilot_options.template_id: str` 신규 필드
- autopilot start 시 template 의 모든 설정을 한 번에 적용 (TTS preset, render_plan motion, subtitle_style, image style, bgm policy)
- 사용자가 후속 단계에서 manual override 가능

변경 대상: `app/services/template_registry.py` (신규), `app/services/autopilot.py`, `app/services/render_plan.py`, `app/static/app.js`, `app/static/index.html`, `tests/test_template_registry.py`.

완료 기준:
- Autopilot 시작 전에 template 선택 가능
- template 이 TTS, image prompt, render_plan, subtitle_style 에 한 번에 반영
- 기존 수동 옵션으로 override 가능
- 사용자 정의 template 저장/불러오기

## 6. 우선순위 (의존성 반영해 재정렬)

원본 plan 의 순서가 의존성 모순. 갱신:

1. **Phase 2a** — TTS 단일 subprocess 메모리 정리 (가장 가벼운 응급 수정)
2. **Phase 2b/2c** — 필요 시 escalate
3. **Phase 0** — render_plan keyframe + motion expander
4. **Phase 1a** — caption QA report (가벼운 가시화)
5. **Phase 6** — template system (Phase 0 의 motion preset + Phase 1b 의 caption_template 모두 묶어서 사용)
6. **Phase 1b** — caption_template enum (Phase 6 와 짝)
7. **Phase 5** — shorts 자동 파생 (Phase 0 + Phase 6 둘 다 필요)
8. **Phase 3** — voice design builder
9. **Phase 4** — voice cloning (가장 권리 민감, 마지막)
10. **Phase 1c** — caption split/merge editor (UI 가장 무거움, 수요 확인 후 결정)

가장 먼저 해야 할 일은 **Phase 2a** — 적은 변경으로 1455 가 해결되는지 먼저 확인. 안 되면 2b → 2c 로 escalate. 그래야 시간을 가장 적게 쓰면서 핵심 차단을 푼다.

## 7. 신규/추가 위험 (원본 누락)

| 위험 | 결정 |
|---|---|
| OmniVoice 모델 버전 변경으로 음색 시프트 | `OMNIVOICE_MODEL_REVISION` config 로 핀 — 이전 프로젝트 재현성 보호 |
| Phase 2b/2c 의 batch reload 비용 | 2a 가 충분하면 escalate 안 함 — 비용 측정 후 결정 |
| Phase 0 keyframe 도입 시 두 시스템 공존 버그 | `expand_motion_preset()` 단일 함수가 ground truth, motion 은 alias 만 |
| Phase 1b 의 `caption_style` 이 기존 `subtitle_style.effect` 와 의미 충돌 | `caption_template` 으로 rename |
| Phase 4 voice cloning 권리 문제 | 기본 비활성, upload 시 명시 동의 체크 |
| Phase 5 hook 탐지 V2 (Ollama) 가 source_draft 와 GPU 경합 | gpu_guard 통해 직렬화 (이미 패턴 존재) |
| `ref_text` 누락 시 OmniVoice 동작 미정의 | Whisper 자동 transcription 으로 강제 채움 |
| Phase 2 batch progress aggregation | parent 가 file watch (`tts/_batch_N.done`) + DB poll 합산 |

## 8. 테스트 계획

단위 테스트:

- `expand_motion_preset()` 모든 alias → keyframes (Phase 0)
- caption QA count 케이스 (long/short/missing word) (Phase 1a)
- `caption_template → subtitle_style override` 매핑 (Phase 1b)
- TTS sentence loop cleanup 호출 회수 (Phase 2a)
- pipe protocol parent/child round trip (Phase 2b — implemented 시)
- voice builder → instruct 문자열 (Phase 3)
- ref_audio 길이/형식 검증 (Phase 4)
- shorts hook scoring 함수 (Phase 5)
- template 적용 → 모든 하위 설정 반영 + override 우선순위 (Phase 6)

통합 테스트:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1
python -m pytest tests\test_render_motion.py tests\test_render_plan.py tests\test_subtitle.py tests\test_tts_pipeline.py tests\test_tts_worker.py tests\test_template_registry.py -q
```

실전 검증:

- 30초 / 60초 / 90초 / 180초 실제 TTS — 각 길이에서 1455 발생 여부 측정 (Phase 2a 효과 정량화)
- landscape + shorts 동시 출력 (Phase 5)
- caption QA report 항목 (Phase 1a)
- template `documentary_youtube` 적용 후 autopilot end-to-end (Phase 6)

## 9. 완료 기준

- 1분 이상 실제 OmniVoice TTS 가 안정적으로 성공 (Phase 2a 가 충분하면 단일 subprocess, 부족하면 2b/2c)
- render_plan 에 `keyframes` 가 (option) 반영되며 기존 `motion` 도 그대로 동작
- caption QA report 가 render report 에 포함
- 사용자가 template 하나를 고르면 TTS/자막/모션/이미지 스타일이 일관되게 적용
- longform 에서 shorts 후보가 자동 생성
- voice cloning 은 사용자 명시 업로드만 동작, ref_text 미입력 시 Whisper 자동 채움
- Operator 에서 TTS 실패율, caption QA, render 품질 지표 확인 가능

## 10. 본 plan 의 핵심 변경 (원본 대비)

1. **Phase 2 를 a/b/c 로 escalation** — 단일 subprocess 메모리 정리 → 장기 pipe subprocess → multi-batch. 가장 저렴한 수정부터.
2. **Phase 1 을 1a/1b/1c 로 분할** — 원본 단일 phase 가 너무 광범위.
3. **`motion` 과 `keyframes` 의 단일 source of truth 정의** — `expand_motion_preset()` 함수가 진실, motion 은 alias.
4. **`caption_style` → `caption_template` rename** — 기존 `subtitle_style.effect` 와 의미 분리.
5. **Voice cloning 의 `ref_text` 미입력 시 Whisper 자동 채움** — 이미 통합된 `transcribe.py` 활용.
6. **Shorts hook 탐지 방식 명시** (heuristic V1, Ollama V2).
7. **Template 저장 위치 결정** — 시스템(코드) + 사용자(파일) 분리.
8. **OmniVoice 모델 revision 핀** — 음색 재현성 보호.
9. **Autopilot 와의 통합 명시** — `autopilot_options.template_id` 필드.
10. **arxiv 가짜 링크 제거**.
11. **action_hint 구체 텍스트 명시** (사용자가 보는 1455 안내문).
12. **우선순위 의존성 반영해 재정렬** — Phase 2 → 0 → 1a → 6 → 1b → 5 → 3 → 4 → 1c.
