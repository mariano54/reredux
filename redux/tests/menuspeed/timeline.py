"""timeline.py SCEN STEP EMU ROM DSV SWEEP.json [N] [--vanilla] [--hooks ADDR,..] : replay a sweep scenario (the
flow of SWEEP.json, phase 0) up to step STEP (its key in the JSON), give its input and log N frames (default 200):
per frame the picture change, master brightness (main / sub), a main-loop lag mark, and the calls of the watched
functions (fades, wipes, overlay loads, proc switches, animation waits, task-menu waits, SEs) with their caller."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_B  # noqa: E402
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mh, meas, flow, scen

WATCH = {
    0x020712B0: 'FS_LoadOverlay', 0x0203CDC8: 'OvlUnload', 0x020279B4: 'WipeSet', 0x02027ACC: 'WipeIsFinished',
    0x0204E060: 'FadeSet', 0x0204E0E0: 'FadeIsRunning', 0x0204C560: 'ClactAnimActive', 0x0202DBE4: 'TaskMenuIsFinish',
    0x0203AA88: 'ProcQueue', 0x0203A9BC: 'ProcSwitch', 0x0203AAB0: 'ProcCreate', 0x02006214: 'SE',
    0x020069F4: 'VOICE', 0x0206DA38: 'SEQSTART', 0x0206C33C: 'SEQSTOP',
}
LOOP = 0x0209DA64

a = sys.argv[1:]
vanilla = '--vanilla' in a
shots = None
if '--shots' in a:
    i = a.index('--shots')
    shots = tuple(int(x) for x in a[i + 1].split(','))
    del a[i:i + 2]
prof = None
if '--prof' in a:
    i = a.index('--prof')
    prof = tuple(int(x) for x in a[i + 1].split(','))
    del a[i:i + 2]
extra = []
if '--hooks' in a:
    extra = [int(x, 16) for x in a[a.index('--hooks') + 1].split(',')]
    a = [x for i, x in enumerate(a) if a[i - 1] != '--hooks' and x != '--hooks']
a = [x for x in a if not x.startswith('--')]
name, step, kind, rom, dsv, sw = a[:6]
N = int(a[6]) if len(a) > 6 else 200
R = json.load(open(sw))
steps = scen.SCEN[name](vanilla)
E = mh.emu(kind, rom, dsv, tag=f'tl_{os.getpid()}')
cache = os.path.join(RR_B, 'menuspeed', 'boot', os.path.basename(rom).replace('.nds', ''))
os.makedirs(cache, exist_ok=True)
flow.start(E, cache, teleport=scen.TELEPORT.get(name))
seen = {}
target = None
for st in steps:
    if st[0] == '=':
        meas._press(E, st[1], meas.HOLD) if st[1] is not None else None
        E.step(max(0, st[2] - (meas.HOLD if st[1] is not None else 0)))
        continue
    if st[0] == '=goto':
        flow.goto(E, st[1], st[2])
        continue
    if st[0] == '=wild':
        flow.wild(E)
        continue
    if st[0] == '=face':
        E.step(2, (st[1],))
        E.step(20)
        continue
    k = st[0]
    seen[k] = seen.get(k, 0) + 1
    key = k if seen[k] == 1 else f'{k}#{seen[k]}'
    if key == step:
        target = st
        break
    r = R[key]
    fr = (r['ready'][0] if r['ready'][0] is not None else (r['resp'][0] or 0) + 120) + 30
    meas._press(E, st[1], meas.HOLD)
    E.step(fr - meas.HOLD)
assert target, f'step {step} not found'
E.hook(*WATCH, *extra)
E.hooks()
prev = E.hash()
lp = E.r32(LOOP)
print(f'== {step}: input {target[1]!r} at frame 0 (ready in the sweep: {R.get(step, {}).get("ready")})')
def events():
    g = E.gsys()
    ev = E.r32(g + 0x18) if g else 0
    out = []
    while mh.ram_ok(ev) and len(out) < 6:
        out.append(f'{E.r32(ev + 4):08X}:{E.r32(ev + 8)}')
        ev = E.r32(ev)
    return ' < '.join(out)


pev = None
for f in range(N):
    if prof and f == prof[0]:
        E.L.ml_prof_start()
    if prof and f == prof[1]:
        E.L.ml_prof_dump(os.fsencode(f'/tmp/prof_{os.getpid()}.txt'), 1)
        print('profile', f'/tmp/prof_{os.getpid()}.txt')
    meas._press(E, target[1] if f < meas.HOLD else None, 1)
    h = E.hash()
    l2 = E.r32(LOOP)
    bm, bs = E.r16(0x0400006C), E.r16(0x0400106C)
    ev = []
    for fr, pc, r0, r1, r2, r3, lr, *_ in E.hooks():
        n = WATCH.get(pc, f'{pc:08X}')
        if n in ('FS_LoadOverlay',):
            ev.append(f'{n}({r1})')
        elif n in ('FadeSet',):
            ev.append(f'{n}({r0},{r1},{r2},{r3}) lr {lr:08X}')
        elif n in ('SE', 'VOICE'):
            ev.append(f'{n}({r0}) lr {lr:08X}')
        elif n == 'WipeSet':
            ev.append(f'{n}({r0},{r1},{r2}) lr {lr:08X}')
        else:
            ev.append(f'{n}({r0:#x},{r1:#x}) lr {lr:08X}' if pc not in WATCH else f'{n} lr {lr:08X}')
    # collapse repeats
    cnt = {}
    for e in ev:
        cnt[e] = cnt.get(e, 0) + 1
    evs = ', '.join(e if c == 1 else f'{e} x{c}' for e, c in cnt.items())
    if shots and shots[0] <= f <= shots[1] and (f - shots[0]) % shots[2] == 0:
        os.makedirs('/tmp/tlshots', exist_ok=True)
        E.image().save(f'/tmp/tlshots/{f:04d}.png')
    e = events()
    if e != pev:
        evs = (evs + '  ' if evs else '') + 'EV ' + (e or '-')
        pev = e
    print(f'{f:4d} {"*" if h != prev else " "} {"L" if l2 == lp else " "} br {bm:04X}/{bs:04X}  {evs}')
    prev, lp = h, l2
