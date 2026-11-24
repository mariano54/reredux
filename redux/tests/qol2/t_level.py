"""t_level.py LANG KIND MODE TAP [LEARN] : level-up / move learning from KIND_LANG_MODE_kg (Patrat Lv10 lead): its EXP
is set to one below Lv11, then it beats a wild Patrat (Tackle until the KO).
TAP none: no input until the stat box (level-up jingle + delay run their full length); B: B every 10 frames.
LEARN keep: answer "delete a move?" YES, then KEEP OLD MOVES (touch); forget: YES, forget move 1 (Leer).
MEAS: ko2box = KO (foe HP 0 seen) -> stat box (level-up state 9); st6_8 = level-up states 6..8 frames
(message + jingle + delay); learn = learn prompt answered -> field free. States of the level-up sequence
(ov167 FUN_021B7E18, *r1) are logged."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, sys
from qt import QR

lang, kind, mode, tapk = sys.argv[1:5]
learn = sys.argv[5] if len(sys.argv) > 5 else 'keep'
q = QR(f'level_{kind}_{lang}_{mode}_{tapk}_{learn}', lang, kind)
q.load(f'{mode}_kg')
q.step(5)
lv, exp = q.pparam(0, 0x9E), q.pparam(0, 8)
q.say('Patrat level', lv, 'exp', exp)
q.check('medium-fast growth (exp = lv^3)', exp, lv ** 3)
q.set_pparam(0, 8, (lv + 1) ** 3 - 1)
lvl_states = []


def lvh(a, s):
    r = q.emu.memory.register_arm9
    st = q.r32(r.r1)
    if not lvl_states or lvl_states[-1][1] != st:
        lvl_states.append((q.frame, st))


q.emu.memory.register_exec(0x021B7E18, lvh, 2)
q.bed('PATRAT')
q.check('battle menu', q.until({'menu'}, 3000, tap='B'), 'menu')
q.rec = q.dir + '/rec'
os.makedirs(q.rec, exist_ok=True)
for k in range(6):                       # Tackle until the level-up sequence starts
    if q.ui() == 'menu':
        q.fight(0)
        q.step(30)
    for i in range(40):
        q.step(10)
        if lvl_states or q.ui() == 'menu':
            break
    if lvl_states:
        break
tk = q.frame
for i in range(120):                      # until the stat box (state 9)
    if any(s >= 9 for f, s in lvl_states):
        break
    if tapk != 'none':
        q.tap(tapk, idle=4)
    else:
        q.step(10)
s = {}
for f, st in lvl_states:
    s.setdefault(st, f)
q.say('level-up states', lvl_states[:20])
box = s.get(9)
q.say('MEAS ko2box', (box - lvl_states[0][0]) if box else None, 'MEAS st6_8', (s[9] - s[6]) if 9 in s and 6 in s else None,
      'MEAS st8', (s[9] - s[8]) if 9 in s and 8 in s else None)
q.snap('statbox')
q.step(30)
q.tap('A')                                # stat box page 1 -> 2
q.step(30)
q.tap('A')
q.step(60)
q.snap('after_box')
def buttons():
    """two big buttons on the bottom screen (FORGET / KEEP OLD MOVES, or a yes/no): light pixels at their centres"""
    im = q.emu.screenshot().convert('RGB')
    c, d = im.getpixel((40, 240)), im.getpixel((128, 236))
    return c[0] == c[1] == c[2] >= 48 and d[0] == d[1] == d[2] >= 48


mv0 = [q.pparam(0, 0x36 + i) for i in range(4)]
# learn prompt: "wants to learn ... Should a move be deleted?" (A through the text) -> FORGET / KEEP OLD MOVES
for i in range(40):
    if buttons():
        break
    q.hold('A', 4)
    for k in range(12):
        q.step(1)
        if buttons():
            break
q.snap('learn_q')
q.check('FORGET / KEEP buttons', buttons(), True)
q.step(20)
if learn == 'keep':
    tl = q.frame
    q.touch(128, 100)                     # KEEP OLD MOVES
else:
    q.touch(128, 50)                      # FORGET -> the move screen
    q.step(60)
    q.snap('move_screen')
    q.touch(65, 56)                       # move 0
    q.step(40)
    q.snap('move_detail')
    tl = q.frame
    q.touch(128, 165)                     # FORGET
q.step(20)
q.snap('after_choice')
moves_end = None
asked = 0
for i in range(200):
    if buttons() and asked < 3:           # vanilla "Give up on learning X?" -> the upper button (YES)
        asked += 1
        q.snap('yesno2')
        q.touch(128, 50)
        q.step(30)
        continue
    if q.field_ready():
        moves_end = q.frame
        break
    q.tap('B', idle=10)
q.say('second question (give up?) asked', asked)
q.check('"give up?" asked: vanilla only', asked > 0, learn == 'keep' and not (kind == 'q2t' and mode == 'def'))
q.rec = None
ok = q.wait_free(1200, tap='B')
q.say('MEAS learn', (moves_end or q.frame) - tl)
q.check('field after the battle', ok, True)
mv = [q.pparam(0, 0x36 + i) for i in range(4)]
q.say('moves before', mv0, 'after', mv, 'qol2_dbg', q.q2dbg())
q.check('Patrat Lv 11 after the battle', q.pparam(0, 0x9E), lv + 1)
q.check('moves', mv == mv0, learn == 'keep')
if learn != 'keep':
    q.check('Headbutt learned', 29 in mv, True)
q.snap('end')
q.result(dict(states=lvl_states[:20]))
