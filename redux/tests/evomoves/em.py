"""em.py : DeSmuME helpers for the evomoves tests (on statview's sv.SV): the em_dbg struct, the q2tst mailbox,
opening the party summary, the learnset / evolution data from the named tree."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import json, os, sys
sys.path.insert(0, f'{RR_T}/statview')
from sv import SV, B, SVD
if os.environ.get('EMU') == 'melon':         # melonDS (melemu.py): MPU / data aborts as on hardware
    import melemu
    melemu.install()

R = f'{RR_RX}'
EVD = B + '/evomoves'
MAX_FAM, MAX_LEARN = 16, 32


class EM(SV):
    def __init__(self, name, lang, rom=None, tag=None, dsv=None, elf=True):
        if os.environ.get('EMU') == 'melon':
            name = 'mel_' + name
        rom = rom or f'{B}/out/em_{lang}.nds'
        tag = tag or f'em_{lang}'
        dsv = dsv or f'{B}/statview_integ/dsv/rel_{lang}_smoke_{lang}.dsv'
        super().__init__(name, rom, tag, dsv, elf=f'{B}/redux3/{lang}_follow.elf' if elf else None)
        self.lang = lang
        self.T = self.sym_addr('q2tst') if 'q2tst' in self.sym else None
        self.D = self.sym_addr('em_dbg') if 'em_dbg' in self.sym else None

    def q2(self, cmd, a=0, b=0, c=0):
        T = self.T
        self.w32(T + 8, a); self.w32(T + 12, b); self.w32(T + 16, c); self.w32(T + 4, cmd)
        self.step(3)
        assert self.r32(T + 4) == 0, 'q2tst not run'
        return self.r32(T + 20)

    def dbg(self):
        D = self.d = self.D
        r8, r16 = self.r8, self.r16
        o = 4
        names = 'on shown listmode cursor scroll nlearn next nfam lines overflow known pending'.split()
        d = {n: r8(D + o + i) for i, n in enumerate(names)}
        o += len(names)
        for n in 'species form level creates finnews hides finolds inits exits scrolls enters flushes rights'.split():
            d[n] = r16(D + o)
            o += 2
        d['fam'] = [r16(D + o + 2 * i) for i in range(MAX_FAM)][:d['nfam']]
        o += 2 * MAX_FAM
        d['learn_lv'] = [r16(D + o + 2 * i) for i in range(MAX_LEARN)][:d['nlearn']]
        o += 2 * MAX_LEARN
        d['learn_mv'] = [r16(D + o + 2 * i) for i in range(MAX_LEARN)][:d['nlearn']]
        d['magic'] = self.r32(D)
        return d

    def page(self):
        """the summary app's page (app+0x58) and shown page (app+0x5C), via the em_input hook's last app"""
        return None

    def open_summary(self, slot=0):
        """field -> X menu -> POKéMON -> party slot -> A (summary)"""
        self.tap('X'); self.step(40); self.touch(64, 48); self.step(90)
        for _ in range(slot):
            self.tap('DOWN'); self.step(10)
        self.tap('A'); self.step(90); self.tap('A'); self.step(90); self.tap('A'); self.step(150)

    def close_summary(self):
        for _ in range(4):
            self.tap('B'); self.step(40)
        return self.wait_field(2000, tap='B', settle=30)


def learnsets():
    return json.load(open(R + '/build/named/redux/data/learnsets.json'))


def evolutions():
    return json.load(open(R + '/build/named/redux/data/evolutions.json'))
