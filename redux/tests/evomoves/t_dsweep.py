"""t_dsweep.py LANG [FIRST LAST] : every species (default 1-649) on the Pokédex INFO page: all registered as caught
(q2tst cmd 7), the entry opened, then each species shown in turn (the list's next entry set to it, DOWN): its base
stats, total and abilities checked against personal.json, our box on the top screen; shots of every 50th; the Pokédex
closed at the end (field reached = no crash)."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from em import EM
from ds import ds, expect, open_entry, species_list, show

lang = sys.argv[1]
lo, hi = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else (1, 649)
q = EM(f'em_dsweep_{lang}', lang)
q.boot_continue()
open_entry(q, 649)
d = ds(q)
q.check('INFO with our box', (d['on'], d['shown']), (1, 1))
lst, count, idxp = species_list(q)
bad = 0
for sp in range(lo, hi + 1):
    d = show(q, lst, count, idxp, sp)
    st, tot, ab = expect(sp, d['form'])
    got = (d['species'], d['shown'], d['caught'], d['pending'], d['stats'], d['total'], d['abil'])
    want = (sp, 1, 1, 0, st, tot, ab)
    if got != want:
        bad += 1
        q.check(f'species {sp}', got, want)
        q.snap(f'bad_{sp}')
    elif sp % 50 == 0:
        q.snap(f'sp{sp}')
q.say('checked', hi - lo + 1, 'bad', bad, ds(q))
q.check('every species', bad, 0)
q.tap('B'); q.step(150)
q.tap('B'); q.step(150)
q.check('field after the Pokédex', q.wait_field(3000, tap='B', settle=30), True)
q.result()
q.sheet(cols=7)
