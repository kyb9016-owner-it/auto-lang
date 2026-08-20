# 대화 카드 (Dialogue Card) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** HOOK 콘텐츠의 RIGHT 표현이 실제 대화에서 어떻게 쓰이는지 보여주는 대화 카드를 캐러셀에 추가한다.

**Architecture:** Claude API 프롬프트에 대화 생성 필드를 추가하고, 새 Pillow 렌더러(`renderer/dialogue_card.py`)로 대화 카드 PNG를 생성한다. 파이프라인에서 WR 카드 다음, CTA 카드 앞에 대화 카드를 삽입하고, Cloudinary 업로드 → Instagram 캐러셀에 포함한다.

**Tech Stack:** Python, Pillow, Claude API (Haiku), Cloudinary, Instagram Graph API

---

### Task 1: Claude API 프롬프트에 대화 필드 추가

**Files:**
- Modify: `generator/claude_gen.py:132-184` (`_build_hook_prompt` 함수)

- [ ] **Step 1: `_build_hook_prompt`에 dialogue 필드 추가**

`generator/claude_gen.py`의 `_build_hook_prompt` 함수에서, 반환 JSON 스키마의 `"vocab"` 필드 뒤에 `"dialogue"` 필드를 추가한다:

```python
# 기존 vocab 필드 뒤에 추가
  "dialogue": [
    {{"speaker": "A", "line": "대화 원문 ({lc['name']})", "pronunciation": "로마자/병음 (영어는 null)", "korean_phonetic": "한글 발음", "korean": "한국어 번역"}},
    {{"speaker": "B", "line": "대화 원문 ({lc['name']})", "pronunciation": "로마자/병음 (영어는 null)", "korean_phonetic": "한글 발음", "korean": "한국어 번역"}},
    {{"speaker": "A", "line": "...", "pronunciation": "...", "korean_phonetic": "...", "korean": "..."}},
    {{"speaker": "B", "line": "RIGHT 표현이 포함된 대사", "pronunciation": "...", "korean_phonetic": "...", "korean": "..."}}
  ]
```

또한 Rules 섹션에 다음 규칙을 추가:
```
- dialogue: RIGHT 표현이 자연스럽게 등장하는 2~4턴 대화. 마지막 턴에 RIGHT 표현이 포함되어야 함. 각 턴에 원문, 발음(영어는 null), 한글 발음, 한국어 번역 포함.
```

- [ ] **Step 2: 로컬에서 dry-run 테스트**

```bash
cd /Users/kong/projects/auto-lang
python3 -c "
from generator import claude_gen
data = claude_gen.generate_hook('en')
print('dialogue' in data)
for turn in data.get('dialogue', []):
    print(f\"{turn['speaker']}: {turn['line']} / {turn['korean']}\")
"
```

Expected: `True` 출력 후 2~4턴 대화 표시

- [ ] **Step 3: 커밋**

```bash
git add generator/claude_gen.py
git commit -m "feat: HOOK 프롬프트에 dialogue 필드 추가"
```

---

### Task 2: 대화 카드 렌더러 생성

**Files:**
- Create: `renderer/dialogue_card.py`

- [ ] **Step 1: `renderer/dialogue_card.py` 작성**

Apple 라이트 스타일 대화 카드 렌더러. `vocab_card.py`와 동일한 색상 팔레트 사용.

```python
"""Apple 라이트 스타일 대화 카드 렌더러"""
from __future__ import annotations
import os
from PIL import Image, ImageDraw
from renderer import fonts as F
from renderer.themes import CARD_W, CARD_H, PAD

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")

# Apple 색상
BG         = (245, 245, 247)   # #F5F5F7
TEXT_MAIN  = (29, 29, 31)      # #1D1D1F
TEXT_SUB   = (134, 134, 139)   # #86868B
APPLE_BLUE = (0, 113, 227)     # #0071E3
SPEAKER_A  = (134, 134, 139)   # A는 회색
SPEAKER_B  = (0, 113, 227)     # B는 파랑 (RIGHT 표현 화자)

USABLE_W = CARD_W - PAD * 2


def _tw(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]


def _th(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[3] - bb[1]


def _wrap(draw, text, font, max_w, is_cjk=False):
    if is_cjk:
        lines, cur = [], ""
        for ch in text:
            if _tw(draw, cur + ch, font) > max_w:
                lines.append(cur)
                cur = ch
            else:
                cur += ch
        if cur:
            lines.append(cur)
        return lines
    words = text.split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if _tw(draw, test, font) > max_w:
            if cur:
                lines.append(cur)
            cur = w
        else:
            cur = test
    if cur:
        lines.append(cur)
    return lines


def _main_font_fn(lang: str):
    if lang == "ja":
        return F.noto_jp
    if lang == "zh":
        return F.noto_sc
    return F.outfit


def render_dialogue_card(dialogue: list[dict], lang: str, date_str: str,
                         slot: str, right_text: str = "") -> str:
    """
    대화 카드 1장 렌더링 (Apple 라이트 스타일).

    dialogue: [{"speaker": "A/B", "line": "...", "pronunciation": "...",
                "korean_phonetic": "...", "korean": "..."}]
    right_text: RIGHT 표현 (하이라이트용)
    Returns: output/dialogue_{lang}_{slot}_{date_str}.png
    """
    F.ensure_fonts()

    img = Image.new("RGB", (CARD_W, CARD_H), BG)
    draw = ImageDraw.Draw(img)

    is_cjk = lang in ("zh", "ja")
    font_fn = _main_font_fn(lang)

    # ── 상단 레이블 ────────────────────────────────────────
    label_font = F.noto_kr(26)
    draw.text((PAD, 80), "실전 대화", font=label_font, fill=TEXT_SUB)

    # Apple Blue 구분선
    draw.rectangle([PAD, 120, CARD_W - PAD, 122], fill=APPLE_BLUE)

    cur_y = 150

    # ── 대화 턴 렌더링 ────────────────────────────────────
    # 동적 폰트 크기: 턴 수에 따라 조절
    n_turns = len(dialogue)
    if n_turns <= 2:
        line_size, pron_size, ko_size, speaker_size = 44, 26, 28, 22
    elif n_turns == 3:
        line_size, pron_size, ko_size, speaker_size = 38, 24, 26, 20
    else:
        line_size, pron_size, ko_size, speaker_size = 34, 22, 24, 18

    # 전체 높이 계산 후 시작 y 조정
    avail_h = CARD_H - 150 - 60  # 상단 여백 - 하단 워터마크
    # 각 턴의 예상 높이를 대략 계산
    est_turn_h = line_size + pron_size + ko_size + 50  # 대사 + 발음 + 번역 + 간격
    total_est = est_turn_h * n_turns
    if total_est < avail_h:
        # 수직 중앙 정렬
        cur_y = 150 + (avail_h - total_est) // 3

    content_w = USABLE_W - 40  # 스피커 라벨 공간 확보

    for i, turn in enumerate(dialogue):
        speaker = turn.get("speaker", "A")
        line = turn.get("line", "")
        pronunciation = turn.get("pronunciation") or ""
        korean_phonetic = turn.get("korean_phonetic", "")
        korean = turn.get("korean", "")

        # RIGHT 표현 포함 턴 감지 (마지막 턴 또는 right_text 포함)
        is_highlight = (right_text and right_text.lower() in line.lower()) or \
                       (i == len(dialogue) - 1)

        speaker_color = APPLE_BLUE if is_highlight else TEXT_SUB
        line_color = TEXT_MAIN

        # 스피커 라벨
        spk_font = F.noto_kr(speaker_size)
        draw.text((PAD, cur_y + 4), speaker, font=spk_font, fill=speaker_color)

        text_x = PAD + 40

        # 하이라이트 턴: 왼쪽 파란 바
        if is_highlight:
            bar_top = cur_y
            # 높이는 나중에 계산해서 그림 — 일단 위치 기억
            highlight_bar_top = cur_y

        # 대사 원문
        line_font = font_fn(line_size)
        line_lines = _wrap(draw, line, line_font, content_w, is_cjk)
        for ln in line_lines:
            bb = draw.textbbox((0, 0), ln, font=line_font)
            draw.text((text_x, cur_y - bb[1]), ln, font=line_font, fill=line_color)
            cur_y += _th(draw, ln, line_font) + 6
        cur_y += 4

        # 한글 발음
        if korean_phonetic:
            kp_font = F.noto_kr(pron_size)
            kp_lines = _wrap(draw, korean_phonetic, kp_font, content_w, True)
            for ln in kp_lines:
                draw.text((text_x, cur_y), ln, font=kp_font, fill=TEXT_SUB)
                cur_y += _th(draw, ln, kp_font) + 4
            cur_y += 2

        # 한국어 번역
        ko_font = F.noto_kr(ko_size)
        ko_lines = _wrap(draw, korean, ko_font, content_w, True)
        for ln in ko_lines:
            draw.text((text_x, cur_y), ln, font=ko_font, fill=TEXT_SUB)
            cur_y += _th(draw, ln, ko_font) + 4

        # 하이라이트 바 그리기
        if is_highlight:
            draw.rectangle([PAD - 4, highlight_bar_top, PAD, cur_y],
                           fill=APPLE_BLUE)

        cur_y += 24  # 턴 간 간격

    # ── 하단 워터마크 ──────────────────────────────────────
    wm_font = F.outfit(28)
    wm = "@langcard.studio"
    wmw = _tw(draw, wm, wm_font)
    draw.text(((CARD_W - wmw) // 2, CARD_H - 50), wm,
              font=wm_font, fill=TEXT_SUB)

    # ── 저장 ───────────────────────────────────────────────
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR,
                            f"dialogue_{lang}_{slot}_{date_str}.png")
    img.save(out_path, "PNG", optimize=True)
    print(f"  ✓ 대화 카드 저장: {out_path}")
    return out_path
```

- [ ] **Step 2: 커밋**

```bash
git add renderer/dialogue_card.py
git commit -m "feat: 대화 카드 렌더러 추가 (Apple 라이트 스타일)"
```

---

### Task 3: 파이프라인에 대화 카드 통합

**Files:**
- Modify: `pipeline.py:31-50` (GenerationResult에 필드 추가)
- Modify: `pipeline.py:89-114` (_step3_render에 대화 카드 렌더 추가)
- Modify: `pipeline.py:174-201` (_step7_upload에 대화 카드 업로드 추가)

- [ ] **Step 1: GenerationResult에 dialogue 필드 추가**

`pipeline.py`에서:
```python
# GenerationResult에 추가 (vocab_pngs 아래)
dialogue_png: str = ""
dialogue_card_url: Optional[str] = None
```

- [ ] **Step 2: _step3_render에 대화 카드 렌더링 추가**

`pipeline.py`의 `_step3_render` 함수 끝에 (vocab 렌더링 뒤에):
```python
from renderer import dialogue_card as dialogue_renderer

# 대화 카드 렌더링
dialogue_list = result.hook_data.get("dialogue", [])
if dialogue_list:
    result.dialogue_png = dialogue_renderer.render_dialogue_card(
        dialogue_list, result.lang, result.today,
        slot=result.slot, right_text=result.hook_data.get("right", ""))
```

import는 함수 내에서 하거나 파일 상단에 추가. 파일 상단 import 추가 권장:
```python
from renderer import dialogue_card as dialogue_renderer
```

- [ ] **Step 3: _step7_upload에 대화 카드 업로드 추가**

`pipeline.py`의 `_step7_upload` 함수에서 vocab 업로드 뒤에:
```python
# 대화 카드 업로드
if result.dialogue_png:
    try:
        result.dialogue_card_url = cloudinary_up.upload(
            result.dialogue_png, result.lang, "dialogue",
            suffix="conv", date_str=result.today)
    except Exception as e:
        print(f"  ⚠ 대화 카드 업로드 실패 (건너뜀): {e}")
```

- [ ] **Step 4: 커밋**

```bash
git add pipeline.py
git commit -m "feat: 파이프라인에 대화 카드 생성·업로드 통합"
```

---

### Task 4: Worker API 응답에 대화 카드 URL 포함

**Files:**
- Modify: `worker/api.py:217-228` (응답 dict)

- [ ] **Step 1: /job 응답에 dialogue_card_url 추가**

`worker/api.py`의 `/job` 엔드포인트 응답에:
```python
return {
    "status": "ok",
    ...
    "vocab_card_urls": result.vocab_card_urls,
    "dialogue_card_url": result.dialogue_card_url,  # 추가
    ...
}
```

dry_run 응답에도 동일하게 추가:
```python
"dialogue_card_url": None,  # 추가
```

- [ ] **Step 2: 커밋**

```bash
git add worker/api.py
git commit -m "feat: Worker 응답에 dialogue_card_url 포함"
```

---

### Task 5: Instagram 캐러셀에 대화 카드 삽입

**Files:**
- Modify: `uploader/instagram.py` (`post_hook_reel` 함수 또는 캐러셀 관련)
- Modify: `dispatch.py` (대화 카드를 캐러셀에 포함)

- [ ] **Step 1: dispatch.py에서 대화 카드 URL을 HOOK 릴스 캐러셀에 포함**

현재 HOOK은 릴스(영상)로 올라가고, 단어 캐러셀은 별도 포스팅이다. 대화 카드는 단어 캐러셀에 첫 번째 슬라이드로 삽입하는 게 가장 자연스럽다.

`dispatch.py`에서 단어 캐러셀 포스팅 부분 수정:
```python
# 기존 vocab_card_urls 앞에 dialogue_card_url 삽입
dialogue_card_url = data.get("dialogue_card_url")

if vocab_card_urls:
    try:
        time.sleep(5)
        # 대화 카드를 단어 캐러셀 앞에 삽입
        carousel_urls = vocab_card_urls
        if dialogue_card_url:
            carousel_urls = [dialogue_card_url] + vocab_card_urls
        instagram.post_vocab_carousel(carousel_urls, lang, hook_data)
        notify.send(f"📖 <b>{flag} 단어+대화 캐러셀 업로드 완료</b> ✅ ({len(carousel_urls)}장)")
    except Exception as e:
        notify.send(f"⚠️ <b>{flag} 단어+대화 캐러셀 실패</b> (건너뜀)\n<code>{e}</code>")
        print(f"  ⚠ {flag} 단어+대화 캐러셀 실패: {e}")
elif dialogue_card_url:
    # vocab은 없지만 대화 카드만 있는 경우 — 단독 포스팅
    try:
        time.sleep(5)
        instagram.post_vocab_carousel([dialogue_card_url], lang, hook_data)
        notify.send(f"💬 <b>{flag} 대화 카드 업로드 완료</b> ✅")
    except Exception as e:
        notify.send(f"⚠️ <b>{flag} 대화 카드 실패</b> (건너뜀)\n<code>{e}</code>")
```

- [ ] **Step 2: 커밋**

```bash
git add dispatch.py
git commit -m "feat: 대화 카드를 단어 캐러셀에 통합"
```

---

### Task 6: dry-run 테스트 및 배포

**Files:** (변경 없음 — 실행만)

- [ ] **Step 1: 로컬 dry-run 테스트**

Worker 서버에서 dry-run으로 전체 파이프라인 테스트:
```bash
ssh root@89.167.127.109 "cd /opt/auto-lang && git pull origin main && systemctl restart langcard-worker"
ssh kong-main "cd /opt/auto-lang && git pull origin main"
ssh kong-main "cd /opt/auto-lang && .venv/bin/python3 dispatch.py --slot evening --dry-run --lang ja"
```

Expected: Worker 로그에 "대화 카드 저장" 출력, data JSON에 `dialogue` 필드 포함

- [ ] **Step 2: 생성된 대화 카드 이미지 확인**

Worker에서 생성된 PNG를 로컬로 가져와 확인:
```bash
scp root@89.167.127.109:/opt/auto-lang/output/dialogue_*.png /Users/kong/projects/auto-lang/output/
open /Users/kong/projects/auto-lang/output/dialogue_*.png
```

- [ ] **Step 3: 실제 포스팅 테스트 (1개 언어)**

```bash
ssh kong-main "cd /opt/auto-lang && .venv/bin/python3 dispatch.py --slot evening --lang ja"
```

Expected: Instagram에 HOOK 릴스 + 대화카드+단어 캐러셀 업로드 성공
