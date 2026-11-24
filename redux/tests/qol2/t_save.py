"""t_save.py LANG KIND MODE : menu save from KIND_LANG_MODE_kg (X, touch SAVE; A on the yes/no if one comes),
EventSave_Update (OVL_12 0x02163B38) states logged. The battery save is left in
<battery dir>/KIND_LANG_save_MODE.dsv for t_boot.py.
MEAS q = touch -> yes/no (state 4) or, with quick save, state 5; write = state 5 -> 10 (pre-scan + write);
total = touch -> field free."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, sys
from qt import QR

lang, kind, mode = sys.argv[1:4]
q = QR(f'save_{kind}_{lang}_{mode}', lang, kind, run=f'save_{mode}')
q.load(f'{mode}_kg')
st = []


def sh(a, s):
    v = q.r32(q.emu.memory.register_arm9.r1)
    if not st or st[-1][1] != v:
        st.append((q.frame, v))


q.emu.memory.register_exec(0x02163B38, sh, 2)
q.step(5)
q.tap('X')
q.step(40)
t0 = q.frame
q.emu.input.touch_set_pos(190, 92)
q.step(6)
q.emu.input.touch_release()
asked = False
for i in range(1500):
    q.step(1)
    if st and st[-1][1] == 4 and (q.frame - st[-1][0]) % 20 == 10:
        q.hold('A', 4)              # YES (repeated until the yes/no takes it)
        asked = True
    if st and st[-1][1] >= 10 and q.field_ready():
        break
ok = q.wait_free(600)
tf = q.frame
f = {}
for fr, v in st:
    f.setdefault(v, fr)
q.say('save states', st)
quick = q.flag(0x5DD)
q.check('yes/no answered by the player: only without quick save', asked, not quick)
q.say('MEAS q', (f.get(4 if not quick else 5, 0) - t0), 'MEAS write', (f[10] - f[5]) if 10 in f and 5 in f else None,
      'MEAS total', tf - t0, 'quick', quick, 'qol2_dbg', q.q2dbg())
q.check('save done (state 10 reached)', 10 in f, True)
q.check('field after', ok, True)
q.snap('after')
q.step(120)
try:
    q.emu.close()                       # flush the battery save
except Exception as e:
    q.say('close:', e)
dsv = q.dsv(kind, lang, f'save_{mode}')
q.say('battery save', dsv, os.path.exists(dsv) and os.path.getsize(dsv))
q.check('battery save written', os.path.exists(dsv), True)
q.result(dict(write=(f[10] - f[5]) if 10 in f and 5 in f else None, total=tf - t0))
