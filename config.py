"""LangCard Studio — 전역 설정"""

SLOT_CONFIG = {
    "morning": {
        "label": "아침",
        "emoji": "🌅",
        "topic_ko": "인사 & 소개",
        "topic_en": "Greetings & Introductions",
        "topic_badge": "GREETINGS",
        "cron_utc": "0 23 * * *",   # 08:00 KST
    },
    "lunch": {
        "label": "점심",
        "emoji": "☕",
        "topic_ko": "카페 & 식당",
        "topic_en": "Cafe & Restaurant",
        "topic_badge": "CAFE",
        "cron_utc": "0 3 * * *",    # 12:00 KST
    },
    "evening": {
        "label": "저녁",
        "emoji": "✈️",
        "topic_ko": "여행 & 쇼핑",
        "topic_en": "Travel & Shopping",
        "topic_badge": "TRAVEL",
        "cron_utc": "0 11 * * *",   # 20:00 KST
    },
}

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

HASHTAGS = (
    "#영어회화 #중국어회화 #일본어회화 #외국어공부 #랭카드스튜디오 "
    "#하루3회 #오늘의표현 #영어 #중국어 #일본어 #language "
    "#회화공부 #언어공부 #LangCardStudio #langcard"
)

HISTORY_MAX = 50  # 언어별로 최근 몇 개 표현을 중복 방지에 사용
