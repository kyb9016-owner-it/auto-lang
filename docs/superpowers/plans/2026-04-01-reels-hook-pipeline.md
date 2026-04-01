# Reels HOOK Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 7초 Short Reels를 15초 HOOK형(HOOK → WRONG→RIGHT → CTA) 릴스로 교체하고, 슬롯별 1개 언어만 포스팅하도록 파이프라인을 전환한다.

**Architecture:** 기존 main.py 8단계 파이프라인 구조를 유지하면서 내부 모듈(config, claude_gen, card, tts_gen, reel, instagram, history)을 수정한다. 새 파일은 만들지 않고, 기존 파일에 HOOK형 함수/프롬프트를 추가한다.

**Tech Stack:** Python 3, Pillow, edge-tts, ffmpeg, Anthropic Claude API, Cloudinary, Instagram Graph API

---

## File Structure

| 파일 | 변경 유형 | 책임 |
|------|----------|------|
| `config.py` | 수정 | `SLOT_LANG_MAP`, 한국어 TTS 음성, HOOK용 해시태그 추가 |
| `generator/claude_gen.py` | 수정 | HOOK형 프롬프트 & 생성 함수 추가 |
| `generator/history.py` | 수정 | HOOK형 저장/중복체크 구조 변경 |
| `renderer/card.py` | 수정 | HOOK/WRONG→RIGHT/CTA 카드 렌더 함수 3개 추가 |
| `renderer/tts_gen.py` | 수정 | 이중 언어 TTS(한국어+타겟) 생성 함수 추가 |
| `renderer/reel.py` | 수정 | `render_hook_reel()` 15초 구조 합성 함수 추가 |
| `uploader/instagram.py` | 수정 | HOOK형 릴스 캡션 빌더 추가 |
| `main.py` | 수정 | 파이프라인 흐름을 HOOK형으로 전환 |

---

### Task 1: config.py — 슬롯-언어 매핑 & 한국어 TTS 설정 추가

**Files:**
- Modify: `config.py:82-103` (TTS_VOICES 섹션 뒤에 추가)

- [ ] **Step 1: `SLOT_LANG_MAP` 추가**

`config.py`의 `TTS_VOICES` 뒤에 다음을 추가:

```python
# ── 슬롯-언어 매핑 (HOOK 릴스용) ──────────────────────────────────────────
SLOT_LANG_MAP = {
    "morning": "en",
    "lunch":   "zh",
    "evening": "ja",
}

# ── 한국어 TTS 음성 (HOOK 나레이션용) ─────────────────────────────────────
KO_TTS_VOICE = "ko-KR-SunHiNeural"
```

- [ ] **Step 2: HOOK용 해시태그 추가**

`LANG_HASHTAGS` 뒤에 다음을 추가:

```python
# ── HOOK 릴스용 해시태그 (틀린표현 교정 콘텐츠) ────────────────────────────
HOOK_HASHTAGS = {
    "en": (
        "#영어공부 #영어표현 #영어회화 #틀리기쉬운영어 "
        "#영어실수 #영어교정 #dailyenglish #commonmistakes "
        "#외국어공부 #langcard"
    ),
    "zh": (
        "#중국어공부 #중국어표현 #중국어회화 #틀리기쉬운중국어 "
        "#중국어실수 #중국어교정 #dailychinese #chinesemistakes "
        "#외국어공부 #langcard"
    ),
    "ja": (
        "#일본어공부 #일본어표현 #일본어회화 #틀리기쉬운일본어 "
        "#일본어실수 #일본어교정 #dailyjapanese #japanesemistakes "
        "#외국어공부 #langcard"
    ),
}
```

- [ ] **Step 3: 동작 확인**

Run: `python3 -c "from config import SLOT_LANG_MAP, KO_TTS_VOICE, HOOK_HASHTAGS; print(SLOT_LANG_MAP); print(KO_TTS_VOICE); print(list(HOOK_HASHTAGS.keys()))"`
Expected: `{'morning': 'en', 'lunch': 'zh', 'evening': 'ja'}` + `ko-KR-SunHiNeural` + `['en', 'zh', 'ja']`

- [ ] **Step 4: Commit**

```bash
git add config.py
git commit -m "feat: add SLOT_LANG_MAP, KO_TTS_VOICE, HOOK_HASHTAGS to config"
```

---

### Task 2: generator/claude_gen.py — HOOK형 프롬프트 & 생성 함수

**Files:**
- Modify: `generator/claude_gen.py`

- [ ] **Step 1: HOOK형 시스템 프롬프트 추가**

`claude_gen.py` 파일 하단(`generate_collection` 함수 위)에 다음을 추가:

```python
_HOOK_SYSTEM = """You are a language correction content creator for Korean Instagram.
You create "common mistake → correct expression" content for Korean learners.
The content must be accurate: WRONG must be a real, common mistake Koreans actually make.
RIGHT must be the natural, native-speaker expression.
Always respond with valid JSON only. No markdown, no extra text."""
```

- [ ] **Step 2: HOOK형 프롬프트 빌더 추가**

`generate_collection` 함수 위에 다음을 추가:

```python
def _build_hook_prompt(lang: str, recent_wrongs: list[str]) -> str:
    lc = LANG_CONFIG[lang]
    history_str = "\n".join(f"  - {w}" for w in recent_wrongs) if recent_wrongs else "  (없음)"

    pronunciation_field = ""
    if lc["has_pronunciation"]:
        pronunciation_field = f'"pronunciation": "{lc["pronunciation_label"]} of the RIGHT expression",'
    else:
        pronunciation_field = '"pronunciation": null,'

    return f"""Generate ONE common mistake that Korean speakers make in {lc['name']}.

Topic: Everyday expressions (일상생활 표현)

Rules:
- WRONG must be a mistake Koreans ACTUALLY make frequently (Konglish, direct translation, grammar error, etc.)
- RIGHT must be what native speakers naturally say in the same situation
- The difference must have clear learning value (not trivially obvious)
- HOOK must stop scrolling in 1 second — provocative, short, in Korean
- TTS parts must be under 15 characters each (for timing control)
- MUST be different from these recently used WRONG expressions:
{history_str}

Return ONLY this JSON:
{{
  "hook": "짧고 강한 한국어 문장 (예: '이거 영어로 말하면 99%가 틀림')",
  "wrong": "the incorrect {lc['name']} expression Koreans commonly say",
  "right": "the natural/correct {lc['name']} expression",
  "right_ko": "RIGHT의 한국어 뜻",
  {pronunciation_field}
  "tts_parts": {{
    "intro": "한국어 도입 (15자 이내, 예: '많은 사람들이 이렇게 말합니다')",
    "bridge": "한국어 연결 (15자 이내, 예: '하지만 올바른 표현은')",
    "outro": "한국어 마무리 (15자 이내, 예: RIGHT의 한국어 뜻)"
  }},
  "subtitle_lines": [
    "자막1: HOOK 요약 (10단어 이내)",
    "❌ WRONG 표현",
    "→ WRONG의 한국어 뜻",
    "✅ RIGHT 표현",
    "→ RIGHT의 한국어 뜻"
  ],
  "cta": "저장/댓글 유도 문구 (예: '이거 몰랐으면 저장 👆')"
}}"""
```

- [ ] **Step 3: `generate_hook` 함수 추가**

```python
def generate_hook(lang: str, max_retries: int = 3) -> dict:
    """
    HOOK형 콘텐츠 생성 (WRONG→RIGHT 교정 포맷).
    중복 감지: wrong 표현 기준으로 체크.
    """
    for attempt in range(1, max_retries + 1):
        recent_wrongs = history.get_recent_hook(lang)
        prompt = _build_hook_prompt(lang, recent_wrongs)
        data = _call_api(prompt)
        wrong = data["wrong"]

        if not history.is_hook_duplicate(lang, wrong):
            history.add_hook(lang, wrong, data["right"])
            if attempt > 1:
                print(f"  ↻ {lang} 재시도 {attempt}회 만에 새 표현: {wrong}")
            return data

        print(f"  ⚠ {lang} 중복 감지 (시도 {attempt}/{max_retries}): {wrong!r}")

    print(f"  ✗ {lang} 재시도 초과, 중복 허용: {data['wrong']!r}")
    history.add_hook(lang, data["wrong"], data["right"])
    return data
```

- [ ] **Step 4: 임포트 확인**

Run: `python3 -c "from generator.claude_gen import generate_hook; print('OK')"`
Expected: 이 시점에서는 `history.get_recent_hook`이 아직 없으므로 ImportError 또는 AttributeError. Task 3에서 해결.

- [ ] **Step 5: Commit**

```bash
git add generator/claude_gen.py
git commit -m "feat: add HOOK prompt builder and generate_hook function"
```

---

### Task 3: generator/history.py — HOOK형 히스토리 관리

**Files:**
- Modify: `generator/history.py`

- [ ] **Step 1: HOOK 히스토리 함수 3개 추가**

`history.py` 파일 하단(`mark_slot_posted` 뒤)에 다음을 추가:

```python
# ── HOOK 히스토리 (wrong/right 쌍 관리) ──────────────────────────────────

def get_recent_hook(lang: str) -> list[str]:
    """최근 HOOK wrong 표현 목록 반환"""
    data = _load()
    hook_key = f"{lang}_hook"
    entries = data.get(hook_key, [])[-HISTORY_MAX:]
    return [e["wrong"] for e in entries if isinstance(e, dict)]


def is_hook_duplicate(lang: str, wrong: str) -> bool:
    """HOOK wrong 표현이 히스토리에 있으면 True"""
    recent_wrongs = get_recent_hook(lang)
    if not recent_wrongs:
        return False

    if wrong in set(recent_wrongs):
        return True

    norm_new = _normalize(wrong)
    for hist_wrong in recent_wrongs:
        ratio = SequenceMatcher(None, norm_new, _normalize(hist_wrong)).ratio()
        if ratio >= HISTORY_SIMILARITY_THRESHOLD:
            return True

    return False


def add_hook(lang: str, wrong: str, right: str) -> None:
    """HOOK wrong/right 쌍 저장"""
    data = _load()
    hook_key = f"{lang}_hook"
    if hook_key not in data:
        data[hook_key] = []
    data[hook_key].append({"wrong": wrong, "right": right})
    data[hook_key] = data[hook_key][-HISTORY_MAX:]
    _save(data)
```

- [ ] **Step 2: 동작 확인**

Run: `python3 -c "from generator.history import get_recent_hook, is_hook_duplicate, add_hook; print(get_recent_hook('en')); print(is_hook_duplicate('en', 'test')); print('OK')"`
Expected: `[]` + `False` + `OK`

- [ ] **Step 3: generate_hook E2E 확인**

Run: `python3 -c "from generator.claude_gen import generate_hook; print('import OK')"`
Expected: `import OK`

- [ ] **Step 4: Commit**

```bash
git add generator/history.py
git commit -m "feat: add HOOK history functions (get_recent_hook, is_hook_duplicate, add_hook)"
```

---

### Task 4: renderer/card.py — HOOK/WRONG→RIGHT/CTA 카드 렌더링

**Files:**
- Modify: `renderer/card.py` (파일 하단에 함수 3개 추가)

- [ ] **Step 1: `render_hook_card` 함수 추가**

`card.py` 파일 하단에 HOOK 카드 렌더 함수 추가. 기존 `render()` 함수의 배경 생성/폰트 로딩 패턴을 재사용:

```python
def render_hook_card(hook_text: str, lang: str, date_str: str,
                     slot: str = "morning", bg_path: str = None) -> str:
    """
    HOOK 카드: 한국어 HOOK 텍스트를 중앙에 크게 표시.
    Returns: output/hook_{lang}_{slot}_{date_str}.png
    """
    W, H = 1080, 1350
    topic = _get_topic_for_slot(slot)
    canvas = _make_gradient_bg(W, H, topic)

    if bg_path and os.path.exists(bg_path):
        canvas = _composite_bg_image(canvas, bg_path, W, H)

    draw = ImageDraw.Draw(canvas)

    # HOOK 텍스트 (중앙, 큰 볼드)
    font_hook = _load_font("bold", 72)
    _draw_centered_text(draw, hook_text, font_hook, W, H,
                        fill="white", shadow=True)

    out = os.path.join(OUTPUT_DIR, f"hook_{lang}_{slot}_{date_str}.png")
    canvas.save(out, "PNG")
    print(f"  ✓ HOOK 카드: {out}")
    return out
```

주의: `_get_topic_for_slot`, `_make_gradient_bg`, `_composite_bg_image`, `_load_font`, `_draw_centered_text` 등 헬퍼는 기존 `card.py` 내부 함수를 사용. 만약 이름이 다르면 기존 함수명에 맞춰 수정.

실제 구현 시 card.py의 기존 헬퍼 함수(그라데이션 배경 생성, 텍스트 줄바꿈 등)를 정확히 참조해서 작성할 것. 위 코드는 구조 예시이며, 기존 `render()` 함수의 패턴(그라데이션 생성 → 배경 합성 → 텍스트 그리기 → 저장)을 따라야 함.

- [ ] **Step 2: `render_wrong_right_card` 함수 추가**

```python
def render_wrong_right_card(data: dict, lang: str, date_str: str,
                            slot: str = "morning", bg_path: str = None) -> str:
    """
    WRONG→RIGHT 카드: 상단에 ❌ 틀린 표현(빨간+취소선), 하단에 ✅ 올바른 표현(초록+강조).
    data: {"wrong": str, "right": str, "right_ko": str, "pronunciation": str|None}
    Returns: output/wrongright_{lang}_{slot}_{date_str}.png
    """
    W, H = 1080, 1350
    topic = _get_topic_for_slot(slot)
    canvas = _make_gradient_bg(W, H, topic)

    if bg_path and os.path.exists(bg_path):
        canvas = _composite_bg_image(canvas, bg_path, W, H)

    draw = ImageDraw.Draw(canvas)

    # ❌ WRONG (상단 1/3, 빨간 계열)
    font_wrong = _load_font("bold", 56)
    wrong_y = H * 0.25
    wrong_text = f"❌  {data['wrong']}"
    _draw_text_at(draw, wrong_text, font_wrong, W // 2, wrong_y,
                  fill="#FF6B6B", anchor="mm", shadow=True)
    # 취소선 효과 (wrong 텍스트 위에 선)
    bbox = draw.textbbox((0, 0), data['wrong'], font=font_wrong)
    line_w = bbox[2] - bbox[0]
    line_y = wrong_y
    draw.line([(W // 2 - line_w // 2, line_y), (W // 2 + line_w // 2, line_y)],
              fill="#FF6B6B", width=4)

    # ✅ RIGHT (하단 1/3, 초록 계열)
    font_right = _load_font("bold", 60)
    right_y = H * 0.55
    right_text = f"✅  {data['right']}"
    _draw_text_at(draw, right_text, font_right, W // 2, right_y,
                  fill="#51CF66", anchor="mm", shadow=True)

    # 한국어 뜻
    font_ko = _load_font("regular", 40)
    ko_y = right_y + 80
    _draw_text_at(draw, data['right_ko'], font_ko, W // 2, ko_y,
                  fill="white", anchor="mm")

    # 발음 (중국어/일본어만)
    if data.get('pronunciation'):
        font_pron = _load_font("regular", 32)
        pron_y = ko_y + 60
        _draw_text_at(draw, f"({data['pronunciation']})", font_pron,
                      W // 2, pron_y, fill="#CCCCCC", anchor="mm")

    out = os.path.join(OUTPUT_DIR, f"wrongright_{lang}_{slot}_{date_str}.png")
    canvas.save(out, "PNG")
    print(f"  ✓ WRONG→RIGHT 카드: {out}")
    return out
```

- [ ] **Step 3: `render_cta_card` 함수 추가**

```python
def render_cta_card(cta_text: str, lang: str, date_str: str,
                    slot: str = "morning", bg_path: str = None) -> str:
    """
    CTA 카드: 저장/댓글 유도 문구 + 계정 정보.
    Returns: output/cta_{lang}_{slot}_{date_str}.png
    """
    W, H = 1080, 1350
    topic = _get_topic_for_slot(slot)
    canvas = _make_gradient_bg(W, H, topic)

    if bg_path and os.path.exists(bg_path):
        canvas = _composite_bg_image(canvas, bg_path, W, H)

    draw = ImageDraw.Draw(canvas)

    # CTA 텍스트 (중앙)
    font_cta = _load_font("bold", 52)
    _draw_centered_text(draw, cta_text, font_cta, W, H,
                        fill="white", shadow=True)

    # 계정 정보 (하단)
    font_account = _load_font("regular", 28)
    _draw_text_at(draw, "@langcard.studio", font_account,
                  W // 2, H * 0.85, fill="#AAAAAA", anchor="mm")

    out = os.path.join(OUTPUT_DIR, f"cta_{lang}_{slot}_{date_str}.png")
    canvas.save(out, "PNG")
    print(f"  ✓ CTA 카드: {out}")
    return out
```

주의: 위 3개 함수 모두 card.py의 기존 내부 헬퍼(`_make_gradient_bg` 같은 그라데이션 생성 함수, 텍스트 렌더링 유틸 등)의 정확한 이름과 시그니처를 확인한 후 맞춰서 작성해야 함. 위 코드에서 `_get_topic_for_slot`, `_draw_centered_text`, `_draw_text_at` 등은 실제 card.py 내부에 있는 함수명으로 교체 필요.

구현 시 card.py를 읽고 기존 헬퍼 함수 목록을 확인한 후 정확한 함수명으로 호출할 것.

- [ ] **Step 4: dry-run 테스트**

Run: `python3 -c "from renderer.card import render_hook_card; print('import OK')"`
Expected: `import OK`

- [ ] **Step 5: Commit**

```bash
git add renderer/card.py
git commit -m "feat: add render_hook_card, render_wrong_right_card, render_cta_card"
```

---

### Task 5: renderer/tts_gen.py — 이중 언어 TTS 생성

**Files:**
- Modify: `renderer/tts_gen.py`

- [ ] **Step 1: `generate_hook_tts` 함수 추가**

`tts_gen.py` 파일 하단에 다음을 추가:

```python
def generate_hook_tts(data: dict, lang: str, date_str: str,
                      slot: str = "default") -> Optional[str]:
    """
    HOOK형 이중 언어 TTS 생성.
    한국어 나레이션 + 타겟 언어 WRONG/RIGHT 발음을 조합.

    구조: [KO intro] → [LANG wrong] → [KO bridge] → [LANG right] → [KO outro]

    data: {"wrong": str, "right": str, "tts_parts": {"intro": str, "bridge": str, "outro": str}}
    Returns: 합성된 오디오 파일 경로 또는 None
    """
    from config import KO_TTS_VOICE

    os.makedirs(TTS_DIR, exist_ok=True)
    out = os.path.join(TTS_DIR, f"hook_{lang}_{slot}_{date_str}.mp3")

    # 캐시 체크
    cache_text = f"{data['wrong']}|{data['right']}"
    if os.path.exists(out):
        if _read_cache_text(out) == cache_text:
            print(f"  ✓ TTS 캐시 사용: {os.path.basename(out)}")
            return out
        print(f"  ↻ TTS 내용 변경됨, 재생성: {os.path.basename(out)}")

    tts_parts = data.get("tts_parts", {})
    parts = [
        ("intro", tts_parts.get("intro", "이런 표현을 많이 씁니다"), "ko", KO_TTS_VOICE),
        ("wrong", data["wrong"], lang, None),  # 타겟 언어 음성 (슬롯별)
        ("bridge", tts_parts.get("bridge", "올바른 표현은"), "ko", KO_TTS_VOICE),
        ("right", data["right"], lang, None),
        ("outro", tts_parts.get("outro", data.get("right_ko", "")), "ko", KO_TTS_VOICE),
    ]

    part_files = []
    for i, (label, text, part_lang, voice_override) in enumerate(parts):
        if not text.strip():
            continue
        part_path = os.path.join(TTS_DIR, f"_hook_{lang}_{date_str}_{i}_{label}.mp3")

        if voice_override:
            # 한국어: 직접 지정 음성
            try:
                asyncio.run(_gen_async(text, voice_override, part_path))
                print(f"  ✓ TTS ({label}): {text[:20]}")
            except Exception as e:
                print(f"  ⚠ TTS ({label}) 실패: {e}")
                continue
        else:
            # 타겟 언어: 기존 _generate 함수 사용
            if not _generate(text, part_lang, part_path, slot=slot):
                continue

        if os.path.exists(part_path):
            part_files.append(part_path)

    if len(part_files) < 3:
        print(f"  ⚠ HOOK TTS 파트 부족 ({len(part_files)}/5), 생성 실패")
        return None

    # 파트 합성
    ok = _concat_mp3_files(part_files, out)

    # TTS 길이 검증 & 속도 조절
    if ok and os.path.exists(out):
        total_dur = _get_audio_duration(out)
        if total_dur > 10.0:
            # 10초 초과 시 속도 올려서 재생성
            print(f"  ⚠ TTS 총 {total_dur:.1f}초 > 10초, 속도 조절 시도")
            sped_up = os.path.join(TTS_DIR, f"_hook_{lang}_{date_str}_fast.mp3")
            speed_factor = min(1.3, total_dur / 10.0)
            try:
                subprocess.run([
                    "ffmpeg", "-y", "-i", out,
                    "-filter:a", f"atempo={speed_factor}",
                    "-c:a", "libmp3lame", "-b:a", "128k",
                    sped_up, "-loglevel", "error"
                ], check=True)
                import shutil
                shutil.move(sped_up, out)
                print(f"  ✓ TTS 속도 {speed_factor:.2f}x 적용")
            except Exception as e:
                print(f"  ⚠ 속도 조절 실패 (원본 유지): {e}")

    # 임시 파일 정리
    for fp in part_files:
        try:
            os.remove(fp)
        except OSError:
            pass

    if ok and os.path.exists(out):
        size_kb = os.path.getsize(out) // 1024
        dur = _get_audio_duration(out)
        print(f"  ✓ HOOK TTS 합성 완료: {os.path.basename(out)} ({dur:.1f}초, {size_kb} KB)")
        _write_cache_text(out, cache_text)
        return out

    return None
```

- [ ] **Step 2: 임포트 확인**

Run: `python3 -c "from renderer.tts_gen import generate_hook_tts; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add renderer/tts_gen.py
git commit -m "feat: add generate_hook_tts for dual-language TTS"
```

---

### Task 6: renderer/reel.py — 15초 HOOK 릴스 합성

**Files:**
- Modify: `renderer/reel.py`

- [ ] **Step 1: `render_hook_reel` 함수 추가**

`reel.py` 파일 하단에 다음을 추가:

```python
def render_hook_reel(hook_png: str, wrongright_png: str, cta_png: str,
                     tts_path: Optional[str],
                     lang: str, date_str: str,
                     slot: str = "daily") -> str:
    """
    HOOK 릴스: [HOOK 2초] → [WRONG→RIGHT 10초 + TTS] → [CTA 3초]
    = 총 15초
    Returns: output/hook_{lang}_{slot}_{date_str}.mp4
    """
    os.makedirs(FRAMES_DIR, exist_ok=True)

    segments = []

    # ── HOOK 카드 (2초, 무음) ─────────────────────────────────────────
    padded_hook = os.path.join(FRAMES_DIR, f"hook_{lang}_{date_str}_hook.png")
    _pad_to_9_16(hook_png, padded_hook)
    seg_hook = os.path.join(FRAMES_DIR, f"hook_{lang}_{date_str}_seg_hook.mp4")
    _make_segment(padded_hook, None, 2.0, seg_hook)
    segments.append(seg_hook)

    # ── WRONG→RIGHT 카드 (TTS 기반 길이, 최소 8초 최대 11초) ──────────
    padded_wr = os.path.join(FRAMES_DIR, f"hook_{lang}_{date_str}_wr.png")
    _pad_to_9_16(wrongright_png, padded_wr)

    tts_dur = _get_audio_duration(tts_path) if tts_path else 0.0
    wr_duration = max(8.0, min(11.0, tts_dur + 1.0))

    seg_wr = os.path.join(FRAMES_DIR, f"hook_{lang}_{date_str}_seg_wr.mp4")
    _make_segment(padded_wr, tts_path, wr_duration, seg_wr)
    segments.append(seg_wr)

    # ── CTA 카드 (3초, 무음) ──────────────────────────────────────────
    padded_cta = os.path.join(FRAMES_DIR, f"hook_{lang}_{date_str}_cta.png")
    _pad_to_9_16(cta_png, padded_cta)
    seg_cta = os.path.join(FRAMES_DIR, f"hook_{lang}_{date_str}_seg_cta.mp4")
    _make_segment(padded_cta, None, 3.0, seg_cta)
    segments.append(seg_cta)

    # ── 최종 합성 ─────────────────────────────────────────────────────
    out_path = os.path.join(OUTPUT_DIR, f"hook_{lang}_{slot}_{date_str}.mp4")
    _concat_segments(segments, out_path)

    size_kb = os.path.getsize(out_path) // 1024
    print(f"  ✓ HOOK 릴스 저장: {out_path} ({size_kb} KB)")
    return out_path
```

- [ ] **Step 2: 임포트 확인**

Run: `python3 -c "from renderer.reel import render_hook_reel; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add renderer/reel.py
git commit -m "feat: add render_hook_reel for 15-second HOOK reels"
```

---

### Task 7: uploader/instagram.py — HOOK형 캡션 빌더 & 포스팅

**Files:**
- Modify: `uploader/instagram.py`

- [ ] **Step 1: HOOK_HASHTAGS 임포트 추가**

`instagram.py` 상단의 config 임포트에 `HOOK_HASHTAGS` 추가:

```python
from config import LANG_CONFIG, SLOT_CONFIG, HASHTAGS, LANG_HASHTAGS, HOOK_HASHTAGS
```

- [ ] **Step 2: HOOK형 캡션 빌더 추가**

기존 `_build_short_reel_caption` 뒤에 다음을 추가:

```python
def _build_hook_reel_caption(lang: str, data: dict) -> str:
    """HOOK형 릴스 캡션 (WRONG→RIGHT + CTA)"""
    lc = LANG_CONFIG[lang]

    lines = [
        f"{lc['flag']} {lc['name_ko']} — 이 표현 틀리고 있었다면?",
        "",
        f"❌  {data['wrong']}",
        f"✅  {data['right']}  →  {data['right_ko']}",
    ]

    if data.get("pronunciation"):
        lines.append(f"({data['pronunciation']})")

    lines += [
        "",
        data.get("cta", "이거 몰랐으면 저장 👆"),
        "",
        HOOK_HASHTAGS.get(lang, LANG_HASHTAGS.get(lang, HASHTAGS)),
    ]
    return "\n".join(lines)
```

- [ ] **Step 3: `post_hook_reel` 함수 추가**

기존 `post_short_reel` 뒤에 다음을 추가:

```python
def post_hook_reel(video_url: str, lang: str, data: dict) -> str:
    """HOOK형 릴스 포스팅. Returns: media_id"""
    caption = _build_hook_reel_caption(lang, data)
    print(f"\n  📤 HOOK 릴스 포스팅 ({lang})...")

    # 컨테이너 생성
    resp = _api("POST", f"{IG_ID}/media", params={
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "share_to_feed": "true",
    })
    container_id = resp["id"]
    print(f"  → 컨테이너: {container_id}")

    # 상태 폴링 (최대 300초)
    _wait_for_container(container_id, timeout=300)

    # 퍼블리시
    pub = _api("POST", f"{IG_ID}/media_publish", params={
        "creation_id": container_id,
    })
    media_id = pub["id"]
    print(f"  ✅ HOOK 릴스 포스팅 완료: {media_id}")
    return media_id
```

주의: `_wait_for_container`는 기존 instagram.py에 컨테이너 상태 폴링 로직이 있는지 확인. 기존 `post_short_reel` 내부의 폴링 로직을 재사용. 만약 인라인으로 되어 있다면, 기존 패턴을 그대로 복제하여 사용.

- [ ] **Step 4: 임포트 확인**

Run: `python3 -c "from uploader.instagram import post_hook_reel; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add uploader/instagram.py
git commit -m "feat: add HOOK reel caption builder and post_hook_reel"
```

---

### Task 8: main.py — 파이프라인 전환

**Files:**
- Modify: `main.py`

- [ ] **Step 1: 임포트 업데이트**

`main.py` 상단의 임포트에 추가:

```python
from config import LANGUAGES, TOPIC_CONFIG, get_today_topic, SLOT_LANG_MAP
```

- [ ] **Step 2: `run` 함수를 HOOK형으로 전환**

`run()` 함수 전체를 리팩터링. 핵심 변경:

1. `slot`이 주어지면 `SLOT_LANG_MAP[slot]`으로 언어 1개 결정
2. Step 2: `claude_gen.generate_hook(lang)` 호출
3. Step 3: `card.render_hook_card()`, `card.render_wrong_right_card()`, `card.render_cta_card()` 호출
4. Step 4: `tts_gen.generate_hook_tts()` 호출
5. Step 5: `reel.render_hook_reel()` 호출
6. Step 6: 리캡 캐러셀 유지 (구성만 4장으로 변경)
7. Step 7: Cloudinary 업로드 (릴스 1개)
8. Step 8: `instagram.post_hook_reel()` 호출

```python
def run(dry_run: bool, slot: str, forced_topic=None) -> None:
    today     = date.today().strftime("%Y%m%d")
    yesterday = (date.today() - timedelta(days=1)).strftime("%Y%m%d")

    # 슬롯 → 언어 결정
    lang = SLOT_LANG_MAP[slot]
    topic = forced_topic or get_today_topic()

    # ── 중복 포스팅 방지 ─────────────────────────────────────────────
    from generator.history import is_slot_posted, mark_slot_posted
    if not dry_run and is_slot_posted(today, slot):
        print(f"\n⚠ [{today}] '{slot}' 슬롯은 이미 포스팅 완료 — 건너뜁니다.")
        return

    from config import LANG_CONFIG
    lc = LANG_CONFIG[lang]
    print(f"\n{'='*54}")
    print(f"LangCard Studio HOOK  |  {slot} → {lc['flag']} {lc['name_ko']}")
    print(f"{'='*54}")

    # [1] 폰트 준비
    print("\n[1/8] 폰트 확인 & 다운로드")
    F.ensure_fonts()

    # [2] Claude API HOOK 표현 생성
    print(f"\n[2/8] Claude API HOOK 표현 생성 ({lang})")
    try:
        hook_data = claude_gen.generate_hook(lang)
        print(f"  ✓ WRONG: {hook_data['wrong']}")
        print(f"  ✓ RIGHT: {hook_data['right']}")
    except Exception as e:
        print(f"  ✗ HOOK 생성 실패: {e}")
        sys.exit(1)

    # 오늘 데이터 저장
    data_json_path = os.path.join("output", f"data_{slot}_{today}.json")
    os.makedirs("output", exist_ok=True)
    with open(data_json_path, "w", encoding="utf-8") as f:
        json.dump({"slot": slot, "lang": lang, "data": hook_data},
                  f, ensure_ascii=False, indent=2)

    # [3] 카드 이미지 렌더링 (HOOK + WRONG→RIGHT + CTA)
    print(f"\n[3/8] 카드 이미지 렌더링 (3장)")
    os.makedirs("tmp", exist_ok=True)
    bg_path = fetch_city_bg(lang, slot)

    hook_png = card_renderer.render_hook_card(
        hook_data["hook"], lang, today, slot=slot, bg_path=bg_path)
    wr_png = card_renderer.render_wrong_right_card(
        hook_data, lang, today, slot=slot, bg_path=bg_path)
    cta_png = card_renderer.render_cta_card(
        hook_data.get("cta", "이거 몰랐으면 저장 👆"), lang, today,
        slot=slot, bg_path=bg_path)

    # [4] TTS 음성 생성 (한국어 + 타겟 언어 이중 TTS)
    print(f"\n[4/8] TTS 음성 생성 (한국어 + {lc['name_ko']})")
    hook_tts = tts_gen.generate_hook_tts(hook_data, lang, today, slot=slot)

    # [5] HOOK 릴스 영상 합성 (15초)
    print(f"\n[5/8] HOOK 릴스 합성 (15초)")
    hook_reel_path = reel_renderer.render_hook_reel(
        hook_png, wr_png, cta_png, hook_tts, lang, today, slot=slot)

    # [6] 전날 리캡 캐러셀 (유지 — 간소화)
    print(f"\n[6/8] 전날 리캡 캐러셀 준비 (어제: {yesterday})")
    recap_pngs = []
    try:
        yest_data_files = __import__('glob').glob(
            os.path.join("output", f"data_*_{yesterday}.json"))
        if yest_data_files:
            # 어제의 3슬롯 WRONG→RIGHT 카드 수집
            for yf in sorted(yest_data_files):
                with open(yf, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                wr_card = os.path.join("output",
                    f"wrongright_{saved['lang']}_{saved['slot']}_{yesterday}.png")
                if os.path.exists(wr_card):
                    recap_pngs.append(wr_card)
            if recap_pngs:
                # 커버 카드 생성
                cover_path = card_renderer.render_recap_cover(
                    {}, topic, yesterday)
                recap_pngs.insert(0, cover_path)
                print(f"  ✓ 리캡 카드 {len(recap_pngs)}장 준비")
            else:
                print(f"  ⚠ 전날 WRONG→RIGHT 카드 없음, 리캡 건너뜀")
        else:
            print(f"  ⚠ 전날 데이터 없음, 리캡 건너뜀")
    except Exception as e:
        print(f"  ⚠ 리캡 준비 실패 (건너뜀): {e}")

    # ── 드라이런 종료 ────────────────────────────────────────────────
    if dry_run:
        print("\n[dry-run] 업로드 생략. 생성된 파일:")
        print(f"  HOOK 카드  : {hook_png}")
        print(f"  W→R 카드   : {wr_png}")
        print(f"  CTA 카드   : {cta_png}")
        print(f"  TTS        : {hook_tts or '없음'}")
        print(f"  HOOK 릴스  : {hook_reel_path}")
        if recap_pngs:
            print(f"  리캡 캐러셀: {len(recap_pngs)}장")
        print("\n완료!")
        return

    # [7] Cloudinary 업로드
    print(f"\n[7/8] Cloudinary 업로드")
    hook_reel_url = cloudinary_up.upload_video(
        hook_reel_path, f"hook_{lang}", today)

    recap_card_urls = []
    if recap_pngs:
        try:
            for i, png in enumerate(recap_pngs):
                url = cloudinary_up.upload(
                    png, lang, "recap", suffix=f"hook_{i}", date_str=yesterday)
                recap_card_urls.append(url)
        except Exception as e:
            print(f"  ⚠ 리캡 업로드 실패 (건너뜀): {e}")
            recap_card_urls = []

    # [8] Instagram 포스팅
    print(f"\n[8/8] Instagram 포스팅")

    # 8-a) 리캡 캐러셀
    if recap_card_urls:
        try:
            instagram.post_recap_carousel(recap_card_urls, topic, {})
            time.sleep(8)
        except Exception as e:
            print(f"  ⚠ 리캡 캐러셀 포스팅 실패 (건너뜀): {e}")

    # 8-b) HOOK 릴스
    try:
        instagram.post_hook_reel(hook_reel_url, lang, hook_data)
        # 스토리 예약
        from story_dispatcher import enqueue_story
        try:
            enqueue_story(hook_reel_url, lang, delay_hours=1.0)
        except Exception as eq_err:
            print(f"  ⚠ 스토리 예약 실패 (건너뜀): {eq_err}")
    except Exception as e:
        print(f"\n✗ HOOK 릴스 포스팅 실패: {e}")
        sys.exit(1)

    print(f"\n✅ 포스팅 완료!")

    if not dry_run:
        mark_slot_posted(today, slot)
```

- [ ] **Step 3: CLI 인터페이스 변경**

`main()` 함수 변경 — `--slot` 필수화, `--lang` deprecated:

```python
def main():
    parser = argparse.ArgumentParser(description="LangCard Studio HOOK 릴스 자동 포스팅")
    parser.add_argument(
        "--slot",
        choices=["morning", "lunch", "evening"],
        required=True,
        help="슬롯 (morning=영어, lunch=중국어, evening=일본어)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="카드+TTS+릴스 생성만, 업로드 안 함",
    )
    parser.add_argument(
        "--lang",
        default=None,
        help="(deprecated — 슬롯이 언어를 결정합니다)",
    )
    args = parser.parse_args()

    if args.lang:
        print(f"  ⚠ --lang은 deprecated입니다. 슬롯({args.slot})이 언어를 결정합니다.")

    run(args.dry_run, args.slot)
```

- [ ] **Step 4: dry-run 테스트**

Run: `python3 main.py --slot morning --dry-run`
Expected: 8단계 파이프라인이 실행되고, HOOK/WRONG→RIGHT/CTA 카드 3장 + TTS + 릴스가 생성됨. 업로드는 건너뜀.

- [ ] **Step 5: Commit**

```bash
git add main.py
git commit -m "feat: switch main pipeline to HOOK reel format (slot-based single lang)"
```

---

### Task 9: E2E 테스트 & 정리

**Files:**
- 전체 파이프라인

- [ ] **Step 1: 3슬롯 dry-run 테스트**

```bash
python3 main.py --slot morning --dry-run
python3 main.py --slot lunch --dry-run
python3 main.py --slot evening --dry-run
```

Expected: 각각 영어/중국어/일본어 HOOK 릴스가 생성됨.

- [ ] **Step 2: 생성된 파일 확인**

```bash
ls -la output/hook_*.png output/wrongright_*.png output/cta_*.png output/hook_*.mp4 output/tts/hook_*.mp3
```

Expected: 각 슬롯별로 카드 3장, TTS 1개, 릴스 1개.

- [ ] **Step 3: deprecated --lang 경고 확인**

Run: `python3 main.py --slot morning --dry-run --lang en`
Expected: `⚠ --lang은 deprecated입니다` 경고 출력 후 정상 동작.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "test: verify HOOK reel pipeline E2E (3 slots dry-run)"
```
