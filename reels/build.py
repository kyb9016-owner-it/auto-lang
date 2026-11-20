#!/opt/homebrew/bin/python3
"""LangCard 릴스 빌드: 구독 큐 JSON -> final.mp4 (lemo-opuscar 렌더러 재사용)
사용: python3 reels/build.py <queue.json> --style chalkboard|random --out <final.mp4> [--pace strict|fast] [--keep-work]
표준 라이브러리만 사용. LIB의 .venv/node는 하위 프로세스로 호출."""
import argparse, json, os, random, shutil, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
LIB = os.environ.get('LEMO_LIB', '/Users/kong/projects/lemo-opuscar')
PY = os.path.join(LIB, '.venv/bin/python')
FONTS = {'ko': 'NotoSansKR-Bold.ttf', 'ja': 'NotoSansJP-Bold.ttf', 'zh': 'NotoSansSC-Bold.ttf'}
KO_VOICE = 'ko-KR-SunHiNeural'
TG = {'en': ('en-US-JennyNeural', 'en-US-GuyNeural'), 'zh': ('zh-CN-XiaoxiaoNeural', 'zh-CN-YunxiNeural'), 'ja': ('ja-JP-NanamiNeural', 'ja-JP-KeitaNeural')}


def die(msg):
    print(f'[build] 실패: {msg}', file=sys.stderr); sys.exit(1)


def run(step, cmd, cwd=None, env=None, timeout=1800):
    t = time.time(); print(f'[build] {step} ...', flush=True)
    e = dict(os.environ); e.update(env or {})
    r = subprocess.run(cmd, cwd=cwd, env=e, timeout=timeout, capture_output=True, text=True)
    if r.returncode != 0:
        die(f'{step} (exit {r.returncode})\n$ {" ".join(cmd)}\n{r.stdout[-1500:]}\n{r.stderr[-2500:]}')
    print(f'[build] {step} 완료 ({time.time()-t:.1f}s)', flush=True)
    return r.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('queue'); ap.add_argument('--style', default='chalkboard'); ap.add_argument('--out', required=True)
    ap.add_argument('--pace', default='fast', choices=['strict', 'fast']); ap.add_argument('--keep-work', action='store_true')
    ap.add_argument('--workers', type=int, default=3)
    a = ap.parse_args()
    if not os.path.isdir(LIB) or not os.path.exists(PY): die(f'lemo-opuscar를 찾을 수 없음: {LIB} (LEMO_LIB 환경변수로 지정)')
    q = json.load(open(a.queue, encoding='utf-8'))
    lang = q.get('lang')
    if lang not in TG: die(f'lang은 en|zh|ja 이어야 함: {lang!r}')
    styles_dir = os.path.join(HERE, 'styles')
    avail = sorted(d for d in os.listdir(styles_dir) if os.path.exists(os.path.join(styles_dir, d, 'index.html')))
    style = random.choice(avail) if a.style == 'random' else a.style
    sdir = os.path.join(styles_dir, style)
    if style not in avail: die(f'스타일 없음: {style} (있는 것: {avail})')
    out = os.path.abspath(a.out); os.makedirs(os.path.dirname(out), exist_ok=True)
    t_all = time.time()

    work = tempfile.mkdtemp(prefix=f'reel_{style}_'); print(f'[build] style={style} lang={lang} work={work}')
    try:
        # 1) 작업 폴더 구성
        shutil.copy(os.path.join(sdir, 'index.html'), work)
        shutil.copytree(os.path.join(HERE, 'common'), os.path.join(work, 'common'))
        fd = os.path.join(work, 'fonts'); os.makedirs(fd)
        for n in ('fonts.css',) + tuple(f'f{i}.woff2' for i in range(8)):   # Fredoka 등(OFL) — LIB core/fonts
            shutil.copy(os.path.join(LIB, 'core/fonts', n), fd)
        for k in {'ko'} | ({lang} & set(FONTS)):
            src = os.path.join(PROJ, 'fonts', FONTS[k])
            if not os.path.exists(src): die(f'폰트 없음: {src}')
            shutil.copy(src, fd)
        for k in FONTS:   # 쓰지 않는 CJK 폰트는 빈 파일 대신 선언만 되어 있으므로 404 경고를 막으려 심볼릭 링크
            dst = os.path.join(fd, FONTS[k])
            if not os.path.exists(dst): os.symlink(os.path.join(PROJ, 'fonts', FONTS[k]), dst)
        data = dict(q); data['opts'] = {'pace': a.pace}
        json.dump(data, open(os.path.join(work, 'data.json'), 'w', encoding='utf-8'), ensure_ascii=False)

        # 2) 내레이션 줄(공통 timeline.js 규약 재사용: node로 narration() 호출)
        js = ("require(%s);const LC=globalThis.LC;const d=JSON.parse(require('fs').readFileSync('data.json','utf8'));"
              "process.stdout.write(JSON.stringify(LC.narration(LC.normalize(d))))") % json.dumps(os.path.join(work, 'common/timeline.js'))
        nar = json.loads(run('내레이션 줄 구성', ['node', '-e', js], cwd=work))
        va, vb = TG[lang]
        lines = []
        for n in nar:
            v = {'ko': KO_VOICE, 'tg': va, 'tgA': va, 'tgB': vb}[n['who']]
            L = {'id': n['id'], 'text': n['text'], 'voice': v}
            if n['who'] == 'ko': L['rate'] = '+5%'
            lines.append(L)
        json.dump(lines, open(os.path.join(work, 'lines.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        os.makedirs(os.path.join(work, 'out'), exist_ok=True)

        # 3) TTS (edge-tts)
        run('TTS(edge-tts)', [PY, 'core/tts/tts_zh.py', os.path.join(work, 'lines.json'), os.path.join(work, 'out/voice'), '--voice', KO_VOICE], cwd=LIB)
        shutil.copy(os.path.join(work, 'out/voice/dur.json'), os.path.join(work, 'dur.json'))

        # 4) 이벤트 → 렌더 → 믹스 → mux
        run('이벤트 내보내기', ['node', 'core/render/events.mjs', work, '--size', '1080x1920'], cwd=LIB)
        run('프레임 렌더', ['node', 'core/render/video.mjs', work, '--fps', '24', '--size', '1080x1920', '--workers', str(a.workers), '--out', os.path.join(work, 'out/video.mp4')],
            cwd=LIB, env={'RENDER_SLOTS': '2'}, timeout=3600)
        run('믹스', [PY, os.path.join(sdir, 'mix.py'), work, os.path.join(work, 'out/mix.wav')], cwd=LIB, env={'LIB': LIB})
        run('mux/마스터링', ['sh', 'core/render/mux.sh', os.path.join(work, 'out/video.mp4'), os.path.join(work, 'out/mix.wav'), out, '24', '0'],
            cwd=LIB, env={'LEMO_COLOR': 'bt709', 'RENDER_SLOTS': '2'})
        if not os.path.exists(out): die('final.mp4가 만들어지지 않음')
        print(f'[build] 완료: {out} (총 {time.time()-t_all:.0f}s)')
    finally:
        if a.keep_work: print(f'[build] 작업 폴더 보존: {work}')
        else: shutil.rmtree(work, ignore_errors=True)


if __name__ == '__main__':
    main()
