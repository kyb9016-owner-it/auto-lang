# 통합 릴스 + Notion 리디자인 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 카드 비주얼을 Notion 웜 미니멀리즘으로 리디자인하고, 모든 카드를 릴스 하나로 통합하며, 단어 카드 폰트 깨짐을 수정한다.

**Architecture:** themes.py에 Notion 팔레트를 적용하고, 각 카드 렌더러(card.py, vocab_card.py, dialogue_card.py)의 하드코딩 색상을 Notion 값으로 교체한다. reel.py의 render_hook_reel에 대화+단어 카드 세그먼트를 추가하고, dispatch.py에서 캐러셀 별도 포스팅을 제거한다.

**Tech Stack:** Python, Pillow, ffmpeg, Cloudinary, Instagram Graph API

---

### Task 1: 단어 카드 폰트 깨짐 수정

**Files:**
- Modify: `renderer/vocab_card.py:78-84`

- [ ] **Step 1: vocab_card.py에서 단어 폰트를 언어별로 분기**

현재 `F.outfit(100)`(Poppins)을 쓰는데 CJK 글리프가 없어서 엑스박스 발생. 언어별 폰트로 교체:

```python
# 기존:
word_font = F.outfit(100)
while _tw(draw, word, word_font) > USABLE_W and word_font.size > 48:
    word_font = F.outfit(word_font.size - 4)

# 변경:
def _word_font(lang, size):
    if lang == "ja": return F.noto_jp(size)
    if lang == "zh": return F.noto_sc(size)
    return F.outfit(size)

word_font = _word_font(lang, 100)
while _tw(draw, word, word_font) > USABLE_W and word_font.size > 48:
    word_font = _word_font(lang, word_font.size - 4)
```

`render_vocab_card` 함수에 `lang` 파라미터는 이미 있음.

- [ ] **Step 2: 커밋**

```bash
git add renderer/vocab_card.py
git commit -m "fix: 단어 카드 CJK 폰트 깨짐 수정 (언어별 폰트 분기)"
```

---

### Task 2: Notion 색상 팔레트 적용

**Files:**
- Modify: `renderer/themes.py` (전체)
- Modify: `renderer/vocab_card.py` (색상 상수)
- Modify: `renderer/dialogue_card.py` (색상 상수)
- Modify: `renderer/card.py` (WR/CTA/HOOK 카드의 하드코딩 색상)

- [ ] **Step 1: themes.py — Notion 팔레트로 CARD_THEMES 전체 교체**

Notion 색상 체계:
- 배경: `#FFFFFF` (순백) 또는 `#F6F5F4` (웜 화이트)
- 메인 텍스트: `(0, 0, 0, 242)` = rgba(0,0,0,0.95)
- 보조 텍스트: `#615D59` = (97, 93, 89)
- 뮤트 텍스트: `#A39E98` = (163, 158, 152)
- 강조: `#0075DE` = (0, 117, 222) Notion Blue
- 배지 배경: `#F2F9FF` = (242, 249, 255)
- 배지 텍스트: `#097FE8` = (9, 127, 232)
- 위스퍼 보더: rgba(0,0,0,0.1)

모든 테마를 Notion 라이트 스타일로 통일 (다크 모드 제거):
```python
# 모든 (lang, slot) 조합을 동일한 Notion 라이트 팔레트로
_NOTION_LIGHT = dict(
    gradient=[(255, 255, 255), (255, 255, 255)],
    topic_badge_bg=(242, 249, 255, 255), topic_badge_fg=(9, 127, 232),
    lang_badge_bg=(0, 0, 0, 13),         lang_badge_fg=(0, 0, 0),
    text_main=(0, 0, 0),                 text_sub=(97, 93, 89, 200),
    kr_badge_bg=(0, 0, 0, 13),
)
```

각 (lang, slot) 테마에 `emoji`와 `slot_keyword`만 개별 유지, 나머지는 `_NOTION_LIGHT` 기반.

- [ ] **Step 2: vocab_card.py, dialogue_card.py — 색상 상수를 Notion으로 교체**

```python
# 공통 Notion 색상 (두 파일 모두)
BG         = (255, 255, 255)     # #FFFFFF
TEXT_MAIN  = (0, 0, 0)           # rgba(0,0,0,0.95) 근사
TEXT_SUB   = (97, 93, 89)        # #615D59
NOTION_BLUE = (0, 117, 222)     # #0075DE
BADGE_BG   = (242, 249, 255)    # #F2F9FF
BADGE_TEXT  = (9, 127, 232)     # #097FE8
```

- [ ] **Step 3: card.py — WR/CTA/HOOK 카드의 하드코딩 Apple 색상을 Notion으로 교체**

`render_wrong_right_card`, `render_cta_card`, `render_hook_card` 함수 내부의:
```python
# Apple → Notion
BG         = (245, 245, 247)  →  (255, 255, 255)
TEXT_MAIN  = (29, 29, 31)     →  (0, 0, 0)
TEXT_SUB   = (134, 134, 139)  →  (97, 93, 89)
APPLE_BLUE = (0, 113, 227)   →  (0, 117, 222)
MUTED      = (142, 142, 147) →  (163, 158, 152)
```

설명 박스 배경도 `(*APPLE_BLUE, 12)` → `(242, 249, 255, 255)` (Notion Badge BG)

- [ ] **Step 4: 커밋**

```bash
git add renderer/themes.py renderer/vocab_card.py renderer/dialogue_card.py renderer/card.py
git commit -m "feat: Notion 웜 미니멀리즘 팔레트 적용 (전체 카드)"
```

---

### Task 3: 릴스에 대화+단어 카드 통합

**Files:**
- Modify: `renderer/reel.py:272-320` (`render_hook_reel` 함수)

- [ ] **Step 1: render_hook_reel 시그니처에 dialogue_png, vocab_pngs 추가**

```python
def render_hook_reel(hook_png: str, wrongright_png: str, cta_png: str,
                     tts_path: Optional[str],
                     lang: str, date_str: str,
                     slot: str = "daily",
                     dialogue_png: Optional[str] = None,
                     vocab_pngs: Optional[list[str]] = None) -> str:
```

- [ ] **Step 2: HOOK→WR→대화→단어3→CTA 세그먼트 구성**

WR 세그먼트 뒤, CTA 세그먼트 앞에 추가:

```python
# ── 대화 카드 (5~8초, 턴 수에 비례, 무음) ─────────────────
if dialogue_png and os.path.exists(dialogue_png):
    padded_dlg = os.path.join(FRAMES_DIR, f"hook_{lang}_{date_str}_dlg.png")
    _pad_to_9_16(dialogue_png, padded_dlg)
    dlg_duration = 7.0  # 대화 읽기 충분한 시간
    seg_dlg = os.path.join(FRAMES_DIR, f"hook_{lang}_{date_str}_seg_dlg.mp4")
    _make_segment(padded_dlg, None, dlg_duration, seg_dlg)
    segments.append(seg_dlg)

# ── 단어 카드 (각 4초, 무음) ──────────────────────────────
for vi, vpng in enumerate(vocab_pngs or []):
    if not os.path.exists(vpng):
        continue
    padded_v = os.path.join(FRAMES_DIR, f"hook_{lang}_{date_str}_v{vi}.png")
    _pad_to_9_16(vpng, padded_v)
    seg_v = os.path.join(FRAMES_DIR, f"hook_{lang}_{date_str}_seg_v{vi}.mp4")
    _make_segment(padded_v, None, 4.0, seg_v)
    segments.append(seg_v)
```

- [ ] **Step 3: 커밋**

```bash
git add renderer/reel.py
git commit -m "feat: 릴스에 대화+단어 카드 세그먼트 추가 (통합 릴스)"
```

---

### Task 4: 파이프라인에서 릴스에 대화+단어 전달

**Files:**
- Modify: `pipeline.py:127-134` (`_step5_reel` 함수)

- [ ] **Step 1: _step5_reel에서 dialogue_png, vocab_pngs 전달**

```python
def _step5_reel(result: GenerationResult, track_times: bool) -> None:
    print(f"\n[5/7] HOOK 릴스 합성")
    t0 = time.time()
    result.hook_reel_path = reel_renderer.render_hook_reel(
        result.hook_png, result.wr_png, result.cta_png,
        result.hook_tts, result.lang, result.today, slot=result.slot,
        dialogue_png=result.dialogue_png,
        vocab_pngs=result.vocab_pngs)
    if track_times:
        result.step_times["step5_reels"] = time.time() - t0
```

- [ ] **Step 2: 커밋**

```bash
git add pipeline.py
git commit -m "feat: 릴스 렌더에 대화+단어 카드 전달"
```

---

### Task 5: dispatch.py에서 캐러셀 별도 포스팅 제거

**Files:**
- Modify: `dispatch.py` (캐러셀 포스팅 블록 제거)

- [ ] **Step 1: 단어+대화 캐러셀 포스팅 블록 제거**

`dispatch.py`에서 `# ── 단어+대화 캐러셀` 블록 전체 삭제 (릴스에 이미 포함됨):

```python
# 아래 블록 전체 삭제:
        # ── 단어+대화 캐러셀 ─────────────────────────────────────────
        if vocab_card_urls or dialogue_card_url:
            try:
                time.sleep(5)
                carousel_urls = list(vocab_card_urls)
                if dialogue_card_url:
                    carousel_urls.insert(0, dialogue_card_url)
                instagram.post_vocab_carousel(carousel_urls, lang, hook_data)
                notify.send(...)
            except Exception as e:
                notify.send(...)
                print(...)
```

릴스 하나만 올라가므로 캐러셀 관련 코드는 불필요.

- [ ] **Step 2: 커밋**

```bash
git add dispatch.py
git commit -m "feat: 캐러셀 별도 포스팅 제거 (릴스 통합)"
```

---

### Task 6: 배포 및 테스트

- [ ] **Step 1: push + 양쪽 서버 배포**
- [ ] **Step 2: dry-run 테스트 (1개 언어)**
- [ ] **Step 3: 생성된 카드 이미지 + 릴스 확인**
