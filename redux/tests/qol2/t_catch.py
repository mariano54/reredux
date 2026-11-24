"""t_catch.py LANG KIND MODE [TAP] : wild encounter + new-species catch timings from KIND_LANG_MODE_kg (Patrat lead,
kit): bed "Wild Lillipup" -> Master Ball -> tap TAP (default B) every 20 frames -> field.
MEAS lines (frames): enc = EventBattleCall state 1 -> 2 (encounter effect); capjingle = frames the
capture-ME wait ran (ov167 0x021B84B6); dex_in = dex registration proc entry -> first blend step (input
accepted later); use2field = Master Ball USE -> field free. Recorded frames: out/<name>/rec (every 2nd)."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import sys
from qt import QR

lang, kind, mode = sys.argv[1], sys.argv[2], sys.argv[3]
tapk = sys.argv[4] if len(sys.argv) > 4 else 'B'
name = f'catch_{kind}_{lang}_{mode}_{tapk}'
q = QR(name, lang, kind)
q.load(f'{mode}_kg')
bc_state = []


def bc(a, s):
    r = q.emu.memory.register_arm9
    st = q.r32(r.r1)
    if not bc_state or bc_state[-1][1] != st:
        bc_state.append((q.frame, st))


q.emu.memory.register_exec(0x02168BAC, bc, 2)
q.hook(0x021B84B6, 'capwait')
q.hook(0x021F434E, 'dex_entry')        # OVL_297 entry fade set-up
q.hook(0x021F4476, 'dex_blend')
q.hook(0x020279B4, 'wipe')
q.step(10)
q.bed('LILLIPUP')
t0 = q.frame
st = q.until({'menu'}, 3000, tap='B')
q.check('battle menu', st, 'menu')
q.say('battle call states', bc_state)
s1 = next((f for f, s in bc_state if s == 1), None)
s2 = next((f for f, s in bc_state if s == 2), None)
enc = s2 - s1 if s1 and s2 else None
q.say('MEAS enc', enc, 'bed->menu', q.frame - t0)
q.snap('menu')
q.rec = q.dir + '/rec'
import os
os.makedirs(q.rec, exist_ok=True)
q.bag_use('balls', 0, 'use')
tu = q.frame - 90                         # bag_use waits 90 frames after the USE touch
for i in range(150):
    q.tap(tapk, idle=14)
    if q.field_ready():
        break
ok = q.wait_free(600, tap=tapk)
tf = q.frame
q.rec = None
caps = [e[0] for e in q.events if e[1] == 'capwait']
dexe = q.first('dex_entry')
dexb = q.first('dex_blend')
q.say('MEAS capjingle', (caps[-1] - caps[0] + 1) if caps else None, 'MEAS dex_in', (dexb - dexe) if dexe and dexb else None,
      'MEAS use2field', tf - tu, 'wipes', sum(1 for e in q.events if e[1] == 'wipe'))
q.check('field after the catch', ok, True)
q.check('Lillipup in the party', 506 in [q.pparam(i, 5) for i in range(4)], True)
q.say('qol2_dbg', q.q2dbg())
q.snap('end')
q.result(dict(enc=enc, cap=(caps[-1] - caps[0] + 1) if caps else None, use2field=tf - tu))
