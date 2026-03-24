"""릴스 영상 렌더러 — ffmpeg로 1080×1920 MP4 생성 (TTS 오디오 포함)"""
from __future__ import annotations
import os
import subprocess
import tempfile
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")
FRAMES_DIR = os.path.join(OUTPUT_DIR, "reel_frames")
TTS_DIR    = os.path.join(OUTPUT_DIR, "tts")


# ── 유틸 ────────────────────────────────────────────────────────────────────

def _pad_to_9_16(src: str, dst: str) -> None:
    """카드 이미지를 1080×1920으로 스케일+패딩 (고품질 리샘플링)"""
    cmd = [
        "ffmpeg", "-y", "-i", src,
        "-vf", "scale=1080:1920:force_original_aspect_ratio=increase:"
               "flags=lanczos,"
               "crop=1080:1920",
        dst, "-loglevel", "error"
    ]
    subprocess.run(cmd, check=True)


def _get_audio_duration(audio_path: str) -> float:
    """ffprobe로 오디오 파일 길이(초) 반환. 실패 시 3.0"""
    if not audio_path or not os.path.exists(audio_path):
        return 0.0
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
            capture_output=True, text=True, timeout=10
        )
        return float(result.stdout.strip()) if result.returncode == 0 else 0.0
    except Exception:
        return 0.0


def _make_segment(padded_png: str, audio_path: Optional[str],
                  duration: float, out_mp4: str) -> None:
    """PNG + 오디오 → 고정 길이 MP4 세그먼트"""
    base_cmd = ["ffmpeg", "-y",
                "-loop", "1", "-t", str(duration), "-i", padded_png]

    if audio_path and os.path.exists(audio_path):
        base_cmd += ["-i", audio_path,
                     "-filter_complex", f"[1:a]apad=pad_dur={duration},atrim=0:{duration}[a]",
                     "-map", "0:v", "-map", "[a]",
                     "-vf", "fps=30,format=yuv420p",
                     "-c:v", "libx264", "-preset", "slow", "-crf", "12",
                     "-c:a", "aac", "-b:a", "128k",
                     "-movflags", "+faststart"]
    else:
        # 오디오 없음 — 무음 트랙 추가 (concat 시 호환성)
        base_cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                     "-map", "0:v", "-map", "1:a",
                     "-vf", "fps=30,format=yuv420p",
                     "-c:v", "libx264", "-preset", "slow", "-crf", "12",
                     "-c:a", "aac", "-b:a", "128k",
                     "-t", str(duration),
                     "-movflags", "+faststart"]

    base_cmd.append(out_mp4)
    result = subprocess.run(base_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"세그먼트 생성 오류:\n{result.stderr[-600:]}")


def _concat_segments(segment_files: list[str], out_path: str) -> None:
    """세그먼트 MP4 목록을 concat demuxer로 합치기"""
    # concat 리스트 파일 생성
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt",
                                     delete=False) as f:
        for seg in segment_files:
            f.write(f"file '{os.path.abspath(seg)}'\n")
        list_path = f.name

    try:
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", list_path,
            "-c", "copy",
            "-movflags", "+faststart",
            out_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"concat 오류:\n{result.stderr[-600:]}")
    finally:
        os.unlink(list_path)


# ── 언어별 숏릴스 (표현 카드 + 단어 카드 + TTS 음성) ───────────────────────

def render_short(expr_path: str, vocab_path: str,
                 expr_tts: Optional[str], vocab_tts: Optional[str],
                 lang: str, date_str: str,
                 hook_path: Optional[str] = None,
                 outro_path: Optional[str] = None) -> str:
    """
    숏릴스: [훅 2s?] → 표현카드(TTS) → 단어카드(TTS) → [아웃트로 2.5s?]
    hook_path / outro_path 가 있으면 앞뒤에 추가.
    Returns: output/short_{lang}_{date_str}.mp4
    """
    os.makedirs(FRAMES_DIR, exist_ok=True)

    # 표현 TTS 두 번 반복 (사이 1초 무음)
    expr_tts_2x = None
    if expr_tts and os.path.exists(expr_tts):
        expr_tts_2x = os.path.join(FRAMES_DIR, f"short_{lang}_{date_str}_expr_2x.mp3")
        tts_dur = _get_audio_duration(expr_tts)
        gap = 1.0  # 반복 사이 무음
        total = tts_dur * 2 + gap
        subprocess.run([
            "ffmpeg", "-y",
            "-i", expr_tts, "-i", expr_tts,
            "-filter_complex",
            f"[0:a]apad=pad_dur={gap}[a0];[a0][1:a]concat=n=2:v=0:a=1[out]",
            "-map", "[out]", "-c:a", "libmp3lame", "-b:a", "128k",
            expr_tts_2x
        ], capture_output=True, text=True)
        if not os.path.exists(expr_tts_2x):
            expr_tts_2x = expr_tts  # 실패 시 원본 사용

    # 오디오 길이 기반 슬라이드 지속시간 결정
    _expr_audio = expr_tts_2x or expr_tts
    expr_dur  = max(4.0, _get_audio_duration(_expr_audio) + 1.5) if _expr_audio else 4.5
    vocab_dur = max(5.0, _get_audio_duration(vocab_tts) + 1.0) if vocab_tts else 5.5

    segments: list[str] = []

    # ── 훅 프레임 ────────────────────────────────────────────────────────
    if hook_path and os.path.exists(hook_path):
        padded_hook = os.path.join(FRAMES_DIR, f"short_{lang}_{date_str}_hook.png")
        _pad_to_9_16(hook_path, padded_hook)
        seg_hook = os.path.join(FRAMES_DIR, f"short_{lang}_{date_str}_seg_hook.mp4")
        _make_segment(padded_hook, None, 2.0, seg_hook)   # 무음 2초
        segments.append(seg_hook)

    # ── 표현 + 단어 카드 ─────────────────────────────────────────────────
    padded_expr  = os.path.join(FRAMES_DIR, f"short_{lang}_{date_str}_expr.png")
    padded_vocab = os.path.join(FRAMES_DIR, f"short_{lang}_{date_str}_vocab.png")
    _pad_to_9_16(expr_path, padded_expr)
    _pad_to_9_16(vocab_path, padded_vocab)

    seg_expr  = os.path.join(FRAMES_DIR, f"short_{lang}_{date_str}_seg_expr.mp4")
    seg_vocab = os.path.join(FRAMES_DIR, f"short_{lang}_{date_str}_seg_vocab.mp4")
    _make_segment(padded_expr,  _expr_audio,  expr_dur,  seg_expr)
    _make_segment(padded_vocab, vocab_tts, vocab_dur, seg_vocab)
    segments += [seg_expr, seg_vocab]

    # ── 아웃트로 프레임 ──────────────────────────────────────────────────
    if outro_path and os.path.exists(outro_path):
        padded_outro = os.path.join(FRAMES_DIR, f"short_{lang}_{date_str}_outro.png")
        _pad_to_9_16(outro_path, padded_outro)
        seg_outro = os.path.join(FRAMES_DIR, f"short_{lang}_{date_str}_seg_outro.mp4")
        _make_segment(padded_outro, None, 2.5, seg_outro)  # 무음 2.5초
        segments.append(seg_outro)

    # ── 최종 합치기 ──────────────────────────────────────────────────────
    out_path = os.path.join(OUTPUT_DIR, f"short_{lang}_{date_str}.mp4")
    _concat_segments(segments, out_path)

    size_kb = os.path.getsize(out_path) // 1024
    print(f"  ✓ 숏릴스 저장: {out_path}  ({size_kb} KB)")
    return out_path


# ── 전날 카드 탐색 ────────────────────────────────────────────────────────────

def find_yesterday_cards(yesterday: str) -> tuple[dict, dict]:
    """
    어제 날짜의 표현/단어 카드 PNG 탐색.
    Returns: (image_paths, vocab_paths) 각 {"en": path, ...}
             파일 없으면 빈 dict 반환
    """
    langs = ["en", "zh", "ja"]
    image_paths = {}
    vocab_paths = {}

    for lang in langs:
        expr_p  = os.path.join(OUTPUT_DIR, f"expr_{lang}_{yesterday}.png")
        vocab_p = os.path.join(OUTPUT_DIR, f"vocab_{lang}_{yesterday}.png")
        if os.path.exists(expr_p):
            image_paths[lang] = expr_p
        if os.path.exists(vocab_p):
            vocab_paths[lang] = vocab_p

    return image_paths, vocab_paths


# ── 종합 릴스 (6장 카드 + TTS 오디오) ────────────────────────────────────────

def render(image_paths: dict, vocab_paths: dict,
           tts_expr_paths: Optional[dict] = None,
           tts_vocab_paths: Optional[dict] = None,
           date_str: Optional[str] = None,
           # 하위 호환용 파라미터
           slot: str = "daily",
           duration: float = 3.0, fade: float = 0.5) -> str:
    """
    어제 카드 6장으로 종합 릴스 생성 (TTS 오디오 포함).
    Returns: output/reel_{date_str}.mp4
    """
    if date_str is None:
        date_str = date.today().strftime("%Y%m%d")

    os.makedirs(FRAMES_DIR, exist_ok=True)
    langs = [l for l in ("en", "zh", "ja") if l in image_paths]

    # 프레임 순서: en_expr, zh_expr, ja_expr, en_vocab, zh_vocab, ja_vocab
    frames = []
    for lang in langs:
        frames.append({
            "png": image_paths[lang],
            "tts": (tts_expr_paths or {}).get(lang),
            "dur_min": duration + 1.0,  # 표현카드: 읽기 여유 +1초
        })
    for lang in langs:
        if lang in vocab_paths:
            frames.append({
                "png": vocab_paths[lang],
                "tts": (tts_vocab_paths or {}).get(lang),
                "dur_min": duration + 2.0,  # 단어 카드: 읽기 여유 +2초
            })

    # 세그먼트 생성
    segments = []
    for i, frame in enumerate(frames):
        padded = os.path.join(FRAMES_DIR, f"recap_{date_str}_frame{i:02d}.png")
        _pad_to_9_16(frame["png"], padded)

        tts_path = frame["tts"]
        # TTS 파일 존재 확인
        if tts_path and not os.path.exists(tts_path):
            tts_path = None

        seg_dur = max(frame["dur_min"],
                      _get_audio_duration(tts_path) + 0.5 if tts_path else frame["dur_min"])

        seg_out = os.path.join(FRAMES_DIR, f"recap_{date_str}_seg{i:02d}.mp4")
        _make_segment(padded, tts_path, seg_dur, seg_out)
        segments.append(seg_out)

    out_path = os.path.join(OUTPUT_DIR, f"reel_{date_str}.mp4")
    _concat_segments(segments, out_path)

    size_kb = os.path.getsize(out_path) // 1024
    print(f"  ✓ 종합 릴스 저장: {out_path}  ({size_kb} KB)")
    return out_path
