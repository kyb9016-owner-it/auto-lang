"""Instagram Graph API — 캐러셀 포스팅"""
import os
import time
import requests
from config import LANG_CONFIG, SLOT_CONFIG, HASHTAGS

BASE_URL = "https://graph.instagram.com/v21.0"
IG_ID    = os.environ["INSTAGRAM_BUSINESS_ID"]
TOKEN    = os.environ["INSTAGRAM_ACCESS_TOKEN"]


def _api(method: str, endpoint: str, **kwargs) -> dict:
    url = f"{BASE_URL}/{endpoint}"
    params = {"access_token": TOKEN, **kwargs.get("params", {})}
    if method == "GET":
        resp = requests.get(url, params=params, timeout=30)
    else:
        resp = requests.post(url, params=params,
                             json=kwargs.get("json"), timeout=30)
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"Instagram API 오류: {data['error']}")
    return data


def _build_caption(slot: str, all_data: dict[str, dict]) -> str:
    """캐러셀 전체 캡션 생성"""
    sc = SLOT_CONFIG[slot]
    lines = [
        f"{sc['emoji']} {sc['label']}의 {sc['topic_ko']} 표현",
        "",
    ]
    for lang in ("en", "zh", "ja"):
        if lang not in all_data:
            continue
        lc = LANG_CONFIG[lang]
        d = all_data[lang]
        lines.append(f"{lc['flag']} {lc['name_ko']}")
        lines.append(f'"{d["main_expression"]}"')
        if lc["has_pronunciation"] and d.get("pronunciation"):
            lines.append(f"({d['pronunciation']})")
        lines.append(f"→ {d['korean_translation']}")
        lines.append("")
    lines += [
        "💾 저장하고 매일 복습해요!",
        "",
        HASHTAGS,
    ]
    return "\n".join(lines)


def _create_image_container(image_url: str, is_carousel_item: bool = True) -> str:
    """단일 이미지 컨테이너 생성 → container_id"""
    params = {
        "image_url": image_url,
        "is_carousel_item": str(is_carousel_item).lower(),
    }
    result = _api("POST", f"{IG_ID}/media", params=params)
    return result["id"]


def _create_carousel_container(child_ids: list[str], caption: str) -> str:
    """캐러셀 컨테이너 생성 → container_id"""
    params = {
        "media_type": "CAROUSEL",
        "children": ",".join(child_ids),
        "caption": caption,
    }
    result = _api("POST", f"{IG_ID}/media", params=params)
    return result["id"]


def _publish(container_id: str) -> str:
    """컨테이너 게시 → media_id"""
    result = _api("POST", f"{IG_ID}/media_publish",
                  params={"creation_id": container_id})
    return result["id"]


def _wait_ready(container_id: str, timeout: int = 120) -> None:
    """컨테이너가 FINISHED 상태가 될 때까지 대기"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = _api("GET", container_id,
                      params={"fields": "status_code"})
        status = result.get("status_code", "")
        if status == "FINISHED":
            return
        if status == "ERROR":
            raise RuntimeError(f"컨테이너 오류: {container_id}")
        time.sleep(5)
    raise TimeoutError(f"컨테이너 대기 시간 초과: {container_id}")


def post_carousel(image_urls: dict[str, str], slot: str,
                  all_data: dict[str, dict]) -> str:
    """
    언어 이미지를 포스팅 (1개면 단일 이미지, 2개+ 면 캐러셀).
    image_urls: {"en": url, ...}
    all_data:   {"en": {...}, ...}
    반환: 게시된 media_id
    """
    langs = [l for l in ("en", "zh", "ja") if l in image_urls]
    caption = _build_caption(slot, all_data)

    if len(langs) == 1:
        # 단일 이미지 포스팅
        print("  → 단일 이미지 컨테이너 생성 중...")
        params = {
            "image_url": image_urls[langs[0]],
            "caption": caption,
        }
        result = _api("POST", f"{IG_ID}/media", params=params)
        cid = result["id"]
        _wait_ready(cid)
        print("  → 게시 중...")
        media_id = _publish(cid)
    else:
        # 캐러셀 포스팅
        print("  → 이미지 컨테이너 생성 중...")
        child_ids = []
        for lang in langs:
            cid = _create_image_container(image_urls[lang])
            _wait_ready(cid)
            child_ids.append(cid)
            print(f"    ✓ {lang} 컨테이너: {cid}")

        print("  → 캐러셀 컨테이너 생성 중...")
        carousel_id = _create_carousel_container(child_ids, caption)
        print("  → 게시 중...")
        media_id = _publish(carousel_id)

    print(f"  ✓ 포스팅 완료! media_id: {media_id}")
    return media_id
