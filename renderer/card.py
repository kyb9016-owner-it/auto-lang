"""Pillow 카드 렌더러 — HTML 디자인 기반"""
from __future__ import annotations
import os
from typing import Optional
from datetime import date, datetime
from PIL import Image, ImageDraw, ImageFont

from config import LANG_CONFIG, SLOT_CONFIG
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
    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    if c3 is None:
        for y in range(h):
            r = c1[0] + (c2[0]-c1[0])*y//h
            g = c1[1] + (c2[1]-c1[1])*y//h
            b = c1[2] + (c2[2]-c1[2])*y//h
            draw.line([(0,y),(w,y)], fill=(r,g,b))
    else:
        half = h//2
        for y in range(half):
            r = c1[0]+(c2[0]-c1[0])*y//half
            g = c1[1]+(c2[1]-c1[1])*y//half
            b = c1[2]+(c2[2]-c1[2])*y//half
            draw.line([(0,y),(w,y)], fill=(r,g,b))
        for y in range(h-half):
            r = c2[0]+(c3[0]-c2[0])*y//(h-half)
            g = c2[1]+(c3[1]-c2[1])*y//(h-half)
            b = c2[2]+(c3[2]-c2[2])*y//(h-half)
            draw.line([(0,half+y),(w,half+y)], fill=(r,g,b))
    return img


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


def render(data: dict, lang: str, topic, save: bool = True) -> str:
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

    # ── 폰트 선언 ────────────────────────────────────────────────────
    font_fn       = _main_font_fn(lang)
    main_font, _  = _fit_font(draw, data["main_expression"],
                               font_fn, USABLE_W, start=88, stop=40)
    label_font    = F.noto_kr(28)
    phonetic_font = F.noto_kr(26)
    pron_font     = F.noto_kr(34)
    ko_font       = F.noto_kr(50)
    bonus_font    = font_fn(38)
    bko_font      = F.noto_kr(32)

    phonetic_text = data.get("korean_phonetic", "")

    def _expr_height() -> int:
        h  = _th(draw, "오늘의 표현", label_font) + 12
        main_lines = _wrap(draw, data["main_expression"], main_font, USABLE_W, is_cjk)
        for ln in main_lines: h += _th(draw, ln, main_font) + 12
        h += 8
        # 한글 음차
        if phonetic_text:
            h += _th(draw, phonetic_text, phonetic_font) + 10
        if lc["has_pronunciation"] and data.get("pronunciation"):
            h += _th(draw, data["pronunciation"], pron_font) + 10
        bb = draw.textbbox((0,0), data["korean_translation"], font=ko_font)
        h += (bb[3]-bb[1]) + 14*2 + 14   # pill
        h += 32   # 구분선
        bonus_lines = _wrap(draw, data.get("bonus_expression",""), bonus_font, USABLE_W, is_cjk)
        for ln in bonus_lines: h += _th(draw, ln, bonus_font) + 8
        if lc["has_pronunciation"] and data.get("bonus_pronunciation"):
            h += _th(draw, data["bonus_pronunciation"], F.noto_kr(28)) + 6
        bko = data.get("bonus_korean","")
        if bko: h += _th(draw, bko, bko_font)
        return h

    # 표현 콘텐츠만 카드 세로 중앙 배치
    expr_h    = _expr_height()
    avail_top = BADGE_Y + BADGE_H   # y=112
    avail_bot = CARD_H - 50         # y=1030
    avail_h   = avail_bot - avail_top
    y = avail_top + max((avail_h - expr_h) // 2, 0)

    # ── "오늘의 표현" 레이블 ──────────────────────────────────────────
    lbl_bb = draw.textbbox((0, 0), "오늘의 표현", font=label_font)
    draw.text(((CARD_W - (lbl_bb[2]-lbl_bb[0])) // 2, y - lbl_bb[1]),
              "오늘의 표현", font=label_font, fill=sub_fill)
    y += _th(draw, "오늘의 표현", label_font) + 12

    # ── 메인 표현 (중앙 정렬) ─────────────────────────────────────────
    main_lines = _wrap(draw, data["main_expression"], main_font, USABLE_W, is_cjk)
    for line in main_lines:
        lw = _tw(draw, line, main_font)
        draw.text(((CARD_W - lw) // 2, y), line, font=main_font, fill=main_fill)
        y += _th(draw, line, main_font) + 12
    y += 8

    # ── 한글 음차 발음 (중앙) ─────────────────────────────────────────
    if phonetic_text:
        pt_display = f"🔊 {phonetic_text}"
        # 🔊 이모지 없이 텍스트만 (이모지 렌더 복잡)
        pt_display = phonetic_text
        pw = _tw(draw, pt_display, phonetic_font)
        draw.text(((CARD_W - pw) // 2, y), pt_display,
                  font=phonetic_font, fill=phonetic_fill)
        y += _th(draw, pt_display, phonetic_font) + 10

    # ── 발음 (중/일, 중앙) ───────────────────────────────────────────
    if lc["has_pronunciation"] and data.get("pronunciation"):
        pt = data["pronunciation"]
        pw = _tw(draw, pt, pron_font)
        draw.text(((CARD_W - pw) // 2, y), pt, font=pron_font, fill=sub_fill)
        y += _th(draw, pt, pron_font) + 10

    # ── 한국어 번역 pill (중앙) ───────────────────────────────────────
    ko_text = data["korean_translation"]
    bb = draw.textbbox((0, 0), ko_text, font=ko_font)
    ktw = bb[2] - bb[0]; kth = bb[3] - bb[1]
    kpx, kpy = 28, 14
    kx0 = cx - ktw//2 - kpx; kx1 = cx + ktw//2 + kpx
    ky1 = y + kth + kpy * 2
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle([kx0, y, kx1, ky1], radius=14,
                                             fill=theme["kr_badge_bg"])
    img = Image.alpha_composite(img, layer)
    draw = ImageDraw.Draw(img)
    draw.text((cx - ktw//2, y + kpy - bb[1]), ko_text, font=ko_font, fill=main_fill)
    y = ky1 + 14

    # ── 구분선 ───────────────────────────────────────────────────────
    div_color = (*ts[:3], ts[3]//2 if len(ts)>3 else 60)
    draw.line([(PAD, y), (CARD_W-PAD, y)], fill=div_color, width=1)
    y += 18

    # ── 보너스 표현 (중앙) ───────────────────────────────────────────
    bonus_lines = _wrap(draw, data.get("bonus_expression",""), bonus_font, USABLE_W, is_cjk)
    for line in bonus_lines:
        lw = _tw(draw, line, bonus_font)
        draw.text(((CARD_W-lw)//2, y), line, font=bonus_font, fill=main_fill)
        y += _th(draw, line, bonus_font) + 8

    if lc["has_pronunciation"] and data.get("bonus_pronunciation"):
        bp_font = F.noto_kr(28)
        bp = data["bonus_pronunciation"]
        bpw = _tw(draw, bp, bp_font)
        draw.text(((CARD_W-bpw)//2, y), bp, font=bp_font, fill=sub_fill)
        y += _th(draw, bp, bp_font) + 6

    bko = data.get("bonus_korean","")
    if bko:
        bkow = _tw(draw, bko, bko_font)
        draw.text(((CARD_W-bkow)//2, y), bko, font=bko_font, fill=sub_fill)

    # ── 워터마크 ─────────────────────────────────────────────────────
    wm_font = F.noto_kr(22)
    wm = "@langcard.studio"
    wmw = _tw(draw, wm, wm_font)
    draw.text(((CARD_W-wmw)//2, CARD_H - 38), wm,
              font=wm_font, fill=(*ts[:3], ts[3]//2 if len(ts)>3 else 90))

    # ── 저장 ─────────────────────────────────────────────────────────
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    today = date.today().strftime("%Y%m%d")
    out_path = os.path.join(OUTPUT_DIR, f"expr_{lang}_{today}.png")
    if save:
        img.convert("RGB").save(out_path, "PNG", optimize=True)
        print(f"  ✓ 카드 저장: {out_path}")
    return out_path


# ── 단어 전용 카드 렌더러 ─────────────────────────────────────────────────────

def render_vocab(data: dict, lang: str, topic, save: bool = True) -> str:
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

    # ── 높이 측정 → 세로 중앙 ────────────────────────────────────────
    def _vocab_block_h() -> int:
        h = _th(draw, "오늘의 단어", lbl_font) + 28
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
    avail_top = BADGE_Y + BADGE_H
    avail_bot = CARD_H - 50
    vy = avail_top + max((avail_bot - avail_top - block_h) // 2, 0)

    # ── "오늘의 단어" 레이블 (중앙) ─────────────────────────────────
    lbl_bb = draw.textbbox((0,0), "오늘의 단어", font=lbl_font)
    draw.text(((CARD_W - (lbl_bb[2]-lbl_bb[0])) // 2, vy - lbl_bb[1]),
              "오늘의 단어", font=lbl_font, fill=sub_fill)
    vy += _th(draw, "오늘의 단어", lbl_font) + 28

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
    today    = date.today().strftime("%Y%m%d")
    out_path = os.path.join(OUTPUT_DIR, f"vocab_{lang}_{today}.png")
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
    save_text = "❤️ 좋아요   📌 저장"
    sb = draw.textbbox((0, 0), save_text, font=save_font)
    sw = sb[2] - sb[0]
    draw.text(((CARD_W - sw) // 2, CARD_H // 3 - sb[1]),
              save_text, font=save_font, fill=WHITE)

    # ── 팔로우 CTA (중앙) ────────────────────────────────────────────────
    follow_font  = F.noto_kr(58)
    follow_line1 = "💙 팔로우하면"
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
