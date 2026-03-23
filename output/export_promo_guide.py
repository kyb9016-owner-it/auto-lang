"""
LangCard Studio — Promo Guide Carousel Exporter
Converts promo_guide_slide_01~05.html to PNG at 1080x1080px.
"""

import os
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTPUT_DIR = Path("/Users/kong/projects/auto-lang/output")

SLIDES = [
    ("promo_guide_slide_01.html", "promo_guide_slide_01.png"),
    ("promo_guide_slide_02.html", "promo_guide_slide_02.png"),
    ("promo_guide_slide_03.html", "promo_guide_slide_03.png"),
    ("promo_guide_slide_04.html", "promo_guide_slide_04.png"),
    ("promo_guide_slide_05.html", "promo_guide_slide_05.png"),
]

WIDTH = 1080
HEIGHT = 1350


def export_slides():
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox", "--disable-gpu"])
        context = browser.new_context(
            viewport={"width": WIDTH, "height": HEIGHT},
            device_scale_factor=1,
        )

        results = []

        for html_name, png_name in SLIDES:
            html_path = OUTPUT_DIR / html_name
            png_path = OUTPUT_DIR / png_name

            if not html_path.exists():
                print(f"  SKIP  {html_name} — file not found")
                results.append((png_name, False, "file not found"))
                continue

            page = context.new_page()
            page.set_viewport_size({"width": WIDTH, "height": HEIGHT})

            # Load file and wait for fonts/images
            page.goto(f"file://{html_path.resolve()}", wait_until="networkidle")

            # Extra wait for Google Fonts to render
            page.wait_for_timeout(1500)

            # Hide scrollbars before capture
            page.add_style_tag(content="body { overflow: hidden !important; scrollbar-width: none !important; }")

            page.screenshot(
                path=str(png_path),
                full_page=False,
                omit_background=False,
                clip={"x": 0, "y": 0, "width": WIDTH, "height": HEIGHT},
            )
            page.close()

            # Validate output
            if png_path.exists() and png_path.stat().st_size > 0:
                size_kb = png_path.stat().st_size // 1024
                print(f"  OK    {png_name}  ({size_kb} KB)")
                results.append((png_name, True, f"{size_kb} KB"))
            else:
                print(f"  FAIL  {png_name} — output file missing or empty")
                results.append((png_name, False, "output empty"))

        context.close()
        browser.close()

    print("\n--- Export Summary ---")
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"Exported: {passed}/{len(SLIDES)} slides")
    for name, ok, note in results:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}  {note}")

    return all(ok for _, ok, _ in results)


if __name__ == "__main__":
    print(f"Starting export — {WIDTH}x{HEIGHT}px\n")
    success = export_slides()
    exit(0 if success else 1)
