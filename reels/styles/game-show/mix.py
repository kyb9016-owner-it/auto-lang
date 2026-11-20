"""게임쇼 스타일 믹스: 128bpm 팝 루프(킥·스네어·하이햇·슬랩 베이스·마림바·브라스 스탭) + 장난감 효과음, 전부 합성(외부 음원 0).
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
BPM = 128; BEAT = 60 / BPM            # index.html의 BPM과 같은 값(그림과 소리가 같은 격자)

# ---- 악기 ----
def kick(v=1):
    d = .28; tt = t_(d); f = 46 + 110 * np.exp(-tt * 30)
    return norm(np.tanh(1.6 * np.sin(2 * np.pi * np.cumsum(f) / SR)) * env_exp(d, .09)) * v
def snare(v=1):
    d = .2; tt = t_(d)
    return norm(bp(noise(d), 1400, 7000) * env_exp(d, .05) + np.sin(2 * np.pi * 190 * tt) * env_exp(d, .035) * .6) * v
def clap(v=1):
    out = np.zeros(int(.22 * SR))
    for k, s in enumerate((0, .011, .023)):
        g = bp(noise(.05), 900, 3200) * env_exp(.05, .012); i = int(s * SR); out[i:i + len(g)] += g[:len(out) - i]
    out += bp(noise(.22), 900, 3200) * env_exp(.22, .06) * .7
    return norm(out) * v
def hat(v=1, d=.05):
    return norm(hp(noise(d), 7500) * env_exp(d, d / 4)) * v
def bass(f, d=.2, v=1):                # 슬랩 베이스: 톱니 + 빠른 필터 닫힘
    tt = t_(d); saw = 2 * ((tt * f) % 1) - 1; x = lp(saw, 700) * np.exp(-tt / (d * .5))
    return norm(x + .5 * np.sin(2 * np.pi * f * tt) * np.exp(-tt / (d * .8))) * v
def marimba(f, d=.35, v=1):
    tt = t_(d)
    return norm(np.sin(2 * np.pi * f * tt) * env_exp(d, .18) + .35 * np.sin(2 * np.pi * f * 4 * tt) * env_exp(d, .035)) * v
def brass(freqs, d=.38, v=1):          # 톱니 디튠 브라스 스탭(필터가 닫힌다)
    tt = t_(d); x = np.zeros_like(tt)
    for f in freqs:
        for det in (-.006, 0, .006): x += 2 * (((tt * f * (1 + det)) % 1) - .5)
    x = lp(x, 2600, 2) / (len(freqs) * 3)
    e = np.minimum(1, tt / .015) * np.exp(-tt / (d * .55)) * np.minimum(1, (d - tt) / .05)
    return norm(x * e) * v
def pip(f, d=.12, v=1):
    tt = t_(d); return norm(np.sign(np.sin(2 * np.pi * f * tt)) * .6 * env_exp(d, d / 3) + np.sin(2 * np.pi * f * tt) * env_exp(d, d / 3)) * v
def buzzer(v=1):                        # 오답 부저
    d = .38; tt = t_(d); x = np.sign(np.sin(2 * np.pi * 150 * tt)) + .6 * np.sign(np.sin(2 * np.pi * 158 * tt))
    return norm(lp(x, 2200) * np.minimum(1, tt / .005) * np.minimum(1, (d - tt) / .04)) * v
def riser(d=.35, v=1):
    n = noise(d); tt = t_(d); out = np.zeros_like(n)
    for i in range(0, len(n), 480):
        hi = min(len(n), i + 480); f = 500 + 5500 * (i / len(n)) ** 2
        out[i:hi] = bp(n[max(0, i - 2000):hi], f * .7, f * 1.3)[-(hi - i):]
    return norm(out * (tt / d) ** 1.5) * v

# ---- 음악: 한 마디 코드 루프(C - G - Am - F), 4분 킥·2/4박 스네어+클랩·8분 하이햇·베이스·마림바 아르페지오 ----
prog = [(48, [60, 64, 67]), (43, [59, 62, 67]), (45, [60, 64, 69]), (41, [60, 65, 69])]
nb = int(DUR / BEAT) + 1
for b in range(nb):
    t = b * BEAT; bar = b // 4; ph = b % 4; root, ch = prog[bar % 4]
    add(music, kick(1.0), t, .55)
    if ph in (1, 3): add(music, snare(1), t, .32); add(music, clap(1), t, .22)
    add(music, hat(1), t + BEAT / 2, .14); 
    if ph == 0 or ph == 2: add(music, hat(1, .11), t, .08)
    for k, off in enumerate((0, .75, 1.5, 2.25)):                       # 슬랩 베이스(싱코페이션)
        if b % 2 == 0 or k < 2: add(music, bass(mid(root + (12 if k == 3 else 0)), .2), t + off * BEAT / 2 * 2 / 2, .32)
    for k in range(2):                                                    # 마림바 8분 아르페지오
        add(music, marimba(mid(ch[(b * 2 + k) % 3] + 12), .32), t + k * BEAT / 2, .2)
    if ph == 0: add(music, brass([mid(x) for x in ch], .3), t, .12)      # 마디 첫 박 스탭

# ---- 효과음(그림의 이벤트에서 생성) ----
for e in EV:
    t, ty = e['t'], e['type']
    if ty == 'write':                       # 타자기 클릭: 몇 글자마다 하나
        n = max(1, e.get('n', 8)); clicks = min(8, max(2, n // 3))
        for k in range(clicks):
            add(fx, sfx.click(1.0 + .08 * (k % 4), .6), t + e['d'] * k / clicks, .16, 0)
    elif ty == 'pop': add(fx, sfx.pop(1), t, .5, 0)
    elif ty == 'slam':
        add(fx, sfx.thump(1, 52), t, 1.0); add(fx, sfx.crash(.6), t, .3, 0)
        add(fx, brass([mid(60), mid(64), mid(67), mid(72)], .5), t, .5)
    elif ty == 'wipe':                      # 하드 컷 징글: 스네어 롤 + 라이저 → 크래시 + 브라스 스탭(컷 순간)
        for k, o in enumerate((-.24, -.16, -.08)): add(fx, snare(1), t + o, .2 + .05 * k, 0)
        add(fx, riser(.3), t - .3, .3, 0); add(fx, sfx.crash(.5), t, .28, 0)
        add(fx, brass([mid(67), mid(71), mid(74)], .3), t, .4)
    elif ty == 'mark':
        k = e['kind']
        if k == 'cross': add(fx, buzzer(1), t + .3, .55, 0); add(fx, sfx.thump(1, 90), t + .45, .6, 0)
        elif k == 'check': add(fx, pip(mid(84), .14), t + .05, .5, 0); add(fx, pip(mid(91), .3), t + .17, .5, 0); add(fx, sfx.ding(1), t + .2, .35, 0)
        elif k == 'strike': add(fx, snare(1), t, .55, 0); add(fx, sfx.whoosh(.2), t - .08, .35, 0)

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
