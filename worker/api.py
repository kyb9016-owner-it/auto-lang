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

from config import LANGUAGES, TOPIC_CONFIG, get_today_topic, _today_kst
from generator import claude_gen, history as hist_module
from renderer import card as card_renderer
from renderer import fonts as F
from renderer import reel as reel_renderer
from renderer import tts_gen
from uploader import cloudinary_up

# ── 앱 초기화 ─────────────────────────────────────────────────────────────────

app = FastAPI(title="LangCard Worker", version="1.1.0")
_start_time = time.time()
_bearer = HTTPBearer()

WORKER_SECRET = os.environ.get("WORKER_SECRET", "")

_TOPIC_MAP = {"greetings": 0, "cafe": 1, "travel": 2}

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
    """
    Steps 1-7 실행 후 결과 URLs 반환.
    main 서버가 결과를 받아 Instagram 포스팅(Step 8)을 수행함.
    """
    today      = _today_kst().strftime("%Y%m%d")
    yesterday  = (_today_kst() - timedelta(days=1)).strftime("%Y%m%d")
    langs      = req.langs or list(LANGUAGES)
    topic      = _get_topic(req.slot, req.topic, req.custom_topic)
    output_dir = _output_path()

    print(f"\n{'='*54}")
    print(f"[Worker] {topic['emoji']} {topic['topic_ko']}  |  langs={langs}  dry_run={req.dry_run}")
    print(f"{'='*54}")

    # ── Step 1: 폰트 ────────────────────────────────────────────────────────
    print("\n[1/7] 폰트 확인")
    try:
        F.ensure_fonts()
    except Exception as e:
        print(f"  ⚠ 폰트 오류 (계속): {e}")

    # ── Step 2: 표현 생성 (프리페치 폴백) ────────────────────────────────────
    print(f"\n[2/7] Claude API 표현 생성")
    all_data: dict[str, dict] = {}

    for lang in langs:
        print(f"  → {lang} 생성 중...")
        try:
            all_data[lang] = claude_gen.generate(lang, topic)
            print(f"  ✓ {lang}: {all_data[lang]['main_expression']}")
        except Exception as e:
            # 2순위: 프리페치 파일 (이벤트는 프리페치 없음)
            if not req.custom_topic:
                prefetched = claude_gen.load_prefetch(today, lang)
                if prefetched:
                    all_data[lang] = prefetched
                    print(f"  ⚠ Claude 실패, 프리페치 사용: {lang}  ({e})")
                    continue
            print(f"  ✗ {lang} 건너뜀 (Claude 실패): {e}")

    if not all_data:
        raise HTTPException(status_code=503, detail="표현 생성 전체 실패")

    # 오늘 데이터 JSON 저장 (일반 슬롯만, 이벤트는 저장 안 함)
    if not req.custom_topic:
        data_json = os.path.join(output_dir, f"data_{today}.json")
        with open(data_json, "w", encoding="utf-8") as f:
            json.dump({"topic": topic, "data": all_data}, f, ensure_ascii=False, indent=2)
        print(f"  ✓ 데이터 저장: {data_json}")
        _try_prefetch_tomorrow(langs, output_dir, all_data)

    # ── Step 3: 카드 렌더링 ─────────────────────────────────────────────────
    print(f"\n[3/7] 카드 이미지 렌더링")
    image_paths: dict[str, str] = {}
    vocab_paths: dict[str, str] = {}
    for lang in list(all_data.keys()):
        try:
            image_paths[lang] = card_renderer.render(all_data[lang], lang, topic)
            vocab_paths[lang] = card_renderer.render_vocab(all_data[lang], lang, topic)
            print(f"  ✓ {lang}: 표현카드 + 단어카드")
        except Exception as e:
            print(f"  ✗ {lang} 렌더링 실패 (건너뜀): {e}")
            all_data.pop(lang, None)

    # ── Step 4: TTS ─────────────────────────────────────────────────────────
    print(f"\n[4/7] TTS 음성 생성")
    expr_tts:  dict[str, str | None] = {}
    vocab_tts: dict[str, str | None] = {}
    for lang in image_paths:
        try:
            expr_tts[lang]  = tts_gen.generate_expression(
                all_data[lang]["main_expression"], lang, today,
                slot=req.slot or "default")
            vocab_tts[lang] = tts_gen.generate_vocab(
                all_data[lang].get("vocab", []), lang, today,
                slot=req.slot or "default")
            print(f"  ✓ {lang}: TTS 생성 완료")
        except Exception as e:
            print(f"  ⚠ {lang} TTS 실패 (건너뜀): {e}")
            expr_tts[lang]  = None
            vocab_tts[lang] = None

    # ── Step 5: 숏릴스 MP4 ─────────────────────────────────────────────────
    print(f"\n[5/7] 숏릴스 생성")

    # 훅·아웃트로 프레임 생성 (언어 공통 아웃트로, 언어별 훅)
    outro_png: str | None = None
    try:
        outro_png = card_renderer.render_outro_frame(today)
    except Exception as e:
        print(f"  ⚠ 아웃트로 프레임 생성 실패 (건너뜀): {e}")

    short_reel_paths: dict[str, str] = {}
    for lang in image_paths:
        try:
            hook_png: str | None = None
            try:
                hook_png = card_renderer.render_hook_frame(lang, today)
            except Exception as e:
                print(f"  ⚠ {lang} 훅 프레임 생성 실패 (건너뜀): {e}")

            path = reel_renderer.render_short(
                image_paths[lang], vocab_paths[lang],
                expr_tts.get(lang), vocab_tts.get(lang),
                lang, today,
                hook_path=hook_png,
                outro_path=outro_png,
            )
            short_reel_paths[lang] = path
            print(f"  ✓ {lang}: {os.path.basename(path)}")
        except Exception as e:
            print(f"  ✗ {lang} 숏릴스 실패 (건너뜀): {e}")

    # ── Step 6: 전날 카드 수집 (일반 슬롯만) ────────────────────────────────
    print(f"\n[6/7] 전날 종합 캐러셀 준비 (어제: {yesterday})")
    recap_pngs: list[str] = []
    yest_topic    = topic     # 초기값 (recap 없을 때 fallback)
    yest_all_data = all_data  # 초기값
    if not req.custom_topic and len(langs) == len(LANGUAGES):
        try:
            yest_imgs, yest_vocs = reel_renderer.find_yesterday_cards(yesterday)
            if len(yest_imgs) == 3:
                yest_json = os.path.join(output_dir, f"data_{yesterday}.json")
                yest_all_data = all_data
                yest_topic    = topic
                if os.path.exists(yest_json):
                    with open(yest_json, "r", encoding="utf-8") as f:
                        saved = json.load(f)
                        yest_all_data = saved.get("data", all_data)
                        yest_topic    = saved.get("topic", topic)
                    print(f"  ✓ 어제 데이터 로드")
                cover_path = card_renderer.render_recap_cover(
                    yest_all_data, yest_topic, yesterday)
                recap_pngs.append(cover_path)
                for lang in ("en", "zh", "ja"):
                    if lang in yest_imgs:
                        recap_pngs.append(yest_imgs[lang])
                    if lang in yest_vocs:
                        recap_pngs.append(yest_vocs[lang])
                print(f"  ✓ 캐러셀 {len(recap_pngs)}장 준비")
            else:
                print(f"  ⚠ 전날 카드 {len(yest_imgs)}/3개, 건너뜀")
        except Exception as e:
            print(f"  ⚠ 전날 카드 탐색 실패 (건너뜀): {e}")
    else:
        print(f"  → 이벤트/단일 언어 모드: 캐러셀 생략")

    # ── dry-run 종료 ─────────────────────────────────────────────────────────
    if req.dry_run:
        print("\n[dry-run] Cloudinary 업로드 생략")
        return {
            "status": "dry_run",
            "today": today,
            "yesterday": yesterday,
            "topic": topic,
            "all_data": all_data,
            "recap_topic": yest_topic,
            "recap_data":  yest_all_data,
            "langs_done": list(short_reel_paths.keys()),
            "recap_pngs_count": len(recap_pngs),
            "short_reel_urls": {},
            "recap_card_urls": [],
            "dry_run": True,
        }

    # ── Step 7: Cloudinary 업로드 ────────────────────────────────────────────
    print(f"\n[7/7] Cloudinary 업로드")
    short_reel_urls: dict[str, str] = {}
    for lang, path in short_reel_paths.items():
        try:
            url = cloudinary_up.upload_video(path, f"short_{lang}", today)
            short_reel_urls[lang] = url
            print(f"  ✓ {lang} 숏릴스 업로드")
        except Exception as e:
            print(f"  ✗ {lang} 숏릴스 업로드 실패: {e}")

    recap_card_urls: list[str] = []
    if recap_pngs:
        _lang_seq   = ("all", "en", "en", "zh", "zh", "ja", "ja")
        _suffix_seq = ("cover", "expr", "vocab", "expr", "vocab", "expr", "vocab")
        for i, png in enumerate(recap_pngs):
            try:
                url = cloudinary_up.upload(
                    png, _lang_seq[i], "recap",
                    suffix=_suffix_seq[i], date_str=yesterday)
                recap_card_urls.append(url)
            except Exception as e:
                print(f"  ⚠ 캐러셀 슬라이드 {i+1} 업로드 실패: {e}")

    print(f"\n✅ Worker 완료: 릴스 {len(short_reel_urls)}개, 캐러셀 {len(recap_card_urls)}장")

    return {
        "status": "ok",
        "slot": req.slot,
        "today": today,
        "yesterday": yesterday,
        "topic": topic,
        "all_data": all_data,
        "recap_topic": yest_topic,
        "recap_data":  yest_all_data,
        "short_reel_urls": short_reel_urls,
        "recap_card_urls": recap_card_urls,
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
