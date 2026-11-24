"""t_egg.py LANG : an Egg in the party (slot 1 gets the egg flag through q2tst): lead summary -> stats page -> SELECT (totals)
-> DOWN (the Egg is skipped; SELECT ignored on Eggs); then the Egg's own summary."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sv import SV, B

lang = sys.argv[1]
q = SV(f'sv_egg_{lang}', f'{B}/out/sv_{lang}.nds', f'sv_{lang}', f'{B}/statview_integ/dsv/rel_{lang}_smoke_{lang}.dsv')
T = q.sym_addr('q2tst')
D = q.sym_addr('sv_dbg')


def q2(cmd, a=0, b=0, c=0):
    q.w32(T + 8, a); q.w32(T + 12, b); q.w32(T + 16, c); q.w32(T + 4, cmd)
    q.step(3)
    assert q.r32(T + 4) == 0, 'q2tst not run'
    return q.r32(T + 20)


def dbg():
    return q.svdbg()


q.boot_continue()
q2(2, 1, 0x4C, 1)
q.check('slot 1 is an Egg', q2(1, 1, 0x4C), 1)
q.tap('X'); q.step(40); q.touch(64, 48); q.step(90)
q.tap('A'); q.step(90); q.tap('A'); q.step(90); q.tap('A'); q.step(150)
q.check('summary opened on the lead', dbg()['mode'], 0)
q.tap('RIGHT'); q.step(60)
q.tap('SELECT'); q.step(60)
q.snap('lead_totals')
q.tap('DOWN'); q.step(90)
q.snap('down_skips_egg')
q.check('DOWN skips the Egg (the game does), totals stay', dbg()['mode'], 1)
q.tap('B'); q.step(90)
q.snap('party')
q.touch(190, 30); q.step(60)            # the Egg's slot
q.snap('egg_slot')
q.tap('A'); q.step(90)
q.snap('egg_menu')
q.tap('A'); q.step(150)
q.snap('egg_summary')
d0 = dbg()
for k in ('SELECT', 'RIGHT', 'SELECT', 'LEFT', 'SELECT'):
    q.tap(k); q.step(60)
    q.snap('egg_' + k)
q.check('Egg summary: SELECT does nothing', (dbg()['toggles'], dbg()['draws']), (d0['toggles'], d0['draws']))
for _ in range(4):
    q.tap('B'); q.step(40)
q.check('field after closing', q.wait_field(2000, tap='B', settle=30), True)
q.result()
q.sheet()
