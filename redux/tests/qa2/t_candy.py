"""t_candy.py LANG KEY [trade] : evolution from the field (QA2 ROM, qa2_LANG_def_bedroom, speed-ups on). Patrat Lv19 +
Rare Candy by script; X -> Bag -> Medicine -> Rare Candy -> Use -> Patrat: Lv20 -> evolution scene (ov284 init /
exit hooks), KEY (A: skip the flicker, B: cancel) tapped every 24 frames. A: Watchog; B: still Patrat.
qol2_dbg.evo_skips counted. trade: instead, the evolution data of every trade-method evolution in Redux is listed
(gen5data) - see the log. Frames recorded every 4 -> sheet build/qa2/candy_LANG_KEY_sheet.png."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qa2 import Q2

lang, key = sys.argv[1], sys.argv[2]
q = Q2(f'candy_{lang}_{key}', lang)
q.load('def_bedroom')
q.step(10)
q.script(['    PokePartyAdd 0x8020, 504, 0, 19', '    ItemAdd 50, 3, 0x8020'])
q.check('Patrat Lv19', (q.pparam(0, 5), q.pparam(0, 0x9E)), (504, 19))
q.hook(0x021E30E0, 'evo_init')
q.hook(0x021E31D8, 'evo_exit')
d0 = q.q2dbg().get('evo_skips', 0)
for k, w in (('X', 40), ((64, 48), 90), ('RIGHT', 60), ('A', 60), ('A', 90), ('A', 60)):
    if isinstance(k, tuple):
        q.touch(*k)
    else:
        q.tap(k)
    q.step(w)
q.snap('candy_used')
for i in range(60):
    if q.first('evo_init'):
        break
    q.tap('A', idle=20)
t0 = q.first('evo_init')
q.check('evolution scene started', t0 is not None, True)
rec = os.path.join(q.dir, 'rec')
os.makedirs(rec, exist_ok=True)
q.rec_frames(rec)
q.every = 4
n = 0
while not q.first('evo_exit') and n < 120:
    q.tap(key, idle=18)
    n += 1
q.rec = None
t1 = q.first('evo_exit')
q.say('MEAS evo frames', (t1 - t0) if t0 and t1 else None, 'qol2_dbg', q.q2dbg())
ok = q.wait_free(2000, tap='B')
q.check('field after', ok, True)
sp = q.pparam(0, 5)
q.check('species', (sp, q.pparam(0, 0x9E)), ((504 if key == 'B' else 505), 20))
if key == 'A':
    q.check('A skipped the flicker (qol2_dbg.evo_skips)', q.q2dbg().get('evo_skips', 0) > d0, True)
q.snap('end')
fs = sorted(f for f in os.listdir(rec) if f.endswith('.png'))
if fs:
    a, b = int(fs[0][:6]), int(fs[-1][:6])
    subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ballfx_sheet.py'),
                    rec, str(a), str(b), str(max(4, (b - a) // 40 // 4 * 4)),
                    os.path.join(os.path.dirname(q.dir), f'candy_{lang}_{key}_rec_sheet.png'), '0', '0', '256', '192', '1'])
q.result(dict(evo=(t1 - t0) if t0 and t1 else None))
q.sheet(both=True)
