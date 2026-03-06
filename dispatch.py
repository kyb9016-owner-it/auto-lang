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


WORKER_URL    = os.environ.get("WORKER_URL", "http://localhost:8000")
WORKER_SECRET = os.environ.get("WORKER_SECRET", "")
TIMEOUT       = 600   # 10분 (렌더링+TTS+ffmpeg 포함)

_SLOT_EMOJI = {
    "morning": "🌅",
    "lunch":   "☕",
    "evening": "✈️",
    "event":   "🎉",
}


def dispatch(slot: str | None, dry_run: bool = False,
             lang_filter: str | None = None,
             custom_topic: dict | None = None) -> dict:
    """
    worker에 작업 요청 후 Instagram 포스팅.
    Returns: worker 응답 dict
    Raises: RuntimeError on failure
    """
    label = slot or "event"
    emoji = _SLOT_EMOJI.get(label, "📌")
    print(f"\n{emoji} {label} 슬롯 시작 (dry_run={dry_run}, lang={lang_filter or 'all'})")
    print(f"  → Worker: {WORKER_URL}/job")

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
        raise RuntimeError(f"Worker 응답 시간 초과 ({TIMEOUT}초)")
    except requests.RequestException as e:
        raise RuntimeError(f"Worker 연결 실패: {e}")

    if data.get("status") not in ("ok", "dry_run"):
        raise RuntimeError(f"Worker 오류: {data}")

    print(f"  ✓ Worker 완료: 릴스 {len(data.get('short_reel_urls', {}))}개, "
          f"캐러셀 {len(data.get('recap_card_urls', []))}장")

    if dry_run:
        print(f"\n[dry-run] Instagram 포스팅 생략. 완료.")
        return data

    # ── Step 8: Instagram 포스팅 ─────────────────────────────────────────────
    print(f"\n[8] Instagram 포스팅")
    topic    = data["topic"]
    all_data = data["all_data"]
    short_reel_urls  = data.get("short_reel_urls", {})
    recap_card_urls  = data.get("recap_card_urls", [])

    # 8-a) 종합 캐러셀 (전날 복습) — 이벤트/단일 언어는 생략
    if recap_card_urls and not custom_topic and not lang_filter:
        try:
            instagram.post_recap_carousel(recap_card_urls, topic, all_data)
            time.sleep(8)
        except Exception as e:
            print(f"  ⚠ 종합 캐러셀 포스팅 실패 (건너뜀): {e}")

    # 8-b) 언어별 숏릴스 (en → zh → ja)
    langs_order = [l for l in ("en", "zh", "ja") if l in short_reel_urls]
    for i, lang in enumerate(langs_order):
        try:
            instagram.post_short_reel(
                short_reel_urls[lang], lang, all_data[lang], topic)
            if i < len(langs_order) - 1:
                time.sleep(8)
        except Exception as e:
            print(f"  ✗ {lang} 릴스 포스팅 실패: {e}")

    total = len(langs_order) + (1 if recap_card_urls and not custom_topic and not lang_filter else 0)
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
