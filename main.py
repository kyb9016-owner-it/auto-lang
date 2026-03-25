"""
LangCard Studio — 메인 실행 스크립트

사용법:
  python main.py                    # 전체 파이프라인 (오늘 주제 자동 결정)
  python main.py --dry-run          # 카드+TTS+릴스 생성만, 업로드 안 함
  python main.py --lang en          # 특정 언어만
  python main.py --topic cafe       # 주제 강제 지정 (greetings|cafe|travel)

파이프라인:
  [1] 오늘 주제 결정 (일별 자동 순환)
  [2] Claude API 표현 생성 (3개 언어 × 한글 음차 포함)
  [3] 카드 이미지 렌더링 (6장: en/zh/ja × 표현/단어)
  [4] TTS 음성 생성 (6개 mp3: expr×3 + vocab×3)
  [5] 언어별 숏릴스 생성 (3개 MP4, ~7초, TTS 포함)
  [6] 종합 릴스 생성 (전날 카드 6장 + TTS, ~20초)
  [7] Cloudinary 업로드
  [8] Instagram 포스팅 (종합릴스 1개 + 숏릴스 3개)
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

from config import LANGUAGES, TOPIC_CONFIG, get_today_topic
from generator import claude_gen
from renderer import card as card_renderer
from renderer import fonts as F
from renderer import reel as reel_renderer
from renderer import tts_gen
from uploader import cloudinary_up, instagram


_TOPIC_MAP = {
    "greetings": 0,
    "cafe":      1,
    "travel":    2,
    "slang":     3,
}


def run(langs: list, dry_run: bool, forced_topic=None, slot: str = None) -> None:
    today     = date.today().strftime("%Y%m%d")
    yesterday = (date.today() - timedelta(days=1)).strftime("%Y%m%d")
    topic     = forced_topic or get_today_topic()

    # ── 중복 포스팅 방지 ─────────────────────────────────────────────
    from generator.history import is_slot_posted, mark_slot_posted
    post_key = slot or topic["topic_ko"]
    if not dry_run and is_slot_posted(today, post_key):
        print(f"\n⚠ [{today}] '{post_key}' 슬롯은 이미 포스팅 완료 — 건너뜁니다.")
        print("  (강제 재실행: --dry-run 으로 이미지만 생성 가능)")
        return

    print(f"\n{'='*54}")
    print(f"LangCard Studio  |  {topic['emoji']} {topic['topic_ko']}")
    print(f"{'='*54}")

    # ──────────────────────────────────────────────────────────────────
    # [1] 폰트 준비
    # ──────────────────────────────────────────────────────────────────
    print("\n[1/8] 폰트 확인 & 다운로드")
    F.ensure_fonts()

    # ──────────────────────────────────────────────────────────────────
    # [2] Claude AI 표현 생성 (한글 음차 포함)
    # ──────────────────────────────────────────────────────────────────
    print(f"\n[2/8] Claude API 표현 생성 ({', '.join(langs)})")
    all_data: dict[str, dict] = {}
    for lang in langs:
        print(f"  → {lang} 생성 중...")
        try:
            all_data[lang] = claude_gen.generate(lang, topic)
            expr = all_data[lang]["main_expression"]
            phon = all_data[lang].get("korean_phonetic", "")
            print(f"  ✓ {lang}: {expr}  [{phon}]")
        except Exception as e:
            # 2순위: 프리페치 파일 (어제 미리 생성해둔 것)
            prefetched = claude_gen.load_prefetch(today, lang)
            if prefetched:
                all_data[lang] = prefetched
                expr = prefetched.get("main_expression", "")
                print(f"  ⚠ Claude 실패, 프리페치 사용: {lang}  [{expr}]")
            else:
                # 3순위: 건너뜀 (전체 실패 방지)
                print(f"  ✗ {lang} 건너뜀 (Claude 실패 + 프리페치 없음): {e}")

    if not all_data:
        print("  ✗ 모든 언어 생성 실패")
        sys.exit(1)

    # 오늘 표현 데이터 JSON 저장 (내일 종합 캐러셀 커버에 사용)
    data_json_path = os.path.join("output", f"data_{today}.json")
    os.makedirs("output", exist_ok=True)
    with open(data_json_path, "w", encoding="utf-8") as f:
        json.dump({"topic": topic, "data": all_data}, f, ensure_ascii=False, indent=2)
    print(f"  ✓ 표현 데이터 저장: {data_json_path}")

    # 내일 프리페치 생성 (오늘 성공한 언어 기준, 파일 없을 때만)
    _prefetch_tomorrow(langs, today)

    # ──────────────────────────────────────────────────────────────────
    # [3] 카드 이미지 렌더링
    # ──────────────────────────────────────────────────────────────────
    print(f"\n[3/8] 카드 이미지 렌더링 (6장)")
    image_paths: dict[str, str] = {}
    vocab_paths: dict[str, str] = {}
    for lang in langs:
        try:
            image_paths[lang] = card_renderer.render(all_data[lang], lang, topic)
            vocab_paths[lang] = card_renderer.render_vocab(all_data[lang], lang, topic)
        except Exception as e:
            print(f"  ✗ {lang} 렌더링 실패: {e}")
            sys.exit(1)

    # ──────────────────────────────────────────────────────────────────
    # [4] TTS 음성 생성 (내일 종합 릴스용 저장)
    # ──────────────────────────────────────────────────────────────────
    print(f"\n[4/8] TTS 음성 생성 ({', '.join(langs)})")
    expr_tts:  dict[str, str | None] = {}
    vocab_tts: dict[str, str | None] = {}
    for lang in langs:
        try:
            expr_tts[lang]  = tts_gen.generate_expression(
                all_data[lang]["main_expression"], lang, today)
            vocab_tts[lang] = tts_gen.generate_vocab(
                all_data[lang].get("vocab", []), lang, today)
        except Exception as e:
            print(f"  ⚠ {lang} TTS 실패 (건너뜀): {e}")
            expr_tts[lang]  = None
            vocab_tts[lang] = None

    # ──────────────────────────────────────────────────────────────────
    # [5] 언어별 숏릴스 생성 (TTS 포함)
    # ──────────────────────────────────────────────────────────────────
    print(f"\n[5/8] 언어별 숏릴스 생성")
    short_reel_paths: dict[str, str] = {}
    for lang in langs:
        try:
            path = reel_renderer.render_short(
                image_paths[lang], vocab_paths[lang],
                expr_tts.get(lang),  vocab_tts.get(lang),
                lang, today
            )
            short_reel_paths[lang] = path
        except Exception as e:
            print(f"  ✗ {lang} 숏릴스 실패: {e}")
            sys.exit(1)

    # ──────────────────────────────────────────────────────────────────
    # [6] 전날 종합 캐러셀 준비 (어제 카드 6장 PNG 수집)
    # ──────────────────────────────────────────────────────────────────
    print(f"\n[6/8] 전날 종합 캐러셀 준비 (어제: {yesterday})")
    recap_pngs: list = []   # [en_expr, en_vocab, zh_expr, zh_vocab, ja_expr, ja_vocab]
    if len(langs) == len(LANGUAGES):   # 3개 언어 모두일 때만
        try:
            yest_imgs, yest_vocs = reel_renderer.find_yesterday_cards(yesterday)
            if len(yest_imgs) == 3:
                # 어제 표현 데이터 로드 (커버 내용 정확성)
                yest_json = os.path.join("output", f"data_{yesterday}.json")
                yest_all_data = all_data   # 폴백: 어제 JSON 없으면 오늘 데이터
                yest_topic    = topic
                if os.path.exists(yest_json):
                    with open(yest_json, "r", encoding="utf-8") as f:
                        saved = json.load(f)
                        yest_all_data = saved.get("data", all_data)
                        yest_topic    = saved.get("topic", topic)
                    print(f"  ✓ 어제 표현 데이터 로드: {yest_json}")
                else:
                    print(f"  ⚠ 어제 JSON 없음, 오늘 데이터로 대체: {yest_json}")
                # 커버 카드 생성 (첫 슬라이드)
                cover_path = card_renderer.render_recap_cover(
                    yest_all_data, yest_topic, yesterday)
                recap_pngs.append(cover_path)
                # 언어별 묶음: en_expr, en_vocab, zh_expr, zh_vocab, ja_expr, ja_vocab
                for lang in ("en", "zh", "ja"):
                    if lang in yest_imgs:
                        recap_pngs.append(yest_imgs[lang])
                    if lang in yest_vocs:
                        recap_pngs.append(yest_vocs[lang])
                print(f"  ✓ 카드 {len(recap_pngs)}장 준비: "
                      f"cover + en_expr, en_vocab, zh_expr, zh_vocab, ja_expr, ja_vocab")
            else:
                print(f"  ⚠ 전날 카드 {len(yest_imgs)}/3개만 발견, 종합 캐러셀 건너뜀")
        except Exception as e:
            print(f"  ⚠ 전날 카드 탐색 실패 (건너뜀): {e}")

    # ── 드라이런 종료 ──────────────────────────────────────────────────
    if dry_run:
        print("\n[dry-run] 업로드 생략. 생성된 파일:")
        for lang in langs:
            print(f"  표현 카드  {lang}: {image_paths[lang]}")
            print(f"  단어 카드  {lang}: {vocab_paths[lang]}")
            print(f"  TTS 표현   {lang}: {expr_tts.get(lang, '없음')}")
            print(f"  TTS 단어   {lang}: {vocab_tts.get(lang, '없음')}")
            print(f"  숏릴스     {lang}: {short_reel_paths.get(lang, '없음')}")
        if recap_pngs:
            print(f"  종합 캐러셀    : {len(recap_pngs)}장 준비됨")
        print("\n완료!")
        return

    # ──────────────────────────────────────────────────────────────────
    # [7] Cloudinary 업로드
    # ──────────────────────────────────────────────────────────────────
    print(f"\n[7/8] Cloudinary 업로드")

    short_reel_urls: dict[str, str] = {}
    for lang in langs:
        try:
            short_reel_urls[lang] = cloudinary_up.upload_video(
                short_reel_paths[lang], f"short_{lang}", today)
        except Exception as e:
            print(f"  ✗ {lang} 숏릴스 업로드 실패: {e}")
            sys.exit(1)

    # 종합 캐러셀: 커버 1장 + 어제 카드 6장 이미지 업로드
    recap_card_urls: list = []
    if recap_pngs:
        # recap_pngs = [cover, en_expr, en_vocab, zh_expr, zh_vocab, ja_expr, ja_vocab]
        _lang_seq   = ("all", "en", "en", "zh", "zh", "ja", "ja")
        _suffix_seq = ("cover", "expr", "vocab", "expr", "vocab", "expr", "vocab")
        try:
            for i, png in enumerate(recap_pngs):
                url = cloudinary_up.upload(
                    png, _lang_seq[i], "recap",
                    suffix=_suffix_seq[i], date_str=yesterday)
                recap_card_urls.append(url)
        except Exception as e:
            print(f"  ⚠ 종합 캐러셀 이미지 업로드 실패 (건너뜀): {e}")
            recap_card_urls = []

    # ──────────────────────────────────────────────────────────────────
    # [8] Instagram 포스팅
    # ──────────────────────────────────────────────────────────────────
    print(f"\n[8/8] Instagram 포스팅")

    # 8-a) 종합 캐러셀 먼저 (전날 복습, 일반 게시물)
    if recap_card_urls:
        try:
            instagram.post_recap_carousel(recap_card_urls, topic, all_data)
            time.sleep(8)
        except Exception as e:
            print(f"  ⚠ 종합 캐러셀 포스팅 실패 (건너뜀): {e}")

    # 8-b) 언어별 숏릴스 (en → zh → ja)
    from story_dispatcher import enqueue_story
    for lang in langs:
        if lang not in short_reel_urls:
            continue
        try:
            instagram.post_short_reel(
                short_reel_urls[lang], lang, all_data[lang], topic)
            # 릴스 포스팅 성공 → 1시간 후 스토리 공유 예약
            try:
                enqueue_story(short_reel_urls[lang], lang, delay_hours=1.0)
            except Exception as eq_err:
                print(f"  ⚠ [{lang}] 스토리 예약 실패 (건너뜀): {eq_err}")
            if lang != langs[-1]:
                time.sleep(8)  # 연속 포스팅 간격
        except Exception as e:
            print(f"\n✗ {lang} 숏릴스 포스팅 실패: {e}")
            sys.exit(1)

    print(f"\n✅ 전체 포스팅 완료! 총 {len(langs) + (1 if recap_card_urls else 0)}개 포스트")

    # 포스팅 완료 기록 (중복 방지용)
    if not dry_run:
        mark_slot_posted(today, post_key)


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
    parser = argparse.ArgumentParser(description="LangCard Studio 자동 포스팅")
    parser.add_argument(
        "--lang",
        choices=LANGUAGES + ["all"],
        default="all",
        help="언어 (기본: all — 영/중/일 전부)",
    )
    parser.add_argument(
        "--topic",
        choices=list(_TOPIC_MAP.keys()),
        default=None,
        help="주제 강제 지정: greetings|cafe|travel (기본: 날짜 기반 자동)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="카드+TTS+릴스 생성만, 업로드 안 함",
    )
    # 하위 호환용 (기존 cron job 대비)
    parser.add_argument("--slot", choices=["morning", "lunch", "evening"],
                        default=None, help="(하위 호환) 슬롯 → 주제로 매핑")
    args = parser.parse_args()

    langs = LANGUAGES if args.lang == "all" else [args.lang]

    # 주제 결정
    forced_topic = None
    if args.topic:
        forced_topic = TOPIC_CONFIG[_TOPIC_MAP[args.topic]]
    elif args.slot:
        _slot_to_topic = {"morning": 0, "lunch": 1, "evening": 2}
        forced_topic = TOPIC_CONFIG[_slot_to_topic[args.slot]]

    run(langs, args.dry_run, forced_topic, slot=args.slot)


if __name__ == "__main__":
    main()
