"""
LangCard Studio — 공용 파이프라인 (Steps 1-7)

main.py, worker/api.py, dispatch.py에서 공유하는 핵심 생성 로직을 캡슐화.

사용법:
    from pipeline import run_generation, post_recap, post_hook_reel_and_story
    result = run_generation(slot, today, yesterday, output_dir, dry_run)
"""
from __future__ import annotations

import glob as _glob
import json
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from config import SLOT_LANG_MAP, LANG_CONFIG, get_today_topic
from generator import claude_gen
from renderer import card as card_renderer
from renderer import fonts as F
from renderer import reel as reel_renderer
from renderer import tts_gen
from renderer import vocab_card as vocab_renderer
from fetcher.unsplash import fetch_city_bg
from uploader import cloudinary_up


# ── 결과 데이터 클래스 ────────────────────────────────────────────────────────

@dataclass
class GenerationResult:
    today: str
    yesterday: str
    slot: str
    lang: str
    hook_data: dict
    hook_png: str = ""
    wr_png: str = ""
    cta_png: str = ""
    hook_reel_path: str = ""
    hook_tts: Optional[str] = None
    recap_pngs: List[str] = field(default_factory=list)
    recap_meta: List[Tuple[str, str]] = field(default_factory=list)
    hook_reel_url: Optional[str] = None
    vocab_pngs: List[str] = field(default_factory=list)
    recap_card_urls: List[str] = field(default_factory=list)
    step_times: Dict[str, float] = field(default_factory=dict)


# ── 스텝별 내부 함수 ──────────────────────────────────────────────────────────

def _step1_fonts(result: GenerationResult, track_times: bool) -> None:
    print("\n[1/7] 폰트 확인 & 다운로드")
    t0 = time.time()
    try:
        F.ensure_fonts()
    except Exception as e:
        print(f"  ⚠ 폰트 오류 (계속): {e}")
    if track_times:
        result.step_times["step1_fonts"] = time.time() - t0


def _step2_generate(result: GenerationResult, output_dir: str, track_times: bool) -> None:
    lc = LANG_CONFIG[result.lang]
    print(f"\n[2/7] Claude API HOOK 표현 생성 ({result.lang})")
    t0 = time.time()
    try:
        hook_data = claude_gen.generate_hook(result.lang)
        print(f"  ✓ WRONG: {hook_data['wrong']}")
        print(f"  ✓ RIGHT: {hook_data['right']}")
    except Exception as e:
        raise RuntimeError(f"HOOK 생성 실패: {e}")

    result.hook_data = hook_data

    data_json_path = os.path.join(output_dir, f"data_{result.slot}_{result.today}.json")
    os.makedirs(output_dir, exist_ok=True)
    with open(data_json_path, "w", encoding="utf-8") as f:
        json.dump({"slot": result.slot, "lang": result.lang, "data": hook_data},
                  f, ensure_ascii=False, indent=2)

    if track_times:
        result.step_times["step2_claude"] = time.time() - t0


def _step3_render(result: GenerationResult, track_times: bool) -> None:
    print(f"\n[3/7] 카드 이미지 렌더링 (3장)")
    t0 = time.time()
    os.makedirs("tmp", exist_ok=True)
    # Apple 디자인: 솔리드 컬러 배경 사용 (Unsplash 사진 비활성화)
    bg_path = None

    result.hook_png = card_renderer.render_hook_card(
        result.hook_data, result.lang, result.today,
        slot=result.slot, bg_path=bg_path)
    result.wr_png = card_renderer.render_wrong_right_card(
        result.hook_data, result.lang, result.today,
        slot=result.slot, bg_path=bg_path)
    result.cta_png = card_renderer.render_cta_card(
        result.hook_data, result.lang, result.today,
        slot=result.slot, bg_path=bg_path)

    vocab_list = result.hook_data.get("vocab", [])
    if vocab_list:
        result.vocab_pngs = vocab_renderer.render_vocab_cards(
            vocab_list, result.lang, result.today, slot=result.slot)
    else:
        result.vocab_pngs = []

    if track_times:
        result.step_times["step3_render"] = time.time() - t0


def _step4_tts(result: GenerationResult, track_times: bool) -> None:
    lc = LANG_CONFIG[result.lang]
    print(f"\n[4/7] TTS 음성 생성 (한국어 + {lc['name_ko']})")
    t0 = time.time()
    result.hook_tts = tts_gen.generate_hook_tts(
        result.hook_data, result.lang, result.today, slot=result.slot)
    if track_times:
        result.step_times["step4_tts"] = time.time() - t0


def _step5_reel(result: GenerationResult, track_times: bool) -> None:
    print(f"\n[5/7] HOOK 릴스 합성 (15초)")
    t0 = time.time()
    result.hook_reel_path = reel_renderer.render_hook_reel(
        result.hook_png, result.wr_png, result.cta_png,
        result.hook_tts, result.lang, result.today, slot=result.slot)
    if track_times:
        result.step_times["step5_reels"] = time.time() - t0


def _step6_recap(result: GenerationResult, output_dir: str,
                 topic: Optional[dict], track_times: bool) -> None:
    print(f"\n[6/7] 전날 리캡 캐러셀 준비 (어제: {result.yesterday})")
    t0 = time.time()
    recap_pngs: List[str] = []
    recap_meta: List[Tuple[str, str]] = []
    try:
        yest_data_files = sorted(_glob.glob(
            os.path.join(output_dir, f"data_*_{result.yesterday}.json")))
        if yest_data_files:
            for yf in yest_data_files:
                with open(yf, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                wr_card = os.path.join(output_dir,
                    f"wrongright_{saved.get('lang', '')}_{saved.get('slot', '')}_{result.yesterday}.png")
                if os.path.exists(wr_card):
                    recap_pngs.append(wr_card)
                    recap_meta.append((saved.get("lang", "all"), f"wr_{saved.get('slot', '')}"))
            if recap_pngs:
                cover_path = card_renderer.render_recap_cover(
                    {}, topic or {}, result.yesterday)
                recap_pngs.insert(0, cover_path)
                recap_meta.insert(0, ("all", "cover"))
                print(f"  ✓ 리캡 카드 {len(recap_pngs)}장 준비")
            else:
                print(f"  ⚠ 전날 WRONG→RIGHT 카드 없음, 리캡 건너뜀")
        else:
            print(f"  ⚠ 전날 데이터 없음, 리캡 건너뜀")
    except Exception as e:
        print(f"  ⚠ 리캡 준비 실패 (건너뜀): {e}")

    result.recap_pngs = recap_pngs
    result.recap_meta = recap_meta
    if track_times:
        result.step_times["step6_carousel"] = time.time() - t0


def _step7_upload(result: GenerationResult, output_dir: str, track_times: bool) -> None:
    print(f"\n[7/7] Cloudinary 업로드")
    t0 = time.time()
    result.hook_reel_url = cloudinary_up.upload_video(
        result.hook_reel_path, f"hook_{result.lang}", result.today)

    recap_card_urls: List[str] = []
    if result.recap_pngs:
        for i, (png, (lng, sfx)) in enumerate(zip(result.recap_pngs, result.recap_meta)):
            try:
                url = cloudinary_up.upload(
                    png, lng, "recap", suffix=sfx, date_str=result.yesterday)
                recap_card_urls.append(url)
            except Exception as e:
                print(f"  ⚠ 리캡 {i} 업로드 실패 (건너뜀): {e}")

    result.recap_card_urls = recap_card_urls
    if track_times:
        result.step_times["step7_upload"] = time.time() - t0


# ── 핵심 공개 함수 ────────────────────────────────────────────────────────────

def run_generation(
    slot: str,
    today: str,
    yesterday: str,
    output_dir: str = "output",
    dry_run: bool = False,
    track_times: bool = False,
    topic: Optional[dict] = None,
    lang: Optional[str] = None,
) -> GenerationResult:
    """
    Steps 1-7 실행: 폰트 → 생성 → 렌더 → TTS → 릴스 → 리캡 → 업로드(dry_run이면 생략).

    Returns:
        GenerationResult — 생성된 파일 경로 및 업로드 URL 포함

    Raises:
        RuntimeError — Step 2 (Claude 생성) 실패 시
    """
    lang = lang or SLOT_LANG_MAP[slot]
    lc = LANG_CONFIG[lang]

    print(f"\n{'='*54}")
    print(f"LangCard Studio HOOK  |  {slot} → {lc['flag']} {lc['name_ko']}")
    print(f"{'='*54}")

    # hook_data는 step2에서 채워짐; 빈 dict으로 초기화
    result = GenerationResult(
        today=today,
        yesterday=yesterday,
        slot=slot,
        lang=lang,
        hook_data={},
    )

    _step1_fonts(result, track_times)
    _step2_generate(result, output_dir, track_times)   # RuntimeError 가능
    _step3_render(result, track_times)
    _step4_tts(result, track_times)
    _step5_reel(result, track_times)
    _step6_recap(result, output_dir, topic, track_times)

    if not dry_run:
        _step7_upload(result, output_dir, track_times)

    return result


# ── 포스팅 헬퍼 (lazy import — worker 환경 호환) ──────────────────────────────

def post_recap(recap_card_urls: List[str], topic: Optional[dict] = None) -> None:
    """리캡 캐러셀을 Instagram에 포스팅한다."""
    from uploader import instagram
    instagram.post_recap_carousel(recap_card_urls, topic or {}, {})


def post_hook_reel_and_story(hook_reel_url: str, lang: str, hook_data: dict,
                              delay_hours: float = 1.0) -> None:
    """HOOK 릴스를 포스팅하고 스토리 예약을 건다."""
    from uploader import instagram
    from story_dispatcher import enqueue_story
    instagram.post_hook_reel(hook_reel_url, lang, hook_data)
    try:
        enqueue_story(hook_reel_url, lang, delay_hours=delay_hours)
    except Exception as e:
        print(f"  ⚠ 스토리 예약 실패 (건너뜀): {e}")
