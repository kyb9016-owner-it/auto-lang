"""
LangCard Studio — 텔레그램 봇 (main 서버용)

명령어:
  /morning  — 아침 슬롯 실행 (인사 & 소개)
  /lunch    — 점심 슬롯 실행 (카페 & 식당)
  /evening  — 저녁 슬롯 실행 (여행 & 쇼핑)
  /dry [morning|lunch|evening]  — 드라이런 (Instagram 포스팅 없음)
  /promo    — 고정 캐러셀 2종 포스팅
  /status   — Worker 헬스 + 마지막 실행 정보

사용법:
  python3 bot/telegram_bot.py
"""

import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env", override=True)

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

ROOT = Path(__file__).parent.parent

# 마지막 실행 정보 (메모리)
_last_run: dict = {}

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

def _run_dispatch(slot: str, dry_run: bool = False) -> tuple[bool, str]:
    """
    dispatch.py를 서브프로세스로 실행.
    Returns: (success: bool, output: str)
    """
    cmd = [sys.executable, str(ROOT / "dispatch.py"), "--slot", slot]
    if dry_run:
        cmd.append("--dry-run")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=660,   # 11분
            cwd=str(ROOT),
        )
        output = (result.stdout + result.stderr).strip()
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, "⏱ 시간 초과 (11분)"
    except Exception as e:
        return False, f"실행 오류: {e}"


def _run_promo() -> tuple[bool, str]:
    """promo.py 실행"""
    try:
        result = subprocess.run(
            [sys.executable, str(ROOT / "promo.py")],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(ROOT),
        )
        output = (result.stdout + result.stderr).strip()
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, "⏱ 시간 초과 (5분)"
    except Exception as e:
        return False, f"실행 오류: {e}"


def _get_status_text() -> str:
    """Worker 헬스 + 마지막 실행 정보 텍스트"""
    # dispatch 모듈 import (main 서버에서 실행)
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
    tail = output[-1000:] if len(output) > 1000 else output
    icon = "✅" if success else "❌"
    await update.message.reply_text(f"{icon} 아침 슬롯 완료\n\n```\n{tail}\n```",
                                    parse_mode="Markdown")


@owner_only
async def cmd_lunch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("☕ 점심 슬롯 실행 중... ⏳")
    success, output = _run_dispatch("lunch")
    _last_run.update(slot="lunch", time=datetime.now().strftime("%Y-%m-%d %H:%M"),
                     result="✅ 성공" if success else "❌ 실패")
    tail = output[-1000:] if len(output) > 1000 else output
    icon = "✅" if success else "❌"
    await update.message.reply_text(f"{icon} 점심 슬롯 완료\n\n```\n{tail}\n```",
                                    parse_mode="Markdown")


@owner_only
async def cmd_evening(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✈️ 저녁 슬롯 실행 중... ⏳")
    success, output = _run_dispatch("evening")
    _last_run.update(slot="evening", time=datetime.now().strftime("%Y-%m-%d %H:%M"),
                     result="✅ 성공" if success else "❌ 실패")
    tail = output[-1000:] if len(output) > 1000 else output
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
    tail = output[-1000:] if len(output) > 1000 else output
    icon = "✅" if success else "❌"
    await update.message.reply_text(f"{icon} 드라이런 완료\n\n```\n{tail}\n```",
                                    parse_mode="Markdown")


@owner_only
async def cmd_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📌 프로모 캐러셀 포스팅 중... ⏳")
    success, output = _run_promo()
    tail = output[-1000:] if len(output) > 1000 else output
    icon = "✅" if success else "❌"
    msg = f"{icon} 프로모 완료\n\n```\n{tail}\n```"
    if success:
        msg += "\n\n💡 Instagram 앱에서 두 게시물을 프로필 상단에 핀 고정해주세요."
    await update.message.reply_text(msg, parse_mode="Markdown")


@owner_only
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = _get_status_text()
    await update.message.reply_text(text)


@owner_only
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 LangCard Studio 봇 명령어\n\n"
        "/morning — 아침 슬롯 실행 🌅\n"
        "/lunch — 점심 슬롯 실행 ☕\n"
        "/evening — 저녁 슬롯 실행 ✈️\n"
        "/dry [morning|lunch|evening] — 드라이런 🧪\n"
        "/promo — 고정 캐러셀 2종 포스팅 📌\n"
        "/status — 서버 상태 확인 🔍\n"
        "/help — 이 메시지",
    )


# ── 메인 ──────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("morning", cmd_morning))
    app.add_handler(CommandHandler("lunch",   cmd_lunch))
    app.add_handler(CommandHandler("evening", cmd_evening))
    app.add_handler(CommandHandler("dry",     cmd_dry))
    app.add_handler(CommandHandler("promo",   cmd_promo))
    app.add_handler(CommandHandler("status",  cmd_status))
    app.add_handler(CommandHandler("help",    cmd_help))
    app.add_handler(CommandHandler("start",   cmd_help))

    logger.info(f"봇 시작 (owner_id={TELEGRAM_OWNER_ID})")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
