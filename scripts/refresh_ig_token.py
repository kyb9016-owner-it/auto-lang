"""Instagram 장기 토큰(IGAA…, Instagram Login 방식) 자동 연장.

장기 토큰은 60일 유효하고, 유효한 동안에만 연장할 수 있다(만료되면 재발급뿐 —
2026-05-03 만료로 3개월 정지된 원인). 월 1회 크론으로 실행해 .env를 새 토큰으로 교체한다.

사용: .venv/bin/python3 scripts/refresh_ig_token.py [--env .env] [--check]
  --check : 연장하지 않고 유효성만 확인
토큰 값은 절대 출력하지 않는다.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

KEY = "INSTAGRAM_ACCESS_TOKEN"
BASE = "https://graph.instagram.com"


def read_token(env_path: str) -> str:
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            if line.startswith(KEY + "="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit(f"{KEY}가 {env_path}에 없습니다")


def replace_token(env_path: str, new_token: str) -> None:
    """같은 디렉터리 임시 파일에 쓰고 원자적으로 교체(권한·소유자 유지)."""
    st = os.stat(env_path)
    with open(env_path, encoding="utf-8") as f:
        lines = f.readlines()
    out = [l for l in lines if not l.startswith(KEY + "=")]
    if out and not out[-1].endswith("\n"):
        out[-1] += "\n"
    out.append(f"{KEY}={new_token}\n")
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(env_path), prefix=".env.")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.writelines(out)
    os.chmod(tmp, st.st_mode & 0o777)
    try:
        os.chown(tmp, st.st_uid, st.st_gid)
    except PermissionError:
        pass
    os.replace(tmp, env_path)


def get_json(url: str) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return json.load(e)
        except Exception:
            return {"error": {"message": f"HTTP {e.code}"}}


def notify(msg: str) -> None:
    try:
        import notify as _n  # 저장소의 텔레그램 알림
        _n.send(msg)
    except Exception as e:
        print(f"(알림 실패: {e})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=os.path.join(ROOT, ".env"))
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    token = read_token(a.env)
    me = get_json(f"{BASE}/v21.0/me?" + urllib.parse.urlencode(
        {"fields": "username", "access_token": token}))
    if "error" in me:
        msg = f"❌ LangCard 인스타 토큰 무효: {me['error'].get('message', '')[:200]} — 재발급 필요"
        print(msg)
        notify(msg)
        return 1
    print(f"토큰 유효: @{me.get('username')}")
    if a.check:
        return 0

    r = get_json(f"{BASE}/refresh_access_token?" + urllib.parse.urlencode(
        {"grant_type": "ig_refresh_token", "access_token": token}))
    new = r.get("access_token")
    if not new:
        msg = f"❌ LangCard 인스타 토큰 연장 실패: {json.dumps(r, ensure_ascii=False)[:200]}"
        print(msg)
        notify(msg)
        return 1
    replace_token(a.env, new)
    days = int(r.get("expires_in", 0)) // 86400
    msg = f"🔑 LangCard 인스타 토큰 연장 완료 (유효 {days}일)"
    print(msg)
    notify(msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
