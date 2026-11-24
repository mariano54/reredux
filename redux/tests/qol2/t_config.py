"""t_config.py LANG KIND STATE : the new game's config halfword (save block 0x1B): text speed (bits 0-3), Battle Style
(bit 6, 1 = Set), Battle Scene (bit 7, 1 = off). qol2 builds must start with Set; the others Shift."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import sys
from qt import Q
lang, kind, state = sys.argv[1:4]
q = Q(f'config_{kind}_{lang}_{state}', lang, kind)
q.load(state)
q.step(3)
r4 = q.r32(q.r32(0x0209A338) + 0x10)
r5 = q.r32(r4 + 0x2C)
a = q.r32(r4 + 0x34) + q.r32(q.r32(r5 + 0x14) + 0xC * 0x1B + 8)
v = q.r16(a)
q.say('config', hex(v), 'text speed', v & 15, 'style Set', v >> 6 & 1, 'scene off', v >> 7 & 1)
# builds with the qol2 module start with Set: q2t, qol2 and qa (the QA test ROM = every release module)
q.check('Battle Style', v >> 6 & 1, 1 if kind.startswith('q2') or kind in ('qol2', 'qa') else 0)
q.check('text speed Fast (speed module default)', v & 15, 2)
q.result()
