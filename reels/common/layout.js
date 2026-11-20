// LangCard 릴스 공통 레이아웃 헬퍼 (스타일 무관, 측정 기반)
// 스타일은 measure용 2D ctx와 fontFor(kind,size)->CSS font 문자열만 넘기면 줄바꿈·자동 축소·세로 쌓기·말풍선 배치를 계산해 쓸 수 있다.
//   const L = LCL.make(ctx, (kind, size) => `700 ${size}px ...`);   // kind: 'ko'(한글 보조/설명) | 'tg'(목표 언어)
//   const B = L.fit(text, kind, {maxW, maxLines, s0, s1, lh});      // -> {text,kind,size,lines,lw[],w,lhp,h}
// 글자 크기 하한·안전영역은 LCL.MIN / LCL.SAFE (README의 스타일 규약)
(function (g) {
  'use strict';
  const SAFE = { x0: 80, x1: 1000, y0: 280, top: 300, bottom: 1480 };   // 글자는 x 80~1000, y 300~1480 (1500 이후는 인스타 UI에 가려짐)
  const MIN = { hook: 110, title: 52, body: 72, bubbleTarget: 56, bubbleSub: 40 };

  const CJK_RE = /[぀-ヿ㐀-鿿＀-￯]/u;
  const PUNCT_RE = /^[。、，．！？）」』】,.!?:;)”’…~]+$/u;
  // 라틴·한글은 단어 단위, 일본어·중국어는 글자 단위로 끊는다. 문장부호는 앞 토큰에 붙여 줄 머리에 오지 않게 한다.
  function tokens(s) {
    const out = [], re = /[぀-ヿ㐀-鿿＀-￯]|[^\s぀-ヿ㐀-鿿＀-￯]+|\s+/gu;
    let m;
    while ((m = re.exec(s))) {
      const tk = m[0];
      if (/^\s+$/.test(tk)) { out.push({ sp: true }); continue; }
      if (PUNCT_RE.test(tk) && out.length && !out[out.length - 1].sp) { out[out.length - 1].t += tk; continue; }
      out.push({ t: tk, cjk: CJK_RE.test(tk) && tk.length === 1 });
    }
    return out;
  }

  function make(ctx, fontFor) {
    const wd = s => ctx.measureText(s).width;
    function wrap(text, maxW) {   // 현재 ctx.font 기준
      const lines = []; let line = '', pendSp = false;
      for (const tk of tokens(text)) {
        if (tk.sp) { pendSp = line !== ''; continue; }
        const cand = line + (pendSp ? ' ' : '') + tk.t;
        if (line === '' || wd(cand) <= maxW) line = cand; else { lines.push(line); line = tk.t; }
        pendSp = false;
        while (wd(line) > maxW && [...line].length > 1) {   // 한 토큰이 maxW보다 길면 글자 단위로 쪼갠다
          let head = '';
          for (const ch of line) { if (wd(head + ch) > maxW && head) break; head += ch; }
          lines.push(head); line = line.slice(head.length);
        }
      }
      if (line) lines.push(line);
      return lines;
    }
    // 크기 자동 축소: s0에서 시작해 줄 수·폭이 맞을 때까지 2px씩. s1(하한)에서 멈춘다(그때는 넘칠 수 있음)
    function fit(text, kind, o) {
      const lh = o.lh || 1.28; let size = Math.round(o.s0);
      for (;;) {
        ctx.font = fontFor(kind, size);
        const lines = wrap(text, o.maxW), lw = lines.map(l => ctx.measureText(l).width), w = Math.max(...lw, 1);
        if ((lines.length <= o.maxLines && w <= o.maxW + .5) || size <= Math.round(o.s1))
          return { text, kind, size, lines, lw, w, lhp: size * lh, h: lines.length * size * lh };
        size -= 2;
      }
    }
    // 세로 쌓기: items=[{id,text,kind,s0,s1,maxLines,color,gap,lh,maxW?}]. 전체가 y1을 넘으면 s0 배율 k와 간격만 줄인다(s1 하한은 유지).
    function stack(items, y0, y1, maxW, cx) {
      let last;
      for (let k = 1; k > .45; k -= .05) {
        const bl = items.filter(it => it.text).map(it => Object.assign({ it }, fit(it.text, it.kind, { maxW: it.maxW || maxW, maxLines: it.maxLines, s0: it.s0 * k, s1: Math.min(it.s1, it.s0 * k), lh: it.lh })));
        let y = y0; bl.forEach((b, i) => { y += i ? (b.it.gap || 30) * k : 0; b.y = y; y += b.h; });
        last = bl.map(b => Object.assign(b, { id: b.it.id, color: b.it.color, cx: cx == null ? 540 : cx }));
        last.bottom = y;
        if (y <= y1) break;
      }
      return last;
    }
    // 말풍선 배치: turns=[{line,ph,ko}]. 외국어 줄 ≥ MIN.bubbleTarget, 보조줄 ≥ MIN.bubbleSub. 영역 안에서 세로 가운데.
    // 반환 [{a,b,c,x,y,w,h,side}] — a/b/c는 fit 결과(+id,cx,y), side 'L'|'R'(홀짝 교대)
    function dialogue(turns, o) {
      o = o || {};
      const X0 = SAFE.x0, X1 = SAFE.x1, Y0 = o.y0 || SAFE.top, Y1 = o.y1 || SAFE.bottom, PADX = 32, PADY = 26, GAP = o.gap || 56, inner = (o.maxInner || 820), idp = o.idPrefix || 'd';
      let res, k = 1;
      for (; k >= .6; k -= .05) {
        res = turns.map((t, i) => {
          const a = fit(t.line, 'tg', { maxW: inner, maxLines: 3, s0: 76 * k, s1: MIN.bubbleTarget, lh: 1.2 });
          const b = t.ph ? fit(t.ph, 'ko', { maxW: inner, maxLines: 2, s0: 50 * k, s1: MIN.bubbleSub, lh: 1.25 }) : null;
          const c = t.ko ? fit(t.ko, 'ko', { maxW: inner, maxLines: 2, s0: 54 * k, s1: MIN.bubbleSub, lh: 1.25 }) : null;
          const parts = [a, b, c].filter(Boolean);
          const w = Math.min(X1 - X0, Math.max(...parts.map(p => p.w)) + PADX * 2), h = parts.reduce((s, p) => s + p.h, 0) + (parts.length - 1) * 10 + PADY * 2;
          return { a, b, c, w: Math.max(w, 420), h, side: i % 2 === 0 ? 'L' : 'R' };
        });
        if (res.reduce((s, r) => s + r.h, 0) + (turns.length - 1) * GAP <= Y1 - Y0) break;
      }
      const tot = res.reduce((s, r) => s + r.h, 0) + (turns.length - 1) * GAP;
      let y = Math.max(Y0, (Y0 + Y1) / 2 - tot / 2);
      res.forEach((r, i) => {
        r.x = r.side === 'L' ? X0 : X1 - r.w; r.y = y; y += r.h + GAP;
        let yy = r.y + PADY; const cx = r.x + r.w / 2;
        [['a', 'l'], ['b', 'p'], ['c', 'k']].forEach(([key, s]) => { const p = r[key]; if (!p) return; p.id = idp + i + s; p.cx = cx; p.y = yy; yy += p.h + 10; });
      });
      return res;
    }
    return { wrap, fit, stack, dialogue };
  }
  g.LCL = { SAFE, MIN, tokens, make };
})(typeof window !== 'undefined' ? window : globalThis);
