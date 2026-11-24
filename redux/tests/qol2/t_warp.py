"""t_warp.py LANG FROM ZONE X Z [DIR] [TO] [KIND] : load state FROM (a bedroom state), warp with the bed menu
to ZONE (X, Z), wait for the field, screenshot, save state TO (default FROM_zZONE)."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import sys
from qt import QR

lang, frm, zone, x, z = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
d = int(sys.argv[6]) if len(sys.argv) > 6 else 0
to = sys.argv[7] if len(sys.argv) > 7 else f'{frm}_z{zone}'
kind = sys.argv[8] if len(sys.argv) > 8 else 'q2t'
q = QR(f'warp_{kind}_{lang}_{to}', lang, kind)
q.load(frm)
q.step(20)
q.check('script found', q.bed_warp(zone, x, z, d), True)
q.check('field free', q.wait_free(1500, tap='B'), True)
q.step(30)
q.say('zone', q.zone(), 'pos', q.pos())
q.check('zone', q.zone(), zone)
q.shot('both')
q.save(to)
q.result()
