"""t_view.py LANG [STATE] : the settings view (SELECT in the free field) on the QA2 ROM, from qa2_LANG_custom_bedroom
(t_menu.py custom: Challenge, White Forest, Classic + graveyard, species limit line, statics, no battle items,
quick save). Death counter set to 3. Checks: SELECT starts the view (rules_dbg.views + 1) and it ends with the
field free; every page shot; SELECT while the bed's list menu (an event) is open does nothing; walking still
works after. Shots build/qa2/view_LANG/, sheet build/qa2/view_LANG_sheet.png."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qa2 import Q2, V_DEATHS

lang = sys.argv[1]
state = sys.argv[2] if len(sys.argv) > 2 else 'custom_bedroom'
q = Q2(f'view_{lang}_{state}', lang)
q.load(state)
q.step(10)
q.setvar(V_DEATHS, 3)
q.say('flags', q.rules_flags(), 'limit', q.var(0x4199), 'city', q.var(0x419A), 'diff', q.var(0x4198))
v0 = q.dbg2()['views']
q.tap('SELECT')
q.step(60)
q.check('SELECT: view started', (q.dbg2()['views'] - v0, q.event_running()), (1, True))
for i in range(20):
    q.snap(f'page_{i:02d}')
    if not q.event_running():
        break
    q.tap('A')
    q.step(70)
q.check('view over, field free', q.wait_free(600), True)
q.snap('after')
# SELECT while an event (the bed's list menu) is open: nothing
q.goto(13, 3)
q.face('LEFT')
q.tap('A')
q.step(150)
v1 = q.dbg2()['views']
q.tap('SELECT')
q.step(60)
q.snap('select_in_event')
q.check('SELECT during an event: no view', q.dbg2()['views'], v1)
q.tap('B')
q.wait_free(600, tap='B')
p0 = q.pos()
q.hold('RIGHT', 20)
q.step(10)
q.check('walks after', q.pos() != p0, True)
q.result()
q.sheet(both=False)
