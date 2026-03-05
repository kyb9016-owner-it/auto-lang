"""Pillow 카드 렌더러 — HTML 디자인 기반"""
from __future__ import annotations
import os
from typing import Optional
from datetime import date
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
        # 국기 PNG — 수직 중앙정렬
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


# ── 메인 렌더 ────────────────────────────────────────────────────────────────

# 레이아웃 구역 상수
_EXPR_ZONE_TOP    = 160   # 표현 구역 시작 y
_EXPR_ZONE_BOTTOM = 690   # 표현 구역 끝 y  (상단 64%)
_VOCAB_ZONE_TOP   = 720   # 단어 구역 시작 y
_VOCAB_ZONE_BOT   = 1040  # 단어 구역 끝 y


def render(data: dict, lang: str, slot: str, save: bool = True) -> str:
    F.ensure_fonts()

    theme  = CARD_THEMES[(lang, slot)]
    lc     = LANG_CONFIG[lang]
    sc     = SLOT_CONFIG[slot]
    is_cjk = lang in ("zh", "ja")
    cx     = CARD_W // 2

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

    # ── 상단 배지 ─────────────────────────────────────────────────────
    # 언어 배지: 각 언어 자국어 표기 (ENG / 中文 / 日本語)
    # 중일어는 NotoSans, 영어는 Poppins
    lang_badge_font = F.noto_kr(30) if lang in ("zh", "ja") else F.outfit(30)
    img, draw, _ = _alpha_badge_emoji(
        img, PAD, BADGE_Y, radius=26,
        bg=theme["lang_badge_bg"], emoji=lc["flag"], text=lc["name_native"],
        emoji_size=32, text_font=lang_badge_font, fg=theme["lang_badge_fg"])

    # 토픽 배지: 영어 단어 (GREETINGS / CAFE / TRAVEL)
    slot_text = sc['topic_badge']
    topic_font = F.outfit(28)
    tmp_tb = ImageDraw.Draw(img).textbbox((0,0), slot_text, font=topic_font)
    slot_w = BADGE_PAD_X + 32 + 8 + (tmp_tb[2]-tmp_tb[0]) + BADGE_PAD_X
    sx = CARD_W - PAD - slot_w
    img, draw, _ = _alpha_badge_emoji(
        img, sx, BADGE_Y, radius=26,
        bg=theme["topic_badge_bg"], emoji=sc["emoji"], text=slot_text,
        emoji_size=32, text_font=topic_font, fg=theme["topic_badge_fg"])

    # ── 메인 폰트 결정 ────────────────────────────────────────────────
    font_fn   = _main_font_fn(lang)
    main_font, _ = _fit_font(draw, data["main_expression"],
                              font_fn, USABLE_W, start=96, stop=44)

    # ── 표현 구역 높이 측정 → 중앙 배치 ──────────────────────────────
    label_font = F.noto_kr(28)
    pron_font  = F.noto_kr(36)
    ko_font    = F.noto_kr(52)
    bonus_font = font_fn(40)
    bko_font   = F.noto_kr(34)

    def _expr_height() -> int:
        h  = _th(draw, "오늘의 표현", label_font) + 12
        main_lines = _wrap(draw, data["main_expression"], main_font, USABLE_W, is_cjk)
        for ln in main_lines: h += _th(draw, ln, main_font) + 12
        h += 8
        if lc["has_pronunciation"] and data.get("pronunciation"):
            h += _th(draw, data["pronunciation"], pron_font) + 10
        bb = draw.textbbox((0,0), data["korean_translation"], font=ko_font)
        h += (bb[3]-bb[1]) + 14*2 + 14   # pill
        h += 32   # 구분선
        bonus_lines = _wrap(draw, data.get("bonus_expression",""), bonus_font, USABLE_W, is_cjk)
        for ln in bonus_lines: h += _th(draw, ln, bonus_font) + 8
        if lc["has_pronunciation"] and data.get("bonus_pronunciation"):
            h += _th(draw, data["bonus_pronunciation"], F.noto_kr(30)) + 6
        bko = data.get("bonus_korean","")
        if bko: h += _th(draw, bko, bko_font)
        return h

    expr_h = _expr_height()
    zone_h = _EXPR_ZONE_BOTTOM - _EXPR_ZONE_TOP
    y = _EXPR_ZONE_TOP + max((zone_h - expr_h) // 2, 0)

    # ── "오늘의 표현" 레이블 (중앙 정렬) ─────────────────────────────
    label_text = "오늘의 표현"
    llw = _tw(draw, label_text, label_font)
    draw.text(((CARD_W - llw) // 2, y), label_text, font=label_font, fill=sub_fill)
    y += _th(draw, label_text, label_font) + 12

    # ── 메인 표현 (중앙 정렬) ─────────────────────────────────────────
    main_lines = _wrap(draw, data["main_expression"], main_font, USABLE_W, is_cjk)
    for line in main_lines:
        lw = _tw(draw, line, main_font)
        draw.text(((CARD_W - lw) // 2, y), line, font=main_font, fill=main_fill)
        y += _th(draw, line, main_font) + 12
    y += 8

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
    # bb[1] 오프셋 보정으로 pill 안에 수직 중앙정렬
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
        bp_font = F.noto_kr(30)
        bp = data["bonus_pronunciation"]
        bpw = _tw(draw, bp, bp_font)
        draw.text(((CARD_W-bpw)//2, y), bp, font=bp_font, fill=sub_fill)
        y += _th(draw, bp, bp_font) + 6

    bko = data.get("bonus_korean","")
    if bko:
        bkow = _tw(draw, bko, bko_font)
        draw.text(((CARD_W-bkow)//2, y), bko, font=bko_font, fill=sub_fill)

    # ── 단어 구역 ─────────────────────────────────────────────────────
    vocab = data.get("vocab", [])
    if vocab:
        vy = _VOCAB_ZONE_TOP
        # 구분선
        draw.line([(PAD, vy), (CARD_W-PAD, vy)], fill=div_color, width=1)
        vy += 20

        # "오늘의 단어" 레이블 (중앙 정렬)
        vl_font = F.noto_kr(26)
        vl_text = "오늘의 단어"
        vlw = _tw(draw, vl_text, vl_font)
        draw.text(((CARD_W - vlw) // 2, vy), vl_text, font=vl_font, fill=sub_fill)
        vy += _th(draw, vl_text, vl_font) + 14

        # 단어 3개: [단어]  뜻
        word_font   = font_fn(34)
        mean_font   = F.noto_kr(30)
        pron_v_font = F.noto_kr(26)
        row_gap = 14

        for item in vocab[:3]:
            word = item.get("word", "")
            mean = item.get("meaning", "")
            pron = item.get("pronunciation") or ""

            ww = _tw(draw, word, word_font)
            mw = _tw(draw, mean, mean_font)
            sep = "  "
            sw = _tw(draw, sep, word_font)
            total = ww + sw + mw
            tx = (CARD_W - total) // 2

            draw.text((tx, vy), word, font=word_font, fill=main_fill)
            draw.text((tx + ww + sw, vy), mean, font=mean_font, fill=sub_fill)

            row_h = max(_th(draw, word, word_font), _th(draw, mean, mean_font))
            if pron and lc["has_pronunciation"]:
                vy += row_h + 2
                pw2 = _tw(draw, pron, pron_v_font)
                draw.text(((CARD_W-pw2)//2, vy), pron,
                          font=pron_v_font, fill=sub_fill)
                vy += _th(draw, pron, pron_v_font) + row_gap
            else:
                vy += row_h + row_gap

    # ── 워터마크 ─────────────────────────────────────────────────────
    wm_font = F.noto_kr(22)
    wm = "@langcard.studio"
    wmw = _tw(draw, wm, wm_font)
    draw.text(((CARD_W-wmw)//2, CARD_H - 38), wm,
              font=wm_font, fill=(*ts[:3], ts[3]//2 if len(ts)>3 else 90))

    # ── 저장 ─────────────────────────────────────────────────────────
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    today = date.today().strftime("%Y%m%d")
    out_path = os.path.join(OUTPUT_DIR, f"{slot}_{lang}_{today}.png")
    if save:
        img.convert("RGB").save(out_path, "PNG", optimize=True)
        print(f"  ✓ 카드 저장: {out_path}")
    return out_path
