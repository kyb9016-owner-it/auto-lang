"""
LangCard Studio — 메인 실행 스크립트

사용법:
  python main.py --slot morning            # 전체 파이프라인 실행
  python main.py --slot lunch --dry-run    # 카드 생성만 (업로드 안 함)
  python main.py --slot evening --lang en  # 특정 언어만
"""
import argparse
import os
import sys

from dotenv import load_dotenv
import pathlib
load_dotenv(pathlib.Path(__file__).parent / ".env", override=True)

from config import LANGUAGES, SLOT_CONFIG
from generator import claude_gen
from renderer import card as card_renderer
from renderer import fonts as F
from uploader import cloudinary_up, instagram


def run(slot: str, langs: list[str], dry_run: bool) -> None:
    sc = SLOT_CONFIG[slot]
    print(f"\n{'='*50}")
    print(f"LangCard Studio  |  {sc['emoji']} {sc['label']} ({sc['topic_ko']})")
    print(f"{'='*50}")

    # 1) 폰트 준비
    print("\n[1/4] 폰트 확인 & 다운로드")
    F.ensure_fonts()

    # 2) Claude AI 표현 생성
    print(f"\n[2/4] Claude API 표현 생성 ({', '.join(langs)})")
    all_data: dict[str, dict] = {}
    for lang in langs:
        print(f"  → {lang} 생성 중...")
        try:
            all_data[lang] = claude_gen.generate(lang, slot)
            print(f"  ✓ {lang}: {all_data[lang]['main_expression']}")
        except Exception as e:
            print(f"  ✗ {lang} 생성 실패: {e}")
            sys.exit(1)

    # 3) 카드 이미지 렌더링 (표현 카드 + 단어 카드)
    print(f"\n[3/4] 카드 이미지 렌더링")
    image_paths: dict[str, str] = {}
    vocab_paths: dict[str, str] = {}
    for lang in langs:
        try:
            image_paths[lang] = card_renderer.render(all_data[lang], lang, slot)
            vocab_paths[lang] = card_renderer.render_vocab(all_data[lang], lang, slot)
        except Exception as e:
            print(f"  ✗ {lang} 렌더링 실패: {e}")
            sys.exit(1)

    if dry_run:
        print("\n[dry-run] 업로드 생략. 카드 저장 위치:")
        for lang, path in image_paths.items():
            print(f"  표현 {lang}: {path}")
        for lang, path in vocab_paths.items():
            print(f"  단어 {lang}: {path}")
        print("\n완료!")
        return

    # 4) Cloudinary 업로드
    print(f"\n[4/4] Cloudinary 업로드 & Instagram 포스팅")
    image_urls: dict[str, str] = {}
    vocab_urls: dict[str, str] = {}
    for lang in langs:
        try:
            image_urls[lang] = cloudinary_up.upload(image_paths[lang], lang, slot)
            vocab_urls[lang]  = cloudinary_up.upload(vocab_paths[lang],  lang, slot, suffix="vocab")
        except Exception as e:
            print(f"  ✗ {lang} 업로드 실패: {e}")
            sys.exit(1)

    # 5-a) 표현 캐러셀 포스팅
    try:
        media_id = instagram.post_carousel(image_urls, slot, all_data)
        print(f"  ✅ 표현 포스팅 완료! media_id: {media_id}")
    except Exception as e:
        print(f"\n✗ 표현 Instagram 포스팅 실패: {e}")
        sys.exit(1)

    # 5-b) 단어 캐러셀 포스팅
    try:
        vocab_id = instagram.post_carousel(vocab_urls, slot, all_data, is_vocab=True)
        print(f"  ✅ 단어 포스팅 완료! media_id: {vocab_id}")
    except Exception as e:
        print(f"\n✗ 단어 Instagram 포스팅 실패: {e}")
        sys.exit(1)

    print(f"\n✅ 전체 포스팅 완료!")


def main():
    parser = argparse.ArgumentParser(description="LangCard Studio 자동 포스팅")
    parser.add_argument(
        "--slot",
        choices=list(SLOT_CONFIG.keys()),
        required=True,
        help="시간대: morning | lunch | evening",
    )
    parser.add_argument(
        "--lang",
        choices=LANGUAGES + ["all"],
        default="all",
        help="언어 (기본: all — 영/중/일 전부)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="카드 생성만, 업로드 안 함",
    )
    args = parser.parse_args()

    langs = LANGUAGES if args.lang == "all" else [args.lang]
    run(args.slot, langs, args.dry_run)


if __name__ == "__main__":
    main()
