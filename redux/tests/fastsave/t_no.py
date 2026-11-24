"""t_no.py ROM QMAP LANG NAME : menu save answered NO (B on the yes/no): no save, the battery unchanged, control back"""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import sys, os
from fs import F, phases
import sav
rom, qmap, lang, name = sys.argv[1:5]
SRC = {'en': os.environ.get('SRC_DSV_EN') or os.path.expanduser(f'{RR_DSV}/q2t_en_save_def.dsv'),
       'jp': os.environ.get('SRC_DSV_JP') or os.path.expanduser(f'{RR_DSV}/q2t_jp_save_def.dsv')}
f = F(rom, f'fs_{name}', name, dsv=SRC[lang], qmap=qmap)
f.boot_continue()
f.hold('DOWN', 10)
f.step(40)
b0 = os.path.join(f.dir, 'before.sav')
b1 = os.path.join(f.dir, 'after.sav')
for p in (b0, b1):
    if os.path.exists(p):
        os.remove(p)
f.emu.backup.export_file(b0)
res = f.menu_save(answer='B', maxf=300)   # NO returns to the start menu (vanilla): the event stays
ph, tot = phases(res)
f.say('states', res['states'])
f.emu.backup.export_file(b1)
f.check('NO: the event went to state 0x11 (no save)', 0x11 in res['first'] and 5 not in res['first'], True)
f.check('battery unchanged', sav.raw(b0) == sav.raw(b1), True)
f.tap('B')
f.step(10)
f.tap('B')
ok = f.wait_field(300, settle=10)
f.check('back in the start menu, B closes it, control back', ok is not None, True)
f.shot('after_no')
f.result()
