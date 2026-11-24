"""qt.py : DeSmuME driver for the qol2 tests (library), on top of build/scripts/rules/rt.py.

Q(name, lang, kind, run) opens build/qol2/roms/<kind>_<lang>_<run>.nds, a symlink to build/qol2/<kind>_<lang>.nds
(kind: q2t = all modules + qol2 + test helpers, n2t = the same without qol2, qol2 / noq2 = release
module sets), so every run has its own DeSmuME battery save (moved aside at start unless keep_save).
Output: build/qol2/out/<name>/ (log.txt, shots, rec/ frames). States: build/qol2/states/.
Extras over RT: per-frame conditional pokes (cpoke: written whenever the old bytes are there, e.g.
while an overlay is loaded), exec hooks with frame stamps, qol2_dbg / speed_dbg / q2tst access."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
from rrenv import skip_frames, no_skip, RENDER_TAIL  # noqa: E402,F401  (RR_SKIP_RENDER: draw only what is looked at)
import os, sys, json
sys.path.insert(0, f'{RR_T}/rules')
import rt as RTM
from rt import RT

B = f'{RR_B}'
Q2 = B + '/qol2'
STATES = Q2 + '/states'
OUTQ = Q2 + '/out'
DBG = ('override on autorun quicksave groups ovl_loads evo_skips egg_skips me_skips pad ci_extra wipes '
       'save_steps box_extra qsaves').split()


class Q(RT):
    def __init__(self, name, lang='en', kind='q2t', run=None, record=False, keep_save=False):
        os.makedirs(Q2 + '/roms', exist_ok=True)
        os.makedirs(STATES, exist_ok=True)
        run = run or name
        link = f'{Q2}/roms/{kind}_{lang}_{run}.nds'
        if not os.path.lexists(link):
            os.symlink(f'../{kind}_{lang}.nds', link)
        RTM.OUT = OUTQ
        if keep_save:
            self._open_keep(link, f'{kind}_{lang}', f'{Q2}/{kind}_{lang}.elf', name)
        else:
            RT.__init__(self, link, f'{kind}_{lang}', f'{Q2}/{kind}_{lang}.elf', name, record)
        self.lang, self.kind = lang, kind
        self.cpokes = []
        self.events = []
        self.fails = []
        self.n = 0

    def _open_keep(self, rom, tag, elf, name):
        """RT.__init__ without moving the battery save aside (Continue tests: the game reads ROM.dsv)"""
        from desmume.emulator import DeSmuME
        self.emu = DeSmuME()
        self.emu.open(rom)
        self.emu.volume_set(0)
        self.m = self.emu.memory.unsigned
        qm = json.load(open(f'{B}/qol/{tag}/qol_map.json'))
        self.sym, self.texts = qm['symbols'], qm.get('texts', {})
        self.fdbg = RTM.nm(elf, 'follow_dbg')
        self.dir = os.path.join(OUTQ, name)
        os.makedirs(self.dir, exist_ok=True)
        self.frame, self.rec = 0, None
        self.log = open(os.path.join(self.dir, 'log.txt'), 'w')

    @staticmethod
    def dsv(kind, lang, run):
        return os.path.expanduser(f'{RR_DSV}/{kind}_{lang}_{run}.dsv')

    # --- frames --------------------------------------------------------------------------------
    @property
    def rec(self):
        return self.__dict__.get('_rec')

    @rec.setter
    def rec(self, path):
        """start recording into path (old frames of an earlier run are removed once per test)"""
        if path and path not in self.__dict__.setdefault('_rec_seen', set()):
            self._rec_seen.add(path)
            if os.path.isdir(path):
                for f in os.listdir(path):
                    if f.endswith('.png'):
                        os.remove(os.path.join(path, f))
        self.__dict__['_rec'] = path

    def step(self, n=1):
        if not self.rec and n > RENDER_TAIL:
            skip_frames(self.emu, n - RENDER_TAIL)
        for _ in range(n):
            for a, old, new in self.cpokes:
                if bytes(self.m[a + i] for i in range(len(old))) == old:
                    for i, x in enumerate(new):
                        self.m[a + i] = x
            super().step(1)

    def cpoke(self, addr, old, new):
        self.cpokes.append((addr, bytes.fromhex(old), bytes.fromhex(new)))

    def hook(self, addr, tag, regs=False):
        """log (frame, tag[, r0, r1]) whenever addr executes"""
        def f(a, s):
            r = self.emu.memory.register_arm9
            self.events.append((self.frame, tag, r.r0 if regs else None, r.r1 if regs else None))
        self.emu.memory.register_exec(addr, f, 2)

    def first(self, tag, after=0):
        return next((e[0] for e in self.events if e[1] == tag and e[0] >= after), None)

    # --- state ---------------------------------------------------------------------------------
    def save(self, name):
        self.emu.savestate.save_file(f'{STATES}/{self.kind}_{self.lang}_{name}.dst')

    def load(self, name, kind=None):
        self.emu.savestate.load_file(f'{STATES}/{kind or self.kind}_{self.lang}_{name}.dst')
        fl = os.environ.get('Q2FLAGS')          # e.g. "5DA=0,5DC=1": flip flags at run time after the load
        if fl:
            self.step(2)
            for it in fl.split(','):
                f, v = it.split('=')
                self.set_flag(int(f, 16), int(v))
            self.say('Q2FLAGS', fl)

    def q2dbg(self):
        a = self.sym.get('qol2_dbg')
        if a is None:
            return {}
        a &= ~1
        v = [self.r8(a + i) for i in range(4)] + [self.r32(a + 4), self.r32(a + 8)] + \
            [self.r16(a + 12 + 2 * i) for i in range(4)] + [self.r32(a + 20 + 4 * i) for i in range(4)] + [self.r16(a + 36)]
        return dict(zip(DBG, v))

    def speed_override(self, v):
        """0 flags, 1 force off, 2 force on (speed_dbg.override; qol2 follows it)"""
        self.w8(self.sym['speed_dbg'] & ~1, v)

    def q2cmd(self, cmd, a=0, b=0, c=0):
        t = self.sym['q2tst'] & ~1
        self.w32(t + 8, a)
        self.w32(t + 12, b)
        self.w32(t + 16, c)
        self.w32(t + 4, cmd)
        self.step(3)
        assert self.r32(t + 4) == 0, 'q2tst cmd not run'
        return self.r32(t + 20)

    def pparam(self, slot, param):
        return self.q2cmd(1, slot, param)

    def set_pparam(self, slot, param, v):
        self.q2cmd(2, slot, param, v)

    def normal(self):
        """both screens at normal master brightness"""
        u = self.emu.memory.unsigned
        return not (u.read_short(0x0400006C) & 0x1F) and not (u.read_short(0x0400106C) & 0x1F)

    def until_dark(self, n=400):
        """step until a screen leaves normal brightness -> frame or None"""
        for i in range(n):
            if not self.normal():
                return self.frame
            self.step(1)
        return None

    def until_lit(self, n=600, stay=20):
        """step until both screens stayed at normal brightness for `stay` frames -> first frame of that run"""
        run = 0
        for i in range(n):
            run = run + 1 if self.normal() else 0
            if run >= stay:
                return self.frame - stay + 1
            self.step(1)
        return None

    def find(self, pat, lo=0x02000000, hi=0x02400000):
        """addresses of byte pattern pat in main RAM"""
        data = bytes(self.emu.memory.unsigned[lo:hi])
        out, i = [], data.find(pat)
        while i >= 0:
            out.append(lo + i)
            i = data.find(pat, i + 1)
        return out

    def bed_warp(self, zone, x, z, d=0):
        """bed test menu row ROUTE (MapChangeWarpPad 437, 52, 700, 0) with its arguments poked in the
        loaded script -> warp anywhere"""
        if self.pos() != (13, 3):
            self.goto(13, 3)
        self.face('LEFT')
        self.tap('A')
        self.step(150)
        hits = self.find(bytes.fromhex('bf00b5013400bc020000'))
        for a in hits:
            for i, v in enumerate((zone, x, z, d)):
                self.w16(a + 2 + 2 * i, v)
        self.say('bed_warp: script hits', [hex(a) for a in hits])
        for _ in range(6):                  # ROWS.index('ROUTE')
            self.tap('DOWN')
            self.step(10)
        self.tap('A')
        return bool(hits)

    # --- results -------------------------------------------------------------------------------
    def snap(self, tag):
        self.n += 1
        return self.shot(f'{self.n:02d}_{tag}')

    def check(self, what, got, want):
        ok = got == want
        self.say(('OK  ' if ok else 'FAIL'), what, 'got', got, 'want', want)
        if not ok:
            self.fails.append(what)
        return ok

    def result(self, extra=None):
        self.say('RESULT', 'PASS' if not self.fails else 'FAIL ' + ', '.join(self.fails))
        res = os.path.join(OUTQ, 'results.jsonl')
        with open(res, 'a') as f:
            f.write(json.dumps(dict(test=os.path.basename(self.dir), lang=self.lang, kind=self.kind,
                                    fails=self.fails, **(extra or {}))) + '\n')
        return not self.fails

    def sheet(self, src=None, out=None, every=None):
        import subprocess
        src = src or self.dir
        out = out or os.path.join(Q2, os.path.basename(self.dir) + '_sheet.png')
        subprocess.run([sys.executable, os.path.join(B, 'scripts', 'r3_sheet.py'), src, out])
        return out


boot_to_menu = RTM.boot_to_menu


def QR(*a, **kw):
    """Q with the rules tests' helpers (tcommon.T: bed menu, battle UI, bag, run away, ...)"""
    import tcommon

    class _QR(Q, getattr(tcommon, '_T_orig', tcommon.T)):
        pass
    return _QR(*a, **kw)
