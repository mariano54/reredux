"""t_sweep.py LANG [FIRST LAST] : every species FIRST..LAST (default 1..649) and every form on the summary's EVO/MOVES page:
the species is written into party slot 0 / 1 alternately (q2tst), UP / DOWN shows it; each page's family and learnset are
checked against the ROM data (expect.py), and that it fits (no overflow, <= 8 lines). Shots of every 40th species and of
the forms -> build/statview_integ/em_sweep_LANG/; at the end the summary is closed (field reached = no crash)."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from em import EM
import expect

lang = sys.argv[1]
lo, hi = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else (1, 649)
cases = []
for sp in range(lo, hi + 1):
    cases.append((sp, 0))
    d = expect._pers[sp]
    for f in range(1, d[0x20]):
        cases.append((sp, f))
q = EM(f'em_sweep_{lang}', lang)
q.boot_continue()
q.open_summary()
q.tap('RIGHT'); q.step(60)
q.tap('RIGHT'); q.step(90)
q.check('our page', q.dbg()['shown'], 1)
slot, bad, n = 0, 0, 0
for sp, form in cases:
    other = 1 - slot
    q.q2(2, other, 0x05, sp)
    q.q2(2, other, 0x6F, form)
    c0 = q.dbg()['creates']
    q.tap('DOWN' if other == 1 else 'UP', 1, 2)
    for _ in range(60):
        q.step(2)
        d = q.dbg()
        if d['creates'] != c0 and d['shown']:
            break
    slot = other
    n += 1
    ok = (d['species'], d['form']) == (sp, form) and d['fam'] == expect.family(sp) and \
        list(zip(d['learn_lv'], d['learn_mv'])) == expect.learnset(sp, form) and d['overflow'] == 0 and d['lines'] <= 8
    if not ok:
        bad += 1
        q.check(f'{sp}:{form}', (d['species'], d['form'], d['fam'], d['overflow'], d['lines']),
                (sp, form, expect.family(sp), 0, d['lines']))
        q.snap(f'bad_{sp}_{form}')
    elif form or sp % 40 == 0:
        q.step(6)
        q.snap(f'sp{sp}_{form}')
q.say('checked', n, 'bad', bad)
q.check('all species', bad, 0)
q.check('field after closing', q.close_summary(), True)
q.result()
q.sheet(cols=10)
