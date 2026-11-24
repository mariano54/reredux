"""t_release.py LANG : the release ROM (build/out/redux3_LANG.nds) with the smoke battery save: lead summary -> stats
(IV / EV columns) -> SELECT x3 (totals, ability, totals) -> DOWN (second Pokémon, totals kept) -> B; shots + sv_dbg."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sv import SV, B

lang = sys.argv[1]
q = SV(f'sv_release_{lang}', f'{B}/out/redux3_{lang}.nds', lang,
       f'{B}/statview_integ/dsv/rel_{lang}_smoke_{lang}.dsv')

q.boot_continue()
q.tap('X'); q.step(40); q.touch(64, 48); q.step(90)
q.tap('A'); q.step(90); q.tap('A'); q.step(90); q.tap('A'); q.step(150)
q.tap('RIGHT'); q.step(60)
q.snap('stats')
d0 = q.svdbg()
q.say('stats', d0)
q.check('stats page: 6 IV / EV rows', (d0['rows'], d0['mode']), (6, 0))
q.check('IV / EV columns inked (Attack row)', q.ink(186, 58, 205, 71) > 5 and q.ink(216, 58, 243, 71) > 5, True)
for k in ('SELECT', 'SELECT', 'SELECT', 'DOWN'):
    q.tap(k); q.step(60)
    q.snap(k)
    q.say(k, q.svdbg())
d = q.svdbg()
q.check('toggles', d['toggles'], 3)
q.check('totals on the second Pokémon', (d['mode'], d['rows']), (1, 6))
q.check('second Pokémon drawn (other IVs)', d['ivs'] != d0['ivs'], True)
for _ in range(4):
    q.tap('B'); q.step(40)
q.check('field after closing', q.wait_field(2000, tap='B', settle=30), True)
q.result()
q.sheet()
