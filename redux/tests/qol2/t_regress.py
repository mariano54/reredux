"""t_regress.py LANG KIND MODE : turbo + follower regressions on Route 19 (KIND_LANG_MODE_r19, Patrat follower):
 1 turbo: R -> on; hold UP 60 frames: field extra ticks counted, tiles faster; R -> off
 2 follower talk: turn to it, A -> its talk script runs (event) -> close
 3 bike: Bicycle added + registered to Y (Bag, Key Items 3rd row), Y -> the follower goes into its ball
   (ballfx_start called, follower hidden), Y -> off the bike, it comes back out (ballfx_start again)
Frames recorded for the sheets."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, sys
from qt import QR
from desmume.controls import Keys, keymask

lang, kind, mode = sys.argv[1:4]
q = QR(f'regress_{kind}_{lang}_{mode}', lang, kind)
q.load(f'{mode}_r19')
q.step(3)
q.set_flag(0x963, 1)
q.step(10)
T = q.sym['turbo_dbg'] & ~1


def tdbg():
    return dict(on=q.r8(T), live=q.r8(T + 1), extra_field=q.r32(T + 16), extra_battle=q.r32(T + 20))


q.tap('R')
q.step(10)
d0 = tdbg()
q.check('turbo on', d0['on'], 1)
p0 = q.pos()
q.hold('DOWN', 3)
q.step(10)
q.emu.input.keypad_add_key(keymask(Keys.KEY_UP))
ch, pos = [], q.pos()
for i in range(60):
    q.step(1)
    if q.pos() != pos:
        ch.append(q.frame)
        pos = q.pos()
q.emu.input.keypad_rm_key(keymask(Keys.KEY_UP))
d1 = tdbg()
iv = [b - a for a, b in zip(ch, ch[1:])]
q.say('turbo walk intervals', iv, 'extra field ticks', d1['extra_field'] - d0['extra_field'])
q.check('turbo: extra field ticks', d1['extra_field'] > d0['extra_field'], True)
q.tap('R')
q.step(10)
q.check('turbo off', tdbg()['on'], 0)
# follower talk
q.step(30)
f3 = q.r32(q.fdbg + 12)
fx, fz = f3 & 0xFFF, (f3 >> 16) & 0xFFF
px, pz = q.pos()
d = 'DOWN' if fz > pz else 'UP' if fz < pz else 'LEFT' if fx < px else 'RIGHT'
q.say('player', (px, pz), 'follower', (fx, fz), '->', d)
q.hold(d, 3)
q.step(15)
q.tap('A')
q.step(60)
ev = q.event_running()
q.snap('talk')
q.check('follower talk script runs', ev, True)
q.wait_free(1500, tap='B')
# bike + ball
import qt as QTM
import rt as RTM
# the follower code's ballfx_start (ITCM; moves with follow.c changes): from the ROM's follower ELF
q.hook(RTM.nm(f'{QTM.Q2}/{kind}_{lang}.elf', 'ballfx_start'), 'ballfx')
q.check('Bicycle added', q.test_cmd(2, 450, 1), 1)
q.tap('X')
q.step(40)
q.touch(190, 48)
q.step(90)
for i in range(4):
    q.touch(130, 180)
    q.step(40)
q.snap('keyitems')
q.touch(126, 72)                         # 3rd row checkbox (Xtransceiver, Pal Pad, Bicycle)
q.step(40)
q.tap('B')
q.step(90)
q.tap('B')
q.wait_free(900, tap='B')
q.step(20)
q.rec = q.dir + '/rec'
os.makedirs(q.rec, exist_ok=True)
n0 = len(q.events)
q.hold('Y', 4)
q.step(120)
q.snap('on_bike')
b1 = [e for e in q.events[n0:] if e[1] == 'ballfx']
q.check('recall: ballfx_start called', len(b1) >= 1, True)
q.hold('UP', 20)
q.step(20)
n1 = len(q.events)
q.hold('Y', 4)
q.step(60)
q.hold('DOWN', 16)
q.step(90)
q.rec = None
q.snap('off_bike')
b2 = [e for e in q.events[n1:] if e[1] == 'ballfx']
q.say('ballfx calls on', len(b1), 'off', len(b2))
q.check('release: ballfx_start called', len(b2) >= 1, True)
q.result()
