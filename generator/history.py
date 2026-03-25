"""생성 히스토리 관리 — 중복 방지용 JSON 저장소"""
import json
import os
import re
from difflib import SequenceMatcher
from config import LANGUAGES, HISTORY_MAX, HISTORY_SIMILARITY_THRESHOLD

HISTORY_PATH = os.path.join(os.path.dirname(__file__), "..", "history.json")


def _load() -> dict:
    if os.path.exists(HISTORY_PATH):
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {lang: [] for lang in LANGUAGES}


def _save(data: dict) -> None:
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _normalize(text: str) -> str:
    """소문자화 + 구두점 제거 + 공백 정규화 (유사도 비교용)"""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def get_recent(lang: str) -> list[str]:
    """최근 HISTORY_MAX 개 표현 반환"""
    data = _load()
    return data.get(lang, [])[-HISTORY_MAX:]


def is_duplicate(lang: str, expression: str) -> bool:
    """
    히스토리에 동일하거나 의미상 유사한 표현이 있으면 True.
    - 정확한 문자열 일치: O(1)
    - 유사도 체크: difflib.SequenceMatcher (임계값 HISTORY_SIMILARITY_THRESHOLD)
    """
    recent = get_recent(lang)
    if not recent:
        return False

    # 1) 정확한 일치 (빠름)
    if expression in set(recent):
        return True

    # 2) 유사도 체크 (퍼지 매칭)
    norm_new = _normalize(expression)
    for hist_expr in recent:
        ratio = SequenceMatcher(None, norm_new, _normalize(hist_expr)).ratio()
        if ratio >= HISTORY_SIMILARITY_THRESHOLD:
            return True

    return False


def add(lang: str, expression: str) -> None:
    """새 표현 추가 후 저장"""
    data = _load()
    if lang not in data:
        data[lang] = []
    data[lang].append(expression)
    # 최대 개수 유지
    data[lang] = data[lang][-HISTORY_MAX:]
    _save(data)


# ── 포스팅 중복 방지 ──────────────────────────────────────────────────

def is_slot_posted(date_str: str, slot: str) -> bool:
    """같은 날짜+슬롯으로 이미 포스팅했으면 True"""
    data = _load()
    posted = data.get("_posted_slots", {})
    return slot in posted.get(date_str, [])


def mark_slot_posted(date_str: str, slot: str) -> None:
    """포스팅 완료 기록"""
    data = _load()
    posted = data.setdefault("_posted_slots", {})
    if date_str not in posted:
        posted[date_str] = []
    if slot not in posted[date_str]:
        posted[date_str].append(slot)
    # 7일 이전 기록 정리
    from datetime import date as _date, timedelta
    cutoff = (_date.today() - timedelta(days=7)).strftime("%Y%m%d")
    for old_date in list(posted.keys()):
        if old_date < cutoff:
            del posted[old_date]
    _save(data)
