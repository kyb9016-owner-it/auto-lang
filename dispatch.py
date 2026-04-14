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

import pipeline
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


_ALL_LANGS = ["en", "zh", "ja"]


def dispatch(slot: str | None, dry_run: bool = False,
             lang_filter: str | None = None,
             custom_topic: dict | None = None) -> dict:
    """
    worker에 3개국어 작업 요청 후 Instagram 포스팅.
    - 슬롯당 en/zh/ja 릴스 3개 순차 포스팅
    - 리캡 캐러셀은 하루 1번만 (최초 슬롯에서 1회)
    Returns: 결과 dict
    """
    label   = slot or "event"
    emoji   = _SLOT_EMOJI.get(label, "📌")
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

    langs_to_run = [lang_filter] if lang_filter else _ALL_LANGS
    dry_tag = " <i>(dry-run)</i>" if dry_run else ""
    print(f"\n{emoji} {label} 슬롯 시작 (dry_run={dry_run}, langs={langs_to_run})")
    notify.send(
        f"{emoji} <b>{label} 슬롯 포스팅 시작</b>{dry_tag}\n"
        f"언어: {' · '.join(langs_to_run)}"
    )

    reel_count          = 0
    carousel_count      = 0
    last_data: dict     = {}
    recap_posted        = False   # 한 실행 내에서 recap 중복 방지

    for lang in langs_to_run:
        flag = _LANG_FLAG.get(lang, lang)
        print(f"\n  → {flag} {lang} Worker 호출")

        payload: dict = {"dry_run": dry_run, "langs": [lang]}
        if slot and slot != "event":
            payload["slot"] = slot
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
            notify.send(f"❌ {flag} Worker 응답 시간 초과 — 건너뜁니다.")
            continue
        except requests.RequestException as e:
            notify.send(f"❌ {flag} Worker 연결 실패: {e}")
            continue

        if data.get("status") not in ("ok", "dry_run"):
            notify.send(f"❌ {flag} Worker 오류: {data}")
            continue

        last_data = data
        hook_data       = data.get("hook_data", {})
        hook_reel_url   = data.get("hook_reel_url")
        recap_card_urls = data.get("recap_card_urls", [])
        vocab_card_urls = data.get("vocab_card_urls", [])

        wrong = hook_data.get("wrong", "")
        right = hook_data.get("right", "")
        print(f"  ✓ {flag} Worker 완료: HOOK 릴스 1개"
              + (f", 리캡 {len(recap_card_urls)}장" if recap_card_urls else ""))
        notify.send(f"📦 {flag} <b>HOOK 생성 완료</b>\n\n{flag} ❌ {wrong}\n{flag} ✅ {right}")

        if dry_run:
            continue

        # ── 리캡 캐러셀 (하루 1번만) ──────────────────────────────────
        if recap_card_urls and not recap_posted and not is_slot_posted(today_str, "recap"):
            try:
                pipeline.post_recap(recap_card_urls)
                recap_posted = True
                carousel_count += 1
                mark_slot_posted(today_str, "recap")
                notify.send(f"📸 <b>리캡 캐러셀 업로드 완료</b> ✅ ({len(recap_card_urls)}장)")
                time.sleep(8)
            except Exception as e:
                notify.send(f"⚠️ <b>리캡 캐러셀 실패</b> (건너뜀)\n<code>{e}</code>")

        # ── HOOK 릴스 ────────────────────────────────────────────────
        if hook_reel_url:
            try:
                pipeline.post_hook_reel_and_story(hook_reel_url, lang, hook_data)
                reel_count += 1
                notify.send(f"🎬 <b>{flag} HOOK 릴스 업로드 완료</b> ✅")
            except Exception as e:
                notify.send(f"❌ <b>{flag} HOOK 릴스 포스팅 실패</b>\n<code>{e}</code>")
                print(f"  ✗ {flag} 릴스 포스팅 실패: {e}")

        # ── 단어 캐러셀 ──────────────────────────────────────────────
        if vocab_card_urls:
            try:
                time.sleep(5)
                instagram.post_vocab_carousel(vocab_card_urls, lang, hook_data)
                notify.send(f"📖 <b>{flag} 단어 캐러셀 업로드 완료</b> ✅ ({len(vocab_card_urls)}장)")
            except Exception as e:
                notify.send(f"⚠️ <b>{flag} 단어 캐러셀 실패</b> (건너뜀)\n<code>{e}</code>")
                print(f"  ⚠ {flag} 단어 캐러셀 실패: {e}")

        if len(langs_to_run) > 1:
            time.sleep(30)   # Instagram API rate limit 여유

    if dry_run:
        elapsed = int(time.time() - t_start)
        notify.send(f"✅ <b>{label} dry-run 완료</b> ({elapsed}초)")
        print(f"\n[dry-run] 완료.")
        return last_data or {}

    # ── 완료 요약 ────────────────────────────────────────────────────
    elapsed = int(time.time() - t_start)
    mins, secs = divmod(elapsed, 60)
    notify.send(
        f"✅ <b>{label} 포스팅 완료!</b>\n"
        f"릴스 {reel_count}개"
        + (f" + 리캡 {carousel_count}개" if carousel_count else "")
        + f"\n소요시간: {mins}분 {secs}초"
    )

    # 릴스가 1개 이상 성공해야만 완료 처리
    if reel_count > 0:
        mark_slot_posted(today_str, post_key)

    print(f"\n✅ {label} 슬롯 완료! 릴스 {reel_count}개 포스팅")
    return last_data or {}


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
