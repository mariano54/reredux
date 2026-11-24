"""t_party.py LANG [ROM TAG] : party summary on the statview test ROM (statview + qol2_test) with the smoke battery
save (Tepig + Bidoof, Pokémon Center). ReRedux layout: IV and EV columns right of the stats, SELECT toggles the Ability
box (ability <-> totals). Known IVs/EVs are written into the lead with PokeParty_SetParam (q2tst mailbox), then:
summary (info page: SELECT does nothing) -> stats page (IV / EV columns: sv_dbg values vs the game's getter, ink in
both columns of every row) -> SELECT (totals) -> DOWN (Bidoof: its values, totals kept) -> SELECT (ability) ->
SELECT (totals) -> UP -> LEFT/RIGHT (page change keeps the box) -> A / B (moves) -> SELECT (ability) -> B out."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sv import SV, B

lang = sys.argv[1]
rom = sys.argv[2] if len(sys.argv) > 2 else f'{B}/out/sv_{lang}.nds'
tag = sys.argv[3] if len(sys.argv) > 3 else f'sv_{lang}'
q = SV(f'sv_party_{lang}', rom, tag, f'{B}/statview_integ/dsv/rel_{lang}_smoke_{lang}.dsv')
T = q.sym_addr('q2tst')
IV = [31, 0, 15, 30, 1, 7]          # HP Atk Def Spe SpA SpD (param order)
EV = [252, 6, 0, 252, 0, 0]
ROW = [0, 1, 2, 4, 5, 3]            # summary row order HP Atk Def SpA SpD Spe -> param index
ROW_Y = [32, 56, 72, 88, 104, 120]  # top of each row's window (screen y)
IV_X, EV_X = (186, 205), (216, 243)  # IV / EV column rects (screen x)


def q2(cmd, a=0, b=0, c=0):
    q.w32(T + 8, a); q.w32(T + 12, b); q.w32(T + 16, c); q.w32(T + 4, cmd)
    q.step(3)
    assert q.r32(T + 4) == 0, 'q2tst not run'
    return q.r32(T + 20)


def ivs(slot):
    return [q2(1, slot, 0x46 + i) for i in range(6)]


def evs(slot):
    return [q2(1, slot, 0x0D + i) for i in range(6)]


def rows(v):
    return [v[i] for i in ROW]


def hp_type(iv):
    return sum((iv[i] & 1) << i for i in range(6)) * 15 // 63 + 1


def columns_inked():
    """every row has text in its IV and EV columns"""
    return all(q.ink(IV_X[0], y + 2, IV_X[1], y + 15) > 5 and q.ink(EV_X[0], y + 2, EV_X[1], y + 15) > 5 for y in ROW_Y)


def page(d, iv, ev):
    return (d['ivs'], d['evs'], d['iv_total'], d['ev_total'], d['hp_type'], d['rows'])


def want(iv, ev):
    return (rows(iv), rows(ev), sum(iv), sum(ev), hp_type(iv), 6)


q.boot_continue()
q.check('sv_dbg magic', q.svdbg()['magic'], 0x57565453)
for i in range(6):
    q2(2, 0, 0x0D + i, 0)               # the setter keeps the EV total <= 510
for i in range(6):
    q2(2, 0, 0x46 + i, IV[i])
    q2(2, 0, 0x0D + i, EV[i])
q2(2, 0, 0x70, 3)                       # Adamant: Attack red, Sp. Atk blue
q.check('lead IVs written', ivs(0), IV)
q.check('lead EVs written', evs(0), EV)
q2(2, 1, 0xA1, 714)                     # second Pokémon: 3-digit HP (widest "cur/max") and Attack
q2(2, 1, 0xA0, 699)
q2(2, 1, 0xA2, 459)
iv1, ev1 = ivs(1), evs(1)
q.say('slot 1 IVs', iv1, 'EVs', ev1, 'HP', q2(1, 1, 0xA0), '/', q2(1, 1, 0xA1), 'Atk', q2(1, 1, 0xA2))
q.tap('X'); q.step(40); q.touch(64, 48); q.step(90)
q.tap('A'); q.step(90); q.tap('A'); q.step(90); q.tap('A'); q.step(150)
q.snap('info')
d = q.svdbg()
q.check('app init: the ability', (d['mode'], d['inits'] >= 1), (0, True))
q.tap('SELECT'); q.step(40)
q.check('SELECT on the info page: nothing', q.svdbg()['toggles'], 0)
q.tap('RIGHT'); q.step(60)
q.snap('stats')
d = q.svdbg()
q.check('stats page: IV / EV values (summary order), totals, Hidden Power', page(d, IV, EV), want(IV, EV))
q.check('stats page: the ability in the box', d['mode'], 0)
q.check('stats page: IV and EV columns printed in every row', columns_inked(), True)
q.tap('SELECT'); q.step(60)
q.snap('totals')
d = q.svdbg()
q.check('SELECT: totals', (d['mode'], d['toggles']), (1, 1))
q.check('totals page keeps the columns', (page(d, IV, EV), columns_inked()), (want(IV, EV), True))
q.tap('DOWN'); q.step(60)
q.snap('totals_next')
d = q.svdbg()
q.check('next Pokémon: its IVs / EVs, totals kept', (d['mode'], page(d, iv1, ev1)), (1, want(iv1, ev1)))
q.tap('SELECT'); q.step(60)
q.snap('ability_next')
q.check('SELECT -> the ability', q.svdbg()['mode'], 0)
q.tap('SELECT'); q.step(60)
q.snap('totals_next2')
q.check('SELECT -> totals again', q.svdbg()['mode'], 1)
q.tap('UP'); q.step(60)
q.tap('LEFT'); q.step(60)
q.snap('info_again')
q.tap('RIGHT'); q.step(60)
q.snap('totals_after_pages')
d = q.svdbg()
q.check('totals kept across pages, lead values', (d['mode'], page(d, IV, EV)), (1, want(IV, EV)))
q.tap('A'); q.step(60)
q.snap('moves_select')
q.tap('B'); q.step(60)
q.snap('moves_back')
q.tap('SELECT'); q.step(60)
q.snap('ability_again')
q.check('back to the ability', q.svdbg()['mode'], 0)
for _ in range(4):
    q.tap('B'); q.step(40)
q.check('field after closing', q.wait_field(2000, tap='B', settle=30), True)
q.snap('field')
q.result()
q.sheet()
