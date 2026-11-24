#!/usr/bin/env python3
"""perf.py : fast, deterministic field-performance benchmark (headless melonDS, emulated cycle counts, no wall clock).

  python3 redux/tests/perf/perf.py                       # all spots, EN release ROM of this worktree, JIT + interpreter
  python3 redux/tests/perf/perf.py --save-baseline main  # ... and keep the results as baseline "main"
  python3 redux/tests/perf/perf.py --baseline main       # ... and print the difference to baseline "main"
  python3 redux/tests/perf/perf.py --spots r20_bridge,castelia --top 30 --rom X.nds --map X_qol_map.json

Spots: savestates at heavy places (Route 20's bridges incl. autumn, its grass, Virbank, Aspertia, Floccesy, Route 19,
Castelia), each replaying a short key script (FRAMES frames: standing, running, walking). The states are made once per
ROM (build/perfstates/<ROM SHA-1>/, ~20 s: the battery save $REDUX_PERF_SAV is continued and warped there, see
mlperf.teleport) and reused until the ROM changes. Each spot runs twice, in parallel with the others:
  J  melonDS with its JIT (what Watermelon DS / melonDS Android users run): ARM9 busy % per frame (halted / idle-loop
     cycles vs all), frames over budget (a main-loop iteration that took 2+ VBlanks), fps60 counters (midpoint
     pictures drawn / left out, fallback updates), new pictures per second while the player moves, polygons /
     vertices of the swapped lists.
  I  the interpreter: the same, plus the cycle profile per function (B2 function starts, swan names, our qol symbols),
     split into inside the 3D draws (phase 1 / phase 2 -> the render call's return) and outside.
Both are exact and repeatable: the same ROM + state + keys give the same numbers (the JIT counts cycles per block, so
its numbers differ from the interpreter's, ~10-15% more busy; compare like with like).
Results: build/perf/results/<sha1>.json; baselines build/perf/baseline_<name>.json.
Paths: REDUX_PERF_LIB (default build/perf-melon/libperf.dylib, built by perf/melon/build.sh when missing),
REDUX_PERF_SAV (battery save), REDUX_PERF_FUNCS (b2funcs.json function starts), REDUX_PERF_NAMES (swan IRDO.yml)."""
import argparse, bisect, glob, hashlib, json, os, pickle, re, subprocess, sys, tempfile, time

T = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(T))
sys.path.insert(0, T)
import rrenv  # noqa: E402

B = rrenv.RR_REAL_B
LIB = os.environ.get('REDUX_PERF_LIB') or os.path.join(B, 'perf-melon', 'libperf.dylib')
SAV = os.environ.get('REDUX_PERF_SAV') or os.path.join(B, 'perf', 'fixture.sav')
FUNCS = os.environ.get('REDUX_PERF_FUNCS') or os.path.join(B, 'ext', 'b2funcs.json')
NAMES = os.environ.get('REDUX_PERF_NAMES') or next(
    (p for p in (os.path.join(os.environ.get('REDUX_SWAN') or os.path.join(B, 'ext', 'swan'), 'IRDO.yml'),)
     if os.path.exists(p)), '')
PY = rrenv.RR_PY

# name: (zone, tile x, tile z, height, season (0 spring .. 3 winter), key script)
SPOTS = {
    'r20_bridge':     (446, 147, 647, 16, 1, '-:30,UP:40,B+UP:40,LEFT:40,RIGHT:30'),
    'r20_bridge_aut': (446, 147, 647, 16, 2, '-:30,LEFT:50,UP:50,B+UP:50'),
    'r20_bridge2':    (446, 142, 664, 16, 1, '-:30,LEFT:60,UP:40,B+LEFT:50'),
    'r20_grass':      (446, 154, 652, 16, 1, '-:30,DOWN:60,UP:60,B+RIGHT:30'),
    'virbank':        (448, 196, 671, 0, 1, '-:30,RIGHT:90,UP:30,B+RIGHT:30'),
    'aspertia':       (427, 55, 712, 16, 1, '-:30,DOWN:60,LEFT:40,B+DOWN:50'),
    'floccesy':       (439, 114, 661, 16, 1, '-:30,DOWN:60,RIGHT:60,B+DOWN:30'),
    'route19':        (437, 60, 694, 16, 1, '-:30,UP:50,LEFT:50,B+DOWN:50'),
    'castelia':       (28, 70, 32, 0, 1, '-:30,DOWN:50,LEFT:50,UP:50'),
    # 690 frames over Route 20 in autumn: block boundaries (map blocks read from the card: the game's own lag frames)
    'r20_long_aut':   (446, 147, 647, 16, 2, '-:30,RIGHT:90,LEFT:90,UP:60,DOWN:60,B+RIGHT:90,B+LEFT:90,B+UP:60,'
                                             'B+DOWN:60,-:60'),
}
# fps60_dbg fields (offsets stable across builds)
F60 = dict(mode=(1, 1), mid=(12, 4), real=(16, 4), van=(20, 4), late=(28, 4), overruns=(84, 4), fallback=(104, 4),
           overloads=(136, 4), mid_skip=(140, 4), mid_late=(200, 4), real_late=(204, 4))
# 3D draw span for the profile split: phase 1 / phase 2 entries -> table B; Run / Alt render-call returns -> table A
DRAW_WATCH = [(0x021808D0, 2), (0x021808F8, 2), (0x021800C8, 1), (0x02180186, 1)]


def sha1(p):
    h = hashlib.sha1()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def ensure_lib():
    if not os.path.exists(LIB):
        subprocess.run(['sh', os.path.join(T, 'melon', 'build.sh'), os.path.dirname(LIB)], check=True)


# ---------------------------------------------------------------------------------------------- workers (one process)
def w_gen(rom, spot, out):
    from mlperf import Melon, Field, teleport
    zone, tx, tz, y, season, _ = SPOTS[spot]
    m = Melon(LIB, rom, SAV)
    m.set_rtc(2026, 10, 15, 12, 0)
    F = Field(m)
    ok = teleport(m, F, zone, tx, tz, y, season)
    m.step(90)
    pl = F.actor(0xFF)
    r = m.state_save(out)
    try:
        m.screenshot(out[:-5] + '.png')
    except ImportError:
        pass
    return dict(ok=bool(ok), zone=F.zone(), tile=[m.s32(pl + 0x44 + 4 * i) >> 16 for i in range(3)] if pl else None,
                follower=bool(F.actor(0xF8)), state=r)


def w_run(rom, mp, state, spot, mode):
    from mlperf import Melon, Field, VBLANK_COUNT, LOOP_FRAMES
    os.environ['ML_JIT'] = '1' if mode == 'J' else '0'
    sym = json.load(open(mp))['symbols']
    D = sym['fps60_dbg']
    m = Melon(LIB, rom, None)
    assert m.state_load(state) == 0, 'state load'
    F = Field(m)
    pl = F.actor(0xFF)
    prof = mode == 'I'
    if prof:
        m.watch([a for a, _ in DRAW_WATCH], [x for _, x in DRAW_WATCH])
        m.prof_start()

    def f60():
        return {k: (m.r8(D + o) if n == 1 else m.r32(D + o)) for k, (o, n) in F60.items()}
    rows = []
    t0, h0 = m.a9()
    hash0 = m.hash(0)
    pos0 = (m.s32(pl + 0x44), m.s32(pl + 0x4C)) if pl else (0, 0)
    c0 = f60()
    for it in SPOTS[spot][5].split(','):
        k, n = it.rsplit(':', 1)
        m.keys = 0
        if k not in ('', '-'):
            m.press(k)
        for _ in range(int(n)):
            vb, lp = m.r32(VBLANK_COUNT), m.r32(LOOP_FRAMES)
            m.step()
            t1, h1 = m.a9()
            hs = m.hash(0)
            pos = (m.s32(pl + 0x44), m.s32(pl + 0x4C)) if pl else (0, 0)
            si = m.swapinfo()
            rows.append(dict(busy=1.0 - (h1 - h0) / max(1, t1 - t0), cyc=(t1 - t0) - (h1 - h0),
                             lag=int((m.r32(VBLANK_COUNT) - vb) > (m.r32(LOOP_FRAMES) - lp)),
                             pic=int(hs != hash0), mv=int(pos != pos0), polys=si[0], verts=si[1], mode=m.r8(D + 1)))
            t0, h0, hash0, pos0 = t1, h1, hs, pos
    c1 = f60()
    res = dict(spot=spot, mode=mode, jit=m.jit_on(), frames=len(rows), rows=rows,
               f60={k: c1[k] - c0[k] for k in F60 if k != 'mode'})
    if prof:
        tmp = tempfile.mkdtemp()
        m.L.ml_prof_dump(os.path.join(tmp, 'a').encode(), 0)
        m.L.ml_profB_dump(os.path.join(tmp, 'b').encode())
        res['prof'] = {t: read_prof(os.path.join(tmp, t)) for t in ('a', 'b')}
    return res


def read_prof(p):
    out = {}
    for line in open(p):
        a, c = line.split()
        if a in ('other', 'halt'):
            continue
        out[int(a, 16)] = int(c)
    return out


# ---------------------------------------------------------------------------------------------- symbols
def symtab(mp):
    """sorted [(start, name)]: B2 functions (main / itcm / overlay 36) + swan names + qol symbols"""
    cache = os.path.join(B, 'perf', 'symtab.pkl')
    base = None
    if os.path.exists(cache):
        try:
            base = pickle.load(open(cache, 'rb'))
        except Exception:
            base = None
    if base is None:
        base = []
        names = {}
        if NAMES and os.path.exists(NAMES):
            cur, mode, segs = None, 'seg', {}
            for line in open(NAMES):
                s = line.strip()
                if s.startswith('Symbols:'):
                    mode = 'sym'
                    continue
                v = s[2:] if s.startswith('- ') else s
                if s.startswith('- '):
                    cur = {}
                if ':' in v and cur is not None:
                    k, _, val = v.partition(':')
                    cur[k.strip()] = val.strip()
                    if mode == 'seg' and k.strip() == 'Name' and 'ID' in cur:
                        segs[int(cur['ID'], 16)] = cur['Name']
                    if mode == 'sym' and k.strip() == 'Segment' and 'Address' in cur:
                        names[(segs.get(int(cur['Segment'], 16), '?'), int(cur['Address'], 16) & ~1)] = cur.get('Name', '?')
        delta = {'overlay_36': ('OVL_36', [0x40]), 'main': ('ARM9', [0, 0x2C]), 'itcm': ('ITCM', [0])}
        if os.path.exists(FUNCS):
            F = json.load(open(FUNCS))
            for seg in ('main', 'itcm', 'overlay_36'):
                for a, n, _ in F.get(seg, []):
                    a &= ~1
                    sg, ds = delta[seg]
                    nm = next((names[(sg, a + d)] for d in ds if (sg, a + d) in names), n)
                    base.append((a, ('ov36:' if seg == 'overlay_36' else '') + nm))
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        pickle.dump(base, open(cache, 'wb'))
    q = [(v & ~1, 'qol:' + k) for k, v in json.load(open(mp))['symbols'].items() if 0x021F0000 <= v < 0x02300000]
    tab = sorted(set(base) | set(q))
    return [a for a, _ in tab], [n for _, n in tab]


def owner(st, pc):
    addrs, names = st
    i = bisect.bisect_right(addrs, pc) - 1
    if i < 0 or pc - addrs[i] > 0x1000:
        return '?%08X' % (pc & ~0xFF)
    return names[i]


# ---------------------------------------------------------------------------------------------- summary
def pct(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(len(v) * p))] if v else 0


def summarize(r, st=None, top=15):
    rows = r['rows']
    n = len(rows)
    mv = [x for x in rows if x['mv']]
    s = dict(busy=round(100 * sum(x['busy'] for x in rows) / n, 1), p90=round(100 * pct([x['busy'] for x in rows], .9), 1),
             max=round(100 * max(x['busy'] for x in rows), 1), kcyc=round(sum(x['cyc'] for x in rows) / n / 1000, 1),
             lag=sum(x['lag'] for x in rows), pics=round(60.0 * sum(x['pic'] for x in mv) / len(mv), 1) if mv else 0.0,
             moving=len(mv), polys=max(x['polys'] for x in rows), verts=max(x['verts'] for x in rows),
             vanfr=sum(1 for x in rows if not x['mode']), **r['f60'])
    if st and 'prof' in r:
        for t, key in (('b', 'draw'), ('a', 'other')):
            agg = {}
            for pc, c in r['prof'][t].items():
                o = owner(st, int(pc))
                agg[o] = agg.get(o, 0) + c
            s[key + '_kcyc'] = round(sum(agg.values()) / n / 1000, 1)
            s['top_' + key] = [(o, round(c / n)) for o, c in sorted(agg.items(), key=lambda x: -x[1])[:top]]
    return s


COLS = [('busy', '%5.1f'), ('p90', '%5.1f'), ('max', '%5.1f'), ('kcyc', '%6.1f'), ('lag', '%3d'), ('pics', '%5.1f'),
        ('mid', '%4d'), ('mid_late', '%4d'), ('fallback', '%4d'), ('vanfr', '%4d'), ('polys', '%4d'), ('verts', '%4d')]


def table(res, base=None):
    hdr = '%-15s %s ' % ('spot', 'm') + ' '.join('%*s' % (len(f % 0), c[:len(f % 0)]) for c, f in COLS)
    hdr += '  draw/other kcyc' if any('draw_kcyc' in v for v in res.values()) else ''
    print(hdr)
    for key in sorted(res):
        s = res[key]
        spot, mode = key.rsplit('/', 1)
        line = '%-15s %s ' % (spot, mode) + ' '.join(f % s.get(c, 0) for c, f in COLS)
        if 'draw_kcyc' in s:
            line += '  %6.1f / %6.1f' % (s['draw_kcyc'], s['other_kcyc'])
        print(line)
        if base and key in base:
            b = base[key]
            d = '%-15s %s ' % ('  vs base', ' ') + ' '.join(
                ('%+*.1f' % (len(f % 0), s.get(c, 0) - b.get(c, 0))) for c, f in COLS)
            if 'draw_kcyc' in s and 'draw_kcyc' in b:
                d += '  %+6.1f / %+6.1f' % (s['draw_kcyc'] - b['draw_kcyc'], s['other_kcyc'] - b['other_kcyc'])
            print(d)


def total_profile(res, top):
    for key in ('draw', 'other'):
        agg, nsp = {}, 0
        for k, s in res.items():
            if 'top_' + key not in s:
                continue
            nsp += 1
            for o, c in s['top_' + key]:
                agg[o] = agg.get(o, 0) + c
        if not nsp:
            continue
        print(f'\n-- interpreter profile, {"inside the 3D draws" if key == "draw" else "outside the draws"}: '
              f'cycles per frame, mean over {nsp} spots (top {top} per spot)')
        for o, c in sorted(agg.items(), key=lambda x: -x[1])[:top]:
            print('%9.0f  %s' % (c / nsp, o))


# ---------------------------------------------------------------------------------------------- main
def run_workers(cmds, jobs):
    procs, outs, pend = [], {}, list(cmds)
    while pend or procs:
        while pend and len(procs) < jobs:
            key, args, out = pend.pop(0)
            procs.append((key, out, subprocess.Popen([PY, os.path.abspath(__file__), '--worker'] + args + [out],
                                                     stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)))
        for p in list(procs):
            if p[2].poll() is not None:
                procs.remove(p)
                err = p[2].stderr.read().decode(errors='replace')
                if p[2].returncode:
                    print(f'{p[0]}: worker failed\n{err[-2000:]}', file=sys.stderr)
                else:
                    outs[p[0]] = json.load(open(p[1]))
        time.sleep(0.05)
    return outs


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--worker':
        kind = sys.argv[2]
        out = sys.argv[-1]
        r = w_gen(*sys.argv[3:6]) if kind == 'gen' else w_run(*sys.argv[3:8])
        json.dump(r, open(out, 'w'))
        return
    ap = argparse.ArgumentParser(description='fast deterministic field-performance benchmark (see the docstring)')
    ap.add_argument('--rom', default=os.path.join(B, 'out', 'redux3_en.nds'))
    ap.add_argument('--map', help='qol_map.json of the ROM (default: build/qol/en/qol_map.json)')
    ap.add_argument('--spots', default=','.join(SPOTS))
    ap.add_argument('--modes', default='JI', help='J (JIT), I (interpreter + profile)')
    ap.add_argument('-j', '--jobs', type=int, default=max(2, (os.cpu_count() or 8) - 2))
    ap.add_argument('--top', type=int, default=20)
    ap.add_argument('--regen', action='store_true', help='make the savestates again')
    ap.add_argument('--save-baseline', metavar='NAME')
    ap.add_argument('--baseline', metavar='NAME')
    a = ap.parse_args()
    t0 = time.time()
    mp = a.map or os.path.join(B, 'qol', 'en', 'qol_map.json')
    ensure_lib()
    sh = sha1(a.rom)[:12]
    sd = os.path.join(B, 'perfstates', sh)
    os.makedirs(sd, exist_ok=True)
    spots = [s for s in a.spots.split(',') if s]
    tmp = tempfile.mkdtemp(prefix='perf_')
    gen = [(s, ['gen', a.rom, s, os.path.join(sd, s + '.mlst')], os.path.join(tmp, f'gen_{s}.json')) for s in spots
           if a.regen or not os.path.exists(os.path.join(sd, s + '.mlst'))]
    if gen:
        g = run_workers(gen, a.jobs)
        for s, v in sorted(g.items()):
            print(f'state {s}: {v}')
        print(f'states for ROM {sh}: {time.time() - t0:.1f} s')
    t1 = time.time()
    cmds = [(f'{s}/{mo}', ['run', a.rom, mp, os.path.join(sd, s + '.mlst'), s, mo], os.path.join(tmp, f'run_{s}_{mo}.json'))
            for s in spots for mo in a.modes]
    raw = run_workers(cmds, a.jobs)
    st = symtab(mp) if 'I' in a.modes else None
    res = {k: summarize(v, st, a.top) for k, v in raw.items()}
    print(f'ROM {os.path.basename(a.rom)} {sh}: {len(cmds)} runs in {time.time() - t1:.1f} s '
          f'(busy % per frame mean / p90 / max, kcyc = busy kilocycles per frame, lag = frames over budget, pics = new '
          f'pictures/s while moving, mid / mid_late = midpoint pictures drawn / left out, fallback = updates in vanilla '
          f'30 fps drawing, van = frames in vanilla drawing)')
    base = None
    if a.baseline:
        bp = os.path.join(B, 'perf', f'baseline_{a.baseline}.json')
        base = json.load(open(bp))['res'] if os.path.exists(bp) else None
        if base is None:
            print('no baseline', bp)
    table(res, base)
    total_profile(res, a.top)
    os.makedirs(os.path.join(B, 'perf', 'results'), exist_ok=True)
    doc = dict(rom=a.rom, sha1=sh, time=time.time(), res=res)
    json.dump(doc, open(os.path.join(B, 'perf', 'results', sh + '.json'), 'w'), indent=1)
    if a.save_baseline:
        json.dump(doc, open(os.path.join(B, 'perf', f'baseline_{a.save_baseline}.json'), 'w'), indent=1)
        print('baseline saved:', a.save_baseline)
    print(f'total {time.time() - t0:.1f} s')


if __name__ == '__main__':
    main()
