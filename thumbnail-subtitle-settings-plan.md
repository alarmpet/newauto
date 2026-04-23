# 썸네일 업로드 및 자막 스타일 설정 기능 구현 계획서

## 목표

현재 앱의 미디어 업로드는 렌더 영상에 들어갈 이미지/영상만 관리한다. 다음 단계에서는 YouTube 업로드용 썸네일을 별도로 업로드하고, 렌더링 단계에서 자막 색상, 크기, 위치, 외곽선, 그림자, 배경, 효과를 프로젝트별로 설정할 수 있게 만든다.

핵심 목표는 다음과 같다.

- 일반 미디어와 독립된 썸네일 업로드/미리보기/삭제 기능 제공
- 프로젝트별 자막 스타일 설정 저장
- 렌더 시 설정값을 실제 영상 자막에 반영
- YouTube 업로드 시 썸네일이 있으면 `thumbnails.set` API로 자동 반영
- 기존 프로젝트와 기존 렌더 흐름은 깨지지 않도록 기본값 유지

## 현재 구조 요약

- 일반 미디어 업로드:
  - API: `POST /api/projects/{pid}/media`
  - 저장 위치: `storage/projects/{pid}/media/`
  - DB 필드: `media_order`
- 자막 생성:
  - `app/services/subtitle.py`
  - 현재는 SRT 파일만 생성
- 렌더 합성:
  - `app/services/render.py`
  - FFmpeg `subtitles=` 필터로 SRT를 입힘
- YouTube 업로드:
  - `app/services/yt_upload.py`
  - 현재는 영상 업로드만 처리

## 권장 설계

### 1. 썸네일 저장 방식

썸네일은 일반 미디어와 분리한다.

```text
storage/projects/{pid}/
├─ media/
├─ tts/
├─ thumbnail/
│  └─ thumbnail.jpg
├─ audio.wav
├─ subtitles.ass
└─ output.mp4
```

허용 확장자는 우선 YouTube 호환 중심으로 제한한다.

- `.jpg`
- `.jpeg`
- `.png`
- `.webp`

업로드 시 내부 저장명은 `thumbnail{ext}` 로 고정한다. 새 썸네일을 올리면 기존 썸네일은 삭제하고 교체한다.

### 2. DB 변경

`projects` 테이블에 아래 컬럼을 추가한다.

```sql
thumbnail_file TEXT NOT NULL DEFAULT ''
subtitle_style TEXT NOT NULL DEFAULT '{}'
```

`thumbnail_file` 은 현재 썸네일 파일명만 저장한다.

`subtitle_style` 은 JSON 문자열로 저장한다. 초기 기본값은 서버에서 merge 해서 사용한다.

예시:

```json
{
  "font_family": "Malgun Gothic",
  "font_size": 48,
  "primary_color": "#FFFFFF",
  "outline_color": "#000000",
  "background_color": "#000000",
  "background_opacity": 0,
  "outline_width": 2,
  "shadow": 1,
  "position": "bottom",
  "margin_v": 80,
  "max_line_chars": 40,
  "effect": "none"
}
```

### 3. 타입 변경

`app/types.py` 에 타입을 추가한다.

```python
SubtitlePosition = Literal["top", "middle", "bottom"]
SubtitleEffect = Literal["none", "fade", "pop", "karaoke"]

class SubtitleStyle(TypedDict, total=False):
    font_family: str
    font_size: int
    primary_color: str
    outline_color: str
    background_color: str
    background_opacity: float
    outline_width: int
    shadow: int
    position: SubtitlePosition
    margin_v: int
    max_line_chars: int
    effect: SubtitleEffect
```

`ProjectRecord`, `ProjectStatus` 에 아래 필드를 추가한다.

```python
thumbnail_file: str
subtitle_style: SubtitleStyle
```

## API 설계

### 썸네일 API

#### 업로드

```http
POST /api/projects/{pid}/thumbnail
Content-Type: multipart/form-data
```

필드:

- `file`: 이미지 파일 1개

응답:

```json
{
  "project": {},
  "thumbnail_url": "/api/projects/{pid}/thumbnail"
}
```

검증:

- 이미지 확장자만 허용
- 파일 1개만 허용
- 너무 큰 파일 제한 권장: 5MB 또는 10MB
- YouTube 권장 규격 안내: 1280x720, 16:9, 2MB 이하 권장

#### 조회

```http
GET /api/projects/{pid}/thumbnail
```

썸네일 파일이 없으면 `404`.

#### 삭제

```http
DELETE /api/projects/{pid}/thumbnail
```

파일 삭제 후 `thumbnail_file` 을 빈 문자열로 업데이트한다.

### 자막 스타일 API

#### 저장

```http
PUT /api/projects/{pid}/subtitle-style
Content-Type: application/json
```

요청 예시:

```json
{
  "font_size": 54,
  "primary_color": "#FFE66D",
  "outline_color": "#101010",
  "outline_width": 3,
  "shadow": 2,
  "position": "bottom",
  "margin_v": 96,
  "effect": "fade"
}
```

응답:

```json
{
  "project": {},
  "effective_style": {}
}
```

검증:

- 색상은 `#RRGGBB` 만 허용
- 폰트 크기는 예: `24~96`
- opacity는 `0~1`
- position/effect는 허용된 값만 저장
- 알 수 없는 키는 무시하거나 400 처리

#### 기본값 조회

프로젝트 조회 응답에 `subtitle_style` 을 포함하면 별도 GET 없이 UI 초기화 가능하다.

필요하면 아래 API도 추가한다.

```http
GET /api/projects/{pid}/subtitle-style
```

## 렌더링 설계

### SRT에서 ASS로 전환

자막 스타일을 제대로 제어하려면 SRT보다 ASS가 적합하다. SRT는 텍스트와 시간 정보 위주이고, 색상/위치/외곽선/그림자/효과 제어가 제한적이다.

변경 방향:

- 기존 `write_srt()` 는 유지
- 새 `write_ass(timings, out_path, style)` 추가
- 렌더에서는 `subtitles.ass` 를 생성하고 FFmpeg `ass=` 필터 또는 `subtitles=` 필터로 입힘

예상 파일:

- `app/services/subtitle.py`
  - `DEFAULT_SUBTITLE_STYLE`
  - `normalize_subtitle_style()`
  - `write_ass()`
  - `write_srt()` 는 기존 호환용 유지

### ASS 스타일 매핑

ASS 색상은 `&HAABBGGRR` 형식이므로 `#RRGGBB` 를 변환해야 한다.

예:

- `#FFFFFF` → `&H00FFFFFF`
- `#FFE66D` → `&H006DE6FF`

position 매핑:

- `top` → ASS Alignment `8`
- `middle` → ASS Alignment `5`
- `bottom` → ASS Alignment `2`

주요 매핑:

- `font_family` → `Fontname`
- `font_size` → `Fontsize`
- `primary_color` → `PrimaryColour`
- `outline_color` → `OutlineColour`
- `background_color` + `background_opacity` → `BackColour`
- `outline_width` → `Outline`
- `shadow` → `Shadow`
- `margin_v` → `MarginV`

### 효과 처리

1차 구현은 렌더 안정성을 우선해 아래 범위로 제한한다.

- `none`: 일반 자막
- `fade`: 각 문장에 `{\fad(120,120)}` 태그 삽입
- `pop`: `{\fscx105\fscy105}` 정도의 정적 강조로 시작

`karaoke` 는 문장 단위 타이밍만 있는 현재 구조에서는 정확도가 떨어질 수 있다. 단어 단위 타이밍이 생긴 뒤 2차 기능으로 분리하는 것이 좋다.

## UI 설계

### Media 단계

현재 `2. Media` 화면 안에 썸네일 카드 영역을 추가한다.

구성:

- `Thumbnail` 섹션
- 썸네일 업로드 버튼
- 현재 썸네일 미리보기
- 권장 규격 안내
- 삭제 버튼

예시 UI 문구:

- “YouTube 썸네일”
- “영상에 들어가는 미디어와 별도로 업로드됩니다.”
- “권장: 1280x720, 16:9, JPG/PNG, 2MB 이하”

### Render 단계

현재 `4. Render` 화면에 `Subtitle Style` 패널을 추가한다.

입력 항목:

- 글꼴 선택: 기본 `Malgun Gothic`
- 크기: range 또는 number
- 글자색: color input
- 외곽선 색: color input
- 외곽선 두께: range
- 그림자: range
- 위치: top/middle/bottom
- 아래/위 여백: number 또는 range
- 배경색: color input
- 배경 투명도: range
- 효과: none/fade/pop
- 미리보기 박스

저장 방식:

- 값 변경 후 `Save subtitle style` 버튼
- 또는 debounce 자동 저장

1차 구현은 명시 저장 버튼이 안전하다.

## YouTube 업로드 연동

`app/services/yt_upload.py` 에 썸네일 반영 단계를 추가한다.

흐름:

1. 영상 업로드 완료
2. `video_id` 확보
3. 프로젝트에 `thumbnail_file` 이 있으면 썸네일 경로 확인
4. YouTube API `youtube.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(...))`
5. 실패해도 영상 업로드 자체는 완료로 둘지, 경고 상태를 따로 둘지 결정

권장:

- 1차 구현에서는 영상 업로드는 `done` 으로 처리
- 썸네일 실패는 로그와 `upload_error` 필드 추가 또는 기존 상태 메시지에 남김

현재 DB에는 `upload_error` 가 없으므로, 필요하면 추가한다.

```sql
upload_error TEXT NOT NULL DEFAULT ''
```

## 구현 단계

### Phase 1. 백엔드 데이터 모델

- `app/db.py`
  - `thumbnail_file`, `subtitle_style` 컬럼 추가
  - migration 추가
  - `_row_to_project()` 에 필드 추가
  - `update_project()` 에 JSON 직렬화 대상 `subtitle_style` 추가
- `app/types.py`
  - `SubtitleStyle` 관련 타입 추가
  - `ProjectRecord`, `ProjectStatus` 확장
- 테스트
  - 기존 DB에도 새 컬럼이 자동 추가되는지 확인
  - 기본 subtitle style이 merge 되는지 확인

### Phase 2. 썸네일 API

- `app/routers/projects.py`
  - `POST /{pid}/thumbnail`
  - `GET /{pid}/thumbnail`
  - `DELETE /{pid}/thumbnail`
  - 파일 저장/교체/삭제 유틸 추가
- 테스트
  - 정상 업로드
  - 기존 썸네일 교체
  - 비이미지 거부
  - 삭제 후 404

### Phase 3. 자막 스타일 API

- `app/routers/projects.py` 또는 새 `app/routers/subtitle.py`
  - `PUT /{pid}/subtitle-style`
  - optional `GET /{pid}/subtitle-style`
- `app/services/subtitle.py`
  - 스타일 검증/정규화 함수 추가
- 테스트
  - 유효한 스타일 저장
  - 잘못된 색상/크기/위치 거부
  - 일부 필드만 저장해도 기본값과 merge

### Phase 4. ASS 자막 렌더링

- `app/services/subtitle.py`
  - `write_ass()` 구현
  - `#RRGGBB` → ASS 색 변환
  - position/effect 반영
- `app/services/render.py`
  - `subtitles.srt` 대신 `subtitles.ass` 생성
  - FFmpeg 필터를 ASS 호환으로 변경
- 테스트
  - ASS 파일 내용에 스타일 필드가 반영되는지 확인
  - 렌더 명령 구성 테스트

### Phase 5. 프런트엔드 UI

- `app/static/index.html`
  - Media 단계에 썸네일 패널 추가
  - Render 단계에 자막 스타일 설정 패널 추가
- `app/static/app.js`
  - Project 타입 주석 확장
  - 썸네일 업로드/삭제/미리보기 로직 추가
  - subtitle style 상태 로드/저장 로직 추가
  - 미리보기 박스 실시간 반영
- `app/static/style.css`
  - thumbnail card
  - subtitle controls
  - preview caption style
- 테스트
  - `npx tsc -p tsconfig.json`

### Phase 6. YouTube 썸네일 연동

- `app/services/yt_upload.py`
  - 영상 업로드 완료 후 썸네일 업로드 추가
- 테스트
  - mock YouTube client로 `thumbnails().set()` 호출 확인
  - 썸네일 없는 프로젝트는 기존처럼 동작 확인

## 우선순위

1. DB/타입 확장
2. 썸네일 업로드 API
3. 자막 스타일 저장 API
4. ASS 자막 렌더 반영
5. UI 패널 추가
6. YouTube 썸네일 자동 반영

이 순서가 좋은 이유는 백엔드 저장 구조가 먼저 안정되어야 UI와 렌더링을 안전하게 붙일 수 있기 때문이다.

## 리스크 및 대응

- FFmpeg ASS 경로 이스케이프 문제:
  - Windows 경로의 `:` 와 `\` 처리를 테스트해야 한다.
- 한글 폰트 문제:
  - 기본값은 Windows 기본 한글 폰트인 `Malgun Gothic` 으로 둔다.
- YouTube 썸네일 제한:
  - 파일 크기/비율 안내와 사전 검증이 필요하다.
- 자막 효과 과욕:
  - 1차는 `none/fade/pop` 까지만 구현하고 karaoke는 보류한다.
- 기존 프로젝트 호환성:
  - migration과 기본값 merge 로 해결한다.

## 완료 기준

- 썸네일을 별도로 업로드, 조회, 삭제할 수 있다.
- 일반 미디어 순서와 썸네일은 서로 영향을 주지 않는다.
- 프로젝트별 자막 스타일을 저장하고 다시 열었을 때 유지된다.
- 렌더된 영상에 설정한 자막 색상, 크기, 위치, 외곽선, 그림자가 반영된다.
- `fade` 효과가 선택된 경우 렌더 결과 자막에 반영된다.
- YouTube 업로드 시 썸네일이 있으면 자동으로 설정된다.
- 기존 테스트와 타입체크가 통과한다.

검증 명령:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\typecheck.ps1
.\omnivoice_env\Scripts\python.exe -m unittest discover -s tests -v
```
