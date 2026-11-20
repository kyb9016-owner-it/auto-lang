"""만화 칸(manga-panels) 스타일 믹스: 애니 오프닝풍 록(왜곡 파워코드·드럼·베이스, 150BPM) + 잉크 붓·종이 효과음, 전부 합성(외부 음원 0).
사용: LIB=<lemo-opuscar 경로> LIB/.venv/bin/python mix.py <작업폴더> [출력 wav]
events.json(EV)과 out/voice/<id>.wav 를 읽는다. 어떤 데이터에도 동작(범용)."""
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
def gtr(f, d=.6, drive=5.0):
    """왜곡 파워코드(루트+5도+옥타브, 약간 디튠한 톱니파 → tanh 클리핑 → 로우패스)"""
    tt = t_(d); x = np.zeros_like(tt)
    for k in (1, 1.5, 2):
        for det in (-.004, .004): x += 2 * (((tt * f * k * (1 + det)) % 1) - .5)
    x = lp(np.tanh(x * drive / 3), 3200)
    return norm(x * np.minimum(1, tt / .004) * np.exp(-tt / (d * .45)))
def bass(f, d=.2):
    tt = t_(d); x = np.sin(2*np.pi*f*tt) + .5*np.sin(2*np.pi*2*f*tt) + .25*np.tanh(3*np.sin(2*np.pi*f*tt))
    return norm(lp(x, 1100) * np.minimum(1, tt/.004) * np.exp(-tt/(d*.55)))
def kick():
    d = .28; tt = t_(d); f = 46 + 100*np.exp(-tt*30)
    return norm(np.sin(2*np.pi*np.cumsum(f)/SR) * env_exp(d, .09))
def snare():
    d = .22; tt = t_(d)
    return norm(bp(noise(d), 1600, 7500)*env_exp(d, .07) + np.sin(2*np.pi*190*tt)*env_exp(d, .05)*.7)
def hat(v=1):
    d = .05; return norm(hp(noise(d), 7500)*env_exp(d, .011)) * v
def cymbal(d=1.2):
    return norm(hp(noise(d), 5000)*env_exp(d, .35))

# ---- 음악: 150 BPM, Am–F–C–G. 1박 코드, 8분 팜뮤트, 킥·스네어·하이햇 ----
BEAT = 60 / 150
prog = [(45, 57), (41, 53), (48, 60), (43, 55)]       # (베이스 루트, 코드 루트)
nb = int(DUR / BEAT) + 1
for b in range(nb):
    t = b * BEAT; bar = b // 4; root, ch = prog[bar % 4]; ph = b % 4
    if ph == 0: add(music, gtr(mid(ch), BEAT * 1.9), t, .55)
    if ph == 2: add(music, gtr(mid(ch + (2 if bar % 2 else 0)), BEAT * .9), t, .4)
    for h in (0, 1):
        add(music, gtr(mid(ch), .09, 7.0), t + h * BEAT / 2, .16 if h else .12)       # 팜뮤트 8분
        add(music, bass(mid(root), .2), t + h * BEAT / 2, .38)
        add(music, hat(.7 if h else 1), t + h * BEAT / 2, .22)
    if ph in (0, 2): add(music, kick(), t, .8)
    if ph in (1, 3): add(music, snare(), t, .55)
    if ph == 3 and bar % 2: add(music, snare(), t + BEAT / 2, .35)
add(music, cymbal(), 0, .25); add(music, kick(), 0, .9)
for e in EV:
    if e['type'] == 'wipe': add(music, cymbal(.8), e['t'], .12)

# ---- 효과음: 잉크 붓·종이·슬램 ----
def brush(d):
    """붓이 종이를 긁는 소리: 대역 잡음에 부드러운 오르내림"""
    return bp(noise(d), 1400, 6200) * np.hanning(int(d * SR)) * .8
for e in EV:
    t, ty = e['t'], e['type']
    if ty == 'write':
        k = max(1, int(e['d'] / .14))
        for j in range(k): add(fx, brush(.1), t + j * e['d'] / k, .32, 0)
    elif ty == 'pop': add(fx, sfx.pop(1), t, .35, 0); add(fx, sfx.click(1.3, .8), t, .3, 0)
    elif ty == 'slam': add(fx, sfx.thump(1, 52), t, 1.0); add(fx, sfx.whoosh(.25), max(0, t - .12), .35, 0); add(fx, sfx.crash(.6), t, .3, 0)
    elif ty == 'wipe':
        d = max(.2, e['d']); add(fx, sfx.whoosh(d, 1), t, .9, 0); add(fx, sfx.thump(1, 70), t, .5, 0)
    elif ty == 'mark':
        k = e['kind']
        if k == 'cross': add(fx, sfx.thump(1, 85), t + .1, .8, 0); add(fx, sfx.whoosh(.2, 1), t, .5, 0)
        elif k == 'check': add(fx, sfx.ding(1), t + .3, .45, 0); add(fx, brush(.35), t, .6, 0)
        elif k == 'strike': add(fx, sfx.whoosh(.18, 1), t, .8, 0); add(fx, sfx.thump(.8, 110), t + .1, .5, 0)

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
env = uniform_filter1d(vm, int(.25 * SR)); duck = 1 - .65 * np.clip(env / .05, 0, 1)
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
