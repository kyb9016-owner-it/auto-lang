"""칠판 스타일 믹스: 음악·효과음은 전부 합성(외부 음원 0), 음성 wav 배치.
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

# ---- 악기 ----
def marimba(f, d=.6, v=1):
    tt = t_(d); x = (np.sin(2*np.pi*f*tt)*env_exp(d, .25) + .35*np.sin(2*np.pi*f*4*tt)*env_exp(d, .04) + .12*np.sin(2*np.pi*f*9.2*tt)*env_exp(d, .015))
    return norm(x) * v
def bass(f, d=.45, v=1):
    tt = t_(d); x = np.sin(2*np.pi*f*tt) + .45*np.sin(2*np.pi*2*f*tt) + .2*np.sin(2*np.pi*3*f*tt)
    e = np.minimum(1, tt/.01) * np.exp(-tt/(d*.6)); return norm(lp(x, 900) * e) * v
def bell(f, d=1.4, v=1):
    tt = t_(d); x = sum(a*np.sin(2*np.pi*f*r*tt)*env_exp(d, tau) for r, a, tau in [(1, 1, .7), (2.76, .35, .3), (5.4, .2, .12)])
    return norm(x) * v
def pad(freqs, d, v=1):
    tt = t_(d); x = np.zeros_like(tt)
    for f in freqs:
        for det in (-.004, 0, .004): x += 2 * (((tt*f*(1+det)) % 1) - .5)
    x = lp(x, 1400, 2) / (len(freqs)*3)
    return x * np.minimum(1, tt/(d*.3)) * np.minimum(1, (d-tt)/(d*.3)) * v
def kick(v=1):
    d = .3; tt = t_(d); f = 48 + 90*np.exp(-tt*28)
    return norm(np.sin(2*np.pi*np.cumsum(f)/SR) * env_exp(d, .1)) * v
def rim(v=1):
    d = .08; tt = t_(d)
    return norm(bp(noise(d), 1500, 5000)*env_exp(d, .006) + np.sin(2*np.pi*1700*tt)*env_exp(d, .01)*.6) * v

# ---- 음악: 부드러운 마림바 아르페지오 + 베이스(박자 0.5초, 장면 전환 구간은 비움) ----
BEAT = .5
prog = [(45, [57, 60, 64]), (41, [53, 57, 60]), (48, [55, 60, 64]), (43, [55, 59, 62])]
wipes = [(e['t'], e.get('d', .4)) for e in EV if e['type'] == 'wipe']
for b in range(int(DUR / BEAT)):
    t = b * BEAT; bar = b // 4; root, ch = prog[bar % 4]; ph = b % 4
    add(music, marimba(mid(ch[(b*3) % 3] + 24), .5), t + .25, .2, .25)
    if t < 2.0:                       # 훅 구간: 킥으로 박자 강조
        if ph in (0, 2): add(music, kick(.9), t, .6)
        if ph in (1, 3): add(music, rim(), t, .3)
    if ph in (0, 2): add(music, bass(mid(root), .4), t, .45)
    if ph == 0: add(music, pad([mid(x) for x in ch], 2.0), t, .1)
for t, d in wipes:
    add(music, bell(mid(81), 1.4), t + d, .18, .2)
add(music, bell(mid(76), 2.5), max(0, DUR - 2.5), .15, .3)

# ---- 효과음 ----
def chalk(d, n):
    """분필 긁는 소리: 대역 잡음 알갱이 열. 길이 d(초), 글자 수 n으로 세기 조절"""
    L = int(d * SR); x = np.zeros(L, np.float32); g = int(.022 * SR); r = np.random.default_rng(int(n * 31 + d * 1000))
    for s in range(0, max(1, L - g), int(.032 * SR)):
        a = (.4 + .6 * r.random()) * min(1, n / 8 + .35)
        x[s:s+g] += (bp(noise(g / SR), 2200, 7200) * np.hanning(g) * a).astype(np.float32)
    return x
for e in EV:
    t, ty = e['t'], e['type']
    if ty == 'write': add(fx, chalk(e['d'], e.get('n', 8)), t, .55, 0)
    elif ty == 'pop': add(fx, sfx.pop(1), t, .5, 0)
    elif ty == 'slam': add(fx, sfx.thump(1, 55), t, 1.0); add(fx, sfx.whoosh(.25), max(0, t - .12), .35, 0); add(fx, sfx.crash(.6), t, .25, 0)
    elif ty == 'wipe': add(fx, lp(noise(max(.2, e['d'])), 1800) * np.hanning(int(max(.2, e['d']) * SR)) * .8, t, .7, 0)
    elif ty == 'mark':
        k = e['kind']
        if k == 'cross': add(fx, sfx.thump(1, 90), t + .45, .6, 0); add(fx, chalk(.5, 10), t, .6, 0)
        elif k == 'check': add(fx, sfx.ding(1), t + .35, .5, 0); add(fx, chalk(.45, 10), t, .6, 0)
        elif k == 'strike': add(fx, chalk(.4, 12), t, .7, 0)

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
mixd = np.stack([limit(mixd[:, 0], .9), limit(mixd[:, 1], .9)], 1)[:int(DUR * SR)]
os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
sf.write(OUT, mixd, SR)
print('mix ok', mixd.shape, 'music gain', round(float(gm), 3))
