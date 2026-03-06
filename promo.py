"""
프로필 상단 고정용 광고 캐러셀 2종 포스팅
  캐러셀 ①: 계정 소개   (promo_intro_slide_01~05.png)
  캐러셀 ②: 활용법 안내  (promo_guide_slide_01~05.png)

사용법:
  python3 promo.py --dry-run   # Cloudinary 업로드까지만 (Instagram 포스팅 생략)
  python3 promo.py             # 업로드 + 포스팅 (--dry-run 없이)

포스팅 후 Instagram 앱에서 두 게시물을 수동으로 핀 고정하세요.
  게시물 3점 메뉴 → "게시물 고정"
"""

import os
import sys
import time
import argparse
from dotenv import load_dotenv

load_dotenv()

from uploader import cloudinary_up
from uploader.instagram import (
    _create_image_container,
    _create_carousel_container,
    _publish,
    _wait_ready,
)
from config import HASHTAGS

# ── 슬라이드 경로 ──────────────────────────────────────────────────────────────

OUTPUT_DIR = "output"

INTRO_SLIDES = [
    os.path.join(OUTPUT_DIR, f"promo_intro_slide_0{i}.png")
    for i in range(1, 6)
]

GUIDE_SLIDES = [
    os.path.join(OUTPUT_DIR, f"promo_guide_slide_0{i}.png")
    for i in range(1, 6)
]

# ── 캡션 ──────────────────────────────────────────────────────────────────────

CAPTION_INTRO = "\n".join([
    "매일, 3개국어로. 진짜 쓰는 표현만 골랐어요. 🇺🇸🇨🇳🇯🇵",
    "",
    "영어, 중국어, 일본어 —",
    "실생활에서 바로 꺼내 쓸 수 있는 표현을 매일 만나보세요.",
    "",
    "스와이프해서 어떤 콘텐츠인지 확인해보세요 👉",
    "",
    "이 중에 배우고 싶은 언어가 있나요? 댓글로 알려주세요 💬",
    "💾 저장해두고 팔로우하면 놓치지 않아요!",
    "",
    HASHTAGS,
])

CAPTION_GUIDE = "\n".join([
    "매일, 3개국어. 각각 표현 하나씩. 🇺🇸🇨🇳🇯🇵",
    "",
    "표현 카드 → 단어 카드 → 숏릴스 발음까지.",
    "어제 배운 표현은 복습 카드로 다시 한 번.",
    "",
    "스와이프해서 어떤 콘텐츠가 올라오는지 확인해보세요 👉",
    "",
    "어떤 콘텐츠가 제일 도움이 될 것 같나요? 댓글로 알려주세요 💬",
    "💾 저장해두고 팔로우하면 매일 받아볼 수 있어요!",
    "",
    HASHTAGS,
])

# ── 헬퍼 ──────────────────────────────────────────────────────────────────────

def _upload_slides(slides: list[str], label: str) -> list[str]:
    """슬라이드 PNG 5장 → Cloudinary → URL 리스트 반환"""
    urls = []
    for i, path in enumerate(slides, start=1):
        if not os.path.exists(path):
            raise FileNotFoundError(f"슬라이드 없음: {path}")
        url = cloudinary_up.upload(
            path,
            lang="all",
            slot_or_label=label,
            suffix=f"slide{i:02d}",
        )
        print(f"    ✓ [{i}/{len(slides)}] 업로드 완료: {os.path.basename(path)}")
        urls.append(url)
    return urls


def _post_carousel(image_urls: list[str], caption: str, label: str) -> str:
    """이미지 URL 리스트 → Instagram 캐러셀 게시물 포스팅 → media_id"""
    print(f"  → {label} 이미지 컨테이너 생성 중...")
    child_ids = []
    for i, url in enumerate(image_urls):
        if i > 0:
            time.sleep(3)
        cid = _create_image_container(url, is_carousel_item=True)
        _wait_ready(cid)
        child_ids.append(cid)
        print(f"    ✓ 슬라이드 {i+1}/{len(image_urls)} 준비")

    print(f"  → {label} 캐러셀 컨테이너 생성 중...")
    carousel_id = _create_carousel_container(child_ids, caption)
    _wait_ready(carousel_id)

    print(f"  → {label} 게시 중...")
    media_id = _publish(carousel_id)
    print(f"  ✓ {label} 완료! media_id: {media_id}")
    return media_id


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="프로필 고정용 광고 캐러셀 포스팅")
    parser.add_argument("--dry-run", action="store_true",
                        help="Cloudinary 업로드까지만 실행 (Instagram 포스팅 생략)")
    args = parser.parse_args()

    # ── 파일 존재 확인 ────────────────────────────────────────────────────────
    print("\n[검사] 슬라이드 파일 확인...")
    for path in INTRO_SLIDES + GUIDE_SLIDES:
        if not os.path.exists(path):
            print(f"  ✗ 없음: {path}")
            sys.exit(1)
    print(f"  ✓ 총 {len(INTRO_SLIDES) + len(GUIDE_SLIDES)}장 확인")

    # ── Cloudinary 업로드 ────────────────────────────────────────────────────
    print("\n[1/4] 캐러셀 ① 업로드 (promo_intro)")
    intro_urls = _upload_slides(INTRO_SLIDES, "promo_intro")

    print("\n[2/4] 캐러셀 ② 업로드 (promo_guide)")
    guide_urls = _upload_slides(GUIDE_SLIDES, "promo_guide")

    if args.dry_run:
        print("\n[dry-run] Instagram 포스팅 생략. 업로드된 URL:")
        for i, url in enumerate(intro_urls, 1):
            print(f"  ①-{i}: {url}")
        for i, url in enumerate(guide_urls, 1):
            print(f"  ②-{i}: {url}")
        print("\ndry-run 완료.")
        return

    # ── Instagram 포스팅 ─────────────────────────────────────────────────────
    print("\n[3/4] 캐러셀 ① Instagram 포스팅 (계정 소개)")
    media_id_intro = _post_carousel(intro_urls, CAPTION_INTRO, "캐러셀 ①")

    print("\n  8초 대기...")
    time.sleep(8)

    print("\n[4/4] 캐러셀 ② Instagram 포스팅 (활용법 안내)")
    media_id_guide = _post_carousel(guide_urls, CAPTION_GUIDE, "캐러셀 ②")

    # ── 완료 ─────────────────────────────────────────────────────────────────
    print("\n" + "="*60)
    print("✅ 프로모 캐러셀 2종 포스팅 완료!")
    print(f"   캐러셀 ① media_id: {media_id_intro}")
    print(f"   캐러셀 ② media_id: {media_id_guide}")
    print("="*60)
    print("\n📌 Instagram 앱에서 두 게시물을 프로필 상단에 핀 고정해주세요.")
    print("   게시물 → 우상단 3점 메뉴 → '게시물 고정'")


if __name__ == "__main__":
    main()
