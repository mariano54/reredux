"""t_nuz.py LANG [MODE] : Nuzlocke edge cases on the QA2 ROM from qa2_LANG_nuz_bedroom (release + graveyard).
MODE revive (default): lead Lillipup Lv3 holding Leftovers + the kit's 2 Dragonite; a wild Lv40 Watchog knocks the
  Lillipup out; Dragonite comes in; a Revive from the Bag revives the Lillipup in the battle; run away. Strict
  marking: Lillipup is still released (to the graveyard box) after the battle, its Leftovers go to the Bag,
  deaths + 1. Also: rules_dbg.faint_marks counts the faint.
MODE egg: a script egg (PokePartyAddEgg) hatched with CallEggHatch; NO at the nickname question -> name entry
  (always nickname); species check.
Shots build/qa2/nuz_LANG_MODE/."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qa2 import Q2, FLAGS, V_DEATHS

lang = sys.argv[1]
mode = sys.argv[2] if len(sys.argv) > 2 else 'revive'
q = Q2(f'nuz_{lang}_{mode}', lang)
q.load('nuz_bedroom')
q.step(10)
for f in ('dupes', 'first', 'noitems', 'statics'):
    q.setflag(FLAGS[f], 0)
party = lambda: [p[0] for p in q.tst()['party']]
LEFTOVERS, REVIVE = 234, 28

if mode == 'egg':
    q.check('nickname rule on', q.flag(FLAGS['nick']), 1)
    q.bed('KIT')
    q.step(200)
    q.wait_free(2000, tap='B')
    q.script(['    PokePartyAddEgg 0x8020, 504, 0'])
    q.check('egg in slot 2', (q.pparam(2, 5), q.pparam(2, 0x4C)), (504, 1))
    q.set_pparam(2, 9, 0)                    # egg cycles left = 0: ready to hatch
    q.script(['    WorkSetConst 0x8020, 0', '    CallEggHatch 0x8020'], wait=False)
    n0 = q.dbg()['nick_forced']
    s = None
    for i in range(240):
        q.step(10)
        if i % 12 == 0:
            q.snap(f'hatch_{i:03d}')
        if q.field_yesno() or q.ui() == 'yesno':
            s = 'yesno'
            break
        if i % 9 == 8:
            q.tap('A', idle=2)
    q.snap('nick_question')
    q.check('hatch: nickname question', s, 'yesno')
    q.step(40)
    q.tap('DOWN')
    q.step(30)
    q.snap('nick_no_selected')
    q.tap('A')                               # NO
    s = None
    for i in range(40):
        q.step(15)
        if i % 4 == 0:
            q.snap(f'after_no_{i:02d}')
        if q.ui() == 'name':
            s = 'name'
            break
    q.snap('name_entry')
    q.check('NO -> name entry anyway (nick_forced + 1)', (q.dbg()['nick_forced'] - n0, s), (1, 'name'))
    q.name_entry()
    q.wait_free(3000, tap='B')
    q.snap('end')
    q.check('hatched Patrat in the party', party(), [149, 149, 504])
    q.check('not an egg any more', q.pparam(2, 0x4C), 0)
    q.check('nicknamed (PF_HasNickname)', q.pparam(2, 0x75), 1)
    q.result()
    q.sheet(both=True)
    sys.exit()

q.script(['    PokePartyAddEx 0x8020, 506, 0, 3, 0, 0, 0, 234, 4'])
q.bed('KIT')
q.step(200)
q.wait_free(2000, tap='B')
q.script([f'    ItemAdd {REVIVE}, 3, 0x8020'])
q.check('party: Lillipup lead + 2 Dragonite', party(), [506, 149, 149])
q.check('Lillipup holds Leftovers', q.pparam(0, 6), LEFTOVERS)
bag0 = q.q2(6, LEFTOVERS)
t0 = q.tst()
d0, e0 = q.dbg(), q.dbg2()
deaths0 = q.var(V_DEATHS)
q.check('battle', q.wild(505, 40), True)
q.snap('battle')
fainted = False
for k in range(8):
    if q.ui() == 'menu':
        q.fight(0)
    for i in range(80):
        q.step(10)
        if q.dbg2()['faint_marks'] > e0['faint_marks']:
            fainted = True
        s = q.ui()
        if s in ('menu', 'yesno'):
            break
        if i % 6 == 5:
            q.tap('A', idle=8)
    q.snap(f'turn{k}')
    if fainted:
        break
q.check('Lillipup fainted: marked', fainted, True)
# "Use next Pokémon?" (wild battle) -> YES -> party list -> Dragonite
for i in range(40):
    s = q.ui()
    if s == 'yesno':
        q.touch(128, 66)                     # YES
        q.step(60)
        q.snap('next_yes')
        break
    q.step(15)
q.snap('party_list')
q.touch(190, 30)                             # second slot (Dragonite)
q.step(40)
q.snap('party_pick')
q.touch(128, 100)                            # SHIFT / Send out
q.step(60)
q.snap('party_shift')
q.check('Dragonite out: battle menu', q.until({'menu'}, 3000, tap='B'), 'menu')
q.snap('menu_dragonite')
# Bag -> Status restore -> Revive -> USE -> Lillipup
q.touch(40, 165)
q.step(60)
q.touch(65, 115)
q.step(60)
q.snap('bag_status')
q.touch(65, 30)
q.step(60)
q.snap('revive_item')
q.touch(128, 175)
q.step(90)
q.snap('revive_target')
q.touch(190, 30)                             # Lillipup (the battle order: Dragonite first)
q.step(120)
q.snap('revive_used')
for i in range(30):
    if q.ui() == 'menu':
        break
    q.tap('A', idle=20)
q.snap('after_revive')
q.check('Revive used (Bag 3 -> 2)', q.q2(6, REVIVE), 2)
q.check('ran', q.run_away('run'), True)
t1, d1, e1 = q.tst(), q.dbg(), q.dbg2()
q.say('after battle: party', t1['party'], 'grave', t1['grave'], 'deaths', q.var(V_DEATHS), e1)
q.check('revived Lillipup still released (strict): party', party(), [149, 149])
q.check('... to the graveyard box', t1['grave'] - t0['grave'], 1)
q.check('deaths + 1', q.var(V_DEATHS) - deaths0, 1)
q.check('its Leftovers went to the Bag', (q.q2(6, LEFTOVERS) - bag0, e1['items_saved'] - e0['items_saved']), (1, 1))
q.snap('field')
q.result()
q.sheet(both=True)
