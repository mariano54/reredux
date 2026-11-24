"""sweep.py SCEN EMU ROM DSV OUT.json [--vanilla] [--phases N] [--margin M] [--speedoff] : the menu-speed sweep, one
scenario (scen.py) per process, run by flowrun.py.

Each scenario starts from the battery save's Continue (Aspertia Pokémon Center). A measured step's resp / ready are
frames from the input to the first changed picture / until the next input is taken (meas.py); the flow goes on at
ready + M (default 30; --margin 1 = an eager player, for the sound check). --vanilla: Redux 1.4.1 (the X menu opens
with the cursor hidden; the PC's two extra lines). --speedoff: the speed-ups flag 0x5DA set after Continue.
Output: OUT.json (steps, _order, _steps, _snd sound events, _hold key repeats, _save block CRCs), OUT_save.bin (the
RAM save buffer at the end), OUT_dir/NN_step.png."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_B  # noqa: E402
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mh, meas, flow, flowrun, scen

a = sys.argv[1:]
vanilla = '--vanilla' in a
speedoff = '--speedoff' in a
phases = int(a[a.index('--phases') + 1]) if '--phases' in a else 2
margin = int(a[a.index('--margin') + 1]) if '--margin' in a else 30
a = [x for x in a if not x.startswith('--') and not x.isdigit()]
name, kind, rom, dsv, out = a[:5]
steps = scen.SCEN[name](vanilla)
E = mh.emu(kind, rom, dsv, tag=f'sw_{name}_{os.getpid()}')
cache = os.path.join(RR_B, 'menuspeed', 'boot', os.path.basename(rom).replace('.nds', ''))
os.makedirs(cache, exist_ok=True)
flow.start(E, cache, teleport=scen.TELEPORT.get(name))
if speedoff:
    flowrun.set_flag(E, 0x5DA, True)
    E.step(2)
meas.snd_hooks(E)
t0 = time.time()
res = flowrun.run(E, steps, phases, margin, os.path.splitext(out)[0] + '_dir', log=lambda *x: print(*x, flush=True))
res['_meta'] = dict(scen=name, emu=kind, rom=os.path.realpath(rom), vanilla=vanilla, phases=phases, margin=margin,
                    speedoff=speedoff, secs=round(time.time() - t0))
data = res.pop('_save_bin', b'')
if data:
    open(os.path.splitext(out)[0] + '_save.bin', 'wb').write(data)
json.dump(res, open(out, 'w'), indent=1)
print('wrote', out, flush=True)
