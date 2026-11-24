"""t_battles.py LANG [FROM] : the rules in battle, from build/rules/out/LANG_test_bedroom.dst (t_menu.py LANG
test: all rules on, graveyard, statics count) on build/rules/rules_LANG_rules_test.nds.

 1 kit (2x Dragonite Lv60, balls, Potions)
 2 Patrat (area 117 first encounter): Potion refused (no items), Master Ball catch, "nickname?" NO ->
   name entry anyway (always nickname)
 3 Patrat again: ball refused (dupes clause)                       -> run
 4 Lillipup (new species, area used): ball refused (area)        -> run
 5 shiny Patrat: shiny clause -> no block, caught (nickname YES)
 6 shiny clause off: shiny Patrat blocked (dupe)                  -> run
 7 trainer Robert (Hyper Potion): item denied, win
 8 graveyard: slot 0 fainted (HP 0) before a battle, win -> slot 0 to the last box
 9 release: graveyard off, slot 0 fainted -> released (box unchanged)
10 gift: no yes/no, straight to the name entry
11 Route 19 grass: random encounter (not static), area 124 marked; 2nd encounter blocked
12 game over: one able Pokemon at 1 HP using Growl -> whiteout -> bank 42 line 4 -> title
Screens: build/rules/out/battles_LANG/, sheet battles_LANG_sheet2.png (both screens)."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, subprocess, sys
from tcommon import T, F
lang = sys.argv[1]
start = int(sys.argv[2]) if len(sys.argv) > 2 else 1
t = T(lang, f'battles_{lang}')
tx = t.texts
TXT = {k: v[2] for k, v in tx.items()}
t.say('texts', {k: TXT[k] for k in ('RULES_CATCH_AREA', 'RULES_CATCH_DUPE', 'RULES_NO_ITEMS', 'RULES_GAME_OVER')})


def step(n):
    return start <= n


def checkpoint(n):
    t.save(f'{lang}_b{n}')


def load(n):
    t.load(f'{lang}_b{n}' if n > 1 else f'{lang}_test_bedroom')


load(start)
if step(1):
    t.bed('KIT')
    t.step(200)
    t.wait_free(2000, tap='B')
    tst = t.tst()
    t.check('kit: party', [p[0] for p in tst['party']], [149, 149])
    checkpoint(2)

if step(2):
    d0 = t.dbg()
    t.bed('PATRAT')
    t.check('battle menu', t.until({'menu'}, 3000), 'menu')
    d = t.dbg()
    t.check('Patrat: wild start, area 117 marked', (d['wild_starts'] - d0['wild_starts'], d['last_area'],
                                                   d['last_block'], 117 in t.areas()), (1, 117, 0, True))
    t.snap('patrat_menu')
    t.bag_use('hp', 0, 'potion_refused')
    d = t.dbg()
    t.check('Potion refused (no items)', (d['bag_refused'], d['last_refuse_msg']), (1, TXT['RULES_NO_ITEMS']))
    t.check('bag closed', t.bag_close(), True)
    t.bag_use('balls', 0, 'master_ball')
    t.check('nickname question', t.until({'yesno'}, 3000), 'yesno')
    t.snap('nick_question')
    t.touch(128, 115)                          # NO
    t.step(10)
    s = t.until({'name'}, 600, tap=None)
    t.snap('name_entry_after_no')
    t.check('always nickname: name entry after NO', (s, t.dbg()['nick_forced']), ('name', 1))
    t.name_entry()
    t.wait_free(3000, tap='B')
    tst = t.tst()
    t.check('Patrat in the party', [p[0] for p in tst['party']], [149, 149, 504])
    checkpoint(3)

if step(3):
    t.bed('PATRAT')
    t.until({'menu'}, 3000)
    d = t.dbg()
    t.check('Patrat again: dupe block', d['last_block'], 2)
    t.bag_use('balls', 0, 'dupe_refused')
    d = t.dbg()
    t.check('ball refused (dupes)', d['last_refuse_msg'], TXT['RULES_CATCH_DUPE'])
    t.bag_close()
    t.check('ran', t.run_away('dupe_run'), True)
    checkpoint(4)

if step(4):
    t.bed('LILLIPUP')
    t.until({'menu'}, 3000)
    d = t.dbg()
    t.check('Lillipup: area block', (d['last_species'], d['last_block']), (506, 1))
    t.bag_use('balls', 0, 'area_refused')
    t.check('ball refused (area used)', t.dbg()['last_refuse_msg'], TXT['RULES_CATCH_AREA'])
    t.bag_close()
    t.check('ran', t.run_away(), True)
    checkpoint(5)

if step(5):
    t.bed('SHINY')
    t.until({'menu'}, 3000)
    t.snap('shiny_menu')
    d = t.dbg()
    t.check('shiny Patrat: shiny, no block', (d['last_shiny'], d['last_block']), (1, 0))
    t.bag_use('balls', 0, 'shiny_throw')
    t.check('nickname question', t.until({'yesno'}, 3000), 'yesno')
    t.touch(128, 66)                           # YES
    t.step(10)
    t.check('name entry', t.until({'name'}, 600, tap=None), 'name')
    t.name_entry()
    t.wait_free(3000, tap='B')
    t.check('shiny caught', [p[0] for p in t.tst()['party']], [149, 149, 504, 504])
    checkpoint(6)

if step(6):
    t.set_flag(F['shiny'], 0)
    t.bed('SHINY')
    t.until({'menu'}, 3000)
    d = t.dbg()
    t.check('shiny clause off: blocked (dupe)', (d['last_shiny'], d['last_block']), (1, 2))
    t.run_away()
    t.set_flag(F['shiny'], 1)
    checkpoint(7)

if step(7):
    d0 = t.dbg()['trainer_items_denied']
    t.bed('TRAINER')
    t.check('trainer battle menu', t.until({'menu'}, 4000), 'menu')
    t.check('trainer item denied', t.dbg()['trainer_items_denied'] - d0, 1)
    t.snap('trainer')
    t.fight(0)
    t.wait_free(4000, tap='B')
    t.snap('trainer_after')
    checkpoint(8)

if step(8):
    tst0 = t.tst()
    t.test_cmd(1, 0, 0)                        # slot 0 fainted
    t.bed('PATRAT')
    t.until({'menu'}, 3000)
    t.run_away()
    tst = t.tst()
    d = t.dbg()
    t.say('graveyard: before', tst0, 'after', tst)
    t.check('graveyard: slot 0 gone, in the last box, deaths+1',
            (tst['party_count'], tst['grave'] - tst0['grave'], tst['deaths'] - tst0['deaths'], d['graved']),
            (tst0['party_count'] - 1, 1, 1, 1))
    checkpoint(9)

if step(9):
    tst0 = t.tst()
    t.set_flag(F['grave'], 0)
    t.test_cmd(1, 1, 0)                        # slot 1 (Patrat) fainted; Dragonite leads
    t.bed('PATRAT')
    t.until({'menu'}, 3000)
    t.run_away()
    tst = t.tst()
    t.say('release: before', tst0, 'after', tst)
    t.check('release: slot 1 gone, box unchanged, deaths+1',
            (tst['party_count'], tst['grave'] - tst0['grave'], tst['deaths'] - tst0['deaths']),
            (tst0['party_count'] - 1, 0, 1))
    t.set_flag(F['grave'], 1)
    checkpoint(10)

if step(10):
    t.bed('GIFT')
    s = t.until({'name', 'yesno'}, 1500)
    t.snap('gift')
    t.check('gift: name entry without the yes/no', s, 'name')
    t.name_entry()
    t.wait_free(2000, tap='B')
    t.check('gift in the party', t.tst()['party'][-1][0], 504)
    checkpoint(11)

def grass_encounter(w0=None):
    """walk left/right in Route 19's grass (from (60, 695)) until a wild battle starts. RNG-robust: with w0 (wild_starts
    before the walk to the grass), a battle that already started on the way counts"""
    if w0 is None:
        w0 = t.dbg()['wild_starts']
    for i in range(600):
        if t.dbg()['wild_starts'] > w0:
            return True
        t.hold('RIGHT' if (i // 2) % 2 else 'LEFT', 16)
        t.step(4)
        if t.dbg()['wild_starts'] > w0:
            return True
    return False


if step(11):
    t.bed('ROUTE')
    t.wait_free(2000)
    w0 = t.dbg()['wild_starts']
    t.goto(60, 695)
    t.snap('route19')
    t.say('zone', t.zone(), 'pos', t.pos())
    found = grass_encounter(w0)
    d = t.dbg()
    for _ in range(4):          # a species caught before (dupes clause) doesn't use the area: try the next one
        if not found or d['last_block'] != 2 or 124 in t.areas():
            break
        t.say('dupe encounter first', d['last_species'], '(area not used):', t.areas())
        t.until({'menu'}, 3000)
        t.run_away()
        found = grass_encounter()
        d = t.dbg()
    t.check('random encounter on Route 19 (not static), area 124 used', (found, d['last_static'], d['last_area'],
                                                                         d['last_block'], 124 in t.areas()),
            (True, 0, 124, 0, True))
    t.until({'menu'}, 3000)
    t.snap('route19_battle')
    t.run_away()
    found = grass_encounter()
    t.until({'menu'}, 3000)
    d = t.dbg()
    t.say('2nd encounter', d['last_species'], 'block', d['last_block'])
    t.check('2nd encounter on Route 19: blocked (area or dupe)', (found, d['last_block'] in (1, 2)), (True, True))
    t.bag_use('balls', 1, 'route19_refused')
    t.check('ball refused', t.dbg()['last_refuse_msg'] in (TXT['RULES_CATCH_AREA'], TXT['RULES_CATCH_DUPE']), True)
    t.bag_close()
    t.run_away()
    checkpoint(12)

if step(12):
    n = t.tst()['party_count']
    for i in range(1, n):
        t.test_cmd(1, i, 0)
    t.test_cmd(1, 0, 1)
    t.say('game over setup', t.tst())
    w0 = t.dbg()['wild_starts']
    t.goto(60, 695)
    grass_encounter(w0)
    seen, shots = 0, 0
    for k in range(2400):      # Growl until our 1-HP lead faints (RNG-robust: the foe may be slow to hit, e.g. Bide)
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
    t.say('lose kind', t.dbg()['lose_kind'], 'blackouts', t.dbg()['blackouts'])
    for i in range(200):                       # the whiteout screen (ov295, bank 42 line 4), then the reset
        if t.gsys() == 0 or t.dbg()['lose_kind'] != 3:
            break
        if i % 6 == 0 and shots < 16:
            t.snap(f'gameover{shots:02d}')
            shots += 1
        t.step(20)
        if i % 15 == 14:
            t.tap('A')
    t.say('blackouts before the reset', t.dbg()['blackouts'], 'shots', shots)
    t.step(240)
    t.snap('after_reset')
    t.check('game over: whiteout kind 3, then the game reset (g_GameSystem cleared)', (seen, t.gsys()), (1, 0))
    for i in range(6):
        t.step(150)
        t.snap(f'title{i}')
t.finish()
subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sheet2.py'), t.dir,
                os.path.join(os.path.dirname(t.dir), f'battles_{lang}_sheet2.png')])
