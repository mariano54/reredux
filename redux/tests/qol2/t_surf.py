"""t_surf.py LANG KIND MODE : Surf from Aspertia's pond bank. From KIND_LANG_MODE_kg: warp to (52, 763), Patrat (lead,
follower) gets Surf in move slot 3, flag 2406 (partner with you) cleared, face DOWN, A every 20 frames until the
player is on the water (52, 764). Quick Surf (flag 0x5DE, MODE opt) must not ask "Would you like to Surf?".
MEAS surf = first A -> on the water. Frames recorded."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, sys
from qt import QR

lang, kind, mode = sys.argv[1:4]
q = QR(f'surf_{kind}_{lang}_{mode}', lang, kind)
q.load(f'{mode}_kg')
q.step(5)
q.set_pparam(0, 0x39, 57)                  # move 4 = Surf
q.set_flag(2406, 0)                        # 2406 = a story partner is with you (blocks Surf)
q.check('Surf taught', q.pparam(0, 0x39), 57)
q.bed_warp(427, 48, 764, 0)
q.wait_free(1500, tap='B')
q.step(30)
q.goto(50, 764)                            # walk to the pond's west bank: the follower stays on land
q.say('after warp: moves', [q.pparam(0, 0x36 + i) for i in range(4)], 'egg', q.pparam(0, 0x4C), 'species', q.pparam(0, 5),
      'flag 2406', q.flag(2406))
q.hold('RIGHT', 3)                         # face the water
q.step(20)
q.check('on the bank', q.pos(), (50, 764))
ev = []
LM = None
q.rec = q.dir + '/rec'
os.makedirs(q.rec, exist_ok=True)
t0 = q.frame
on = None
yesno_seen = False
for i in range(60):
    q.hold('A', 4)
    for k in range(16):
        q.step(1)
        if q.pos() == (51, 764):
            on = q.frame
            break
    im = q.emu.screenshot().convert('RGB')
    if on:
        break
q.rec = None
q.step(150)
q.check('still on the water', q.pos()[0] >= 51 and q.pos()[1] == 764, True)
q.say('MEAS surf', (on - t0) if on else None, 'quick surf flag', q.flag(0x5DE))
q.check('surfing', on is not None, True)
q.snap('surfing')
q.result(dict(surf=(on - t0) if on else None))
