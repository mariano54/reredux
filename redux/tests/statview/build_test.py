"""build_test.py [LANG..] : statview test ROMs from the release build's follower ROMs: every release module + qol2_test
(q2tst mailbox) -> build/out/sv_LANG.nds, qol_map in build/qol/sv_LANG/ (the release's build/qol/LANG stays)."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, sys
T = f'{RR_RX}/tools'
sys.path.insert(0, T)
os.chdir(T)
import qol_build
B = os.path.normpath(os.path.join(T, '..', 'build'))
for lang in sys.argv[1:] or ['en', 'jp']:
    m = qol_build.build(f'{B}/redux3/{lang}_followers.nds', f'{B}/out/sv_{lang}.nds', lang, ['qol2_test'], None, False,
                        follower_elf=f'{B}/redux3/{lang}_follow.elf', tag=f'sv_{lang}')
    print('built', lang, m['modules'])
