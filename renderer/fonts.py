"""폰트 로더 — 없으면 자동 다운로드"""
import os
import re
import requests
from PIL import ImageFont

FONTS_DIR = os.path.join(os.path.dirname(__file__), "..", "fonts")
_cache = {}

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
]


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


# 편의 함수들
def bold(size: int) -> ImageFont.FreeTypeFont:
    return get("Boldonse-Regular.ttf", size)

def outfit(size: int) -> ImageFont.FreeTypeFont:
    return get("Poppins-ExtraBold.ttf", size)

def noto_jp(size: int) -> ImageFont.FreeTypeFont:
    return get("NotoSansJP-Bold.ttf", size)

def noto_sc(size: int) -> ImageFont.FreeTypeFont:
    return get("NotoSansSC-Bold.ttf", size)

def noto_kr(size: int) -> ImageFont.FreeTypeFont:
    return get("NotoSansKR-Bold.ttf", size)

def lang_font(lang: str, size: int) -> ImageFont.FreeTypeFont:
    """언어에 맞는 폰트 반환"""
    if lang == "ja":
        return noto_jp(size)
    if lang == "zh":
        return noto_sc(size)
    return bold(size)
