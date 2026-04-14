"""Apple 라이트 스타일 대화 카드 렌더러"""
from __future__ import annotations
import os
from PIL import Image, ImageDraw
from renderer import fonts as F
from renderer.themes import CARD_W, CARD_H, PAD

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")

# Notion 색상
BG         = (255, 255, 255)   # Pure white
TEXT_MAIN  = (0, 0, 0)         # Near-black
TEXT_SUB   = (97, 93, 89)      # Warm gray 500
APPLE_BLUE = (0, 117, 222)     # Notion Blue

USABLE_W = CARD_W - PAD * 2

# 턴 수에 따른 동적 폰트 크기
_FONT_SIZES = {
    2: {"line": 46, "phonetic": 30, "korean": 32, "speaker": 36},
    3: {"line": 38, "phonetic": 26, "korean": 28, "speaker": 32},
    4: {"line": 32, "phonetic": 22, "korean": 24, "speaker": 28},
}

# 파란 하이라이트 바 너비
BLUE_BAR_W = 5
# 하이라이트 턴 들여쓰기 (바 포함)
SPEAKER_LABEL_W = 60


def _tw(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]


def _th(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[3] - bb[1]


def _line_font(lang: str, size: int):
    """언어에 맞는 라인 폰트 반환"""
    if lang == "ja":
        return F.noto_jp(size)
    if lang == "zh":
        return F.noto_sc(size)
    return F.outfit(size)


def _is_highlighted(turn: dict, right_text: str, idx: int, total: int) -> bool:
    """하이라이트 대상 턴인지 판별"""
    if right_text and right_text.lower() in turn.get("line", "").lower():
        return True
    # 마지막 턴은 항상 하이라이트 (fallback)
    if idx == total - 1:
        return True
    return False


def render_dialogue_card(dialogue: list[dict], lang: str, date_str: str,
                         slot: str, right_text: str = "") -> str:
    """
    대화 카드 1장 렌더링 (Apple 라이트 스타일).
    dialogue: [{"speaker": "A/B", "line": "...", "pronunciation": "...",
                "korean_phonetic": "...", "korean": "..."}]
    Returns: output/dialogue_{lang}_{slot}_{date_str}.png
    """
    F.ensure_fonts()

    img  = Image.new("RGB", (CARD_W, CARD_H), BG)
    draw = ImageDraw.Draw(img)

    n_turns = max(2, min(4, len(dialogue)))
    sizes   = _FONT_SIZES.get(n_turns, _FONT_SIZES[4])

    # ── 상단 레이블: "실전 대화" ──────────────────────────────────
    label_font = F.noto_kr(28)
    draw.text((PAD, 100), "실전 대화", font=label_font, fill=TEXT_SUB)

    # ── Apple Blue 구분선 ─────────────────────────────────────────
    label_bb   = draw.textbbox((PAD, 100), "실전 대화", font=label_font)
    sep_y      = label_bb[3] + 24
    draw.rectangle([PAD, sep_y, CARD_W - PAD, sep_y + 2], fill=APPLE_BLUE)

    # ── 대화 턴 렌더링 ────────────────────────────────────────────
    total      = len(dialogue)
    line_gap   = 10   # 같은 턴 내 텍스트 간격
    turn_gap   = 36   # 턴 사이 간격

    speaker_font = F.noto_kr(sizes["speaker"])
    line_size    = sizes["line"]
    pron_size    = sizes["phonetic"]
    ko_size      = sizes["korean"]

    # ── 1-pass: 전체 높이 계산 (수직 중앙 정렬) ─────────────────
    total_h = 0
    for idx, turn in enumerate(dialogue):
        line     = turn.get("line", "")
        phonetic = turn.get("pronunciation") or turn.get("korean_phonetic") or ""
        korean   = turn.get("korean", "")
        lf = _line_font(lang, line_size)
        total_h += _th(draw, line, lf) + line_gap
        if phonetic:
            total_h += _th(draw, phonetic, F.noto_kr(pron_size)) + line_gap
        if korean:
            total_h += _th(draw, korean, F.noto_kr(ko_size))
        if idx < total - 1:
            total_h += turn_gap

    content_top = sep_y + 48
    content_bot = CARD_H - 80  # 워터마크 위
    avail = content_bot - content_top
    turn_y = content_top + max(0, (avail - total_h) // 3)

    # ── 2-pass: 실제 렌더링 ─────────────────────────────────────
    for idx, turn in enumerate(dialogue):
        speaker    = turn.get("speaker", "")
        line       = turn.get("line", "")
        phonetic   = turn.get("pronunciation") or turn.get("korean_phonetic") or ""
        korean     = turn.get("korean", "")
        highlighted = _is_highlighted(turn, right_text, idx, total)

        speaker_color = APPLE_BLUE if highlighted else TEXT_SUB

        # 왼쪽 파란 바 (하이라이트 턴만)
        if highlighted:
            # 턴 높이를 미리 추산해 바 높이 결정 — 나중에 실제 높이로 그림
            bar_start_y = turn_y

        # 스피커 레이블 위치
        speaker_x = PAD + (BLUE_BAR_W + 12 if highlighted else 0)
        draw.text((speaker_x, turn_y), speaker,
                  font=speaker_font, fill=speaker_color)

        # 콘텐츠 x 시작 (스피커 레이블 오른쪽)
        content_x = speaker_x + SPEAKER_LABEL_W

        content_y = turn_y

        # 타깃 언어 라인
        lf = _line_font(lang, line_size)
        # 너무 길면 줄여서 표시
        max_content_w = USABLE_W - SPEAKER_LABEL_W - (BLUE_BAR_W + 12 if highlighted else 0)
        while _tw(draw, line, lf) > max_content_w and lf.size > 20:
            lf = _line_font(lang, lf.size - 2)

        draw.text((content_x, content_y), line,
                  font=lf, fill=TEXT_MAIN)
        bb = draw.textbbox((content_x, content_y), line, font=lf)
        content_y = bb[3] + line_gap

        # 한글 발음
        if phonetic:
            pf = F.noto_kr(pron_size)
            draw.text((content_x, content_y), phonetic,
                      font=pf, fill=TEXT_SUB)
            bb = draw.textbbox((content_x, content_y), phonetic, font=pf)
            content_y = bb[3] + line_gap

        # 한국어 번역
        if korean:
            kf = F.noto_kr(ko_size)
            while _tw(draw, korean, kf) > max_content_w and kf.size > 18:
                kf = F.noto_kr(kf.size - 2)
            draw.text((content_x, content_y), korean,
                      font=kf, fill=TEXT_SUB)
            bb = draw.textbbox((content_x, content_y), korean, font=kf)
            content_y = bb[3]

        # 하이라이트 파란 바 (실제 턴 높이로 그리기)
        if highlighted:
            bar_end_y = content_y + 4
            draw.rectangle(
                [PAD, bar_start_y, PAD + BLUE_BAR_W, bar_end_y],
                fill=APPLE_BLUE
            )

        turn_y = content_y + turn_gap

    # ── 하단 워터마크 ─────────────────────────────────────────────
    brand_font = F.outfit(28)
    brand      = "@langcard.studio"
    bw         = _tw(draw, brand, brand_font)
    draw.text(((CARD_W - bw) // 2, CARD_H - 60), brand,
              font=brand_font, fill=TEXT_SUB)

    # ── 저장 ─────────────────────────────────────────────────────
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR,
                            f"dialogue_{lang}_{slot}_{date_str}.png")
    img.save(out_path, "PNG", optimize=True)
    print(f"  ✓ 대화 카드 저장: {out_path}")
    return out_path
