"""fs.py : DeSmuME harness for the fast-save work (library). Everything stays in this worktree's
redux/build/fastsave/ (ROM symlinks in roms/, output in out/<name>/), battery saves in
<battery dir>/<tag>.dsv (an old one is moved aside, never deleted)."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
from rrenv import skip_frames, no_skip, RENDER_TAIL  # noqa: E402,F401  (RR_SKIP_RENDER: draw only what is looked at)
import json, os, shutil, sys
from desmume.emulator import DeSmuME
from desmume.controls import Keys, keymask

FS = f'{RR_B}/fastsave_integ'   # outputs (scripts: build/scripts/fastsave)
B = os.path.dirname(FS)
OUT = FS + '/out'
DSV_DIR = os.path.expanduser(f'{RR_DSV}')
G_GAMESYSTEM = 0x021410F4
EVENTSAVE_UPDATE = 0x02163B38


def dsv_path(tag):
    return f'{DSV_DIR}/{tag}.dsv'


def move_aside(p):
    if os.path.exists(p):
        k = 0
        while os.path.exists(f'{p}.bak.{k}'):
            k += 1
        os.rename(p, f'{p}.bak.{k}')
        return f'{p}.bak.{k}'
    return None


class F:
    def __init__(self, rom, tag, name, dsv=None, keep=False, qmap=None):
        """rom: ROM file; tag: unique ROM name (symlink roms/<tag>.nds -> rom, battery <tag>.dsv);
        dsv: battery save to start from (copied in), None + keep=False: no battery (new game);
        keep=True: use <tag>.dsv as it is."""
        os.makedirs(FS + '/roms', exist_ok=True)
        link = f'{FS}/roms/{tag}.nds'
        if os.path.lexists(link):
            os.remove(link)
        os.symlink(os.path.abspath(rom), link)
        if not keep:
            move_aside(dsv_path(tag))
            if dsv:
                shutil.copy(dsv, dsv_path(tag))
        self.tag = tag
        self.emu = DeSmuME()
        self.emu.open(link)
        self.emu.volume_set(0)
        self.m = self.emu.memory.unsigned
        self.r = self.emu.memory.register_arm9
        self.dir = os.path.join(OUT, name)
        os.makedirs(self.dir, exist_ok=True)
        self.log = open(os.path.join(self.dir, 'log.txt'), 'w')
        self.frame = 0
        self.sym = {}
        if qmap and os.path.exists(qmap):
            self.sym = json.load(open(qmap))['symbols']
        self.fails = []
        self.events = []

    # --- input / time ---
    def step(self, n=1):
        if n > RENDER_TAIL:
            skip_frames(self.emu, n - RENDER_TAIL)
        for _ in range(n):
            self.emu.cycle(with_joystick=False)
            self.frame += 1

    def hold(self, k, n):
        self.emu.input.keypad_add_key(keymask(getattr(Keys, 'KEY_' + k)))
        self.step(n)
        self.emu.input.keypad_rm_key(keymask(getattr(Keys, 'KEY_' + k)))

    def tap(self, k, n=1, idle=14):
        for _ in range(n):
            self.hold(k, 6)
            self.step(idle)

    def touch(self, x, y, n=6):
        self.emu.input.touch_set_pos(x, y)
        self.step(n)
        self.emu.input.touch_release()

    def shot(self, name):
        p = os.path.join(self.dir, name + '.png')
        self.emu.screenshot().save(p)
        return p

    def say(self, *a):
        s = ' '.join(str(x) for x in a)
        print(s, flush=True)
        self.log.write(s + '\n')
        self.log.flush()

    def check(self, what, got, want):
        ok = got == want
        self.say('OK  ' if ok else 'FAIL', what, 'got', got, 'want', want)
        if not ok:
            self.fails.append(what)
        return ok

    def result(self, extra=None):
        self.say('RESULT', 'PASS' if not self.fails else 'FAIL ' + ', '.join(self.fails))
        with open(os.path.join(OUT, 'results.jsonl'), 'a') as f:
            f.write(json.dumps(dict(test=os.path.basename(self.dir), fails=self.fails, **(extra or {}))) + '\n')
        return not self.fails

    def close(self):
        """flush the battery save (DeSmuME writes the .dsv on close)"""
        try:
            self.emu.close()
        except Exception as e:
            self.say('close:', e)

    def hook(self, addr, fn):
        self.emu.memory.register_exec(addr, fn, 2)

    # --- memory ---
    def r8(self, a): return self.m[a]
    def r16(self, a): return self.m[a] | self.m[a + 1] << 8
    def r32(self, a): return self.r16(a) | self.r16(a + 2) << 16
    def w8(self, a, v): self.m[a] = v & 0xFF
    def w16(self, a, v): self.w8(a, v); self.w8(a + 1, v >> 8)
    def w32(self, a, v): self.w16(a, v); self.w16(a + 2, v >> 16)

    def gsys(self): return self.r32(G_GAMESYSTEM)

    def gd(self):
        g = self.gsys()
        return self.r32(g + 0x1C) if 0x02000000 <= g < 0x02400000 else 0

    def ew(self):
        gd = self.gd()
        return self.r32(gd + 0x1AC) if gd else 0

    def flag(self, f):
        return self.r8(self.ew() + 0x35E + (f >> 3)) >> (f & 7) & 1

    def set_flag(self, f, on=True):
        a = self.ew() + 0x35E + (f >> 3)
        v = self.r8(a)
        self.w8(a, v | 1 << (f & 7) if on else v & ~(1 << (f & 7)))

    def var(self, v): return self.r16(self.ew() + 2 * (v - 0x4000))
    def set_var(self, v, x): self.w16(self.ew() + 2 * (v - 0x4000), x)

    def zone(self):
        gd = self.gd()
        return self.r16(gd + 0x114) if gd else None

    def event_running(self):
        g = self.gsys()
        return self.r32(g + 0x18) != 0 if g else True

    def field_ready(self):
        return self.zone() is not None and not self.event_running()

    def wait_field(self, max_frames=3000, settle=30):
        ok = 0
        for i in range(max_frames):
            if self.field_ready():
                ok += 1
                if ok >= settle:
                    return self.frame - settle + 1
            else:
                ok = 0
            self.step()
        return None

    # --- boot ---
    def boot_continue(self, maxf=4000):
        """power on, A every 10 frames from frame 200 until the GameSystem exists (title, Continue),
        then wait for the field to be free -> frame or None"""
        g = None
        for i in range(maxf):
            if self.gsys():
                g = self.frame
                break
            if self.frame >= 200 and self.frame % 10 == 0:
                self.hold('A', 4)
            else:
                self.step(1)
        if g is None:
            return None
        return self.wait_field(1500, settle=20)

    def find(self, pat, lo=0x02000000, hi=0x02400000):
        data = bytes(self.emu.memory.unsigned[lo:hi])
        out, i = [], data.find(pat)
        while i >= 0:
            out.append(lo + i)
            i = data.find(pat, i + 1)
        return out

    # --- the menu save ---
    def menu_save(self, answer='A', maxf=2500, trace=None):
        """X, touch SAVE, answer the yes/no (tap A as soon as it's up) -> dict of state frames, t0
        (touch), free (field free again)"""
        st = []
        self.save_state = None

        def sh(a, s):
            v = self.r32(self.r.r1)
            self.save_state = v
            if not st or st[-1][1] != v:
                st.append((self.frame, v))
        self.hook(EVENTSAVE_UPDATE, sh)
        self.tap('X')
        self.step(30)
        t0 = self.frame
        self.touch(190, 92)
        free = None
        for i in range(maxf):
            if st and st[-1][1] == 4 and answer:
                self.hold(answer, 2)
                self.step(2)
            else:
                self.step(1)
            if trace:
                trace(self)
            if st and st[-1][1] >= 0x12 and self.field_ready():
                free = self.frame
                break
        self.emu.memory.register_exec(EVENTSAVE_UPDATE, None)
        first = {}
        for fr, v in st:
            first.setdefault(v, fr)
        return dict(t0=t0, states=st, first=first, free=free)


PHASES = [('menu', 'touch', 0), ('panel', 0, 2), ('question', 2, 4), ('yes/no', 4, 5), ('prep+saving msg', 5, 9),
          ('write', 9, 10), ('SE+saved msg', 10, 16), ('hold', 16, 19), ('close', 19, 'free')]


def phases(res):
    f = dict(res['first'])
    f['touch'] = res['t0']
    f['free'] = res['free']
    out = []
    for name, a, b in PHASES:
        fa = f.get(a)
        fb = f.get(b)
        if a == 4 and fa is None:          # quick save: no state 4
            fa = fb = f.get(5)
        if fa is not None and fb is not None:
            out.append((name, fb - fa))
        else:
            out.append((name, None))
    tot = (res['free'] - res['t0']) if res['free'] else None
    return out, tot
