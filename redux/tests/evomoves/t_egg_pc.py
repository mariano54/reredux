"""t_egg_pc.py LANG : the EVO/MOVES page with an Egg in the party and in the PC Box summary.
Egg: party slot 1 becomes an Egg (q2tst); the lead's summary -> EVO/MOVES -> DOWN skips the Egg (the page stays the
lead's); the Egg's own summary: RIGHT never reaches the page. PC: Purrloin (slot 1) is deposited at the Pokémon
Center's PC and its Box summary is opened (statview's t_pc route) -> RIGHT RIGHT -> EVO/MOVES for the Box Pokémon,
A (list) / DOWN / B, LEFT back, B out."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from em import EM
import expect

lang = sys.argv[1]
q = EM(f'em_eggpc_{lang}', lang)
q.boot_continue()
# --- Egg ---
q.q2(2, 1, 0x4C, 1)
q.check('slot 1 is an Egg', q.q2(1, 1, 0x4C), 1)
q.open_summary()
q.tap('RIGHT'); q.step(60)
q.tap('RIGHT'); q.step(90)
d = q.dbg()
q.check('lead: our page', (d['shown'], d['species']), (1, 498))
c0 = d['creates']
q.tap('DOWN'); q.step(90)
q.snap('egg_skipped')
d = q.dbg()
q.check('DOWN skips the Egg: still the lead, not redrawn', (d['shown'], d['species'], d['creates']), (1, 498, c0))
q.tap('B'); q.step(90)
q.touch(190, 30); q.step(60)            # the Egg's slot
q.tap('A'); q.step(90)
q.tap('A'); q.step(150)
q.snap('egg_summary')
r0 = q.dbg()['rights']
for k in ('RIGHT', 'RIGHT', 'RIGHT'):
    q.tap(k); q.step(60)
q.snap('egg_right')
d = q.dbg()
q.check('Egg summary: RIGHT never reaches the page', (d['shown'], d['rights']), (0, r0))
q.check('field after the Egg', q.close_summary(), True)
q.q2(2, 1, 0x4C, 0)
# --- PC ---
q.check('at the PC', q.goto(4, 12), True)
q.face('UP')
seq = ('A,wait:120,A,A,wait:60,RIGHT,A,A,wait:60,A,wait:60,B,wait:60,B,wait:150,DOWN,wait:20,'
       'A,wait:120,A,DOWN,A,wait:150,RIGHT,wait:30,RIGHT,wait:60')
for it in seq.split(','):
    if it.startswith('wait:'):
        q.step(int(it[5:]))
        continue
    q.tap(it)
    q.step(40)
    q.snap(it)
d = q.dbg()
q.say('pc page', d)
q.check('Box summary: EVO/MOVES of the Box Pokémon', (d['shown'], d['species'], d['fam']),
        (1, 509, expect.family(509)))
q.check('Box summary: learnset', list(zip(d['learn_lv'], d['learn_mv'])), expect.learnset(509))
q.tap('A'); q.step(40)
q.tap('DOWN'); q.step(40)
q.snap('pc_list')
q.check('Box summary: list cursor', (q.dbg()['listmode'], q.dbg()['flushes'] >= 2), (1, True))
q.tap('B'); q.step(40)
q.tap('LEFT'); q.step(90)
q.snap('pc_stats')
q.check('LEFT: back to STATS', q.dbg()['shown'], 0)
for _ in range(6):
    q.tap('B')
    q.step(40)
q.check('field after the PC', q.wait_field(3000, tap='B', settle=30), True)
q.result()
q.sheet()
