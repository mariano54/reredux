"""t_newgame.py LANG MODE [ROM] : fresh new game (battery save moved aside) through the real intro on the release
ROM (ROM rel, default) or the QA test ROM (test): boot -> title -> New Game -> Juniper -> naming -> opening
flight -> the Redux 3.0 settings menu -> cutscene -> bedroom. Intro frames every 45 f in <dir>/intro/.

MODE def : Difficulty picker (Easy, back to Challenge), Start -> recap -> No -> Start -> Yes; everything at
           the defaults (Challenge, speed-ups ON, turbo ON, auto-run ON, opt-ins off). The full menu walk-through
           (every page, pickers, B, preset No/Yes, recap) is build/scripts/qa2/t_menu.py.
     nuz : Classic Nuzlocke preset + Graveyard + Statics + both item rules (for the rules tests)
State: build/qa/states/ROM_LANG_MODE_bedroom.dst. Sheets: build/qa/newgame_ROM_LANG_MODE{,_intro}_sheet.png."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qa import QA, FLAGS

lang, mode = sys.argv[1], sys.argv[2]
rom = sys.argv[3] if len(sys.argv) > 3 else 'rel'
name = f'newgame_{rom}_{lang}_{mode}'
q = QA(name, lang, rom)
intro = os.path.join(q.dir, 'intro')
os.makedirs(intro, exist_ok=True)
for f in os.listdir(intro):
    os.remove(os.path.join(intro, f))
ZERO = {k: 0 for k in FLAGS}


def press(k, tag=None, wait=150):
    q.tap(k)
    q.step(wait)
    if tag:
        q.snap(tag)


def want(what, **on):
    q.check(what, q.flags(), dict(ZERO, **on))


def text_speed():
    """config text speed (0 slow, 1 normal, 2 fast; CONFIG save block, see speed/emu.py)"""
    r4 = q.r32(q.r32(0x0209A338) + 0x10)
    r5 = q.r32(r4 + 0x2C)
    a = q.r32(r4 + 0x34) + q.r32(q.r32(r5 + 0x14) + 0xC * 0x1B + 8)
    return q.r16(a) & 15, q.r16(a) >> 6 & 1      # text speed, battle style bit (1 = Set)


# --- boot -> title -> New Game -> intro -> naming -> flight -----------------------------------------
taps = 0
while q.zone() != 427 and q.frame < 30000:
    if q.frame % 45 == 0:
        q.emu.screenshot().save(os.path.join(intro, f'{q.frame:05d}.png'))
    if q.frame >= 300 and q.frame % 20 == 0:
        q.hold('A', 4)
        taps += 1
    else:
        q.step()
q.say('zone 427 (opening) at frame', q.frame, 'after', taps, 'A taps')
q.check('opening reached', q.zone(), 427)
for i in range(420):
    if i % 45 == 0:
        q.emu.screenshot().save(os.path.join(intro, f'{q.frame:05d}.png'))
    q.step()
q.snap('menu_intro_text')
d = q.dbg()
st = q.stored_difficulty()
q.check('new save difficulty Challenge (before the menu)', st and st[0], 2)
q.check('menu not done yet (var 0x4197)', q.var(0x4197), 0)
want('new save: all rule/QoL flags clear')
press('A', 'main')
q.check('default difficulty var = Challenge', q.var(0x4198), 2)

def yesno():
    """the field YES/NO box (top screen, right edge)"""
    p = q.emu.screenshot().convert('RGB').getpixel
    return p((250, 110)) == (248, 248, 248) and p((253, 110)) == (0, 0, 0)


def to_yesno(tag=None, n=24):
    """A through message pages until the YES/NO box shows"""
    for i in range(n):
        if yesno():
            return True
        if tag:
            q.snap(f'{tag}_{i}')
        press('A', wait=90)
    return yesno()


def down(n):
    for _ in range(n):
        press('DOWN', wait=60)


def pick(row, moves, tag=None, at=0):
    """page/main cursor on row `at` -> row `row`, open its picker, move `moves` (+down / -up) from the current
    value (the picker opens on it), A"""
    down(row - at)
    press('A', f'{tag}_picker' if tag else None, wait=200)
    for _ in range(abs(moves)):
        press('DOWN' if moves > 0 else 'UP', wait=60)
    press('A', tag, wait=200)


# main rows: Difficulty, City, Nuzlocke, Catch rules, Items, Speed, Start the adventure!
if mode == 'def':
    pick(0, -2, 'diff_easy')
    q.check('difficulty -> Easy', q.var(0x4198), 0)
    pick(0, 2, 'diff_challenge')
    q.check('difficulty -> Challenge', q.var(0x4198), 2)
    want('defaults')
    down(6)
    press('A', wait=200)
    q.check('recap, then yes/no', to_yesno('recap'), True)
    q.snap('confirm')
    press('DOWN', wait=60)
    press('A', 'confirm_no', wait=200)
    q.check('No -> back in the menu (var 0x4197 still 0)', q.var(0x4197), 0)
    press('A', wait=200)
    to_yesno()
    press('A', 'confirm_yes', wait=60)
    expect = dict(ZERO)
elif mode == 'nuz':
    down(2)
    press('A', 'nuz_page', wait=200)
    press('A', wait=200)                         # Use Classic Nuzlocke preset... -> pages -> Yes
    to_yesno('preset')
    press('A', 'preset', wait=200)
    pick(1, 1, 'graveyard')                      # Fainted: Released -> Graveyard
    down(3)
    press('A', wait=200)                         # Back
    down(1)
    press('A', 'enc_page', wait=200)
    pick(4, -1, 'statics_on')                    # Statics count: On
    down(1)
    press('A', wait=200)                         # Back
    down(1)
    press('A', 'items_page', wait=200)
    pick(0, -1)
    pick(1, -1, 'items_on')
    down(1)
    press('A', wait=200)                         # Back
    expect = dict(ZERO, release=1, grave=1, gameover=1, first=1, dupes=1, shiny=1, nick=1, statics=1, noitems=1,
                  notritems=1)
    want('nuzlocke set', **{k: v for k, v in expect.items() if v})
    q.snap('main_summary')
    down(2)
    press('A', wait=200)
    q.check('recap, then yes/no', to_yesno('recap'), True)
    q.snap('confirm')
    press('A', 'confirm_yes', wait=60)
for _ in range(30):
    if q.var(0x4197) == 1:
        break
    press('A', wait=60)

q.check('menu done (var 0x4197 = 1)', q.var(0x4197), 1)
d = q.dbg()
st = q.stored_difficulty()
q.check('RulesCmd 0 -> Challenge', d['difficulty'], 2)
q.check('stored difficulty Challenge', st and st[0], 2)
q.check('flags after Done', q.flags(), expect)
ts, setstyle = text_speed()
q.check('text speed Fast (2)', ts, 2)
q.check('battle style Set', setstyle, 1)
# the opening cutscene goes on (Mom, the bedroom)
q.step(60)
q.snap('cutscene')
for k in range(4):
    q.step(90)
    q.snap(f'cutscene_{k}')
ok = q.wait_field(6000, tap='A', settle=60)
q.say('field free:', ok, 'zone', q.zone(), 'pos', q.pos(), 'frame', q.frame)
q.check('bedroom reached', (ok, q.zone()), (True, 428))
q.snap('bedroom')
q.save(f'{mode}_bedroom')
q.result()
q.sheet(both=True)
q.sheet(intro, os.path.join(os.path.dirname(q.dir), f'{name}_intro_sheet.png'))
