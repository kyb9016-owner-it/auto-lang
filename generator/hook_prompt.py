"""HOOK(WRONG→RIGHT) 생성 프롬프트·스키마·검증 — 순수 모듈 (stdlib + config만).

서버(claude_gen/hook_queue)와 맥(scripts/fill_hook_queue.py)이 공유한다.
"""
from __future__ import annotations
import re
from config import LANG_CONFIG

HOOK_SYSTEM = """You are a language correction content creator for Korean Instagram.
You create "common mistake → correct expression" content for Korean learners.
The content must be accurate: WRONG must be a real, common mistake Koreans actually make.
RIGHT must be the natural, native-speaker expression.
Always respond with valid JSON only. No markdown, no extra text."""


def build_hook_prompt(lang: str, recent_wrongs: list[str]) -> str:
    lc = LANG_CONFIG[lang]
    history_str = "\n".join(f"  - {w}" for w in recent_wrongs) if recent_wrongs else "  (없음)"

    pronunciation_field = ""
    if lc["has_pronunciation"]:
        pronunciation_field = f'"pronunciation": "{lc["pronunciation_label"]} of the RIGHT expression",'
    else:
        pronunciation_field = '"pronunciation": null,'

    return f"""Generate ONE common mistake that Korean speakers make in {lc['name']}.

Topic: Everyday expressions (일상생활 표현)

Rules:
- WRONG must be a mistake Koreans ACTUALLY make frequently (Konglish, direct translation, grammar error, etc.)
- RIGHT must be what native speakers naturally say in the same situation
- The difference must have clear learning value (not trivially obvious)
- HOOK must stop scrolling in 1 second — provocative, short, in Korean
- TTS parts must be under 15 characters each (for timing control)
- For vocab: pick 3 key words from the wrong or right expression; focus on commonly confused or useful words; type must be in Korean: 동사, 형용사, 부사, 명사, 전치사, 조동사
- dialogue: Generate a 2~4 turn realistic conversation where the RIGHT expression is used naturally. The RIGHT expression MUST appear in one of the turns (preferably the last). Each turn needs: speaker (A or B), line (in {lc['name']}), pronunciation (romanization/pinyin for zh/ja, null for en), korean_phonetic (한글 발음), korean (한국어 번역).
- MUST be different from these recently used WRONG expressions:
{history_str}

Return ONLY this JSON:
{{
  "hook": "짧고 강한 한국어 문장 (예: '이거 영어로 말하면 99%가 틀림')",
  "wrong": "the incorrect {lc['name']} expression Koreans commonly say",
  "wrong_ko_phonetic": "WRONG의 한글 발음 표기 (예: '워 헌 까오씽 지엔따오 니')",
  "right": "the natural/correct {lc['name']} expression",
  "right_ko_phonetic": "RIGHT의 한글 발음 표기 (예: '헌 까오씽 지엔따오 니')",
  "right_ko": "RIGHT의 한국어 뜻",
  {pronunciation_field}
  "tts_parts": {{
    "intro": "한국어 도입 (15자 이내, 예: '많은 사람들이 이렇게 말합니다')",
    "bridge": "한국어 연결 (15자 이내, 예: '하지만 올바른 표현은')",
    "outro": "한국어 마무리 (15자 이내, 예: RIGHT의 한국어 뜻)"
  }},
  "subtitle_lines": [
    "자막1: HOOK 요약 (10단어 이내)",
    "❌ WRONG 표현",
    "→ WRONG의 한국어 뜻",
    "✅ RIGHT 표현",
    "→ RIGHT의 한국어 뜻"
  ],
  "explanation": "틀린 표현이 왜 어색한지, 올바른 표현은 언제/어떻게 쓰는지 2~3문장으로 설명 (한국어). 뉘앙스 차이, 원어민이 실제 쓰는 상황 포함. 예: '\"He is a kind person\"은 문법적으로는 맞지만 원어민 대화에서는 너무 딱딱하게 들려요. 일상에서는 \"He\\'s really nice\"처럼 짧고 자연스러운 표현을 더 많이 써요. 특히 친한 사람을 소개하거나 칭찬할 때 이 표현이 훨씬 자연스럽습니다.'",
  "explanation_short": "릴스 화면용 한 줄 요약 (한국어 22자 이내, 왜 틀렸는지 핵심 결론만. 예: '아이쇼핑은 한국에서만 쓰는 말이에요')",
  "cta": "저장/댓글 유도 문구 (예: '이거 몰랐으면 저장해두세요'). 이모지 사용 금지.",
  "vocab": [
    {{"word": "key word from wrong or right expression", "type": "품사 (동사/형용사/부사/명사/전치사)", "meaning": "한국어 뜻", "phonetic": "한글 발음 (영어만, 중국어/일본어는 null)"}},
    {{"word": "second word", "type": "품사", "meaning": "한국어 뜻", "phonetic": "한글 발음"}},
    {{"word": "third word", "type": "품사", "meaning": "한국어 뜻", "phonetic": "한글 발음"}}
  ],
  "dialogue": [
    {{"speaker": "A", "line": "대화 원문 (in {lc['name']})", "pronunciation": "로마자/병음 (영어는 null)", "korean_phonetic": "한글 발음", "korean": "한국어 번역"}},
    {{"speaker": "B", "line": "대화 원문 (in {lc['name']})", "pronunciation": "로마자/병음 (영어는 null)", "korean_phonetic": "한글 발음", "korean": "한국어 번역"}}
  ]
}}"""


_STR = {"type": "string", "minLength": 1}
_STR_OR_NULL = {"type": ["string", "null"]}

HOOK_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "hook": _STR,
        "wrong": _STR,
        "wrong_ko_phonetic": _STR,
        "right": _STR,
        "right_ko_phonetic": _STR,
        "right_ko": _STR,
        "pronunciation": _STR_OR_NULL,
        "tts_parts": {
            "type": "object",
            "properties": {"intro": _STR, "bridge": _STR, "outro": _STR},
            "required": ["intro", "bridge", "outro"],
        },
        "subtitle_lines": {"type": "array", "items": _STR},
        "explanation": _STR,
        "explanation_short": {"type": "string", "minLength": 1, "maxLength": 30},
        "cta": _STR,
        "vocab": {
            "type": "array",
            "minItems": 3,
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "word": _STR,
                    "type": _STR,
                    "meaning": _STR,
                    "phonetic": _STR_OR_NULL,
                },
                "required": ["word", "type", "meaning", "phonetic"],
            },
        },
        "dialogue": {
            "type": "array",
            "minItems": 2,
            "maxItems": 4,
            "items": {
                "type": "object",
                "properties": {
                    "speaker": _STR,
                    "line": _STR,
                    "pronunciation": _STR_OR_NULL,
                    "korean_phonetic": _STR,
                    "korean": _STR,
                },
                "required": ["speaker", "line", "pronunciation", "korean_phonetic", "korean"],
            },
        },
    },
    "required": [
        "hook", "wrong", "wrong_ko_phonetic", "right", "right_ko_phonetic", "right_ko",
        "pronunciation", "tts_parts", "subtitle_lines", "explanation", "explanation_short", "cta", "vocab", "dialogue",
    ],
}


def _loose(text: str) -> str:
    """느슨한 비교용 정규화: 소문자 + 공백 제거 + 양끝 구두점 제거."""
    t = re.sub(r"\s+", "", str(text).lower())
    return t.strip(".,!?;:。、！？…\"'“”‘’")


def _nonempty(v) -> bool:
    return isinstance(v, str) and v.strip() != ""


def validate_hook(data: dict) -> list[str]:
    """HOOK dict 검증. 문제 목록 반환(빈 리스트 = 정상)."""
    problems: list[str] = []
    if not isinstance(data, dict):
        return ["dict가 아님"]

    for k in ("hook", "wrong", "wrong_ko_phonetic", "right", "right_ko_phonetic",
              "right_ko", "explanation", "cta"):
        if not _nonempty(data.get(k)):
            problems.append(f"{k} 누락/빈 문자열")
    if "pronunciation" not in data or not (data["pronunciation"] is None or isinstance(data["pronunciation"], str)):
        problems.append("pronunciation 누락 또는 타입 오류")

    tts = data.get("tts_parts")
    if not isinstance(tts, dict):
        problems.append("tts_parts 누락")
    else:
        for k in ("intro", "bridge", "outro"):
            if not _nonempty(tts.get(k)):
                problems.append(f"tts_parts.{k} 누락/빈 문자열")

    sub = data.get("subtitle_lines")
    if not isinstance(sub, list) or not sub or not all(_nonempty(s) for s in sub):
        problems.append("subtitle_lines 누락/비정상")

    vocab = data.get("vocab")
    if not isinstance(vocab, list) or len(vocab) != 3:
        problems.append("vocab는 정확히 3개여야 함")
    else:
        for i, v in enumerate(vocab):
            if not isinstance(v, dict):
                problems.append(f"vocab[{i}] dict 아님")
                continue
            for k in ("word", "type", "meaning"):
                if not _nonempty(v.get(k)):
                    problems.append(f"vocab[{i}].{k} 누락/빈 문자열")
            if "phonetic" not in v:
                problems.append(f"vocab[{i}].phonetic 누락")

    dlg = data.get("dialogue")
    if not isinstance(dlg, list) or not (2 <= len(dlg) <= 4):
        problems.append("dialogue는 2~4개여야 함")
    else:
        for i, d in enumerate(dlg):
            if not isinstance(d, dict):
                problems.append(f"dialogue[{i}] dict 아님")
                continue
            for k in ("speaker", "line", "korean_phonetic", "korean"):
                if not _nonempty(d.get(k)):
                    problems.append(f"dialogue[{i}].{k} 누락/빈 문자열")
            if "pronunciation" not in d:
                problems.append(f"dialogue[{i}].pronunciation 누락")
        if _nonempty(data.get("right")):
            right = _loose(data["right"])
            if not any(right in _loose(d.get("line", "")) for d in dlg if isinstance(d, dict)):
                problems.append("right가 dialogue의 어느 line에도 포함되지 않음")

    cta = data.get("cta")
    if isinstance(cta, str) and any(ord(ch) >= 0x1F000 for ch in cta):
        problems.append("cta에 이모지 포함")

    return problems
