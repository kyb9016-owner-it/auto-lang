"""
LangCard Studio — 텔레그램 알림 유틸

dispatch.py, story_dispatcher.py 등에서 호출.
TELEGRAM_TOKEN + TELEGRAM_OWNER_ID 환경변수 필요 (.env).
전송 실패 시 예외를 일으키지 않고 False 반환 → 포스팅 흐름에 영향 없음.
"""

import os
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
_CHAT_ID = os.getenv("TELEGRAM_OWNER_ID", "")   # telegram_bot.py와 동일 변수


def send(text: str, parse_mode: str = "HTML") -> bool:
    """
    텔레그램으로 메시지 전송.
    parse_mode: "HTML" | "Markdown" | "" (plain)
    Returns: True(성공) / False(실패 or 설정 없음)
    """
    if not _TOKEN or not _CHAT_ID:
        return False
    try:
        payload: dict = {"chat_id": _CHAT_ID, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        resp = requests.post(
            f"https://api.telegram.org/bot{_TOKEN}/sendMessage",
            json=payload,
            timeout=10,
        )
        return resp.ok
    except Exception:
        return False
