"""t_boot.py LANG KIND RUN [cgear] [idle] : power on build/qol2/roms/KIND_LANG_RUN.nds with its battery save (t_save.py
RUN = save_MODE), A every 10 frames from frame 200 (title, Continue) until the GameSystem exists, then no
input until the field is free (season banner). cgear: the C-Gear counts as owned (arm9 0x020098C0 ->
return 1), so vanilla asks "C-Gear on?" (A = yes). idle: no A on the title screen until frame 1500.
MEAS gsys = power-on -> GameSystem; field = GameSystem -> field free (banner); C-Gear/net state after."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import sys
from qt import Q

lang, kind, run = sys.argv[1:4]
cgear = 'cgear' in sys.argv[4:]
idle = 'idle' in sys.argv[4:]
q = Q(f'boot_{kind}_{lang}_{run}{"_cgear" if cgear else ""}{"_idle" if idle else ""}', lang, kind, run=run, keep_save=True)
if cgear:
    old = bytes(q.r8(0x020098C0 + i) for i in range(4)).hex()
    q.say('C-Gear check bytes', old)
    q.cpoke(0x020098C0, old, '01207047')
q.hook(0x0219DFAA, 'cgear_check')          # main menu Continue: bl C-Gear obtained?
g = None
for i in range(4000):
    if q.r32(0x021410F4):
        g = q.frame
        break
    if q.frame >= (1500 if idle else 200) and q.frame % 10 == 0:
        q.hold('A', 4)
    else:
        q.step(1)
q.check('GameSystem started', g is not None, True)
from PIL import ImageChops, ImageStat
shots = []
for i in range(600):                      # top screen, every 2nd frame
    q.step(2)
    shots.append((q.frame, q.emu.screenshot().crop((0, 0, 256, 192)).convert('L').resize((64, 48))))
final = shots[-1][1]
diff = [(f, ImageStat.Stat(ImageChops.difference(im, final)).mean[0]) for f, im in shots]
last_off = max((f for f, d in diff if d > 12), default=g)
q.say('banner diff samples', [(f, round(d)) for f, d in diff[::15]])
ok = q.wait_field(600, settle=1)
tf = last_off
q.step(30)
net = q.r32(0x021418B0)
q.say('MEAS gsys', g, 'MEAS field', tf - g if g else None, 'zone', q.zone(),
      'GFL_NET', hex(net), 'cgear checked', q.first('cgear_check'))
q.shot('field')
q.check('field after Continue', ok, True)
q.check('saved zone (bedroom 428)', q.zone(), 428)
q.check('no wireless after Continue (C-Gear off)', net, 0) if kind.startswith('q2') or not cgear else None
q.shot('field')
q.result(dict(gsys=g, field=tf - g if g else None, net=net))
