"""t_rules.py LANG [SCRIPT] [FROM] : run the rules agent's battle scenarios (rules/t_battles.py, or t_battles_jp.py)
unchanged on the QA test ROM (release modules + rules_test + qol2_test), from the QA new game
build/qa/states/test_LANG_nuz_bedroom.dst (t_newgame.py LANG nuz test: Classic Nuzlocke + graveyard + statics + both
item rules). Output build/qa/rules_LANG[_jp]/ and build/qa/battles_LANG_sheet2.png."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, runpy, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import qa
import tcommon

lang = sys.argv[1]
script = sys.argv[2] if len(sys.argv) > 2 else 't_battles.py'
start = sys.argv[3] if len(sys.argv) > 3 else None
Orig = tcommon.T


class Shim(qa.QA, Orig):
    def __init__(self, lang, name, record=False):
        qa.QA.__init__(self, 'rules_' + name, lang, 'test')

    def load(self, name, rom=None):
        if name.endswith('_test_bedroom'):
            name = 'nuz_bedroom'
        return qa.QA.load(self, name, rom)

    def ui(self):
        s = Orig.ui(self)
        if s is None:      # JP-safe yes/no (see qa.QAR)
            p = self.emu.screenshot().convert('RGB').getpixel
            if p((240, 212)) == (128, 8, 8) and p((128, 212)) == (32, 32, 32) and p((128, 270)) == (32, 32, 32):
                return 'yesno'
        return s

    def finish(self):
        self.result()
        self.sheet(both=True)


tcommon.T = Shim
sys.argv = [os.path.join(qa.S, 'rules', script), lang] + ([start] if start else [])
runpy.run_path(sys.argv[0], run_name='__main__')
