"""t_dex.py LANG : the Pokédex entry's EVO/MOVES page: list -> entry (INFO) -> LEFT (ours) -> RIGHT (INFO) -> RIGHT x4
(AREA, CRY, FORMS, ours) -> R / L (scroll) -> touch the arrows -> DOWN (next species) -> touch INFO -> B (list) -> B"""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from em import EM
import expect

lang = sys.argv[1]
q = EM(f'em_dex_{lang}', lang)
DX = q.sym_addr('dx_dbg')


def dx():
    r8, r16 = q.r8, q.r16
    d = dict(magic=q.r32(DX), state=r8(DX + 4), end=r8(DX + 5), shown=r8(DX + 6), pending=r8(DX + 7),
             species=r16(DX + 8), nlearn=r8(DX + 10), scroll=r8(DX + 11), nfam=r8(DX + 12), lines=r8(DX + 13))
    for i, n in enumerate('inits exits injects switches redraws scrolls inputs bars last_action overflow caps'.split()):
        d[n] = r16(DX + 14 + 2 * i)
    return d


q.boot_continue()
q.tap('X'); q.step(40); q.touch(192, 48); q.step(150)
q.snap('list')
q.tap('A'); q.step(90); q.tap('A'); q.step(150)
q.snap('info')
q.tap('LEFT'); q.step(150)
q.snap('evo_from_info')
d = dx()
q.say('dx', d, 'em', q.dbg()['fam'])
q.check('LEFT on INFO: our page', (d['shown'], d['state']), (1, 3))
q.check('our page: species, family, learnset', (d['species'], q.dbg()['fam'], list(zip(q.dbg()['learn_lv'], q.dbg()['learn_mv']))),
        (d['species'], expect.family(d['species']), expect.learnset(d['species'])))
q.tap('RIGHT'); q.step(150)
q.snap('info_from_evo')
q.check('RIGHT on ours: INFO', dx()['shown'], 0)
for k in range(4):
    q.tap('RIGHT'); q.step(150)
    q.snap(f'right{k}')
q.check('RIGHT x4 from INFO: ours', (dx()['shown'], dx()['state']), (1, 3))
q.tap('R'); q.step(40)
q.snap('scroll_r')
q.say('after R', dx())
q.tap('L'); q.step(40)
q.snap('scroll_l')
q.touch(236, 14); q.step(40)
q.snap('touch_down_arrow')
q.say('after touch', dx())
s0 = dx()['species']
q.tap('DOWN'); q.step(60)
q.snap('next_species')
q.check('DOWN: another species on our page', (dx()['species'] != s0, dx()['shown']), (True, 1))
q.touch(54, 180); q.step(150)
q.snap('touch_info')
q.check('touch INFO: INFO', dx()['shown'], 0)
q.touch(182, 180); q.step(150)
q.snap('touch_evo')
q.check('touch the EVO capsule: ours', (dx()['shown'], dx()['state']), (1, 3))
q.touch(150, 180); q.step(150)
q.snap('touch_forms')
q.check('touch FORMS: not ours', dx()['shown'], 0)
q.tap('Y'); q.step(40)
q.snap('checkbox_y')
q.tap('Y'); q.step(40)
q.touch(210, 182); q.step(40)
q.snap('checkbox_touch')
q.touch(210, 182); q.step(40)
q.tap('LEFT'); q.step(150)
q.tap('B'); q.step(150)
q.snap('back_list')
q.tap('B'); q.step(150)
q.check('field after the Pokédex', q.wait_field(3000, tap='B', settle=30), True)
q.say('dx end', dx())
q.result()
q.sheet()
