"""LangCard Studio — 전역 설정"""
from datetime import date, datetime, timezone, timedelta

# KST = UTC+9 (서버가 UTC여도 한국 날짜 기준으로 파일명/로직 통일)
_KST = timezone(timedelta(hours=9))


def _today_kst() -> date:
    """서버 timezone과 무관하게 KST 기준 오늘 날짜 반환"""
    return datetime.now(_KST).date()

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
    """오늘의 주제 반환 (KST 날짜 기반 순환)"""
    epoch = date(2026, 1, 1)
    idx = (_today_kst() - epoch).days % 3
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
# 슬롯별 음성 구분: morning=여성, lunch=남성(차분), evening=남성(캐주얼)
TTS_VOICES = {
    "en": {
        "morning": "en-US-JennyNeural",   # 여성
        "lunch":   "en-US-GuyNeural",     # 남성 (차분)
        "evening": "en-US-DavisNeural",   # 남성 (캐주얼)
        "default": "en-US-JennyNeural",   # fallback
    },
    "zh": {
        "morning": "zh-CN-XiaoxiaoNeural",  # 여성
        "lunch":   "zh-CN-YunyangNeural",   # 남성
        "evening": "zh-CN-YunyangNeural",   # 남성
        "default": "zh-CN-XiaoxiaoNeural",  # fallback
    },
    "ja": {
        "morning": "ja-JP-NanamiNeural",    # 여성
        "lunch":   "ja-JP-KeitaNeural",     # 남성
        "evening": "ja-JP-KeitaNeural",     # 남성
        "default": "ja-JP-NanamiNeural",    # fallback
    },
}

# ── 언어별 해시태그 (개별 포스팅용) ─────────────────────────────────────────
# 전략: 초경쟁 광범위 태그 제거 → 중간 규모 niche 태그 집중 (10개 내외)
LANG_HASHTAGS = {
    "en": (
        "#영어회화 #영어공부 #오늘의영어 #영어표현 "
        "#dailyenglish #englishphrase #learnenglish "
        "#외국어공부 #공부스타그램 #langcard"
    ),
    "zh": (
        "#중국어회화 #중국어공부 #오늘의중국어 #중국어표현 "
        "#dailychinese #chinesephrase #learnchinese "
        "#외국어공부 #공부스타그램 #langcard"
    ),
    "ja": (
        "#일본어회화 #일본어공부 #오늘의일본어 #일본어표현 "
        "#dailyjapanese #japanesephrase #learnjapanese "
        "#외국어공부 #공부스타그램 #langcard"
    ),
}

# 종합 릴스용 해시태그 (3개국어 모두)
HASHTAGS = (
    "#영어회화 #영어공부 #중국어회화 #중국어공부 "
    "#일본어회화 #일본어공부 #3개국어 "
    "#외국어공부 #언어공부 #공부스타그램 "
    "#languagelearning #polyglot #langcard #랭카드스튜디오"
)

# ── 기타 설정 ────────────────────────────────────────────────────────────────
HISTORY_MAX = 200  # 언어별 최근 표현 보관 수 (3회/일 × 66일치)

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
