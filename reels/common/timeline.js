// LangCard 릴스 공통 타임라인 (스타일 무관)
// 입력: data.json({lang, data, opts}) + dur.json(TTS 음성 길이) → 장면 목록·내레이션 이벤트·읽기 시간 계산
// 스타일(index.html)은 window.LC.build()의 결과(tl)를 읽어 그리기만 한다. 규약은 reels/README.md 참조.
(function (g) {
  'use strict';

  // ---- 읽기 속도(페이스) ----
  // strict = LIB readcheck 기본값(한글 4.5자/초, 영문 15자/초, 여유 1.5초). fast = 실제 한국 시청자 속도에 가까운 값.
  const PACE = {
    strict: { cjk: 4.5, lat: 15, pad: 1.5 },
    fast: { cjk: 7.5, lat: 22, pad: 0.7 },
  };
  const WIPE = 0.4;        // 장면 사이 지우개 시간(초)
  const GAP = 0.3;         // 음성 줄 사이 간격

  const isCJK = ch => /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Hangul}]/u.test(ch);

  // 이모지·그림문자 제거(폰트에 글리프가 없으면 두부 문자가 되므로). ❌✅ 등은 스타일이 획으로 직접 그린다.
  function clean(s) {
    if (s == null) return '';
    return String(s)
      .replace(/[\p{Extended_Pictographic}‍️⃣]/gu, '')
      .replace(/[✅❌✔✖]/g, '')
      .replace(/\s+/g, ' ').trim();
  }

  // LIB readcheck와 같은 공식
  function readNeed(text, pace) {
    let cjk = 0, other = 0;
    for (const ch of text) { if (/\s/.test(ch)) continue; isCJK(ch) ? cjk++ : other++; }
    return Math.max(1.5, cjk / pace.cjk + other / pace.lat + pace.pad);
  }

  // 분필로 글씨 쓰는 시간(글자 수 기준, 스타일 공통)
  function writeDur(text) {
    const n = [...text].filter(c => !/\s/.test(c)).length;
    return Math.min(1.6, Math.max(0.5, 0.3 + n * 0.035));
  }

  // 설명 한 줄 요약(최대 maxC자). data.explanation_short 우선(큐 생성 프롬프트가 채울 키).
  // 없으면 explanation 첫 문장에서 maxC자 이내 결론 절(쉼표 단위, 뒤쪽 우선) → 없으면 뒤쪽 단어들 → 그래도 없으면 '' (설명 장면 생략)
  function pickExplain(d, maxC) {
    const count = s => [...s].filter(c => !/\s/.test(c)).length;
    if (d.explanation_short) return clean(d.explanation_short);
    const full = clean(d.explanation);
    if (!full) return '';
    const first = full.split(/(?<=[.!?。！？])\s+/)[0];
    const clauses = first.split(/(?<=[,，、])\s*/).map(x => x.replace(/[,，、]\s*$/, '').trim()).filter(Boolean);
    for (let i = clauses.length - 1; i >= 0; i--) if (count(clauses[i]) <= maxC && count(clauses[i]) >= 6) return clauses[i];
    const words = first.split(' '); let out = [];
    while (words.length && count(out.concat(words[words.length - 1]).join('')) <= maxC) out.unshift(words.pop());
    const tail = out.join(' ');
    return count(tail) >= 8 ? tail : '';
  }

  // 대화 중 right 문장을 포함한 턴(강조용): 정규화 부분일치 또는 글자 이중쌍 유사도
  function highlightIndex(dialogue, right) {
    const norm = s => s.toLowerCase().replace(/[\s\p{P}]/gu, '');
    const R = norm(right);
    if (!R) return -1;
    const bi = s => { const set = new Set(); for (let i = 0; i < s.length - 1; i++) set.add(s.slice(i, i + 2)); return set; };
    let best = -1, bs = 0;
    dialogue.forEach((t, i) => {
      const L = norm(t.line);
      let sc = L.includes(R) ? 1 : 0;
      if (!sc) { const a = bi(L), b = bi(R); let inter = 0; a.forEach(x => b.has(x) && inter++); sc = inter / Math.max(1, Math.min(a.size, b.size)); }
      if (sc > bs) { bs = sc; best = i; }
    });
    return bs >= 0.6 ? best : -1;
  }

  function normalize(input) {
    const lang = input.lang, d = input.data || {};
    const tp = d.tts_parts || {};
    const C = {
      lang,
      hook: clean(d.hook),
      wrong: clean(d.wrong), wrongPh: clean(d.wrong_ko_phonetic),
      right: clean(d.right), rightPh: clean(d.right_ko_phonetic), rightKo: clean(d.right_ko),
      roman: lang === 'en' ? '' : clean(d.pronunciation),
      tts: { intro: clean(tp.intro) || clean(d.hook), bridge: clean(tp.bridge) || '이렇게 말해요', outro: clean(tp.outro) || clean(d.right_ko) },
      explain: pickExplain(d, 22),
      cta: clean(d.cta),
      handle: '@langcard.studio',
      vocab: (d.vocab || []).slice(0, 2).map(v => ({ word: clean(v.word), type: clean(v.type), meaning: clean(v.meaning), phonetic: clean(v.phonetic) })),
      dialogue: [],
    };
    if (!C.hook || !C.wrong || !C.right) throw new Error('hook/wrong/right 필수');
    // 대화는 2턴만: right가 든 턴 + 바로 앞 턴(right 턴이 첫 턴이거나 없으면 첫 두 턴)
    const all = (d.dialogue || []).slice(0, 4).map(t => ({ speaker: clean(t.speaker) || 'A', line: clean(t.line), pron: clean(t.pronunciation), ph: clean(t.korean_phonetic), ko: clean(t.korean) }));
    const h = highlightIndex(all, C.right);
    const pick = h > 0 ? [h - 1, h] : [0, 1];
    C.dialogue = pick.filter(i => all[i]).map(i => all[i]);
    C.hl = h > 0 ? 1 : (h === 0 ? 0 : -1);
    return C;
  }

  // 내레이션 줄 목록(build.py가 같은 규약으로 lines.json을 만든다: 이 함수는 id·text만 돌려준다)
  function narration(C) {
    const L = [
      { id: 'intro', text: C.tts.intro, who: 'ko' },
      { id: 'wrong', text: C.wrong, who: 'tg' },
      { id: 'bridge', text: C.tts.bridge, who: 'ko' },
      { id: 'right', text: C.right, who: 'tg' },
      { id: 'outro', text: C.tts.outro, who: 'ko' },
    ];
    C.dialogue.forEach((t, i) => L.push({ id: 'd' + i, text: t.line, who: i % 2 === 0 ? 'tgA' : 'tgB' }));
    return L;
  }

  // ---- 타임라인 ----
  function build(input, durMap, opts) {
    opts = opts || {};
    const pace = PACE[opts.pace || 'fast'] || PACE.fast;
    const drop = new Set(opts.drop || []);
    const C = normalize(input);
    const D = id => { const v = durMap[id]; if (!(v > 0)) throw new Error('dur.json에 ' + id + ' 없음'); return v; };
    const need = tx => readNeed(tx, pace);
    const EV = [];
    const ev = (t, type, o) => EV.push(Object.assign({ t: +t.toFixed(3), type }, o || {}));
    const voice = (t, id) => ev(t, 'voice', { id, d: +D(id).toFixed(3) });
    const write = (t, id, tx) => ev(t, 'write', { id, d: writeDur(tx), n: [...tx].length });
    const hold = (tx, start) => start + 0.5 * writeDur(tx) + need(tx);   // 글씨 하나가 충분히 읽히는 시각
    const scenes = [], by = {};
    const add = (sc) => { scenes.push(sc); by[sc.id] = sc; return sc; };

    // ① HOOK — 0초부터 화면에 꽉 차게(스크롤 멈춤). 끝에 제목으로 줄어 위로 올라가 WRONG·RIGHT 동안 남는다.
    const hk = add({ id: 'hook', t0: 0, cue: {} });
    ev(0, 'pop'); ev(0.16, 'slam');
    voice(0.12, 'intro');
    hk.t1 = Math.max(2.3, 0.12 + D('intro') + 0.3);
    hk.cue.move = [hk.t1 - 0.55, hk.t1];
    hk.wipe = 0;

    // ② WRONG
    const w = add({ id: 'wrong', t0: hk.t1, cue: {} });
    { const s = w.t0, c = w.cue;
      c.icon = s; ev(s, 'mark', { kind: 'cross' });
      c.text = s + 0.25; write(c.text, 'wrong', C.wrong);
      c.voice = s + 0.3; voice(c.voice, 'wrong');
      c.ph = s + 0.85; if (C.wrongPh) write(c.ph, 'wrongPh', C.wrongPh);
      c.strike = Math.max(c.voice + D('wrong'), c.text + writeDur(C.wrong)) + 0.1; ev(c.strike, 'mark', { kind: 'strike' });
      const ends = [c.voice + D('wrong') + 0.6, c.strike + 0.35 + 0.7, hold(C.wrong, c.text)];
      if (C.wrongPh) ends.push(hold(C.wrongPh, c.ph));
      w.t1 = Math.max(...ends);
      w.wipe = WIPE; w.wipeTop = 440; }

    // ③ RIGHT
    const r = add({ id: 'right', t0: w.t1, cue: {} });
    { const s = r.t0, c = r.cue;
      c.icon = s; ev(s, 'mark', { kind: 'check' });
      c.bridge = s + 0.15; voice(c.bridge, 'bridge');
      c.voice = c.bridge + D('bridge') + 0.25; voice(c.voice, 'right');
      c.text = s + 0.3; write(c.text, 'right', C.right);   // 다리 음성(bridge) 동안 먼저 써 두어 칠판이 비지 않게
      c.ph = c.voice + 0.4; if (C.rightPh) write(c.ph, 'rightPh', C.rightPh);
      c.roman = c.voice + 0.65; if (C.roman) write(c.roman, 'roman', C.roman);
      c.outro = c.voice + D('right') + GAP; voice(c.outro, 'outro');
      c.ko = Math.min(c.outro - 0.2, c.voice + 1.0); if (C.rightKo) write(c.ko, 'rightKo', C.rightKo);
      const ends = [c.outro + D('outro') + 0.7, hold(C.right, c.text)];
      if (C.rightPh) ends.push(hold(C.rightPh, c.ph));
      if (C.roman) ends.push(hold(C.roman, c.roman));
      if (C.rightKo) ends.push(hold(C.rightKo, c.ko));
      r.t1 = Math.max(...ends);
      r.wipe = WIPE; r.wipeTop = 270; }
    hk.titleUntil = r.t1;   // 훅 제목은 RIGHT가 끝날 때까지 화면에 남는다

    // 장면 사이: 지우개가 prev.t1~prev.t1+WIPE에 지나가며, 다음 장면은 prev.t1에 이미 시작(겹침) → 빈 칠판 구간이 없다
    let prev = r;
    // ④ EXPLAIN — 한 줄 요약(≤22자). 요약이 없거나 자동 단축 규칙으로 drop되면 장면 생략
    if (C.explain && !drop.has('explain')) {
      const ex = add({ id: 'explain', t0: prev.t1, cue: {} }); const c = ex.cue; c.box = ex.t0; c.text = ex.t0 + 0.1;
      write(c.text, 'explain', C.explain); ev(ex.t0, 'pop');
      ex.t1 = Math.max(ex.t0 + 2.2, hold(C.explain, c.text));
      ex.wipe = WIPE; ex.wipeTop = 270; prev = ex;
    }
    // ⑤ DIALOGUE — 2턴, 말풍선 순차, 줄마다 목표언어 음성
    const dl = add({ id: 'dialogue', t0: prev.t1, cue: { turns: [] } });
    { let tv = dl.t0 + 0.4, end = dl.t0 + 2;
      C.dialogue.forEach((tn, i) => {
        const cu = { bubble: tv - 0.3, voice: tv, line: tv, ph: tv + 0.25, ko: tv + 0.5 };
        voice(cu.voice, 'd' + i); ev(cu.bubble, 'pop');
        if (tn.line) write(cu.line, 'd' + i + 'l', tn.line);
        if (tn.ph) write(cu.ph, 'd' + i + 'p', tn.ph);
        if (tn.ko) write(cu.ko, 'd' + i + 'k', tn.ko);
        [[tn.line, cu.line], [tn.ph, cu.ph], [tn.ko, cu.ko]].forEach(([x, st]) => { if (x) end = Math.max(end, hold(x, st)); });
        end = Math.max(end, tv + D('d' + i) + 0.6);
        dl.cue.turns.push(cu);
        tv += D('d' + i) + GAP;
      });
      dl.t1 = end; dl.wipe = WIPE; dl.wipeTop = 270; prev = dl; }

    // ⑥ VOCAB — 앞 2개, 음성 없이 효과음만
    if (C.vocab.length && !drop.has('vocab')) {
      const vb = add({ id: 'vocab', t0: prev.t1, cue: { cards: [] } });
      let end = vb.t0 + 2;
      C.vocab.forEach((v, i) => {
        const s = vb.t0 + 0.05 + i * 0.5, cu = { word: s, type: s + 0.1, meaning: s + 0.25, ph: s + 0.4 };
        ev(s, 'pop');
        if (v.word) write(cu.word, 'v' + i + 'w', v.word);
        if (v.meaning) write(cu.meaning, 'v' + i + 'm', v.meaning);
        if (v.phonetic) write(cu.ph, 'v' + i + 'p', v.phonetic);
        [[v.word, cu.word], [v.meaning, cu.meaning], [v.phonetic, cu.ph]].forEach(([x, st]) => { if (x) end = Math.max(end, hold(x, st)); });
        vb.cue.cards.push(cu);
      });
      vb.t1 = end; vb.wipe = WIPE; vb.wipeTop = 270; prev = vb;
    }

    // ⑦ CTA 엔드카드
    const ct = add({ id: 'cta', t0: prev.t1, cue: {} });
    { const c = ct.cue; c.icon = ct.t0; c.text = ct.t0 + 0.1; c.handle = ct.t0 + 0.7;
      ev(ct.t0, 'mark', { kind: 'check' });
      write(c.text, 'cta', C.cta || C.handle); write(c.handle, 'handle', C.handle);
      ct.t1 = Math.max(hold(C.cta || C.handle, c.text), hold(C.handle, c.handle)) + 0.2;
      ct.wipe = 0; }

    scenes.forEach((sc, i) => { if (i < scenes.length - 1) ev(scenes[i].t1, 'wipe', { d: sc.wipe || 0 }); });
    EV.sort((a, b) => a.t - b.t);
    return { C, pace, scenes, by, EV, DUR: +(ct.t1 + 0.9).toFixed(3), WIPE, dropped: [...drop] };
  }

  // 길이 상한(기본 33초): 넘으면 단어 장면 → 설명 장면 순으로 자동 생략
  function buildAuto(input, durMap, opts) {
    opts = opts || {};
    const max = opts.maxDur || 33; let drop = [], tl = build(input, durMap, Object.assign({}, opts, { drop }));
    for (const d of ['vocab', 'explain']) { if (tl.DUR <= max) break; drop = drop.concat(d); tl = build(input, durMap, Object.assign({}, opts, { drop })); }
    return tl;
  }

  // readcheck용 TEXTS 헬퍼: 스타일이 모은 [{id,text,x0,y0,x1,y1,pass?}]를 규약 형식으로 정리
  function texts(list) {
    return list.map(b => ({ id: b.id, text: b.text, x0: b.x0, y0: b.y0, x1: b.x1, y1: b.y1, ...(b.pass ? { pass: true } : {}) }));
  }

  // data.json / dur.json 불러오기(페이지 기준 상대경로)
  async function load() {
    const [input, dur] = await Promise.all([
      fetch('data.json').then(r => { if (!r.ok) throw new Error('data.json ' + r.status); return r.json(); }),
      fetch('dur.json').then(r => { if (!r.ok) throw new Error('dur.json ' + r.status); return r.json(); }),
    ]);
    return { input, dur, opts: input.opts || {} };
  }

  g.LC = { PACE, WIPE, clean, readNeed, writeDur, normalize, narration, build, buildAuto, texts, load, isCJK };
})(typeof window !== 'undefined' ? window : globalThis);
