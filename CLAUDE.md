# LangCard Studio — Claude Code 프로젝트 가이드

## 프로젝트 개요
Instagram 자동화 + 커스텀 캐러셀 제작 통합 파이프라인.

---

## 1. 자동 스케줄 파이프라인 (LangCard)

영어·중국어·일본어 회화 카드를 하루 3회 자동 포스팅.

```bash
python3 main.py --slot [morning|lunch|evening]        # 실제 포스팅
python3 main.py --slot morning --dry-run              # 이미지만 생성
python3 main.py --slot morning --dry-run --lang en    # 특정 언어만
```

**슬롯별 주제**
| 슬롯 | 시간 (KST) | 주제 |
|------|-----------|------|
| morning | 08:00 | 인사 & 소개 |
| lunch   | 12:00 | 카페 & 식당 |
| evening | 20:00 | 여행 & 쇼핑 |

---

## 2. 커스텀 캐러셀 에이전트 파이프라인

자유 주제로 Instagram 캐러셀을 제작할 때 오케스트레이터에게 오더.

**사용법**: 원하는 주제와 방향을 말하면 오케스트레이터가 전체 파이프라인을 관리.

**파이프라인 흐름**
```
card-dispatcher (라우팅)
  └→ instagram-carousel-orchestrator (총괄)
       ├→ carousel-content-strategist (전략)
       ├→ instagram-carousel-copywriter (카피)
       ├→ instagram-carousel-generator (HTML)
       ├→ [HUMAN REVIEW] ← 반드시 승인 후 진행
       └→ slide-production-exporter (PNG 출력)
```

---

## 3. 환경 설정

`.env` 파일에 다음 키 필요:
- `ANTHROPIC_API_KEY`
- `CLOUDINARY_URL`
- `INSTAGRAM_ACCESS_TOKEN`
- `INSTAGRAM_BUSINESS_ID`

---

## 4. 주요 파일 구조

```
main.py                  # LangCard 자동화 진입점
config.py                # 슬롯/언어 설정
generator/claude_gen.py  # Claude API 표현 생성
renderer/card.py         # Pillow 카드 렌더러
renderer/themes.py       # 9개 컬러 테마
uploader/cloudinary_up.py
uploader/instagram.py
.claude/agents/          # 커스텀 캐러셀 에이전트들
```
