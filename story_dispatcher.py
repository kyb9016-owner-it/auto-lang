#!/usr/bin/env python3
"""
스토리 큐 처리기 — 릴스 포스팅 1시간 후 자동 스토리 공유

큐 파일: output/story_queue.json
  [
    {
      "video_url": "https://res.cloudinary.com/.../short_en_20260307.mp4",
      "lang": "en",
      "post_after": "2026-03-07T00:00:00+00:00",
      "posted": false
    },
    ...
  ]

크론: */5 * * * * cd /opt/auto-lang && python3 story_dispatcher.py >> /var/log/langcard/story.log 2>&1
"""
import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

QUEUE_FILE = os.path.join(ROOT, "output", "story_queue.json")
MAX_KEEP   = 200   # 큐 파일에 보관할 최대 항목 수 (오래된 completed 항목 정리)


def enqueue_story(video_url: str, lang: str, delay_hours: float = 1.0) -> None:
    """
    릴스 Cloudinary URL을 스토리 큐에 추가.
    dispatch.py / main.py에서 릴스 포스팅 직후 호출.
    """
    from datetime import timedelta
    post_after = datetime.now(timezone.utc) + timedelta(hours=delay_hours)

    os.makedirs(os.path.dirname(QUEUE_FILE), exist_ok=True)
    queue = _load_queue()

    queue.append({
        "video_url":  video_url,
        "lang":       lang,
        "post_after": post_after.isoformat(),
        "posted":     False,
    })

    _save_queue(queue)
    kst_str = (post_after.astimezone(
        __import__("datetime").timezone(__import__("datetime").timedelta(hours=9))
    )).strftime("%H:%M KST")
    print(f"  📅 스토리 예약: [{lang}] {kst_str} 공유 예정")


def _load_queue() -> list:
    if not os.path.exists(QUEUE_FILE):
        return []
    try:
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_queue(queue: list) -> None:
    # 오래된 posted 항목 정리 (MAX_KEEP 초과 시)
    posted   = [q for q in queue if q.get("posted")]
    pending  = [q for q in queue if not q.get("posted")]
    keep_old = max(0, MAX_KEEP - len(pending))
    queue    = pending + posted[-keep_old:]

    os.makedirs(os.path.dirname(QUEUE_FILE), exist_ok=True)
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)


def run() -> None:
    """큐를 읽어 예약 시각이 된 스토리를 게시."""
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))

    queue = _load_queue()
    if not queue:
        return

    now     = datetime.now(timezone.utc)
    changed = False

    for item in queue:
        if item.get("posted"):
            continue

        try:
            post_after = datetime.fromisoformat(item["post_after"])
        except Exception:
            continue

        if now < post_after:
            continue   # 아직 시간이 안 됨

        lang      = item.get("lang", "?")
        video_url = item.get("video_url", "")
        if not video_url:
            item["posted"] = True  # URL 없으면 건너뜀
            changed = True
            continue

        print(f"\n[스토리 공유] {lang} 릴스 → 스토리")
        try:
            from uploader.instagram import post_video_story
            media_id = post_video_story(video_url)
            item["posted"]          = True
            item["posted_at"]       = now.isoformat()
            item["story_media_id"]  = media_id
            changed = True
            print(f"  ✓ [{lang}] 스토리 공유 완료: {media_id}")
        except Exception as e:
            # 실패 시 재시도 횟수 기록 (3회 초과 시 포기)
            item["retry_count"] = item.get("retry_count", 0) + 1
            if item["retry_count"] >= 3:
                item["posted"]   = True   # 포기
                item["error"]    = str(e)
                changed = True
                print(f"  ✗ [{lang}] 스토리 3회 실패, 포기: {e}")
            else:
                print(f"  ⚠ [{lang}] 스토리 실패 ({item['retry_count']}/3), 다음에 재시도: {e}")

    if changed:
        _save_queue(queue)


if __name__ == "__main__":
    run()
