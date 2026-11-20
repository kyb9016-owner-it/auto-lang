# reels/ — LangCard 모션 릴스 엔진 (lemo-opuscar 기반)

구독 큐 JSON(`{lang, data}`) 한 개 → 세로 1080×1920 / 24fps / h264+aac `final.mp4` (목표 28~33초).

## 사용
```bash
python3 reels/build.py <queue.json> --style chalkboard --out <final.mp4> [--pace fast|strict] [--keep-work] [--workers 3]
python3 reels/build.py ... --style random      # reels/styles/ 중 무작위
```
- 필요: lemo-opuscar(커밋 00a7f9e, 기본 `/Users/kong/projects/lemo-opuscar`, `LEMO_LIB`로 변경), 그 `.venv`(edge-tts), node, ffmpeg, 인터넷(edge-tts).
- 작업은 `tempfile.mkdtemp` 임시 폴더에서 하고 끝나면 삭제(`--keep-work`면 보존). 단계 실패 시 즉시 중단하고 명령·stderr 출력. (프레임 렌더가 드물게 페이지 `NetworkError`로 한 번 실패한 적이 있음 — 재실행하면 통과)
- 파이프라인: 폴더 구성 → 내레이션 줄(`timeline.js narration()`) → TTS(`tts_zh.py`, 줄별 voice) → `events.mjs` → `video.mjs` → 스타일 `mix.py` → `mux.sh`.
- 음성: 한국어 `ko-KR-SunHiNeural`(intro/bridge/outro) + 목표어(en Jenny/Guy, zh Xiaoxiao/Yunxi, ja Nanami/Keita; wrong·right는 첫 음성, 대화는 A/B 교대). 단어·CTA는 효과음만.
- `--pace fast`(기본): 한글 7.5자/초·영문 22자/초·여유 0.7초. `strict`: LIB readcheck 기본값(4.5/15/1.5) — 훨씬 길어진다(약 50초).

## 장면과 길이 (timeline.js가 결정 — 스타일은 건드리지 않는다)
HOOK(0~2.3초) → WRONG → RIGHT → EXPLAIN(선택) → DIALOGUE(2턴) → VOCAB(선택, 2개) → CTA.
- EXPLAIN: 큐의 `explanation_short`(그 키 이름 그대로)를 쓴다. 없으면 `explanation` 첫 문장에서 22자 이내 결론 절(쉼표 단위 → 없으면 뒤쪽 단어들)을 뽑고, 그래도 없으면 장면 생략.
- DIALOGUE: right가 든 턴 + 바로 앞 턴(right 턴이 첫 턴이거나 없으면 첫 두 턴). 내레이션 id는 `d0`,`d1`.
- VOCAB: 앞 2개. `LC.buildAuto`가 33초를 넘으면 VOCAB → EXPLAIN 순으로 자동 생략(`tl.dropped`). 스타일은 장면이 없을 수 있음을 전제로 `tl.by.<id>` 존재 여부로 그린다.
- 장면 전환: `scene.t1`에 지우개가 시작해 `scene.wipe`(0.4초) 동안 훑는다. **다음 장면은 `prev.t1`에 이미 시작(겹침)** — 지워지는 쪽 옛 장면, 지나간 자리 새 장면. 훅→WRONG은 와이프 없음(훅이 제목으로 줄어 RIGHT 끝(`hook.titleUntil`)까지 남음).

## 스타일 작성 규약 (chalkboard = 참조 구현)
스타일 폴더 = `reels/styles/<name>/index.html` + `mix.py`. build.py가 자동 인식하며 `--style random` 후보가 된다.

**역할 분담**: 장면 목록·시작/종료 시각·cue·내레이션 타이밍·읽기 시간은 전부 `timeline.js`(`tl`)가 정한다. 스타일은 그 시각에 맞춰 **그리기와 음향만** 한다. 장면 길이·순서·음성 시각을 스타일이 바꾸지 말 것(음성 파일이 `EV`의 `voice` 시각에 깔리므로 어긋난다).

**페이지 계약** (LIB core/README와 동일): `window.READY`, `window.render(t)`(결정적), `window.DUR`, `window.EV`, `window.TEXTS(t)`. 폰트 로드 후에 READY.
```js
const { input, dur, opts } = await LC.load();          // data.json, dur.json
const tl = LC.buildAuto(input, dur, opts);              // {C, scenes[], by{}, EV, DUR, WIPE, dropped}
window.DUR = tl.DUR; window.EV = tl.EV;
```
- `tl.C`: 정제된 문구(이모지 제거됨: hook, wrong, wrongPh, right, rightPh, rightKo, roman, explain, cta, handle, vocab[2], dialogue[2], hl). 이모지는 폰트에 없으니 ❌✅ 같은 기호는 스타일이 도형으로 직접 그린다.
- `scene.cue`: 요소별 시작 시각(예: `wrong.cue.text/ph/strike`, `dialogue.cue.turns[i].{bubble,line,ph,ko}`). 글씨 쓰는 시간은 `LC.writeDur(text)`를 쓴다(timeline이 같은 값으로 길이를 계산함).
- 한 장면 안에서는 `t < scene.t1`일 때만 읽을 글자를 `TEXTS`에 보고한다(와이프 구간은 제외).

**글자 크기 하한** (`LCL.MIN`, 1080×1920 기준 px): 훅 ≥110(처음 2초 화면 가득) · 훅 제목 ≥52 · WRONG/RIGHT 본문 ≥72(권장 90 이상, 길면 2~3줄 줄바꿈 후 측정 축소) · 말풍선 외국어 줄 ≥56 · 말풍선 한글 보조줄 ≥40. 하한에서도 안 맞으면 줄 수를 늘리거나 문구를 자르지 말고 레이아웃을 바꾼다.

**안전영역** (`LCL.SAFE`): 글자는 x 80~1000, y 300~1480 안에만. 상단 280 미만과 하단 1500 이후(인스타 UI·캡션에 가려짐)에는 핵심 글자 금지. 콘텐츠는 세로 중앙(y≈890)을 중심으로 크게 배치해 칠판(화면)을 채운다. 자동 줄바꿈·크기 축소는 측정 기반이어야 한다(데이터마다 길이가 다르다).

**빈 화면 규칙**: 어떤 프레임도 쓸 글자·도형이 전혀 없는 구간이 0.3초를 넘으면 안 된다. 전환은 0.4초 이내, 이전 장면을 지우는 동시에 다음 장면이 시작되게 겹친다. 새 장면의 첫 요소(아이콘·박스·말풍선 테두리)는 `t0`에 바로 시작하고 글씨는 `t0+0.1~0.3` 안에 시작한다.

**TEXTS 보고 의무**: 읽혀야 하는 모든 글자는 쓰기 시작 프레임부터 **전체 문구**와 화면 픽셀 박스로 보고한다(`LC.texts(list)`). 읽을 글자를 `pass: true`로 숨기지 말 것. 박스가 프레임 밖이면 readcheck가 실패한다.

**공통 헬퍼** (`reels/common/layout.js`, `LCL.make(ctx, fontFor)`): `fit`(측정 기반 줄바꿈·자동 축소), `stack`(세로 쌓기·간격 축소), `dialogue`(말풍선 배치·세로 가운데·하한 준수), `wrap`. 새 스타일은 이를 재사용하고 새로 짜지 않는다. 스타일 고유의 폰트·색·그리기만 구현.

**mix.py**: `LIB` 환경변수 필요, `mix.py <작업폴더> [out.wav]`. `events.json`의 EV(`voice{id,t,d}`, `write{d,n}`, `pop`, `slam`, `mark{kind: cross|check|strike}`, `wipe{d}`)로 `out/voice/<id>.wav`와 `core/audio/sfx.py` 합성 효과음·음악만 배치(외부 음원 0). 음성 위에 음악 −11dB 정도로 덕킹.

**검증 절차** (스타일 추가 시 매번):
1. `python3 reels/build.py <sample>.json --style <name> --out <mp4> --keep-work` 를 en·ja·zh 샘플로 실행(성공, 28~33초, 1080×1920 h264+aac).
2. `node $LIB/core/render/readcheck.mjs <작업폴더> --size 1080x1920 --cjk-cps 7.5 --latin-cps 22 --pad 0.7` 통과(`--pace strict`로 만든 것은 기본값으로).
3. `still.mjs --range 0.1:30:1.5` + `sheet.py` 로 장면 모음을 만들어 **눈으로** 확인: 글자 잘림·두부 문자·상단 침범·겹침·빈 칠판·하한 크기.
4. 선택: 페이지가 `window.CHALKPIX`처럼 "그려진 픽셀 수"를 노출하면 0.04초 간격으로 훑어 빈 구간(0.3초 초과) 검사를 자동화.

## chalkboard 한계
- 글씨는 폰트 글리프를 사선 경계로 "써 내려가는" 방식(획순 엔진 아님: 한·일·중 전 글자 획 데이터가 없음). ❌/✅/밑줄/말풍선/북마크는 획으로 직접 그림.
