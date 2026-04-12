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
    # ─── ENGLISH ─────────────────────────────── Apple Dark / Light / Dark
    ("en", "morning"): dict(
        gradient=[(0, 0, 0), (0, 0, 0)],
        topic_badge_bg=(0, 113, 227, 230),  topic_badge_fg=(255, 255, 255),
        lang_badge_bg=(255, 255, 255, 30),  lang_badge_fg=(255, 255, 255),
        text_main=(255, 255, 255),          text_sub=(255, 255, 255, 160),
        kr_badge_bg=(255, 255, 255, 25),
        emoji="😊",
        slot_keyword="sunrise",
    ),
    ("en", "lunch"): dict(
        gradient=[(245, 245, 247), (245, 245, 247)],
        topic_badge_bg=(0, 113, 227, 230),  topic_badge_fg=(255, 255, 255),
        lang_badge_bg=(0, 0, 0, 30),        lang_badge_fg=(29, 29, 31),
        text_main=(29, 29, 31),             text_sub=(0, 0, 0, 140),
        kr_badge_bg=(0, 0, 0, 20),
        emoji="☕",
        slot_keyword="street daytime",
    ),
    ("en", "evening"): dict(
        gradient=[(0, 0, 0), (0, 0, 0)],
        topic_badge_bg=(0, 113, 227, 230),  topic_badge_fg=(255, 255, 255),
        lang_badge_bg=(255, 255, 255, 30),  lang_badge_fg=(255, 255, 255),
        text_main=(255, 255, 255),          text_sub=(255, 255, 255, 160),
        kr_badge_bg=(255, 255, 255, 25),
        emoji="🗺️",
        slot_keyword="night lights",
    ),
    # ─── CHINESE ─────────────────────────────── Apple Light / Dark / Light
    ("zh", "morning"): dict(
        gradient=[(245, 245, 247), (245, 245, 247)],
        topic_badge_bg=(0, 113, 227, 230),  topic_badge_fg=(255, 255, 255),
        lang_badge_bg=(0, 0, 0, 30),        lang_badge_fg=(29, 29, 31),
        text_main=(29, 29, 31),             text_sub=(0, 0, 0, 140),
        kr_badge_bg=(0, 0, 0, 20),
        emoji="🙏",
        slot_keyword="sunrise",
    ),
    ("zh", "lunch"): dict(
        gradient=[(0, 0, 0), (0, 0, 0)],
        topic_badge_bg=(0, 113, 227, 230),  topic_badge_fg=(255, 255, 255),
        lang_badge_bg=(255, 255, 255, 30),  lang_badge_fg=(255, 255, 255),
        text_main=(255, 255, 255),          text_sub=(255, 255, 255, 160),
        kr_badge_bg=(255, 255, 255, 25),
        emoji="🧋",
        slot_keyword="street daytime",
    ),
    ("zh", "evening"): dict(
        gradient=[(245, 245, 247), (245, 245, 247)],
        topic_badge_bg=(0, 113, 227, 230),  topic_badge_fg=(255, 255, 255),
        lang_badge_bg=(0, 0, 0, 30),        lang_badge_fg=(29, 29, 31),
        text_main=(29, 29, 31),             text_sub=(0, 0, 0, 140),
        kr_badge_bg=(0, 0, 0, 20),
        emoji="🗺️",
        slot_keyword="night lights",
    ),
    # ─── JAPANESE ────────────────────────────── Apple Dark / Light / Dark
    ("ja", "morning"): dict(
        gradient=[(0, 0, 0), (0, 0, 0)],
        topic_badge_bg=(0, 113, 227, 230),  topic_badge_fg=(255, 255, 255),
        lang_badge_bg=(255, 255, 255, 30),  lang_badge_fg=(255, 255, 255),
        text_main=(255, 255, 255),          text_sub=(255, 255, 255, 160),
        kr_badge_bg=(255, 255, 255, 25),
        emoji="🌸",
        slot_keyword="sunrise",
    ),
    ("ja", "lunch"): dict(
        gradient=[(245, 245, 247), (245, 245, 247)],
        topic_badge_bg=(0, 113, 227, 230),  topic_badge_fg=(255, 255, 255),
        lang_badge_bg=(0, 0, 0, 30),        lang_badge_fg=(29, 29, 31),
        text_main=(29, 29, 31),             text_sub=(0, 0, 0, 140),
        kr_badge_bg=(0, 0, 0, 20),
        emoji="🍵",
        slot_keyword="street daytime",
    ),
    ("ja", "evening"): dict(
        gradient=[(0, 0, 0), (0, 0, 0)],
        topic_badge_bg=(0, 113, 227, 230),  topic_badge_fg=(255, 255, 255),
        lang_badge_bg=(255, 255, 255, 30),  lang_badge_fg=(255, 255, 255),
        text_main=(255, 255, 255),          text_sub=(255, 255, 255, 160),
        kr_badge_bg=(255, 255, 255, 25),
        emoji="🏷️",
        slot_keyword="night lights",
    ),
}

CARD_W = 1080
CARD_H = 1350

# 릴스용 고해상도 (렌더링 시 2배로 그려 다운스케일 → 선명)
REEL_W = 1080
REEL_H = 1920
PAD = 72
USABLE_W = CARD_W - PAD * 2
