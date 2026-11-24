"""t_twice.py ROM QMAP LANG NAME [N] [quick] [speedoff] : Continue, N (default 2) menu saves in a row; phases and fs_dbg
counters after each; battery left in <battery dir>/fs_NAME.dsv"""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import sys, os, json
from fs import F, phases
rom, qmap, lang, name = sys.argv[1:5]
rest = sys.argv[5:]
N = int(rest[0]) if rest and rest[0].isdigit() else 2
SRC = {'en': os.environ.get('SRC_DSV_EN') or os.path.expanduser(f'{RR_DSV}/q2t_en_save_def.dsv'),
       'jp': os.environ.get('SRC_DSV_JP') or os.path.expanduser(f'{RR_DSV}/q2t_jp_save_def.dsv')}
f = F(rom, f'fs_{name}', name, dsv=os.environ.get('SRC_DSV', SRC[lang]), qmap=qmap)
f.boot_continue()
if 'quick' in rest:
    f.set_flag(0x5DD, True)
if 'speedoff' in rest:
    f.set_flag(0x5DA, True)
if os.environ.get('STEP_TICKS') and f.sym.get('fs_dbg'):
    f.w16((f.sym['fs_dbg'] & ~1) + 4, int(os.environ['STEP_TICKS']))
if os.environ.get('CMP_TICKS') and f.sym.get('fs_dbg'):
    f.w16((f.sym['fs_dbg'] & ~1) + 6, int(os.environ['CMP_TICKS']))
f.step(30)
DBG = 'skipped changed compared verified promoted dropped guard resets saves steps updates max_ticks seeded'.split()


def dbg():
    a = f.sym.get('fs_dbg')
    if a is None:
        return {}
    a &= ~1
    return {k: f.r32(a + 12 + 4 * i) for i, k in enumerate(DBG)}


out = []
for k in range(N):
    res = f.menu_save()
    ph, tot = phases(res)
    d = dbg()
    f.say(f'save {k}: PHASES', ' '.join(f'{n}={v}' for n, v in ph), 'TOTAL', tot)
    f.say(f'save {k}: fs_dbg', d)
    out.append(dict(phases=ph, total=tot, dbg=d, states=res['states']))
    f.step(40)
f.shot('end')
f.step(60)
f.close()
json.dump(out, open(os.path.join(f.dir, 'meas.json'), 'w'))
