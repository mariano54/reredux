"""t_prep.py LANG MODE [KIND] : from KIND_LANG_MODE_bedroom: bed GIFT (Patrat, no nickname) + KIT (2 Dragonite,
balls) -> state MODE_kg (Patrat lead); then ROUTE (Route 19 grass) -> state MODE_r19. Shots in out/prep_*."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import sys
from qt import QR

lang, mode = sys.argv[1], sys.argv[2]
kind = sys.argv[3] if len(sys.argv) > 3 else 'q2t'
q = QR(f'prep_{kind}_{lang}_{mode}', lang, kind)
q.load(f'{mode}_bedroom')
q.step(30)
q.bed('GIFT')
q.step(60)
q.snap('gift')
q.tap('A')                       # "You received a Pokémon!"
q.step(90)
q.snap('nick_q')
q.tap('B')                       # nickname? -> No
q.step(30)
q.check('gift: field free', q.wait_free(1500, tap='B'), True)
q.bed('KIT')
q.check('kit: field free', q.wait_free(1500, tap='B'), True)
q.check('party', [q.pparam(i, 5) for i in range(3)], [504, 149, 149])
q.snap('kg')
q.save(f'{mode}_kg')
q.bed('ROUTE')
q.check('route 19: field free', q.wait_free(1500, tap='B'), True)
q.step(60)
q.say('zone', q.zone(), 'pos', q.pos())
q.snap('r19')
q.save(f'{mode}_r19')
q.result()
