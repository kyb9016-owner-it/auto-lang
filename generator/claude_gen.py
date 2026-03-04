"""Claude API로 회화 표현 생성"""
import json
import os
import anthropic
from config import LANG_CONFIG, SLOT_CONFIG
from generator import history

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

SYSTEM_PROMPT = """You are a language learning content creator for Korean learners studying English, Chinese, or Japanese.
Generate practical, natural, commonly used expressions — NOT textbook formal ones.
Always respond with valid JSON only. No markdown, no extra text."""


def _build_prompt(lang: str, slot: str) -> str:
    lc = LANG_CONFIG[lang]
    sc = SLOT_CONFIG[slot]
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

Topic: {sc['topic_en']} ({sc['topic_ko']})
Time slot: {sc['label']} ({sc['topic_ko']})

Rules:
- Must be natural, practical, real-world usage (not textbook)
- Difficulty: beginner ~ intermediate
- Use proper mixed case for English (e.g. "How have you been?" not "HOW HAVE YOU BEEN?")
- MUST be different from these recently used expressions:
{history_str}

Return ONLY this JSON:
{{
  "main_expression": "the {lc['name']} expression",{pronunciation_fields}
  "korean_translation": "Korean translation",
  "context": "짧은 상황 설명 (15자 이내)",
  "bonus_expression": "a related bonus expression in {lc['name']}",
  "bonus_korean": "Korean translation of the bonus expression",
  "emoji": "1~2 relevant emojis"
}}"""


def generate(lang: str, slot: str) -> dict:
    """표현 생성 후 히스토리 저장. dict 반환"""
    prompt = _build_prompt(lang, slot)

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    text = message.content[0].text.strip()
    # JSON 블록 추출 (혹시 ```json 감싸진 경우 대비)
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    data = json.loads(text)
    history.add(lang, data["main_expression"])
    return data
