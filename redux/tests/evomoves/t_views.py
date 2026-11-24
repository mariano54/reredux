"""t_views.py LANG [SPECIES[:FORM[:LEVEL]] ..] : party summary on the EVO/MOVES page for a list of species (written into
party slot 1 through the q2tst mailbox, then DOWN onto it), a screenshot of each; checks the page's family and learnset
against the named tree. Default list: the README's showcase (simple, stone, branching, non-evolvers, forms, places)."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from em import EM
import expect

lang = sys.argv[1]
DEFAULT = ['4:0:20', '25:0:30', '133:0:20', '236:0:15', '265:0:5', '79:0:30', '412:0:20', '458:0:20', '588:0:20',
           '349:0:20', '290:0:20', '82:0:40', '447:0:20', '281:0:25', '128:0:30', '386:1:50', '479:2:30', '150:0:70',
           '366:0:20', '43:0:20']
specs = sys.argv[2:] or DEFAULT
q = EM(f'em_views_{lang}', lang)
q.boot_continue()
q.open_summary()
q.tap('RIGHT'); q.step(60)
q.tap('RIGHT'); q.step(90)
q.check('our page', q.dbg()['shown'], 1)
for s in specs:
    sp, form, lv = (list(map(int, s.split(':'))) + [0, 0])[:3]
    q.q2(2, 1, 0x05, sp)
    q.q2(2, 1, 0x6F, form)
    if lv:
        q.q2(2, 1, 0x9E, lv)
    q.tap('DOWN'); q.step(70)
    d = q.dbg()
    q.snap(f'sp{sp}_{form}')
    fam, learn = expect.family(sp), expect.learnset(sp, form)
    q.check(f'{sp}:{form} species/form shown', (d['species'], d['form']), (sp, form))
    q.check(f'{sp}:{form} family', d['fam'], fam)
    q.check(f'{sp}:{form} learnset', list(zip(d['learn_lv'], d['learn_mv'])), learn)
    q.check(f'{sp}:{form} fits', (d['overflow'], d['lines'] <= 8), (0, True))
    q.say('lines', d['lines'], 'next', d['next'], 'scroll', d['scroll'])
    q.tap('UP'); q.step(70)
q.check('field after closing', q.close_summary(), True)
q.result()
q.sheet()
