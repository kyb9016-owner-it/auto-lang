"""생성 히스토리 관리 — 중복 방지용 JSON 저장소"""
import json
import os
from config import LANGUAGES, HISTORY_MAX

HISTORY_PATH = os.path.join(os.path.dirname(__file__), "..", "history.json")


def _load() -> dict:
    if os.path.exists(HISTORY_PATH):
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {lang: [] for lang in LANGUAGES}


def _save(data: dict) -> None:
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_recent(lang: str) -> list[str]:
    """최근 HISTORY_MAX 개 표현 반환"""
    data = _load()
    return data.get(lang, [])[-HISTORY_MAX:]


def add(lang: str, expression: str) -> None:
    """새 표현 추가 후 저장"""
    data = _load()
    if lang not in data:
        data[lang] = []
    data[lang].append(expression)
    # 최대 개수 유지
    data[lang] = data[lang][-HISTORY_MAX:]
    _save(data)
