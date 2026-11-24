"""t_ci.py LANG KIND MODE [turbo] : 3D field effect (EventFieldEffect, OVL_36 0x021BBA14) timing for the bed menu's
"Wild Patrat" battle start (KIND_LANG_MODE_kg). turbo: press R in the field first (2x field; qol2 must not
double the cut-in again). MEAS ci9 = frames in play state 9; ci = first -> last callback frame."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, sys
from qt import QR

lang, kind, mode = sys.argv[1:4]
turbo = len(sys.argv) > 4 and sys.argv[4] == 'turbo'
q = QR(f'ci_{kind}_{lang}_{mode}{"_turbo" if turbo else ""}', lang, kind)
q.load(f'{mode}_kg')
st = []


def ch(a, s):
    v = q.r32(q.emu.memory.register_arm9.r1)
    st.append((q.frame, v))


q.emu.memory.register_exec(0x021BBA14, ch, 2)
q.step(5)
if turbo:
    q.tap('R')
    q.step(10)
    a = q.sym['turbo_dbg'] & ~1
    q.say('turbo on/live', q.r8(a), q.r8(a + 1))
    q.check('turbo on', q.r8(a), 1)
q.rec = q.dir + '/rec'
os.makedirs(q.rec, exist_ok=True)
q.bed('PATRAT')
q.check('battle menu', q.until({'menu'}, 3000, tap='B'), 'menu')
q.rec = None
f9 = [f for f, v in st if v == 9]
calls = len(st)
q.say('states', sorted(set(v for f, v in st)), 'calls', calls)
q.say('MEAS ci9', (f9[-1] - f9[0] + 1) if f9 else None, 'MEAS ci', (st[-1][0] - st[0][0]) if st else None,
      'calls9', len(f9), 'qol2_dbg', q.q2dbg())
q.result(dict(ci9=(f9[-1] - f9[0] + 1) if f9 else None))
