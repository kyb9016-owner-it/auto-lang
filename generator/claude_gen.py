"""Claude API로 회화 표현 생성"""
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
- MUST be different from these recently used expressions:
{history_str}

Return ONLY this JSON:
{{
  "main_expression": "the {lc['name']} expression",{pronunciation_fields}
  "korean_phonetic": "한글 발음 (한국어 독자가 읽을 수 있는 한글 발음 표기, 예: Nice to meet you → 나이스 투 밋 유)",
  "korean_translation": "Korean translation",
  "context": "짧은 상황 설명 (15자 이내)",
  "bonus_expression": "a related bonus expression in {lc['name']}",
  "bonus_korean": "Korean translation of the bonus expression",
  "vocab": [
    {{"word": "word1 in {lc['name']}", "meaning": "Korean meaning", "pronunciation": "romanization if needed else null", "korean_phonetic": "한글 발음"}},
    {{"word": "word2 in {lc['name']}", "meaning": "Korean meaning", "pronunciation": "romanization if needed else null", "korean_phonetic": "한글 발음"}},
    {{"word": "word3 in {lc['name']}", "meaning": "Korean meaning", "pronunciation": "romanization if needed else null", "korean_phonetic": "한글 발음"}}
  ],
  "emoji": "1~2 relevant emojis"
}}"""


def _call_api(prompt: str) -> dict:
    """Claude API 호출 후 JSON 파싱"""
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=900,
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
    recent = history.get_recent(lang)
    recent_set = set(recent)
    data = {}

    for attempt in range(1, max_retries + 1):
        prompt = _build_prompt(lang, topic)
        data = _call_api(prompt)
        expr = data["main_expression"]

        if expr not in recent_set:
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
