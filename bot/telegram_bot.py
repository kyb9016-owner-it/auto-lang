"""
LangCard Studio — 텔레그램 봇 (main 서버용)

명령어:
  /morning  — 아침 슬롯 실행 (인사 & 소개)
  /lunch    — 점심 슬롯 실행 (카페 & 식당)
  /evening  — 저녁 슬롯 실행 (여행 & 쇼핑)
  /dry [morning|lunch|evening]  — 드라이런 (Instagram 포스팅 없음)
  /promo    — 고정 캐러셀 2종 포스팅
  /event [주제]  — 이벤트/재밌는 표현 포스팅
  /lang <slot> <en|zh|ja>  — 특정 언어만 단독 포스팅
  /status   — Worker 헬스 + 마지막 실행 정보
  /log [n]  — cron 로그 최근 n줄 (기본 30)
  /update   — git pull + 봇 재시작
  /restart  — Worker 서비스 재시작
  /cron     — 다음 자동 실행까지 남은 시간
  /topic    — 오늘 슬롯별 주제 확인
  /history [en|zh|ja]  — 최근 사용 표현 목록
  /prefetch — 내일 표현 미리 생성

사용법:
  python3 bot/telegram_bot.py
"""

import logging
import os
import random
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env", override=True)

import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ── 로깅 ──────────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── 설정 ──────────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN    = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_OWNER_ID = int(os.environ["TELEGRAM_OWNER_ID"])
WORKER_URL        = os.environ.get("WORKER_URL", "http://localhost:8000")
WORKER_SECRET     = os.environ.get("WORKER_SECRET", "")

ROOT = Path(__file__).parent.parent

# 마지막 실행 정보 (메모리)
_last_run: dict = {}

# 이벤트 주제 목록
_EVENT_TOPICS = [
    {"topic_ko": "슬랭 & 유행어",      "topic_en": "Slang & Trending Phrases",    "badge": "TREND",  "emoji": "🔥"},
    {"topic_ko": "영화 & 드라마 대사", "topic_en": "Movie & Drama Quotes",         "badge": "DRAMA",  "emoji": "🎬"},
    {"topic_ko": "직장 & 회사생활",    "topic_en": "Office & Work Life",            "badge": "OFFICE", "emoji": "💼"},
    {"topic_ko": "SNS & 인터넷 밈",    "topic_en": "Social Media & Internet Memes", "badge": "MEME",   "emoji": "📱"},
    {"topic_ko": "파티 & 축하",        "topic_en": "Party & Celebration",           "badge": "PARTY",  "emoji": "🎉"},
    {"topic_ko": "연애 & 데이트",      "topic_en": "Romance & Dating",              "badge": "LOVE",   "emoji": "💕"},
    {"topic_ko": "스포츠 & 응원",      "topic_en": "Sports & Cheering",             "badge": "SPORT",  "emoji": "⚽"},
    {"topic_ko": "음식 & 먹방",        "topic_en": "Food & Mukbang",                "badge": "FOOD",   "emoji": "🍜"},
]


# ── 인증 데코레이터 ─────────────────────────────────────────────────────────────

def owner_only(func):
    """TELEGRAM_OWNER_ID 외 요청 무시"""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != TELEGRAM_OWNER_ID:
            logger.warning(f"무시: user_id={update.effective_user.id}")
            return
        return await func(update, context)
    wrapper.__name__ = func.__name__
    return wrapper


# ── dispatch 호출 헬퍼 ────────────────────────────────────────────────────────

def _run_dispatch(slot: str, dry_run: bool = False,
                  lang_filter: str | None = None) -> tuple[bool, str]:
    cmd = [sys.executable, str(ROOT / "dispatch.py"), "--slot", slot]
    if dry_run:
        cmd.append("--dry-run")
    if lang_filter:
        cmd.extend(["--lang", lang_filter])
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=660, cwd=str(ROOT))
        output = (result.stdout + result.stderr).strip()
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, "⏱ 시간 초과 (11분)"
    except Exception as e:
        return False, f"실행 오류: {e}"


def _run_event(topic: dict) -> tuple[bool, str]:
    cmd = [
        sys.executable, str(ROOT / "dispatch.py"),
        "--event-topic-ko", topic["topic_ko"],
        "--event-topic-en", topic["topic_en"],
        "--event-badge",    topic.get("badge", "EVENT"),
        "--event-emoji",    topic.get("emoji", "🎉"),
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=660, cwd=str(ROOT))
        output = (result.stdout + result.stderr).strip()
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, "⏱ 시간 초과 (11분)"
    except Exception as e:
        return False, f"실행 오류: {e}"


def _run_promo() -> tuple[bool, str]:
    try:
        result = subprocess.run(
            [sys.executable, str(ROOT / "promo.py")],
            capture_output=True, text=True, timeout=300, cwd=str(ROOT))
        output = (result.stdout + result.stderr).strip()
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, "⏱ 시간 초과 (5분)"
    except Exception as e:
        return False, f"실행 오류: {e}"


def _worker_get(path: str, timeout: int = 10) -> dict:
    resp = requests.get(
        f"{WORKER_URL}{path}",
        headers={"Authorization": f"Bearer {WORKER_SECRET}"},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


def _worker_post(path: str, body: dict | None = None, timeout: int = 10) -> dict:
    resp = requests.post(
        f"{WORKER_URL}{path}",
        json=body or {},
        headers={"Authorization": f"Bearer {WORKER_SECRET}"},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


def _get_status_text() -> str:
    sys.path.insert(0, str(ROOT))
    try:
        from dispatch import check_health
        health = check_health()
    except Exception as e:
        health = {"status": "error", "detail": str(e)}

    if health.get("status") == "ok":
        uptime = health.get("uptime_sec", 0)
        h, m = divmod(uptime // 60, 60)
        worker_text = f"✅ Worker 정상 (업타임: {h}시간 {m}분)"
    else:
        worker_text = f"❌ Worker 오류: {health.get('detail', '알 수 없음')}"

    last = _last_run
    if last:
        last_text = (
            f"\n\n📋 마지막 실행\n"
            f"  슬롯: {last.get('slot', '-')}\n"
            f"  시각: {last.get('time', '-')}\n"
            f"  결과: {last.get('result', '-')}"
        )
    else:
        last_text = "\n\n📋 마지막 실행: 없음"

    return worker_text + last_text


# ── 명령어 핸들러 ─────────────────────────────────────────────────────────────

@owner_only
async def cmd_morning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🌅 아침 슬롯 실행 중... ⏳\n(완료까지 약 3-5분 소요)")
    success, output = _run_dispatch("morning")
    _last_run.update(slot="morning", time=datetime.now().strftime("%Y-%m-%d %H:%M"),
                     result="✅ 성공" if success else "❌ 실패")
    tail = output[-1500:] if len(output) > 1500 else output
    icon = "✅" if success else "❌"
    await update.message.reply_text(f"{icon} 아침 슬롯 완료\n\n```\n{tail}\n```",
                                    parse_mode="Markdown")


@owner_only
async def cmd_lunch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("☕ 점심 슬롯 실행 중... ⏳")
    success, output = _run_dispatch("lunch")
    _last_run.update(slot="lunch", time=datetime.now().strftime("%Y-%m-%d %H:%M"),
                     result="✅ 성공" if success else "❌ 실패")
    tail = output[-1500:] if len(output) > 1500 else output
    icon = "✅" if success else "❌"
    await update.message.reply_text(f"{icon} 점심 슬롯 완료\n\n```\n{tail}\n```",
                                    parse_mode="Markdown")


@owner_only
async def cmd_evening(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✈️ 저녁 슬롯 실행 중... ⏳")
    success, output = _run_dispatch("evening")
    _last_run.update(slot="evening", time=datetime.now().strftime("%Y-%m-%d %H:%M"),
                     result="✅ 성공" if success else "❌ 실패")
    tail = output[-1500:] if len(output) > 1500 else output
    icon = "✅" if success else "❌"
    await update.message.reply_text(f"{icon} 저녁 슬롯 완료\n\n```\n{tail}\n```",
                                    parse_mode="Markdown")


@owner_only
async def cmd_dry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """사용법: /dry morning|lunch|evening"""
    args = context.args
    slot = args[0] if args and args[0] in ("morning", "lunch", "evening") else "morning"
    await update.message.reply_text(f"🧪 드라이런: {slot} ⏳")
    success, output = _run_dispatch(slot, dry_run=True)
    tail = output[-1500:] if len(output) > 1500 else output
    icon = "✅" if success else "❌"
    await update.message.reply_text(f"{icon} 드라이런 완료\n\n```\n{tail}\n```",
                                    parse_mode="Markdown")


@owner_only
async def cmd_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📌 프로모 캐러셀 포스팅 중... ⏳")
    success, output = _run_promo()
    tail = output[-1500:] if len(output) > 1500 else output
    icon = "✅" if success else "❌"
    msg = f"{icon} 프로모 완료\n\n```\n{tail}\n```"
    if success:
        msg += "\n\n💡 Instagram 앱에서 두 게시물을 프로필 상단에 핀 고정해주세요."
    await update.message.reply_text(msg, parse_mode="Markdown")


@owner_only
async def cmd_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    사용법:
      /event          → 랜덤 이벤트 주제
      /event 슬랭     → 슬랭 & 유행어
      /event 직장     → 직장 & 회사생활
      /event 직접입력 → 커스텀 주제
    """
    keyword = " ".join(context.args).strip() if context.args else ""

    topic = None
    if keyword:
        for t in _EVENT_TOPICS:
            if keyword in t["topic_ko"] or keyword.lower() in t["topic_en"].lower():
                topic = t
                break
        if not topic:
            # 키워드를 커스텀 주제로 사용
            topic = {
                "topic_ko":   keyword,
                "topic_en":   keyword,
                "badge":      "EVENT",
                "emoji":      "🎉",
                "theme_slot": "morning",
            }
    else:
        topic = random.choice(_EVENT_TOPICS)

    await update.message.reply_text(
        f"{topic['emoji']} 이벤트 포스팅 시작!\n"
        f"주제: {topic['topic_ko']}\n\n"
        f"완료까지 약 3-5분 소요... ⏳"
    )
    success, output = _run_event(topic)
    _last_run.update(slot=f"event:{topic['topic_ko']}",
                     time=datetime.now().strftime("%Y-%m-%d %H:%M"),
                     result="✅ 성공" if success else "❌ 실패")
    tail = output[-1500:] if len(output) > 1500 else output
    icon = "✅" if success else "❌"
    await update.message.reply_text(
        f"{icon} 이벤트 완료 ({topic['topic_ko']})\n\n```\n{tail}\n```",
        parse_mode="Markdown"
    )


@owner_only
async def cmd_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """사용법: /lang morning|lunch|evening en|zh|ja"""
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "사용법: /lang [morning|lunch|evening] [en|zh|ja]\n예) /lang morning en"
        )
        return
    slot = args[0] if args[0] in ("morning", "lunch", "evening") else None
    lang = args[1] if args[1] in ("en", "zh", "ja") else None
    if not slot or not lang:
        await update.message.reply_text("슬롯: morning/lunch/evening   언어: en/zh/ja")
        return

    lang_flag = {"en": "🇺🇸", "zh": "🇨🇳", "ja": "🇯🇵"}.get(lang, "")
    await update.message.reply_text(f"{lang_flag} {slot} — {lang} 단독 포스팅 중... ⏳")
    success, output = _run_dispatch(slot, lang_filter=lang)
    _last_run.update(slot=f"{slot}:{lang}", time=datetime.now().strftime("%Y-%m-%d %H:%M"),
                     result="✅ 성공" if success else "❌ 실패")
    tail = output[-1500:] if len(output) > 1500 else output
    icon = "✅" if success else "❌"
    await update.message.reply_text(f"{icon} {lang_flag} {lang} 단독 포스팅 완료\n\n```\n{tail}\n```",
                                    parse_mode="Markdown")


@owner_only
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = _get_status_text()
    await update.message.reply_text(text)


@owner_only
async def cmd_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """사용법: /log [줄수] (기본 30, 최대 100)"""
    n = 30
    if context.args:
        try:
            n = min(int(context.args[0]), 100)
        except ValueError:
            pass

    log_path = "/var/log/langcard/cron.log"
    try:
        result = subprocess.run(
            ["tail", f"-{n}", log_path],
            capture_output=True, text=True, timeout=10
        )
        text = result.stdout or "(로그 없음)"
    except Exception as e:
        text = f"로그 읽기 실패: {e}"

    tail = text[-3000:] if len(text) > 3000 else text
    await update.message.reply_text(
        f"📋 cron.log 최근 {n}줄\n\n```\n{tail}\n```",
        parse_mode="Markdown"
    )


@owner_only
async def cmd_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """git pull 후 봇 재시작"""
    await update.message.reply_text("🔄 코드 업데이트 중...")
    result = subprocess.run(
        ["git", "pull", "origin", "main"],
        capture_output=True, text=True, timeout=60, cwd=str(ROOT)
    )
    output = (result.stdout + result.stderr).strip()
    if result.returncode == 0:
        await update.message.reply_text(
            f"✅ pull 완료\n```\n{output}\n```\n\n재시작 중...",
            parse_mode="Markdown"
        )
        subprocess.Popen(["systemctl", "restart", "langcard-bot"])
    else:
        await update.message.reply_text(
            f"❌ pull 실패\n```\n{output}\n```",
            parse_mode="Markdown"
        )


@owner_only
async def cmd_restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Worker 서버 재시작"""
    await update.message.reply_text("🔄 Worker 재시작 중...")
    try:
        data = _worker_post("/restart", timeout=15)
        await update.message.reply_text(f"✅ Worker 재시작 요청 완료\n{data.get('message', '')}")
    except Exception as e:
        await update.message.reply_text(f"❌ Worker 재시작 실패: {e}")


@owner_only
async def cmd_cron(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """다음 자동 실행까지 남은 시간"""
    now = datetime.now(timezone.utc)
    kst = timezone(timedelta(hours=9))

    slots = [
        ("morning 🌅", 23, 0),
        ("lunch   ☕", 3,  0),
        ("evening ✈️", 11, 0),
    ]
    lines = ["⏰ 다음 자동 실행 시간\n"]
    for name, h, m in slots:
        next_run = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
        diff = next_run - now
        hours, rem = divmod(int(diff.total_seconds()), 3600)
        minutes = rem // 60
        kst_time = next_run.astimezone(kst).strftime("%m/%d %H:%M KST")
        lines.append(f"{name}: {kst_time} (약 {hours}시간 {minutes}분 후)")

    await update.message.reply_text("\n".join(lines))


@owner_only
async def cmd_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """오늘 슬롯별 주제 확인"""
    sys.path.insert(0, str(ROOT))
    from config import SLOT_CONFIG, get_today_topic
    today_topic = get_today_topic()
    lines = [f"📅 오늘의 주제: {today_topic['emoji']} {today_topic['topic_ko']}\n"]
    for slot, cfg in SLOT_CONFIG.items():
        lines.append(f"{cfg['emoji']} {slot}: {cfg['topic_ko']}")
    lines.append(f"\n🎉 이벤트 주제 목록:")
    for t in _EVENT_TOPICS:
        lines.append(f"  {t['emoji']} {t['topic_ko']}")
    lines.append("\n사용: /event 슬랭  또는  /event (랜덤)")
    await update.message.reply_text("\n".join(lines))


@owner_only
async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """사용법: /history [en|zh|ja]"""
    lang = context.args[0] if context.args and context.args[0] in ("en", "zh", "ja") else None
    try:
        path = f"/history?lang={lang}" if lang else "/history"
        data = _worker_get(path)
        lines = ["📝 최근 사용 표현\n"]
        if lang:
            exprs = data.get("expressions", [])[-15:]
            flag = {"en": "🇺🇸", "zh": "🇨🇳", "ja": "🇯🇵"}.get(lang, "")
            lines.append(f"{flag} {lang}:")
            for e in exprs:
                lines.append(f"  · {e}")
        else:
            for l in ("en", "zh", "ja"):
                flag = {"en": "🇺🇸", "zh": "🇨🇳", "ja": "🇯🇵"}.get(l, "")
                exprs = data.get(l, [])[-5:]
                lines.append(f"\n{flag} {l}:")
                for e in exprs:
                    lines.append(f"  · {e}")
        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        await update.message.reply_text(f"❌ 히스토리 조회 실패: {e}")


@owner_only
async def cmd_prefetch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """내일 표현 미리 생성. /prefetch force 로 강제 재생성"""
    force = "force" in (context.args or [])
    await update.message.reply_text("🔄 내일 표현 미리 생성 중... ⏳ (약 1분)")
    try:
        data = _worker_post("/prefetch", {"force": force}, timeout=120)
        status   = data.get("status")
        topic    = data.get("topic", {})
        langs    = data.get("langs", [])
        tomorrow = data.get("tomorrow", "")
        if status == "already_exists":
            msg = (f"ℹ️ 이미 존재: {tomorrow}\n"
                   f"주제: {topic.get('topic_ko', '-')}\n"
                   f"언어: {', '.join(langs)}\n\n"
                   f"강제 재생성: /prefetch force")
        else:
            msg = (f"✅ 프리페치 완료: {tomorrow}\n"
                   f"주제: {topic.get('topic_ko', '-')}\n"
                   f"언어: {', '.join(langs)}")
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"❌ 프리페치 실패: {e}")


@owner_only
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 LangCard Studio 봇 명령어\n\n"
        "── 포스팅 ──\n"
        "/morning — 아침 슬롯 🌅\n"
        "/lunch   — 점심 슬롯 ☕\n"
        "/evening — 저녁 슬롯 ✈️\n"
        "/dry [morning|lunch|evening] — 드라이런 🧪\n"
        "/lang [슬롯] [en|zh|ja] — 특정 언어만 🌐\n"
        "/event [주제] — 이벤트/재밌는 표현 🎉\n"
        "/promo — 고정 캐러셀 📌\n\n"
        "── 관리 ──\n"
        "/status  — 서버 상태 🔍\n"
        "/log [n] — cron 로그 📋\n"
        "/cron    — 다음 실행 시간 ⏰\n"
        "/topic   — 오늘 주제 + 이벤트 목록 📅\n"
        "/history [en|zh|ja] — 표현 히스토리 📝\n"
        "/prefetch [force] — 내일 표현 미리 생성 ⚡\n"
        "/update  — 코드 업데이트 + 재시작 🔄\n"
        "/restart — Worker 재시작 🔁\n"
        "/help    — 이 메시지"
    )


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("morning",  cmd_morning))
    app.add_handler(CommandHandler("lunch",    cmd_lunch))
    app.add_handler(CommandHandler("evening",  cmd_evening))
    app.add_handler(CommandHandler("dry",      cmd_dry))
    app.add_handler(CommandHandler("promo",    cmd_promo))
    app.add_handler(CommandHandler("event",    cmd_event))
    app.add_handler(CommandHandler("lang",     cmd_lang))
    app.add_handler(CommandHandler("status",   cmd_status))
    app.add_handler(CommandHandler("log",      cmd_log))
    app.add_handler(CommandHandler("update",   cmd_update))
    app.add_handler(CommandHandler("restart",  cmd_restart))
    app.add_handler(CommandHandler("cron",     cmd_cron))
    app.add_handler(CommandHandler("topic",    cmd_topic))
    app.add_handler(CommandHandler("history",  cmd_history))
    app.add_handler(CommandHandler("prefetch", cmd_prefetch))
    app.add_handler(CommandHandler("help",     cmd_help))
    app.add_handler(CommandHandler("start",    cmd_help))

    logger.info(f"봇 시작 (owner_id={TELEGRAM_OWNER_ID})")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
