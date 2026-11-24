"""mh.py : one driver API over the headless melonDS (bfix libbf: MPU, hooks, audio) and DeSmuME (py-desmume) for the
menu-speed measurements and tests (library).

  E = emu('mel'|'dsm', rom, dsv=None)   battery save: a DeSmuME .dsv (footer cut for melonDS) or a raw .sav
  E.step(n, keys=(), touch=None)        keys: names ('A', 'B', 'UP', ...); touch: (x, y) on the bottom screen
  E.hash()                              hash of both screens of the picture on show (frame-exact response checks)
  E.ssave(k) / E.sload(k)               in-memory savestate slot k (melonDS) / a temp file (DeSmuME)
  E.r8/r16/r32/w8/w16/w32, E.image()    memory, both screens as one 256x384 picture
  E.hook(pc, ...), E.hooks()            exec hooks: [(frame, pc, r0, r1, r2, r3, lr)] since the last call
Field helpers (any B2-based ROM): gsys / gd / zone / field_ready / boot_continue / teleport."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, struct, sys, tempfile, zlib

KEYS = ['A', 'B', 'SELECT', 'START', 'RIGHT', 'LEFT', 'UP', 'DOWN', 'R', 'L', 'X', 'Y']
GSYS = 0x021410F4


def ram_ok(p):
    return 0x02000000 <= p < 0x02400000


def romkey(rom):
    r = os.path.realpath(rom)
    return f'{r}:{os.path.getmtime(r)}:{os.path.getsize(r)}'


def _raw_save(dsv):
    d = open(dsv, 'rb').read()
    cut = d.find(b'|<--Snip')
    return d[:cut] if cut > 0 else d


class Base:
    frame = 0

    def r16(self, a):
        return self.r8(a) | self.r8(a + 1) << 8

    def r32(self, a):
        return self.r16(a) | self.r16(a + 2) << 16

    def w16(self, a, v):
        self.w8(a, v)
        self.w8(a + 1, v >> 8)

    def w32(self, a, v):
        self.w16(a, v)
        self.w16(a + 2, v >> 16)

    def hold(self, k, n=4):
        self.step(n, (k,) if isinstance(k, str) else k)

    def tap(self, k, n=4, idle=16):
        self.hold(k, n)
        self.step(idle)

    def touch(self, x, y, n=4, idle=16):
        self.step(n, touch=(x, y))
        self.step(idle)

    # --- field (RAM) ---
    def gsys(self):
        g = self.r32(GSYS)
        return g if ram_ok(g) else 0

    def gd(self):
        g = self.gsys()
        d = self.r32(g + 0x1C) if g else 0
        return d if ram_ok(d) else 0

    def zone(self):
        d = self.gd()
        return self.r16(d + 0x114) if d else None

    def event(self):
        g = self.gsys()
        return self.r32(g + 0x18) != 0 if g else True

    def fieldmap(self):
        g = self.gsys()
        f = self.r32(g + 0x20) if g else 0
        return f if ram_ok(f) else 0

    def field_ready(self):
        return self.zone() is not None and not self.event() and self.fieldmap() != 0

    def wait_field(self, maxf=3000, settle=30, tap=None):
        ok = 0
        for i in range(maxf):
            if self.field_ready():
                ok += 1
                if ok >= settle:
                    return True
            else:
                ok = 0
            if tap and i % 20 == 0 and not self.field_ready():
                self.hold(tap, 4)
            else:
                self.step(1)
        return False

    def pos(self):
        d = self.gd()
        if not d:
            return None
        x = struct.unpack('<i', struct.pack('<I', self.r32(d + 0x118)))[0] >> 16
        z = struct.unpack('<i', struct.pack('<I', self.r32(d + 0x120)))[0] >> 16
        return self.r16(d + 0x114), x, z

    def boot_continue(self, maxf=3000, teleport=None):
        """power on -> title -> Continue -> field; teleport=(zone, tx, tz, y): GameData's location rewritten before the
        field is built (feel6/teleport.py)"""
        self.step(300)
        done = False
        for _ in range(maxf):
            gd = self.gd()
            if teleport and gd and not self.fieldmap() and not done:
                zone, tx, tz, y = teleport
                self.w16(gd + 0x114, zone)
                self.w32(gd + 0x118, (tx * 16 + 8) << 12)
                self.w32(gd + 0x11C, (y << 12) & 0xFFFFFFFF)
                self.w32(gd + 0x120, (tz * 16 + 8) << 12)
                done = True
            if self.fieldmap():
                break
            if not self.gsys():
                self.hold('A', 4)
                self.step(6)
            else:
                self.step(1)
        return self.wait_field(2500, settle=40)


class Mel(Base):
    kind = 'mel'

    def __init__(self, rom, dsv=None):
        sys.path.insert(0, RR_MEL)
        import mel as M
        self.M, self.L = M, M.L
        sav = None
        if dsv:
            fd, sav = tempfile.mkstemp(suffix='.sav')
            os.write(fd, _raw_save(dsv) if dsv.endswith('.dsv') else open(dsv, 'rb').read())
            os.close(fd)
        os.environ['NOSPURESET'] = '1'
        self.m = M.Mel(os.path.realpath(rom), sav)
        if sav:
            os.remove(sav)
        self.frame = 0
        self._hooks = False
        self.romkey = romkey(rom)

    def step(self, n=1, keys=(), touch=None):
        km = 0
        for k in keys:
            km |= 1 << KEYS.index(k)
        t, x, y = (1, touch[0], touch[1]) if touch else (0, 0, 0)
        for _ in range(n):
            self.L.ml_frame(km, t, x, y)
            self.frame += 1

    def hash(self):
        return self.L.ml_hash(0) * 0x100000001 ^ self.L.ml_hash(1)

    def ssave(self, k=0):
        self.L.ml_state_mem_save(k)
        self.__dict__.setdefault('_sf', {})[k] = self.frame

    def sload(self, k=0):
        r = self.L.ml_state_mem_load(k)
        assert r == 0, r
        self.frame = self._sf[k]

    def state_file_save(self, path):
        return self.m.save(path)

    def state_file_load(self, path):
        self.L.ml_state_load(os.fsencode(path))

    def r8(self, a):
        return self.m.r8(a)

    def r16(self, a):
        return self.m.r16(a)

    def r32(self, a):
        return self.m.r32(a)

    def read(self, a, n):
        return self.m.read(a, n)

    def w8(self, a, v):
        if 0x02000000 <= a < 0x02400000:
            self.m.ram[a & 0x3FFFFF] = v & 0xFF
        else:
            self.L.ml_write8(a, v & 0xFF)

    def image(self):
        return self.m.image()

    def hook(self, *pcs):
        for p in pcs:
            self.L.ml_hook_add(p & ~1)
        self._hooks = True

    def hooks(self):
        """[(frame, pc, r0, r1, r2, r3, lr, [r0+0x2C], [r0+0x38], [sp+4])]; melonDS logs its own frame counter (NumFrames): mapped to self.frame"""
        if not self._hooks:
            return []
        log = self.m.hook_log()
        nf = self.L.ml_frames()
        out = []
        for e in log:
            pc, r0, r1, r2, r3, lr, sp, fr = e[:8]
            out.append((self.frame - (nf - fr), pc, r0, r1, r2, r3, lr, e[8], e[9], e[11], e))
        return out

    def wav_start(self, path):
        return self.L.ml_wav_start(os.fsencode(path))

    def wav_stop(self):
        return self.L.ml_wav_stop()


class Dsm(Base):
    kind = 'dsm'

    def __init__(self, rom, dsv=None, tag=None):
        """the battery save is DeSmuME's <battery dir>/<rom name>.dsv: the ROM is linked under a unique name (an old
        .dsv of that name is moved aside, never deleted) and dsv copied there"""
        import shutil
        from desmume.emulator import DeSmuME
        from desmume.controls import Keys, keymask
        self.Keys, self.keymask = Keys, keymask
        d = os.path.join(RR_B, 'menuspeed', 'roms')
        os.makedirs(d, exist_ok=True)
        tag = tag or f'{os.getpid()}'
        link = os.path.join(d, f'ms_{tag}.nds')
        if os.path.lexists(link):
            os.remove(link)
        os.symlink(os.path.realpath(rom), link)
        bd = os.path.expanduser(RR_DSV)
        os.makedirs(bd, exist_ok=True)
        mine = os.path.join(bd, f'ms_{tag}.dsv')
        if os.path.exists(mine):
            k = 0
            while os.path.exists(f'{mine}.bak.{k}'):
                k += 1
            os.rename(mine, f'{mine}.bak.{k}')
        if dsv:
            shutil.copy(dsv, mine)
        self.emu = DeSmuME()
        self.emu.open(link)
        self.emu.volume_set(0)
        self.mem = self.emu.memory.unsigned
        self.frame = 0
        self.romkey = romkey(rom)
        self._log = []
        self._tmp = tempfile.mkdtemp(prefix='ms_dst_')
        self._sf = {}

    def step(self, n=1, keys=(), touch=None):
        inp = self.emu.input
        for k in keys:
            inp.keypad_add_key(self.keymask(getattr(self.Keys, 'KEY_' + k)))
        if touch:
            inp.touch_set_pos(*touch)
        for _ in range(n):
            self.emu.cycle(with_joystick=False)
            self.frame += 1
        for k in keys:
            inp.keypad_rm_key(self.keymask(getattr(self.Keys, 'KEY_' + k)))
        if touch:
            inp.touch_release()

    def hash(self):
        return zlib.crc32(self.emu.display_buffer_as_rgbx())

    def ssave(self, k=0):
        self.emu.savestate.save_file(os.path.join(self._tmp, f'{k}.dst'))
        self._sf[k] = self.frame

    def sload(self, k=0):
        self.emu.savestate.load_file(os.path.join(self._tmp, f'{k}.dst'))
        self.frame = self._sf[k]

    def state_file_save(self, path):
        self.emu.savestate.save_file(path)

    def state_file_load(self, path):
        self.emu.savestate.load_file(path)

    def r8(self, a):
        return self.mem[a]

    def read(self, a, n):
        return bytes(self.mem[a:a + n])

    def w8(self, a, v):
        self.mem[a] = v & 0xFF

    def image(self):
        return self.emu.screenshot().convert('RGB')

    def hook(self, *pcs):
        regs = self.emu.memory.register_arm9
        for p in pcs:
            def cb(addr, size, p=p):
                r0, sp = regs.r0, regs.sp
                rd = (lambda a: self.r32(a) if ram_ok(a) else 0)
                self._log.append((self.frame, p & ~1, r0, regs.r1, regs.r2, regs.r3, regs.lr, rd(r0 + 0x2C),
                                  rd(r0 + 0x38), rd(sp + 4), None))
                return True
            self.emu.memory.register_exec(p & ~1, cb)

    def hooks(self):
        out, self._log = self._log, []
        return out


def emu(kind, rom, dsv=None, tag=None):
    return Mel(rom, dsv) if kind == 'mel' else Dsm(rom, dsv, tag)
