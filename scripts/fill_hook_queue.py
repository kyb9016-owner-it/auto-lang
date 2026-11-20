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


# ── 맥 환경 ──────────────────────────────────────────────────────────

def read_oauth_token() -> str | None:
    """키체인의 워커 토큰(없으면 None → 일반 로그인). 값은 출력 금지."""
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


def upload(host: str, lang: str, payload: dict) -> str:
    stamp = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    name = f"{stamp}_{''.join(random.choices(string.ascii_lowercase + string.digits, k=6))}.json"
    remote_dir = f"{REMOTE_QUEUE}/{lang}"
    ssh(host, f"mkdir -p {remote_dir}")
    fd, local = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        r = subprocess.run(["scp", "-q", local, f"{host}:{remote_dir}/{name}.tmp"],
                           capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            raise RuntimeError(f"scp 실패: {(r.stderr or '')[:300]}")
    finally:
        os.unlink(local)
    ssh(host, f"mv {remote_dir}/{name}.tmp {remote_dir}/{name} && chown -R langcard:langcard {REMOTE_DIR}/queue")
    return name


# ── 메인 ─────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="구독(claude -p)으로 HOOK 큐 채우기")
    ap.add_argument("--target", type=int, default=3, help="언어별 큐 목표 개수")
    ap.add_argument("--langs", default=",".join(config.LANGUAGES))
    ap.add_argument("--dry-run", action="store_true", help="생성·검증만, 업로드 안 함(JSON 출력)")
    ap.add_argument("--host", default="sns-worker")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    args = ap.parse_args()
    langs = [l.strip() for l in args.langs.split(",") if l.strip()]

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
                if args.dry_run:
                    print(json.dumps(payload, ensure_ascii=False, indent=2))
                else:
                    upload(args.host, lang, payload)
                known.append(data["wrong"])
                added += 1
                ok = True
                break
            if not ok:
                failures.append("3회 재시도 실패 — 이 건 건너뜀")
        summary.append((lang, existing, added, failures))

    print("\n== 요약 ==", file=sys.stderr)
    for lang, existing, added, failures in summary:
        print(f"{lang}: 기존 {existing} / 추가 {added}" + (" (dry-run)" if args.dry_run else ""), file=sys.stderr)
        for f in failures:
            print(f"   - {f}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
