# Stickman Reference Prompt Plan

상태: `[Implemented - reference library scaffold added]`

목표:

- 스틱맨이 멀리 보이는 실루엣이나 개미처럼 흐르는 문제를 줄인다.
- 문장 전체를 설명문처럼 넣는 대신, 레퍼런스 기반 템플릿으로 장면을 조립한다.
- 나중에 LoRA를 붙이더라도 지금 구조를 그대로 재사용할 수 있게 한다.

## 외부 참고 자료

1. Civitai Stickfigures SDXL LoRA  
   https://civitai.green/models/700803/stickfigures  
   - SDXL 1.0 기반 stick figure LoRA
   - Trigger words: `Flipchartvisu`, `Stick figure`

2. Civitai SDXL prompt phrasing guide  
   https://civitai.red/articles/3847/how-to-phrase-your-sdxl-prompts  
   - SDXL은 긴 설명문보다 짧은 키워드 묶음이 더 잘 먹는다는 방향
   - 키워드 순서가 중요하다는 점 참고

3. Civitai prompt guide PDF  
   https://assets-global.website-files.com/68060174d5c5548774c431f2/680ecd155378b7b440e2529b_xudotinepebenagikife.pdf  
   - Topic / Camera Angle / Style / Focus / Lighting / Refined details 구조 참고

## 이번에 반영한 구조

- `app/services/stickman_reference_library.py`
  - 외부 레퍼런스 목록 보관
  - 장면 카테고리별 템플릿 보관
- `app/services/image_prompting.py`
  - 문장 키워드에 따라 템플릿 선택
  - `trigger hint Stick figure` 포함
  - `template_key`, `reference_names`를 prompt payload에 함께 저장
  - manifest에도 reference library 포함

## 현재 템플릿

- `default`
  - 일반 설명형 장면
- `giant_battle`
  - 거인, 돌, 물매, 대결 장면
- `prayer`
  - 기도, 무릎 꿇기, 빛
- `time_pressure`
  - 시계, 시간 압박, 달리기
- `money_choice`
  - 돈, 갈림길, 선택

## 현재 판단

- UTF-8 파일/API 입력 경로에서는 한국어 키워드 매칭이 정상 동작한다.
- PowerShell 인라인 한글은 진단용으로는 신뢰하기 어렵다.
- SDXL base만으로도 방향은 잡히지만, 단일 주인공 집중도를 더 높이려면 LoRA 적용이 유리하다.
- 코드 기준으로는 LoRA를 붙일 준비가 끝났다.
  - `txt2img_sdxl_stickman_lora.json`
  - `lora_name`, `lora_strength` route 옵션
  - `scripts/install_stickfigures_lora.ps1`

## LoRA 설치 상태

- Civitai `Stickfigures` 모델은 현재 공개 메타데이터 조회는 가능하지만, 실제 파일 다운로드는 로그인된 세션 또는 API 토큰이 필요하다.
- 설치 스크립트:
  - `powershell -ExecutionPolicy Bypass -File .\scripts\install_stickfigures_lora.ps1`
- 지원 방식:
  - `CIVITAI_API_TOKEN` 환경변수 사용
  - 또는 `-Token "..."` 파라미터 직접 전달
- 토큰이 없을 때는 왜 막히는지 안내하고 중단하도록 해두었다.

## 다음 권장 순서

1. `CIVITAI_API_TOKEN` 설정 후 `install_stickfigures_lora.ps1` 실행
2. 템플릿 4개를 10~12개로 확장
3. 실제 자주 쓰는 주제 기준으로 템플릿 세분화
   - 기도
   - 실패 후 재도전
   - 시간 압박
   - 돈/유혹
   - 갈림길/선택
   - 거인/도전
4. 템플릿별 샘플 이미지 한 장씩 고정 검수본 저장

## 완료 기준

- 같은 문장군에서 스틱맨이 배경 실루엣으로 흐르지 않는다.
- 단일 주인공, 단일 행동, 큰 소품이 일관되게 보인다.
- `image_prompts_manifest.json`만 봐도 어떤 템플릿/레퍼런스를 썼는지 추적 가능하다.
## 2026-04-27 Additional Update

- Template coverage now includes `temptation`, `recovery`, `storm_fear`, and `study_focus`.
- Step 2 image panel now exposes `LoRA Name` and `LoRA Strength` directly in the UI.
- Prompt suggestion status now shows the selected `template_key`.
- Operator model status now exposes a dedicated `Stickfigures LoRA` readiness row.
