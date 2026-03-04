"""Cloudinary에 이미지 업로드 → public URL 반환"""
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


def upload(image_path: str, lang: str, slot: str) -> str:
    """이미지를 Cloudinary에 업로드하고 public URL 반환"""
    today = date.today().strftime("%Y%m%d")
    public_id = f"langcard/{slot}_{lang}_{today}"

    result = cloudinary.uploader.upload(
        image_path,
        public_id=public_id,
        overwrite=True,
        resource_type="image",
        format="jpg",           # Instagram은 JPG 선호
        quality="auto:good",
        transformation=[{"width": 1080, "height": 1080, "crop": "limit"}],
    )

    url = result["secure_url"]
    print(f"  ✓ Cloudinary 업로드: {url}")
    return url
