"""Unsplash API를 사용해 도시 배경 이미지를 가져오는 모듈"""
from __future__ import annotations

import os
import random
import pathlib

import requests
from dotenv import load_dotenv

load_dotenv(pathlib.Path(__file__).parent.parent / ".env", override=True)

from city_pools import LANG_CITIES, SLOT_KEYWORDS

_TMP_DIR = pathlib.Path(__file__).parent.parent / "tmp"


def fetch_city_bg(lang: str, slot: str, city: str = None) -> str | None:
    """
    Unsplash에서 슬롯/언어에 맞는 도시 배경 이미지를 내려받아 경로 반환.

    Parameters
    ----------
    lang : str
        언어 코드 ("en", "zh", "ja")
    slot : str
        시간대 슬롯 ("morning", "lunch", "evening")
    city : str, optional
        도시명. None이면 LANG_CITIES[lang]에서 무작위 선택.

    Returns
    -------
    str | None
        저장된 임시 파일 경로. 오류 발생 시 None.
    """
    access_key = os.environ.get("UNSPLASH_ACCESS_KEY", "")
    if not access_key:
        return None

    try:
        if city is None:
            cities = LANG_CITIES.get(lang, [])
            if not cities:
                return None
            city = random.choice(cities)

        keyword = SLOT_KEYWORDS.get(slot, "cityscape")
        query = f"{city} {keyword} cityscape"

        resp = requests.get(
            "https://api.unsplash.com/photos/random",
            params={
                "query": query,
                "orientation": "portrait",
                "client_id": access_key,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        image_url = data["urls"]["regular"]

        img_resp = requests.get(image_url, timeout=30)
        img_resp.raise_for_status()

        _TMP_DIR.mkdir(parents=True, exist_ok=True)
        out_path = _TMP_DIR / f"bg_{lang}_{slot}.jpg"
        out_path.write_bytes(img_resp.content)

        return str(out_path)

    except Exception:
        return None
