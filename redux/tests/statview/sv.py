"""sv.py : DeSmuME driver for the statview tests (library, on top of rt.py).

SV(name, rom_path, qol_tag, dsv=None): opens build/sv/roms/<name>.nds (a symlink to rom_path) so the battery save
<battery dir>/<name>.nds.dsv is per run; an old one is moved aside (never deleted); dsv (a saved game) is copied
in when given. Output build/sv/<name>/ (log, NN_tag.png shots)."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rt as RTM
from rt import RT

B = RTM.B
SVD = B + '/statview_integ'
DSV_DIR = os.path.expanduser(f'{RR_DSV}')


class SV(RT):
    def __init__(self, name, rom, tag, dsv=None, elf=None):
        os.makedirs(SVD + '/roms', exist_ok=True)
        link = f'{SVD}/roms/svi_{name}.nds'
        if os.path.lexists(link):
            os.remove(link)
        os.symlink(rom, link)
        mine = os.path.join(DSV_DIR, 'svi_' + name + '.dsv')
        if os.path.exists(mine):
            k = 0
            while os.path.exists(f'{mine}.bak.{k}'):
                k += 1
            os.rename(mine, f'{mine}.bak.{k}')
        if dsv:
            shutil.copy(dsv, mine)
        from desmume.emulator import DeSmuME
        self.emu = DeSmuME()
        self.emu.open(link)
        self.emu.volume_set(0)
        self.m = self.emu.memory.unsigned
        q = json.load(open(f'{B}/qol/{tag}/qol_map.json'))
        self.sym, self.texts = q['symbols'], q.get('texts', {})
        self.fdbg = RTM.nm(elf, 'follow_dbg') if elf else None
        self.dir = os.path.join(SVD, name)
        os.makedirs(self.dir, exist_ok=True)
        for f in os.listdir(self.dir):
            if f.endswith('.png'):
                os.remove(os.path.join(self.dir, f))
        self.frame, self.rec, self.n, self.fails = 0, None, 0, []
        self.log = open(os.path.join(self.dir, 'log.txt'), 'w')

    def snap(self, tag):
        self.n += 1
        return self.shot(f'{self.n:02d}_{tag}')

    def check(self, what, got, want):
        ok = got == want
        self.say(('OK  ' if ok else 'FAIL'), what, 'got', got, 'want', want)
        if not ok:
            self.fails.append(what)
        return ok

    def result(self):
        self.say('RESULT', 'PASS' if not self.fails else 'FAIL ' + ', '.join(self.fails))
        return not self.fails

    def sheet(self, out=None, both=True, cols=0):
        import subprocess
        out = out or os.path.join(SVD, os.path.basename(self.dir) + '_sheet.png')
        subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sheet.py'),
                        self.dir, out] + (['--both'] if both else []) + (['--cols', str(cols)] if cols else []))
        self.say('sheet', out)
        return out

    def boot_continue(self, max_frames=1500):
        """power on -> title -> main menu -> Continue -> field"""
        for i in range(max_frames):
            self.step(1)
            if self.frame >= 200 and self.frame % 30 == 0:
                self.hold('A', 4)
            if self.r32(0x021410F4):
                break
        ok = self.wait_field(1500, settle=30)
        self.say('continue: field', ok, 'zone', self.zone(), 'frame', self.frame)
        return ok

    def sym_addr(self, name):
        return self.sym[name] & ~1

    def svdbg(self):
        """statview.c SvDbg (ReRedux layout): mode 0 ability / 1 totals; ivs / evs of the last drawn stats page in
        summary row order (HP, Atk, Def, SpA, SpD, Spe); rows = IV / EV rows printed on it"""
        D = self.sym_addr('sv_dbg')
        return dict(magic=self.r32(D), mode=self.r8(D + 4), cur=self.r8(D + 5), hp_type=self.r8(D + 6),
                    rows=self.r8(D + 7), ivs=[self.r8(D + 8 + i) for i in range(6)],
                    evs=[self.r16(D + 14 + 2 * i) for i in range(6)], iv_total=self.r16(D + 26),
                    ev_total=self.r16(D + 28), draws=self.r16(D + 30), toggles=self.r16(D + 32),
                    inits=self.r16(D + 34))

    def ink(self, x0, y0, x1, y1, top=True):
        """number of text pixels (the stats' dark grey 0x585050-ish) in a rect of the top (or bottom) screen"""
        im = self.emu.screenshot().convert('RGB')
        oy = 0 if top else 192
        n = 0
        for y in range(y0, y1):
            for x in range(x0, x1):
                r, g, b = im.getpixel((x, y + oy))
                if r < 120 and g < 120 and b < 120 and abs(r - b) < 24:
                    n += 1
        return n
