"""t_continue.py LANG [unova] : power on the release ROM with t_smoke.py's battery save (rel_LANG_smoke_LANG.dsv, kept),
title -> main menu -> Continue: no "C-Gear on?" prompt (the check at 0x0219DFAA logged), field at the saved spot,
no wireless (GFL_NET 0), the settings menu doesn't come back (var 0x4197 = 1), flags/difficulty as saved.
unova: instead, main menu -> Unova Link (DOWN, A) -> shots of its screens (Key System difficulty: Challenge).
Shots build/qa/continue_LANG[_unova]/."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qa import QA

lang = sys.argv[1]
unova = 'unova' in sys.argv[2:]
q = QA(f'continue_{lang}' + ('_unova' if unova else ''), lang, 'rel', run=f'smoke_{lang}', keep_save=True)
dsv = QA.dsv('rel', lang, f'smoke_{lang}')
q.check('battery save present', os.path.exists(dsv), True)
q.hook(0x0219DFAA, 'cgear_check')
shots = 0
for i in range(900):
    q.step(1)
    if q.frame % 60 == 0 and shots < 12:
        q.snap(f'boot{shots:02d}')
        shots += 1
    if q.frame >= 200 and q.frame % 30 == 0:
        if unova and q.frame >= 420:
            break
        q.hold('A', 4)
    if q.r32(0x021410F4):
        break
if unova:
    q.step(60)
    q.snap('main_menu')
    q.tap('DOWN')
    q.step(20)
    q.snap('main_menu_down')
    q.tap('A')
    for k in range(8):
        q.step(60)
        q.snap(f'unova{k}')
    q.tap('A')
    for k in range(6):
        q.step(60)
        q.snap(f'unova_a{k}')
    q.result()
    q.sheet(both=True)
    sys.exit()
g = q.frame if q.r32(0x021410F4) else None
q.check('GameSystem started (Continue)', g is not None, True)
ok = q.wait_field(1500, settle=30)
for k in range(3):
    q.snap(f'field{k}')
    q.step(30)
net = q.r32(0x021418B0)
q.say('zone', q.zone(), 'pos', q.pos(), 'GFL_NET', hex(net), 'cgear check at', q.first('cgear_check'))
q.check('field after Continue', ok, True)
q.check('saved spot (Pokémon Center 435)', q.zone(), 435)
q.check('no C-Gear prompt / wireless off', net, 0)
q.check('settings menu done (var 0x4197)', q.var(0x4197), 1)
st = q.stored_difficulty()
q.check('difficulty Challenge after the save', st and st[0], 2)
q.say('flags', q.flags())
q.result()
q.sheet(both=True)
