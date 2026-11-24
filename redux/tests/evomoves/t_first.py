"""t_first.py LANG : first look: party summary -> RIGHT RIGHT (our page) -> shots, A list mode, DOWN, B, DOWN (next Pokémon),
LEFT, B out"""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from em import EM

lang = sys.argv[1]
q = EM(f'em_first_{lang}', lang)
q.boot_continue()
q.say('dbg magic', hex(q.dbg()['magic']))
q.open_summary()
q.snap('status')
q.tap('RIGHT'); q.step(60)
q.snap('stats')
q.tap('RIGHT'); q.step(90)
q.snap('evo')
q.say('dbg', q.dbg())
q.tap('A'); q.step(40)
q.snap('list')
q.tap('DOWN'); q.step(30)
q.tap('DOWN'); q.step(30)
q.snap('list_down2')
q.say('dbg', q.dbg())
q.tap('B'); q.step(40)
q.snap('list_off')
q.tap('DOWN'); q.step(90)
q.snap('next_mon')
q.say('dbg', q.dbg())
q.tap('UP'); q.step(90)
q.tap('LEFT'); q.step(90)
q.snap('back_stats')
q.tap('RIGHT'); q.step(90)
q.snap('evo_again')
q.check('field after closing', q.close_summary(), True)
q.say('dbg', q.dbg())
q.result()
q.sheet()
