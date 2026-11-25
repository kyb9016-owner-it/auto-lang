#!/usr/bin/env python3
"""맥에서 실행: 구독(`claude -p`)으로 HOOK JSON을 미리 만들어 서버 큐에 올린다.

stdlib만 사용. 유료 API 키는 자식 프로세스 env에서 제거한다.
"""
from __future__ import annotations
import argparse
import datetime as dt
import glob
import json
import os
import random
import re
import shutil
import string
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, ROOT)

import config  # noqa: E402
from generator.hook_prompt import HOOK_SYSTEM, HOOK_JSON_SCHEMA, build_hook_prompt, validate_hook  # noqa: E402
from generator.history import is_similar_wrong  # noqa: E402

REMOTE_DIR = "/opt/auto-lang"
REMOTE_QUEUE = f"{REMOTE_DIR}/queue/hook"
ANTHROPIC_AUTH_ENV = ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL",
                       "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX"]
KEYCHAIN_SERVICE = "ai-subscription-worker-oauth"
SUBSCRIPTION_AUTH_METHODS = {"claude.ai", "oauth_token"}
DEFAULT_MODEL = "claude-opus-5-5"
REELS_DIR = os.path.join(ROOT, "reels")
STYLE_HISTORY_PATH = os.path.expanduser("~/.local/state/langcard/style_history.json")
STYLE_HISTORY_MAX = 30
STYLE_AVOID_LAST = 2
RENDER_TIMEOUT = 1200


# ── 순수 함수 ────────────────────────────────────────────────────────

def build_claude_args(model: str, system_prompt: str, json_schema: dict | None) -> list[str]:
    """헤드리스 `claude -p` 인자. 🔴 --bare 금지(API키 전용). 도구 0개·설정 미적용."""
    args = ["-p"]
    if model:
        args += ["--model", model]
    args += ["--no-session-persistence", "--strict-mcp-config", "--system-prompt", system_prompt]
    if json_schema:
        args += ["--json-schema", json.dumps(json_schema)]
    args += ["--output-format", "json", "--tools", "", "--safe-mode", "--setting-sources", ""]
    return args


def subscription_env(env: dict, oauth_token: str | None = None) -> dict:
    """Anthropic 인증 변수를 제거(유료 과금 방지) + (있으면) 워커 OAuth 토큰 주입."""
    out = {k: v for k, v in env.items() if k not in ANTHROPIC_AUTH_ENV}
    if oauth_token:
        out["CLAUDE_CODE_OAUTH_TOKEN"] = oauth_token
    return out


def parse_claude_output(stdout: str) -> dict:
    """`claude -p --output-format json` 출력에서 HOOK dict 추출. 실패 시 ValueError."""
    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError:
        raise ValueError(f"claude -p 출력이 JSON이 아닙니다: {stdout[:300]}")
    if not isinstance(parsed, dict):
        raise ValueError("claude -p 출력이 객체가 아닙니다")
    if parsed.get("is_error"):
        raise ValueError(f"claude -p 오류 응답: {json.dumps(parsed, ensure_ascii=False)[:500]}")
    so = parsed.get("structured_output")
    if isinstance(so, dict):
        return so
    text = parsed.get("result")
    if isinstance(text, str) and text.strip():
        t = text.strip()
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```$", "", t).strip()
        try:
            obj = json.loads(t)
        except json.JSONDecodeError:
            raise ValueError(f"result를 JSON으로 파싱 못 함: {t[:300]}")
        if isinstance(obj, dict):
            return obj
    raise ValueError("structured_output/result 없음")


def wrongs_from_history(history: dict, lang: str, limit: int = 200) -> list[str]:
    entries = history.get(f"{lang}_hook", [])[-limit:]
    return [e["wrong"] for e in entries if isinstance(e, dict) and "wrong" in e]


def list_styles(reels_dir: str, allowed: list[str] | None = None) -> list[str]:
    """reels/styles/*/index.html 이 있는 스타일(이름이 _로 시작하면 제외). allowed가 있으면 교집합."""
    found = sorted(
        os.path.basename(os.path.dirname(p))
        for p in glob.glob(os.path.join(reels_dir, "styles", "*", "index.html"))
        if not os.path.basename(os.path.dirname(p)).startswith("_")
    )
    if allowed:
        found = [s for s in found if s in set(allowed)]
    return found


def choose_style(available: list[str], recent: list[str], rng: random.Random) -> str:
    """최근 사용 마지막 2개를 제외하고 무작위. 후보가 없으면 전체에서 무작위."""
    if not available:
        raise ValueError("사용 가능한 스타일이 없습니다")
    avoid = set(recent[-STYLE_AVOID_LAST:]) if recent else set()
    pool = [s for s in available if s not in avoid] or list(available)
    return rng.choice(pool)


def load_style_history(path: str | None = None) -> list[str]:
    path = path or STYLE_HISTORY_PATH
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:  # noqa: BLE001
        return []
    return [x for x in data if isinstance(x, str)][-STYLE_HISTORY_MAX:] if isinstance(data, list) else []


def record_style(style: str, path: str | None = None) -> list[str]:
    """렌더 성공한 스타일을 기록에 추가(최근 30개 유지, 디렉터리 없으면 생성). 갱신된 목록 반환."""
    path = path or STYLE_HISTORY_PATH
    hist = (load_style_history(path) + [style])[-STYLE_HISTORY_MAX:]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False)
    os.replace(tmp, path)
    return hist


def missing_videos(names: list[str]) -> list[str]:
    """파일명 목록에서 같은 이름 .mp4가 없는 .json 이름들(정렬)."""
    have = set(names)
    return sorted(n for n in names if n.endswith(".json") and n[: -len(".json")] + ".mp4" not in have)


def parse_queue_listing(text: str) -> dict[str, list[str]]:
    """`ls` 출력(줄마다 `<lang>/<name>`) → {lang: [name...]}."""
    out: dict[str, list[str]] = {}
    for line in text.splitlines():
        line = line.strip()
        if "/" not in line:
            continue
        lang, name = line.split("/", 1)
        if lang and name and "/" not in name:
            out.setdefault(lang, []).append(name)
    return out


# ── 맥 환경 ──────────────────────────────────────────────────────────

def read_oauth_token() -> str | None:
    """키체인의 워커 토큰(없으면 None → 일반 로그인). 값은 출력 금지.
    맥이 아니면(미니PC 리눅스, 2026-11-25) 키체인이 없으므로 환경변수 CLAUDE_CODE_OAUTH_TOKEN만 본다."""
    if sys.platform != "darwin":
        tok = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
        return tok if tok.startswith("sk-ant-oat") else None
    try:
        r = subprocess.run(["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
                           capture_output=True, text=True, timeout=10)
    except Exception:  # noqa: BLE001
        return None
    tok = (r.stdout or "").strip() if r.returncode == 0 else ""
    return tok if tok.startswith("sk-ant-oat") else None


def assert_subscription_auth(env: dict) -> None:
    try:
        r = subprocess.run(["claude", "auth", "status"], env=env, capture_output=True,
                           text=True, timeout=30)
        method = json.loads(r.stdout).get("authMethod")
    except Exception as e:  # noqa: BLE001
        print(f"구독 인증 확인 실패: {e}", file=sys.stderr)
        sys.exit(2)
    if method not in SUBSCRIPTION_AUTH_METHODS:
        print(f"구독 인증이 아닙니다(authMethod={method}) — 유료 과금 방지를 위해 중단.", file=sys.stderr)
        sys.exit(2)


def run_claude(prompt: str, model: str, env: dict) -> dict:
    cwd = tempfile.mkdtemp(prefix="hook-fill-")
    try:
        r = subprocess.run(["claude"] + build_claude_args(model, HOOK_SYSTEM, HOOK_JSON_SCHEMA),
                           cwd=cwd, env=env, input=prompt, capture_output=True, text=True,
                           timeout=300)
        if r.returncode != 0:
            raise RuntimeError(f"claude -p 종료 코드 {r.returncode}: {(r.stderr or '')[:500]}")
        return parse_claude_output(r.stdout)
    finally:
        shutil.rmtree(cwd, ignore_errors=True)


# ── 원격 ─────────────────────────────────────────────────────────────

def ssh(host: str, cmd: str) -> str:
    r = subprocess.run(["ssh", host, cmd], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"ssh 실패({cmd[:60]}): {(r.stderr or '')[:300]}")
    return r.stdout


def remote_queue_state(host: str, lang: str) -> tuple[int, list[str]]:
    """원격 큐의 (파일 수, 그 안의 wrong 목록)."""
    out = ssh(host, f"ls {REMOTE_QUEUE}/{lang}/*.json 2>/dev/null | wc -l").strip()
    n = int(out or 0)
    wrongs: list[str] = []
    if n:
        # 파일별 JSON을 한 줄씩 받기 위해 jq 없이 python 대신 cat 후 로컬 파싱
        raw = ssh(host, f"for f in {REMOTE_QUEUE}/{lang}/*.json; do cat \"$f\"; echo; echo '@@SEP@@'; done")
        for chunk in raw.split("@@SEP@@"):
            chunk = chunk.strip()
            if not chunk:
                continue
            try:
                wrongs.append(json.loads(chunk)["data"]["wrong"])
            except Exception:  # noqa: BLE001
                pass
    return n, wrongs


def new_queue_name() -> str:
    """확장자 없는 큐 항목 이름(json·mp4 공용)."""
    stamp = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    return f"{stamp}_{''.join(random.choices(string.ascii_lowercase + string.digits, k=6))}"


def push_file(host: str, lang: str, local: str, remote_name: str) -> None:
    """mkdir -p → scp .tmp → mv → chown. json·mp4 공용."""
    remote_dir = f"{REMOTE_QUEUE}/{lang}"
    ssh(host, f"mkdir -p {remote_dir}")
    r = subprocess.run(["scp", "-q", local, f"{host}:{remote_dir}/{remote_name}.tmp"],
                       capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise RuntimeError(f"scp 실패: {(r.stderr or '')[:300]}")
    ssh(host, f"mv {remote_dir}/{remote_name}.tmp {remote_dir}/{remote_name} && {{ [ \"$(id -u)\" != 0 ] || chown -R langcard:langcard {REMOTE_DIR}/queue; }}")


def write_json(path: str, payload: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def upload(host: str, lang: str, payload: dict, name: str | None = None) -> str:
    name = (name or new_queue_name()) + ".json"
    fd, local = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        write_json(local, payload)
        push_file(host, lang, local, name)
    finally:
        os.unlink(local)
    return name


def render_reel(queue_json: str, style: str, out_mp4: str, workers: int) -> bool:
    """reels/build.py로 mp4 렌더. 실패해도 예외 대신 False(경고 출력)."""
    try:
        r = subprocess.run([sys.executable, os.path.join(REELS_DIR, "build.py"), queue_json,
                            "--style", style, "--out", out_mp4, "--workers", str(workers)],
                           cwd=ROOT, capture_output=True, text=True, timeout=RENDER_TIMEOUT)
    except Exception as e:  # noqa: BLE001
        print(f"경고: 렌더 실행 실패({style}): {e}", file=sys.stderr)
        return False
    if r.returncode != 0 or not os.path.exists(out_mp4) or os.path.getsize(out_mp4) == 0:
        tail = ((r.stderr or "") + (r.stdout or ""))[-400:]
        print(f"경고: 렌더 실패({style}) 종료코드 {r.returncode}: {tail}", file=sys.stderr)
        return False
    return True


def pick_and_render(queue_json: str, out_mp4: str, available: list[str], workers: int) -> str | None:
    """스타일 선택 → 렌더. 성공 시 스타일을 기록하고 이름 반환, 실패면 None."""
    style = choose_style(available, load_style_history(), random.Random())
    if not render_reel(queue_json, style, out_mp4, workers):
        return None
    try:
        record_style(style)
    except Exception as e:  # noqa: BLE001
        print(f"경고: 스타일 기록 저장 실패: {e}", file=sys.stderr)
    return style


def backfill(host: str, langs: list[str], available: list[str], workers: int, stats: dict) -> None:
    """서버 큐에서 mp4 없는 JSON을 받아 렌더 → mp4만 업로드."""
    pats = " ".join(f"{l}/*.json {l}/*.mp4" for l in langs)
    try:
        listing = ssh(host, f"cd {REMOTE_QUEUE} && ls -1 {pats} 2>/dev/null; true")
    except Exception as e:  # noqa: BLE001
        print(f"백필 목록 조회 실패: {e}", file=sys.stderr)
        return
    by_lang = parse_queue_listing(listing)
    for lang in langs:
        for jname in missing_videos(by_lang.get(lang, [])):
            st = stats.setdefault(lang, {"ok": 0, "fail": 0, "styles": []})
            tmp = tempfile.mkdtemp(prefix="hook-backfill-")
            try:
                local_json = os.path.join(tmp, jname)
                r = subprocess.run(["scp", "-q", f"{host}:{REMOTE_QUEUE}/{lang}/{jname}", local_json],
                                   capture_output=True, text=True, timeout=120)
                if r.returncode != 0:
                    print(f"경고: 백필 JSON 받기 실패 {lang}/{jname}", file=sys.stderr)
                    st["fail"] += 1
                    continue
                mp4_name = jname[: -len(".json")] + ".mp4"
                out_mp4 = os.path.join(tmp, mp4_name)
                style = pick_and_render(local_json, out_mp4, available, workers)
                if not style:
                    st["fail"] += 1
                    continue
                push_file(host, lang, out_mp4, mp4_name)
                st["ok"] += 1
                st["styles"].append(style)
            except Exception as e:  # noqa: BLE001
                print(f"경고: 백필 실패 {lang}/{jname}: {e}", file=sys.stderr)
                st["fail"] += 1
            finally:
                shutil.rmtree(tmp, ignore_errors=True)


# ── 메인 ─────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="구독(claude -p)으로 HOOK 큐 채우기")
    ap.add_argument("--target", type=int, default=3, help="언어별 큐 목표 개수")
    ap.add_argument("--langs", default=",".join(config.LANGUAGES))
    ap.add_argument("--dry-run", action="store_true", help="생성·검증만, 업로드 안 함(JSON 출력)")
    ap.add_argument("--host", default="sns-worker")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--no-render", action="store_true", help="영상 렌더 전부 끔(JSON만)")
    ap.add_argument("--no-backfill", action="store_true", help="서버 큐의 mp4 없는 항목 백필 끔")
    ap.add_argument("--styles", default=os.environ.get("REEL_STYLES", ""), help="허용 스타일 목록(쉼표 구분, 환경변수 REEL_STYLES)")
    ap.add_argument("--render-workers", type=int, default=3, help="build.py --workers")
    args = ap.parse_args()
    langs = [l.strip() for l in args.langs.split(",") if l.strip()]
    allowed = [x.strip() for x in args.styles.split(",") if x.strip()]
    available = [] if args.no_render else list_styles(REELS_DIR, allowed or None)
    do_render = bool(available)
    if not args.no_render and not do_render:
        print("경고: 사용 가능한 릴스 스타일이 없어 렌더를 건너뜁니다.", file=sys.stderr)
    render_stats: dict[str, dict] = {}

    env = subscription_env(dict(os.environ), read_oauth_token())
    assert_subscription_auth(env)

    try:
        history = json.loads(ssh(args.host, f"cat {REMOTE_DIR}/history.json"))
    except Exception as e:  # noqa: BLE001
        print(f"원격 history 로드 실패: {e}", file=sys.stderr)
        return 1

    summary = []
    for lang in langs:
        try:
            existing, queued_wrongs = remote_queue_state(args.host, lang)
        except Exception as e:  # noqa: BLE001
            print(f"[{lang}] 원격 큐 조회 실패: {e}", file=sys.stderr)
            return 1
        need = max(0, args.target - existing)
        known = wrongs_from_history(history, lang) + queued_wrongs
        added, failures = 0, []
        rs = render_stats.setdefault(lang, {"ok": 0, "fail": 0, "styles": []})
        for _ in range(need):
            ok = False
            for attempt in range(1, 4):
                try:
                    data = run_claude(build_hook_prompt(lang, known), args.model, env)
                except Exception as e:  # noqa: BLE001
                    failures.append(f"시도{attempt}: {e}")
                    continue
                problems = validate_hook(data)
                if problems:
                    failures.append(f"시도{attempt}: 검증 실패 {problems}")
                    continue
                if is_similar_wrong(data["wrong"], known):
                    failures.append(f"시도{attempt}: 중복/유사 {data['wrong']!r}")
                    continue
                payload = {"lang": lang,
                           "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                           "model": args.model, "data": data}
                base = new_queue_name()
                style = None
                tmp = tempfile.mkdtemp(prefix="hook-reel-")
                keep = False
                try:
                    if do_render:
                        local_json = os.path.join(tmp, base + ".json")
                        out_mp4 = os.path.join(tmp, base + ".mp4")
                        write_json(local_json, dict(payload, reel_style=available[0]))
                        style = pick_and_render(local_json, out_mp4, available, args.render_workers)
                        if style:
                            payload["reel_style"] = style
                            rs["ok"] += 1
                            rs["styles"].append(style)
                        else:
                            rs["fail"] += 1
                    if args.dry_run:
                        print(json.dumps(payload, ensure_ascii=False, indent=2))
                        if style:
                            keep = True
                            print(f"[dry-run] 렌더 결과(업로드 안 함): {out_mp4}", file=sys.stderr)
                    else:
                        if style:
                            try:
                                push_file(args.host, lang, out_mp4, base + ".mp4")
                            except Exception as e:  # noqa: BLE001
                                print(f"경고: mp4 업로드 실패, JSON만 올림: {e}", file=sys.stderr)
                                payload.pop("reel_style", None)
                                rs["ok"] -= 1
                                rs["fail"] += 1
                        upload(args.host, lang, payload, name=base)
                finally:
                    if not keep:
                        shutil.rmtree(tmp, ignore_errors=True)
                known.append(data["wrong"])
                added += 1
                ok = True
                break
            if not ok:
                failures.append("3회 재시도 실패 — 이 건 건너뜀")
        summary.append((lang, existing, added, failures))

    backfill_stats: dict[str, dict] = {}
    if do_render and not args.no_backfill:
        if args.dry_run:
            print("[dry-run] 백필은 건너뜀", file=sys.stderr)
        else:
            backfill(args.host, langs, available, args.render_workers, backfill_stats)

    def fmt(st: dict) -> str:
        return f"렌더 성공 {st['ok']} / 실패 {st['fail']}" + (f" 스타일 {','.join(st['styles'])}" if st["styles"] else "")

    print("\n== 요약 ==", file=sys.stderr)
    for lang, existing, added, failures in summary:
        print(f"{lang}: 기존 {existing} / 추가 {added}" + (" (dry-run)" if args.dry_run else ""), file=sys.stderr)
        if do_render:
            print(f"   렌더: {fmt(render_stats[lang])}", file=sys.stderr)
        if lang in backfill_stats:
            print(f"   백필: {fmt(backfill_stats[lang])}", file=sys.stderr)
        for f in failures:
            print(f"   - {f}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
