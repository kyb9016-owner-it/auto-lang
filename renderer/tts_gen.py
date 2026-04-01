"""TTS 음성 생성 — edge-tts (Microsoft Azure 무료 고품질 TTS)"""
from __future__ import annotations
import asyncio
import os
import subprocess
import tempfile
import time
from typing import Optional

try:
    import edge_tts
    _HAS_EDGE_TTS = True
except ImportError:
    _HAS_EDGE_TTS = False
    print("  ⚠ edge-tts 미설치. TTS 생성 건너뜀. (pip install edge-tts)")

from config import TTS_VOICES

TTS_DIR = os.path.join(os.path.dirname(__file__), "..", "output", "tts")

WORD_DURATION = 2.0  # 단어카드: 단어당 오디오 지속시간 (초)


# ── 저수준 유틸 ───────────────────────────────────────────────────────────────

async def _gen_async(text: str, voice: str, out_path: str) -> None:
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(out_path)


def _generate(text: str, lang: str, out_path: str, slot: str = "default") -> bool:
    """TTS 생성 공통 함수. 성공 여부 반환.
    - 1차: 슬롯 지정 음성으로 최대 3회 재시도
    - 2차: 1차 전체 실패 시 default 음성으로 1회 폴백
    """
    if not _HAS_EDGE_TTS:
        return False
    os.makedirs(TTS_DIR, exist_ok=True)
    voices = TTS_VOICES.get(lang, {})
    if isinstance(voices, dict):
        primary_voice = voices.get(slot) or voices.get("default", "en-US-JennyNeural")
        fallback_voice = voices.get("default", "en-US-JennyNeural")
    else:
        primary_voice = voices
        fallback_voice = voices

    # 1차: 지정 음성으로 3회 시도
    for attempt in range(3):
        try:
            asyncio.run(_gen_async(text, primary_voice, out_path))
            size_kb = os.path.getsize(out_path) // 1024
            print(f"  ✓ TTS 생성: {os.path.basename(out_path)}  ({size_kb} KB)")
            return True
        except Exception as e:
            if attempt < 2:
                print(f"  ↻ TTS 재시도 {attempt + 1}/2 ({lang}): {e}")
                time.sleep(2)
            else:
                print(f"  ⚠ TTS 기본 음성 실패 ({lang}/{primary_voice}): {e}")

    # 2차: 폴백 음성으로 1회 시도 (기본 음성과 다를 때만)
    if fallback_voice != primary_voice:
        try:
            print(f"  ↻ TTS 폴백 음성 시도 ({lang}/{fallback_voice})")
            asyncio.run(_gen_async(text, fallback_voice, out_path))
            size_kb = os.path.getsize(out_path) // 1024
            print(f"  ✓ TTS 폴백 성공: {os.path.basename(out_path)}  ({size_kb} KB)")
            return True
        except Exception as e:
            print(f"  ⚠ TTS 폴백도 실패 ({lang}/{fallback_voice}): {e}")

    return False


def _get_audio_duration(path: str) -> float:
    """ffprobe로 오디오 길이(초) 반환. 실패 시 0.0"""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=10
        )
        return float(result.stdout.strip()) if result.returncode == 0 else 0.0
    except Exception:
        return 0.0


def _pad_to_duration(src: str, dst: str, duration: float) -> bool:
    """오디오를 정확히 duration초로 패딩 (뒤에 무음 추가 후 trim)."""
    try:
        cmd = [
            "ffmpeg", "-y", "-i", src,
            "-filter_complex",
            f"[0:a]apad=pad_dur={duration},atrim=0:{duration}[a]",
            "-map", "[a]", "-c:a", "libmp3lame", "-b:a", "128k",
            dst, "-loglevel", "error"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0
    except Exception:
        return False


def _concat_mp3_files(files: list, out: str) -> bool:
    """MP3 파일 목록을 순서대로 이어붙이기 (concat demuxer)."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for fp in files:
            f.write(f"file '{os.path.abspath(fp)}'\n")
        list_path = f.name
    try:
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", list_path,
            "-af", "aresample=44100",
            "-c:a", "libmp3lame", "-ar", "44100", "-b:a", "128k",
            out, "-loglevel", "error"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0
    finally:
        os.unlink(list_path)


# ── 캐시 헬퍼 ─────────────────────────────────────────────────────────────────

def _read_cache_text(mp3_path: str) -> str:
    """mp3 옆에 저장된 .txt 사이드카 파일에서 캐시된 텍스트 읽기. 없으면 빈 문자열."""
    txt_path = mp3_path.replace(".mp3", ".txt")
    try:
        with open(txt_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


def _write_cache_text(mp3_path: str, text: str) -> None:
    """mp3 옆에 .txt 사이드카 파일로 텍스트 저장 (캐시 검증용)."""
    txt_path = mp3_path.replace(".mp3", ".txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(text.strip())


# ── 공개 함수 ─────────────────────────────────────────────────────────────────

def generate_expression(expression: str, lang: str, date_str: str,
                        slot: str = "default") -> Optional[str]:
    """
    메인 표현 TTS 생성.
    캐시가 있어도 텍스트가 다르면 재생성 (드라이런 후 내용 변경 대비).
    Returns: 오디오 파일 경로 (output/tts/expr_{lang}_{slot}_{date_str}.mp3)
             실패 시 None
    """
    out = os.path.join(TTS_DIR, f"expr_{lang}_{slot}_{date_str}.mp3")
    if os.path.exists(out):
        if _read_cache_text(out) == expression.strip():
            print(f"  ✓ TTS 캐시 사용: {os.path.basename(out)}")
            return out
        print(f"  ↻ TTS 내용 변경됨, 재생성: {os.path.basename(out)}")
    if _generate(expression, lang, out, slot=slot):
        _write_cache_text(out, expression)
        return out
    return None


def generate_vocab(vocab: list, lang: str, date_str: str,
                   slot: str = "default") -> Optional[str]:
    """
    단어 TTS 생성 — 단어마다 개별 TTS 후 WORD_DURATION(2초)로 패딩, 이어붙이기.
    캐시가 있어도 텍스트가 다르면 재생성.
    Returns: 오디오 파일 경로 (output/tts/vocab_{lang}_{slot}_{date_str}.mp3)
             실패 시 None
    """
    words = [item.get("word", "") for item in vocab[:3] if item.get("word")]
    cache_text = "|".join(words)   # 캐시 키: 단어 목록

    out = os.path.join(TTS_DIR, f"vocab_{lang}_{slot}_{date_str}.mp3")
    if os.path.exists(out):
        if _read_cache_text(out) == cache_text:
            print(f"  ✓ TTS 캐시 사용: {os.path.basename(out)}")
            return out
        print(f"  ↻ TTS 내용 변경됨, 재생성: {os.path.basename(out)}")

    os.makedirs(TTS_DIR, exist_ok=True)

    # 단어별 TTS 생성 → WORD_DURATION초 패딩 → 이어붙이기
    padded_files = []
    for i, word in enumerate(words):
        raw_path    = os.path.join(TTS_DIR, f"_tmp_{lang}_{date_str}_w{i}_raw.mp3")
        padded_path = os.path.join(TTS_DIR, f"_tmp_{lang}_{date_str}_w{i}_pad.mp3")

        if not _generate(word, lang, raw_path, slot=slot):
            continue   # 단어 하나 실패 → 건너뜀

        tts_dur = _get_audio_duration(raw_path)
        target  = max(WORD_DURATION, tts_dur + 0.3)   # 최소 2초, TTS가 길면 0.3초 여유

        if _pad_to_duration(raw_path, padded_path, target):
            padded_files.append(padded_path)

    if not padded_files:
        return None

    # 단어가 1개면 바로 복사, 여러 개면 concat
    if len(padded_files) == 1:
        import shutil
        shutil.copy2(padded_files[0], out)
        ok = True
    else:
        ok = _concat_mp3_files(padded_files, out)

    # 임시 파일 정리
    for fp in padded_files:
        try:
            os.remove(fp)
        except OSError:
            pass
    for i in range(len(words)):
        for suffix in ("_raw.mp3",):
            p = os.path.join(TTS_DIR, f"_tmp_{lang}_{date_str}_w{i}{suffix}")
            try:
                os.remove(p)
            except OSError:
                pass

    if ok and os.path.exists(out):
        size_kb = os.path.getsize(out) // 1024
        print(f"  ✓ TTS 단어 합성 완료: {os.path.basename(out)}  "
              f"({len(padded_files)}단어 × {WORD_DURATION}s = {size_kb} KB)")
        _write_cache_text(out, cache_text)
        return out

    return None


def generate_hook_tts(data: dict, lang: str, date_str: str,
                      slot: str = "default") -> Optional[str]:
    """
    HOOK형 이중 언어 TTS 생성.
    한국어 나레이션 + 타겟 언어 WRONG/RIGHT 발음을 조합.

    구조: [KO intro] → [LANG wrong] → [KO bridge] → [LANG right] → [KO outro]

    data: {"wrong": str, "right": str, "tts_parts": {"intro": str, "bridge": str, "outro": str}}
    Returns: 합성된 오디오 파일 경로 또는 None
    """
    from config import KO_TTS_VOICE

    os.makedirs(TTS_DIR, exist_ok=True)
    out = os.path.join(TTS_DIR, f"hook_{lang}_{slot}_{date_str}.mp3")

    # 캐시 체크
    cache_text = f"{data['wrong']}|{data['right']}"
    if os.path.exists(out):
        if _read_cache_text(out) == cache_text:
            print(f"  ✓ TTS 캐시 사용: {os.path.basename(out)}")
            return out
        print(f"  ↻ TTS 내용 변경됨, 재생성: {os.path.basename(out)}")

    tts_parts = data.get("tts_parts", {})
    parts = [
        ("intro", tts_parts.get("intro", "이런 표현을 많이 씁니다"), "ko", KO_TTS_VOICE),
        ("wrong", data["wrong"], lang, None),  # 타겟 언어 음성 (슬롯별)
        ("bridge", tts_parts.get("bridge", "올바른 표현은"), "ko", KO_TTS_VOICE),
        ("right", data["right"], lang, None),
        ("outro", tts_parts.get("outro", data.get("right_ko", "")), "ko", KO_TTS_VOICE),
    ]

    part_files = []
    for i, (label, text, part_lang, voice_override) in enumerate(parts):
        if not text.strip():
            continue
        part_path = os.path.join(TTS_DIR, f"_hook_{lang}_{date_str}_{i}_{label}.mp3")

        if voice_override:
            # 한국어: 직접 지정 음성
            try:
                asyncio.run(_gen_async(text, voice_override, part_path))
                print(f"  ✓ TTS ({label}): {text[:20]}")
            except Exception as e:
                print(f"  ⚠ TTS ({label}) 실패: {e}")
                continue
        else:
            # 타겟 언어: 기존 _generate 함수 사용 (slot-based voice selection)
            if not _generate(text, part_lang, part_path, slot=slot):
                continue

        if os.path.exists(part_path):
            part_files.append(part_path)

    if len(part_files) < 3:
        print(f"  ⚠ HOOK TTS 파트 부족 ({len(part_files)}/5), 생성 실패")
        return None

    # 파트 합성
    ok = _concat_mp3_files(part_files, out)

    # TTS 길이 검증 & 속도 조절 (10초 초과 시)
    if ok and os.path.exists(out):
        total_dur = _get_audio_duration(out)
        if total_dur > 10.0:
            print(f"  ⚠ TTS 총 {total_dur:.1f}초 > 10초, 속도 조절 시도")
            sped_up = os.path.join(TTS_DIR, f"_hook_{lang}_{date_str}_fast.mp3")
            speed_factor = min(1.3, total_dur / 10.0)
            try:
                subprocess.run([
                    "ffmpeg", "-y", "-i", out,
                    "-filter:a", f"atempo={speed_factor}",
                    "-c:a", "libmp3lame", "-b:a", "128k",
                    sped_up, "-loglevel", "error"
                ], check=True)
                import shutil
                shutil.move(sped_up, out)
                print(f"  ✓ TTS 속도 {speed_factor:.2f}x 적용")
            except Exception as e:
                print(f"  ⚠ 속도 조절 실패 (원본 유지): {e}")

    # 임시 파일 정리
    for fp in part_files:
        try:
            os.remove(fp)
        except OSError:
            pass

    if ok and os.path.exists(out):
        size_kb = os.path.getsize(out) // 1024
        dur = _get_audio_duration(out)
        print(f"  ✓ HOOK TTS 합성 완료: {os.path.basename(out)} ({dur:.1f}초, {size_kb} KB)")
        _write_cache_text(out, cache_text)
        return out

    return None
