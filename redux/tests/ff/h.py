"""h.py : small DeSmuME harness for the fix-float work (worktree-local; nothing outside it is written
except <battery dir>/ffi_*.dsv, which are moved aside, never deleted).

H(rom, tag, sav=None, elf=None): opens a symlink build/ff_integ/roms/ffi_<tag>.nds -> rom (so the battery save
is <battery dir>/ffi_<tag>.dsv), copies `sav` there first (an old one is moved aside)."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, shutil, subprocess, sys
from desmume.emulator import DeSmuME
from desmume.controls import Keys, keymask

FF = f'{RR_B}/ff_integ'   # outputs, ROM links, battery copies
G_GAMESYSTEM = 0x021410F4


def nm(elf, name):
    for l in subprocess.run(['arm-none-eabi-nm', elf], capture_output=True, text=True).stdout.splitlines():
        a, t, n = l.split()
        if n == name:
            return int(a, 16)
    return None


class H:
    def __init__(self, rom, tag, sav=None, elf=None, outdir=None):
        os.makedirs(FF + '/roms', exist_ok=True)
        link = f'{FF}/roms/ffi_{tag}.nds'
        if os.path.lexists(link):
            os.remove(link)
        os.symlink(os.path.abspath(rom), link)
        dsv = os.path.expanduser(f'{RR_DSV}/ffi_{tag}.dsv')
        if os.path.exists(dsv):
            k = 0
            while os.path.exists(f'{dsv}.bak.{k}'):
                k += 1
            os.rename(dsv, f'{dsv}.bak.{k}')
        if sav:
            shutil.copy(sav, dsv)
        self.emu = DeSmuME()
        self.emu.open(link)
        self.emu.volume_set(0)
        self.m = self.emu.memory.unsigned
        self.fdbg = nm(elf, 'follow_dbg') if elf else None
        self.frame = 0
        self.dir = outdir or f'{FF}/out/{tag}'
        os.makedirs(self.dir, exist_ok=True)
        self.rec = None
        self.hooks = []

    def step(self, n=1):
        for _ in range(n):
            for f in self.hooks:
                f(self)
            self.emu.cycle(with_joystick=False)
            self.frame += 1
            if self.rec:
                self.emu.screenshot().crop((0, 0, 256, 192)).save(f'{self.rec}/{self.frame:06d}.png', compress_level=1)

    def hold(self, k, n):
        self.emu.input.keypad_add_key(keymask(getattr(Keys, 'KEY_' + k)))
        self.step(n)
        self.emu.input.keypad_rm_key(keymask(getattr(Keys, 'KEY_' + k)))

    def tap(self, k, n=1, idle=14):
        for _ in range(n):
            self.hold(k, 6)
            self.step(idle)

    def shot(self, name, top=True):
        im = self.emu.screenshot()
        if top:
            im = im.crop((0, 0, 256, 192))
        p = os.path.join(self.dir, name + '.png')
        im.save(p)
        return p

    def r8(self, a):
        return self.m[a]

    def r16(self, a):
        return self.m[a] | self.m[a + 1] << 8

    def r32(self, a):
        return self.r16(a) | self.r16(a + 2) << 16

    def s32(self, a):
        v = self.r32(a)
        return v - (1 << 32) if v & 0x80000000 else v

    def w8(self, a, v):
        self.m[a] = v & 0xFF

    def w16(self, a, v):
        self.w8(a, v)
        self.w8(a + 1, v >> 8)

    def w32(self, a, v):
        self.w16(a, v)
        self.w16(a + 2, v >> 16)

    def gsys(self):
        return self.r32(G_GAMESYSTEM)

    def gd(self):
        g = self.gsys()
        return self.r32(g + 0x1C) if 0x02000000 <= g < 0x02400000 else 0

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
                    return True
            else:
                ok = 0
            self.step()
        return False

    def pos(self):
        v = self.r32(self.fdbg + 8)
        return v & 0xFFFF, v >> 16

    def fpos(self):
        v = self.r32(self.fdbg + 12)
        return v & 0xFFF, v >> 16 & 0xFFF

    def cont(self, max_frames=1500):
        """power on -> title -> Continue -> field"""
        for i in range(max_frames):
            self.step(1)
            if self.frame >= 200 and self.frame % 30 == 0:
                self.hold('A', 4)
            if self.gsys():
                break
        return self.wait_field(1500, settle=30)

    def actors(self):
        """[(addr, uid, obj)] of the field actors in use"""
        g = self.gsys()
        f = self.r32(g + 0x08) if g else 0
        return f

    def find_actor(self, sys_addr, uid):
        cap = self.r16(sys_addr + 4)
        a = self.r32(sys_addr + 0x1C)
        for i in range(cap):
            p = a + 0x100 * i
            if self.r32(p) & 1 and self.r16(p + 8) == uid:
                return p
        return None
