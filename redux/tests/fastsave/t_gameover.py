"""t_gameover.py LANG : the Nuzlocke game over must not save (fastsave x rules). QA test ROM (release modules +
rules_test + qol2_test), from the qa nuz new game (build/qa/states/test_LANG_nuz_bedroom.dst, copied to
build/fastsave_integ/states/), own ROM link (own battery).
 1 bed KIT, then a menu save in the bedroom (the first save: B2's whole-save write) -> battery exported (before)
 2 bed ROUTE (Route 19), every Pokemon but the lead fainted, the lead at 1 HP; walk in the grass until a random
   encounter (wild_starts + 1: RNG-robust, any number of steps); fight until rules_dbg.lose_kind = 3 (game over),
   A through the game-over text until the reset (GameSystem gone) + 400 frames
 3 from step 2 on: no call of the save engine (0x0203B9BC), EventSave_Update (0x02163B38) or the card-write
   entry (0x0203C07C, fastsave's fs_guard site); the battery exported after the reset == the one before."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import json, os, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'qa'))
import sav
from fs import FS
import qa
qa.QA_DIR, qa.STATES = FS + '/qa', FS + '/states'     # ROM links stay in build/qa/roms (unique names)

lang = sys.argv[1]
B = os.path.dirname(FS)
OUTD = os.path.join(FS, 'out', f'gameover_{lang}')
os.makedirs(OUTD, exist_ok=True)
STATE = os.path.join(FS, 'states', f'test_{lang}_nuz_bedroom.dst')
os.makedirs(os.path.dirname(STATE), exist_ok=True)
shutil.copy(f'{B}/qa/states/test_{lang}_nuz_bedroom.dst', STATE)
EVENTSAVE_UPDATE = 0x02163B38

t = qa.QAR(f'fs_gameover_{lang}', lang, 'test', run=f'fsgameover_{lang}')
t.emu.savestate.load_file(STATE)
t.say('state loaded', STATE)
t.step(10)
reg = t.emu.memory.register_arm9
cnt = dict(engine=0, eventsave=0, cardwrite=0)
es = {}


def h_eng(a, s):
    cnt['engine'] += 1


def h_es(a, s):
    cnt['eventsave'] += 1
    v = t.r32(reg.r1)
    es['state'] = v


def h_cw(a, s):
    cnt['cardwrite'] += 1


t.emu.memory.register_exec(0x0203B9BC, h_eng, 2)
t.emu.memory.register_exec(EVENTSAVE_UPDATE, h_es, 2)
t.emu.memory.register_exec(0x0203C07C, h_cw, 2)

# 1 kit + menu save
t.bed('KIT')
t.step(200)
t.wait_free(2000, tap='B')
t.check('kit', [p[0] for p in t.tst()['party']], [149, 149])
t.tap('X')
t.step(30)
t.touch(190, 92)
saved = None
for i in range(6000):
    if es.get('state') == 4:
        t.hold('A', 2)
        t.step(2)
    else:
        t.step(1)
    if es.get('state', 0) >= 0x12 and t.field_ready():
        saved = t.frame
        break
t.check('menu save in the bedroom completed', saved is not None and cnt['cardwrite'] > 0, True)
t.say('MEAS first menu save: counts', dict(cnt), 'frame', saved)
t.step(30)
before = os.path.join(OUTD, 'battery_before.sav')
if os.path.exists(before):
    os.remove(before)
t.emu.backup.export_file(before)
c = sav.check(before)
t.check('saved battery valid (both copies: CRCs)', (c['A']['bad'], c['B']['bad']), ([], []))

# 2 game over
for k in cnt:
    cnt[k] = 0
t.bed('ROUTE')
t.wait_free(2000)
n = t.tst()['party_count']
for i in range(1, n):
    t.test_cmd(1, i, 0)
t.test_cmd(1, 0, 1)
w0 = t.dbg()['wild_starts']
t.goto(60, 695)                 # RNG-robust: the encounter may already start on the way through the grass
for i in range(900):
    if t.dbg()['wild_starts'] > w0:
        break
    t.hold('RIGHT' if (i // 2) % 2 else 'LEFT', 16)
    t.step(4)
    if t.dbg()['wild_starts'] > w0:
        break
t.check('Route 19 random encounter', t.dbg()['wild_starts'] > w0, True)
t.until({'menu'}, 3000)
t.snap('route19')
seen = 0
for k in range(900):
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
for i in range(300):
    if t.gsys() == 0 or t.dbg()['lose_kind'] != 3:
        break
    if i % 6 == 0 and shots < 12:
        t.snap(f'gameover{shots:02d}')
        shots += 1
    t.step(20)
    if i % 15 == 14:
        t.tap('A')
t.step(400)
t.snap('after_reset')
t.check('game over (lose_kind 3), then reset (GameSystem gone)', (seen, t.gsys()), (1, 0))
t.say('MEAS game over path: counts', dict(cnt))
t.check('no save during the game over (engine / EventSave / card writes)', dict(cnt),
        dict(engine=0, eventsave=0, cardwrite=0))
after = os.path.join(OUTD, 'battery_after.sav')
if os.path.exists(after):
    os.remove(after)
t.emu.backup.export_file(after)
t.check('battery unchanged by the game over', open(after, 'rb').read()[:0x80000] == open(before, 'rb').read()[:0x80000],
        True)
for a in (0x0203B9BC, EVENTSAVE_UPDATE, 0x0203C07C):
    t.emu.memory.register_exec(a, None)
t.say('fails', t.fails)
print('RESULT', 'PASS' if not t.fails else 'FAIL ' + ', '.join(t.fails))
