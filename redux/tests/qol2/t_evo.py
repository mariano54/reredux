"""t_evo.py LANG KIND MODE TAP : real evolution after a battle, from KIND_LANG_MODE_kg: Patrat (lead) set to Lv19 with
EXP one below Lv20, beats a wild Patrat -> Lv20 -> evolves into Watchog. TAP (A or B) every 30 frames during
the evolution scene (B: cancel, the species must stay Patrat).
MEAS evo = evolution proc init -> exit (ov284 0x021E30E0 / 0x021E31D8). Frames recorded every 4."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, sys
from qt import QR

lang, kind, mode, tapk = sys.argv[1:5]
q = QR(f'evo_{kind}_{lang}_{mode}_{tapk}', lang, kind)
q.load(f'{mode}_kg')
q.step(5)
q.set_pparam(0, 0x9E, 19)
q.set_pparam(0, 8, 20 ** 3 - 1)
q.say('Patrat level', q.pparam(0, 0x9E), 'exp', q.pparam(0, 8))
q.hook(0x021E30E0, 'evo_init')
q.hook(0x021E31D8, 'evo_exit')
q.bed('PATRAT')
q.check('battle menu', q.until({'menu'}, 3000, tap='B'), 'menu')
for k in range(6):
    if q.ui() == 'menu':
        q.fight(0)
    for i in range(60):
        q.step(10)
        if q.ui() == 'menu' or q.first('evo_init'):
            break
    if q.first('evo_init'):
        break
    if q.ui() != 'menu':                  # level-up messages / stat box
        for i in range(60):
            q.tap('A', idle=10)
            if q.first('evo_init') or q.ui() == 'menu':
                break
    if q.first('evo_init'):
        break
t0 = q.first('evo_init')
q.check('evolution started', t0 is not None, True)
q.rec = q.dir + '/rec'
os.makedirs(q.rec, exist_ok=True)
q.every = 4
n = 0
while not q.first('evo_exit') and n < 100:
    q.tap(tapk, idle=24)
    n += 1
q.rec = None
t1 = q.first('evo_exit')
q.say('MEAS evo', (t1 - t0) if t0 and t1 else None)
ok = q.wait_free(1500, tap='B')
q.check('field after', ok, True)
sp = q.pparam(0, 5)
q.say('species', sp, 'level', q.pparam(0, 0x9E), 'qol2_dbg', q.q2dbg())
q.check('species', sp, 504 if tapk == 'B' else 505)
q.snap('end')
q.result(dict(evo=(t1 - t0) if t0 and t1 else None))
