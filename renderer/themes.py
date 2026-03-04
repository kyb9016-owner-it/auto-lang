"""언어 × 슬롯별 카드 테마 (9가지)"""

# 각 테마 키: (lang, slot)
# gradient: list of 2~3 RGB tuples
# topic_badge_bg / fg: (R,G,B,A) / (R,G,B)
# lang_badge_bg / fg: same
# text_main: (R,G,B) — 메인 텍스트
# text_sub: (R,G,B,A) — 보조 텍스트
# kr_badge_bg: (R,G,B,A) — 한국어 번역 pill 배경
# emoji: str — 배경 대형 이모지

CARD_THEMES = {
    # ─── ENGLISH ────────────────────────────────────────────────────
    ("en", "morning"): dict(
        gradient=[(255, 60, 172), (120, 75, 160), (43, 134, 197)],
        topic_badge_bg=(255, 230, 0, 220),  topic_badge_fg=(26, 26, 26),
        lang_badge_bg=(255, 255, 255, 50),  lang_badge_fg=(255, 255, 255),
        text_main=(255, 255, 255),          text_sub=(255, 255, 255, 180),
        kr_badge_bg=(255, 255, 255, 50),
        emoji="😊",
    ),
    ("en", "lunch"): dict(
        gradient=[(249, 83, 198), (185, 29, 115)],
        topic_badge_bg=(255, 255, 255, 230), topic_badge_fg=(185, 29, 115),
        lang_badge_bg=(255, 255, 255, 50),  lang_badge_fg=(255, 255, 255),
        text_main=(255, 255, 255),          text_sub=(255, 255, 255, 180),
        kr_badge_bg=(255, 255, 255, 50),
        emoji="☕",
    ),
    ("en", "evening"): dict(
        gradient=[(71, 118, 230), (142, 84, 233)],
        topic_badge_bg=(0, 245, 212, 230),  topic_badge_fg=(26, 26, 26),
        lang_badge_bg=(255, 255, 255, 50),  lang_badge_fg=(255, 255, 255),
        text_main=(255, 255, 255),          text_sub=(255, 255, 255, 180),
        kr_badge_bg=(255, 255, 255, 50),
        emoji="🗺️",
    ),
    # ─── CHINESE ────────────────────────────────────────────────────
    ("zh", "morning"): dict(
        gradient=[(255, 107, 53), (238, 9, 121)],
        topic_badge_bg=(255, 230, 0, 220),  topic_badge_fg=(26, 26, 26),
        lang_badge_bg=(255, 255, 255, 50),  lang_badge_fg=(255, 255, 255),
        text_main=(255, 255, 255),          text_sub=(255, 255, 255, 180),
        kr_badge_bg=(255, 255, 255, 50),
        emoji="🙏",
    ),
    ("zh", "lunch"): dict(
        gradient=[(247, 151, 30), (255, 210, 0)],
        topic_badge_bg=(26, 26, 26, 230),   topic_badge_fg=(255, 210, 0),
        lang_badge_bg=(0, 0, 0, 38),        lang_badge_fg=(26, 26, 26),
        text_main=(26, 26, 26),             text_sub=(0, 0, 0, 140),
        kr_badge_bg=(0, 0, 0, 30),
        emoji="🧋",
    ),
    ("zh", "evening"): dict(
        gradient=[(6, 214, 160), (17, 138, 178)],
        topic_badge_bg=(255, 230, 0, 220),  topic_badge_fg=(26, 26, 26),
        lang_badge_bg=(255, 255, 255, 50),  lang_badge_fg=(255, 255, 255),
        text_main=(255, 255, 255),          text_sub=(255, 255, 255, 180),
        kr_badge_bg=(255, 255, 255, 50),
        emoji="🗺️",
    ),
    # ─── JAPANESE ───────────────────────────────────────────────────
    ("ja", "morning"): dict(
        gradient=[(155, 93, 229), (0, 187, 249)],
        topic_badge_bg=(0, 245, 212, 230),  topic_badge_fg=(26, 26, 26),
        lang_badge_bg=(255, 255, 255, 50),  lang_badge_fg=(255, 255, 255),
        text_main=(255, 255, 255),          text_sub=(255, 255, 255, 180),
        kr_badge_bg=(255, 255, 255, 50),
        emoji="🌸",
    ),
    ("ja", "lunch"): dict(
        gradient=[(0, 245, 212), (0, 187, 249), (155, 93, 229)],
        topic_badge_bg=(255, 255, 255, 230), topic_badge_fg=(155, 93, 229),
        lang_badge_bg=(255, 255, 255, 50),  lang_badge_fg=(255, 255, 255),
        text_main=(255, 255, 255),          text_sub=(255, 255, 255, 180),
        kr_badge_bg=(255, 255, 255, 50),
        emoji="🍵",
    ),
    ("ja", "evening"): dict(
        gradient=[(247, 37, 133), (114, 9, 183)],
        topic_badge_bg=(255, 230, 0, 220),  topic_badge_fg=(26, 26, 26),
        lang_badge_bg=(255, 255, 255, 50),  lang_badge_fg=(255, 255, 255),
        text_main=(255, 255, 255),          text_sub=(255, 255, 255, 180),
        kr_badge_bg=(255, 255, 255, 50),
        emoji="🏷️",
    ),
}

CARD_W = 1080
CARD_H = 1080
PAD = 72
USABLE_W = CARD_W - PAD * 2
