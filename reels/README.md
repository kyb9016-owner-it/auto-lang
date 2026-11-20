# reels/ — LangCard 모션 릴스 엔진 (lemo-opuscar 기반)

구독 큐 JSON(`{lang, data}`) 한 개 → 세로 1080×1920 / 24fps / h264+aac `final.mp4`.

## 사용
```bash
python3 reels/build.py <queue.json> --style chalkboard --out <final.mp4> [--pace strict|fast] [--keep-work] [--workers 3]
python3 reels/build.py ... --style random      # reels/styles/ 중 무작위
```
- 필요: lemo-opuscar(커밋 00a7f9e, 기본 `/Users/kong/projects/lemo-opuscar`, `LEMO_LIB`로 변경), 그 `.venv`(edge-tts), node, ffmpeg, 인터넷(edge-tts).
- 작업은 `tempfile.mkdtemp` 임시 폴더에서 하고 끝나면 삭제(`--keep-work`면 보존). 단계 실패 시 즉시 중단하고 명령·stderr 출력.
- 파이프라인: 폴더 구성 → 내레이션 줄(`timeline.js narration()`) → TTS(`tts_zh.py`, 줄별 voice) → `events.mjs` → `video.mjs` → 스타일 `mix.py` → `mux.sh`.
- 음성: 한국어 `ko-KR-SunHiNeural`(intro/bridge/outro) + 목표어(en Jenny/Guy, zh Xiaoxiao/Yunxi, ja Nanami/Keita; wrong·right는 첫 음성, 대화는 A/B 교대). 단어·CTA는 효과음만.
- `--pace strict`(기본): LIB readcheck 기본값(한글 4.5자/초)을 만족하도록 장면 길이를 잡음 → 약 50~55초. `fast`: 한글 7.5자/초 기준 → 약 40초. fast 검증: `readcheck.mjs <작업폴더> --size 1080x1920 --cjk-cps 7.5 --latin-cps 22 --pad 0.7`.

## 구조
```
reels/build.py
reels/common/timeline.js     # 스타일 공통: 데이터+dur.json → 장면·cue·EV·DUR, readNeed/writeDur/texts 헬퍼
reels/styles/<name>/index.html + mix.py
```
장면 순서: HOOK(0~2.3초, 0초부터 화면 가득+쾅 효과, 이후 제목으로 줄어 위에 남음) → WRONG → RIGHT → EXPLAIN → DIALOGUE → VOCAB → CTA.

## 새 스타일 추가
1. `reels/styles/<name>/` 에 `index.html`, `mix.py` 를 만든다(build.py가 자동 인식, `--style random` 후보가 됨).
2. `index.html`: `<script src="common/timeline.js">` 로드 → `LC.load()`(data.json·dur.json) → `tl = LC.build(input, dur, opts)`.
   - `tl.scenes[]`: `{id, t0, t1, wipe, wipeTop, cue{...}}` (id: hook/wrong/right/explain/dialogue/vocab/cta). 장면 안 요소의 시작 시각은 `cue`에 있고, 스타일은 그 시각에 그리기만 한다. 장면 길이·읽기 시간은 timeline이 계산하므로 스타일이 바꾸지 않는다.
   - `tl.C`(정제된 문구, 이모지 제거됨), `tl.EV`, `tl.DUR`. `window.DUR/EV/READY/render(t)/TEXTS(t)` 를 LIB 규약대로 노출. `TEXTS`는 `LC.texts(list)`로 정리하고, 읽혀야 할 글자는 첫 프레임부터 전체 문구·박스를 보고한다.
   - 글자 크기는 측정 기반 자동 축소(줄바꿈 포함), 안전영역 x 80~1000, y 280~1230 유지.
   - 폰트는 build.py가 `fonts/`에 복사(Fredoka=OFL, Noto Sans KR/JP/SC). 새 폰트가 필요하면 build.py에 추가.
3. `mix.py <작업폴더> [out.wav]`: `LIB` 환경변수 필요. `events.json`의 EV(`voice{id,t,d}`, `write`, `pop`, `slam`, `mark{kind}`, `wipe`)로 `out/voice/<id>.wav`와 합성 효과음·음악을 배치.
4. 검증: build 후 `node $LIB/core/render/readcheck.mjs <작업폴더> --size 1080x1920`, `still.mjs`/`sheet.py` 로 눈 검수.

## chalkboard 한계
- 글씨는 폰트 글리프를 사선 경계로 "써 내려가는" 방식(획순 엔진 아님: 한·일·중 전 글자 획 데이터가 없음). ❌/✅/밑줄/말풍선/북마크는 획으로 직접 그림.
- 설명(explain)이 46자를 넘으면 쉼표 단위로 앞 절을 버리고 결론 쪽만 보여 준다. 큐에 `explanation_short` 필드가 있으면 그걸 우선 사용.
