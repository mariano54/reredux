"""t_apps.py LANG KIND MODE [APPS] : start-menu apps from KIND_LANG_MODE_kg (bedroom): X, touch the app, then B.
MEAS per app: open = touch -> app fully lit (20 frames at normal brightness); close = B -> field lit again;
sel = touch -> first fade frame. APPS: comma list of party, bag, card (default all three)."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import sys
from qt import QR

lang, kind, mode = sys.argv[1:4]
apps = sys.argv[4].split(',') if len(sys.argv) > 4 else ['party', 'bag', 'card']
POS = {'party': (64, 48), 'bag': (190, 48), 'card': (64, 92)}
q = QR(f'apps_{kind}_{lang}_{mode}', lang, kind)
q.load(f'{mode}_kg')
q.hook(0x020279B4, 'wipe')
q.step(5)
res = {}
for app in apps:
    q.tap('X')
    q.step(40)
    t0 = q.frame
    q.emu.input.touch_set_pos(*POS[app])
    q.step(6)
    q.emu.input.touch_release()
    d = q.until_dark(300)
    lit = q.until_lit(600)
    q.snap(app)
    q.step(20)
    t1 = q.frame
    q.hold('B', 4)
    d2 = q.until_dark(300)
    lit2 = q.until_lit(600)
    q.wait_free(300)
    q.step(20)
    res[app] = (d - t0 if d else None, lit - t0 if lit else None, lit2 - t1 if lit2 else None)
    q.say(f'MEAS {app} sel {res[app][0]} open {res[app][1]} close {res[app][2]}')
    if q.ui() is not None or not q.field_ready():
        q.tap('B')
        q.wait_free(300)
q.say('wipes', len([e for e in q.events if e[1] == 'wipe']), 'qol2_dbg', q.q2dbg())
q.check('all measured', all(None not in v for v in res.values()), True)
q.result(res)
