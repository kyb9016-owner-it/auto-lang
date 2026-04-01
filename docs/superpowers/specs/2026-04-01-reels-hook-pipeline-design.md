# Reels HOOK Pipeline Design

> 기존 7초 Short Reels를 15초 HOOK형 릴스로 교체하는 파이프라인 리디자인.

## 1. 개요

### 변경 목적
- 기존: 3개국어 × 표현+어휘 카드 = 6장 + 3개 릴스 (7초)
- 변경: 슬롯당 1개국어 × HOOK/WRONG→RIGHT/CTA = 3장 + 1개 릴스 (15초)
- "틀린 표현 → 올바른 표현" 구조로 도파민형 숏폼 콘텐츠 제작

### 접근법
기존 파이프라인(main.py 8단계) 내부 수정. 인프라(edge-tts, ffmpeg, Cloudinary, Instagram API) 100% 재사용.

## 2. 슬롯-언어 매핑

| 슬롯 | 시간 (KST) | 언어 | 주제 |
|------|-----------|------|------|
| morning | 08:00 | 영어 (en) | 일상생활 표현 |
| lunch | 12:00 | 중국어 (zh) | 일상생활 표현 |
| evening | 20:00 | 일본어 (ja) | 일상생활 표현 |

- 슬롯별 주제 구분 없음. 3개 슬롯 모두 "실생활에서 자주 틀리는 표현" 주제.
- `config.py`에 `SLOT_LANG_MAP = {"morning": "en", "lunch": "zh", "evening": "ja"}` 추가.

## 3. 콘텐츠 생성 (claude_gen.py 확장)

### Claude API 출력 구조

```json
{
  "hook": "이거 영어로 말하면 99%가 틀림",
  "wrong": "I am boring",
  "right": "I am bored",
  "right_ko": "나 지루해",
  "pronunciation": null,
  "tts_parts": {
    "intro": "많은 사람들이 이렇게 말합니다",
    "bridge": "하지만 올바른 표현은",
    "outro": "나 지루해"
  },
  "subtitle_lines": [
    "99%가 틀리는 영어 표현",
    "❌ I am boring",
    "→ 나는 지루한 사람이야",
    "✅ I am bored",
    "→ 나 지루해"
  ],
  "cta": "이거 몰랐으면 저장 👆"
}
```

필드 설명:
- `hook`: HOOK 카드 텍스트. 1초 안에 스크롤을 멈추게 하는 한국어 문장.
- `wrong`: 한국인이 실제로 자주 하는 실수 표현 (타겟 언어).
- `right`: 원어민이 자연스럽게 쓰는 올바른 표현 (타겟 언어).
- `right_ko`: RIGHT의 한국어 뜻.
- `pronunciation`: 중국어=병음, 일본어=로마자, 영어=null.
- `tts_parts`: 한국어 나레이션 조각들 (타겟 언어 발음 사이에 삽입).
- `subtitle_lines`: 화면에 순차 표시할 자막 배열.
- `cta`: 저장/댓글 유도 문구.

### 프롬프트 검증 조건
- WRONG이 실제로 흔한 실수인지 (억지 오류 금지)
- RIGHT가 원어민 기준으로 자연스러운 표현인지
- WRONG과 RIGHT의 차이가 학습 가치가 있는지 (너무 사소한 차이 금지)

## 4. 카드 렌더링 (card.py 확장)

기존 Pillow 렌더러에 HOOK형 카드 3장 렌더 함수 추가.

### 카드 1 — HOOK (2초)
- 배경: 슬롯 테마 그라데이션 (기존 재사용)
- 중앙에 HOOK 텍스트 (한국어, 큰 볼드)
- 예: "이거 영어로 말하면 99%가 틀림"

### 카드 2 — WRONG → RIGHT (10초)
- 상단: ❌ 틀린 표현 (빨간 계열, 취소선)
- 하단: ✅ 올바른 표현 (초록 계열, 강조)
- 한국어 뜻 + 발음(중/일) 표시
- TTS가 이 구간에서 나레이션

### 카드 3 — CTA (3초)
- CTA 텍스트 + 계정 로고/아이디
- 예: "저장하면 까먹지 않아요 👆"

모든 카드: 1080×1350 렌더링 (기존 동일).

## 5. TTS 생성 (tts_gen.py 확장)

### 이중 언어 TTS 구성

한국어 설명 + 타겟 언어 발음을 조합:

```
[한국어: intro] → [타겟언어: WRONG 발음] → [한국어: bridge] → [타겟언어: RIGHT 발음] → [한국어: outro]
```

TTS 파일 5개 생성 후 ffmpeg로 concat:
1. `intro.mp3` — 한국어 TTS (`ko-KR-SunHiNeural`)
2. `wrong.mp3` — 타겟 언어 TTS (기존 음성 프로필 재사용)
3. `bridge.mp3` — 한국어 TTS
4. `right.mp3` — 타겟 언어 TTS
5. `outro.mp3` — 한국어 TTS

한국어 음성: `ko-KR-SunHiNeural` (여성) 기본.
타겟 언어 음성: 기존 `LANG_CONFIG`의 슬롯별 음성 재사용.

### TTS 길이 제어
- 5조각 합산이 10초를 초과하면 카드 2 구간에 맞지 않음
- edge-tts `--rate` 옵션으로 속도 조절 (기본 `+0%`, 초과 시 `+10%`~`+20%`)
- 프롬프트에서 `tts_parts` 각 문장을 15자 이내로 제한

## 6. 릴스 영상 합성 (reel.py 수정)

### 기존 `render_short()` 수정

```
[HOOK 카드 — 2초, 무음] → [WRONG→RIGHT 카드 — 10초, TTS 오디오] → [CTA 카드 — 3초, 무음]
= 총 15초
```

- 1080×1350 카드 → 1080×1920 패딩 (기존 로직 재사용)
- TTS 합성 오디오는 카드 2 구간에만 배치
- ffmpeg concat demuxer (기존 방식)

## 7. 업로더 & 포스팅

### Cloudinary
변경 없음. `upload_video()`로 MP4 1개 업로드.

### Instagram 포스팅

**릴스 (슬롯당 1개)**
- `post_short_reel()` 수정
- 캡션 구조:

```
❌ I am boring
✅ I am bored → 나 지루해

이거 몰랐으면 저장해두세요 👆

#영어공부 #영어표현 #영어회화 #틀리기쉬운영어
```

- 해시태그: 언어별 세트 (`#영어공부` / `#중국어공부` / `#일본어공부`)
- `share_to_feed=true` 유지

**리캡 캐러셀 (유지)**
- 구성 변경: 커버 + 3슬롯의 WRONG→RIGHT 카드 = 4장
- 기존 7장 → 4장으로 축소

## 8. main.py 흐름 변경

```
Step 1: 폰트 검증                    ← 유지
Step 2: Claude API 표현 생성          ← 변경 (HOOK형 프롬프트, 1개 언어)
Step 3: 카드 이미지 렌더링            ← 변경 (HOOK/WRONG→RIGHT/CTA 3장)
Step 4: TTS 음성 생성                ← 변경 (한국어+타겟언어 이중 TTS)
Step 5: 릴스 영상 합성               ← 변경 (15초 구조)
Step 6: 어제의 리캡 캐러셀            ← 유지 (4장으로 축소)
Step 7: Cloudinary 업로드            ← 유지
Step 8: Instagram 포스팅             ← 변경 (릴스 1개 + 리캡 캐러셀)
```

## 9. history.json 변경

저장 구조:
```json
{
  "date": "2026-04-01",
  "slot": "morning",
  "lang": "en",
  "hook": "이거 영어로 말하면 99%가 틀림",
  "wrong": "I am boring",
  "right": "I am bored",
  "right_ko": "나 지루해"
}
```

중복 체크: `wrong` + `right` 조합으로 fuzzy matching (기존 similarity threshold 0.65 유지).

## 10. CLI 인터페이스

```bash
python3 main.py --slot morning              # morning 슬롯 실행 (영어 릴스)
python3 main.py --slot morning --dry-run    # 이미지/영상만 생성, 포스팅 안 함
```

기존 `--lang` 플래그는 deprecated 처리. 전달 시 무시하고 경고 출력.

## 11. 변경 파일 목록

| 파일 | 변경 유형 |
|------|----------|
| `config.py` | 수정 — `SLOT_LANG_MAP` 추가, 한국어 TTS 음성 설정 |
| `generator/claude_gen.py` | 수정 — HOOK형 프롬프트 모드 추가 |
| `renderer/card.py` | 수정 — HOOK/WRONG→RIGHT/CTA 카드 렌더 함수 추가 |
| `renderer/tts_gen.py` | 수정 — 이중 언어 TTS 생성 함수 추가 |
| `renderer/reel.py` | 수정 — `render_short()` 15초 구조로 변경 |
| `uploader/instagram.py` | 수정 — 캡션 생성 로직 변경 |
| `main.py` | 수정 — 파이프라인 흐름 조정 (1언어, HOOK형) |
| `generator/history.py` | 수정 — 저장/중복체크 구조 변경 |
