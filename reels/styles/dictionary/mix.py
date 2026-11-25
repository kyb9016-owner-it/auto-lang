"""사전(dictionary) 스타일 믹스: 아주 조용한 앰비언트 패드 + 부드러운 피아노 음(공개되는 순간) + 희미한 종이 넘기는 소리. 전부 합성(외부 음원 0).
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
music = np.zeros((N, 2), np.float32); fx = np.zeros((N, 2), np.float32); vox = np.zeros((N, 2), np.float32); amb = np.zeros((N, 2), np.float32)
mid = lambda m: 440 * 2 ** ((m - 69) / 12)
rs = np.random.default_rng(1604)

def piano(f, d=1.8, v=1.0):
    """부드러운 피아노풍: 배음 몇 개 + 지수 감쇠, 해머 노이즈는 저역 통과로 둥글게"""
    tt = t_(d); x = np.zeros_like(tt)
    for k, (a, tau) in enumerate([(1, .9), (.45, .55), (.22, .35), (.1, .22), (.05, .14)], 1):
        x += a * np.sin(2 * np.pi * f * k * (1 + .0004 * k * k) * tt) * np.exp(-tt / (tau * (d / 1.8) + .05))
    x *= np.minimum(1, tt / .008)
    h = lp(noise(.06), 1200) * env_exp(.06, .014) * .15
    x[:len(h)] += h
    return norm(lp(x, 3600)) * v
def pad(freqs, d, v=1.0):
    tt = t_(d); x = np.zeros_like(tt)
    for f in freqs:
        for det in (-.003, 0, .003):
            ph = 2 * np.pi * f * (1 + det) * tt
            x += np.sin(ph) + .2 * np.sin(2 * ph)
    x = lp(x, 900, 2) / (len(freqs) * 3)
    e = np.minimum(1, tt / (d * .4)) * np.minimum(1, (d - tt) / (d * .4))
    return x * e ** 1.5 * v
def rustle(d=.34, v=1.0):
    """종이 넘기는 소리: 대역 통과 노이즈 + 부드러운 엔벨로프(느린 어택)"""
    x = bp(noise(d), 1800, 7000) * np.sin(np.pi * np.linspace(0, 1, int(d * SR), endpoint=False)) ** 1.6
    n = len(x); x = x * (.6 + .4 * np.abs(lp(noise(d), 40)[:n]) / (np.abs(lp(noise(d), 40)).max() + 1e-9))
    return norm(x) * v

# ---- 음악: 5초마다 바뀌는 느린 패드(Cmaj9 - Am9 - Fmaj7 - G6) + 아주 듬성한 높은 피아노 음 ----
chords = [(48, [60, 64, 67, 71]), (45, [57, 60, 64, 71]), (41, [57, 60, 64, 67]), (43, [59, 62, 67, 69])]
BAR = 5.0
for b in range(int(DUR / BAR) + 1):
    t = b * BAR; root, ch = chords[b % 4]
    add(music, pad([mid(root)] + [mid(x) for x in ch], BAR + 3.0), t - .8, .5, -.1)
    add(music, pad([mid(root - 12)], BAR + 3.0, 1), t - .8, .3, .1)
    for off in (1.2, 3.1):                               # 한 마디에 두 음만
        if rs.random() < .25: continue
        n = ch[int(rs.integers(0, len(ch)))] + 12
        add(music, piano(mid(n), 2.6), t + off, .14, rs.uniform(-.3, .3))
add(music, piano(mid(67), 4.0), 0.1, .25, 0)
add(music, piano(mid(72), 4.5), max(0, DUR - 3.4), .22, 0)

# ---- 효과음(아주 조용하게) ----
PENT = [72, 74, 76, 79, 81, 84]; ni = 0
REVEAL = ('right', 'explain', 'cta', 'd0l', 'd1l', 'v0w', 'v1w', 'wrong')
for e in EV:
    t, ty = e['t'], e['type']
    if ty == 'write' and e.get('id') in REVEAL:        # 공개되는 주요 문구: 부드러운 피아노 음 하나(5음 음계 순환)
        add(fx, piano(mid(PENT[ni % len(PENT)]), 1.8, 1), t + .05, .1, rs.uniform(-.25, .25)); ni += 1
    elif ty == 'pop': add(fx, piano(mid(PENT[(ni + 2) % len(PENT)] - 12), 1.4, .8), t, .07, 0)
    elif ty == 'slam': pass
    elif ty == 'wipe':                                 # 쪽 넘김: 희미한 종이 소리
        add(fx, rustle(max(.3, e['d'] + .1), 1), t - .02, .2, 0)
    elif ty == 'mark':
        k = e['kind']
        if k == 'cross': add(fx, piano(mid(55), 1.6, .8), t + .05, .14, 0)
        elif k == 'check': add(fx, piano(mid(72), 2.0, 1), t + .05, .16, 0); add(fx, piano(mid(79), 2.2, 1), t + .2, .12, 0)
        elif k == 'strike': add(fx, rustle(.22, 1), t, .12, 0)

# ---- 앰비언트: 아주 낮은 룸 톤(공기) ----
air = lp(noise(N / SR), 400) * (.7 + .3 * np.sin(2 * np.pi * .12 * np.arange(N) / SR))
amb[:, 0] = amb[:, 1] = air.astype(np.float32)

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
rms = lambda x, m=act: np.sqrt(np.mean(x[m] ** 2) + 1e-12) if m.any() else 1.0
vr = rms(vox.mean(1)); mr = rms(music.mean(1)) + 1e-9
gm = vr / mr / (10 ** (11 / 20)); music *= gm                    # 음악 = 음성 −11dB
ar = rms(amb.mean(1), np.ones(N, bool)) + 1e-9; amb *= vr / ar / (10 ** (34 / 20))
mixd = music + fx * .8 + amb + vox
fade = np.ones(N, np.float32); nf = int(1.0 * SR); e0 = int(DUR * SR); fade[e0 - nf:e0] = np.linspace(1, 0, nf)
mixd *= fade[:, None]
mixd = np.stack([limit(mixd[:, 0], .9), limit(mixd[:, 1], .9)], 1)[:int(DUR * SR)]
os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
sf.write(OUT, mixd, SR)
print('mix ok', mixd.shape, 'music gain', round(float(gm), 3))
