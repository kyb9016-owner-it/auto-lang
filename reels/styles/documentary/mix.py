"""다큐멘터리 스타일 믹스: 앰비언트 패드 + 부드러운 피아노풍 음 + 낮은 필름 프로젝터 노이즈. 전부 합성(외부 음원 0).
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
rs = np.random.default_rng(2026)

# ---- 악기 ----
def piano(f, d=1.8, v=1.0):
    """부드러운 피아노풍: 배음 몇 개 + 지수 감쇠, 짧은 해머 노이즈(저역 통과로 둥글게)"""
    tt = t_(d); x = np.zeros_like(tt)
    for k, (a, tau) in enumerate([(1, .9), (.5, .55), (.28, .35), (.14, .22), (.07, .14)], 1):
        x += a * np.sin(2 * np.pi * f * k * (1 + .0004 * k * k) * tt) * np.exp(-tt / (tau * (d / 1.8) + .05))
    x *= np.minimum(1, tt / .006)
    h = lp(noise(.06), 1500) * env_exp(.06, .012) * .25
    x[:len(h)] += h
    return norm(lp(x, 4200)) * v
def pad(freqs, d, v=1.0):
    """느린 어택·릴리스의 따뜻한 패드(사인+삼각 약간, 미세 디튠)"""
    tt = t_(d); x = np.zeros_like(tt)
    for f in freqs:
        for det in (-.003, 0, .003):
            ph = 2 * np.pi * f * (1 + det) * tt
            x += np.sin(ph) + .25 * np.sin(2 * ph) + .08 * np.sin(3 * ph)
    x = lp(x, 1100, 2) / (len(freqs) * 3)
    e = np.minimum(1, tt / (d * .38)) * np.minimum(1, (d - tt) / (d * .38))
    return x * e ** 1.5 * v
def tick(v=1.0):
    d = .018; return norm(hp(noise(d), 2500) * env_exp(d, .004)) * v
def soft_thump(v=1.0, f=62):
    d = .5; tt = t_(d); return norm(np.sin(2 * np.pi * f * tt * (1 - .1 * tt)) * env_exp(d, .16)) * v

# ---- 음악: 4초마다 코드가 바뀌는 앰비언트 패드 + 듬성한 피아노 음 (Am9 - Fmaj7 - C - G) ----
chords = [(45, [57, 60, 64, 67]), (41, [53, 57, 60, 64]), (48, [55, 60, 64, 67]), (43, [55, 59, 62, 66])]
BAR = 4.0
for b in range(int(DUR / BAR) + 1):
    t = b * BAR; root, ch = chords[b % 4]
    add(music, pad([mid(root)] + [mid(x) for x in ch], BAR + 2.4), t - .6, .55, -.1)
    add(music, pad([mid(root - 12)], BAR + 2.4, 1), t - .6, .35, .1)
    # 피아노: 한 마디에 3~4음, 느리고 부드럽게
    for j, off in enumerate([0.5, 1.5, 2.25, 3.0]):
        if j == 3 and rs.random() < .5: continue
        n = ch[(b * 3 + j * 2) % len(ch)] + 12 * (1 if j % 2 else 0)
        add(music, piano(mid(n), 2.0), t + off, .22 if j else .3, rs.uniform(-.3, .3))
add(music, piano(mid(57), 3.5), 0.05, .35, 0)      # 오프닝: 낮은 한 음
add(music, piano(mid(69), 4.0), max(0, DUR - 3.2), .3, 0)   # 엔딩: 길게 남는 음
add(music, piano(mid(76), 4.0), max(0, DUR - 3.0), .2, 0)

# ---- 효과음(조용하게) ----
for e in EV:
    t, ty = e['t'], e['type']
    if ty == 'write':
        n = int(e.get('n', 8)); cnt = max(2, min(16, n // 3))
        for k in range(cnt):                                # 자막 타자: 아주 작은 틱
            add(fx, tick(.5 + .5 * rs.random()), t + k * e['d'] / cnt, .06, 0)
    elif ty == 'pop': add(fx, piano(mid(81), 1.2, .8), t, .12, 0)
    elif ty == 'slam': pass                                   # 다큐는 쾅 하는 소리 없음
    elif ty == 'wipe':
        d = max(.3, e['d']); add(fx, lp(noise(d), 1500) * np.hanning(int(d * SR)) * .5, t, .22, 0)
    elif ty == 'mark':
        k = e['kind']
        if k == 'cross': add(fx, soft_thump(1, 58), t + .1, .5, 0); add(fx, piano(mid(52), 1.4, .8), t + .1, .14, 0)
        elif k == 'check': add(fx, piano(mid(72), 2.0, 1), t + .1, .22, 0); add(fx, piano(mid(79), 2.0, 1), t + .22, .16, 0)
        elif k == 'strike': add(fx, lp(noise(.35), 3500) * np.hanning(int(.35 * SR)) * .5, t, .25, 0)   # 펜 긋는 소리

# ---- 필름 프로젝터 노이즈(아주 낮게): 24Hz 맥동 하스 + 드문 먼지 소리 ----
tt = np.arange(N) / SR
hiss = bp(noise(N / SR), 2500, 9000) * (.55 + .45 * (np.sin(2 * np.pi * 24 * tt) > 0)) * (.8 + .2 * np.sin(2 * np.pi * .3 * tt))
rum = lp(noise(N / SR), 120) * 1.5 * (.6 + .4 * np.sin(2 * np.pi * 24 * tt))
for _ in range(int(DUR * 3)):
    s = int(rs.random() * (N - 800)); hiss[s:s + 300] += (rs.standard_normal(300) * np.exp(-np.arange(300) / 40) * (2 + 4 * rs.random())).astype(np.float32)
amb[:, 0] = amb[:, 1] = (hiss + rum).astype(np.float32)

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
ar = rms(amb.mean(1), np.ones(N, bool)) + 1e-9; amb *= vr / ar / (10 ** (32 / 20))   # 프로젝터 노이즈 = 음성 −32dB
mixd = music + fx * .8 + amb + vox
fade = np.ones(N, np.float32); nf = int(1.0 * SR); e0 = int(DUR * SR); fade[e0 - nf:e0] = np.linspace(1, 0, nf)   # 끝 1초 페이드아웃
mixd *= fade[:, None]
mixd = np.stack([limit(mixd[:, 0], .9), limit(mixd[:, 1], .9)], 1)[:int(DUR * SR)]
os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
sf.write(OUT, mixd, SR)
print('mix ok', mixd.shape, 'music gain', round(float(gm), 3))
