"""t_select.py LANG : SELECT in the field (rules.c settings view, rules_dbg.views) vs SELECT in the summary (statview_keys)
on the statview test ROM (all release modules + qol2_test) with the smoke battery save (Continue, Pokémon Center).
 1 SELECT in the free field: the settings view starts (views + 1), A until the field is free
 2 X -> Pokémon -> lead -> Summary -> stats page -> SELECT x3 (statview toggles + 3: totals / ability / totals)
 3 SELECT x2 again (IV, EV view left on) then B out: the last B pressed together with SELECT, and SELECT tapped every
   frame while the party / start menu close: the settings view must not start (views unchanged), field free
 4 SELECT in the field again: the view starts (views + 1), closes; walking works"""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sv import SV, B
from desmume.controls import Keys, keymask

lang = sys.argv[1]
q = SV(f'sv_select_{lang}', f'{B}/out/sv_{lang}.nds', f'sv_{lang}', f'{B}/statview_integ/dsv/rel_{lang}_smoke_{lang}.dsv',
       elf=f'{B}/redux3/{lang}_follow.elf')
D = q.sym_addr('sv_dbg')
RD = q.sym_addr('rules_dbg')


def views():
    return q.r32(RD + 52)


def toggles():
    return q.svdbg()['toggles']


def close_view():
    for i in range(30):
        if not q.event_running():
            break
        q.tap('A')
        q.step(70)
    return q.wait_field(900, settle=30)


q.boot_continue()
q.check('field free after Continue', q.wait_field(900, settle=30), True)
v0 = views()
q.tap('SELECT'); q.step(60)
q.snap('field_view')
q.check('1 field SELECT: view started', (views() - v0, q.event_running()), (1, True))
q.check('1 view closed, field free', close_view(), True)
v1 = views()
t0 = toggles()
q.tap('X'); q.step(40); q.touch(64, 48); q.step(90)
q.tap('A'); q.step(90); q.tap('A'); q.step(90); q.tap('A'); q.step(150)
q.tap('RIGHT'); q.step(60)
q.snap('stats')
for k in range(3):
    q.tap('SELECT'); q.step(60)
    q.snap(f'sel{k}')
q.check('2 summary SELECT x3 toggles (statview)', (toggles() - t0, q.svdbg()['mode']), (3, 1))
q.tap('SELECT'); q.step(40)
q.tap('SELECT'); q.step(40)
q.check('3 totals on', q.svdbg()['mode'], 1)
q.check('3 no settings view inside the summary', views(), v1)
# B out of the summary first: while it redraws a page (SELECT's view change, as vanilla's UP/DOWN Pokémon change)
# the summary ignores keys until its print queue is done, so SELECT mashed every few frames there swallows B (vanilla
# behaviour, measured with build/scripts/statview/dbg_spam.py). Then B out of the party list / start menu (every 60
# frames) with SELECT tapped every 4 frames in between (not with B: SELECT+B = SELECT), until free
q.tap('B'); q.step(60)
q.snap('summary_closed')
mB, mS = keymask(Keys.KEY_B), keymask(Keys.KEY_SELECT)
free = 0
for i in range(600):
    if i % 30 == 1:
        q.emu.input.keypad_add_key(mB)
    if i % 2 == 0 and i % 30 != 1:
        q.emu.input.keypad_add_key(mS)
    q.step(1)
    q.emu.input.keypad_rm_key(mB)
    q.emu.input.keypad_rm_key(mS)
    q.step(1)
    if q.field_ready() and not q.event_running():
        free += 1
        if free >= 4:
            break
    else:
        free = 0
q.step(30)
q.snap('closed_with_select')
q.say('views after closing with SELECT spam', views(), 'v1', v1, 'event', q.event_running(), 'frame', q.frame)
# SELECT spam right as the field became free may legitimately open the view (the player pressed it in the field);
# only a view started before the field was free would be a clash. Record which.
if views() != v1:
    q.say('a view started while/after closing (SELECT held into the free field)')
    close_view()
v2 = views()
q.check('3 field free after the summary', q.wait_field(900, settle=30), True)
# plain close (no SELECT while closing): open the summary again, SELECT there, close with B only
q.tap('X'); q.step(40); q.touch(64, 48); q.step(90)
q.tap('A'); q.step(90); q.tap('A'); q.step(90); q.tap('A'); q.step(150)
q.tap('RIGHT'); q.step(60)
q.tap('SELECT'); q.step(60)
q.tap('SELECT'); q.step(2)
for _ in range(4):
    q.tap('B'); q.step(40)
q.check('3b field after B', q.wait_field(2000, tap='B', settle=30), True)
q.check('3b SELECT in the summary did not start the settings view', views(), v2)
q.tap('SELECT'); q.step(60)
q.snap('field_view2')
q.check('4 field SELECT again: view started', (views() - v2, q.event_running()), (1, True))
q.check('4 view closed', close_view(), True)
p0 = q.pos()
q.hold('LEFT', 20); q.step(10)
q.check('4 walks after', q.pos() != p0, True)
q.result()
q.sheet()
