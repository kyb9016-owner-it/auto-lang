"""Pillow 카드 렌더러 — HTML 디자인 기반 리디자인"""
from __future__ import annotations
import os
from typing import Optional
from datetime import date
from PIL import Image, ImageDraw

from config import LANG_CONFIG, SLOT_CONFIG
from renderer.themes import CARD_THEMES, CARD_W, CARD_H, PAD, USABLE_W
from renderer import fonts as F

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")

# ── 상수 ────────────────────────────────────────────────────────────────────
BOTTOM_PAD   = 80    # 하단 여백
CONTENT_GAP  = 14   # 요소 간 간격
BADGE_Y      = 64   # 상단 배지 y
BADGE_H      = 46   # 배지 높이
BADGE_PAD_X  = 22   # 배지 좌우 내부 여백
BADGE_PAD_Y  = 10   # 배지 상하 내부 여백


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
    """20×20 도트 그리드 오버레이"""
    layer = Image.new("RGBA", img.size, (0,0,0,0))
    draw  = ImageDraw.Draw(layer)
    dot_color = (255,255,255,15) if text_main == (255,255,255) else (0,0,0,12)
    spacing = 32
    for x in range(0, CARD_W, spacing):
        for y in range(0, CARD_H, spacing):
            draw.ellipse([x-2, y-2, x+2, y+2], fill=dot_color)
    return Image.alpha_composite(img, layer)


def _emoji_bg(img: Image.Image, emoji: str) -> Image.Image:
    """큰 이모지를 우하단에 12% 투명도로 렌더링"""
    # 시스템 이모지 폰트 탐색
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
        return img  # 이모지 폰트 없으면 생략

    try:
        layer = Image.new("RGBA", img.size, (0,0,0,0))
        d = ImageDraw.Draw(layer)
        d.text((CARD_W - 60, CARD_H - 60), emoji,
               font=emoji_font, anchor="rb",
               embedded_color=True)
        # 12% 불투명도로 합성
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


def _alpha_pill(img: Image.Image, cx: int, y: int, text: str, font,
                bg: tuple, fg: tuple, pad_x: int = 28, pad_y: int = 10):
    """중앙정렬 pill 배지 — alpha_composite 방식. 다음 y 반환"""
    tmp_draw = ImageDraw.Draw(img)
    bb = tmp_draw.textbbox((0,0), text, font=font)
    tw = bb[2] - bb[0]
    th = bb[3] - bb[1]
    x0 = cx - tw//2 - pad_x
    x1 = cx + tw//2 + pad_x
    y1 = y + th + pad_y*2
    layer = Image.new("RGBA", img.size, (0,0,0,0))
    ImageDraw.Draw(layer).rounded_rectangle([x0,y,x1,y1], radius=(y1-y)//2, fill=bg)
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
              start: int = 82, stop: int = 34, step: int = 4):
    for size in range(start, stop-1, -step):
        f = font_fn(size)
        if _tw(draw, text, f) <= max_w:
            return f, size
    return font_fn(stop), stop


def _draw_lines_centered(draw: ImageDraw.Draw, lines: list[str], font,
                          y: int, fill: tuple, gap: int = 10) -> int:
    for line in lines:
        w = _tw(draw, line, font)
        draw.text(((CARD_W-w)//2, y), line, font=font, fill=fill)
        y += _th(draw, line, font) + gap
    return y


# ── 콘텐츠 높이 사전 측정 ────────────────────────────────────────────────────

def _measure_content(draw, data: dict, lang: str, lc: dict,
                     main_font, is_cjk: bool) -> int:
    h = 0
    label_font = F.noto_kr(24)
    pron_font  = F.noto_kr(34)
    ko_font    = F.noto_kr(44)
    bonus_font = F.lang_font(lang, 32)
    bko_font   = F.noto_kr(28)

    # 레이블
    h += _th(draw, "오늘의 표현", label_font) + CONTENT_GAP + 4
    # 메인 표현
    main_lines = _wrap(draw, data["main_expression"], main_font, USABLE_W, is_cjk)
    for line in main_lines:
        h += _th(draw, line, main_font) + 10
    h += CONTENT_GAP
    # 발음
    if lc["has_pronunciation"] and data.get("pronunciation"):
        h += _th(draw, f"[{data['pronunciation']}]", pron_font) + CONTENT_GAP
    # 한국어 pill
    bb = draw.textbbox((0,0), data["korean_translation"], font=ko_font)
    h += (bb[3]-bb[1]) + 20*2 + CONTENT_GAP  # pad_y*2
    # 구분선
    h += 28
    # 보너스 표현
    bonus_lines = _wrap(draw, data.get("bonus_expression",""), bonus_font, USABLE_W, is_cjk)
    for line in bonus_lines:
        h += _th(draw, line, bonus_font) + 8
    if lc["has_pronunciation"] and data.get("bonus_pronunciation"):
        h += _th(draw, f"[{data['bonus_pronunciation']}]", F.noto_kr(24)) + 8
    # 보너스 한국어
    h += _th(draw, f"→ {data.get('bonus_korean','')}", bko_font)
    return h


# ── 메인 렌더 ────────────────────────────────────────────────────────────────

def render(data: dict, lang: str, slot: str, save: bool = True) -> str:
    F.ensure_fonts()

    theme  = CARD_THEMES[(lang, slot)]
    lc     = LANG_CONFIG[lang]
    sc     = SLOT_CONFIG[slot]
    is_cjk = lang in ("zh", "ja")
    cx     = CARD_W // 2  # 수평 중심

    # ── 배경 ─────────────────────────────────────────────────────────
    g = theme["gradient"]
    bg = _gradient(CARD_W, CARD_H, g[0], g[1], g[2] if len(g)>2 else None)
    img = bg.convert("RGBA")

    # 도트 오버레이
    img = _dot_overlay(img, theme["text_main"])

    # 이모지 배경
    img = _emoji_bg(img, theme["emoji"])

    draw = ImageDraw.Draw(img)

    # ── 상단 배지 ─────────────────────────────────────────────────────
    badge_font = F.noto_kr(26)

    lang_text = lc["name_ko"]
    lw = _tw(draw, lang_text, badge_font) + BADGE_PAD_X*2
    img, draw = _alpha_badge(img,
        (PAD, BADGE_Y, PAD+lw, BADGE_Y+BADGE_H), radius=23,
        bg=theme["lang_badge_bg"], text=lang_text, font=badge_font,
        fg=theme["lang_badge_fg"])

    slot_text = sc["topic_ko"]
    sw = _tw(draw, slot_text, badge_font) + BADGE_PAD_X*2
    sx = CARD_W - PAD - sw
    img, draw = _alpha_badge(img,
        (sx, BADGE_Y, sx+sw, BADGE_Y+BADGE_H), radius=23,
        bg=theme["topic_badge_bg"], text=slot_text, font=badge_font,
        fg=theme["topic_badge_fg"])

    # ── 콘텐츠 시작 y (하단 앵커) ─────────────────────────────────────
    label_font = F.noto_kr(24)
    main_font, _ = _fit_font(draw, data["main_expression"],
                              lambda s: F.lang_font(lang, s),
                              USABLE_W, start=82, stop=34)

    content_h = _measure_content(draw, data, lang, lc, main_font, is_cjk)
    y = max(CARD_H - BOTTOM_PAD - content_h, 400)

    # ── "오늘의 표현" 레이블 ──────────────────────────────────────────
    label_text = "오늘의 표현"
    lw2 = _tw(draw, label_text, label_font)
    ts = theme["text_sub"]
    draw.text(((CARD_W-lw2)//2, y), label_text,
              font=label_font, fill=(*ts[:3], ts[3] if len(ts)>3 else 180))
    y += _th(draw, label_text, label_font) + CONTENT_GAP + 4

    # ── 메인 표현 ──────────────────────────────────────────────────────
    main_lines = _wrap(draw, data["main_expression"], main_font, USABLE_W, is_cjk)
    y = _draw_lines_centered(draw, main_lines, main_font, y,
                              fill=(*theme["text_main"], 255), gap=10)
    y += CONTENT_GAP

    # ── 발음 (중/일) ────────────────────────────────────────────────
    if lc["has_pronunciation"] and data.get("pronunciation"):
        pron_font = F.noto_kr(34)
        pron_text = f"[{data['pronunciation']}]"
        pw = _tw(draw, pron_text, pron_font)
        draw.text(((CARD_W-pw)//2, y), pron_text,
                  font=pron_font, fill=(*ts[:3], ts[3] if len(ts)>3 else 170))
        y += _th(draw, pron_text, pron_font) + CONTENT_GAP

    # ── 한국어 번역 pill ─────────────────────────────────────────────
    ko_font = F.noto_kr(44)
    img, draw, y = _alpha_pill(img, cx, y,
                                data["korean_translation"], ko_font,
                                bg=theme["kr_badge_bg"],
                                fg=theme["text_main"],
                                pad_x=28, pad_y=12)

    # ── 구분선 ───────────────────────────────────────────────────────
    div_color = (*ts[:3], ts[3] if len(ts)>3 else 80)
    draw.line([(PAD+60, y), (CARD_W-PAD-60, y)], fill=div_color, width=1)
    y += 28

    # ── 보너스 표현 ──────────────────────────────────────────────────
    bonus_font = F.lang_font(lang, 32)
    bonus_lines = _wrap(draw, data.get("bonus_expression",""), bonus_font, USABLE_W, is_cjk)
    y = _draw_lines_centered(draw, bonus_lines, bonus_font, y,
                              fill=(*theme["text_main"], 255), gap=8)

    if lc["has_pronunciation"] and data.get("bonus_pronunciation"):
        bp_font = F.noto_kr(24)
        bp = f"[{data['bonus_pronunciation']}]"
        bpw = _tw(draw, bp, bp_font)
        draw.text(((CARD_W-bpw)//2, y), bp,
                  font=bp_font, fill=(*ts[:3], ts[3] if len(ts)>3 else 160))
        y += _th(draw, bp, bp_font) + 8

    bko_font = F.noto_kr(28)
    bko = f"→ {data.get('bonus_korean','')}"
    bkw = _tw(draw, bko, bko_font)
    draw.text(((CARD_W-bkw)//2, y), bko,
              font=bko_font, fill=(*ts[:3], ts[3] if len(ts)>3 else 160))

    # ── 워터마크 ─────────────────────────────────────────────────────
    wm_font = F.noto_kr(20)
    wm = "@langcard.studio"
    wmw = _tw(draw, wm, wm_font)
    draw.text(((CARD_W-wmw)//2, CARD_H-44), wm,
              font=wm_font, fill=(*ts[:3], ts[3] if len(ts)>3 else 120))

    # ── 저장 ─────────────────────────────────────────────────────────
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    today = date.today().strftime("%Y%m%d")
    out_path = os.path.join(OUTPUT_DIR, f"{slot}_{lang}_{today}.png")
    if save:
        img.convert("RGB").save(out_path, "PNG", optimize=True)
        print(f"  ✓ 카드 저장: {out_path}")
    return out_path
