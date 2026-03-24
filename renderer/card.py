"""Pillow 카드 렌더러 — HTML 디자인 기반"""
from __future__ import annotations
import os
from typing import Optional
from datetime import date, datetime
from PIL import Image, ImageDraw, ImageFont

from config import LANG_CONFIG, SLOT_CONFIG, _today_kst
from renderer.themes import CARD_THEMES, CARD_W, CARD_H, PAD, USABLE_W
from renderer import fonts as F

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")

# ── 이모지 폰트 (Apple Color Emoji / Noto Color Emoji) ──────────────────────
_EMOJI_FONT_PATH = None
for _p in ["/System/Library/Fonts/Apple Color Emoji.ttc",
           "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"]:
    if os.path.exists(_p):
        _EMOJI_FONT_PATH = _p
        break

# ── 상수 ────────────────────────────────────────────────────────────────────
BOTTOM_PAD   = 72    # 하단 여백
CONTENT_GAP  = 16   # 요소 간 간격
BADGE_Y      = 60   # 상단 배지 y
BADGE_H      = 52   # 배지 높이
BADGE_PAD_X  = 24   # 배지 좌우 내부 여백
BADGE_PAD_Y  = 11   # 배지 상하 내부 여백


# ── 유틸 ────────────────────────────────────────────────────────────────────

def _gradient(w: int, h: int, c1: tuple, c2: tuple,
              c3: Optional[tuple] = None) -> Image.Image:
    import numpy as np
    if c3 is None:
        t = np.linspace(0, 1, h, dtype=np.float32)[:, None]
        arr = (1 - t) * np.array(c1, dtype=np.float32) + t * np.array(c2, dtype=np.float32)
    else:
        half = h // 2
        t1 = np.linspace(0, 1, half, dtype=np.float32)[:, None]
        top = (1 - t1) * np.array(c1, dtype=np.float32) + t1 * np.array(c2, dtype=np.float32)
        t2 = np.linspace(0, 1, h - half, dtype=np.float32)[:, None]
        bot = (1 - t2) * np.array(c2, dtype=np.float32) + t2 * np.array(c3, dtype=np.float32)
        arr = np.concatenate([top, bot], axis=0)
    arr = np.clip(arr + np.random.uniform(-0.5, 0.5, arr.shape).astype(np.float32), 0, 255)
    row = np.round(arr).astype(np.uint8)
    pixels = np.broadcast_to(row[:, None, :], (h, w, 3)).copy()
    return Image.fromarray(pixels, "RGB")


def _dot_overlay(img: Image.Image, text_main: tuple) -> Image.Image:
    """20px 그리드 도트 오버레이 (HTML 1px dot 스타일)"""
    layer = Image.new("RGBA", img.size, (0,0,0,0))
    draw  = ImageDraw.Draw(layer)
    dot_color = (255,255,255,15) if text_main == (255,255,255) else (0,0,0,12)
    spacing = 20
    for x in range(0, CARD_W, spacing):
        for y in range(0, CARD_H, spacing):
            draw.ellipse([x-1, y-1, x+1, y+1], fill=dot_color)
    return Image.alpha_composite(img, layer)


def _emoji_bg(img: Image.Image, emoji: str) -> Image.Image:
    """큰 이모지를 우하단에 12% 투명도로 렌더링"""
    emoji_font = None
    for path in [
        "/System/Library/Fonts/Apple Color Emoji.ttc",
        "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
    ]:
        if os.path.exists(path):
            try:
                from PIL import ImageFont
                emoji_font = ImageFont.truetype(path, 300)
                break
            except Exception:
                pass

    if emoji_font is None:
        return img

    try:
        layer = Image.new("RGBA", img.size, (0,0,0,0))
        d = ImageDraw.Draw(layer)
        d.text((CARD_W - 60, CARD_H - 60), emoji,
               font=emoji_font, anchor="rb",
               embedded_color=True)
        layer.putalpha(
            layer.getchannel("A").point(lambda p: int(p * 0.12))
        )
        return Image.alpha_composite(img, layer)
    except Exception:
        return img


def _alpha_badge(img: Image.Image, xy: tuple, radius: int, bg: tuple,
                 text: str, font, fg: tuple,
                 pad_x: int = BADGE_PAD_X, pad_y: int = BADGE_PAD_Y):
    """반투명 배지 — alpha_composite 방식"""
    x0, y0, x1, y1 = xy
    layer = Image.new("RGBA", img.size, (0,0,0,0))
    ImageDraw.Draw(layer).rounded_rectangle([x0,y0,x1,y1], radius=radius, fill=bg)
    img = Image.alpha_composite(img, layer)
    draw = ImageDraw.Draw(img)
    draw.text((x0 + pad_x, y0 + pad_y), text, font=font, fill=(*fg[:3], 255))
    return img, draw


def _alpha_badge_emoji(img: Image.Image, x0: int, y0: int, radius: int,
                       bg: tuple, emoji: str, text: str, emoji_size: int,
                       text_font, fg: tuple,
                       pad_x: int = BADGE_PAD_X, pad_y: int = BADGE_PAD_Y):
    """이모지 + 텍스트 배지. 수직 중앙정렬 + 국기 PNG 지원."""
    tmp = ImageDraw.Draw(img)
    tb = tmp.textbbox((0, 0), text, font=text_font)
    tw = tb[2] - tb[0]
    gap = 8
    total_w = pad_x + emoji_size + gap + tw + pad_x
    x1 = x0 + total_w
    y1 = y0 + BADGE_H

    # 배지 배경
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=bg)
    img = Image.alpha_composite(img, layer)

    # 배지 수직 중앙 y
    badge_cy = y0 + BADGE_H // 2
    ex = x0 + pad_x

    # 이모지: 국기면 PNG, 아니면 Color Emoji 폰트
    fp = F.flag_path(emoji)
    if fp:
        ey = badge_cy - emoji_size // 2
        flag_img = Image.open(fp).convert("RGBA").resize(
            (emoji_size, emoji_size), Image.LANCZOS)
        img.paste(flag_img, (ex, ey), flag_img)
    elif _EMOJI_FONT_PATH:
        try:
            ef = ImageFont.truetype(_EMOJI_FONT_PATH, emoji_size)
            ey = badge_cy - emoji_size // 2
            el = Image.new("RGBA", img.size, (0, 0, 0, 0))
            ImageDraw.Draw(el).text((ex, ey), emoji,
                                    font=ef, embedded_color=True, anchor="lt")
            img = Image.alpha_composite(img, el)
        except Exception:
            pass

    # 텍스트: bb[1] 오프셋 보정으로 수직 중앙정렬
    th = tb[3] - tb[1]
    tx = ex + emoji_size + gap
    ty = badge_cy - th // 2 - tb[1]

    draw = ImageDraw.Draw(img)
    draw.text((tx, ty), text, font=text_font, fill=(*fg[:3], 255))
    return img, draw, x1


def _alpha_pill(img: Image.Image, cx: int, y: int, text: str, font,
                bg: tuple, fg: tuple, pad_x: int = 28, pad_y: int = 12):
    """중앙정렬 pill 배지 — alpha_composite 방식. 다음 y 반환"""
    tmp_draw = ImageDraw.Draw(img)
    bb = tmp_draw.textbbox((0,0), text, font=font)
    tw = bb[2] - bb[0]
    th = bb[3] - bb[1]
    x0 = cx - tw//2 - pad_x
    x1 = cx + tw//2 + pad_x
    y1 = y + th + pad_y*2
    layer = Image.new("RGBA", img.size, (0,0,0,0))
    ImageDraw.Draw(layer).rounded_rectangle([x0,y,x1,y1], radius=12, fill=bg)
    img = Image.alpha_composite(img, layer)
    draw = ImageDraw.Draw(img)
    draw.text((cx - tw//2, y + pad_y), text, font=font, fill=(*fg[:3], 255))
    return img, draw, y1 + CONTENT_GAP


def _tw(draw: ImageDraw.Draw, text: str, font) -> int:
    return draw.textbbox((0,0), text, font=font)[2]


def _th(draw: ImageDraw.Draw, text: str, font) -> int:
    bb = draw.textbbox((0,0), text, font=font)
    return bb[3] - bb[1]


def _section_label(draw: ImageDraw.Draw, y: int, text: str, font,
                   text_fill: tuple, line_fill: tuple,
                   card_w: int = 1080, pad: int = PAD) -> int:
    """'─── 텍스트 ───' 스타일 섹션 레이블. 다음 y 반환."""
    bb   = draw.textbbox((0, 0), text, font=font)
    tw   = bb[2] - bb[0]
    th   = bb[3] - bb[1]
    tx   = (card_w - tw) // 2
    ty   = y - bb[1]                        # bb[1] 오프셋 보정
    line_y = y + (bb[3] + bb[1]) // 2      # 시각적 중앙 선
    gap  = 14                               # 텍스트~선 간격
    draw.line([(pad, line_y), (tx - gap, line_y)],           fill=line_fill, width=1)
    draw.line([(tx + tw + gap, line_y), (card_w - pad, line_y)], fill=line_fill, width=1)
    draw.text((tx, ty), text, font=font, fill=text_fill)
    return y + th


def _wrap(draw: ImageDraw.Draw, text: str, font, max_w: int,
          is_cjk: bool = False) -> list[str]:
    if is_cjk:
        lines, cur = [], ""
        for ch in text:
            if _tw(draw, cur+ch, font) > max_w:
                lines.append(cur); cur = ch
            else:
                cur += ch
        if cur: lines.append(cur)
        return lines
    words = text.split()
    lines, cur = [], ""
    for w in words:
        test = (cur+" "+w).strip()
        if _tw(draw, test, font) > max_w:
            if cur: lines.append(cur)
            cur = w
        else:
            cur = test
    if cur: lines.append(cur)
    return lines


def _fit_font(draw: ImageDraw.Draw, text: str, font_fn, max_w: int,
              start: int = 88, stop: int = 36, step: int = 4):
    for size in range(start, stop-1, -step):
        f = font_fn(size)
        if _tw(draw, text, f) <= max_w:
            return f, size
    return font_fn(stop), stop


def _draw_lines_left(draw: ImageDraw.Draw, lines: list[str], font,
                     x: int, y: int, fill: tuple, gap: int = 10) -> int:
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += _th(draw, line, font) + gap
    return y


def _main_font_fn(lang: str):
    """언어별 메인 표현 폰트 함수 반환 (영어는 Outfit 대소문자)"""
    if lang == "ja":
        return F.noto_jp
    if lang == "zh":
        return F.noto_sc
    return F.outfit  # 영어: Outfit (대소문자 지원)


def _topic_to_slot(topic) -> str:
    """topic dict 또는 slot str → theme_slot str 반환"""
    if isinstance(topic, dict):
        return topic.get("theme_slot", "morning")
    return topic  # 이미 slot str인 경우 (하위 호환)


# ── 메인 렌더 ────────────────────────────────────────────────────────────────

# 레이아웃 구역 상수
_EXPR_ZONE_TOP    = 160   # 표현 구역 시작 y
_EXPR_ZONE_BOTTOM = 690   # 표현 구역 끝 y  (상단 64%)
_VOCAB_ZONE_TOP   = 720   # 단어 구역 시작 y
_VOCAB_ZONE_BOT   = 1040  # 단어 구역 끝 y


def render(data: dict, lang: str, topic, date_str: str = "", save: bool = True) -> str:
    """
    표현 카드 렌더링.
    topic: dict (TOPIC_CONFIG 항목) 또는 str (하위 호환용 slot 이름)
    """
    F.ensure_fonts()

    slot   = _topic_to_slot(topic)
    theme  = CARD_THEMES[(lang, slot)]
    lc     = LANG_CONFIG[lang]
    is_cjk = lang in ("zh", "ja")
    cx     = CARD_W // 2

    # topic 표시 정보 추출
    if isinstance(topic, dict):
        badge_text = topic["badge"]
        badge_emoji = topic["emoji"]
    else:
        sc = SLOT_CONFIG[slot]
        badge_text  = sc["topic_badge"]
        badge_emoji = sc["emoji"]

    # ── 배경 ─────────────────────────────────────────────────────────
    g = theme["gradient"]
    bg = _gradient(CARD_W, CARD_H, g[0], g[1], g[2] if len(g)>2 else None)
    img = bg.convert("RGBA")
    img = _dot_overlay(img, theme["text_main"])
    img = _emoji_bg(img, theme["emoji"])
    draw = ImageDraw.Draw(img)

    ts        = theme["text_sub"]
    sub_fill  = (*ts[:3], ts[3] if len(ts)>3 else 200)
    main_fill = (*theme["text_main"], 255)
    # 한글 음차용: sub_fill보다 살짝 밝게
    phonetic_fill = (*ts[:3], min(ts[3]+30, 255) if len(ts)>3 else 220)

    # ── 상단 배지 ─────────────────────────────────────────────────────
    lang_badge_font = F.noto_kr(30) if lang in ("zh", "ja") else F.outfit(30)
    img, draw, _ = _alpha_badge_emoji(
        img, PAD, BADGE_Y, radius=26,
        bg=theme["lang_badge_bg"], emoji=lc["flag"], text=lc["name_native"],
        emoji_size=32, text_font=lang_badge_font, fg=theme["lang_badge_fg"])

    topic_font = F.outfit(28)
    tmp_tb = ImageDraw.Draw(img).textbbox((0,0), badge_text, font=topic_font)
    slot_w = BADGE_PAD_X + 32 + 8 + (tmp_tb[2]-tmp_tb[0]) + BADGE_PAD_X
    sx = CARD_W - PAD - slot_w
    img, draw, _ = _alpha_badge_emoji(
        img, sx, BADGE_Y, radius=26,
        bg=theme["topic_badge_bg"], emoji=badge_emoji, text=badge_text,
        emoji_size=32, text_font=topic_font, fg=theme["topic_badge_fg"])

    # ── Korean Anchor — 배지 바로 아래 고정 ────────────────────────────
    anchor  = data.get("korean_anchor", "")
    lbl_txt = anchor if anchor else "오늘의 표현"
    label_font = F.noto_kr(28)
    lbl_f   = F.noto_kr(34) if anchor else label_font
    anchor_y = BADGE_Y + BADGE_H + 24
    lbl_bb  = draw.textbbox((0, 0), lbl_txt, font=lbl_f)
    draw.text(((CARD_W - (lbl_bb[2]-lbl_bb[0])) // 2, anchor_y - lbl_bb[1]),
              lbl_txt, font=lbl_f, fill=sub_fill)

    phonetic_text = data.get("korean_phonetic", "")
    bonus_phonetic = data.get("bonus_korean_phonetic", "")
    bko = data.get("bonus_korean", "")

    # ── 폰트 크기 자동 축소: 전체 콘텐츠가 카드 안에 들어올 때까지 ────
    avail_top_base = anchor_y + _th(draw, lbl_txt, lbl_f) + 40
    avail_bot = CARD_H - 60  # 워터마크 여백
    total_avail = avail_bot - avail_top_base

    font_fn = _main_font_fn(lang)
    scale = 1.0
    for attempt in range(5):  # 최대 4회 축소
        _s = lambda sz: max(int(sz * scale), 18)
        main_font, _ = _fit_font(draw, data["main_expression"],
                                  font_fn, USABLE_W, start=_s(88), stop=_s(40))
        phonetic_font = F.noto_kr(_s(30))
        pron_font     = F.noto_kr(_s(34))
        ko_font       = F.noto_kr(_s(50))
        bonus_font    = font_fn(_s(38))
        bko_font      = F.noto_kr(_s(32))
        bonus_label_font = F.noto_kr(_s(22))
        bph_font      = F.noto_kr(_s(24))

        ko_lines = _wrap(draw, data["korean_translation"], ko_font, USABLE_W - 56, True)

        # 메인 블록 높이
        mh = 0
        for ln in ko_lines: mh += _th(draw, ln, ko_font) + 6
        mh += 32 + 20
        for ln in _wrap(draw, data["main_expression"], main_font, USABLE_W, is_cjk):
            mh += _th(draw, ln, main_font) + 14
        mh += 10
        if phonetic_text:
            for ln in _wrap(draw, phonetic_text, phonetic_font, USABLE_W, True):
                mh += _th(draw, ln, phonetic_font) + 6
            mh += 10
        if lc["has_pronunciation"] and data.get("pronunciation"):
            mh += _th(draw, data["pronunciation"], pron_font) + 14

        # 보너스 블록 높이
        bh = _th(draw, "보너스 표현", bonus_label_font) + 16
        for ln in _wrap(draw, data.get("bonus_expression",""), bonus_font, USABLE_W, is_cjk):
            bh += _th(draw, ln, bonus_font) + 8
        if bonus_phonetic:
            for ln in _wrap(draw, bonus_phonetic, bph_font, USABLE_W, True):
                bh += _th(draw, ln, bph_font) + 6
            bh += 4
        if bko:
            for ln in _wrap(draw, bko, bko_font, USABLE_W, True):
                bh += _th(draw, ln, bko_font) + 6

        if mh + bh + 30 <= total_avail:  # 30px 최소 간격
            break
        scale -= 0.1  # 10%씩 축소

    content_h = mh
    avail_top = avail_top_base
    avail_h   = avail_bot - avail_top
    # 보너스 하단 고정 위치 결정
    bonus_block_h = bh
    by_start = CARD_H - 60 - bonus_block_h
    # 메인 콘텐츠: 보너스 위 영역에서 중앙 배치
    main_avail_bot = by_start - 20  # 보너스와 20px 간격
    main_avail = main_avail_bot - avail_top
    golden_center = avail_top + int(main_avail * 0.38)
    y = max(golden_center - content_h // 2, avail_top)
    y = min(y, main_avail_bot - content_h)  # 보너스와 겹침 방지

    # ── 1) 한국어 번역 pill (중앙, 줄바꿈 지원) ─────────────────────
    kpx, kpy = 28, 14
    ko_total_h = sum(_th(draw, ln, ko_font) + 6 for ln in ko_lines) - 6
    pill_h = ko_total_h + kpy * 2
    # pill 너비 = 가장 긴 줄 기준
    ko_max_w = max(_tw(draw, ln, ko_font) for ln in ko_lines)
    kx0 = cx - ko_max_w//2 - kpx; kx1 = cx + ko_max_w//2 + kpx
    ky1 = y + pill_h
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle([kx0, y, kx1, ky1], radius=14,
                                             fill=theme["kr_badge_bg"])
    img = Image.alpha_composite(img, layer)
    draw = ImageDraw.Draw(img)
    ty = y + kpy
    for ln in ko_lines:
        lw = _tw(draw, ln, ko_font)
        bb = draw.textbbox((0, 0), ln, font=ko_font)
        draw.text(((CARD_W - lw) // 2, ty - bb[1]), ln, font=ko_font, fill=main_fill)
        ty += _th(draw, ln, ko_font) + 6
    y = ky1 + 20

    # ── 2) 영어 메인 표현 (중앙 정렬) ────────────────────────────────
    main_lines = _wrap(draw, data["main_expression"], main_font, USABLE_W, is_cjk)
    for line in main_lines:
        lw = _tw(draw, line, main_font)
        draw.text(((CARD_W - lw) // 2, y), line, font=main_font, fill=main_fill)
        y += _th(draw, line, main_font) + 14
    y += 10

    # ── 3) 한글 음차 발음 (중앙, 줄바꿈 지원) ────────────────────────
    if phonetic_text:
        ph_lines = _wrap(draw, phonetic_text, phonetic_font, USABLE_W, True)
        for ln in ph_lines:
            pw = _tw(draw, ln, phonetic_font)
            draw.text(((CARD_W - pw) // 2, y), ln,
                      font=phonetic_font, fill=phonetic_fill)
            y += _th(draw, ln, phonetic_font) + 6
        y += 10

    # ── 4) 발음 (중/일, 중앙) ────────────────────────────────────────
    if lc["has_pronunciation"] and data.get("pronunciation"):
        pt = data["pronunciation"]
        pw = _tw(draw, pt, pron_font)
        draw.text(((CARD_W - pw) // 2, y), pt, font=pron_font, fill=sub_fill)
        y += _th(draw, pt, pron_font) + 14

    # ── 보너스 표현 — 하단 고정 ────────────────────────────────────────
    bonus_label = "보너스 표현"
    bonus_lines = _wrap(draw, data.get("bonus_expression",""), bonus_font, USABLE_W, is_cjk)
    by = by_start

    # "보너스 표현" 레이블
    blw = _tw(draw, bonus_label, bonus_label_font)
    draw.text(((CARD_W - blw) // 2, by), bonus_label,
              font=bonus_label_font, fill=sub_fill)
    by += _th(draw, bonus_label, bonus_label_font) + 16

    # 보너스 한국어 (먼저)
    if bko:
        bko_lines = _wrap(draw, bko, bko_font, USABLE_W, True)
        for ln in bko_lines:
            bkow = _tw(draw, ln, bko_font)
            draw.text(((CARD_W-bkow)//2, by), ln, font=bko_font, fill=main_fill)
            by += _th(draw, ln, bko_font) + 6

    # 보너스 영어 표현
    for line in bonus_lines:
        lw = _tw(draw, line, bonus_font)
        draw.text(((CARD_W-lw)//2, by), line, font=bonus_font, fill=main_fill)
        by += _th(draw, line, bonus_font) + 8

    # 보너스 한글 발음
    if bonus_phonetic:
        bph_lines = _wrap(draw, bonus_phonetic, bph_font, USABLE_W, True)
        for ln in bph_lines:
            bphw = _tw(draw, ln, bph_font)
            draw.text(((CARD_W-bphw)//2, by), ln,
                      font=bph_font, fill=phonetic_fill)
            by += _th(draw, ln, bph_font) + 6

    # ── 워터마크 ─────────────────────────────────────────────────────
    wm_font = F.noto_kr(22)
    wm = "@langcard.studio"
    wmw = _tw(draw, wm, wm_font)
    draw.text(((CARD_W-wmw)//2, CARD_H - 38), wm,
              font=wm_font, fill=(*ts[:3], ts[3]//2 if len(ts)>3 else 90))

    # ── 저장 ─────────────────────────────────────────────────────────
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    _date    = date_str or _today_kst().strftime("%Y%m%d")
    out_path = os.path.join(OUTPUT_DIR, f"expr_{lang}_{slot}_{_date}.png")
    if save:
        img.convert("RGB").save(out_path, "PNG", optimize=True)
        print(f"  ✓ 카드 저장: {out_path}")
    return out_path


# ── 단어 전용 카드 렌더러 ─────────────────────────────────────────────────────

def render_vocab(data: dict, lang: str, topic, date_str: str = "", save: bool = True) -> str:
    """
    단어 전용 카드 렌더링.
    topic: dict (TOPIC_CONFIG 항목) 또는 str (하위 호환용 slot 이름)
    """
    F.ensure_fonts()

    slot   = _topic_to_slot(topic)
    theme  = CARD_THEMES[(lang, slot)]
    lc     = LANG_CONFIG[lang]
    is_cjk = lang in ("zh", "ja")
    cx     = CARD_W // 2

    # topic 표시 정보 추출
    if isinstance(topic, dict):
        badge_text  = topic["badge"]
        badge_emoji = topic["emoji"]
    else:
        sc = SLOT_CONFIG[slot]
        badge_text  = sc["topic_badge"]
        badge_emoji = sc["emoji"]

    # ── 배경 ─────────────────────────────────────────────────────────
    g = theme["gradient"]
    bg = _gradient(CARD_W, CARD_H, g[0], g[1], g[2] if len(g)>2 else None)
    img = bg.convert("RGBA")
    img = _dot_overlay(img, theme["text_main"])
    img = _emoji_bg(img, theme["emoji"])
    draw = ImageDraw.Draw(img)

    ts        = theme["text_sub"]
    sub_fill  = (*ts[:3], ts[3] if len(ts)>3 else 200)
    main_fill = (*theme["text_main"], 255)
    phonetic_fill = (*ts[:3], min(ts[3]+30, 255) if len(ts)>3 else 220)

    # ── 상단 배지 ─────────────────────────────────────────────────────
    lang_badge_font = F.noto_kr(30) if lang in ("zh", "ja") else F.outfit(30)
    img, draw, _ = _alpha_badge_emoji(
        img, PAD, BADGE_Y, radius=26,
        bg=theme["lang_badge_bg"], emoji=lc["flag"], text=lc["name_native"],
        emoji_size=32, text_font=lang_badge_font, fg=theme["lang_badge_fg"])

    topic_font = F.outfit(28)
    tmp_tb     = ImageDraw.Draw(img).textbbox((0,0), badge_text, font=topic_font)
    slot_w     = BADGE_PAD_X + 32 + 8 + (tmp_tb[2]-tmp_tb[0]) + BADGE_PAD_X
    img, draw, _ = _alpha_badge_emoji(
        img, CARD_W - PAD - slot_w, BADGE_Y, radius=26,
        bg=theme["topic_badge_bg"], emoji=badge_emoji, text=badge_text,
        emoji_size=32, text_font=topic_font, fg=theme["topic_badge_fg"])

    font_fn      = _main_font_fn(lang)
    vocab        = data.get("vocab", [])
    word_font    = font_fn(50)
    mean_font    = F.noto_kr(36)
    pron_font    = F.noto_kr(28)
    phonetic_font = F.noto_kr(24)
    lbl_font     = F.noto_kr(28)
    item_gap     = 44

    # ── "오늘의 단어" 레이블 — 배지 바로 아래 고정 ─────────────────────
    label_y = BADGE_Y + BADGE_H + 24
    lbl_bb = draw.textbbox((0,0), "오늘의 단어", font=lbl_font)
    draw.text(((CARD_W - (lbl_bb[2]-lbl_bb[0])) // 2, label_y - lbl_bb[1]),
              "오늘의 단어", font=lbl_font, fill=sub_fill)

    # ── 높이 측정 → 황금비 배치 (레이블 제외) ──────────────────────────
    def _vocab_block_h() -> int:
        h = 0
        for item in vocab[:3]:
            word = item.get("word","")
            mean = item.get("meaning","")
            pron = item.get("pronunciation") or ""
            kp   = item.get("korean_phonetic", "")
            row_h = max(_th(draw, word, word_font), _th(draw, mean, mean_font))
            h += row_h
            if pron and lc["has_pronunciation"]:
                h += 6 + _th(draw, pron, pron_font)
            if kp:
                h += 4 + _th(draw, kp, phonetic_font)
            h += item_gap
        return h - item_gap

    block_h   = _vocab_block_h()
    avail_top = label_y + _th(draw, "오늘의 단어", lbl_font) + 40
    avail_bot = CARD_H - 50
    avail_h   = avail_bot - avail_top
    golden_center = avail_top + int(avail_h * 0.38)
    vy = max(golden_center - block_h // 2, avail_top)

    # ── 단어 항목 ────────────────────────────────────────────────────
    for i, item in enumerate(vocab[:3]):
        word = item.get("word","")
        mean = item.get("meaning","")
        pron = item.get("pronunciation") or ""
        kp   = item.get("korean_phonetic", "")

        # 단어 + 뜻 한 줄
        ww   = _tw(draw, word, word_font)
        mw   = _tw(draw, mean, mean_font)
        sep  = "  "
        sw   = _tw(draw, sep, word_font)
        row_w = ww + sw + mw
        tx   = (CARD_W - row_w) // 2

        wh = _th(draw, word, word_font)
        mh = _th(draw, mean, mean_font)
        row_h = max(wh, mh)
        wb = draw.textbbox((0,0), word, font=word_font)
        mb = draw.textbbox((0,0), mean, font=mean_font)
        draw.text((tx,          vy + (row_h - wh) // 2 - wb[1]), word, font=word_font, fill=main_fill)
        draw.text((tx+ww+sw,    vy + (row_h - mh) // 2 - mb[1]), mean, font=mean_font, fill=sub_fill)
        vy += row_h

        if pron and lc["has_pronunciation"]:
            vy += 6
            pb   = draw.textbbox((0,0), pron, font=pron_font)
            pw   = pb[2] - pb[0]
            draw.text(((CARD_W-pw)//2, vy - pb[1]), pron, font=pron_font, fill=sub_fill)
            vy += _th(draw, pron, pron_font)

        # 한글 음차 (발음 아래)
        if kp:
            vy += 4
            kpb  = draw.textbbox((0,0), kp, font=phonetic_font)
            kpw  = kpb[2] - kpb[0]
            draw.text(((CARD_W-kpw)//2, vy - kpb[1]), kp,
                      font=phonetic_font, fill=phonetic_fill)
            vy += _th(draw, kp, phonetic_font)

        if i < len(vocab[:3]) - 1:
            vy += item_gap

    # ── 워터마크 ─────────────────────────────────────────────────────
    wm_font = F.noto_kr(22)
    wm      = "@langcard.studio"
    wmw     = _tw(draw, wm, wm_font)
    draw.text(((CARD_W-wmw)//2, CARD_H - 38), wm,
              font=wm_font, fill=(*ts[:3], ts[3]//2 if len(ts)>3 else 90))

    # ── 저장 ─────────────────────────────────────────────────────────
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    _date    = date_str or _today_kst().strftime("%Y%m%d")
    out_path = os.path.join(OUTPUT_DIR, f"vocab_{lang}_{slot}_{_date}.png")
    if save:
        img.convert("RGB").save(out_path, "PNG", optimize=True)
        print(f"  ✓ 단어 카드 저장: {out_path}")
    return out_path


# ── 종합 캐러셀 커버 카드 ──────────────────────────────────────────────────────

def render_recap_cover(all_data: dict, topic: dict, date_str: str) -> str:
    """
    종합 캐러셀 첫 슬라이드 커버 카드 생성.
    날짜 기반 제목 + 3개국어 표현 미리보기 + 스와이프 CTA.
    date_str: "YYYYMMDD" (어제 날짜)
    Returns: output/recap_cover_{date_str}.png
    """
    F.ensure_fonts()

    # ── 날짜 포맷 변환: "20260305" → "3월 5일의 표현" ─────────────────
    dt      = datetime.strptime(date_str, "%Y%m%d")
    date_ko = f"{dt.month}월 {dt.day}일의 표현"

    cx = CARD_W // 2

    # ── 배경: 짙은 네이비 그라디언트 ──────────────────────────────────
    bg  = _gradient(CARD_W, CARD_H, (12, 15, 40), (28, 35, 75), (18, 22, 55))
    img = bg.convert("RGBA")

    # 도트 오버레이 (밝은 텍스트 기준)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d_ov  = ImageDraw.Draw(layer)
    for x in range(0, CARD_W, 20):
        for y in range(0, CARD_H, 20):
            d_ov.ellipse([x-1, y-1, x+1, y+1], fill=(255, 255, 255, 12))
    img = Image.alpha_composite(img, layer)

    draw = ImageDraw.Draw(img)

    # ── 색상 정의 ──────────────────────────────────────────────────────
    WHITE        = (255, 255, 255, 255)
    WHITE_DIM    = (255, 255, 255, 160)
    WHITE_FAINT  = (255, 255, 255, 100)
    GOLD         = (255, 213, 79, 255)    # 날짜 강조색
    DIVIDER      = (255, 255, 255, 40)

    # ── 폰트 ──────────────────────────────────────────────────────────
    date_font    = F.noto_kr(62)   # "3월 5일의 표현"
    label_font   = F.noto_kr(28)   # 섹션 레이블
    expr_font_en = F.outfit(40)
    expr_font_zh = F.noto_sc(38)
    expr_font_ja = F.noto_jp(38)
    phon_font    = F.noto_kr(26)   # 한글 음차
    cta_font     = F.noto_kr(34)   # 하단 CTA

    _EXPR_FONTS = {"en": expr_font_en, "zh": expr_font_zh, "ja": expr_font_ja}

    # ── 상단 주제 배지 (우상단) ───────────────────────────────────────
    badge_text  = topic.get("badge", "")
    badge_emoji = topic.get("emoji", "📖")
    topic_font  = F.outfit(28)
    tmp_tb      = draw.textbbox((0, 0), badge_text, font=topic_font)
    slot_w      = BADGE_PAD_X + 32 + 8 + (tmp_tb[2]-tmp_tb[0]) + BADGE_PAD_X
    img, draw, _ = _alpha_badge_emoji(
        img, CARD_W - PAD - slot_w, BADGE_Y, radius=26,
        bg=(255, 213, 79, 200), emoji=badge_emoji, text=badge_text,
        emoji_size=32, text_font=topic_font, fg=(26, 26, 26))

    # ── 날짜 제목 (수직 1/4 지점) ─────────────────────────────────────
    y = 180
    dt_bb = draw.textbbox((0, 0), date_ko, font=date_font)
    dt_w  = dt_bb[2] - dt_bb[0]
    draw.text(((CARD_W - dt_w) // 2, y - dt_bb[1]), date_ko,
              font=date_font, fill=GOLD)
    y += (dt_bb[3] - dt_bb[1]) + 32

    # 구분선
    draw.line([(PAD, y), (CARD_W - PAD, y)], fill=DIVIDER, width=1)
    y += 36

    # ── "어제의 표현" 레이블 ──────────────────────────────────────────
    _section_label(draw, y, "어제의 표현 미리보기", label_font,
                   text_fill=(*WHITE_DIM[:3], WHITE_DIM[3]),
                   line_fill=DIVIDER)
    y += _th(draw, "어제의 표현 미리보기", label_font) + 32

    # ── 언어별 표현 미리보기 ──────────────────────────────────────────
    for lang in ("en", "zh", "ja"):
        if lang not in all_data:
            continue
        d   = all_data[lang]
        lc  = LANG_CONFIG[lang]
        ef  = _EXPR_FONTS.get(lang, expr_font_en)

        # 국기 배지 (좌측 인라인)
        fp = F.flag_path(lc["flag"])
        flag_size = 36
        fx = PAD + 8
        fy = y + 4

        if fp:
            flag_img = Image.open(fp).convert("RGBA").resize(
                (flag_size, flag_size), Image.LANCZOS)
            img.paste(flag_img, (fx, fy), flag_img)

        # 표현 텍스트 (국기 오른쪽)
        expr_x     = PAD + 8 + flag_size + 14
        expr_max_w = CARD_W - expr_x - PAD
        expr_text  = d.get("main_expression", "")
        is_cjk     = lang in ("zh", "ja")

        # 한 줄에 맞게 잘라내기 (너무 길면 ...)
        while _tw(draw, expr_text, ef) > expr_max_w and len(expr_text) > 6:
            expr_text = expr_text[:-1]
        if expr_text != d.get("main_expression", ""):
            expr_text = expr_text.rstrip(".,!？！…") + "…"

        eb = draw.textbbox((0, 0), expr_text, ef)
        draw.text((expr_x, y - eb[1]), expr_text, font=ef, fill=WHITE)
        y += (eb[3] - eb[1]) + 6

        # 한글 음차
        phonetic = d.get("korean_phonetic", "")
        if phonetic:
            # 너무 길면 자르기
            ph_disp = phonetic
            while _tw(draw, ph_disp, phon_font) > expr_max_w and len(ph_disp) > 4:
                ph_disp = ph_disp[:-1]
            if ph_disp != phonetic:
                ph_disp = ph_disp.rstrip() + "…"
            ph_x = expr_x
            pb   = draw.textbbox((0, 0), ph_disp, phon_font)
            draw.text((ph_x, y - pb[1]), ph_disp,
                      font=phon_font, fill=WHITE_FAINT)
            y += (pb[3] - pb[1]) + 4

        y += 28   # 언어 간 간격

    # ── 구분선 ────────────────────────────────────────────────────────
    draw.line([(PAD, y), (CARD_W - PAD, y)], fill=DIVIDER, width=1)
    y += 36

    # ── CTA: 스와이프 ─────────────────────────────────────────────────
    cta_text = "스와이프해서 복습하기"
    cta_w    = _tw(draw, cta_text, cta_font)
    cb       = draw.textbbox((0, 0), cta_text, cta_font)
    draw.text(((CARD_W - cta_w) // 2, y - cb[1]),
              cta_text, font=cta_font, fill=GOLD)
    y += (cb[3] - cb[1]) + 14

    # 화살표 (NotoSansKR 지원 문자)
    arrow = "- - -"
    af    = F.noto_kr(28)
    aw    = _tw(draw, arrow, af)
    ab    = draw.textbbox((0, 0), arrow, af)
    draw.text(((CARD_W - aw) // 2, y - ab[1]), arrow, font=af, fill=(*GOLD[:3], 160))

    # ── 워터마크 ──────────────────────────────────────────────────────
    wm_font = F.noto_kr(22)
    wm      = "@langcard.studio"
    wmw     = _tw(draw, wm, wm_font)
    draw.text(((CARD_W - wmw) // 2, CARD_H - 38), wm,
              font=wm_font, fill=(255, 255, 255, 60))

    # ── 저장 ──────────────────────────────────────────────────────────
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, f"recap_cover_{date_str}.png")
    img.convert("RGB").save(out_path, "PNG", optimize=True)
    print(f"  ✓ 커버 카드 저장: {out_path}")
    return out_path


# ── 훅 & 아웃트로 프레임 ────────────────────────────────────────────────────

FRAMES_DIR = os.path.join(OUTPUT_DIR, "reel_frames")  # reel.py와 동일 경로 공유


# ── 슬롯 섹션 커버 (복습 캐러셀용) ──────────────────────────────────────────

def render_slot_cover(slot: str, lang: str, data: dict, topic, date_str: str) -> str:
    """
    복습 캐러셀 섹션 구분 커버 카드.
    슬롯(아침/점심/저녁) + 언어 + 표현 미리보기.
    Returns: output/slot_cover_{slot}_{date_str}.png
    """
    F.ensure_fonts()

    _SLOT_LABEL  = {"morning": "아침 표현", "lunch": "점심 표현", "evening": "저녁 표현"}
    _SLOT_TIME   = {"morning": "08:00 AM",  "lunch": "12:00 PM",  "evening": "08:00 PM"}
    _SLOT_ACCENT = {
        "morning": (255, 190, 60),   # amber
        "lunch":   (80,  220, 170),  # teal
        "evening": (180, 120, 255),  # violet
    }

    slot_label = _SLOT_LABEL.get(slot, slot)
    slot_time  = _SLOT_TIME.get(slot, "")
    accent     = _SLOT_ACCENT.get(slot, (255, 213, 79))
    lc  = LANG_CONFIG[lang]
    cx  = CARD_W // 2

    # ── 배경: 짙은 네이비 (recap_cover와 동일) ───────────────────────
    bg  = _gradient(CARD_W, CARD_H, (12, 15, 40), (28, 35, 75), (18, 22, 55))
    img = bg.convert("RGBA")

    # 도트 오버레이
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d_ov  = ImageDraw.Draw(layer)
    for x in range(0, CARD_W, 20):
        for y in range(0, CARD_H, 20):
            d_ov.ellipse([x - 1, y - 1, x + 1, y + 1], fill=(255, 255, 255, 12))
    img = Image.alpha_composite(img, layer)

    # 상단 컬러 액센트 바
    bar_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(bar_layer).rectangle([0, 0, CARD_W, 10], fill=(*accent, 255))
    img = Image.alpha_composite(img, bar_layer)

    draw = ImageDraw.Draw(img)
    WHITE     = (255, 255, 255, 255)
    WHITE_DIM = (255, 255, 255, 160)
    DIVIDER   = (255, 255, 255, 40)

    # ── 슬롯 시간 pill (상단 중앙) ────────────────────────────────────
    time_font = F.outfit(30)
    tb = draw.textbbox((0, 0), slot_time, font=time_font)
    tw = tb[2] - tb[0]; th = tb[3] - tb[1]
    px, py = 24, 12
    tx0 = cx - tw // 2 - px; tx1 = cx + tw // 2 + px
    ty0 = 60;                 ty1 = ty0 + th + py * 2
    pill = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(pill).rounded_rectangle([tx0, ty0, tx1, ty1], radius=16,
                                           fill=(*accent, 50))
    img  = Image.alpha_composite(img, pill)
    draw = ImageDraw.Draw(img)
    draw.text((cx - tw // 2, ty0 + py - tb[1]), slot_time,
              font=time_font, fill=(*accent, 255))

    # ── 슬롯 레이블 (중앙) ────────────────────────────────────────────
    label_font = F.noto_kr(90)
    lb = draw.textbbox((0, 0), slot_label, font=label_font)
    lw = lb[2] - lb[0]; lh = lb[3] - lb[1]
    y_label = CARD_H // 2 - lh // 2 - 60
    draw.text(((CARD_W - lw) // 2, y_label - lb[1]), slot_label,
              font=label_font, fill=WHITE)
    y_after = y_label + lh + 40

    # ── 국기 + 언어명 ─────────────────────────────────────────────────
    lang_font = F.noto_kr(46)
    lang_text = lc["name_native"]
    flag_size = 48
    ltb = draw.textbbox((0, 0), lang_text, font=lang_font)
    ltw = ltb[2] - ltb[0]; lth = ltb[3] - ltb[1]
    row_w = flag_size + 16 + ltw
    fx = cx - row_w // 2
    fy = y_after

    fp = F.flag_path(lc["flag"])
    if fp:
        flag_img = Image.open(fp).convert("RGBA").resize(
            (flag_size, flag_size), Image.LANCZOS)
        img.paste(flag_img, (fx, fy), flag_img)

    draw = ImageDraw.Draw(img)
    draw.text((fx + flag_size + 16,
               fy + flag_size // 2 - lth // 2 - ltb[1]),
              lang_text, font=lang_font, fill=(*accent, 255))
    y_after = fy + max(flag_size, lth) + 52

    # ── 표현 미리보기 ─────────────────────────────────────────────────
    expr_text = data.get("main_expression", "")
    if expr_text:
        draw.line([(PAD, y_after - 20), (CARD_W - PAD, y_after - 20)],
                  fill=DIVIDER, width=1)
        expr_font = _main_font_fn(lang)(40)
        disp = expr_text
        while _tw(draw, disp, expr_font) > USABLE_W and len(disp) > 6:
            disp = disp[:-1]
        if disp != expr_text:
            disp = disp.rstrip(".,!？！…") + "…"
        eb = draw.textbbox((0, 0), disp, expr_font)
        ew = eb[2] - eb[0]
        draw.text(((CARD_W - ew) // 2, y_after - eb[1]), disp,
                  font=expr_font, fill=WHITE_DIM)

    # ── 워터마크 ─────────────────────────────────────────────────────
    wm_font = F.noto_kr(22)
    wm      = "@langcard.studio"
    wmw     = _tw(draw, wm, wm_font)
    draw.text(((CARD_W - wmw) // 2, CARD_H - 38), wm,
              font=wm_font, fill=(255, 255, 255, 60))

    # ── 저장 ─────────────────────────────────────────────────────────
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, f"slot_cover_{slot}_{date_str}.png")
    img.convert("RGB").save(out_path, "PNG", optimize=True)
    print(f"  ✓ 슬롯 커버 저장: {out_path}")
    return out_path


_HOOK_QUESTION = {
    "en": ("🇺🇸", "영어", "이거 영어로\n어떻게 말할까요?"),
    "zh": ("🇨🇳", "중국어", "이거 중국어로\n어떻게 말할까요?"),
    "ja": ("🇯🇵", "일본어", "이거 일본어로\n어떻게 말할까요?"),
}


def render_hook_frame(lang: str, date_str: str) -> str:
    """
    숏릴스 첫 2초 — 스크롤 정지 훅 프레임.
    언어별 질문("이거 영어로 어떻게 말할까요?")을 크게 표시.
    Returns: output/frames/hook_{lang}_{date_str}.png
    """
    F.ensure_fonts()
    os.makedirs(FRAMES_DIR, exist_ok=True)

    flag_emoji, lang_ko, question = _HOOK_QUESTION.get(
        lang, ("🌐", "외국어", "이거 외국어로\n어떻게 말할까요?")
    )
    cx = CARD_W // 2

    # ── 배경: 짙은 네이비 그라디언트 (recap_cover와 동일) ──────────────
    bg  = _gradient(CARD_W, CARD_H, (12, 15, 40), (28, 35, 75), (18, 22, 55))
    img = bg.convert("RGBA")
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d_ov  = ImageDraw.Draw(layer)
    for x in range(0, CARD_W, 20):
        for y in range(0, CARD_H, 20):
            d_ov.ellipse([x - 1, y - 1, x + 1, y + 1], fill=(255, 255, 255, 12))
    img  = Image.alpha_composite(img, layer)
    draw = ImageDraw.Draw(img)

    WHITE = (255, 255, 255, 255)
    GOLD  = (255, 213, 79, 255)

    # ── 언어 배지 (상단 중앙) ────────────────────────────────────────────
    badge_font = F.noto_kr(32)
    badge_text = f"오늘의 {lang_ko}"
    tb = draw.textbbox((0, 0), badge_text, font=badge_font)
    bw = tb[2] - tb[0]
    bh = tb[3] - tb[1]
    bp = 16
    bx0 = cx - bw // 2 - bp - 20 - 8  # 국기 이미지 여유
    bx1 = cx + bw // 2 + bp
    by0 = 140
    by1 = by0 + bh + bp * 2
    badge_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(badge_layer).rounded_rectangle(
        [bx0, by0, bx1, by1], radius=20, fill=(255, 213, 79, 200)
    )
    img  = Image.alpha_composite(img, badge_layer)
    draw = ImageDraw.Draw(img)

    # 국기 PNG
    fp = F.flag_path(flag_emoji)
    if fp:
        flag_img = Image.open(fp).convert("RGBA").resize((36, 36), Image.LANCZOS)
        img.paste(flag_img, (bx0 + bp, by0 + (by1 - by0 - 36) // 2), flag_img)
        draw = ImageDraw.Draw(img)
    draw.text(
        (bx0 + bp + 36 + 8, by0 + bp - tb[1]),
        badge_text, font=badge_font, fill=(26, 26, 26, 255)
    )

    # ── 질문 텍스트 (중앙) ───────────────────────────────────────────────
    q_font = F.noto_kr(88)
    lines  = question.split("\n")
    line_heights = []
    for line in lines:
        bb = draw.textbbox((0, 0), line, font=q_font)
        line_heights.append(bb[3] - bb[1])
    total_h = sum(line_heights) + 20 * (len(lines) - 1)
    y = CARD_H // 2 - total_h // 2 - 40

    for i, line in enumerate(lines):
        bb  = draw.textbbox((0, 0), line, font=q_font)
        lw  = bb[2] - bb[0]
        draw.text(((CARD_W - lw) // 2, y - bb[1]), line, font=q_font, fill=WHITE)
        y  += line_heights[i] + 20

    # ── 하단 힌트 ────────────────────────────────────────────────────────
    hint_font = F.noto_kr(38)
    hint_text = "소리 켜고 들어봐요 🔊"
    hb = draw.textbbox((0, 0), hint_text, font=hint_font)
    hw = hb[2] - hb[0]
    draw.text(
        ((CARD_W - hw) // 2, CARD_H * 3 // 4 - hb[1]),
        hint_text, font=hint_font, fill=(*GOLD[:3], 200)
    )

    # ── 워터마크 ────────────────────────────────────────────────────────
    wm_font = F.noto_kr(22)
    wm      = "@langcard.studio"
    wmw     = _tw(draw, wm, wm_font)
    draw.text(((CARD_W - wmw) // 2, CARD_H - 38), wm,
              font=wm_font, fill=(255, 255, 255, 60))

    out_path = os.path.join(FRAMES_DIR, f"hook_{lang}_{date_str}.png")
    img.convert("RGB").save(out_path, "PNG", optimize=True)
    print(f"  ✓ 훅 프레임 저장: {out_path}")
    return out_path


def render_outro_frame(date_str: str) -> str:
    """
    숏릴스 마지막 2.5초 — 팔로우 CTA 아웃트로 프레임.
    "@langcard.studio / 팔로우하면 매일 3개국어!"
    Returns: output/frames/outro_{date_str}.png
    """
    F.ensure_fonts()
    os.makedirs(FRAMES_DIR, exist_ok=True)

    cx = CARD_W // 2

    # ── 배경 ────────────────────────────────────────────────────────────
    bg  = _gradient(CARD_W, CARD_H, (10, 12, 35), (22, 30, 65), (15, 18, 48))
    img = bg.convert("RGBA")
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d_ov  = ImageDraw.Draw(layer)
    for x in range(0, CARD_W, 20):
        for y in range(0, CARD_H, 20):
            d_ov.ellipse([x - 1, y - 1, x + 1, y + 1], fill=(255, 255, 255, 12))
    img  = Image.alpha_composite(img, layer)
    draw = ImageDraw.Draw(img)

    WHITE = (255, 255, 255, 255)
    GOLD  = (255, 213, 79, 255)

    # ── 좋아요 + 저장 CTA (상단) ────────────────────────────────────────
    save_font = F.noto_kr(64)
    save_text = "♥ 좋아요   ★ 저장"
    sb = draw.textbbox((0, 0), save_text, font=save_font)
    sw = sb[2] - sb[0]
    draw.text(((CARD_W - sw) // 2, CARD_H // 3 - sb[1]),
              save_text, font=save_font, fill=WHITE)

    # ── 팔로우 CTA (중앙) ────────────────────────────────────────────────
    follow_font  = F.noto_kr(58)
    follow_line1 = "팔로우하면"
    follow_line2 = "매일 3개국어!"
    for i, line in enumerate([follow_line1, follow_line2]):
        fb = draw.textbbox((0, 0), line, font=follow_font)
        fw = fb[2] - fb[0]
        fy = CARD_H // 2 - 20 + i * (fb[3] - fb[1] + 16)
        draw.text(((CARD_W - fw) // 2, fy - fb[1]), line,
                  font=follow_font, fill=WHITE)

    # ── 계정명 배지 ──────────────────────────────────────────────────────
    acc_font = F.outfit(46)
    acc_text = "@langcard.studio"
    ab = draw.textbbox((0, 0), acc_text, font=acc_font)
    aw = ab[2] - ab[0]
    ah = ab[3] - ab[1]
    ax0 = cx - aw // 2 - 24
    ax1 = cx + aw // 2 + 24
    ay0 = CARD_H * 2 // 3 + 20
    ay1 = ay0 + ah + 24
    acc_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(acc_layer).rounded_rectangle(
        [ax0, ay0, ax1, ay1], radius=18, fill=(255, 213, 79, 220)
    )
    img  = Image.alpha_composite(img, acc_layer)
    draw = ImageDraw.Draw(img)
    draw.text((ax0 + 24, ay0 + 12 - ab[1]), acc_text,
              font=acc_font, fill=(20, 20, 50, 255))

    # ── 워터마크 ────────────────────────────────────────────────────────
    wm_font = F.noto_kr(22)
    wm      = "@langcard.studio"
    wmw     = _tw(draw, wm, wm_font)
    draw.text(((CARD_W - wmw) // 2, CARD_H - 38), wm,
              font=wm_font, fill=(255, 255, 255, 60))

    out_path = os.path.join(FRAMES_DIR, f"outro_{date_str}.png")
    img.convert("RGB").save(out_path, "PNG", optimize=True)
    print(f"  ✓ 아웃트로 프레임 저장: {out_path}")
    return out_path


# ── 컬렉션 캐러셀 렌더러 ──────────────────────────────────────────────────────

_COLL_BG1 = (12, 15, 40)
_COLL_BG2 = (28, 35, 75)
_COLL_BG3 = (18, 22, 55)
_COLL_GOLD   = (255, 213, 79, 255)
_COLL_AMBER  = (255, 190, 60, 255)
_COLL_WHITE  = (255, 255, 255, 255)
_COLL_DIM    = (255, 255, 255, 160)
_COLL_FAINT  = (255, 255, 255, 90)
_COLL_DIV    = (255, 255, 255, 40)


def _coll_base_img() -> tuple:
    """컬렉션 공용 다크 배경 + 도트 오버레이. (img, draw) 반환."""
    bg  = _gradient(CARD_W, CARD_H, _COLL_BG1, _COLL_BG2, _COLL_BG3)
    img = bg.convert("RGBA")
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d_ov  = ImageDraw.Draw(layer)
    for x in range(0, CARD_W, 20):
        for y in range(0, CARD_H, 20):
            d_ov.ellipse([x-1, y-1, x+1, y+1], fill=(255, 255, 255, 12))
    img  = Image.alpha_composite(img, layer)
    return img, ImageDraw.Draw(img)


def _coll_watermark(img: Image.Image) -> Image.Image:
    draw = ImageDraw.Draw(img)
    wm_font = F.noto_kr(22)
    wm  = "@langcard.studio"
    wmw = draw.textbbox((0, 0), wm, font=wm_font)[2]
    draw.text(((CARD_W - wmw) // 2, CARD_H - 38), wm,
              font=wm_font, fill=(255, 255, 255, 60))
    return img


def render_collection_cover(theme: dict, date_str: str) -> str:
    """
    컬렉션 캐러셀 커버 카드 (1/10).
    theme: {"title_ko": "...", "title_en": "...", "emoji": "..."}
    Returns: output/collection_cover_{date_str}.png
    """
    F.ensure_fonts()
    img, draw = _coll_base_img()
    cx = CARD_W // 2

    # 상단 날짜 pill
    dt = datetime.strptime(date_str, "%Y%m%d")
    date_txt = f"{dt.month}월 {dt.day}일"
    date_f   = F.noto_kr(30)
    db = draw.textbbox((0, 0), date_txt, font=date_f)
    dw = db[2]-db[0]; dh = db[3]-db[1]
    px, py = 20, 10
    dx0 = cx - dw//2 - px; dx1 = cx + dw//2 + px
    dy0 = 80;               dy1 = dy0 + dh + py*2
    pill = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(pill).rounded_rectangle([dx0, dy0, dx1, dy1], radius=16,
                                           fill=(*_COLL_AMBER[:3], 60))
    img = Image.alpha_composite(img, pill)
    draw = ImageDraw.Draw(img)
    draw.text((cx - dw//2, dy0 + py - db[1]), date_txt,
              font=date_f, fill=_COLL_AMBER)

    # 중앙 이모지 (큰 장식)
    emoji_font_path = None
    for _p in ["/System/Library/Fonts/Apple Color Emoji.ttc",
               "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"]:
        if os.path.exists(_p):
            emoji_font_path = _p
            break
    if emoji_font_path:
        try:
            ef = ImageFont.truetype(emoji_font_path, 160)
            el = Image.new("RGBA", img.size, (0, 0, 0, 0))
            eb = ImageDraw.Draw(el).textbbox((0, 0), theme["emoji"], font=ef)
            ew = eb[2]-eb[0]
            ImageDraw.Draw(el).text((cx - ew//2, 280 - eb[1]), theme["emoji"],
                                    font=ef, embedded_color=True)
            el.putalpha(el.getchannel("A").point(lambda p: int(p * 0.9)))
            img = Image.alpha_composite(img, el)
            draw = ImageDraw.Draw(img)
        except Exception:
            pass

    # 테마 제목 KO (대형)
    title_f = F.noto_kr(72)
    tb = draw.textbbox((0, 0), theme["title_ko"], font=title_f)
    tw = tb[2]-tb[0]
    # 너무 길면 축소
    t_font = title_f
    for sz in range(72, 39, -4):
        t_font = F.noto_kr(sz)
        tb = draw.textbbox((0, 0), theme["title_ko"], font=t_font)
        if (tb[2]-tb[0]) <= USABLE_W:
            break
    tb = draw.textbbox((0, 0), theme["title_ko"], font=t_font)
    tw = tb[2]-tb[0]
    draw.text((cx - tw//2, 520 - tb[1]), theme["title_ko"],
              font=t_font, fill=_COLL_WHITE)

    # 테마 제목 EN (작게)
    en_f  = F.outfit(34)
    eb2   = draw.textbbox((0, 0), theme["title_en"], font=en_f)
    ew2   = eb2[2]-eb2[0]
    draw.text((cx - ew2//2, 612 - eb2[1]), theme["title_en"],
              font=en_f, fill=_COLL_DIM)

    # 구분선
    draw.line([(PAD*2, 680), (CARD_W-PAD*2, 680)], fill=_COLL_DIV, width=1)

    # CTA
    cta_f   = F.noto_kr(38)
    cta_txt = "스와이프해서 저장하기"
    cb      = draw.textbbox((0, 0), cta_txt, font=cta_f)
    cw      = cb[2]-cb[0]
    draw.text((cx - cw//2, 720 - cb[1]), cta_txt, font=cta_f, fill=_COLL_GOLD)

    arr_f   = F.noto_kr(30)
    arr_txt = "- - - - - -"
    ab2     = draw.textbbox((0, 0), arr_txt, font=arr_f)
    aw2     = ab2[2]-ab2[0]
    draw.text((cx - aw2//2, 782 - ab2[1]), arr_txt,
              font=arr_f, fill=(*_COLL_GOLD[:3], 140))

    # 아이템 수 표시
    cnt_f   = F.noto_kr(28)
    cnt_txt = "표현 8가지"
    ctb     = draw.textbbox((0, 0), cnt_txt, font=cnt_f)
    ctw     = ctb[2]-ctb[0]
    draw.text((cx - ctw//2, 840 - ctb[1]), cnt_txt,
              font=cnt_f, fill=_COLL_FAINT)

    img = _coll_watermark(img)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, f"collection_cover_{date_str}.png")
    img.convert("RGB").save(out_path, "PNG", optimize=True)
    print(f"  ✓ 컬렉션 커버 저장: {out_path}")
    return out_path


def render_collection_slide(item: dict, index: int, total: int, date_str: str) -> str:
    """
    컬렉션 슬라이드 (2~9/10).
    item: {"korean_phrase": "...", "context": "...",
           "en": "...", "en_phonetic": "...",
           "zh": "...", "zh_phonetic": "...",
           "ja": "...", "ja_phonetic": "..."}
    Returns: output/collection_slide_{index:02d}_{date_str}.png
    """
    F.ensure_fonts()
    img, draw = _coll_base_img()
    cx = CARD_W // 2

    # 슬라이드 번호 pill (우상단)
    num_txt  = f"{index}/{total}"
    num_f    = F.outfit(28)
    nb       = draw.textbbox((0, 0), num_txt, font=num_f)
    nw       = nb[2]-nb[0]; nh = nb[3]-nb[1]
    npx, npy = 16, 8
    nx1      = CARD_W - PAD
    nx0      = nx1 - nw - npx*2
    ny0      = 68; ny1 = ny0 + nh + npy*2
    num_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(num_layer).rounded_rectangle([nx0, ny0, nx1, ny1], radius=14,
                                                fill=(*_COLL_AMBER[:3], 180))
    img  = Image.alpha_composite(img, num_layer)
    draw = ImageDraw.Draw(img)
    draw.text((nx0 + npx, ny0 + npy - nb[1]), num_txt, font=num_f, fill=(20, 20, 50, 255))

    # 상단 강조 바
    bar = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(bar).rectangle([0, 0, CARD_W, 8], fill=(*_COLL_AMBER[:3], 255))
    img  = Image.alpha_composite(img, bar)
    draw = ImageDraw.Draw(img)

    # ── 폰트 사전 결정 ─────────────────────────────────────────────────
    kr_txt  = item.get("korean_phrase", "")
    kr_f    = F.noto_kr(76)
    for sz in range(76, 47, -4):
        kr_f = F.noto_kr(sz)
        kb_tmp = draw.textbbox((0, 0), kr_txt, font=kr_f)
        if (kb_tmp[2]-kb_tmp[0]) <= USABLE_W:
            break

    ctx_txt = item.get("context", "")
    ctx_f   = F.noto_kr(30)
    flag_size  = 44
    phonetic_f = F.noto_kr(24)

    _LANG_EXPRS = [
        ("en", item.get("en", ""), "🇺🇸", F.outfit(42),   item.get("en_phonetic", "")),
        ("zh", item.get("zh", ""), "🇨🇳", F.noto_sc(40),  item.get("zh_phonetic", "")),
        ("ja", item.get("ja", ""), "🇯🇵", F.noto_jp(40),  item.get("ja_phonetic", "")),
    ]

    # ── 전체 콘텐츠 높이 계산 → 세로 중앙 ────────────────────────────
    kb    = draw.textbbox((0, 0), kr_txt, font=kr_f)
    kr_h  = kb[3]-kb[1]
    ctx_h = (_th(draw, ctx_txt, ctx_f) + 12) if ctx_txt else 0
    div_h = 28   # 구분선 영역
    row_h_list = []
    for _, expr, _, ef, phonetic in _LANG_EXPRS:
        eb = draw.textbbox((0, 0), expr[:40], font=ef)
        expr_h = eb[3]-eb[1]
        if phonetic:
            ph = _th(draw, phonetic, phonetic_f)
            content_h = expr_h + 5 + ph
        else:
            content_h = expr_h
        row_h_list.append(max(flag_size, content_h))
    lang_total = sum(row_h_list) + 28 * (len(row_h_list) - 1)
    total_h = kr_h + 18 + ctx_h + div_h + 16 + lang_total

    avail_top = 140   # 번호 배지 아래
    avail_bot = CARD_H - 50
    y = avail_top + max((avail_bot - avail_top - total_h) // 2, 0)

    # ── 한국어 문구 ────────────────────────────────────────────────────
    kb  = draw.textbbox((0, 0), kr_txt, font=kr_f)
    kw  = kb[2]-kb[0]
    draw.text((cx - kw//2, y - kb[1]), kr_txt, font=kr_f, fill=_COLL_WHITE)
    y += kr_h + 18

    # ── 상황 힌트 ─────────────────────────────────────────────────────
    if ctx_txt:
        ctb = draw.textbbox((0, 0), ctx_txt, font=ctx_f)
        ctw = ctb[2]-ctb[0]
        draw.text((cx - ctw//2, y - ctb[1]), ctx_txt, font=ctx_f, fill=_COLL_DIM)
        y += _th(draw, ctx_txt, ctx_f) + 12

    # ── 구분선 ───────────────────────────────────────────────────────
    draw.line([(PAD, y+10), (CARD_W-PAD, y+10)], fill=_COLL_DIV, width=1)
    y += div_h

    # ── 언어별 표현 (3행) ────────────────────────────────────────────
    for idx, (lang_code, expr, flag_emoji, expr_f, phonetic) in enumerate(_LANG_EXPRS):
        row_h = row_h_list[idx]

        # 국기 PNG
        fp = F.flag_path(flag_emoji)
        if fp:
            fy = y + (row_h - flag_size) // 2
            flag_img = Image.open(fp).convert("RGBA").resize(
                (flag_size, flag_size), Image.LANCZOS)
            img.paste(flag_img, (PAD, fy), flag_img)
            draw = ImageDraw.Draw(img)

        # 표현 텍스트 + 발음 (세로 중앙 배치)
        ex_x     = PAD + flag_size + 16
        ex_max_w = CARD_W - ex_x - PAD
        disp = expr
        while _tw(draw, disp, expr_f) > ex_max_w and len(disp) > 4:
            disp = disp[:-1]
        if disp != expr:
            disp = disp.rstrip(".,!？！…") + "…"
        eb = draw.textbbox((0, 0), disp, font=expr_f)
        eh = eb[3]-eb[1]

        # phonetic 포함 전체 콘텐츠 높이로 수직 중앙 결정
        if phonetic:
            ph = _th(draw, phonetic, phonetic_f)
            content_h = eh + 5 + ph
        else:
            content_h = eh
        start_y = y + (row_h - content_h) // 2

        ty = start_y - eb[1]
        draw.text((ex_x, ty), disp, font=expr_f, fill=_COLL_WHITE)

        # 발음 텍스트 (표현 바로 아래, 흐리게)
        if phonetic:
            py = start_y + eh + 5
            draw.text((ex_x, py), phonetic, font=phonetic_f,
                      fill=(*_COLL_DIM[:3], 200))

        y += row_h + 28

    img = _coll_watermark(img)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, f"collection_slide_{index:02d}_{date_str}.png")
    img.convert("RGB").save(out_path, "PNG", optimize=True)
    print(f"  ✓ 컬렉션 슬라이드 저장: {out_path}")
    return out_path


def render_collection_cta(date_str: str) -> str:
    """
    컬렉션 캐러셀 CTA 슬라이드 (10/10).
    Returns: output/collection_cta_{date_str}.png
    """
    F.ensure_fonts()
    img, draw = _coll_base_img()
    cx = CARD_W // 2

    # 상단 바
    bar = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(bar).rectangle([0, 0, CARD_W, 8], fill=(*_COLL_AMBER[:3], 255))
    img  = Image.alpha_composite(img, bar)
    draw = ImageDraw.Draw(img)

    # 저장 아이콘 텍스트
    icon_f   = F.noto_kr(100)
    icon_txt = "💾"
    try:
        for _p in ["/System/Library/Fonts/Apple Color Emoji.ttc",
                   "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"]:
            if os.path.exists(_p):
                ef = ImageFont.truetype(_p, 120)
                el = Image.new("RGBA", img.size, (0, 0, 0, 0))
                eb = ImageDraw.Draw(el).textbbox((0, 0), icon_txt, font=ef)
                ew = eb[2]-eb[0]
                ImageDraw.Draw(el).text((cx - ew//2, 200 - eb[1]), icon_txt,
                                        font=ef, embedded_color=True)
                img = Image.alpha_composite(img, el)
                draw = ImageDraw.Draw(img)
                break
    except Exception:
        pass

    # 메인 CTA 텍스트
    m1_f   = F.noto_kr(62)
    m1_txt = "저장해두고 써봐요!"
    m1b    = draw.textbbox((0, 0), m1_txt, font=m1_f)
    m1w    = m1b[2]-m1b[0]
    draw.text((cx - m1w//2, 390 - m1b[1]), m1_txt, font=m1_f, fill=_COLL_GOLD)

    m2_f   = F.noto_kr(38)
    m2_txt = "매일 새로운 표현이 올라와요"
    m2b    = draw.textbbox((0, 0), m2_txt, font=m2_f)
    m2w    = m2b[2]-m2b[0]
    draw.text((cx - m2w//2, 478 - m2b[1]), m2_txt, font=m2_f, fill=_COLL_DIM)

    # 구분선
    draw.line([(PAD*2, 560), (CARD_W-PAD*2, 560)], fill=_COLL_DIV, width=1)

    # 팔로우 텍스트
    f1_f   = F.noto_kr(46)
    f1_txt = "팔로우하면 매일 받아볼 수 있어요"
    f1b    = draw.textbbox((0, 0), f1_txt, font=f1_f)
    f1w    = f1b[2]-f1b[0]
    # 너무 길면 줄바꿈
    if f1w > USABLE_W:
        f1_f = F.noto_kr(38)
        f1b  = draw.textbbox((0, 0), f1_txt, font=f1_f)
        f1w  = f1b[2]-f1b[0]
    draw.text((cx - f1w//2, 598 - f1b[1]), f1_txt, font=f1_f, fill=_COLL_WHITE)

    # 계정 배지
    acc_f   = F.outfit(46)
    acc_txt = "@langcard.studio"
    ab      = draw.textbbox((0, 0), acc_txt, font=acc_f)
    aw      = ab[2]-ab[0]; ah = ab[3]-ab[1]
    ax0 = cx - aw//2 - 28; ax1 = cx + aw//2 + 28
    ay0 = 690;              ay1 = ay0 + ah + 28
    acc_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(acc_layer).rounded_rectangle([ax0, ay0, ax1, ay1], radius=20,
                                                fill=(*_COLL_GOLD[:3], 220))
    img  = Image.alpha_composite(img, acc_layer)
    draw = ImageDraw.Draw(img)
    draw.text((ax0 + 28, ay0 + 14 - ab[1]), acc_txt,
              font=acc_f, fill=(20, 20, 50, 255))

    # 3개국어 힌트
    hint_f   = F.noto_kr(30)
    hint_txt = "🇺🇸 영어  🇨🇳 중국어  🇯🇵 일본어"
    # 이모지 대신 텍스트로 처리 (이모지 렌더 이슈 방지)
    hint_txt2 = "영어 · 중국어 · 일본어"
    hb = draw.textbbox((0, 0), hint_txt2, font=hint_f)
    hw = hb[2]-hb[0]
    draw.text((cx - hw//2, 790 - hb[1]), hint_txt2, font=hint_f, fill=_COLL_FAINT)

    img = _coll_watermark(img)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, f"collection_cta_{date_str}.png")
    img.convert("RGB").save(out_path, "PNG", optimize=True)
    print(f"  ✓ 컬렉션 CTA 저장: {out_path}")
    return out_path
