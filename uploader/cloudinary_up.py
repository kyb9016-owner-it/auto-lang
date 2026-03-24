"""Cloudinary에 이미지/영상 업로드 → public URL 반환"""
import os
from urllib.parse import urlparse
import cloudinary
import cloudinary.uploader
from datetime import date


def _init_cloudinary():
    url = os.environ.get("CLOUDINARY_URL", "")
    parsed = urlparse(url)
    cloudinary.config(
        cloud_name=parsed.hostname,
        api_key=parsed.username,
        api_secret=parsed.password,
    )


_init_cloudinary()


def upload(image_path: str, lang: str, slot_or_label: str,
           suffix: str = "", date_str: str = "") -> str:
    """이미지를 Cloudinary에 업로드하고 public URL 반환.
    date_str: 날짜 태그 (기본값: 오늘). 어제 카드 업로드 시 yesterday 날짜 전달.
    """
    date_tag = date_str or date.today().strftime("%Y%m%d")
    tag = f"_{suffix}" if suffix else ""
    public_id = f"langcard/{slot_or_label}_{lang}{tag}_{date_tag}"

    result = cloudinary.uploader.upload(
        image_path,
        public_id=public_id,
        overwrite=True,
        resource_type="image",
        format="png",
        transformation=[{"width": 1080, "height": 1350, "crop": "limit", "quality": 100}],
    )

    url = result["secure_url"]
    print(f"  ✓ Cloudinary 업로드: {url}")
    return url


def upload_video(video_path: str, label: str, date_str: str = "",
                 suffix: str = "") -> str:
    """
    영상(MP4)을 Cloudinary에 업로드하고 public URL 반환.
    Instagram Reels용: resource_type="video"
    """
    if not date_str:
        date_str = date.today().strftime("%Y%m%d")
    tag = f"_{suffix}" if suffix else ""
    public_id = f"langcard/{label}{tag}_{date_str}"

    result = cloudinary.uploader.upload(
        video_path,
        public_id=public_id,
        overwrite=True,
        resource_type="video",
    )

    url = result["secure_url"]
    print(f"  ✓ Cloudinary 영상 업로드: {url}")
    return url
