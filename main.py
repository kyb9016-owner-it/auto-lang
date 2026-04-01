"""
LangCard Studio — 메인 실행 스크립트 (HOOK 릴스)

사용법:
  python main.py --slot morning               # 영어 HOOK 릴스 포스팅
  python main.py --slot lunch                 # 중국어 HOOK 릴스 포스팅
  python main.py --slot evening               # 일본어 HOOK 릴스 포스팅
  python main.py --slot morning --dry-run     # 카드+TTS+릴스 생성만, 업로드 안 함
  python main.py --slot morning --topic cafe  # 주제 강제 지정

파이프라인:
  [1] 폰트 확인 & 다운로드
  [2] Claude API HOOK 표현 생성 (슬롯 → 1개 언어)
  [3] 카드 이미지 렌더링 (3장: hook / wrong→right / CTA)
  [4] TTS 음성 생성 (한국어 + 타겟 언어 이중 TTS)
  [5] HOOK 릴스 합성 (15초)
  [6] 전날 리캡 캐러셀 준비
  [7] Cloudinary 업로드
  [8] Instagram 포스팅 (HOOK 릴스 1개)
"""
import argparse
import json
import os
import sys
import time
from datetime import date, timedelta

from dotenv import load_dotenv
import pathlib
load_dotenv(pathlib.Path(__file__).parent / ".env", override=True)

from config import TOPIC_CONFIG, get_today_topic
import pipeline


_TOPIC_MAP = {
    "greetings": 0,
    "cafe":      1,
    "travel":    2,
    "slang":     3,
}


def run(dry_run: bool, slot: str, forced_topic=None) -> None:
    today     = date.today().strftime("%Y%m%d")
    yesterday = (date.today() - timedelta(days=1)).strftime("%Y%m%d")

    topic = forced_topic or get_today_topic()

    # ── 중복 포스팅 방지 ─────────────────────────────────────────────
    from generator.history import is_slot_posted, mark_slot_posted
    if not dry_run and is_slot_posted(today, slot):
        print(f"\n⚠ [{today}] '{slot}' 슬롯은 이미 포스팅 완료 — 건너뜁니다.")
        return

    try:
        result = pipeline.run_generation(
            slot=slot,
            today=today,
            yesterday=yesterday,
            output_dir="output",
            dry_run=dry_run,
            track_times=False,
            topic=topic,
        )
    except RuntimeError as e:
        print(f"  ✗ {e}")
        sys.exit(1)

    # ── 드라이런 종료 ────────────────────────────────────────────────
    if dry_run:
        print("\n[dry-run] 업로드 생략. 생성된 파일:")
        print(f"  HOOK 카드  : {result.hook_png}")
        print(f"  W→R 카드   : {result.wr_png}")
        print(f"  CTA 카드   : {result.cta_png}")
        print(f"  TTS        : {result.hook_tts or '없음'}")
        print(f"  HOOK 릴스  : {result.hook_reel_path}")
        if result.recap_pngs:
            print(f"  리캡 캐러셀: {len(result.recap_pngs)}장")
        print("\n완료!")
        return

    # [8] Instagram 포스팅
    print(f"\n[8/8] Instagram 포스팅")

    if result.recap_card_urls:
        try:
            pipeline.post_recap(result.recap_card_urls, topic)
            time.sleep(8)
        except Exception as e:
            print(f"  ⚠ 리캡 캐러셀 포스팅 실패 (건너뜀): {e}")

    try:
        pipeline.post_hook_reel_and_story(
            result.hook_reel_url, result.lang, result.hook_data)
    except Exception as e:
        print(f"\n✗ HOOK 릴스 포스팅 실패: {e}")
        sys.exit(1)

    print(f"\n✅ 포스팅 완료!")

    mark_slot_posted(today, slot)


def _prefetch_tomorrow(langs: list, today: str) -> None:
    """오늘 실행 성공 후 내일 표현을 미리 생성해 저장 (실패 시 무시)"""
    from datetime import date as _date
    from generator import claude_gen
    tomorrow = (_date.today() + timedelta(days=1)).strftime("%Y%m%d")
    prefetch_path = os.path.join("output", f"data_prefetch_{tomorrow}.json")
    if os.path.exists(prefetch_path):
        return

    epoch = _date(2026, 1, 1)
    tomorrow_idx   = (_date.today() + timedelta(days=1) - epoch).days % 3
    tomorrow_topic = TOPIC_CONFIG[tomorrow_idx]

    print(f"\n  [프리페치] 내일({tomorrow}) 표현 미리 생성 중...")
    prefetch_data: dict[str, dict] = {}
    for lang in langs:
        try:
            prefetch_data[lang] = claude_gen.generate(lang, tomorrow_topic)
            print(f"    ✓ {lang}")
        except Exception as e:
            print(f"    ⚠ {lang} 실패 (무시): {e}")

    if prefetch_data:
        os.makedirs("output", exist_ok=True)
        with open(prefetch_path, "w", encoding="utf-8") as f:
            json.dump({"topic": tomorrow_topic, "data": prefetch_data},
                      f, ensure_ascii=False, indent=2)
        print(f"    ✓ 저장: {prefetch_path}")


def main():
    parser = argparse.ArgumentParser(description="LangCard Studio HOOK 릴스 자동 포스팅")
    parser.add_argument(
        "--slot",
        choices=["morning", "lunch", "evening"],
        required=True,
        help="슬롯 (morning=영어, lunch=중국어, evening=일본어)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="카드+TTS+릴스 생성만, 업로드 안 함",
    )
    parser.add_argument(
        "--lang",
        default=None,
        help="(deprecated — 슬롯이 언어를 결정합니다)",
    )
    parser.add_argument(
        "--topic",
        choices=list(_TOPIC_MAP.keys()),
        default=None,
        help="주제 강제 지정 (기본: 날짜 기반 자동)",
    )
    args = parser.parse_args()

    if args.lang:
        print(f"  ⚠ --lang은 deprecated입니다. 슬롯({args.slot})이 언어를 결정합니다.")

    forced_topic = None
    if args.topic:
        forced_topic = TOPIC_CONFIG[_TOPIC_MAP[args.topic]]

    run(args.dry_run, args.slot, forced_topic)


if __name__ == "__main__":
    main()
