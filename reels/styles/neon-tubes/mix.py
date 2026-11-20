"""네온 튜브 스타일 믹스: 변압기 험 + 릴레이 클릭 + 네온 점등음 + 시티팝풍 합성 음악(외부 음원 0), 음성 wav 배치.
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
RNG = np.random.default_rng(11)

# ---- 악기 ----
def pluck(f, d=.5, v=1):
    tt = t_(d); x = 2 * ((tt * f) % 1) - 1; x += .6 * (2 * ((tt * f * 1.004) % 1) - 1)
    x = lp(x, 3200) * env_exp(d, .16) * np.minimum(1, tt / .003)
    return norm(x) * v
def bass(f, d=.4, v=1):
    tt = t_(d); x = (2 * ((tt * f) % 1) - 1) * .7 + np.sin(2 * np.pi * f * tt)
    e = np.minimum(1, tt / .008) * np.exp(-tt / (d * .55)); return norm(lp(x, 700) * e) * v
def bell(f, d=1.2, v=1):
    tt = t_(d); x = sum(a * np.sin(2 * np.pi * f * r * tt) * env_exp(d, tau) for r, a, tau in [(1, 1, .5), (2.76, .35, .25), (5.4, .2, .1)])
    return norm(x) * v
def pad(freqs, d, v=1):
    tt = t_(d); x = np.zeros_like(tt)
    for f in freqs:
        for det in (-.005, 0, .005): x += 2 * (((tt * f * (1 + det)) % 1) - .5)
    x = lp(x, 1300, 2) / (len(freqs) * 3)
    return x * np.minimum(1, tt / (d * .3)) * np.minimum(1, (d - tt) / (d * .3)) * v
def kick(v=1):
    d = .3; tt = t_(d); f = 46 + 95 * np.exp(-tt * 30)
    return norm(np.sin(2 * np.pi * np.cumsum(f) / SR) * env_exp(d, .11)) * v
def clap(v=1):
    d = .14; return norm(bp(noise(d), 1100, 3600) * (env_exp(d, .03) + .5 * np.roll(env_exp(d, .02), int(.012 * SR)))) * v
def hat(v=1):
    d = .05; return norm(hp(noise(d), 7000) * env_exp(d, .011)) * v

# ---- 네온 고유 음 ----
def tick(v=1):
    return sfx.click(1.9 + RNG.random() * .6, v)        # 릴레이/점등 클릭
def neon_strike(v=1):
    """점등: 클릭 - 어둠 - 클릭 - 지직 - 램프업(50ms/70ms 규칙에 맞춘 3번 깜박임)"""
    d = .5; x = np.zeros(int(d * SR), np.float32)
    for tt, g in [(0, 1), (.12, .7), (.27, .9)]:
        c = sfx.click(1.4, 1) * g; s = int(tt * SR); x[s:s + len(c)] += c[:len(x) - s]
    tt = t_(d); saw = 2 * ((tt * 120) % 1) - 1
    buzz = bp(saw, 500, 3500) * np.clip((tt - .27) / .12, 0, 1) * np.exp(-tt / .4) * .5
    cr = lp(hp(noise(d), 3500) * (RNG.random(len(tt)) > .993) * 4, 9000) * np.exp(-tt / .3)
    return norm(x * .9 + buzz + cr) * v
def sizzle(d=.6, v=1):
    tt = t_(d); cr = hp(noise(d), 2500) * (RNG.random(len(tt)) > .985) * 3
    return norm(lp(cr, 9000) * env_exp(d, d * .5)) * v
def glass_ting(v=1):
    d = .9; tt = t_(d)
    return norm(sum(a * np.sin(2 * np.pi * f * tt) * env_exp(d, tau) for f, a, tau in [(3520, 1, .25), (5274, .5, .15), (7459, .3, .08)])) * v
def hum(d, v=1):
    tt = t_(d); x = sum(a * np.sin(2 * np.pi * f * tt + p) for f, a, p in [(100, 1, 0), (200, .5, 1), (300, .35, 2), (500, .12, 3)])
    x *= 1 + .08 * np.sin(2 * np.pi * 0.7 * tt)
    return norm(x) * v

# ---- 음악: 시티팝풍 합성(Am7-Fmaj7-Cmaj7-G6, 박자 .5초, 훅 구간은 킥+클랩으로 강하게) ----
BEAT = .5
prog = [(33, [57, 60, 64, 67]), (29, [53, 57, 60, 64]), (36, [55, 60, 64, 67]), (31, [55, 59, 62, 64])]
wipes = [(e['t'], e.get('d', .4)) for e in EV if e['type'] == 'wipe']
inw = lambda t: any(a - .02 <= t <= a + d for a, d in wipes)
for b in range(int(DUR / BEAT)):
    t = b * BEAT; bar = b // 4; root, ch = prog[bar % 4]; ph = b % 4
    last = t > DUR - 2.4
    # 8분 아르페지오 2음(둘째는 엇박)
    add(music, pluck(mid(ch[(b * 2) % 4] + 12), .4), t, .22)
    add(music, pluck(mid(ch[(b * 2 + 1) % 4] + 12), .4), t + .25, .17)
    if not last:
        if t < 2.4:
            add(music, kick(1.0), t, .8)
            if ph in (1, 3): add(music, clap(), t, .35)
            add(music, hat(), t + .25, .22)
        else:
            if ph in (0, 2): add(music, kick(.9), t, .6)
            if ph in (1, 3): add(music, clap(), t, .22)
            add(music, hat(), t + .25, .14)
        if ph in (0, 2, 3): add(music, bass(mid(root + (12 if ph == 3 else 0)), .38), t, .4)
    if ph == 0: add(music, pad([mid(x) for x in ch], 2.0), t, .1)
for t, d in wipes:
    add(music, bell(mid(88), 1.0), t + d, .12, .2)
add(music, bell(mid(81), 2.4), max(0, DUR - 2.4), .14, .3)

# ---- 효과음 ----
PENT = [69, 72, 74, 76, 79, 81, 84, 86, 88]   # 점등할 때마다 올라가는 음(A 단조 펜타토닉)
note = [0]
def strike_note(t, v=.5):
    m = PENT[note[0] % len(PENT)] + 12 * (note[0] // len(PENT) % 2); note[0] += 1
    add(fx, pluck(mid(m), .6), t, v, .0)
for e in EV:
    t, ty = e['t'], e['type']
    if ty == 'write':
        d = e['d']; n = max(3, int(d / .045))
        for k in range(n):
            add(fx, tick(.4 + .3 * RNG.random()), t + k * d / n, .17, 0)           # 튜브를 따라 달리는 점등 릴레이
        add(fx, bp(2 * ((t_(d) * 120) % 1) - 1, 500, 2600) * np.sin(np.pi * t_(d) / d) * .4, t, .16, 0)
    elif ty == 'pop': add(fx, neon_strike(.8), t, .55, 0); strike_note(t + .27)
    elif ty == 'slam':
        add(fx, sfx.thump(1, 52), t, 1.0); add(fx, sfx.whoosh(.25), max(0, t - .12), .35, 0)
        add(fx, neon_strike(1), max(0, t - .1), .8, 0); add(fx, sizzle(.7), t, .6, 0); add(fx, sfx.crash(.6), t, .18, 0)
    elif ty == 'wipe':
        d = max(.3, e['d']); tt = t_(d)
        zap = bp(noise(d), 700, 5000) * (.6 + .4 * np.sign(np.sin(2 * np.pi * 70 * tt))) * np.hanning(len(tt))
        add(fx, zap, t, .6, 0)
        for k in range(5): add(fx, sfx.clack(1.6, .6), t + k * d / 5, .25, 0)
    elif ty == 'mark':
        k = e['kind']
        if k == 'cross': add(fx, neon_strike(.9), t, .6, 0); add(fx, sfx.thump(1, 90), t + .1, .5, 0)
        elif k == 'check': add(fx, neon_strike(.9), t, .55, 0); add(fx, sfx.ding(1), t + .3, .45, 0); strike_note(t + .35, .6)
        elif k == 'strike':       # 오답 줄이 깨진다: 흰 섬광 + 유리 금 + 지직 + 어두워짐
            add(fx, glass_ting(1), t, .5, 0); add(fx, sizzle(.8), t, .7, 0); add(fx, sfx.thump(.8, 60), t, .5, 0)

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
gm = vr / mr / (10 ** (11 / 20)); music *= gm
mixd = music + fx * .8 + vox
# 변압기 험: 음성 레벨 기준 약 -30dB 상시(음악 앞뒤 공백에도 "침묵 = 험")
h = hum(N / SR, 1)[:N] * vr * .035
mixd += h[:, None].astype(np.float32)
mixd = np.stack([limit(mixd[:, 0], .9), limit(mixd[:, 1], .9)], 1)[:int(DUR * SR)]
os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
sf.write(OUT, mixd, SR)
print('mix ok', mixd.shape, 'music gain', round(float(gm), 3))
