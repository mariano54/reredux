"""t_menu.py LANG MODE [ROM] : fresh new game through the real intro to the Redux 3.0 settings menu (redesign:
"Name: Value" rows, pickers, preset confirm, recap) -> bedroom. ROM qa2 (default) or rel.

MODE def    : look at the main page, Start -> recap -> Yes; everything at the defaults
     custom : every page and a picker of each kind; B cancels a picker; preset No then Yes; Fainted
              Graveyard; Species limit: evolution line; Statics, No battle items, Quick save on; City
              White Forest; Difficulty Easy -> (B) -> Challenge; recap -> No -> Start -> Yes
     nuz    : Classic preset (Yes) + Graveyard + Species limit: same species + both item rules (state for
              the rules tests)
Checks every flag / var after Start, the KeyInfo (difficulty, city, no keys), the text speed. State
build/qa2/states/ROM_LANG_MODE_bedroom.dst; sheets build/qa2/menu_ROM_LANG_MODE_sheet.png (both screens)."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qa2 import Q2, FLAGS, V_DIFF, V_LIMIT, V_CITY, V_DONE

lang, mode = sys.argv[1], sys.argv[2]
rom = sys.argv[3] if len(sys.argv) > 3 else 'qa2'
q = Q2(f'menu_{rom}_{lang}_{mode}', lang, rom)
ZERO = {k: 0 for k in FLAGS}


def press(k, tag=None, wait=200):
    q.tap(k)
    q.step(wait)
    if tag:
        q.snap(tag)


def down(n):
    for _ in range(n):
        press('DOWN', wait=60)


def want(what, **on):
    q.check(what, q.rules_flags(), dict(ZERO, **on))


def pick(row, value, tag=None, rows_before=0):
    """on a page whose cursor is on row `rows_before`: go to `row`, open its picker, move to `value`
    (relative moves from the current value: DOWN/UP counts given as +n/-n), A"""
    down(row - rows_before)
    press('A', f'{tag}_picker' if tag else None)
    for _ in range(abs(value)):
        press('DOWN' if value > 0 else 'UP', wait=40)
    if tag:
        q.snap(f'{tag}_hl')
    press('A', tag)


# --- boot -> title -> New Game -> intro -> naming -> flight -----------------------------------------
while q.zone() != 427 and q.frame < 30000:
    if q.frame >= 300 and q.frame % 20 == 0:
        q.hold('A', 4)
    else:
        q.step()
q.check('opening reached', q.zone(), 427)
q.step(420)
q.snap('intro_text')
q.check('new save: Challenge, no keys', q.keyinfo() and (q.keyinfo()['difficulty'], q.keyinfo()['obtained'],
                                                         q.keyinfo()['unlocked']), (2, [0] * 5, [0] * 5))
want('new save: all rule/QoL flags clear')
press('A', 'main')
expect, vars_ = dict(ZERO), {V_DIFF: 2, V_LIMIT: 0, V_CITY: 0}

if mode == 'custom':
    # Difficulty picker: cursor on Challenge (current, marked); UP UP = Easy
    pick(0, -2, 'diff_easy')
    q.check('difficulty -> Easy', q.var(V_DIFF), 0)
    q.snap('main_after_easy')              # cursor still on the Difficulty row
    press('A', 'diff_picker2')             # picker: Easy marked
    press('DOWN', wait=40)
    press('B', 'diff_cancel')              # B: no change
    q.check('B in the picker keeps Easy', q.var(V_DIFF), 0)
    press('A')
    press('DOWN', wait=40)
    press('DOWN', wait=40)
    press('A', 'diff_challenge')
    q.check('difficulty -> Challenge', q.var(V_DIFF), 2)
    # City picker
    pick(1, 1, 'city_white')
    q.check('city -> White Forest', q.var(V_CITY), 1)
    # Nuzlocke page: PRESET FAINT GAMEOVER NICK BACK
    down(1)
    press('A', 'nuz_page')
    press('A')
    q.check('preset: info pages, then yes/no', q.pages_until_yesno('preset_info') is not None, True)
    q.snap('preset_yesno')
    press('DOWN', wait=30)
    press('A', 'preset_no')
    want('preset: No changes nothing')
    press('A')
    q.pages_until_yesno()
    press('A', 'preset_yes')
    want('preset: Yes', release=1, gameover=1, first=1, dupes=1, shiny=1, nick=1)
    pick(1, 1, 'faint_graveyard')          # Released -> Graveyard
    want('Fainted: Graveyard', release=1, grave=1, gameover=1, first=1, dupes=1, shiny=1, nick=1)
    q.snap('nuz_page_after')
    press('B', 'nuz_b_back')
    q.snap('main_after_nuz')
    # Catch page: FIRST DUPES LIMIT SHINY STATICS BACK
    down(1)
    press('A', 'enc_page')
    pick(2, 2, 'limit_line')
    q.check('species limit -> evolution line', q.var(V_LIMIT), 2)
    pick(4, -1, 'statics_on', rows_before=2)   # On is above Off
    want('statics on', release=1, grave=1, gameover=1, first=1, dupes=1, shiny=1, nick=1, statics=1)
    down(1)
    press('A', 'enc_back_row')
    # Items page: NOITEMS NOTRITEMS BACK
    down(1)
    press('A', 'items_page')
    pick(0, -1, 'noitems_on')
    down(2)
    press('A', 'items_back_row')
    # Speed page: SPEED TURBO AUTORUN QSAVE QSURF BACK
    down(1)
    press('A', 'qol_page')
    pick(3, -1, 'qsave_on')
    down(2)
    press('A', 'main_summary')
    expect = dict(ZERO, release=1, grave=1, gameover=1, first=1, dupes=1, shiny=1, nick=1, statics=1, noitems=1,
                  quicksave=1)
    vars_ = {V_DIFF: 2, V_LIMIT: 2, V_CITY: 1}
    want('all chosen', **{k: v for k, v in expect.items() if v})
    # Start: recap pages, No, then again Yes
    down(1)
    press('A')
    q.check('recap pages, then yes/no', q.pages_until_yesno('recap') is not None, True)
    q.snap('confirm')
    press('DOWN', wait=30)
    press('A', 'confirm_no')
    q.check('No -> menu not done', q.var(V_DONE), 0)
    press('A')
    q.pages_until_yesno()
    press('A', 'confirm_yes', wait=60)
elif mode == 'nuz':
    down(2)
    press('A', 'nuz_page')
    press('A')
    q.pages_until_yesno()
    press('A', 'preset_yes')
    pick(1, 1)                              # Graveyard
    press('B')
    down(1)
    press('A', 'enc_page')
    pick(2, 1, 'limit_species')
    press('B')
    down(1)
    press('A', 'items_page')
    pick(0, -1)
    pick(1, -1, rows_before=0)
    down(1)
    press('A')
    q.snap('main_summary')
    down(2)
    expect = dict(ZERO, release=1, grave=1, gameover=1, first=1, dupes=1, shiny=1, nick=1, noitems=1, notritems=1)
    vars_ = {V_DIFF: 2, V_LIMIT: 1, V_CITY: 0}
    press('A')
    q.check('recap pages, then yes/no', q.pages_until_yesno('recap') is not None, True)
    q.snap('confirm')
    press('A', 'confirm_yes', wait=60)
else:
    down(6)
    press('A')
    q.check('recap pages, then yes/no', q.pages_until_yesno('recap') is not None, True)
    q.snap('confirm')
    press('A', 'confirm_yes', wait=60)

for i in range(30):
    if q.var(V_DONE) == 1:
        break
    press('A', wait=60)
q.check('menu done (var 0x4197 = 1)', q.var(V_DONE), 1)
q.check('flags after Start', q.rules_flags(), expect)
q.check('vars after Start', {hex(v): q.var(v) for v in vars_}, {hex(v): x for v, x in vars_.items()})
ki = q.keyinfo()
q.say('KeyInfo', ki)
q.check('KeyInfo: difficulty, city, no keys', ki and (ki['difficulty'], ki['city'], ki['obtained'], ki['unlocked']),
        (vars_[V_DIFF], vars_[V_CITY], [0] * 5, [0] * 5))
q.step(60)
for k in range(4):
    q.step(90)
    q.snap(f'cutscene_{k}')
ok = q.wait_field(6000, tap='A', settle=60)
q.check('bedroom reached', (ok, q.zone()), (True, 428))
q.snap('bedroom')
q.save(f'{mode}_bedroom')
q.result()
q.sheet(both=True)
