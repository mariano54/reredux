"""batch.py OUTDIR [-j N] JOB... : run sweep.py jobs in parallel (at most N emulators, default 6).
JOB = SCEN:ROM:LANG:EMU[:EXTRA,ARGS[:TAG]], ROM = van (Redux 1.4.1, EN only) | base (build/out/base_LANG.nds: ReRedux before this
module) | new (build/out/redux3_LANG.nds) | a path; EMU = mel | dsm. Logs and JSON: OUTDIR/SCEN_ROM_LANG_EMU.*"""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_B, RR_PY  # noqa: E402
import os, subprocess, sys, time

a = sys.argv[1:]
out = a.pop(0)
j = 6
if a and a[0] == '-j':
    j = int(a[1])
    a = a[2:]
os.makedirs(out, exist_ok=True)
HERE = os.path.dirname(os.path.abspath(__file__))
B = RR_B


def rom(r, lang):
    if r == 'van':
        return f'{B}/vanilla_rom/redux.nds'
    if r == 'base':
        return f'{B}/out/base_{lang}.nds'
    if r == 'new':
        return f'{B}/out/redux3_{lang}.nds'
    return r


def dsv(lang):
    return f'{B}/statview_integ/dsv/rel_{lang}_smoke_{lang}.dsv'


jobs = []
for spec in a:
    scen, r, lang, emu, *x = spec.split(':')
    extra = x[0].split(',') if x else []
    tag = f'{scen}_{os.path.basename(r).replace(".nds", "") if "/" in r else r}_{lang}_{emu}' + (f'_{x[1]}' if len(x) > 1 else '')
    cmd = [RR_PY, f'{HERE}/sweep.py', scen, emu, rom(r, lang), dsv(lang), f'{out}/{tag}.json'] + (['--vanilla'] if r == 'van' else []) + extra
    jobs.append((tag, cmd))
run = []
t0 = time.time()
while jobs or run:
    while jobs and len(run) < j:
        tag, cmd = jobs.pop(0)
        lf = open(f'{out}/{tag}.log', 'w')
        run.append((tag, subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT), time.time()))
    for x in list(run):
        if x[1].poll() is not None:
            run.remove(x)
            print(f'{x[0]}: rc {x[1].returncode} ({time.time() - x[2]:.0f}s)', flush=True)
    time.sleep(1)
print(f'all done in {time.time() - t0:.0f}s', flush=True)
