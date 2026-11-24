"""t_dexsweep.py LANG [FIRST LAST] : every species (default 1-649) on the Pokédex's EVO/MOVES page: all species registered
as caught (q2tst cmd 7), the Pokédex opened on the first entry, LEFT onto EVO/MOVES; then for each species the next
entry of the Pokédex's species list (the module context's list: +0x18 array, +0x1C count, +0x20 index pointer) is set
to it and DOWN shows it: its family and learnset checked against the ROM data (expect.py); shots of every 50th and the
showcase species; the Pokédex closed at the end (field reached = no crash)."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from em import EM
import expect

lang = sys.argv[1]
lo, hi = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else (1, 649)
q = EM(f'em_dexsweep_{lang}', lang)
DX = q.sym_addr('dx_dbg')


def dx():
    r8, r16 = q.r8, q.r16
    d = dict(state=r8(DX + 4), shown=r8(DX + 6), pending=r8(DX + 7), species=r16(DX + 8), lines=r8(DX + 13))
    for i, n in enumerate('inits exits injects switches redraws scrolls inputs bars last_action overflow caps caught'
                          .split()):
        d[n] = r16(DX + 14 + 2 * i)
    d['ctx'] = q.r32(DX + 40)
    return d


q.boot_continue()
T = q.T
q.w32(T + 8, 1); q.w32(T + 12, 649); q.w32(T + 4, 7)
for _ in range(600):
    q.step(1)
    if not q.r32(T + 4):
        break
q.check('species 1-649 caught', (q.r32(T + 4), q.r32(T + 20)), (0, 649))
q.tap('X'); q.step(40); q.touch(192, 48); q.step(400)
q.touch(28, 137); q.step(90)
for _ in range(3):
    q.tap('UP', 1, 4)
q.step(30)
q.tap('A'); q.step(200)
q.snap('entry')
q.tap('LEFT'); q.step(150)
q.snap('ours')
d = dx()
q.check('our page', (d['shown'], d['state'], d['caught']), (1, 3, 1))
ctx = d['ctx']
lst, count, idxp = q.r32(ctx + 0x18), q.r16(ctx + 0x1C), q.r32(ctx + 0x20)
q.say('list', hex(lst), 'count', count, 'index ptr', hex(idxp))
bad = 0
for sp in range(lo, hi + 1):
    i = q.r16(idxp)
    nxt = (i + 1) % count
    q.w16(lst + 2 * nxt, sp)
    r0 = dx()['redraws']
    q.tap('DOWN', 1, 2)
    for _ in range(80):
        q.step(2)
        d = dx()
        if d['redraws'] != r0 and not d['pending']:
            break
    e = q.dbg()
    ok = (d['species'] == sp and d['shown'] == 1 and d['caught'] == 1 and e['fam'] == expect.family(sp) and
          list(zip(e['learn_lv'], e['learn_mv'])) == expect.learnset(sp) and d['overflow'] == 0 and d['lines'] <= 9)
    if not ok:
        bad += 1
        q.check(f'species {sp}', (d['species'], d['shown'], d['caught'], e['fam'], d['overflow'], d['lines']),
                (sp, 1, 1, expect.family(sp), 0, d['lines']))
        q.snap(f'bad_{sp}')
    elif sp % 50 == 0 or sp in (25, 133, 236, 265, 290, 412, 458, 649):
        q.step(6)
        q.snap(f'sp{sp}')
    q.step(24)
q.say('checked', hi - lo + 1, 'bad', bad)
q.check('every species', bad, 0)
q.tap('B'); q.step(150)
q.tap('B'); q.step(150)
q.check('field after the Pokédex', q.wait_field(3000, tap='B', settle=30), True)
q.result()
q.sheet(cols=8)
