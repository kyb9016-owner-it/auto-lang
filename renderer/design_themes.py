"""25개 디자인 시스템 팔레트 — 주간 로테이션용"""

DESIGN_THEMES = {
    # ── Dark + Color accent ──────────────────────────────────────────────────
    "linear": {
        "name": "Linear",
        "mode": "dark",
        "bg": (8, 9, 10),
        "card_bg": (25, 26, 27),
        "text_main": (247, 248, 248),
        "text_sub": (138, 143, 152),
        "accent": (94, 106, 210),
        "accent_light": (94, 106, 210, 30),
        "wrong_color": (239, 68, 68),
    },
    "spotify": {
        "name": "Spotify",
        "mode": "dark",
        "bg": (18, 18, 18),
        "card_bg": (24, 24, 24),
        "text_main": (255, 255, 255),
        "text_sub": (179, 179, 179),
        "accent": (30, 215, 96),
        "accent_light": (30, 215, 96, 30),
        "wrong_color": (243, 114, 127),
    },
    "stripe": {
        "name": "Stripe",
        "mode": "dark",
        "bg": (10, 37, 64),
        "card_bg": (15, 45, 75),
        "text_main": (255, 255, 255),
        "text_sub": (160, 180, 200),
        "accent": (99, 91, 255),
        "accent_light": (99, 91, 255, 30),
        "wrong_color": (234, 34, 97),
    },
    "superhuman": {
        "name": "Superhuman",
        "mode": "dark",
        "bg": (13, 13, 13),
        "card_bg": (22, 22, 22),
        "text_main": (255, 255, 255),
        "text_sub": (150, 150, 150),
        "accent": (168, 85, 247),
        "accent_light": (168, 85, 247, 30),
        "wrong_color": (220, 38, 38),
    },
    "cursor": {
        "name": "Cursor",
        "mode": "dark",
        "bg": (12, 12, 12),
        "card_bg": (22, 22, 22),
        "text_main": (255, 255, 255),
        "text_sub": (150, 150, 150),
        "accent": (0, 212, 170),
        "accent_light": (0, 212, 170, 30),
        "wrong_color": (207, 45, 86),
    },
    "supabase": {
        "name": "Supabase",
        "mode": "dark",
        "bg": (23, 23, 23),
        "card_bg": (28, 28, 28),
        "text_main": (250, 250, 250),
        "text_sub": (180, 180, 180),
        "accent": (62, 207, 142),
        "accent_light": (62, 207, 142, 30),
        "wrong_color": (220, 38, 38),
    },
    "raycast": {
        "name": "Raycast",
        "mode": "dark",
        "bg": (7, 8, 10),
        "card_bg": (16, 17, 17),
        "text_main": (249, 249, 249),
        "text_sub": (156, 156, 157),
        "accent": (255, 99, 99),
        "accent_light": (255, 99, 99, 30),
        "wrong_color": (255, 99, 99),
    },
    "warp": {
        "name": "Warp",
        "mode": "dark",
        "bg": (20, 20, 18),
        "card_bg": (30, 30, 28),
        "text_main": (250, 249, 246),
        "text_sub": (175, 174, 172),
        "accent": (200, 180, 120),
        "accent_light": (200, 180, 120, 30),
        "wrong_color": (220, 38, 38),
    },
    "x_ai": {
        "name": "xAI",
        "mode": "dark",
        "bg": (31, 34, 40),
        "card_bg": (40, 44, 52),
        "text_main": (255, 255, 255),
        "text_sub": (180, 180, 190),
        "accent": (255, 255, 255),
        "accent_light": (255, 255, 255, 20),
        "wrong_color": (239, 68, 68),
    },
    "figma": {
        "name": "Figma",
        "mode": "dark",
        "bg": (30, 30, 30),
        "card_bg": (44, 44, 44),
        "text_main": (255, 255, 255),
        "text_sub": (170, 170, 170),
        "accent": (242, 78, 30),
        "accent_light": (242, 78, 30, 30),
        "wrong_color": (220, 38, 38),
    },
    "framer": {
        "name": "Framer",
        "mode": "dark",
        "bg": (0, 0, 0),
        "card_bg": (9, 9, 9),
        "text_main": (255, 255, 255),
        "text_sub": (166, 166, 166),
        "accent": (0, 153, 255),
        "accent_light": (0, 153, 255, 30),
        "wrong_color": (239, 68, 68),
    },
    "spacex": {
        "name": "SpaceX",
        "mode": "dark",
        "bg": (0, 0, 0),
        "card_bg": (10, 10, 10),
        "text_main": (240, 240, 250),
        "text_sub": (160, 160, 170),
        "accent": (0, 120, 215),
        "accent_light": (0, 120, 215, 30),
        "wrong_color": (220, 38, 38),
    },

    # ── Light / Warm ─────────────────────────────────────────────────────────
    "notion": {
        "name": "Notion",
        "mode": "light",
        "bg": (255, 255, 255),
        "card_bg": (255, 255, 255),
        "text_main": (0, 0, 0),
        "text_sub": (97, 93, 89),
        "accent": (0, 117, 222),
        "accent_light": (242, 249, 255, 255),
        "wrong_color": (221, 91, 0),
    },
    "pinterest": {
        "name": "Pinterest",
        "mode": "light",
        "bg": (255, 255, 255),
        "card_bg": (249, 245, 240),
        "text_main": (33, 25, 34),
        "text_sub": (98, 98, 91),
        "accent": (230, 0, 35),
        "accent_light": (230, 0, 35, 25),
        "wrong_color": (158, 10, 10),
    },
    "airbnb": {
        "name": "Airbnb",
        "mode": "light",
        "bg": (255, 255, 255),
        "card_bg": (255, 255, 255),
        "text_main": (34, 34, 34),
        "text_sub": (106, 106, 106),
        "accent": (255, 56, 92),
        "accent_light": (255, 56, 92, 25),
        "wrong_color": (193, 53, 21),
    },
    "cal": {
        "name": "Cal.com",
        "mode": "light",
        "bg": (255, 255, 255),
        "card_bg": (255, 255, 255),
        "text_main": (36, 36, 36),
        "text_sub": (137, 137, 137),
        "accent": (36, 36, 36),
        "accent_light": (36, 36, 36, 20),
        "wrong_color": (220, 38, 38),
    },
    "mintlify": {
        "name": "Mintlify",
        "mode": "light",
        "bg": (255, 255, 255),
        "card_bg": (255, 255, 255),
        "text_main": (13, 13, 13),
        "text_sub": (102, 102, 102),
        "accent": (24, 226, 153),
        "accent_light": (212, 250, 232, 255),
        "wrong_color": (212, 86, 86),
    },
    "wise": {
        "name": "Wise",
        "mode": "light",
        "bg": (255, 255, 255),
        "card_bg": (255, 255, 255),
        "text_main": (14, 15, 12),
        "text_sub": (134, 134, 133),
        "accent": (159, 232, 112),
        "accent_light": (226, 246, 213, 255),
        "wrong_color": (208, 50, 56),
    },

    # ── Monochrome ───────────────────────────────────────────────────────────
    "vercel": {
        "name": "Vercel",
        "mode": "dark",
        "bg": (0, 0, 0),
        "card_bg": (17, 17, 17),
        "text_main": (237, 237, 237),
        "text_sub": (136, 136, 136),
        "accent": (255, 255, 255),
        "accent_light": (255, 255, 255, 20),
        "wrong_color": (255, 91, 79),
    },
    "tesla": {
        "name": "Tesla",
        "mode": "dark",
        "bg": (0, 0, 0),
        "card_bg": (10, 10, 10),
        "text_main": (255, 255, 255),
        "text_sub": (120, 120, 120),
        "accent": (255, 255, 255),
        "accent_light": (255, 255, 255, 20),
        "wrong_color": (220, 38, 38),
    },
    "apple": {
        "name": "Apple",
        "mode": "light",
        "bg": (245, 245, 247),
        "card_bg": (245, 245, 247),
        "text_main": (29, 29, 31),
        "text_sub": (134, 134, 139),
        "accent": (0, 113, 227),
        "accent_light": (0, 113, 227, 25),
        "wrong_color": (255, 59, 48),
    },
    "uber": {
        "name": "Uber",
        "mode": "dark",
        "bg": (0, 0, 0),
        "card_bg": (15, 15, 15),
        "text_main": (255, 255, 255),
        "text_sub": (140, 140, 140),
        "accent": (255, 255, 255),
        "accent_light": (255, 255, 255, 15),
        "wrong_color": (220, 38, 38),
    },

    # ── Vivid ─────────────────────────────────────────────────────────────────
    "nvidia": {
        "name": "NVIDIA",
        "mode": "dark",
        "bg": (0, 0, 0),
        "card_bg": (26, 26, 26),
        "text_main": (255, 255, 255),
        "text_sub": (167, 167, 167),
        "accent": (118, 185, 0),
        "accent_light": (118, 185, 0, 30),
        "wrong_color": (229, 32, 32),
    },
    "coinbase": {
        "name": "Coinbase",
        "mode": "dark",
        "bg": (5, 15, 44),
        "card_bg": (10, 25, 60),
        "text_main": (255, 255, 255),
        "text_sub": (160, 170, 190),
        "accent": (0, 82, 255),
        "accent_light": (0, 82, 255, 30),
        "wrong_color": (220, 38, 38),
    },
    "revolut": {
        "name": "Revolut",
        "mode": "dark",
        "bg": (15, 15, 20),
        "card_bg": (25, 25, 32),
        "text_main": (255, 255, 255),
        "text_sub": (150, 155, 165),
        "accent": (73, 79, 223),
        "accent_light": (73, 79, 223, 30),
        "wrong_color": (226, 59, 74),
    },
}

# 주간 로테이션 순서 (밝은/어두운 교차로 변화감 극대화)
THEME_ROTATION = [
    "linear", "notion", "spotify", "pinterest",
    "stripe", "airbnb", "supabase", "mintlify",
    "raycast", "wise", "cursor", "apple",
    "superhuman", "figma", "framer", "vercel",
    "nvidia", "tesla", "coinbase", "uber",
    "warp", "revolut", "spacex", "x_ai", "cal",
]


def get_weekly_theme() -> dict:
    """KST 기준 이번 주 테마 반환 (오버라이드 파일 우선)"""
    import os
    from datetime import datetime, timezone, timedelta

    # Check override file
    override_path = os.path.join(os.path.dirname(__file__), "..", "theme_override.txt")
    if os.path.exists(override_path):
        try:
            key = open(override_path).read().strip()
            if key in DESIGN_THEMES:
                theme = DESIGN_THEMES[key].copy()
                theme["key"] = key
                theme["overridden"] = True
                return theme
        except Exception:
            pass

    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    week_num = now.isocalendar()[1]
    idx = week_num % len(THEME_ROTATION)
    key = THEME_ROTATION[idx]
    theme = DESIGN_THEMES[key].copy()
    theme["key"] = key
    return theme


def get_theme_by_key(key: str) -> dict:
    """키로 특정 테마 반환"""
    theme = DESIGN_THEMES[key].copy()
    theme["key"] = key
    return theme


def list_themes() -> list[dict]:
    """전체 테마 리스트 반환 (key, name, mode)"""
    return [
        {"key": k, "name": v["name"], "mode": v["mode"]}
        for k, v in DESIGN_THEMES.items()
    ]
