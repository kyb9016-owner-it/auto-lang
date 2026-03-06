"""LangCard Studio — 전역 설정"""
from datetime import date

# ── 주제 설정 (일별 순환: 0→인사, 1→카페, 2→여행) ───────────────────────────
TOPIC_CONFIG = {
    0: {
        "topic_ko": "인사 & 소개",
        "topic_en": "Greetings & Introductions",
        "badge": "GREETINGS",
        "emoji": "🌅",
        "theme_slot": "morning",   # CARD_THEMES 키 매핑
    },
    1: {
        "topic_ko": "카페 & 식당",
        "topic_en": "Cafe & Restaurant",
        "badge": "CAFE",
        "emoji": "☕",
        "theme_slot": "lunch",
    },
    2: {
        "topic_ko": "여행 & 쇼핑",
        "topic_en": "Travel & Shopping",
        "badge": "TRAVEL",
        "emoji": "✈️",
        "theme_slot": "evening",
    },
}


def get_today_topic() -> dict:
    """오늘의 주제 반환 (날짜 기반 순환)"""
    epoch = date(2026, 1, 1)
    idx = (date.today() - epoch).days % 3
    return TOPIC_CONFIG[idx]


# ── 언어 설정 ────────────────────────────────────────────────────────────────
LANGUAGES = ["en", "zh", "ja"]

LANG_CONFIG = {
    "en": {
        "name": "English",
        "name_ko": "영어",
        "name_native": "ENG",
        "flag": "🇺🇸",
        "has_pronunciation": False,
        "pronunciation_label": None,
    },
    "zh": {
        "name": "Chinese",
        "name_ko": "중국어",
        "name_native": "中文",
        "flag": "🇨🇳",
        "has_pronunciation": True,
        "pronunciation_label": "병음",
    },
    "ja": {
        "name": "Japanese",
        "name_ko": "일본어",
        "name_native": "日本語",
        "flag": "🇯🇵",
        "has_pronunciation": True,
        "pronunciation_label": "로마자",
    },
}

# ── TTS 음성 설정 (edge-tts) ─────────────────────────────────────────────────
TTS_VOICES = {
    "en": "en-US-JennyNeural",
    "zh": "zh-CN-XiaoxiaoNeural",
    "ja": "ja-JP-NanamiNeural",
}

# ── 언어별 해시태그 (개별 포스팅용) ─────────────────────────────────────────
LANG_HASHTAGS = {
    "en": (
        "#영어 #영어공부 #영어회화 #영어표현 #오늘의영어 "
        "#english #englishlearning #learnenglish #영어스피킹 "
        "#외국어공부 #공부스타그램 #languagelearning "
        "#오늘의표현 #오늘의단어 #langcard #랭카드스튜디오"
    ),
    "zh": (
        "#중국어 #중국어공부 #중국어회화 #오늘의중국어 #중국어표현 "
        "#chinese #chineselearning #learnchinese #普通话 "
        "#외국어공부 #공부스타그램 #languagelearning "
        "#오늘의표현 #오늘의단어 #langcard #랭카드스튜디오"
    ),
    "ja": (
        "#일본어 #일본어공부 #일본어회화 #오늘의일본어 #일본어표현 "
        "#japanese #japaneselearning #learnjapanese #日本語 "
        "#외국어공부 #공부스타그램 #languagelearning "
        "#오늘의표현 #오늘의단어 #langcard #랭카드스튜디오"
    ),
}

# 종합 릴스용 해시태그 (3개국어 모두)
HASHTAGS = (
    "#영어 #영어공부 #영어회화 #영어표현 #오늘의영어 "
    "#중국어 #중국어공부 #중국어회화 #오늘의중국어 "
    "#일본어 #일본어공부 #일본어회화 #오늘의일본어 "
    "#3개국어 #외국어공부 #언어공부 #공부스타그램 "
    "#languagelearning #polyglot #multilingual "
    "#english #chinese #japanese "
    "#오늘의표현 #오늘의단어 #langcard #랭카드스튜디오"
)

# ── 기타 설정 ────────────────────────────────────────────────────────────────
HISTORY_MAX = 50  # 언어별로 최근 몇 개 표현을 중복 방지에 사용

# ── 하위 호환용 SLOT_CONFIG (기존 코드 참조 대비) ─────────────────────────────
SLOT_CONFIG = {
    "morning": {
        "label": "아침",
        "emoji": "🌅",
        "topic_ko": "인사 & 소개",
        "topic_en": "Greetings & Introductions",
        "topic_badge": "GREETINGS",
        "cron_utc": "0 23 * * *",
    },
    "lunch": {
        "label": "점심",
        "emoji": "☕",
        "topic_ko": "카페 & 식당",
        "topic_en": "Cafe & Restaurant",
        "topic_badge": "CAFE",
        "cron_utc": "0 3 * * *",
    },
    "evening": {
        "label": "저녁",
        "emoji": "✈️",
        "topic_ko": "여행 & 쇼핑",
        "topic_en": "Travel & Shopping",
        "topic_badge": "TRAVEL",
        "cron_utc": "0 11 * * *",
    },
}
