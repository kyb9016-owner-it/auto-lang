"""Apple 제품 페이지 스타일 단어 카드 렌더러"""
from __future__ import annotations
import os
from PIL import Image, ImageDraw
from renderer import fonts as F
from renderer.themes import CARD_W, CARD_H, PAD

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")

# Notion 색상
BG         = (255, 255, 255)      # Pure white
TEXT_MAIN  = (0, 0, 0)            # Near-black
TEXT_SUB   = (97, 93, 89)         # Warm gray 500
APPLE_BLUE = (0, 117, 222)        # Notion Blue
BLUE_LIGHT = (242, 249, 255, 255) # Badge bg

USABLE_W = CARD_W - PAD * 2


def _word_font(lang, size):
    if lang == "ja": return F.noto_jp(size)
    if lang == "zh": return F.noto_sc(size)
    return F.outfit(size)


def _tw(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]


def _th(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[3] - bb[1]


def render_vocab_card(vocab_item: dict, idx: int, total: int,
                      lang: str, date_str: str, slot: str) -> str:
    """
    단어 카드 1장 렌더링 (Apple 제품 페이지 스타일).
    vocab_item: {word, type, meaning, phonetic}
    idx: 0-based index
    Returns: output/vocab_{lang}_{slot}_{date_str}_{idx+1}.png
    """
    F.ensure_fonts()

    img  = Image.new("RGB", (CARD_W, CARD_H), BG)
    draw = ImageDraw.Draw(img)

    word     = vocab_item.get("word", "")
    wtype    = vocab_item.get("type", "")
    meaning  = vocab_item.get("meaning", "")
    phonetic = vocab_item.get("phonetic") or ""

    # ── 상단 레이블: "오늘의 단어 1/3" ──────────────────────────
    label_font = F.noto_kr(26)
    label_text = f"오늘의 단어  {idx + 1}/{total}"
    draw.text((PAD, 100), label_text, font=label_font, fill=TEXT_SUB)

    # ── 품사 배지 (Apple Blue 알약형) ────────────────────────────
    badge_font = F.noto_kr(28)
    badge_pad_x, badge_pad_y = 20, 10
    badge_w = _tw(draw, wtype, badge_font) + badge_pad_x * 2
    badge_h = _th(draw, wtype, badge_font) + badge_pad_y * 2
    badge_y = 180

    # 배지 배경 (연한 파랑)
    badge_layer = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    badge_draw  = ImageDraw.Draw(badge_layer)
    badge_draw.rounded_rectangle(
        [PAD, badge_y, PAD + badge_w, badge_y + badge_h],
        radius=badge_h // 2,
        fill=(*APPLE_BLUE, 20)
    )
    img = img.convert("RGBA")
    img = Image.alpha_composite(img, badge_layer)
    img = img.convert("RGB")
    draw = ImageDraw.Draw(img)

    # 배지 텍스트
    draw.text((PAD + badge_pad_x, badge_y + badge_pad_y), wtype,
              font=badge_font, fill=APPLE_BLUE)

    # ── 단어 — 크고 진하게 ───────────────────────────────────────
    word_font = _word_font(lang, 100)
    # 너무 길면 축소
    while _tw(draw, word, word_font) > USABLE_W and word_font.size > 48:
        word_font = _word_font(lang, word_font.size - 4)

    word_y = badge_y + badge_h + 40
    draw.text((PAD, word_y), word, font=word_font, fill=TEXT_MAIN)
    bb = draw.textbbox((PAD, word_y), word, font=word_font)
    word_bottom = bb[3]

    # ── 한글 발음 ────────────────────────────────────────────────
    pron_y = word_bottom + 16
    if phonetic:
        pron_font = F.noto_kr(34)
        draw.text((PAD, pron_y), phonetic, font=pron_font, fill=TEXT_SUB)
        bb = draw.textbbox((PAD, pron_y), phonetic, font=pron_font)
        pron_y = bb[3] + 24
    else:
        pron_y += 10

    # ── Apple Blue 구분선 ────────────────────────────────────────
    draw.rectangle([PAD, pron_y, CARD_W - PAD, pron_y + 2], fill=APPLE_BLUE)
    pron_y += 28

    # ── 한국어 뜻 — 크게 ─────────────────────────────────────────
    ko_font = F.noto_kr(64)
    while _tw(draw, meaning, ko_font) > USABLE_W and ko_font.size > 40:
        ko_font = F.noto_kr(ko_font.size - 4)

    draw.text((PAD, pron_y), meaning, font=ko_font, fill=TEXT_MAIN)

    # ── 하단 브랜드 ──────────────────────────────────────────────
    brand_font = F.outfit(28)
    brand = "@langcard.studio"
    bw = _tw(draw, brand, brand_font)
    draw.text(((CARD_W - bw) // 2, CARD_H - 50), brand,
              font=brand_font, fill=TEXT_SUB)

    # ── 저장 ─────────────────────────────────────────────────────
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, f"vocab_{lang}_{slot}_{date_str}_{idx + 1}.png")
    img.save(out_path, "PNG", optimize=True)
    print(f"  ✓ 단어 카드 {idx+1}/{total} 저장: {out_path}")
    return out_path


def render_vocab_cards(vocab_list: list, lang: str,
                       date_str: str, slot: str) -> list[str]:
    """vocab_list (최대 3개) → 카드 PNG 경로 리스트 반환"""
    items = vocab_list[:3]
    total = len(items)
    paths = []
    for i, item in enumerate(items):
        paths.append(render_vocab_card(item, i, total, lang, date_str, slot))
    return paths
