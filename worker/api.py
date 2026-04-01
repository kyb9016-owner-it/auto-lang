"""
LangCard Studio — Worker FastAPI 서버
worker 서버에서 실행: uvicorn worker.api:app --host 0.0.0.0 --port 8000

담당 작업 (Steps 1-7):
  1. 폰트 확인
  2. Claude API 표현 생성 (프리페치 폴백 포함)
  3. 카드 이미지 렌더링
  4. TTS 음성 생성
  5. 숏릴스 MP4 생성
  6. 전날 종합 캐러셀 PNG 수집
  7. Cloudinary 업로드
  → 결과 URLs + 데이터를 JSON으로 main 서버에 반환
"""

import json
import os
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path

# ── 경로 설정 (auto-lang 루트를 sys.path에 추가) ─────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env", override=True)

from fastapi import FastAPI, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from config import LANGUAGES, TOPIC_CONFIG, COLLECTION_THEMES, get_today_topic, _today_kst, SLOT_LANG_MAP
from generator import claude_gen, history as hist_module
from renderer import card as card_renderer
from renderer import fonts as F
from renderer import reel as reel_renderer
from fetcher.unsplash import fetch_city_bg
from renderer import tts_gen
from uploader import cloudinary_up

# ── 앱 초기화 ─────────────────────────────────────────────────────────────────

app = FastAPI(title="LangCard Worker", version="1.1.0")
_start_time = time.time()
_bearer = HTTPBearer()

WORKER_SECRET = os.environ.get("WORKER_SECRET", "")

_TOPIC_MAP = {"greetings": 0, "cafe": 1, "travel": 2, "slang": 3}

# 슬롯별 대표 언어 (복습 캐러셀에서 슬롯당 1언어 표시)
_SLOT_LANG = {"morning": "en", "lunch": "zh", "evening": "ja"}

# ── 이벤트 주제 목록 ──────────────────────────────────────────────────────────

EVENT_TOPICS = [
    {"topic_ko": "슬랭 & 유행어",      "topic_en": "Slang & Trending Phrases",   "badge": "TREND",  "emoji": "🔥", "theme_slot": "morning"},
    {"topic_ko": "영화 & 드라마 대사", "topic_en": "Movie & Drama Quotes",        "badge": "DRAMA",  "emoji": "🎬", "theme_slot": "evening"},
    {"topic_ko": "직장 & 회사생활",    "topic_en": "Office & Work Life",           "badge": "OFFICE", "emoji": "💼", "theme_slot": "lunch"},
    {"topic_ko": "SNS & 인터넷 밈",    "topic_en": "Social Media & Internet Memes","badge": "MEME",   "emoji": "📱", "theme_slot": "morning"},
    {"topic_ko": "파티 & 축하",        "topic_en": "Party & Celebration",          "badge": "PARTY",  "emoji": "🎉", "theme_slot": "evening"},
    {"topic_ko": "연애 & 데이트",      "topic_en": "Romance & Dating",             "badge": "LOVE",   "emoji": "💕", "theme_slot": "morning"},
    {"topic_ko": "스포츠 & 응원",      "topic_en": "Sports & Cheering",            "badge": "SPORT",  "emoji": "⚽", "theme_slot": "evening"},
    {"topic_ko": "음식 & 먹방",        "topic_en": "Food & Mukbang",               "badge": "FOOD",   "emoji": "🍜", "theme_slot": "lunch"},
]


# ── 인증 ──────────────────────────────────────────────────────────────────────

def _verify(creds: HTTPAuthorizationCredentials = Security(_bearer)):
    if not WORKER_SECRET or creds.credentials != WORKER_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return creds


# ── 요청 모델 ─────────────────────────────────────────────────────────────────

class JobRequest(BaseModel):
    slot: str | None = None           # morning | lunch | evening (선택)
    topic: str | None = None          # greetings | cafe | travel (선택)
    custom_topic: dict | None = None  # 이벤트용 커스텀 주제
    langs: list[str] | None = None    # ["en","zh","ja"] (기본: 전체)
    dry_run: bool = False

class PrefetchRequest(BaseModel):
    force: bool = False  # 기존 파일 덮어쓰기


# ── 헬퍼 ──────────────────────────────────────────────────────────────────────

def _get_topic(slot: str | None, topic_key: str | None, custom_topic: dict | None = None) -> dict:
    """custom_topic → topic_key → slot → 오늘 자동 순으로 주제 결정"""
    if custom_topic:
        return custom_topic
    _SLOT_TO_TOPIC = {"morning": "greetings", "lunch": "cafe", "evening": "travel"}
    key = topic_key or _SLOT_TO_TOPIC.get(slot or "", "")
    if key and key in _TOPIC_MAP:
        return TOPIC_CONFIG[_TOPIC_MAP[key]]
    return get_today_topic()


def _output_path() -> str:
    p = ROOT / "output"
    p.mkdir(exist_ok=True)
    return str(p)


# ── 엔드포인트 ────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status": "ok",
        "uptime_sec": int(time.time() - _start_time),
    }


@app.post("/restart")
def restart_worker(creds=Security(_verify)):
    """Worker 서비스 재시작 (systemd)"""
    try:
        subprocess.Popen(["systemctl", "restart", "langcard-worker"])
        return {"status": "ok", "message": "재시작 요청됨"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/history")
def get_history(lang: str | None = None, creds=Security(_verify)):
    """최근 사용 표현 히스토리"""
    if lang and lang in ("en", "zh", "ja"):
        recent = hist_module.get_recent(lang)
        return {"status": "ok", "lang": lang, "expressions": recent[-20:]}
    result = {}
    for l in LANGUAGES:
        result[l] = hist_module.get_recent(l)[-10:]
    return {"status": "ok", **result}


@app.get("/event-topics")
def get_event_topics(creds=Security(_verify)):
    """이벤트 주제 목록"""
    return {"status": "ok", "topics": EVENT_TOPICS}


@app.post("/prefetch")
def run_prefetch(req: PrefetchRequest = PrefetchRequest(), creds=Security(_verify)):
    """내일 프리페치 강제 생성"""
    tomorrow = (_today_kst() + timedelta(days=1)).strftime("%Y%m%d")
    prefetch_path = os.path.join(_output_path(), f"data_prefetch_{tomorrow}.json")

    if os.path.exists(prefetch_path) and not req.force:
        with open(prefetch_path, "r", encoding="utf-8") as f:
            existing = json.load(f)
        return {"status": "already_exists", "tomorrow": tomorrow,
                "topic": existing.get("topic"), "langs": list(existing.get("data", {}).keys())}

    epoch = date(2026, 1, 1)
    tomorrow_idx   = (_today_kst() + timedelta(days=1) - epoch).days % 3
    tomorrow_topic = TOPIC_CONFIG[tomorrow_idx]

    prefetch_data: dict = {}
    for lang in LANGUAGES:
        try:
            prefetch_data[lang] = claude_gen.generate(lang, tomorrow_topic)
        except Exception as e:
            print(f"  ⚠ {lang} 프리페치 실패: {e}")

    if not prefetch_data:
        raise HTTPException(status_code=503, detail="프리페치 생성 전체 실패")

    with open(prefetch_path, "w", encoding="utf-8") as f:
        json.dump({"topic": tomorrow_topic, "data": prefetch_data}, f, ensure_ascii=False, indent=2)

    return {"status": "ok", "tomorrow": tomorrow,
            "topic": tomorrow_topic, "langs": list(prefetch_data.keys())}


@app.post("/job")
def run_job(req: JobRequest, creds=Security(_verify)):
    today      = _today_kst().strftime("%Y%m%d")
    yesterday  = (_today_kst() - timedelta(days=1)).strftime("%Y%m%d")
    topic      = _get_topic(req.slot, req.topic, req.custom_topic)
    output_dir = _output_path()
    slot       = req.slot or "morning"

    # 슬롯 → 단일 언어
    lang = SLOT_LANG_MAP.get(slot, "en")

    print(f"\n{'='*54}")
    print(f"[Worker HOOK] {slot} → {lang}  dry_run={req.dry_run}")
    print(f"{'='*54}")

    t_job = time.time()
    step_times: dict[str, float] = {}

    # Step 1: 폰트
    print("\n[1/7] 폰트 확인")
    t0 = time.time()
    try:
        F.ensure_fonts()
    except Exception as e:
        print(f"  ⚠ 폰트 오류 (계속): {e}")
    step_times["step1_fonts"] = time.time() - t0

    # Step 2: HOOK 표현 생성
    print(f"\n[2/7] Claude API HOOK 표현 생성 ({lang})")
    t0 = time.time()
    try:
        hook_data = claude_gen.generate_hook(lang)
        print(f"  ✓ WRONG: {hook_data['wrong']}")
        print(f"  ✓ RIGHT: {hook_data['right']}")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"HOOK 생성 실패: {e}")
    step_times["step2_claude"] = time.time() - t0

    # 데이터 JSON 저장
    data_json = os.path.join(output_dir, f"data_{slot}_{today}.json")
    with open(data_json, "w", encoding="utf-8") as f:
        json.dump({"slot": slot, "lang": lang, "data": hook_data},
                  f, ensure_ascii=False, indent=2)

    # Step 3: HOOK 카드 렌더링 (3장)
    print(f"\n[3/7] HOOK 카드 렌더링")
    t0 = time.time()
    bg_path = fetch_city_bg(lang, slot)

    hook_png = card_renderer.render_hook_card(
        hook_data["hook"], lang, today, slot=slot, bg_path=bg_path)
    wr_png = card_renderer.render_wrong_right_card(
        hook_data, lang, today, slot=slot, bg_path=bg_path)
    cta_png = card_renderer.render_cta_card(
        hook_data.get("cta", "이거 몰랐으면 저장해두세요"), lang, today,
        slot=slot, bg_path=bg_path)
    step_times["step3_render"] = time.time() - t0

    # Step 4: 이중 언어 TTS
    print(f"\n[4/7] TTS 음성 생성")
    t0 = time.time()
    hook_tts = tts_gen.generate_hook_tts(hook_data, lang, today, slot=slot)
    step_times["step4_tts"] = time.time() - t0

    # Step 5: HOOK 릴스 합성
    print(f"\n[5/7] HOOK 릴스 합성")
    t0 = time.time()
    hook_reel_path = reel_renderer.render_hook_reel(
        hook_png, wr_png, cta_png, hook_tts, lang, today, slot=slot)
    step_times["step5_reels"] = time.time() - t0

    # Step 6: 리캡 캐러셀 (유지 — 간소화)
    print(f"\n[6/7] 전날 리캡 캐러셀 준비")
    t0 = time.time()
    recap_pngs = []
    recap_meta = []
    try:
        import glob as _glob
        yest_data_files = sorted(_glob.glob(
            os.path.join(output_dir, f"data_*_{yesterday}.json")))
        if yest_data_files:
            for yf in yest_data_files:
                with open(yf, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                wr_card = os.path.join(output_dir,
                    f"wrongright_{saved.get('lang', '')}_{saved.get('slot', '')}_{yesterday}.png")
                if os.path.exists(wr_card):
                    recap_pngs.append(wr_card)
                    recap_meta.append((saved.get('lang', 'all'), f"wr_{saved.get('slot', '')}"))
            if recap_pngs:
                cover_path = card_renderer.render_recap_cover({}, topic, yesterday)
                recap_pngs.insert(0, cover_path)
                recap_meta.insert(0, ("all", "cover"))
                print(f"  ✓ 리캡 카드 {len(recap_pngs)}장 준비")
            else:
                print(f"  ⚠ 전날 WRONG→RIGHT 카드 없음")
        else:
            print(f"  ⚠ 전날 데이터 없음")
    except Exception as e:
        print(f"  ⚠ 리캡 준비 실패: {e}")
    step_times["step6_carousel"] = time.time() - t0

    # dry-run
    if req.dry_run:
        print(f"\n✅ Worker 완료 (dry-run)  ⏱ 총 {time.time() - t_job:.0f}s")
        return {
            "status": "dry_run",
            "today": today,
            "slot": slot,
            "lang": lang,
            "hook_data": hook_data,
            "hook_reel_url": None,
            "recap_card_urls": [],
            "step_times": step_times,
            "dry_run": True,
        }

    # Step 7: Cloudinary 업로드
    print(f"\n[7/7] Cloudinary 업로드")
    t0 = time.time()
    hook_reel_url = cloudinary_up.upload_video(hook_reel_path, f"hook_{lang}", today)

    recap_card_urls = []
    if recap_pngs:
        for i, (png, (lng, sfx)) in enumerate(zip(recap_pngs, recap_meta)):
            try:
                url = cloudinary_up.upload(png, lng, "recap", suffix=sfx, date_str=yesterday)
                recap_card_urls.append(url)
            except Exception as e:
                print(f"  ⚠ 리캡 {i} 업로드 실패: {e}")
    step_times["step7_upload"] = time.time() - t0

    print(f"\n✅ Worker 완료  ⏱ 총 {time.time() - t_job:.0f}s")

    return {
        "status": "ok",
        "today": today,
        "slot": slot,
        "lang": lang,
        "hook_data": hook_data,
        "hook_reel_url": hook_reel_url,
        "recap_card_urls": recap_card_urls,
        "step_times": step_times,
        "dry_run": False,
    }


# ── 프리페치 헬퍼 ─────────────────────────────────────────────────────────────

def _try_prefetch_tomorrow(langs: list, output_dir: str, today_data: dict):
    """오늘 생성 성공 후 내일 표현을 미리 생성해 저장 (실패해도 무시)"""
    tomorrow = (_today_kst() + timedelta(days=1)).strftime("%Y%m%d")
    prefetch_path = os.path.join(output_dir, f"data_prefetch_{tomorrow}.json")
    if os.path.exists(prefetch_path):
        return

    epoch = date(2026, 1, 1)
    tomorrow_idx   = (_today_kst() + timedelta(days=1) - epoch).days % 3
    tomorrow_topic = TOPIC_CONFIG[tomorrow_idx]

    print(f"\n  [프리페치] 내일({tomorrow}) 표현 미리 생성 중...")
    prefetch_data: dict[str, dict] = {}
    for lang in langs:
        try:
            prefetch_data[lang] = claude_gen.generate(lang, tomorrow_topic)
            print(f"    ✓ {lang} 프리페치 완료")
        except Exception as e:
            print(f"    ⚠ {lang} 프리페치 실패 (무시): {e}")

    if prefetch_data:
        with open(prefetch_path, "w", encoding="utf-8") as f:
            json.dump({"topic": tomorrow_topic, "data": prefetch_data},
                      f, ensure_ascii=False, indent=2)
        print(f"    ✓ 프리페치 저장: {prefetch_path}")
