"""build_test.py [LANG..] : QA test ROMs from the release build's follower ROM build/redux3/LANG_followers.nds:
every release qol module + rules_test (bed test menu) + qol2_test (q2tst mailbox), no icon
-> build/qa/roms/qa_test_LANG.nds (+ .elf), qol_map in build/qol/qa_test_LANG/. Run after build_redux3.py."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, shutil, sys
T = f'{RR_RX}/tools'
sys.path.insert(0, T)
os.chdir(T)
import qol_build
B = f'{RR_B}'
R = B + '/qa/roms'
os.makedirs(R, exist_ok=True)
for lang in sys.argv[1:] or ['en', 'jp']:
    src, elf = f'{B}/redux3/{lang}_followers.nds', f'{B}/redux3/{lang}_follow.elf'
    out = f'{R}/qa_test_{lang}.nds'
    try:
        m = qol_build.build(src, out, lang, ['rules_test', 'qol2_test'], None, False, follower_elf=elf,
                            tag=f'qa_test_{lang}')
    except qol_build.QolError as e:
        sys.exit(f'qol: {e}')
    shutil.copy(elf, f'{R}/qa_test_{lang}.elf')
    print('built', out, 'modules', m.get('modules'))
