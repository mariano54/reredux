"""bxlib.py : battle-exit timing harness (DeSmuME / py-desmume) for any B2 ROM (US-code ROMs get hooks).

Bx(rom, name, us=True, fresh_save=True|False|path) opens ROM through a per-run symlink build/battleexit/roms/<name>.nds
(own battery save <battery dir>/<name>.dsv; an old one is moved aside, never deleted; fresh_save=PATH copies
that .dsv in first: Continue tests). Per frame it records: master brightness of both screens, the main-loop
CPU scanline count (VCOUNT when the main loop enters its VBlank wait) and loop iterations, GameEvent
callbacks run (callback, state), GFL_FadeSet calls, overlay loads, BGM calls, the field/event state.
"""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import json, os, shutil, struct, sys
from desmume.emulator import DeSmuME
from desmume.controls import Keys, keymask

RX = f'{RR_RX}'
B = RR_B
OUT = B + '/battleexit'
GSYS = 0x021410F4
NAMES = {}


def names():
    """W2 names for B2 addresses (w2b2map.tsv) -> {addr & ~1: name}"""
    if not NAMES:
        p = os.environ.get('RR_W2B2MAP') or os.path.join(RR_B, 'ext', 'w2b2map.tsv')
        for l in (open(p) if os.path.exists(p) else []):
            r = l.rstrip('\n').split('\t')
            if len(r) > 3 and not r[1].startswith(('loc_', 'off_', 'dword_', 'locret', 'word_', 'byte_', 'unk_', 'jpt_', 'def_')):
                NAMES.setdefault(int(r[3], 16) & ~1, r[1])
        NAMES.update({0x02168BAC: 'EventBattleCall_Callback'})
    return NAMES


def nm(a):
    return names().get(a & ~1, '%08X' % a)


class Bx:
    def __init__(self, rom, name, us=True, save=None, record=None, qol_map=None):
        self.alias = {}
        if qol_map and os.path.exists(qol_map):
            sym = json.load(open(qol_map))['symbols']
            for n, orig in (('bx_battlecall', 0x02168BAD), ('bx_fadewait', 0x0202FF19)):
                if n in sym:
                    self.alias[sym[n] | 1] = orig
        os.makedirs(OUT + '/roms', exist_ok=True)
        link = f'{OUT}/roms/int_{name}.nds'
        if os.path.lexists(link):
            os.remove(link)
        os.symlink(rom, link)
        dsv = os.path.expanduser(f'{RR_DSV}/int_{name}.dsv')
        if os.path.exists(dsv):
            k = 0
            while os.path.exists(f'{dsv}.bak.{k}'):
                k += 1
            os.rename(dsv, f'{dsv}.bak.{k}')
        if save:
            shutil.copy(save, dsv)
        self.name, self.us, self.dsv = name, us, dsv
        self.emu = DeSmuME()
        self.emu.open(link)
        self.emu.volume_set(0)
        self.m = self.emu.memory.unsigned
        self.dir = os.path.join(OUT, name)
        os.makedirs(self.dir, exist_ok=True)
        self.log = open(os.path.join(self.dir, 'log.txt'), 'w')
        self.frame = 0
        self.rows = []          # per-frame records (only while tracing)
        self.tracing = False
        self.rec = record
        self.cur = dict(ev=[], fade=[], ovl=[], bgm=[], loops=0, vc=[])
        self.battles = 0
        if us:
            self._hooks()

    # --- hooks (US code) ---------------------------------------------------------------------------
    def _hooks(self):
        mem = self.emu.memory
        r = mem.register_arm9

        def ev(a, s):
            cb = self.r32(r.r0 + 4)
            cb = self.alias.get(cb, cb)
            if cb == 0x02168BAD:
                self.battles += 1
            if self.tracing:
                self.cur['ev'].append((cb, self.r32(r.r0 + 8)))

        def fade(a, s):
            if self.tracing:
                self.cur['fade'].append((r.r0, r.r1, r.r2, r.r3 if r.r3 < 0x80000000 else r.r3 - (1 << 32)))

        def ovl(a, s):
            if self.tracing:
                self.cur['ovl'].append(r.r1)

        def wait(a, s):
            if r.r0 == 1 and r.r1 == 1:
                self.cur['loops'] += 1
                self.cur['vc'].append(self.m.read_short(0x04000006) & 0x1FF)

        def bgm(tag):
            def f(a, s):
                if self.tracing:
                    self.cur['bgm'].append((tag, r.r0, r.r1))
            return f
        mem.register_exec(0x02016CF8, ev, 2)          # GameEvent_RunCallback
        mem.register_exec(0x0204E060, fade, 2)        # GFL_FadeSet(mode, from, to, wait)
        mem.register_exec(0x020712B0, ovl, 2)         # FS_LoadOverlay(target, id)
        mem.register_exec(0x02079BB0, wait, 4)        # OS_WaitIrq (ARM)
        for a, t in ((0x02005DF4, 'play'), (0x02005E10, 'stop'), (0x02005EA0, 'fadeout'), (0x02005E68, 'fadein'),
                     (0x02005ED4, 'push'), (0x02005F0C, 'pop'), (0x02005E74, 'fadeinex')):
            mem.register_exec(a, bgm(t), 2)

    def hook(self, addr, tag, fn=None):
        """log tag in this frame's record whenever addr runs (Thumb addr: pass it without bit 0)"""
        def f(a, s):
            if self.tracing:
                self.cur.setdefault('tags', []).append(tag if fn is None else (tag, fn(self)))
        self.emu.memory.register_exec(addr, f, 2)

    # --- frames ------------------------------------------------------------------------------------
    def step(self, n=1):
        for _ in range(n):
            self.emu.cycle(with_joystick=False)
            self.frame += 1
            if self.tracing:
                row = dict(f=self.frame, bt=self.m.read_short(0x0400006C), bb=self.m.read_short(0x0400106C),
                           **self.cur)
                if self.us:
                    row.update(ev_run=self.event_running(), zone=self.zone())
                self.rows.append(row)
                if self.rec:
                    self.emu.screenshot().save(os.path.join(self.rec, f'{self.frame:06d}.png'), compress_level=1)
            self.cur = dict(ev=[], fade=[], ovl=[], bgm=[], loops=0, vc=[])

    def trace(self, on=True, rec=None):
        self.tracing = on
        if rec is not None:
            os.makedirs(rec, exist_ok=True)
            for f in os.listdir(rec):
                if f.endswith('.png'):
                    os.remove(os.path.join(rec, f))
            self.rec = rec
        if not on:
            self.rec = None

    def press(self, k):
        self.emu.input.keypad_add_key(keymask(getattr(Keys, 'KEY_' + k)))

    def release(self, k):
        self.emu.input.keypad_rm_key(keymask(getattr(Keys, 'KEY_' + k)))

    def hold(self, k, n):
        self.press(k)
        self.step(n)
        self.release(k)

    def tap(self, k, n=1, idle=14):
        for _ in range(n):
            self.hold(k, 6)
            self.step(idle)

    def touch(self, x, y, idle=14):
        self.emu.input.touch_set_pos(x, y)
        self.step(6)
        self.emu.input.touch_release()
        self.step(idle)

    def shot(self, tag):
        p = os.path.join(self.dir, f'{self.frame:06d}_{tag}.png')
        self.emu.screenshot().save(p)
        return p

    def say(self, *a):
        s = ' '.join(str(x) for x in a)
        print(s, flush=True)
        self.log.write(s + '\n')
        self.log.flush()

    def save_state(self, path):
        self.emu.savestate.save_file(path)

    def load_state(self, path):
        self.emu.savestate.load_file(path)

    # --- memory ------------------------------------------------------------------------------------
    def r8(self, a):
        return self.m[a]

    def r16(self, a):
        return self.m[a] | self.m[a + 1] << 8

    def r32(self, a):
        return self.r16(a) | self.r16(a + 2) << 16

    def w8(self, a, v):
        self.m[a] = v & 0xFF

    def w16(self, a, v):
        self.w8(a, v)
        self.w8(a + 1, v >> 8)

    def w32(self, a, v):
        self.w16(a, v)
        self.w16(a + 2, v >> 16)

    def gsys(self):
        return self.r32(GSYS)

    def gd(self):
        g = self.gsys()
        return self.r32(g + 0x1C) if 0x02000000 <= g < 0x02400000 else 0

    def zone(self):
        gd = self.gd()
        return self.r16(gd + 0x114) if gd else None

    def event_running(self):
        g = self.gsys()
        return self.r32(g + 0x18) != 0 if 0x02000000 <= g < 0x02400000 else True

    def ew(self):
        gd = self.gd()
        return self.r32(gd + 0x1AC) if gd else 0

    def flag(self, f):
        return self.r8(self.ew() + 0x35E + (f >> 3)) >> (f & 7) & 1

    def set_flag(self, f, on=True):
        a = self.ew() + 0x35E + (f >> 3)
        v = self.r8(a)
        self.w8(a, v | 1 << (f & 7) if on else v & ~(1 << (f & 7)))

    def normal(self):
        return not (self.m.read_short(0x0400006C) & 0x1F) and not (self.m.read_short(0x0400106C) & 0x1F)

    def dump(self, path=None):
        path = path or os.path.join(self.dir, 'trace.json')
        json.dump(self.rows, open(path, 'w'))
        return path


def bright(v):
    """master brightness register -> signed level (-16 black .. 0 .. +16 white)"""
    mode, lv = v >> 14 & 3, min(v & 0x1F, 16)
    return lv if mode == 1 else -lv if mode == 2 else 0


def summarize(rows, out=None):
    """timeline lines: frame, brightness top/bottom, loops, vcount, events (named), fades, overlays, bgm"""
    lines = []
    prev_ev = None
    for r in rows:
        evs = tuple(dict.fromkeys(f'{nm(cb)}:{st}' for cb, st in r['ev']))
        bits = []
        if evs != prev_ev:
            bits.append('ev ' + ' '.join(evs))
            prev_ev = evs
        if r['fade']:
            bits.append('FADE ' + ' '.join('%d:%d>%d w%d' % f for f in r['fade']))
        if r['ovl']:
            bits.append('OVL ' + ' '.join(str(o) for o in r['ovl']))
        if r['bgm']:
            bits.append('BGM ' + ' '.join('%s(%x,%x)' % b for b in r['bgm']))
        if r.get('tags'):
            bits.append('TAG ' + ' '.join(str(t) for t in r['tags']))
        lines.append('%6d b%+3d/%+3d L%d vc%-8s er%d z%s %s' % (
            r['f'], bright(r['bt']), bright(r['bb']), r['loops'], ','.join(str(v) for v in r['vc']),
            int(r.get('ev_run', 0)), r.get('zone'), ' | '.join(bits)))
    if out:
        open(out, 'w').write('\n'.join(lines) + '\n')
    return lines
