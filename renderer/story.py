"""스토리 이미지 렌더러 — Playwright로 HTML → 1080×1920 PNG"""
import asyncio
import os
import sys
from datetime import date

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")


def _build_html(all_data: dict, slot: str) -> str:
    """슬롯 데이터로 스토리 HTML 생성"""
    # config는 런타임에 import (프로젝트 루트가 sys.path에 있어야 함)
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from config import SLOT_CONFIG, LANG_CONFIG

    sc  = SLOT_CONFIG[slot]
    en  = all_data.get("en", {})
    zh  = all_data.get("zh", {})
    ja  = all_data.get("ja", {})

    def esc(s):
        return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"','&quot;')

    en_expr  = esc(en.get("main_expression",""))
    en_ko    = esc(en.get("korean_translation",""))
    zh_expr  = esc(zh.get("main_expression",""))
    zh_pron  = esc(zh.get("pronunciation",""))
    zh_ko    = esc(zh.get("korean_translation",""))
    ja_expr  = esc(ja.get("main_expression",""))
    ja_pron  = esc(ja.get("pronunciation",""))
    ja_ko    = esc(ja.get("korean_translation",""))

    zh_pron_html = f'<div class="pronunciation">{zh_pron}</div>' if zh_pron else ""
    ja_pron_html = f'<div class="pronunciation">{ja_pron}</div>' if ja_pron else ""

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<style>
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{
  width:1080px; height:1920px; overflow:hidden; background:#000;
  font-family:'Noto Sans KR','Segoe UI',sans-serif;
}}
.story {{
  width:1080px; height:1920px;
  background:linear-gradient(170deg,#ff6ec7 0%,#a855f7 45%,#3b82f6 100%);
  position:relative; display:flex; flex-direction:column; align-items:center; overflow:hidden;
}}
.story::before {{
  content:''; position:absolute; inset:0;
  background-image:radial-gradient(circle,rgba(255,255,255,0.10) 1.5px,transparent 1.5px);
  background-size:36px 36px; z-index:0;
}}
.orb {{ position:absolute; border-radius:50%; filter:blur(120px); pointer-events:none; z-index:0; }}
.orb1 {{ width:700px; height:700px; background:#ff6ec7; opacity:.35; top:-200px; right:-200px; }}
.orb2 {{ width:600px; height:600px; background:#3b82f6; opacity:.30; bottom:-100px; left:-150px; }}
.top-bar {{
  position:relative; z-index:10; width:100%;
  padding:90px 72px 0; display:flex; align-items:center; justify-content:space-between;
}}
.brand-lc {{ font-size:72px; font-weight:900; color:#fff; letter-spacing:-2px; font-family:Georgia,serif; line-height:1; }}
.brand-name {{ font-size:22px; font-weight:600; color:rgba(255,255,255,.75); letter-spacing:4px; text-transform:uppercase; margin-top:4px; }}
.date-badge {{
  background:rgba(255,255,255,.2); border:1.5px solid rgba(255,255,255,.45);
  border-radius:30px; padding:10px 28px; font-size:22px; font-weight:700; color:#fff;
}}
.title-area {{ position:relative; z-index:10; margin-top:80px; text-align:center; padding:0 72px; }}
.title-tag {{
  display:inline-block; background:rgba(255,255,255,.18); border:1.5px solid rgba(255,255,255,.45);
  border-radius:40px; padding:12px 40px; font-size:28px; font-weight:700; color:#fff;
  letter-spacing:2px; margin-bottom:28px;
}}
.title-main {{ font-size:62px; font-weight:900; color:#fff; line-height:1.15; letter-spacing:-1px; }}
.title-sub {{ font-size:32px; color:rgba(255,255,255,.7); margin-top:16px; }}
.cards-area {{ position:relative; z-index:10; margin-top:64px; width:100%; padding:0 56px; display:flex; flex-direction:column; gap:32px; }}
.lang-card {{
  background:rgba(255,255,255,.14); border:1.5px solid rgba(255,255,255,.35);
  border-radius:28px; padding:36px 48px;
}}
.lang-header {{ display:flex; align-items:center; gap:16px; margin-bottom:18px; }}
.flag {{ font-size:36px; }}
.lang-name {{ font-size:26px; font-weight:700; color:rgba(255,255,255,.8); letter-spacing:1px; text-transform:uppercase; }}
.expression {{ font-size:42px; font-weight:800; color:#fff; line-height:1.25; margin-bottom:10px; }}
.pronunciation {{ font-size:26px; color:rgba(255,255,255,.6); margin-bottom:10px; }}
.translation {{ font-size:28px; font-weight:600; color:rgba(255,255,255,.85); border-left:3px solid rgba(255,255,255,.5); padding-left:16px; }}
.divider {{ position:relative; z-index:10; width:calc(100% - 112px); height:1px; background:rgba(255,255,255,.25); margin:48px 56px 0; }}
.cta-area {{ position:relative; z-index:10; margin-top:auto; margin-bottom:90px; text-align:center; padding:0 72px; width:100%; }}
.cta-box {{
  background:rgba(255,255,255,.18); border:1.5px solid rgba(255,255,255,.45);
  border-radius:28px; padding:40px 48px;
}}
.cta-text {{ font-size:36px; font-weight:800; color:#fff; line-height:1.4; margin-bottom:20px; }}
.cta-handle {{ font-size:28px; font-weight:700; color:rgba(255,255,255,.75); letter-spacing:2px; }}
</style>
</head>
<body>
<div class="story">
  <div class="orb orb1"></div>
  <div class="orb orb2"></div>

  <div class="top-bar">
    <div><div class="brand-lc">LC</div><div class="brand-name">LangCard Studio</div></div>
    <div class="date-badge">오늘의 표현</div>
  </div>

  <div class="title-area">
    <div class="title-tag">{esc(sc["emoji"])} {esc(sc["label"])} {esc(sc["topic_ko"])} 표현</div>
    <div class="title-main">오늘의 {esc(sc["topic_ko"])}<br>3개국어로!</div>
    <div class="title-sub">영어 · 중국어 · 일본어</div>
  </div>

  <div class="cards-area">
    <div class="lang-card">
      <div class="lang-header"><span class="flag">🇺🇸</span><span class="lang-name">English</span></div>
      <div class="expression">{en_expr}</div>
      <div class="translation">→ {en_ko}</div>
    </div>
    <div class="lang-card">
      <div class="lang-header"><span class="flag">🇨🇳</span><span class="lang-name">中文</span></div>
      <div class="expression">{zh_expr}</div>
      {zh_pron_html}
      <div class="translation">→ {zh_ko}</div>
    </div>
    <div class="lang-card">
      <div class="lang-header"><span class="flag">🇯🇵</span><span class="lang-name">日本語</span></div>
      <div class="expression">{ja_expr}</div>
      {ja_pron_html}
      <div class="translation">→ {ja_ko}</div>
    </div>
  </div>

  <div class="divider"></div>

  <div class="cta-area">
    <div class="cta-box">
      <div class="cta-text">💾 저장하고 매일 복습하기!</div>
      <div class="cta-handle">@langcard.studio</div>
    </div>
  </div>
</div>
</body>
</html>"""


async def _screenshot(html: str, out_path: str) -> None:
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1080, "height": 1920})
        await page.set_content(html, wait_until="networkidle")
        await page.wait_for_timeout(400)
        await page.screenshot(
            path=out_path, full_page=False,
            clip={"x": 0, "y": 0, "width": 1080, "height": 1920}
        )
        await browser.close()


def render(all_data: dict, slot: str) -> str:
    """스토리 이미지 렌더링 → 저장 경로 반환"""
    today    = date.today().strftime("%Y%m%d")
    out_path = os.path.join(OUTPUT_DIR, f"story_{slot}_{today}.png")
    html     = _build_html(all_data, slot)
    asyncio.run(_screenshot(html, out_path))
    print(f"  ✓ 스토리 저장: {out_path}")
    return out_path
