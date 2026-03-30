# YouTube Shorts MVP — 캐릭터 대화 영상 자동 생성

**Date:** 2026-03-30
**Status:** Approved

## 개요

LangCard Studio에 YouTube Shorts 자동 생성 파이프라인을 추가한다.
언어별 고정 캐릭터 2명이 D-ID 립싱크로 대화하는 15~30초 영상을 생성하고,
YouTube Data API v3로 업로드한다. Instagram 파이프라인과 독립 실행.

## 파이프라인 흐름

```
youtube_shorts.py (CLI 진입점)
  │
  ├─ 1. Claude API → 대화 시나리오 생성 (4~6턴)
  ├─ 2. edge-tts → 턴별 음성 MP3
  ├─ 3. D-ID API → 캐릭터별 립싱크 MP4
  ├─ 4. FFmpeg → 최종 합성 (레이아웃 + 자막 + 전환)
  └─ 5. YouTube Data API → Shorts 업로드
```

## 새로 생성하는 파일

| 파일 | 역할 |
|------|------|
| `youtube_shorts.py` | CLI 진입점 (main.py와 독립) |
| `youtube/__init__.py` | 패키지 초기화 |
| `youtube/scenario_gen.py` | Claude API 대화 시나리오 생성 |
| `youtube/did_client.py` | D-ID API 클라이언트 (립싱크 생성) |
| `youtube/composer.py` | FFmpeg 영상 합성 (레이아웃 + 자막) |
| `youtube/uploader.py` | YouTube Data API v3 업로드 |
| `assets/characters/` | 언어별 고정 캐릭터 이미지 (6장) |

## 기존 인프라 재활용

| 기존 모듈 | 재활용 방식 |
|-----------|-----------|
| `config.py` | TOPIC_CONFIG, LANGUAGES, LANG_CONFIG |
| `renderer/tts_gen.py` | edge-tts 음성 생성 함수 |
| `renderer/fonts.py` | Noto Sans KR 폰트 (자막용) |
| `renderer/themes.py` | 배경 그라디언트 색상 |
| `generator/history.py` | 시나리오 중복 방지 |
| `uploader/cloudinary_up.py` | D-ID용 이미지/음성 임시 업로드 |

## 섹션 1: 대화 시나리오 생성

### 모듈: `youtube/scenario_gen.py`

Claude API(Haiku)로 상황별 대화 시나리오를 JSON으로 생성한다.

### 시나리오 JSON 포맷

```json
{
  "lang": "en",
  "topic": "카페 & 식당",
  "situation": "카페에서 아이스 아메리카노를 주문하는 상황",
  "characters": {
    "A": {"name": "수진", "role": "한국인 학습자", "voice": "en-US-AriaNeural"},
    "B": {"name": "Emma", "role": "원어민 바리스타", "voice": "en-US-JennyNeural"}
  },
  "turns": [
    {"speaker": "A", "text": "Hi, can I get an iced Americano?", "korean": "안녕하세요, 아이스 아메리카노 하나 주세요", "pronunciation": null},
    {"speaker": "B", "text": "Sure! What size would you like?", "korean": "물론이죠! 사이즈 어떤 걸로 하시겠어요?", "pronunciation": null},
    {"speaker": "A", "text": "A large one, please.", "korean": "큰 걸로 주세요", "pronunciation": null},
    {"speaker": "B", "text": "That'll be $4.50. Anything else?", "korean": "4달러 50센트입니다. 다른 거 필요하신 거 있으세요?", "pronunciation": null}
  ],
  "key_expression": "Can I get ~?",
  "key_expression_korean": "~를 주시겠어요?"
}
```

### 설계 포인트

- **턴 수:** 4~6턴 (15~30초 Shorts 적합)
- **화자 A:** 항상 한국인 학습자 — 외국어로 말함 (TTS도 외국어 음성 사용, 약간 다른 음색으로 구분)
- **화자 B:** 원어민 — 자연스럽게 응답
- **핵심 표현:** 대화에서 배울 수 있는 패턴 1개 추출 (영상 마지막 정리)
- **LangCard 연동:** 기존 TOPIC_CONFIG 주제를 상황으로 확장
- **중복 방지:** 기존 history.py 활용 — 같은 상황 반복 안 됨
- **모델:** claude-haiku-4-5-20251001 (비용 최적화, 기존과 동일)

### 중국어/일본어 차이

- 중국어: pronunciation 필드에 병음 포함
- 일본어: pronunciation 필드에 로마자 포함
- 영어: pronunciation null

## 섹션 2: 캐릭터 & 립싱크

### 언어별 고정 캐릭터

| 언어 | 캐릭터 A (한국인) | 캐릭터 B (원어민) |
|------|-----------------|-----------------|
| 영어 | 수진 (여성, 20대) | Emma (여성, 20대 미국인) |
| 중국어 | 민준 (남성, 20대) | 小美 (여성, 20대 중국인) |
| 일본어 | 하은 (여성, 20대) | ゆうき (남성, 20대 일본인) |

- 캐릭터 이미지: AI 생성(DALL-E/Midjourney)으로 1회 제작
- 저장 위치: `assets/characters/{lang}_{role}.png`
  - 예: `en_learner.png`, `en_native.png`, `zh_learner.png`, ...
- 이미지 요건: 정면 얼굴, 중립 표정, 깨끗한 배경 (D-ID 최적 조건)
- Cloudinary에 사전 업로드 → URL 고정 (초기 셋업 시 1회, config.py에 URL 저장)

### D-ID API 클라이언트: `youtube/did_client.py`

```python
def generate_lipsync(character_image_url: str, audio_url: str) -> str:
    """
    1. POST https://api.d-id.com/talks
       - source_url: 캐릭터 이미지 URL (Cloudinary)
       - audio_url: TTS 음성 URL (Cloudinary)
       - config: {
           "stitch": true,
           "result_format": "mp4"
         }

    2. GET /talks/{id} — 폴링 (완료까지 ~10-30초)
       - 2초 간격, 최대 60초 타임아웃

    3. 완료 → result_url에서 MP4 다운로드

    Returns: 로컬 MP4 경로 (output/yt_clips/)
    """
```

### 턴별 처리

- 각 턴마다 개별 D-ID 요청 (짧은 오디오 → 빠른 처리, 정확한 립싱크)
- 턴별 MP4 클립을 FFmpeg로 순차 합성
- D-ID 요청은 캐릭터별로 병렬 가능 (A턴 3개 + B턴 3개 동시)

### 비용

- 한 턴 평균 ~3초 × 6턴, 캐릭터별 말하는 분량만 생성
- A가 3턴(~9초) + B가 3턴(~9초) = ~18초 D-ID 요청
- 비용: ~$0.90/영상, 월 ~$27 (일 1개)

### 폴백

- D-ID 실패 시 → 정적 이미지 + TTS 음성만으로 영상 생성 (기존 릴스 방식)
- API 할당량 소진 시 → 큐에 저장, 다음 실행 시 재시도

## 섹션 3: FFmpeg 영상 합성

### 모듈: `youtube/composer.py`

### 영상 레이아웃 (1080×1920)

```
┌──────────────────────┐
│   📚 오늘의 영어회화   │  ← 상단 타이틀 바 (80px)
│   카페에서 주문하기    │     배경: 테마 색상
├──────────────────────┤
│                      │
│   ┌──────────────┐   │  ← 말하는 캐릭터 영상 (720×720)
│   │              │   │     중앙 배치
│   │  립싱크 영상   │   │     말하는 캐릭터만 표시
│   │              │   │
│   └──────────────┘   │
│                      │
│   ┌──────────────┐   │  ← 대사 자막 영역
│   │  외국어 대사   │   │     큰 글씨, 흰색
│   │  한국어 번역   │   │     작은 글씨, 회색
│   └──────────────┘   │
│                      │
│  ━━━━━━━━━━━━━━━━━━  │  ← 진행 바 (현재 턴 / 전체)
└──────────────────────┘
```

### 턴 전환

- A가 말할 때 → A 캐릭터 립싱크 영상 표시
- B가 말할 때 → B 캐릭터 립싱크 영상으로 전환
- 전환 시 0.3초 크로스페이드

### 마지막 장면 (3초)

```
┌──────────────────────┐
│                      │
│   💡 오늘의 핵심표현   │
│                      │
│   "Can I get ~?"     │  ← 핵심 패턴 강조
│   ~를 주시겠어요?     │
│                      │
│   좋아요 & 구독 🔔    │  ← CTA
└──────────────────────┘
```

마지막 카드는 Pillow로 렌더링 → 3초 정적 프레임.

### FFmpeg 합성 단계

1. 턴별 립싱크 MP4 클립 준비 (D-ID 출력)
2. 각 클립에 배경 + 타이틀 바 합성 (overlay filter)
3. 자막 오버레이 (drawtext filter, Noto Sans KR)
4. 진행 바 오버레이 (drawbox filter)
5. 턴 간 크로스페이드 전환 (xfade filter, 0.3초)
6. 마지막 핵심표현 카드 (Pillow PNG → 3초 영상)
7. 전체 concat → 최종 MP4

### 인코딩 설정

- 코덱: libx264
- CRF: 18 (YouTube 권장 고품질)
- 프레임레이트: 30fps
- 픽셀 포맷: yuv420p
- 오디오: AAC, 128kbps
- 해상도: 1080×1920

## 섹션 4: YouTube 업로드

### 모듈: `youtube/uploader.py`

### OAuth 2.0 인증

- 최초 1회: 브라우저에서 Google OAuth 동의 → `token.json` 저장
- 이후 자동: refresh token으로 갱신
- `.env` 추가 키: `YOUTUBE_CLIENT_SECRET_FILE` (OAuth 클라이언트 비밀 JSON 경로)

### 업로드 메타데이터

```python
{
    "title": "[🇺🇸영어] 카페에서 주문하기 — Can I get ~? #Shorts",
    "description": (아래 참조),
    "tags": ["영어회화", "영어공부", "일상영어", "카페영어", "LangCard", "Shorts"],
    "categoryId": "27",  # Education
    "privacyStatus": "public",
    "madeForKids": False,
    "selfDeclaredMadeForKids": False,
}
```

### 설명란 포맷

```
☕ 카페에서 아이스 아메리카노 주문하기

📝 대화 스크립트
수진: Hi, can I get an iced Americano?
      (안녕하세요, 아이스 아메리카노 하나 주세요)
Emma: Sure! What size would you like?
      (물론이죠! 사이즈 어떤 걸로 하시겠어요?)
수진: A large one, please.
      (큰 걸로 주세요)
Emma: That'll be $4.50. Anything else?
      (4달러 50센트입니다. 다른 거 필요하신 거 있으세요?)

💡 핵심표현: Can I get ~? (~를 주시겠어요?)

#영어회화 #영어공부 #일상영어 #Shorts
```

### 제목 규칙

- 포맷: `[{국기}{언어}] {상황} — {핵심표현} #Shorts`
- 60자 이내
- 핵심 키워드 앞배치

### API 할당량

- YouTube Data API: 10,000 유닛/일
- 업로드 1회: ~1,600 유닛
- 하루 3개(언어별) 업로드: ~4,800 유닛 → 여유 있음

## 섹션 5: CLI & 실행

### 진입점: `youtube_shorts.py`

```bash
# 기본 실행 (오늘 주제, 3개 언어)
python youtube_shorts.py

# 특정 언어만
python youtube_shorts.py --lang en

# 드라이런 (영상 생성만, 업로드 안 함)
python youtube_shorts.py --dry-run

# 주제 지정
python youtube_shorts.py --topic cafe
```

### 실행 흐름

```python
def main():
    1. 폰트 확인 (fonts.ensure_fonts())
    2. 큐 확인 (youtube_queue.json → 재시도 대상)
    3. for lang in langs:
        a. 대화 시나리오 생성 (scenario_gen)
        b. 턴별 TTS 음성 생성 (tts_gen)
        c. 음성 Cloudinary 업로드 (cloudinary_up)
        d. D-ID 립싱크 생성 (did_client)
        e. FFmpeg 합성 (composer)
        f. YouTube 업로드 (uploader) — dry-run이면 건너뜀
    4. 임시 파일 정리
```

### 에러 처리 & 큐

- 실패 시 → `output/youtube_queue.json`에 저장
- 다음 실행 시 큐 먼저 처리 → 재시도
- 3회 실패 → 포기 (로그 남김)
- 기존 `story_dispatcher.py`의 큐 패턴과 동일

### main.py와의 관계

- 완전 독립 실행 (별도 CLI)
- 공유 자원: config.py, fonts.py, tts_gen.py, cloudinary_up.py, history.py
- 나중에 main.py에서 `--youtube` 플래그로 통합 가능

## 환경 설정 추가

### .env 추가 키

```
DID_API_KEY=your_d-id_api_key
YOUTUBE_CLIENT_SECRET_FILE=client_secret.json
```

### requirements.txt 추가

```
google-auth-oauthlib>=1.0.0
google-auth-httplib2>=0.2.0
google-api-python-client>=2.0.0
requests>=2.31.0  # (이미 있음, D-ID API용)
```

### config.py 추가

```python
# YouTube Shorts 설정
YOUTUBE_CONFIG = {
    "category_id": "27",  # Education
    "privacy_status": "public",
    "made_for_kids": False,
}

# 언어별 YouTube 해시태그
YOUTUBE_HASHTAGS = {
    "en": ["영어회화", "영어공부", "일상영어", "LearnEnglish", "DailyEnglish"],
    "zh": ["중국어회화", "중국어공부", "일상중국어", "学中文", "ChineseLearning"],
    "ja": ["일본어회화", "일본어공부", "일상일본어", "日本語勉強", "LearnJapanese"],
}

# 캐릭터 설정
YOUTUBE_CHARACTERS = {
    "en": {
        "A": {"name": "수진", "role": "한국인 학습자", "image": "assets/characters/en_learner.png"},
        "B": {"name": "Emma", "role": "원어민", "image": "assets/characters/en_native.png"},
    },
    "zh": {
        "A": {"name": "민준", "role": "한국인 학습자", "image": "assets/characters/zh_learner.png"},
        "B": {"name": "小美", "role": "원어민", "image": "assets/characters/zh_native.png"},
    },
    "ja": {
        "A": {"name": "하은", "role": "한국인 학습자", "image": "assets/characters/ja_learner.png"},
        "B": {"name": "ゆうき", "role": "원어민", "image": "assets/characters/ja_native.png"},
    },
}
```

## 비용 요약

| 항목 | 영상 1개 | 월 (일 1개) |
|------|---------|-----------|
| Claude API (Haiku) | ~$0.01 | ~$0.30 |
| edge-tts | 무료 | 무료 |
| D-ID 립싱크 | ~$0.90 | ~$27 |
| Cloudinary | 기존 | 기존 |
| YouTube API | 무료 | 무료 |
| **합계** | **~$0.91** | **~$27** |

## 제약 사항 & 향후 확장

### MVP 제약

- 캐릭터 이미지는 수동 제작 (1회)
- 영상 레이아웃 고정 (커스터마이즈 미지원)
- 썸네일 자동 생성 미포함 (YouTube 자동 선택)

### 향후 확장 가능

- 캐릭터 교체/추가 (config만 수정)
- D-ID → Hedra/SadTalker 교체 (did_client.py만 교체)
- main.py 통합 (`--youtube` 플래그)
- 썸네일 자동 생성 (Pillow)
- 배경음악 추가
- GitHub Actions 스케줄링
