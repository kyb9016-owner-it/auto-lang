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

from config import LANGUAGES, TOPIC_CONFIG, get_today_topic, SLOT_LANG_MAP
from generator import claude_gen
from renderer import card as card_renderer
from renderer import fonts as F
from renderer import reel as reel_renderer
from renderer import tts_gen
from uploader import cloudinary_up, instagram
from fetcher.unsplash import fetch_city_bg


_TOPIC_MAP = {
    "greetings": 0,
    "cafe":      1,
    "travel":    2,
    "slang":     3,
}


def run(dry_run: bool, slot: str, forced_topic=None) -> None:
    today     = date.today().strftime("%Y%m%d")
    yesterday = (date.today() - timedelta(days=1)).strftime("%Y%m%d")

    # 슬롯 → 언어 결정
    lang = SLOT_LANG_MAP[slot]
    topic = forced_topic or get_today_topic()

    # ── 중복 포스팅 방지 ─────────────────────────────────────────────
    from generator.history import is_slot_posted, mark_slot_posted
    if not dry_run and is_slot_posted(today, slot):
        print(f"\n⚠ [{today}] '{slot}' 슬롯은 이미 포스팅 완료 — 건너뜁니다.")
        return

    from config import LANG_CONFIG
    lc = LANG_CONFIG[lang]
    print(f"\n{'='*54}")
    print(f"LangCard Studio HOOK  |  {slot} → {lc['flag']} {lc['name_ko']}")
    print(f"{'='*54}")

    # [1] 폰트 준비
    print("\n[1/8] 폰트 확인 & 다운로드")
    F.ensure_fonts()

    # [2] Claude API HOOK 표현 생성
    print(f"\n[2/8] Claude API HOOK 표현 생성 ({lang})")
    try:
        hook_data = claude_gen.generate_hook(lang)
        print(f"  ✓ WRONG: {hook_data['wrong']}")
        print(f"  ✓ RIGHT: {hook_data['right']}")
    except Exception as e:
        print(f"  ✗ HOOK 생성 실패: {e}")
        sys.exit(1)

    # 오늘 데이터 저장
    data_json_path = os.path.join("output", f"data_{slot}_{today}.json")
    os.makedirs("output", exist_ok=True)
    with open(data_json_path, "w", encoding="utf-8") as f:
        json.dump({"slot": slot, "lang": lang, "data": hook_data},
                  f, ensure_ascii=False, indent=2)

    # [3] 카드 이미지 렌더링 (HOOK + WRONG→RIGHT + CTA)
    print(f"\n[3/8] 카드 이미지 렌더링 (3장)")
    os.makedirs("tmp", exist_ok=True)
    bg_path = fetch_city_bg(lang, slot)

    hook_png = card_renderer.render_hook_card(
        hook_data["hook"], lang, today, slot=slot, bg_path=bg_path)
    wr_png = card_renderer.render_wrong_right_card(
        hook_data, lang, today, slot=slot, bg_path=bg_path)
    cta_png = card_renderer.render_cta_card(
        hook_data.get("cta", "이거 몰랐으면 저장해두세요"), lang, today,
        slot=slot, bg_path=bg_path)

    # [4] TTS 음성 생성 (한국어 + 타겟 언어 이중 TTS)
    print(f"\n[4/8] TTS 음성 생성 (한국어 + {lc['name_ko']})")
    hook_tts = tts_gen.generate_hook_tts(hook_data, lang, today, slot=slot)

    # [5] HOOK 릴스 영상 합성 (15초)
    print(f"\n[5/8] HOOK 릴스 합성 (15초)")
    hook_reel_path = reel_renderer.render_hook_reel(
        hook_png, wr_png, cta_png, hook_tts, lang, today, slot=slot)

    # [6] 전날 리캡 캐러셀 (유지 — 간소화)
    print(f"\n[6/8] 전날 리캡 캐러셀 준비 (어제: {yesterday})")
    recap_pngs = []
    try:
        import glob as _glob
        yest_data_files = sorted(_glob.glob(
            os.path.join("output", f"data_*_{yesterday}.json")))
        if yest_data_files:
            for yf in yest_data_files:
                with open(yf, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                wr_card = os.path.join("output",
                    f"wrongright_{saved.get('lang', '')}_{saved.get('slot', '')}_{yesterday}.png")
                if os.path.exists(wr_card):
                    recap_pngs.append(wr_card)
            if recap_pngs:
                cover_path = card_renderer.render_recap_cover(
                    {}, topic, yesterday)
                recap_pngs.insert(0, cover_path)
                print(f"  ✓ 리캡 카드 {len(recap_pngs)}장 준비")
            else:
                print(f"  ⚠ 전날 WRONG→RIGHT 카드 없음, 리캡 건너뜀")
        else:
            print(f"  ⚠ 전날 데이터 없음, 리캡 건너뜀")
    except Exception as e:
        print(f"  ⚠ 리캡 준비 실패 (건너뜀): {e}")

    # ── 드라이런 종료 ────────────────────────────────────────────────
    if dry_run:
        print("\n[dry-run] 업로드 생략. 생성된 파일:")
        print(f"  HOOK 카드  : {hook_png}")
        print(f"  W→R 카드   : {wr_png}")
        print(f"  CTA 카드   : {cta_png}")
        print(f"  TTS        : {hook_tts or '없음'}")
        print(f"  HOOK 릴스  : {hook_reel_path}")
        if recap_pngs:
            print(f"  리캡 캐러셀: {len(recap_pngs)}장")
        print("\n완료!")
        return

    # [7] Cloudinary 업로드
    print(f"\n[7/8] Cloudinary 업로드")
    hook_reel_url = cloudinary_up.upload_video(
        hook_reel_path, f"hook_{lang}", today)

    recap_card_urls = []
    if recap_pngs:
        try:
            for i, png in enumerate(recap_pngs):
                url = cloudinary_up.upload(
                    png, lang, "recap", suffix=f"hook_{i}", date_str=yesterday)
                recap_card_urls.append(url)
        except Exception as e:
            print(f"  ⚠ 리캡 업로드 실패 (건너뜀): {e}")
            recap_card_urls = []

    # [8] Instagram 포스팅
    print(f"\n[8/8] Instagram 포스팅")

    if recap_card_urls:
        try:
            instagram.post_recap_carousel(recap_card_urls, topic, {})
            time.sleep(8)
        except Exception as e:
            print(f"  ⚠ 리캡 캐러셀 포스팅 실패 (건너뜀): {e}")

    try:
        instagram.post_hook_reel(hook_reel_url, lang, hook_data)
        from story_dispatcher import enqueue_story
        try:
            enqueue_story(hook_reel_url, lang, delay_hours=1.0)
        except Exception as eq_err:
            print(f"  ⚠ 스토리 예약 실패 (건너뜀): {eq_err}")
    except Exception as e:
        print(f"\n✗ HOOK 릴스 포스팅 실패: {e}")
        sys.exit(1)

    print(f"\n✅ 포스팅 완료!")

    if not dry_run:
        mark_slot_posted(today, slot)


def _prefetch_tomorrow(langs: list, today: str) -> None:
    """오늘 실행 성공 후 내일 표현을 미리 생성해 저장 (실패 시 무시)"""
    from datetime import date as _date
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
