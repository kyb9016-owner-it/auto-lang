"""팝아트 스타일 믹스: 음악·효과음은 전부 합성(외부 음원 0), 음성 wav 배치.
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

# ---- 악기: 60년대 엑조티카(비브라폰·마림바·콩가·셰이커·워킹 베이스) ----
def vibes(f, d=.9, v=1):
    tt = t_(d); trem = 1 + .25 * np.sin(2*np.pi*5.5*tt)
    x = (np.sin(2*np.pi*f*tt)*env_exp(d, .55) + .3*np.sin(2*np.pi*f*4*tt)*env_exp(d, .12)) * trem
    return norm(x) * v
def marimba(f, d=.45, v=1):
    tt = t_(d); x = (np.sin(2*np.pi*f*tt)*env_exp(d, .2) + .3*np.sin(2*np.pi*f*4*tt)*env_exp(d, .04))
    return norm(x) * v
def bass(f, d=.4, v=1):
    tt = t_(d); x = np.sin(2*np.pi*f*tt) + .5*np.sin(2*np.pi*2*f*tt) + .15*np.sin(2*np.pi*3*f*tt)
    e = np.minimum(1, tt/.008) * np.exp(-tt/(d*.5)); return norm(lp(x, 800) * e) * v
def conga(hi=True, v=1):
    d = .22; tt = t_(d); f0 = 330 if hi else 220
    f = f0 * (1 + .35*np.exp(-tt*40)); x = np.sin(2*np.pi*np.cumsum(f)/SR) * env_exp(d, .07)
    return norm(x + .3*bp(noise(d), 800, 3000)*env_exp(d, .01)) * v
def shaker(v=1):
    d = .07; return norm(hp(noise(d), 5500) * np.hanning(int(d*SR)*2)[:int(round(d*SR))]) * v
def clap(v=1):
    d = .12; x = bp(noise(d), 900, 3500) * env_exp(d, .025); return norm(x) * v
def stab(freqs, d=.28, v=1):
    tt = t_(d); x = sum(np.sign(np.sin(2*np.pi*f*tt)) for f in freqs) / len(freqs)
    return norm(lp(x, 2200) * env_exp(d, .1)) * v

# ---- 음악: 112bpm 근처(박자 .5초), 장면 전환 구간은 베이스만 남기고 와이프에 위쉬 ----
BEAT = .5
prog = [(36, [60, 64, 67, 71]), (41, [60, 65, 69, 72]), (43, [62, 65, 67, 71]), (36, [60, 64, 67, 69])]   # Cmaj7 F6 G7 C6
melody = [0, 2, 3, 2, 1, 3, 2, 0]
wipes = [(e['t'], max(e.get('d', .4), .3)) for e in EV if e['type'] == 'wipe']
for b in range(int(DUR / BEAT)):
    t = b * BEAT; bar = b // 4; root, ch = prog[bar % 4]; ph = b % 4
    walk = [root, root + 7, root + 4, root + 7][ph]
    add(music, bass(mid(walk), .4), t, .5)
    if ph in (1, 3): add(music, conga(True), t, .38); add(music, conga(False), t + .25, .22)
    add(music, shaker(), t, .22); add(music, shaker(), t + .25, .12)
    if ph == 2: add(music, clap(), t, .3)
    if b % 2 == 0: add(music, marimba(mid(ch[melody[(b//2) % 8] % 4] + 24), .45), t + .25, .26)
    if ph == 0: add(music, vibes(mid(ch[1] + 12), 1.8), t, .2)
    if t < 2.0 and ph in (0, 2): add(music, sfx.thump(1, 60), t, .5)   # 훅 구간 킥
for t, d in wipes:
    add(music, vibes(mid(84), 1.2), t + d * .5, .14, .2)
add(music, vibes(mid(79), 2.5), max(0, DUR - 2.5), .16, .3)

# ---- 효과음: 인쇄소 폴리 ----
def squeegee(d, n):
    """스퀴지 긁는 소리: 대역 잡음 + 끝의 가벼운 종이 소리"""
    L = int(d * SR); x = bp(noise(d), 1200, 5200)[:L] * (np.hanning(L) ** .6) * min(1, n / 8 + .4)
    return x.astype(np.float32)
for e in EV:
    t, ty = e['t'], e['type']
    if ty == 'write': add(fx, squeegee(max(.15, e['d'] * .8), e.get('n', 8)), t, .32, 0); add(fx, sfx.click(1.0), t + .02, .18)
    elif ty == 'pop': add(fx, sfx.thump(1, 80), t, .45); add(fx, bp(noise(.08), 1500, 5000) * env_exp(.08, .02), t, .25, 0)
    elif ty == 'slam': add(fx, sfx.thump(1, 55), t, 1.0); add(fx, sfx.whoosh(.25), max(0, t - .12), .35, 0); add(fx, sfx.crash(.6), t, .25, 0); add(fx, clap(), t, .5)
    elif ty == 'wipe': dd = max(.3, e['d']); add(fx, sfx.whoosh(dd + .1), t, .6, 0)
    elif ty == 'mark':
        k = e['kind']
        if k == 'cross': add(fx, sfx.thump(1, 90), t, .7, 0); add(fx, sfx.clack(.8), t + .02, .4, 0)
        elif k == 'check': add(fx, sfx.ding(1), t + .05, .5, 0); add(fx, sfx.thump(1, 110), t, .4, 0)
        elif k == 'strike': add(fx, squeegee(.35, 12), t, .6, 0); add(fx, sfx.thump(1, 65), t + .25, .5, 0)

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
