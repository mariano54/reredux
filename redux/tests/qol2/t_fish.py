"""t_fish.py LANG KIND MODE [CASTS] : fishing at Aspertia's pond (west bank (50, 764), facing east) from
KIND_LANG_MODE_kg: a Super Rod is added and registered to Y (Bag, Key Items checkbox), then CASTS casts (default 3):
Y, wait for the bite (EventFieldFishing state 4, OVL_33 0x021793B8), A, run from the battle.
MEAS bite = per cast, state 2 (settle) start -> state 4 (bite) start; cast = Y -> bite."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import sys
from qt import QR

lang, kind, mode = sys.argv[1:4]
casts = int(sys.argv[4]) if len(sys.argv) > 4 else 3
q = QR(f'fish_{kind}_{lang}_{mode}', lang, kind)
q.load(f'{mode}_kg')
q.step(5)
q.check('Super Rod added', q.test_cmd(2, 447, 1), 1)
q.tap('X')
q.step(40)
q.touch(190, 48)                       # Bag
q.step(90)
for i in range(4):
    q.touch(130, 180)                  # >> to Key Items
    q.step(40)
q.touch(126, 72)                       # Super Rod's Y checkbox
q.step(40)
q.snap('registered')
q.tap('B')
q.step(90)
q.tap('B')                             # close the X menu too
q.wait_free(600, tap=None)
q.say('after the Bag', q.pos())
q.step(30)
q.bed_warp(427, 48, 764, 0)
q.wait_free(1500, tap='B')
q.goto(50, 764)
q.hold('RIGHT', 3)
q.step(20)
q.check('on the bank', q.pos(), (50, 764))
st = []


def fh(a, s):
    v = q.r32(q.emu.memory.register_arm9.r1)
    if not st or st[-1][1] != v:
        st.append((q.frame, v))


q.emu.memory.register_exec(0x021793B8, fh, 2)
bites, totals = [], []
for c in range(casts):
    n0 = len(st)
    ty = q.frame
    q.hold('Y', 4)
    got = None
    for i in range(600):
        q.step(1)
        if any(v == 4 for f, v in st[n0:]):
            got = q.frame
            break
    s2 = next((f for f, v in st[n0:] if v == 2), None)
    s4 = next((f for f, v in st[n0:] if v == 4), None)
    bites.append((s4 - s2) if s2 and s4 else None)
    totals.append((s4 - ty) if s4 else None)
    q.say('cast', c, 'states', st[n0:], 'bite', bites[-1])
    q.hold('A', 4)                     # hook it -> wild battle
    q.check(f'cast {c}: battle', q.until({'menu'}, 3000, tap='B'), 'menu')
    q.run_away()
    q.wait_free(1500, tap='B')
    q.step(30)
q.say('MEAS bite', bites, 'MEAS cast', totals)
q.result(dict(bite=bites, cast=totals))
