"""노트(notebook) 스타일 믹스: 로파이 피아노 + 부드러운 패드(박자 느리게), 글씨 쓸 때 연필 긁는 틱, 페이지 넘김 소리. 전부 합성(외부 음원 0).
사용: LIB=<lemo-opuscar 경로> LIB/.venv/bin/python mix.py <작업폴더> [출력 wav]
작업폴더에서 events.json(페이지가 내보낸 EV)과 out/voice/<id>.wav 를 읽는다. 어떤 데이터에도 동작(범용)."""
import json, sys, os
LIB = os.environ.get('LIB') or sys.exit('mix.py: LIB 환경변수(lemo-opuscar 경로) 필요')
sys.path.insert(0, LIB)
import numpy as np, soundfile as sf, soxr
from scipy.ndimage import uniform_filter1d
from core.audio import sfx
from core.audio.sfx import SR, add, bp, lp, hp, noise, t_, env_exp, norm, compress, limit

HERE = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else sys.exit('usage: mix.py <workdir> [out.wav]')
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, 'out', 'mix.wav')
ev = json.load(open(f'{HERE}/events.json'))
DUR = ev['dur']; EV = ev['ev']
N = int((DUR + 1.0) * SR)
music = np.zeros((N, 2), np.float32); fx = np.zeros((N, 2), np.float32); vox = np.zeros((N, 2), np.float32)
mid = lambda m: 440 * 2 ** ((m - 69) / 12)
rs = np.random.default_rng(1126)

# ---- 악기 ----
def keys(f, d=2.0, v=1.0):
    """로파이 전기피아노풍: 사인 배음 + 부드러운 감쇠 + 살짝 어두운 로우패스, 미세한 피치 흔들림"""
    tt = t_(d); wob = 1 + .0012 * np.sin(2 * np.pi * 4.2 * tt + rs.random() * 6)
    x = np.zeros_like(tt)
    for k, (a, tau) in enumerate([(1, 1.0), (.42, .6), (.2, .35), (.09, .2)], 1):
        x += a * np.sin(2 * np.pi * f * k * wob * tt) * np.exp(-tt / (tau * (d / 2.0) + .05))
    x *= np.minimum(1, tt / .008)
    x += .5 * np.sin(2 * np.pi * f * 2.0 * tt) * np.exp(-tt / .06) * .3            # 해머 같은 짧은 배음
    return norm(lp(x, 2600)) * v
def pad(freqs, d, v=1.0):
    tt = t_(d); x = np.zeros_like(tt)
    for f in freqs:
        for det in (-.003, 0, .003):
            ph = 2 * np.pi * f * (1 + det) * tt
            x += np.sin(ph) + .2 * np.sin(2 * ph)
    x = lp(x, 900, 2) / (len(freqs) * 3)
    e = np.minimum(1, tt / (d * .35)) * np.minimum(1, (d - tt) / (d * .35))
    return x * e ** 1.5 * v
def sub(f, d=1.4, v=1.0):
    tt = t_(d); x = np.sin(2 * np.pi * f * tt) * np.minimum(1, tt / .02) * np.exp(-tt / (d * .5))
    return norm(x) * v
def brush(d=.12, v=1.0):
    return norm(bp(noise(d), 4000, 9000) * np.hanning(int(round(d * SR)))) * v

# ---- 음악: 70bpm 부드러운 코드 4개 반복(Fmaj7 - Em7 - Dm7 - Cmaj9), 피아노 아르페지오 + 패드 + 낮은 베이스 + 아주 작은 브러시 ----
BPM = 70; BEAT = 60 / BPM; BAR = 4 * BEAT
chords = [(41, [57, 60, 64, 69]), (40, [55, 59, 62, 67]), (38, [53, 57, 60, 65]), (36, [55, 59, 62, 67])]
pattern = [0, 1, 2, 3, 2, 1, 2, 1]                              # 8분음표 아르페지오 인덱스
for b in range(int(DUR / BAR) + 2):
    t0 = b * BAR; root, ch = chords[b % 4]
    add(music, pad([mid(x) for x in ch], BAR + 1.6), t0 - .4, .5, -.1)
    add(music, sub(mid(root + 12), BAR * .9), t0, .55, 0)
    for j, ix in enumerate(pattern):
        if j % 2 == 1 and rs.random() < .35: continue           # 군데군데 비워 숨 쉬게
        n = ch[ix] + (12 if j in (0, 4) else 0)
        add(music, keys(mid(n), 1.8), t0 + j * BEAT / 2 + (rs.random() - .5) * .018, .26 if j % 2 == 0 else .17, rs.uniform(-.25, .25))
    for j in (3, 7):
        add(music, brush(.12, 1), t0 + j * BEAT / 2, .1, .2)
add(music, keys(mid(72), 3.5), max(0, DUR - 3.2), .22, 0)       # 끝에 길게 남는 음

# ---- 효과음 ----
def scratch(d, n, v=1.0, lo=1800, hi=6500):
    """연필·펜 긁는 소리: 짧은 대역 잡음 획을 왕복하듯 이어 붙인다(글자 수 n이 많을수록 촘촘)"""
    L = max(int(d * SR), 400); x = np.zeros(L, np.float32); k = int(max(2, min(14, d / .075 + n / 14)))
    r = np.random.default_rng(int(n * 131 + d * 1000))
    for i in range(k):
        s = int(i * (L - int(.06 * SR)) / max(1, k - 1)); ln = int((.05 + .05 * r.random()) * SR)
        seg = bp(noise(ln / SR), lo * (.8 + .4 * r.random()), hi * (.8 + .3 * r.random())) * np.hanning(ln) * (.45 + .55 * r.random()) * (1 if i % 2 == 0 else .75)
        e = min(L, s + ln); x[s:e] += seg[:e - s].astype(np.float32)
    return x * v
def page_flip(d, v=1.0):
    """종이 한 장 넘기는 소리: 대역 잡음의 쓸림 + 시작의 잔 바스락 + 끝의 가벼운 '탁'"""
    n = int(max(.3, d) * SR); tt = np.arange(n) / n
    sw = bp(noise(max(.3, d)), 900, 6500) * (np.sin(np.pi * tt) ** 1.5) * (.6 + .4 * np.sin(2 * np.pi * 9 * tt))
    for _ in range(6):
        s = int(rs.random() * n * .35); m = 120 + int(rs.random() * 200); sw[s:s + m] += (hp(noise(m / SR), 2500) * np.exp(-np.arange(m) / 40) * (.5 + rs.random())).astype(np.float32)[:max(0, min(m, n - s))]
    e = int(n * .9); m = int(.05 * SR); sw[e:e + m] += (hp(noise(m / SR), 1200) * np.exp(-np.arange(m) / 500) * 1.4).astype(np.float32)[:max(0, min(m, n - e))]
    return norm(sw) * v
def tap(v=1.0):
    d = .07; tt = t_(d); return norm(np.sin(2 * np.pi * 330 * tt) * env_exp(d, .012) + hp(noise(d), 1500) * env_exp(d, .006) * .5) * v

for e in EV:
    t, ty = e['t'], e['type']
    if ty == 'write': add(fx, scratch(e['d'], e.get('n', 8)), t, .5, 0)
    elif ty == 'pop': add(fx, tap(1), t, .35, 0)
    elif ty == 'slam': pass                                   # 노트는 쾅 소리 없음
    elif ty == 'wipe': add(fx, page_flip(max(.3, e['d'])), t, .75, 0)
    elif ty == 'mark':
        k = e['kind']
        if k == 'cross': add(fx, scratch(.38, 14, 1, 1500, 5500), t, .55, 0)
        elif k == 'check': add(fx, scratch(.4, 12, 1, 1500, 5500), t, .5, 0); add(fx, keys(mid(79), 1.6), t + .38, .2, 0); add(fx, keys(mid(84), 1.6), t + .5, .14, 0)
        elif k == 'strike': add(fx, scratch(.42, 16, 1, 1200, 5000), t, .65, 0)

# ---- 음성 ----
vm = np.zeros(N, np.float32)
for e in EV:
    if e['type'] != 'voice': continue
    p = f"{HERE}/out/voice/{e['id']}.wav"
    w, sr = sf.read(p); w = w if w.ndim == 1 else w.mean(1)
    w = soxr.resample(w.astype(np.float32), sr, SR); w = hp(compress(w, .12, 3.0), 80)
    s = int(e['t'] * SR)
    if s + len(w) > N: w = w[:N - s]
    vox[s:s+len(w), :] += w[:, None]; vm[s:s+len(w)] += np.abs(w)
env = uniform_filter1d(vm, int(.25 * SR)); duck = 1 - .6 * np.clip(env / .05, 0, 1)
duck = uniform_filter1d(duck, int(.15 * SR)).astype(np.float32)
music *= duck[:, None]; fx *= (1 - .3 * np.clip(env / .05, 0, 1))[:, None].astype(np.float32)
act = vm > .01
rms = lambda x: np.sqrt(np.mean(x[act] ** 2) + 1e-12) if act.any() else 1.0
vr = rms(vox.mean(1)); mr = rms(music.mean(1)) + 1e-9
gm = vr / mr / (10 ** (11 / 20)); music *= gm                    # 음악 = 음성 −11dB
mixd = music + fx * .8 + vox
fade = np.ones(N, np.float32); nf = int(1.0 * SR); e0 = int(DUR * SR); fade[e0 - nf:e0] = np.linspace(1, 0, nf)   # 끝 1초 페이드아웃
mixd *= fade[:, None]
mixd = np.stack([limit(mixd[:, 0], .9), limit(mixd[:, 1], .9)], 1)[:int(DUR * SR)]
os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
sf.write(OUT, mixd, SR)
print('mix ok', mixd.shape, 'music gain', round(float(gm), 3))
