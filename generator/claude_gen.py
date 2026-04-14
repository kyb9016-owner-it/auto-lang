"""Claude API로 회화 표현 생성"""
from __future__ import annotations
import json
import os
import anthropic
from config import LANG_CONFIG
from generator import history

_PREFETCH_DIR = "output"


def load_prefetch(date_str: str, lang: str) -> dict | None:
    """
    프리페치 파일에서 특정 날짜·언어 표현 로드.
    Claude API 실패 시 폴백으로 사용.
    """
    path = os.path.join(_PREFETCH_DIR, f"data_prefetch_{date_str}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            saved = json.load(f)
        return saved.get("data", {}).get(lang)
    except Exception:
        return None

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

SYSTEM_PROMPT = """You are a language learning content creator for Korean learners studying English, Chinese, or Japanese.
Generate practical, natural, commonly used expressions — NOT textbook formal ones.
Always respond with valid JSON only. No markdown, no extra text."""


def _build_prompt(lang: str, topic: dict) -> str:
    lc = LANG_CONFIG[lang]
    recent = history.get_recent(lang)
    history_str = "\n".join(f"  - {h}" for h in recent) if recent else "  (없음)"

    pronunciation_fields = ""
    if lc["has_pronunciation"]:
        pronunciation_fields = f"""
  "pronunciation": "{lc['pronunciation_label']} (romanization/pinyin of main_expression)",
  "bonus_pronunciation": "{lc['pronunciation_label']} of bonus_expression","""
    else:
        pronunciation_fields = """
  "pronunciation": null,
  "bonus_pronunciation": null,"""

    return f"""Generate ONE {lc['name']} conversation expression for Korean learners.

Topic: {topic['topic_en']} ({topic['topic_ko']})

Rules:
- MUST be a real, widely-used expression that native speakers actually say in daily life
- NOT textbook/formal — use casual, authentic spoken language
- Difficulty: beginner ~ intermediate
- Use proper mixed case for English (e.g. "How have you been?" not "HOW HAVE YOU BEEN?")
- MUST be different in MEANING from these recently used expressions (not just wording):
{history_str}

Return ONLY this JSON:
{{
  "korean_anchor": "이 표현을 쓰는 상황을 짧게 설명 (3~8자, ~할 때/~하는 상황). 예: '처음 만났을 때', '길 물어볼 때', '약속 잡을 때', '고마울 때'",
  "main_expression": "the {lc['name']} expression",{pronunciation_fields}
  "korean_phonetic": "한글 발음 (한국어 독자가 읽을 수 있는 한글 발음 표기, 예: Nice to meet you → 나이스 투 밋 유)",
  "korean_translation": "Korean translation",
  "context": "짧은 상황 설명 (15자 이내)",
  "bonus_expression": "a related bonus expression in {lc['name']}",
  "bonus_korean": "Korean translation of the bonus expression",
  "bonus_korean_phonetic": "bonus_expression의 한글 발음 표기 (예: All good things, I hope! → 올 굿 씽스, 아이 홉!)",
  "vocab": [
    {{"word": "word1 in {lc['name']}", "meaning": "Korean meaning", "pronunciation": "romanization if needed else null", "korean_phonetic": "한글 발음"}},
    {{"word": "word2 in {lc['name']}", "meaning": "Korean meaning", "pronunciation": "romanization if needed else null", "korean_phonetic": "한글 발음"}},
    {{"word": "word3 in {lc['name']}", "meaning": "Korean meaning", "pronunciation": "romanization if needed else null", "korean_phonetic": "한글 발음"}}
  ],
  "usage_tip": "이 표현의 사용 상황과 뉘앙스를 2~3문장으로 설명 (한국어). 언제 쓰는지, 어떤 뉘앙스인지, 비슷한 표현과의 차이 등 포함. 예: '오랫동안 못 봤던 사람에게 쓰는 표현이에요. Nice to meet you는 처음 만날 때 쓰고, 이 표현은 아는 사람에게 다시 만났을 때 써요. 격식 없는 상황에서 자연스럽게 사용할 수 있어요.'",
  "emoji": "1~2 relevant emojis"
}}"""


def _call_api(prompt: str) -> dict:
    """Claude API 호출 후 JSON 파싱"""
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1800,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    text = message.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)


def generate(lang: str, topic: dict, max_retries: int = 3) -> dict:
    """
    표현 생성 후 히스토리 저장. dict 반환.
    중복 감지 시 최대 max_retries 회 재시도.
    """
    data = {}

    for attempt in range(1, max_retries + 1):
        prompt = _build_prompt(lang, topic)
        data = _call_api(prompt)
        expr = data["main_expression"]

        if not history.is_duplicate(lang, expr):
            history.add(lang, expr)
            if attempt > 1:
                print(f"  ↻ {lang} 재시도 {attempt}회 만에 새 표현: {expr}")
            return data

        # 중복 감지 — 재시도
        print(f"  ⚠ {lang} 중복 감지 (시도 {attempt}/{max_retries}): {expr!r}")

    # max_retries 초과해도 중복이면 마지막 결과 그냥 사용
    print(f"  ✗ {lang} 재시도 초과, 중복 허용: {data['main_expression']!r}")
    history.add(lang, data["main_expression"])
    return data


_HOOK_SYSTEM = """You are a language correction content creator for Korean Instagram.
You create "common mistake → correct expression" content for Korean learners.
The content must be accurate: WRONG must be a real, common mistake Koreans actually make.
RIGHT must be the natural, native-speaker expression.
Always respond with valid JSON only. No markdown, no extra text."""


def _build_hook_prompt(lang: str, recent_wrongs: list[str]) -> str:
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


def generate_hook(lang: str, max_retries: int = 3) -> dict:
    """
    HOOK형 콘텐츠 생성 (WRONG→RIGHT 교정 포맷).
    중복 감지: wrong 표현 기준으로 체크.
    """
    for attempt in range(1, max_retries + 1):
        recent_wrongs = history.get_recent_hook(lang)
        prompt = _build_hook_prompt(lang, recent_wrongs)
        data = _call_api(prompt)
        wrong = data["wrong"]

        if not history.is_hook_duplicate(lang, wrong):
            history.add_hook(lang, wrong, data["right"])
            if attempt > 1:
                print(f"  ↻ {lang} 재시도 {attempt}회 만에 새 표현: {wrong}")
            return data

        print(f"  ⚠ {lang} 중복 감지 (시도 {attempt}/{max_retries}): {wrong!r}")

    print(f"  ✗ {lang} 재시도 초과, 중복 허용: {data['wrong']!r}")
    history.add_hook(lang, data["wrong"], data["right"])
    return data


_COLLECTION_SYSTEM = """You are a language content creator for Korean learners.
Generate relatable Korean everyday phrases with their natural equivalents in English, Chinese, and Japanese.
Always respond with valid JSON only. No markdown, no extra text."""


def generate_collection(theme: dict, n: int = 8) -> list[dict]:
    """
    테마 기반 한국어 표현 → EN/ZH/JA 비교 컬렉션 생성.
    Returns: [{"korean_phrase": "...", "context": "...",
               "en": "...", "en_phonetic": "...(한글 발음)",
               "zh": "...", "zh_phonetic": "...(pinyin)",
               "ja": "...", "ja_phonetic": "...(romaji)"}, ...]
    """
    prompt = f"""Generate {n} short Korean everyday phrases with their natural equivalents in English, Chinese, and Japanese.

Theme: {theme['title_en']} ({theme['title_ko']})

Rules:
- Korean phrases must be short (2~8 chars), commonly used in daily conversation
- Foreign expressions must be casual/natural, NOT textbook formal
- Each phrase must be conceptually distinct from others in the list
- context: 1~2 word situational hint in Korean (10자 이내)
- Do NOT repeat similar meanings
- en_phonetic: 한글 발음 표기 (e.g. "저스트 윙 잇")
- zh_phonetic: 한글 발음 표기 (e.g. "쑤이 비엔 바")
- ja_phonetic: 한글 발음 표기 (e.g. "난토카 나루 요")

Return ONLY a JSON array of exactly {n} objects:
[
  {{
    "korean_phrase": "대충 해",
    "context": "귀찮을 때",
    "en": "Just wing it",
    "en_phonetic": "저스트 윙 잇",
    "zh": "随便吧",
    "zh_phonetic": "쑤이 비엔 바",
    "ja": "なんとかなるよ",
    "ja_phonetic": "난토카 나루 요"
  }}
]"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=_COLLECTION_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    text = message.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    items = json.loads(text)
    if not isinstance(items, list):
        raise ValueError(f"generate_collection: expected list, got {type(items)}")
    return items[:n]
