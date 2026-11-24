"""mlperf.py : ctypes wrapper of the perf benchmark's headless melonDS (perf/melon: libperf.dylib) + B2 field helpers and
the teleport used to make the benchmark's savestates. ML_JIT=1 in the environment (read by ml_init) = JIT on."""
import ctypes, os, tempfile

KEYS = {k: 1 << i for i, k in enumerate(['A', 'B', 'SELECT', 'START', 'RIGHT', 'LEFT', 'UP', 'DOWN', 'R', 'L', 'X', 'Y'])}
GSYS = 0x021410F4
VBLANK_COUNT = 0x027FFC3C           # OS VBlank counter (bumped by the IRQ)
LOOP_FRAMES = 0x0209DA64            # GFL_VBlankUpdate's frame counter: once per main-loop iteration
U64 = ctypes.c_ulonglong


class Melon:
    def __init__(self, lib, rom, sav=None):
        self.L = L = ctypes.CDLL(lib)
        L.ml_init.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        L.ml_frame.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_int, ctypes.c_int]
        L.ml_ram.restype = ctypes.POINTER(ctypes.c_uint8)
        L.ml_hash.restype = ctypes.c_uint32
        for f in ('ml_a9_halt', 'ml_a9_ts', 'ml_prof_halt', 'ml_prof_other'):
            getattr(L, f).restype = U64
        for f in ('ml_state_save', 'ml_state_load', 'ml_prof_dump', 'ml_profB_dump'):
            getattr(L, f).argtypes = [ctypes.c_char_p] + ([ctypes.c_int] if f == 'ml_prof_dump' else [])
        L.ml_wlog.restype = ctypes.POINTER(U64)
        path = None
        if sav:
            data = open(sav, 'rb').read()
            if len(data) not in (1 << 19, 1 << 18, 1 << 20, 1 << 16) and len(data) > 122:
                data = data[:-122]          # DeSmuME .dsv footer
            fd, path = tempfile.mkstemp(suffix='.sav')
            os.write(fd, data)
            os.close(fd)
        r = L.ml_init(rom.encode(), (path or '').encode())
        if path:
            os.remove(path)
        if r:
            raise RuntimeError(f'ml_init {r}')
        self.ram = L.ml_ram()
        self.keys = 0
        self.frame = 0

    def step(self, n=1):
        for _ in range(n):
            self.L.ml_frame(self.keys, 0, 0, 0)
            self.frame += 1

    def press(self, k):
        for x in k.split('+'):
            self.keys |= KEYS[x]

    def hold(self, k, n):
        self.press(k)
        self.step(n)
        self.keys = 0

    def r8(self, a): return self.ram[a & 0x3FFFFF]
    def r16(self, a): return self.r8(a) | self.r8(a + 1) << 8
    def r32(self, a): return self.r16(a) | self.r16(a + 2) << 16

    def s32(self, a):
        v = self.r32(a)
        return v - (1 << 32) if v & 0x80000000 else v

    def w8(self, a, v): self.ram[a & 0x3FFFFF] = v & 0xFF
    def w16(self, a, v): self.w8(a, v); self.w8(a + 1, v >> 8)
    def w32(self, a, v): self.w16(a, v); self.w16(a + 2, v >> 16)
    def ram_bytes(self): return ctypes.string_at(self.ram, 0x400000)

    def a9(self): return self.L.ml_a9_ts(), self.L.ml_a9_halt()
    def jit_on(self): return self.L.ml_jit_on()
    def hash(self, screen=0): return self.L.ml_hash(screen)

    def swapinfo(self):
        g = (ctypes.c_uint32 * 6)()
        self.L.ml_swapinfo(g)
        return tuple(g)

    def screenshot(self, path):
        from PIL import Image
        self.L.ml_fb.restype = ctypes.POINTER(ctypes.c_uint32)
        im = Image.new('RGB', (256, 384))
        for s in range(2):
            buf = ctypes.string_at(self.L.ml_fb(s), 256 * 192 * 4)
            im.paste(Image.frombuffer('RGBA', (256, 192), buf, 'raw', 'BGRA', 0, 1).convert('RGB'), (0, 192 * s))
        im.save(path)

    def set_rtc(self, y, mo, d, h, mi):self.L.ml_set_rtc(y, mo, d, h, mi, 0)
    def state_save(self, p): return self.L.ml_state_save(p.encode())
    def state_load(self, p): return self.L.ml_state_load(p.encode())

    def watch(self, addrs, acts):
        a = (ctypes.c_uint32 * len(addrs))(*addrs)
        b = (ctypes.c_uint32 * len(acts))(*acts)
        self.L.ml_watch_set(a, len(addrs))
        self.L.ml_watch_act(b, len(acts))

    def prof_start(self):
        self.L.ml_prof_start()
        self.L.ml_profB_start()


def ram_ok(p):
    return 0x02000000 <= p < 0x02400000


class Field:
    def __init__(self, m):
        self.m = m

    def gsys(self):
        g = self.m.r32(GSYS)
        return g if ram_ok(g) else 0

    def gd(self):
        g = self.gsys()
        d = self.m.r32(g + 0x1C) if g else 0
        return d if ram_ok(d) else 0

    def zone(self):
        d = self.gd()
        return self.m.r16(d + 0x114) if d else None

    def event(self):
        g = self.gsys()
        return self.m.r32(g + 0x18) != 0 if g else True

    def field(self):
        g = self.gsys()
        f = self.m.r32(g + 0x20) if g else 0
        return f if ram_ok(f) else 0

    def actor(self, uid):
        f = self.field()
        if not f:
            return 0
        sys_ = self.m.r32(f + 0x40)
        if not ram_ok(sys_):
            return 0
        cap, base = self.m.r16(sys_ + 4), self.m.r32(sys_ + 0x1C)
        if not ram_ok(base) or cap > 128:
            return 0
        for i in range(cap):
            a = base + i * 0x100
            if self.m.r32(a) & 1 and self.m.r16(a + 8) == uid:
                return a
        return 0

    def ready(self):
        return self.zone() is not None and not self.event() and self.field() != 0

    def wait_ready(self, maxf=3000, settle=30):
        ok = 0
        for _ in range(maxf):
            if self.ready():
                ok += 1
                if ok >= settle:
                    return True
            else:
                ok = 0
            self.m.step()
        return False


def teleport(m, F, zone, tx, tz, y, season=None, settle=60):
    """Continue the battery save into ZONE at tile (TX, TZ), height Y (world units): at the first frame GameData exists
    (before the field is built), every RAM copy of the saved location (zone + fx32 x/y/z, found by value) is rewritten
    (also the one the Continue map change loads the map matrix from: zones outside the overworld matrix work too);
    SEASON (0 spring .. 3 winter) is written to GameData +0x1C8."""
    m.step(300)
    for _ in range(900):
        gd = F.gd()
        if gd and not F.field():
            break
        if not F.gsys():
            m.hold('A', 4)
            m.step(6)
        else:
            m.step(1)
    gd = F.gd()
    if not gd:
        return False
    z0 = m.r16(gd + 0x114)
    key = bytes(m.r8(gd + 0x118 + i) for i in range(12))
    ram = m.ram_bytes()
    X, Y, Z = (tx * 16 + 8) << 12, y << 12, (tz * 16 + 8) << 12
    p = ram.find(key)
    while p >= 0:
        a = 0x02000000 + p
        m.w32(a, X)
        m.w32(a + 4, Y)
        m.w32(a + 8, Z)
        for zo in (-4, 12):
            if m.r16(a + zo) == z0:
                m.w16(a + zo, zone)
        p = ram.find(key, p + 1)
    # the tile copy (u16 x, u16 y, u32 z) at GameData +0x2FB0, when it holds the saved location
    if m.r16(gd + 0x2FB0) == (key[2] | key[3] << 8):
        m.w16(gd + 0x2FB0, tx)
        m.w16(gd + 0x2FB2, y >> 4)
        m.w32(gd + 0x2FB4, tz)
    if season is not None:
        m.w8(gd + 0x1C8, season)
    for _ in range(600):
        if F.field():
            break
        m.step(1)
    return F.wait_ready(2500, settle=settle)
