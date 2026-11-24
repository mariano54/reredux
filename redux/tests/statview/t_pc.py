"""t_pc.py LANG [SEQ] : PC summary on the statview test ROM: smoke battery save (Pokémon Center), Bidoof (slot 1) gets
known IVs/EVs (q2tst), walk to the PC (4, 12), then SEQ (comma list: KEY, KEY*N, wait:N, touch:X:Y), a both-screens
shot after each item; sv_dbg logged. Default SEQ deposits Bidoof, then opens its summary from the Box."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sv import SV, B

lang = sys.argv[1]
q = SV(f'sv_pc_{lang}', f'{B}/out/sv_{lang}.nds', f'sv_{lang}', f'{B}/statview_integ/dsv/rel_{lang}_smoke_{lang}.dsv',
       elf=f'{B}/redux3/{lang}_follow.elf')
T = q.sym_addr('q2tst')
D = q.sym_addr('sv_dbg')
IV = [5, 10, 20, 25, 30, 31]        # HP Atk Def Spe SpA SpD
EV = [100, 0, 50, 0, 0, 4]
ROW = [0, 1, 2, 4, 5, 3]


def q2(cmd, a=0, b=0, c=0):
    q.w32(T + 8, a); q.w32(T + 12, b); q.w32(T + 16, c); q.w32(T + 4, cmd)
    q.step(3)
    assert q.r32(T + 4) == 0, 'q2tst not run'
    return q.r32(T + 20)


def dbg():
    return q.svdbg()


q.boot_continue()
V0 = q.r32(q.sym_addr('rules_dbg') + 52)        # rules_dbg.views (SELECT settings view in the field)
for i in range(6):
    q2(2, 1, 0x0D + i, 0)
for i in range(6):
    q2(2, 1, 0x46 + i, IV[i])
    q2(2, 1, 0x0D + i, EV[i])
q.say('slot 1 IVs', [q2(1, 1, 0x46 + i) for i in range(6)], 'EVs', [q2(1, 1, 0x0D + i) for i in range(6)])
q.say('pos', q.pos())
q.check('at the PC', q.goto(4, 12), True)
q.face('UP')
seq = sys.argv[2] if len(sys.argv) > 2 else ('A,wait:120,A,A,wait:60,RIGHT,A,A,wait:60,A,wait:60,B,wait:60,B,wait:150,DOWN,wait:20,'
                                            'A,wait:120,A,DOWN,A,wait:150,RIGHT,wait:30,SELECT,wait:30,SELECT,wait:30,'
                                            'SELECT,wait:30,B,wait:60')
log = []
for it in seq.split(','):
    if it.startswith('wait:'):
        q.step(int(it[5:]))
        continue
    if it.startswith('touch:'):
        _, x, y = it.split(':')
        q.touch(int(x), int(y))
    else:
        k, _, n = it.partition('*')
        q.tap(k, int(n or 1))
    q.step(40)
    q.snap(it.replace(':', '_').replace('*', 'x'))
    q.say(it, dbg())
    log.append((it, dbg()))
q.say('expect rows', [IV[i] for i in ROW], [EV[i] for i in ROW])
if len(sys.argv) <= 2:
    sel = [d for it, d in log if it == 'SELECT']
    st = [d for it, d in log if it == 'RIGHT'][-1]
    hpt = sum((IV[i] & 1) << i for i in range(6)) * 15 // 63 + 1
    q.check('Box summary stats page: IV / EV columns',
            (st['mode'], st['ivs'], st['evs'], st['iv_total'], st['ev_total'], st['hp_type'], st['rows']),
            (0, [IV[i] for i in ROW], [EV[i] for i in ROW], sum(IV), sum(EV), hpt, 6))
    q.check('Box summary SELECT x3: totals / ability / totals', [d['mode'] for d in sel], [1, 0, 1])
    q.check('Box summary totals keep the values', (sel[2]['ivs'], sel[2]['evs']), ([IV[i] for i in ROW], [EV[i] for i in ROW]))
    for _ in range(6):
        q.tap('B')
        q.step(40)
    q.check('field after the PC', q.wait_field(3000, tap='B', settle=30), True)
    q.check('Box summary SELECT: no settings view', q.r32(q.sym_addr('rules_dbg') + 52), V0)
    q.snap('field')
    q.result()
q.sheet()
