"""구독 큐 — 맥이 `claude -p`(구독)로 미리 만든 HOOK JSON을 서버가 하나씩 꺼내 쓴다.

파일 포맷: {"lang": "en", "created_at": ISO, "model": "...", "data": {HOOK dict}}
"""
from __future__ import annotations
import json
import os
import shutil

from generator import history
from generator.hook_prompt import validate_hook

_DEFAULT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "queue", "hook")


def _root() -> str:
    return os.path.abspath(os.environ.get("HOOK_QUEUE_DIR") or _DEFAULT_ROOT)


# 문서·외부 참조용 (환경변수 미설정 시 기본 경로)
QUEUE_ROOT = os.path.abspath(_DEFAULT_ROOT)


def _files(lang: str) -> list[str]:
    d = os.path.join(_root(), lang)
    if not os.path.isdir(d):
        return []
    return sorted(
        os.path.join(d, n) for n in os.listdir(d)
        if n.endswith(".json") and not n.endswith(".tmp")
    )


def _move(path: str, sub: str) -> None:
    dest_dir = os.path.join(_root(), sub)
    os.makedirs(dest_dir, exist_ok=True)
    shutil.move(path, os.path.join(dest_dir, os.path.basename(path)))


def count(lang: str) -> int:
    return len(_files(lang))


def pop(lang: str) -> dict | None:
    """큐에서 검증 통과한 HOOK 하나를 꺼내 used/로 옮기고 data 반환. 없으면 None."""
    for path in _files(lang):
        reason = None
        data = None
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            data = payload["data"]
            problems = validate_hook(data)
            if problems:
                reason = "검증 실패: " + "; ".join(problems)
            elif history.is_hook_duplicate(lang, data["wrong"]):
                reason = f"중복: {data['wrong']!r}"
        except Exception as e:  # noqa: BLE001
            reason = f"로드 실패: {e}"

        if reason:
            print(f"  ⚠ 큐 파일 거부({os.path.basename(path)}): {reason}")
            _move(path, "rejected")
            continue
        _move(path, "used")
        return data
    return None
