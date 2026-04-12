# Instagram Carousel Orchestrator — Memory

## Export Toolchain
- Playwright (Python sync API) + Chromium is available and working on this machine.
- Use `networkidle` wait + 1500ms extra delay for Google Fonts to render before screenshot.
- Clip parameter: `{"x":0,"y":0,"width":1080,"height":1080}` prevents oversized captures.
- Export script pattern: write to `output/export_{project}.py`, run with `python3`.

## LangCard Studio Brand Conventions
- Background: #0D1B2A (deep navy)
- Accent: #FFD54F (gold)
- Fonts: DM Sans (English/numbers) + Noto Sans KR (Korean)
- Forbidden words: "자동", "자동화", "봇", "AI", "알고리즘"
- Canvas: 1080x1080px (square) for feed carousels
- File naming: `promo_intro_slide_01.png` ~ `promo_intro_slide_05.png` in `/output/`

## Slide Structure (Account Intro Carousel — confirmed approved)
1. Cover: Brand name (large gold) + flag emojis + tagline
2. Value Prop: 3-language breakdown with left-border card rows
3. Content Preview: Mini-card layout (flag + expression in gold + Korean meaning)
4. Topics: Icon box + 2-column text for each content pillar
5. CTA: Centered, handle in pill badge, flag emoji row footer

## Slide Structure (Content Guide Carousel — confirmed approved, 1 revision)
Output: promo_guide_slide_01~05.png in /output/
1. Cover: "매일, 3개국어" gold headline + 3 flag rows (each language on separate line) + tagline
2. Expression Cards: type badge + title + 3 mini-card previews (flag / gold expr / KO meaning)
3. Vocab + Reels: type badge + 2-column blocks (card icon left, reels icon right) + equation footer
4. Review Carousel: type badge + Day1→Day2 timeline visual + insight box
5. CTA: Follow label + gold main copy + handle pill + flag row

## Revision Pattern — Multilingual Account Framing
- "1표현 × 3개국어" (one expression translated into 3 languages) was factually wrong for LangCard Studio: each language posts its own independent expression.
- Correct framing: "매일, 3개국어 / 각 언어 표현 하나씩" — parallel listing per language.
- Rule: always verify whether a multilingual account translates one expression or posts separate expressions per language before using multiplication/formula framing in cover copy.

## Pipeline Notes
- Sub-agents (carousel-content-strategist, instagram-carousel-copywriter, instagram-carousel-generator, slide-production-exporter) are defined in `.claude/agents/` but not invokable as Skills — orchestrator executes their logic directly.
- Always pass full outputs between steps; never summarize mid-pipeline.
- Human Review gate is mandatory before export; only "approve" (or unambiguous affirmative) triggers Step 6.
