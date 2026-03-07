"""Instagram Graph API — 릴스 및 캐러셀 포스팅"""
import os
import time
from datetime import datetime, timezone, timedelta
import requests
from config import LANG_CONFIG, SLOT_CONFIG, HASHTAGS, LANG_HASHTAGS

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


# ── 캡션 빌더 ────────────────────────────────────────────────────────────────

_TOPIC_HOOK = {
    "GREETINGS": {
        "en": "처음 만나는 순간, 영어로는 이렇게 말해요 👋\n소리 켜고 들어봐요 🔊",
        "zh": "처음 만나는 순간, 중국어로는 이렇게 말해요 👋\n소리 켜고 들어봐요 🔊",
        "ja": "처음 만나는 순간, 일본어로는 이렇게 말해요 👋\n소리 켜고 들어봐요 🔊",
    },
    "CAFE": {
        "en": "카페·식당에서 꼭 쓰는 영어 표현 ☕\n소리 켜고 들어봐요 🔊",
        "zh": "카페·식당에서 꼭 쓰는 중국어 표현 ☕\n소리 켜고 들어봐요 🔊",
        "ja": "카페·식당에서 꼭 쓰는 일본어 표현 ☕\n소리 켜고 들어봐요 🔊",
    },
    "TRAVEL": {
        "en": "여행·쇼핑할 때 영어로는 이렇게 말해요 ✈️\n소리 켜고 들어봐요 🔊",
        "zh": "여행·쇼핑할 때 중국어로는 이렇게 말해요 ✈️\n소리 켜고 들어봐요 🔊",
        "ja": "여행·쇼핑할 때 일본어로는 이렇게 말해요 ✈️\n소리 켜고 들어봐요 🔊",
    },
}

_RECAP_HOOK = {
    "GREETINGS": "어제의 인사 표현 3개국어 버전 🤝 소리 켜고 들어봐요 🔊",
    "CAFE":      "어제의 카페·식당 표현 3개국어 복습 ☕ 소리 켜고 들어봐요 🔊",
    "TRAVEL":    "어제의 여행·쇼핑 표현 3개국어 총정리 ✈️ 소리 켜고 들어봐요 🔊",
}

_RECAP_CAROUSEL_HOOK = {
    "GREETINGS": "어제의 인사 표현 3개국어로 복습해요 🤝\n스와이프해서 확인하세요 👉",
    "CAFE":      "어제의 카페·식당 표현 3개국어로 복습해요 ☕\n스와이프해서 확인하세요 👉",
    "TRAVEL":    "어제의 여행·쇼핑 표현 3개국어로 복습해요 ✈️\n스와이프해서 확인하세요 👉",
}


def _build_short_reel_caption(lang: str, data: dict, topic: dict) -> str:
    """언어별 숏릴스 캡션 (표현 + 단어 정보 포함)"""
    lc     = LANG_CONFIG[lang]
    badge  = topic.get("badge", "GREETINGS") if isinstance(topic, dict) else "GREETINGS"
    hook   = _TOPIC_HOOK.get(badge, {}).get(lang,
             f"{lc['flag']} {lc['name_ko']} 오늘의 표현 🔊\n소리 켜고 들어봐요 🔊")

    phonetic = data.get("korean_phonetic", "")
    pron     = data.get("pronunciation", "")
    lc_has_pron = lc["has_pronunciation"]

    lines = [
        hook,
        "",
        f"{lc['flag']} {lc['name_ko']} 오늘의 표현",
        f'"{data["main_expression"]}"',
    ]
    if phonetic:
        lines.append(f"🔊 {phonetic}")
    if lc_has_pron and pron:
        lines.append(f"({pron})")
    lines += [
        f"→ {data['korean_translation']}",
        "",
    ]

    # 단어 미리보기
    vocab = data.get("vocab", [])
    if vocab:
        lines.append("📖 오늘의 단어")
        for item in vocab[:3]:
            word = item.get("word", "")
            meaning = item.get("meaning", "")
            kp = item.get("korean_phonetic", "")
            word_pron = item.get("pronunciation", "")
            entry = f"• {word}"
            if lc_has_pron and word_pron:
                entry += f" ({word_pron})"
            if kp:
                entry += f" [{kp}]"
            entry += f"  →  {meaning}"
            lines.append(entry)
        lines.append("")

    lines += [
        "이 표현 써본 적 있나요? 댓글로 알려주세요 💬",
        "💾 저장해두고 오늘 꼭 한 번 써보세요!",
        "",
        LANG_HASHTAGS.get(lang, HASHTAGS),
    ]
    return "\n".join(lines)


def _build_recap_carousel_caption(topic: dict, all_data: dict[str, dict]) -> str:
    """종합 캐러셀 캡션 (스와이프 유도, 오디오 문구 없음)"""
    badge = topic.get("badge", "GREETINGS") if isinstance(topic, dict) else "GREETINGS"
    hook  = _RECAP_CAROUSEL_HOOK.get(badge, "어제의 3개국어 표현 복습 📖\n스와이프해서 확인하세요 👉")

    lines = [hook, ""]
    for lang in ("en", "zh", "ja"):
        if lang not in all_data:
            continue
        lc = LANG_CONFIG[lang]
        d  = all_data[lang]
        lines.append(f"{lc['flag']} {lc['name_ko']}")
        lines.append(f'"{d["main_expression"]}"')
        phonetic = d.get("korean_phonetic", "")
        if phonetic:
            lines.append(f"🔊 {phonetic}")
        if lc["has_pronunciation"] and d.get("pronunciation"):
            lines.append(f"({d['pronunciation']})")
        lines.append(f"→ {d['korean_translation']}")
        lines.append("")

    lines += [
        "어떤 표현이 제일 기억에 남았나요? 댓글로 알려주세요 💬",
        "💾 저장해두고 오늘도 써봐요!",
        "",
        HASHTAGS,
    ]
    return "\n".join(lines)


def _build_recap_reel_caption(topic: dict, all_data: dict[str, dict]) -> str:
    """종합 릴스 캡션 (3개국어 표현 요약)"""
    badge = topic.get("badge", "GREETINGS") if isinstance(topic, dict) else "GREETINGS"
    hook  = _RECAP_HOOK.get(badge, "어제의 3개국어 표현 복습 🎬 소리 켜고 들어봐요 🔊")

    lines = [hook, ""]
    for lang in ("en", "zh", "ja"):
        if lang not in all_data:
            continue
        lc = LANG_CONFIG[lang]
        d  = all_data[lang]
        lines.append(f"{lc['flag']} {lc['name_ko']}")
        lines.append(f'"{d["main_expression"]}"')
        phonetic = d.get("korean_phonetic", "")
        if phonetic:
            lines.append(f"🔊 {phonetic}")
        if lc["has_pronunciation"] and d.get("pronunciation"):
            lines.append(f"({d['pronunciation']})")
        lines.append(f"→ {d['korean_translation']}")
        lines.append("")

    lines += [
        "어떤 언어가 제일 어렵게 느껴지나요? 💬",
        "💾 저장해두고 오늘도 복습해봐요!",
        "",
        HASHTAGS,
    ]
    return "\n".join(lines)


# ── API 헬퍼 ─────────────────────────────────────────────────────────────────

def _create_image_container(image_url: str, is_carousel_item: bool = True,
                            retries: int = 4, delay: int = 8) -> str:
    """단일 이미지 컨테이너 생성 → container_id"""
    params = {
        "image_url": image_url,
        "is_carousel_item": str(is_carousel_item).lower(),
    }
    for attempt in range(1, retries + 1):
        try:
            result = _api("POST", f"{IG_ID}/media", params=params)
            return result["id"]
        except RuntimeError as e:
            if attempt == retries:
                raise
            print(f"    ⚠ 컨테이너 생성 실패 (시도 {attempt}/{retries}), {delay}초 후 재시도...")
            time.sleep(delay)
            delay *= 2
    raise RuntimeError("컨테이너 생성 최대 재시도 초과")


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


# ── 포스팅 함수 ──────────────────────────────────────────────────────────────

def post_short_reel(video_url: str, lang: str,
                    data: dict, topic: dict) -> str:
    """
    언어별 숏릴스 포스팅 (TTS 음성 포함 ~7초 영상)
    Returns: media_id
    """
    lc = LANG_CONFIG[lang]
    caption = _build_short_reel_caption(lang, data, topic)

    print(f"  → {lc['name_ko']} 숏릴스 컨테이너 생성 중... (영상 처리 중)")
    result = _api("POST", f"{IG_ID}/media", params={
        "video_url": video_url,
        "media_type": "REELS",
        "caption": caption,
        "share_to_feed": "true",
    })
    cid = result["id"]
    _wait_ready(cid, timeout=300)
    print(f"  → {lc['name_ko']} 숏릴스 게시 중...")
    media_id = _publish(cid)
    print(f"  ✓ {lc['name_ko']} 숏릴스 완료! media_id: {media_id}")
    return media_id


def post_recap_carousel(image_urls: list, topic: dict,
                        all_data: dict) -> str:
    """
    어제 카드 6장을 일반 캐러셀 게시물로 포스팅.
    image_urls: [en_expr, en_vocab, zh_expr, zh_vocab, ja_expr, ja_vocab] 순서
    Returns: media_id
    """
    caption = _build_recap_carousel_caption(topic, all_data)

    print("  → 종합 캐러셀 이미지 컨테이너 생성 중...")
    child_ids = []
    for i, url in enumerate(image_urls):
        if i > 0:
            time.sleep(3)
        cid = _create_image_container(url, is_carousel_item=True)
        _wait_ready(cid)
        child_ids.append(cid)
        print(f"    ✓ 슬라이드 {i+1}/{len(image_urls)} 준비")

    print("  → 종합 캐러셀 컨테이너 생성 중...")
    carousel_id = _create_carousel_container(child_ids, caption)
    _wait_ready(carousel_id)
    print("  → 종합 캐러셀 게시 중...")
    media_id = _publish(carousel_id)
    print(f"  ✓ 종합 캐러셀 완료! media_id: {media_id}")
    return media_id


def post_recap_reel(video_url: str, topic: dict,
                    all_data: dict[str, dict]) -> str:
    """
    종합 릴스 포스팅 (전날 6장 카드 + TTS)
    Returns: media_id
    """
    caption = _build_recap_reel_caption(topic, all_data)

    print("  → 종합 릴스 컨테이너 생성 중... (영상 처리 중)")
    result = _api("POST", f"{IG_ID}/media", params={
        "video_url": video_url,
        "media_type": "REELS",
        "caption": caption,
        "share_to_feed": "true",
    })
    cid = result["id"]
    _wait_ready(cid, timeout=300)
    print("  → 종합 릴스 게시 중...")
    media_id = _publish(cid)
    print(f"  ✓ 종합 릴스 완료! media_id: {media_id}")
    return media_id


# ── 하위 호환 함수 (기존 코드 참조 대비) ────────────────────────────────────

def post_story(image_url: str) -> str:
    """스토리 이미지 포스팅 → media_id"""
    print("  → 스토리 컨테이너 생성 중...")
    result = _api("POST", f"{IG_ID}/media",
                  params={"image_url": image_url, "media_type": "STORIES"})
    cid = result["id"]
    _wait_ready(cid)
    print("  → 스토리 게시 중...")
    media_id = _publish(cid)
    print(f"  ✓ 스토리 완료! media_id: {media_id}")
    return media_id


def post_reel(video_url: str, slot: str, all_data: dict[str, dict]) -> str:
    """하위 호환용 릴스 포스팅 (slot str 기반)"""
    sc = SLOT_CONFIG[slot]
    reel_hook = {
        "morning": "같은 상황, 3개국어로는 어떻게 다를까? 🤝",
        "lunch":   "카페·식당 표현, 3개국어로 비교해봤어요 ☕",
        "evening": "여행·쇼핑할 때 쓰는 표현 3개국어 버전 ✈️",
    }
    caption = (
        f"{reel_hook.get(slot, '3개국어 표현 모아보기 🎬')}\n\n"
        f"영어 · 중국어 · 일본어\n"
        f"오늘의 표현 + 핵심 단어까지 한 번에!\n\n"
        f"어떤 언어가 제일 어렵게 느껴지나요? 💬\n\n"
        f"{HASHTAGS}"
    )
    print("  → 릴스 컨테이너 생성 중... (영상 처리 시간 소요)")
    result = _api("POST", f"{IG_ID}/media", params={
        "video_url": video_url,
        "media_type": "REELS",
        "caption": caption,
        "share_to_feed": "true",
    })
    cid = result["id"]
    _wait_ready(cid, timeout=300)
    print("  → 릴스 게시 중...")
    media_id = _publish(cid)
    print(f"  ✓ 릴스 완료! media_id: {media_id}")
    return media_id


# ── 분석 함수 ─────────────────────────────────────────────────────────────────

def get_recent_media(limit: int = 30) -> list[dict]:
    """최근 미디어 목록 (id, timestamp, media_type, media_product_type, like_count, comments_count)"""
    data = _api("GET", f"{IG_ID}/media", params={
        "fields": "id,timestamp,media_type,media_product_type,like_count,comments_count",
        "limit": limit,
    })
    return data.get("data", [])


def get_media_insights(media_id: str, media_type: str = "",
                       media_product_type: str = "") -> dict:
    """
    특정 미디어 인사이트 조회. 폴백 포함:
      REELS → plays 우선, 실패 시 impressions
      그 외  → impressions 우선, 실패 시 plays
    에러 시 {"_error": str} 반환.
    """
    is_reel = media_product_type == "REELS"
    # REELS: plays 우선 / 그 외: impressions 우선, 실패 시 교차 재시도
    metric_order = (
        ["plays,reach,saved", "impressions,reach,saved"] if is_reel
        else ["impressions,reach,saved", "plays,reach,saved"]
    )

    def _parse(raw: list) -> dict:
        out = {}
        for item in raw:
            name = item["name"]
            val = item.get("value")
            if val is None and item.get("values"):
                val = item["values"][0].get("value", 0)
            out[name] = val or 0
        # plays → impressions 키 통일
        if "plays" in out and "impressions" not in out:
            out["impressions"] = out["plays"]
        return out

    last_err = "알 수 없는 오류"
    for metrics in metric_order:
        try:
            data = _api("GET", f"{media_id}/insights", params={
                "metric": metrics,
                "period": "lifetime",
            })
            return _parse(data.get("data", []))
        except Exception as e:
            last_err = str(e)
            continue  # 다음 메트릭 세트 시도

    return {"_error": last_err}


def get_analytics(limit: int = 30) -> dict:
    """
    최근 포스팅 분석 종합 (시간대·슬롯별 집계 포함).

    슬롯 분류 (KST 기준):
      morning: 05~10시, lunch: 11~14시, evening: 17~22시, other: 나머지

    Returns:
      {total, posts, by_slot, best_slot, best_hour, top_hours}
    """
    KST = timezone(timedelta(hours=9))
    _SLOT_RANGES = {
        "morning": range(5, 11),
        "lunch":   range(11, 15),
        "evening": range(17, 23),
    }

    def _classify_slot(kst_hour: int) -> str:
        for slot, rng in _SLOT_RANGES.items():
            if kst_hour in rng:
                return slot
        return "other"

    media_list = get_recent_media(limit)

    posts  = []
    errors: list[str] = []
    slot_stats: dict[str, list] = {"morning": [], "lunch": [], "evening": [], "other": []}
    hour_stats: dict[int, list] = {}

    for m in media_list:
        media_id           = m["id"]
        ts                 = m.get("timestamp", "")
        media_type         = m.get("media_type", "")
        media_product_type = m.get("media_product_type", "")  # REELS / POST / AD

        # KST 변환
        try:
            dt_utc   = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            dt_kst   = dt_utc.astimezone(KST)
            kst_hour = dt_kst.hour
            ts_label = dt_kst.strftime("%Y-%m-%d %H:%M KST")
        except Exception:
            dt_kst   = None
            kst_hour = -1
            ts_label = ts

        # 인사이트 조회 (media_product_type으로 Reels 여부 판단)
        insights = get_media_insights(media_id, media_type, media_product_type)
        err_msg  = insights.pop("_error", None)
        if err_msg and len(errors) < 3:
            errors.append(f"{media_id}: {err_msg}")

        impressions = insights.get("impressions", 0)
        reach       = insights.get("reach", 0)
        video_views = insights.get("plays", insights.get("video_views", 0))
        saved       = insights.get("saved", 0)
        likes       = m.get("like_count", 0) or 0
        comments    = m.get("comments_count", 0) or 0
        engagement  = likes + comments + saved

        slot = _classify_slot(kst_hour)

        post = {
            "id":          media_id,
            "timestamp":   ts_label,
            "kst_hour":    kst_hour,
            "slot":        slot,
            "media_type":  media_type,
            "impressions": impressions,
            "reach":       reach,
            "video_views": video_views,
            "saved":       saved,
            "likes":       likes,
            "comments":    comments,
            "engagement":  engagement,
        }
        posts.append(post)
        slot_stats[slot].append(post)
        if kst_hour >= 0:
            hour_stats.setdefault(kst_hour, []).append(post)

    # 슬롯별 평균 계산
    def _avg(plist: list, key: str) -> float:
        return sum(p[key] for p in plist) / len(plist) if plist else 0.0

    by_slot: dict = {}
    for slot, sp in slot_stats.items():
        if not sp:
            continue
        by_slot[slot] = {
            "count":       len(sp),
            "impressions": round(_avg(sp, "impressions")),
            "reach":       round(_avg(sp, "reach")),
            "video_views": round(_avg(sp, "video_views")),
            "engagement":  round(_avg(sp, "engagement")),
        }

    # 최고 슬롯 (impressions 기준)
    best_slot = max(by_slot, key=lambda s: by_slot[s]["impressions"]) if by_slot else None

    # 시간대별 상위 3개
    hour_avgs = {
        h: round(sum(p["impressions"] for p in hp) / len(hp))
        for h, hp in hour_stats.items() if hp
    }
    top_hours = sorted(hour_avgs.items(), key=lambda x: x[1], reverse=True)[:3]
    best_hour = top_hours[0][0] if top_hours else None

    return {
        "total":     len(posts),
        "posts":     posts,
        "by_slot":   by_slot,
        "best_slot": best_slot,
        "best_hour": best_hour,
        "top_hours": top_hours,
        "errors":    errors,   # API 오류 메시지 (최대 3개)
    }


# ── 하위 호환 함수 (기존 코드 참조 대비) ────────────────────────────────────

def post_carousel(image_urls: dict[str, str], slot: str,
                  all_data: dict[str, dict], is_vocab: bool = False) -> str:
    """하위 호환용 캐러셀 포스팅"""
    from config import SLOT_CONFIG as SC
    _EXPR_HOOK = {
        "morning": "오늘 처음 만나는 사람한테 뭐라고 할 것 같아요? 👀\n3개국어로 배워봐요 👇",
        "lunch":   "카페·식당에서 꼭 쓰는 그 표현 ☕\n3개국어로는 이렇게 말해요 👇",
        "evening": "여행·쇼핑할 때 이 말 몰라서 당황한 적 있나요? ✈️\n오늘 바로 외워가세요 👇",
    }
    _VOCAB_HOOK = {
        "morning": "오늘의 인사 핵심 단어, 3개국어로 한 번에 📖\n스와이프해서 확인하세요 👉",
        "lunch":   "카페·식당에서 바로 쓸 수 있는 단어 모음 ☕📖\n스와이프해서 확인하세요 👉",
        "evening": "여행·쇼핑 필수 어휘 3개국어로 총정리 ✈️📖\n스와이프해서 확인하세요 👉",
    }
    sc = SC[slot]
    if is_vocab:
        lines = [_VOCAB_HOOK.get(slot, f"📖 {sc['label']}의 {sc['topic_ko']} 단어"), ""]
        for lang in ("en", "zh", "ja"):
            if lang not in all_data: continue
            lc = LANG_CONFIG[lang]
            vocab = all_data[lang].get("vocab", [])
            lines.append(f"{lc['flag']} {lc['name_ko']}")
            for item in vocab:
                pron = f" ({item['pronunciation']})" if lc["has_pronunciation"] and item.get("pronunciation") else ""
                lines.append(f"  • {item['word']}{pron}  →  {item['meaning']}")
            lines.append("")
        lines += ["어떤 단어가 제일 낯설었나요? 댓글로 알려주세요 💬",
                  "💾 저장해두고 오늘 한 번 써보세요!", "", HASHTAGS]
    else:
        lines = [_EXPR_HOOK.get(slot, f"{sc['emoji']} {sc['label']}의 {sc['topic_ko']} 표현"), ""]
        for lang in ("en", "zh", "ja"):
            if lang not in all_data: continue
            lc = LANG_CONFIG[lang]
            d = all_data[lang]
            lines.append(f"{lc['flag']} {lc['name_ko']}")
            lines.append(f'"{d["main_expression"]}"')
            if lc["has_pronunciation"] and d.get("pronunciation"):
                lines.append(f"({d['pronunciation']})")
            lines.append(f"→ {d['korean_translation']}")
            lines.append("")
        lines += ["가장 배우고 싶은 언어가 뭔가요? 댓글로 알려주세요 💬",
                  "💾 저장해두고 오늘 꼭 한 번 써보세요!", "", HASHTAGS]
    caption = "\n".join(lines)

    langs = [l for l in ("en", "zh", "ja") if l in image_urls]
    if len(langs) == 1:
        params = {"image_url": image_urls[langs[0]], "caption": caption}
        result = _api("POST", f"{IG_ID}/media", params=params)
        cid = result["id"]
        _wait_ready(cid)
        media_id = _publish(cid)
    else:
        child_ids = []
        for i, lang in enumerate(langs):
            if i > 0:
                time.sleep(3)
            cid = _create_image_container(image_urls[lang])
            _wait_ready(cid)
            child_ids.append(cid)
        carousel_id = _create_carousel_container(child_ids, caption)
        _wait_ready(carousel_id)
        media_id = _publish(carousel_id)
    print(f"  ✓ 포스팅 완료! media_id: {media_id}")
    return media_id
