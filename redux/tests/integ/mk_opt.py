"""mk_opt.py LANG : qol2 kind-qa 'opt' states (Quick save 0x5DD + Quick Surf 0x5DE on) from the def ones
(def_bedroom -> opt_bedroom, def_kg -> opt_kg). The redesigned settings menu has no separate Speed page, so
t_menu2.py can't make them; the flags are what the menu sets."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import sys
sys.path.insert(0, f'{RR_T}/qol2')
from qt import QR
lang = sys.argv[1]
q = QR(f'mkopt_qa_{lang}', lang, 'qa')
for st in ('bedroom', 'kg'):
    q.load(f'def_{st}')
    q.step(5)
    q.set_flag(0x5DD)
    q.set_flag(0x5DE)
    q.step(5)
    q.check(f'{st} flags', (q.flag(0x5DD), q.flag(0x5DE)), (1, 1))
    q.save(f'opt_{st}')
q.result()
