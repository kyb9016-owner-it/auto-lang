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
    # ─── ENGLISH ─────────────────────────────── Notion Light
    ("en", "morning"): dict(
        gradient=[(255, 255, 255), (255, 255, 255)],
        topic_badge_bg=(242, 249, 255, 255), topic_badge_fg=(9, 127, 232),
        lang_badge_bg=(0, 0, 0, 13),         lang_badge_fg=(0, 0, 0),
        text_main=(0, 0, 0),                 text_sub=(97, 93, 89, 200),
        kr_badge_bg=(0, 0, 0, 13),
        emoji="😊",
        slot_keyword="sunrise",
    ),
    ("en", "lunch"): dict(
        gradient=[(255, 255, 255), (255, 255, 255)],
        topic_badge_bg=(242, 249, 255, 255), topic_badge_fg=(9, 127, 232),
        lang_badge_bg=(0, 0, 0, 13),         lang_badge_fg=(0, 0, 0),
        text_main=(0, 0, 0),                 text_sub=(97, 93, 89, 200),
        kr_badge_bg=(0, 0, 0, 13),
        emoji="☕",
        slot_keyword="street daytime",
    ),
    ("en", "evening"): dict(
        gradient=[(255, 255, 255), (255, 255, 255)],
        topic_badge_bg=(242, 249, 255, 255), topic_badge_fg=(9, 127, 232),
        lang_badge_bg=(0, 0, 0, 13),         lang_badge_fg=(0, 0, 0),
        text_main=(0, 0, 0),                 text_sub=(97, 93, 89, 200),
        kr_badge_bg=(0, 0, 0, 13),
        emoji="🗺️",
        slot_keyword="night lights",
    ),
    # ─── CHINESE ─────────────────────────────── Notion Light
    ("zh", "morning"): dict(
        gradient=[(255, 255, 255), (255, 255, 255)],
        topic_badge_bg=(242, 249, 255, 255), topic_badge_fg=(9, 127, 232),
        lang_badge_bg=(0, 0, 0, 13),         lang_badge_fg=(0, 0, 0),
        text_main=(0, 0, 0),                 text_sub=(97, 93, 89, 200),
        kr_badge_bg=(0, 0, 0, 13),
        emoji="🙏",
        slot_keyword="sunrise",
    ),
    ("zh", "lunch"): dict(
        gradient=[(255, 255, 255), (255, 255, 255)],
        topic_badge_bg=(242, 249, 255, 255), topic_badge_fg=(9, 127, 232),
        lang_badge_bg=(0, 0, 0, 13),         lang_badge_fg=(0, 0, 0),
        text_main=(0, 0, 0),                 text_sub=(97, 93, 89, 200),
        kr_badge_bg=(0, 0, 0, 13),
        emoji="🧋",
        slot_keyword="street daytime",
    ),
    ("zh", "evening"): dict(
        gradient=[(255, 255, 255), (255, 255, 255)],
        topic_badge_bg=(242, 249, 255, 255), topic_badge_fg=(9, 127, 232),
        lang_badge_bg=(0, 0, 0, 13),         lang_badge_fg=(0, 0, 0),
        text_main=(0, 0, 0),                 text_sub=(97, 93, 89, 200),
        kr_badge_bg=(0, 0, 0, 13),
        emoji="🗺️",
        slot_keyword="night lights",
    ),
    # ─── JAPANESE ────────────────────────────── Notion Light
    ("ja", "morning"): dict(
        gradient=[(255, 255, 255), (255, 255, 255)],
        topic_badge_bg=(242, 249, 255, 255), topic_badge_fg=(9, 127, 232),
        lang_badge_bg=(0, 0, 0, 13),         lang_badge_fg=(0, 0, 0),
        text_main=(0, 0, 0),                 text_sub=(97, 93, 89, 200),
        kr_badge_bg=(0, 0, 0, 13),
        emoji="🌸",
        slot_keyword="sunrise",
    ),
    ("ja", "lunch"): dict(
        gradient=[(255, 255, 255), (255, 255, 255)],
        topic_badge_bg=(242, 249, 255, 255), topic_badge_fg=(9, 127, 232),
        lang_badge_bg=(0, 0, 0, 13),         lang_badge_fg=(0, 0, 0),
        text_main=(0, 0, 0),                 text_sub=(97, 93, 89, 200),
        kr_badge_bg=(0, 0, 0, 13),
        emoji="🍵",
        slot_keyword="street daytime",
    ),
    ("ja", "evening"): dict(
        gradient=[(255, 255, 255), (255, 255, 255)],
        topic_badge_bg=(242, 249, 255, 255), topic_badge_fg=(9, 127, 232),
        lang_badge_bg=(0, 0, 0, 13),         lang_badge_fg=(0, 0, 0),
        text_main=(0, 0, 0),                 text_sub=(97, 93, 89, 200),
        kr_badge_bg=(0, 0, 0, 13),
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
