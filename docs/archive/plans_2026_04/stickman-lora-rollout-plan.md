# Stickman LoRA Rollout Plan

## 2026-04-27 Relevance Review

Latest user review found that generated images still do not reliably match the sentence, context, or even core keyword. The next work round is therefore moved to:

- `visual-relevance-recovery-plan.md`

Important correction:

- Stickfigures LoRA is installed and was used, but LoRA only affects style.
- The current prompt layer can still choose the wrong subject/action/prop.
- The latest Korean sample reused media from older batch projects, so the visuals were not generated from the active Korean script.
- Next priority is not more LoRA tuning. It is sentence/script binding, clean Korean keyword fixtures, structured visual briefs, candidate generation, and a render preflight relevance gate.

상태: `[Verified - LoRA installed and single workflow generation succeeded]`

## 확인 완료

- LoRA 파일 설치 완료:
  - `C:\Users\petbl\autotube\ComfyUI\models\loras\Stickfigures-000005.safetensors`
  - size: `228,462,156` bytes
- Trigger hints:
  - `Flipchartvisu`
  - `Stick figure`
- ComfyUI LoRA workflow 실사용 검증 완료:
  - workflow: `txt2img_sdxl_stickman_lora`
  - prompt id: `7fe0ec6a-f031-45d0-a585-767f1e5afc3b`
- output:
  - `C:\Users\petbl\autotube\ComfyUI\output\lora_verify_stickman_00001_.png`

## 2026-04-27 Batch Checkpoint

- representative LoRA batch generation completed:
  - project: `b609e71caad0`
  - project dir: `C:\Users\petbl\newauto\storage\projects\b609e71caad0`
  - manifest: `image_prompts_manifest.json`
  - summary: `stickman_lora_batch_summary.json`
  - imported media: 8 images
- reusable batch script added:
  - `scripts/run_stickman_lora_batch.py`
- LoRA-aware smoke helper updated:
  - `scripts/check_comfyui_smoke.py` now accepts `--lora-name` and `--lora-strength`
- focused hard-scene sweep completed:
  - project: `6eca26cb33be`
  - sentence indices: `1, 3, 6`
  - variants per scene: `3`
  - total candidates: `9`

## First Visual Findings

좋았던 점:
- giant battle은 더 이상 "개미 같은 실루엣"이 아니라 명확한 stick figure로 읽힌다.
- prayer도 선형 인체 형태가 분명해서 base SDXL보다 훨씬 일관적이다.
- storm scene도 단일 주인공 중심 읽힘은 유지된다.

아쉬운 점:
- money choice는 돈/갈림길보다 pose variation 쪽으로 샌다.
- prayer는 기도보다는 명상/yoga처럼 보일 여지가 있다.
- storm_fear는 파도보다 비/배경선 중심으로 표현돼서 "폭풍 앞 공포"가 약하다.
- 일부 템플릿은 oversized prop이 충분히 크게 안 잡힌다.

## Immediate Next Tuning

1. `money_choice`
   - fork road를 더 직접적으로 강조
   - money prop를 "single oversized bill held clearly in front"로 강화
2. `prayer`
   - hands clasped / kneeling / head bowed를 더 강하게 고정
3. `storm_fear`
   - oversized wave ahead / tiny hero facing wave 구조를 positive_core에 직접 삽입
4. 전체 공통
   - white background + centered hero + single prop 고정 강화
   - 불필요한 자세 다양성 감소
5. hard scene selection
   - `prayer`, `money_choice`, `storm_fear`는 single render보다 multi-seed selection이 더 효율적이므로 best-of-3 선택 루프를 기본 전략으로 본다

## 이제 달라진 점

- 더 이상 "LoRA 준비 단계"가 아니다.
- 다음 라운드부터는 base SDXL 임시 보정이 아니라, 실제 Stickfigures LoRA 기준으로 프롬프트/템플릿/배치 품질을 조정해야 한다.
- 운영 화면에서도 `Stickfigures LoRA` 준비 여부를 확인할 수 있으므로, 누락 상태를 바로 감지할 수 있다.

## 다음 작업 목표

1. LoRA 기준 샘플 배치 검증
2. base SDXL 대비 품질 비교 기준 고정
3. 1~2분 한국어 영상용 장면 세트 재생성
4. 최종 E2E 렌더까지 연결

## Phase 1. LoRA 샘플 배치 검증

목표:
- 대표 장면 6~8개를 LoRA 기준으로 다시 생성
- "개미처럼 작아 보이는 문제"가 실제로 줄었는지 눈으로 확인

대표 장면:
- giant_battle
- prayer
- time_pressure
- money_choice
- temptation
- recovery
- storm_fear
- study_focus

작업:
- 같은 checkpoint, 같은 seed 규칙으로 LoRA on/off 비교
- sentence별 `template_key`, prompt, output path를 manifest에 남김
- 결과를 보고 template별 positive/negative를 1회 더 조정

완료 기준:
- 최소 6장 이상에서 단일 주인공 silhouette가 분명히 보일 것
- oversized prop/action readability가 base SDXL보다 나아질 것

## Phase 2. Prompt / Template 재조정

목표:
- LoRA가 들어온 상태에 맞춰 prompt를 더 짧고 세게 정리

작업:
- `trigger hint Stick figure` + `Flipchartvisu` 실제 효과 비교
- template별 불필요한 scenic token 제거
- negative prompt를 crowd / tiny subject / realistic scene 중심으로 더 강하게 분리

우선 조정 대상:
- giant_battle: giant vs hero scale contrast
- prayer: kneeling pose clarity
- temptation: forbidden object visibility
- storm_fear: wave/rain dominance

완료 기준:
- 템플릿별 장면 의도가 1장만 봐도 읽힐 것

## Phase 3. 한국어 1~2분 샘플 영상 재생성

목표:
- 한국어 대본 + fixed seed TTS + Stickfigures LoRA 이미지로 새 샘플 MP4 생성

작업:
- 1~2분 길이 한국어 대본 선택
- 이미지 6~10장 LoRA 기준 재생성
- scene_plan / render_plan rebuild
- 최종 `output.mp4` 렌더

검증:
- TTS voice consistency 유지
- generated image resolution 확인
- render report, QA frame, ffprobe 확인

완료 기준:
- 사람이 봤을 때 "스틱맨 주인공이 분명하다"고 말할 수 있는 최종 영상 1개

## Phase 4. 오토파일럿 연결 마감

목표:
- URL / keyword / script 입력 후 LoRA 기반 이미지 경로까지 자동으로 타게 만들기

작업:
- autopilot image queue 기본값에 `lora_name` 옵션 넣기
- visual_source_mode가 `comfyui_auto`일 때 stickman workflow 기본화 여부 결정
- debug log에 `template_key`, `lora_name`, `lora_strength` 노출

완료 기준:
- 수동 입력 없이도 autopilot에서 LoRA 이미지 큐까지 자연스럽게 이어질 것

## 권장 진행 순서

1. focused sweep 결과에서 hard scene 후보 선택
2. 선택된 이미지로 1~2분 한국어 샘플 영상 재생성
3. autopilot LoRA 기본 연결
4. 필요 시 hard scene만 best-of-3 재시도

## 한 줄 결론

이제 병목은 "설치"가 아니라 "실물 품질 튜닝"이다. 다음 라운드는 LoRA 기준 샘플 비교와 실제 한국어 영상 재생성에 집중하면 된다.
