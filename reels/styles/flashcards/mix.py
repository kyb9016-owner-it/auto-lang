"""플래시카드 스타일 믹스: 따뜻한 패드 + 부드러운 건반(펠트 피아노풍) + 조용한 종이 소리(카드 놓기·밀기·뒤집기)·부드러운 체크 클릭. 전부 합성(외부 음원 0).
사용: LIB=<lemo-opuscar 경로> LIB/.venv/bin/python mix.py <작업폴더> [출력 wav]
작업폴더에서 events.json과 out/voice/<id>.wav 를 읽는다. 어떤 데이터에도 동작(범용). slam은 무시."""
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
rs = np.random.default_rng(2027)

# ---- 악기 ----
def keys(f, d=2.0, v=1.0):
    """펠트 피아노/로즈 중간: 낮은 배음 몇 개 + 부드러운 어택 + 지수 감쇠"""
    tt = t_(d); x = np.zeros_like(tt)
    for k, (a, tau) in enumerate([(1, 1.0), (.32, .6), (.12, .35), (.05, .2)], 1):
        x += a * np.sin(2 * np.pi * f * k * tt) * np.exp(-tt / (tau * (d / 2.0) + .05))
    x *= np.minimum(1, tt / .012)
    return norm(lp(x, 2800)) * v
def pad(freqs, d, v=1.0):
    tt = t_(d); x = np.zeros_like(tt)
    for f in freqs:
        for det in (-.003, 0, .003):
            ph = 2 * np.pi * f * (1 + det) * tt
            x += np.sin(ph) + .2 * np.sin(2 * ph)
    x = lp(x, 900, 2) / (len(freqs) * 3)
    e = np.minimum(1, tt / (d * .4)) * np.minimum(1, (d - tt) / (d * .4))
    return x * e ** 1.5 * v
def paper(d=.28, lo=900, hi=4200, v=1.0):
    """종이 스치는 소리: 대역 노이즈 + 부드러운 윤곽"""
    n = int(d * SR); w = np.hanning(n) ** 1.5
    return norm(bp(noise(d), lo, hi) * w) * v
def card_down(v=1.0):
    """카드를 책상에 내려놓는 소리: 짧은 둔탁함 + 종이 소리"""
    tt = t_(.16); th = np.sin(2 * np.pi * 150 * tt * (1 - .5 * tt)) * env_exp(.16, .035)
    return norm(th * .8 + lp(noise(.16), 1800) * env_exp(.16, .02) * .7) * v
def click(v=1.0):
    d = .05; tt = t_(d); return norm((np.sin(2 * np.pi * 1900 * tt) * .5 + hp(noise(d), 2500) * .5) * env_exp(d, .007)) * v
def swish(d=.4, v=1.0):
    """카드 뒤집기: 위로 올라가는 대역 + 내려놓는 끝소리"""
    n = int(d * SR); x = bp(noise(d), 1500, 6500) * np.sin(np.pi * np.linspace(0, 1, n)) ** 2
    return norm(x) * v

# ---- 음악: 4초마다 코드가 바뀌는 따뜻한 패드 + 듬성한 건반 (Cmaj7 - Am7 - Fmaj7 - G6) ----
chords = [(48, [55, 59, 62, 64]), (45, [52, 57, 60, 64]), (41, [53, 57, 60, 64]), (43, [55, 59, 62, 64])]
BAR = 4.0
for b in range(int(DUR / BAR) + 1):
    t = b * BAR; root, ch = chords[b % 4]
    add(music, pad([mid(root)] + [mid(x) for x in ch], BAR + 2.4), t - .6, .55, -.1)
    add(music, pad([mid(root - 12)], BAR + 2.4, 1), t - .6, .3, .1)
    for j, off in enumerate([0.5, 1.5, 2.25, 3.0]):
        if j == 3 and rs.random() < .5: continue
        n = ch[(b * 3 + j * 2) % len(ch)] + 12 * (1 if j % 2 else 0)
        add(music, keys(mid(n), 2.2), t + off, .2 if j else .28, rs.uniform(-.3, .3))
add(music, keys(mid(60), 3.5), 0.05, .3, 0)
add(music, keys(mid(72), 4.0), max(0, DUR - 3.2), .26, 0)
add(music, keys(mid(79), 4.0), max(0, DUR - 3.0), .18, 0)

# ---- 효과음(모두 조용하게) ----
flip_done = False
for e in EV:
    t, ty = e['t'], e['type']
    if ty == 'write':
        d = min(.45, e['d']); add(fx, paper(d, 2500, 7000, .5), t, .035, rs.uniform(-.2, .2))   # 연필 스치는 소리(아주 작게)
    elif ty == 'pop': add(fx, card_down(1), t, .2, 0)
    elif ty == 'slam': pass
    elif ty == 'wipe':
        d = e['d']
        if d <= 0: continue
        if not flip_done:                                  # 첫 번째 와이프 = WRONG→RIGHT 카드 뒤집기
            add(fx, swish(.4, 1), t, .28, 0); add(fx, card_down(1), t + .38, .16, 0); flip_done = True
        else:                                              # 카드가 옆으로 밀려 나가는 소리
            add(fx, paper(.42, 700, 3800, 1), t, .22, -.2); add(fx, card_down(.8), t + .3, .12, .1)
    elif ty == 'mark':
        k = e['kind']
        if k == 'cross': add(fx, card_down(1), t + .12, .22, 0); add(fx, keys(mid(52), 1.4, .8), t + .12, .12, 0)
        elif k == 'check': add(fx, click(1), t + .22, .2, 0); add(fx, keys(mid(79), 1.8, 1), t + .26, .14, 0); add(fx, keys(mid(84), 1.8, 1), t + .36, .1, 0)
        elif k == 'strike': add(fx, paper(.3, 1500, 5000, 1), t, .12, 0)   # 연필 취소선

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
fr = rms(fx.mean(1), np.ones(N, bool)) + 1e-9
fx *= min(1.0, (vr / fr) / (10 ** (16 / 20)) * 4) if fr > 0 else 1   # 효과음이 음성 위로 튀지 않게 상한
mixd = music + fx * .9 + vox
fade = np.ones(N, np.float32); nf = int(1.0 * SR); e0 = int(DUR * SR); fade[e0 - nf:e0] = np.linspace(1, 0, nf)
mixd *= fade[:, None]
mixd = np.stack([limit(mixd[:, 0], .9), limit(mixd[:, 1], .9)], 1)[:int(DUR * SR)]
os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
sf.write(OUT, mixd, SR)
print('mix ok', mixd.shape, 'music gain', round(float(gm), 3))
