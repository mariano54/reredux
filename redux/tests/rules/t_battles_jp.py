"""t_battles_jp.py [LANG] : the rules in battle without registering a new Pokedex species (the JP build hangs on the
dex-registration screen of a new catch, a jp_port issue). From LANG_test_bedroom.dst (all rules on, graveyard,
statics count), rules_LANG_rules_test.nds:
 1 kit; gift Patrat: no yes/no, straight to the name entry (always nickname)
 2 Patrat (dupe): Potion refused (no items), ball refused (dupes)                 -> run
 3 Lillipup (1st in area 117): no block, area marked                               -> run
 4 Lillipup again: ball refused (area)                                            -> run
 5 shiny Patrat: shiny clause, no block; clause off -> dupe block                 -> run
 6 dupes + first-catch off: Patrat caught (no dex screen), "nickname?" NO -> name entry
 7 trainer Robert: item denied, win
 8 graveyard (slot fainted before a battle) / 9 release
10 Route 19 grass: random encounter; game over (1-HP lead, Growl) -> bank 42 line 4 -> reset
Screens: build/rules/out/bjp_LANG/, sheet bjp_LANG_sheet2.png."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, subprocess, sys
from tcommon import T, F
lang = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('-') else 'jp'
t = T(lang, f'bjp_{lang}')
TXT = {k: v[2] for k, v in t.texts.items()}
t.load(f'{lang}_test_bedroom')

t.bed('KIT')
t.step(200)
t.wait_free(2000, tap='B')
t.check('kit', [p[0] for p in t.tst()['party']], [149, 149])
t.bed('GIFT')
s = t.until({'name', 'yesno'}, 1500)
t.snap('gift_name_entry')
t.check('gift: name entry without the yes/no', s, 'name')
t.name_entry()
t.wait_free(2000, tap='B')
t.check('gift Patrat in the party', t.tst()['party'][-1][0], 504)

t.bed('PATRAT')
t.until({'menu'}, 3000)
d = t.dbg()
t.check('Patrat (gifted): dupe block, area not used', (d['last_block'], 117 in t.areas()), (2, False))
t.bag_use('hp', 0, 'potion_refused')
t.check('Potion refused (no items)', t.dbg()['last_refuse_msg'], TXT['RULES_NO_ITEMS'])
t.bag_close()
t.bag_use('balls', 0, 'dupe_refused')
t.check('ball refused (dupes)', t.dbg()['last_refuse_msg'], TXT['RULES_CATCH_DUPE'])
t.bag_close()
t.check('ran', t.run_away(), True)

t.bed('LILLIPUP')
t.until({'menu'}, 3000)
d = t.dbg()
t.check('Lillipup: first in the area', (d['last_block'], 117 in t.areas()), (0, True))
t.run_away()
t.bed('LILLIPUP')
t.until({'menu'}, 3000)
t.check('Lillipup again: area block', t.dbg()['last_block'], 1)
t.bag_use('balls', 0, 'area_refused')
t.check('ball refused (area)', t.dbg()['last_refuse_msg'], TXT['RULES_CATCH_AREA'])
t.bag_close()
t.run_away()

t.bed('SHINY')
t.until({'menu'}, 3000)
t.snap('shiny')
d = t.dbg()
t.check('shiny Patrat: shiny clause, no block', (d['last_shiny'], d['last_block']), (1, 0))
t.run_away()
t.set_flag(F['shiny'], 0)
t.bed('SHINY')
t.until({'menu'}, 3000)
d = t.dbg()
t.check('shiny clause off: dupe block', (d['last_shiny'], d['last_block']), (1, 2))
t.run_away()
t.set_flag(F['shiny'], 1)

if '--catch' in sys.argv:      # the JP post-catch proc (ov297) hangs until jp_port is fixed
    t.set_flag(F['dupes'], 0)
    t.set_flag(F['first'], 0)
    t.bed('PATRAT')
    t.until({'menu'}, 3000)
    t.bag_use('balls', 0, 'catch')
    t.check('nickname question', t.until({'yesno'}, 3000), 'yesno')
    t.snap('nick_question')
    t.touch(128, 115)                              # NO
    t.step(10)
    s = t.until({'name'}, 600, tap=None)
    t.snap('name_entry_after_no')
    t.check('always nickname: name entry after NO', (s, t.dbg()['nick_forced'] >= 1), ('name', True))
    t.name_entry()
    t.wait_free(3000, tap='B')
    t.check('caught', [p[0] for p in t.tst()['party']], [149, 149, 504, 504])
    t.set_flag(F['dupes'], 1)
    t.set_flag(F['first'], 1)

d0 = t.dbg()['trainer_items_denied']
t.bed('TRAINER')
t.check('trainer battle', t.until({'menu'}, 4000), 'menu')
t.check('trainer item denied', t.dbg()['trainer_items_denied'] - d0, 1)
t.snap('trainer')
t.fight(0)
t.wait_free(4000, tap='B')

tst0 = t.tst()
t.test_cmd(1, 0, 0)
t.bed('PATRAT')
t.until({'menu'}, 3000)
t.run_away()
tst = t.tst()
t.check('graveyard: party-1, box+1, deaths+1',
        (tst['party_count'] - tst0['party_count'], tst['grave'] - tst0['grave'], tst['deaths'] - tst0['deaths']), (-1, 1, 1))
tst0 = tst
t.set_flag(F['grave'], 0)
t.test_cmd(1, 1, 0)
t.bed('PATRAT')
t.until({'menu'}, 3000)
t.run_away()
tst = t.tst()
t.check('release: party-1, box same, deaths+1',
        (tst['party_count'] - tst0['party_count'], tst['grave'] - tst0['grave'], tst['deaths'] - tst0['deaths']), (-1, 0, 1))
t.set_flag(F['grave'], 1)
t.save(f'{lang}_bjp9')

t.bed('ROUTE')
t.wait_free(2000)
t.goto(60, 695)
n = t.tst()['party_count']
for i in range(1, n):
    t.test_cmd(1, i, 0)
t.test_cmd(1, 0, 1)
w0 = t.dbg()['wild_starts']
for i in range(600):
    t.hold('RIGHT' if (i // 2) % 2 else 'LEFT', 16)
    t.step(4)
    if t.dbg()['wild_starts'] > w0:
        break
d = t.dbg()
t.check('Route 19 random encounter (not static)', (d['wild_starts'] > w0, d['last_static'], d['last_area']), (True, 0, 124))
t.until({'menu'}, 3000)
t.snap('route19')
seen = 0
for k in range(600):
    if t.dbg()['lose_kind'] == 3:
        seen = 1
        break
    if t.gsys() == 0:
        break
    if k % 4 == 0 and t.ui() == 'menu':
        t.fight(1)
    elif k % 4 == 2:
        t.tap('B', idle=4)
    else:
        t.step(10)
shots = 0
for i in range(200):
    if t.gsys() == 0 or t.dbg()['lose_kind'] != 3:
        break
    if i % 6 == 0 and shots < 16:
        t.snap(f'gameover{shots:02d}')
        shots += 1
    t.step(20)
    if i % 15 == 14:
        t.tap('A')
t.step(400)
t.snap('after_reset')
t.check('game over: kind 3, then reset', (seen, t.gsys()), (1, 0))
t.finish()
subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sheet2.py'), t.dir,
                os.path.join(os.path.dirname(t.dir), f'bjp_{lang}_sheet2.png')])
