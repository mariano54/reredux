"""tlbatch.py OUTDIR SCEN EMU ROM SWEEP.json N STEP... [-j J] [--vanilla] : timeline.py for several steps in parallel
(OUTDIR/tl_SCEN_STEP.txt)."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_B, RR_PY  # noqa: E402
import os, subprocess, sys, time

a = sys.argv[1:]
van = '--vanilla' in a
a = [x for x in a if x != '--vanilla']
j = 6
if '-j' in a:
    i = a.index('-j')
    j = int(a[i + 1])
    del a[i:i + 2]
out, scen, emu, rom, sw, n = a[:6]
steps = a[6:]
lang = 'jp' if '_jp' in os.path.basename(rom) else 'en'
dsv = f'{RR_B}/statview_integ/dsv/rel_{lang}_smoke_{lang}.dsv'
HERE = os.path.dirname(os.path.abspath(__file__))
os.makedirs(out, exist_ok=True)
run = []
while steps or run:
    while steps and len(run) < j:
        s = steps.pop(0)
        f = open(f'{out}/tl_{scen}_{s}.txt', 'w')
        run.append((s, subprocess.Popen([RR_PY, f'{HERE}/timeline.py', scen, s, emu, rom, dsv, sw, n] + (['--vanilla'] if van else []),
                                        stdout=f, stderr=subprocess.DEVNULL)))
    for x in list(run):
        if x[1].poll() is not None:
            run.remove(x)
            print(x[0], 'done', flush=True)
    time.sleep(1)
