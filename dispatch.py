"""
LangCard Studio — Dispatch 슬롯 실행기 (main 서버용)

worker 서버에 Steps 1-7을 위임하고, 결과 URLs로 Instagram 포스팅(Step 8)을 수행.
cron 및 텔레그램 봇이 이 스크립트를 호출함.

사용법:
  python3 dispatch.py --slot morning [--dry-run]
  python3 dispatch.py --slot lunch
  python3 dispatch.py --slot evening
  python3 dispatch.py --slot morning --lang en
  python3 dispatch.py --event-topic-ko "슬랭" --event-topic-en "Slang" --event-badge "TREND" --event-emoji "🔥"
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env", override=True)

import requests

from uploader import instagram
import notify


WORKER_URL    = os.environ.get("WORKER_URL", "http://localhost:8000")
WORKER_SECRET = os.environ.get("WORKER_SECRET", "")
TIMEOUT       = 900   # 15분 (렌더링+TTS+ffmpeg 포함)

_SLOT_EMOJI = {
    "morning": "🌅",
    "lunch":   "☕",
    "evening": "✈️",
    "event":   "🎉",
}

_LANG_FLAG = {"en": "🇺🇸", "zh": "🇨🇳", "ja": "🇯🇵"}


def dispatch(slot: str | None, dry_run: bool = False,
             lang_filter: str | None = None,
             custom_topic: dict | None = None) -> dict:
    """
    worker에 작업 요청 후 Instagram 포스팅.
    Returns: worker 응답 dict
    Raises: RuntimeError on failure
    """
    label  = slot or "event"
    emoji  = _SLOT_EMOJI.get(label, "📌")
    t_start = time.time()

    # ── 중복 포스팅 방지 ─────────────────────────────────────────────
    from datetime import date as _date
    from generator.history import is_slot_posted, mark_slot_posted
    today_str = _date.today().strftime("%Y%m%d")
    post_key  = slot or "event"
    if not dry_run and is_slot_posted(today_str, post_key):
        msg = f"⚠ [{today_str}] '{post_key}' 슬롯은 이미 포스팅 완료 — 건너뜁니다."
        print(f"\n{msg}")
        notify.send(msg)
        return {"status": "skipped", "reason": "already_posted"}

    print(f"\n{emoji} {label} 슬롯 시작 (dry_run={dry_run}, lang={lang_filter or 'all'})")
    print(f"  → Worker: {WORKER_URL}/job")

    # ── [🔔 1] 시작 알림 ─────────────────────────────────────────────────────
    dry_tag = " <i>(dry-run)</i>" if dry_run else ""
    notify.send(
        f"{emoji} <b>{label} 슬롯 포스팅 시작</b>{dry_tag}\n"
        f"언어: {lang_filter or 'en · zh · ja'}"
    )

    # ── worker 호출 ──────────────────────────────────────────────────────────
    payload: dict = {"dry_run": dry_run}
    if slot and slot != "event":
        payload["slot"] = slot
    if lang_filter:
        payload["langs"] = [lang_filter]
    if custom_topic:
        payload["custom_topic"] = custom_topic

    try:
        resp = requests.post(
            f"{WORKER_URL}/job",
            json=payload,
            headers={"Authorization": f"Bearer {WORKER_SECRET}"},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.Timeout:
        msg = f"Worker 응답 시간 초과 ({TIMEOUT}초)"
        notify.send(f"❌ <b>{label} 슬롯 실패</b>\n{msg}")
        raise RuntimeError(msg)
    except requests.RequestException as e:
        msg = f"Worker 연결 실패: {e}"
        notify.send(f"❌ <b>{label} 슬롯 실패</b>\n{msg}")
        raise RuntimeError(msg)

    if data.get("status") not in ("ok", "dry_run"):
        msg = f"Worker 오류: {data}"
        notify.send(f"❌ <b>{label} 슬롯 실패</b>\n{msg}")
        raise RuntimeError(msg)

    topic        = data.get("topic", {})
    all_data     = data.get("all_data", {})
    short_reel_urls      = data.get("short_reel_urls", {})
    collection_card_urls = data.get("collection_card_urls", [])
    collection_theme     = data.get("collection_theme", {})
    tts_failed           = data.get("tts_failed", [])

    print(f"  ✓ Worker 완료: 릴스 {len(short_reel_urls)}개, "
          f"캐러셀 {len(collection_card_urls)}장")

    # TTS 실패 알림 (무음 릴스 업로드 예정임을 운영자에게 통보)
    if tts_failed:
        flags = " ".join(_LANG_FLAG.get(l, l.upper()) for l in tts_failed)
        notify.send(
            f"⚠️ <b>{label} TTS 실패 — 무음 릴스</b>\n"
            f"언어: {flags} ({', '.join(tts_failed)})\n"
            f"음성 오류 / 재시도 필요 시 /{label} 재전송"
        )

    # ── [🔔 2] Worker 완료 + 표현 미리보기 ──────────────────────────────────
    topic_text = ""
    if topic:
        t_emoji = topic.get("emoji", "")
        t_ko    = topic.get("topic_ko", "")
        topic_text = f"\n주제: {t_emoji} {t_ko}"

    expr_lines = []
    for lang in ("en", "zh", "ja"):
        if lang in all_data:
            flag = _LANG_FLAG.get(lang, "")
            expr = all_data[lang].get("main_expression", "")
            if expr:
                expr_lines.append(f"{flag} {expr}")

    expr_preview = "\n".join(expr_lines)
    notify.send(
        f"📦 <b>콘텐츠 생성 완료</b>{topic_text}\n\n"
        + (expr_preview if expr_preview else "(표현 없음)")
    )

    if dry_run:
        elapsed = int(time.time() - t_start)
        notify.send(f"✅ <b>{label} dry-run 완료</b> ({elapsed}초)")
        print(f"\n[dry-run] Instagram 포스팅 생략. 완료.")
        return data

    # ── Step 8: Instagram 포스팅 ─────────────────────────────────────────────
    print(f"\n[8] Instagram 포스팅")

    reel_count     = 0
    carousel_count = 0

    # 8-a) 컬렉션 캐러셀 — 이벤트/단일 언어는 생략
    if collection_card_urls and not custom_topic and not lang_filter:
        try:
            instagram.post_collection_carousel(collection_card_urls, collection_theme)
            carousel_count += 1
            # ── [🔔 3] 캐러셀 완료 ──────────────────────────────────────────
            theme_name = collection_theme.get("title_ko", "컬렉션")
            notify.send(f"📸 <b>컬렉션 캐러셀 업로드 완료</b> ✅\n{theme_name} ({len(collection_card_urls)}장)")
            time.sleep(8)
        except Exception as e:
            notify.send(f"⚠️ <b>컬렉션 캐러셀 실패</b> (건너뜀)\n<code>{e}</code>")
            print(f"  ⚠ 컬렉션 캐러셀 포스팅 실패 (건너뜀): {e}")

    # 8-b) 언어별 숏릴스 (en → zh → ja)
    from story_dispatcher import enqueue_story
    langs_order = [l for l in ("en", "zh", "ja") if l in short_reel_urls]
    for i, lang in enumerate(langs_order):
        flag = _LANG_FLAG.get(lang, lang.upper())
        try:
            instagram.post_short_reel(
                short_reel_urls[lang], lang, all_data[lang], topic)
            reel_count += 1
            # ── [🔔 4] 언어별 릴스 완료 ─────────────────────────────────────
            notify.send(f"🎬 <b>{flag} {lang.upper()} 릴스 업로드 완료</b> ✅")

            # 릴스 포스팅 성공 → 1시간 후 스토리 공유 예약
            try:
                enqueue_story(short_reel_urls[lang], lang, delay_hours=1.0)
            except Exception as eq_err:
                print(f"  ⚠ [{lang}] 스토리 예약 실패 (건너뜀): {eq_err}")
            if i < len(langs_order) - 1:
                time.sleep(8)
        except Exception as e:
            notify.send(f"❌ <b>{flag} {lang.upper()} 릴스 포스팅 실패</b>\n<code>{e}</code>")
            print(f"  ✗ {lang} 릴스 포스팅 실패: {e}")

    # ── [🔔 5] 전체 완료 요약 ────────────────────────────────────────────────
    elapsed = int(time.time() - t_start)
    mins, secs = divmod(elapsed, 60)
    total = reel_count + carousel_count
    notify.send(
        f"✅ <b>{label} 포스팅 완료!</b>\n"
        f"릴스 {reel_count}개"
        + (f" + 캐러셀 {carousel_count}개" if carousel_count else "")
        + f"\n소요시간: {mins}분 {secs}초"
    )

    # 포스팅 완료 기록 (중복 방지용)
    if not dry_run and total > 0:
        mark_slot_posted(today_str, post_key)

    print(f"\n✅ {label} 슬롯 완료! 총 {total}개 포스팅")
    return data


def check_health() -> dict:
    """Worker 헬스 체크"""
    try:
        resp = requests.get(
            f"{WORKER_URL}/health",
            headers={"Authorization": f"Bearer {WORKER_SECRET}"},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"status": "error", "detail": str(e)}


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LangCard 슬롯 실행기")
    parser.add_argument("--slot", choices=["morning", "lunch", "evening"],
                        help="실행할 슬롯 (이벤트 시 생략)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Worker 작업만 실행, Instagram 포스팅 생략")
    parser.add_argument("--lang", choices=["en", "zh", "ja"],
                        help="특정 언어만 처리")
    # 이벤트용
    parser.add_argument("--event-topic-ko", help="이벤트 주제 (한국어)")
    parser.add_argument("--event-topic-en", help="이벤트 주제 (영어)")
    parser.add_argument("--event-badge",    default="EVENT", help="이벤트 배지 텍스트")
    parser.add_argument("--event-emoji",    default="🎉",    help="이벤트 이모지")
    args = parser.parse_args()

    custom_topic = None
    if args.event_topic_ko and args.event_topic_en:
        custom_topic = {
            "topic_ko":   args.event_topic_ko,
            "topic_en":   args.event_topic_en,
            "badge":      args.event_badge,
            "emoji":      args.event_emoji,
            "theme_slot": "morning",
        }

    if not args.slot and not custom_topic:
        parser.error("--slot 또는 --event-topic-ko/en 중 하나는 필수입니다.")

    try:
        dispatch(args.slot, dry_run=args.dry_run,
                 lang_filter=args.lang, custom_topic=custom_topic)
    except Exception as e:
        print(f"\n✗ 실패: {e}", file=sys.stderr)
        sys.exit(1)
