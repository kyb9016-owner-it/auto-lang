"""text-flash-cuts 믹스: 하프시코드 16분 오스티나토 + 콘트라베이스 피치카토 + 우드블록 시계(박자 0.4초=150BPM), 카드 히트(고역 잡음+금속 링+52Hz 드롭, 컷마다 음정 상승),
장면 컷 직전 하드 사일런스(음악만 게이트). 외부 음원 0. 사용: LIB=<lemo-opuscar> LIB/.venv/bin/python mix.py <작업폴더> [출력 wav]"""
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

# ---- 악기 ----
def harpsi(f, d=.28, v=1):       # 하프시코드: 톱니+배음, 빠른 감쇠
    tt = t_(d); x = np.zeros_like(tt)
    for k, a in ((1, 1), (2, .55), (3, .4), (4, .25), (5, .15)): x += a * np.sin(2 * np.pi * f * k * tt + .3 * k)
    return norm(bp(x, 300, 6000) * np.exp(-tt / (d * .22)) * np.minimum(1, tt / .002)) * v
def contrabass(f, d=.4, v=1):    # 피치카토
    tt = t_(d); x = np.sin(2 * np.pi * f * tt) + .5 * np.sin(2 * np.pi * 2 * f * tt) + .25 * np.sin(2 * np.pi * 3 * f * tt)
    return norm(lp(x, 700) * np.minimum(1, tt / .004) * np.exp(-tt / (d * .38))) * v
def woodblock(v=1):
    d = .07; tt = t_(d); return norm(np.sin(2 * np.pi * 1180 * tt) * env_exp(d, .012) + .5 * bp(noise(d), 1500, 4500) * env_exp(d, .008)) * v
def card_hit(pitch=1.0, v=1):    # 카드 히트: 고역 잡음 + 금속 링(1760/2637/4186Hz) + 52Hz 드롭
    d = .5; tt = t_(d)
    tr = hp(noise(d), 2500) * env_exp(d, .02)
    ring = sum(a * np.sin(2 * np.pi * f * pitch * tt) * env_exp(d, tau) for f, a, tau in ((1760, 1, .1), (2637, .6, .07), (4186, .35, .05)))
    f0 = 52 * pitch + 70 * np.exp(-tt * 40); drop = np.sin(2 * np.pi * np.cumsum(f0) / SR) * env_exp(d, .14)
    return norm(.55 * tr / (np.abs(tr).max() + 1e-9) + .35 * norm(ring) + .9 * drop) * v

# ---- 음악: 16분 오스티나토(E 프리지안) + 박자마다 우드블록 시계 + 베이스 ----
BEAT = .4; S16 = BEAT / 4
OST = [64, 65, 64, 71, 64, 65, 67, 65]     # E F E B E F G F (♭9)
ROOT = [40, 40, 41, 40, 43, 41, 40, 38]
nb = int(DUR / BEAT) + 1
for b in range(nb):
    t = b * BEAT; bar = b // 4; ph = b % 4
    for q in range(4):
        n = OST[(b * 4 + q) % len(OST)] + (12 if (b // 8) % 2 else 0)
        add(music, harpsi(mid(n)), t + q * S16, .17 if q else .22, .2)
    add(music, woodblock(), t, .35, 0)
    if ph in (0, 2): add(music, contrabass(mid(ROOT[bar % len(ROOT)]), .4), t, .55, 0)
# 하드 사일런스: RIGHT 공개 직전과 CTA 직전 .3초 음악 게이트(우드블록 시계 하나만 남음)
wipes = [e['t'] for e in EV if e['type'] == 'wipe']
sil = []
if len(wipes) >= 2: sil.append(wipes[1])
if len(wipes) >= 3: sil.append(wipes[-1])
gate = np.ones(N, np.float32)
for t in sil: gate[max(0, int((t - .3) * SR)):int(t * SR)] = 0
music *= gate[:, None]
for t in sil: add(music, woodblock(), t - .3, .5, 0)
add(music, sfx.rumble(1.2, .5)[:int(1.2 * SR)] if hasattr(sfx, 'rumble') else np.zeros(10), max(0, DUR - 1.8), .18, 0)

# ---- 효과음: 컷마다 카드 히트(음정 상승) ----
hits = 0
for e in EV:
    t, ty = e['t'], e['type']
    if ty == 'pop': add(fx, card_hit(1.0 + .03 * min(hits, 20), .6), t, .55, 0); hits += 1
    elif ty == 'slam': add(fx, card_hit(.8, 1), t, .9, 0); add(fx, sfx.thump(1, 52), t, .9)
    elif ty == 'wipe': add(fx, card_hit(1.0 + .04 * min(hits, 20), .8), t, .7, 0); hits += 1
    elif ty == 'write': add(fx, sfx.click(1.0 + .02 * min(e.get('n', 8), 10), .6), t, .35, 0)
    elif ty == 'mark':
        k = e['kind']
        if k == 'cross': add(fx, sfx.thump(1, 60), t, .8)
        elif k == 'check': add(fx, sfx.ding(1), t, .45, 0)
        elif k == 'strike': add(fx, sfx.clack(.9, 1), t, .7, 0); add(fx, sfx.thump(1, 52), t, .6)

# ---- 음성 + 덕킹 ----
vm = np.zeros(N, np.float32)
for e in EV:
    if e['type'] != 'voice': continue
    w, sr = sf.read(f"{HERE}/out/voice/{e['id']}.wav"); w = w if w.ndim == 1 else w.mean(1)
    w = soxr.resample(w.astype(np.float32), sr, SR); w = hp(compress(w, .12, 3.0), 80)
    s = int(e['t'] * SR)
    if s + len(w) > N: w = w[:N - s]
    vox[s:s + len(w), :] += w[:, None]; vm[s:s + len(w)] += np.abs(w)
env = uniform_filter1d(vm, int(.25 * SR)); duck = 1 - .6 * np.clip(env / .05, 0, 1)
duck = uniform_filter1d(duck, int(.15 * SR)).astype(np.float32)
music *= duck[:, None]; fx *= (1 - .3 * np.clip(env / .05, 0, 1))[:, None].astype(np.float32)
act = vm > .01
rms = lambda x: np.sqrt(np.mean(x[act] ** 2) + 1e-12) if act.any() else 1.0
vr = rms(vox.mean(1)); mr = rms(music.mean(1)) + 1e-9
gm = vr / mr / (10 ** (11 / 20)); music *= gm
mixd = music + fx * .8 + vox
mixd = np.stack([limit(mixd[:, 0], .9), limit(mixd[:, 1], .9)], 1)[:int(DUR * SR)]
os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
sf.write(OUT, mixd, SR)
print('mix ok', mixd.shape, 'music gain', round(float(gm), 3))
