"""폰트 로더 — 없으면 자동 다운로드"""
from __future__ import annotations
import os
import requests
from typing import Optional
from PIL import ImageFont

FONTS_DIR = os.path.join(os.path.dirname(__file__), "..", "fonts")
_cache: dict = {}

# GitHub raw URL에서 직접 TTF 다운로드
_FONT_URLS = [
    (
        "Boldonse-Regular.ttf",
        "https://github.com/google/fonts/raw/main/ofl/boldonse/Boldonse-Regular.ttf",
    ),
    (
        "Poppins-ExtraBold.ttf",
        "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-ExtraBold.ttf",
    ),
    (
        "NotoSansJP-Bold.ttf",
        "https://github.com/google/fonts/raw/main/ofl/notosansjp/NotoSansJP%5Bwght%5D.ttf",
    ),
    (
        "NotoSansSC-Bold.ttf",
        "https://github.com/google/fonts/raw/main/ofl/notosanssc/NotoSansSC%5Bwght%5D.ttf",
    ),
    (
        "NotoSansKR-Bold.ttf",
        "https://github.com/google/fonts/raw/main/ofl/notosanskr/NotoSansKR%5Bwght%5D.ttf",
    ),
    # 국기 PNG (Twemoji 72x72)
    (
        "flag_us.png",
        "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f1fa-1f1f8.png",
    ),
    (
        "flag_cn.png",
        "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f1e8-1f1f3.png",
    ),
    (
        "flag_jp.png",
        "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f1ef-1f1f5.png",
    ),
]

# 국기 이모지 → PNG 파일명 매핑
_FLAG_MAP = {
    "🇺🇸": "flag_us.png",
    "🇨🇳": "flag_cn.png",
    "🇯🇵": "flag_jp.png",
}


def flag_path(emoji: str) -> Optional[str]:
    """국기 이모지 → PNG 절대경로. 없으면 None."""
    filename = _FLAG_MAP.get(emoji)
    if filename:
        p = os.path.join(FONTS_DIR, filename)
        if os.path.exists(p):
            return p
    return None


def _download_font(filename, url):
    """URL에서 TTF 직접 다운로드."""
    path = os.path.join(FONTS_DIR, filename)
    if os.path.exists(path):
        return True
    try:
        resp = requests.get(url, timeout=30, allow_redirects=True)
        resp.raise_for_status()
        os.makedirs(FONTS_DIR, exist_ok=True)
        with open(path, "wb") as f:
            f.write(resp.content)
        print(f"  ✓ 폰트 다운로드: {filename}")
        return True
    except Exception as e:
        print(f"  ✗ 폰트 다운로드 실패 ({filename}): {e}")
        return False


def ensure_fonts():
    """필요한 폰트 모두 다운로드"""
    for filename, url in _FONT_URLS:
        _download_font(filename, url)


def _path(filename: str) -> str:
    return os.path.join(FONTS_DIR, filename)


def get(filename: str, size: int) -> ImageFont.FreeTypeFont:
    key = (filename, size)
    if key not in _cache:
        full = _path(filename)
        if os.path.exists(full):
            _cache[key] = ImageFont.truetype(full, size)
        else:
            _cache[key] = ImageFont.load_default(size)
    return _cache[key]


def _get_bold(filename: str, size: int, weight: int = 700) -> ImageFont.FreeTypeFont:
    """Variable font에서 Bold(700) 인스턴스를 반환. 별도 캐시 키 사용."""
    key = (filename, size, weight)
    if key not in _cache:
        full = _path(filename)
        if os.path.exists(full):
            f = ImageFont.truetype(full, size)
            try:
                f.set_variation_by_axes([weight])
            except Exception:
                try:
                    f.set_variation_by_name("Bold")
                except Exception:
                    pass
            _cache[key] = f
        else:
            _cache[key] = ImageFont.load_default(size)
    return _cache[key]


# 편의 함수들
def bold(size: int) -> ImageFont.FreeTypeFont:
    return get("Boldonse-Regular.ttf", size)

def outfit(size: int) -> ImageFont.FreeTypeFont:
    return get("Poppins-ExtraBold.ttf", size)

def noto_jp(size: int) -> ImageFont.FreeTypeFont:
    return _get_bold("NotoSansJP-Bold.ttf", size)

def noto_sc(size: int) -> ImageFont.FreeTypeFont:
    return _get_bold("NotoSansSC-Bold.ttf", size)

def noto_kr(size: int) -> ImageFont.FreeTypeFont:
    return _get_bold("NotoSansKR-Bold.ttf", size)

def lang_font(lang: str, size: int) -> ImageFont.FreeTypeFont:
    """언어에 맞는 폰트 반환"""
    if lang == "ja":
        return noto_jp(size)
    if lang == "zh":
        return noto_sc(size)
    return bold(size)
