"""rt.py : DeSmuME driver for the Redux 3.0 rules tests (library; see the t_*.py scenarios).

RT(rom, tag) opens ROM, reads build/qol/<tag>/qol_map.json (rules_dbg, rules_tst addresses) and
the follower ELF next to the ROM's base for follow_dbg (player position). Helpers: tap/hold/wait,
shots (DIR/NAME.png) and per-frame recording (DIR/rec/NNNNNN.png for ballfx_sheet.py), RAM
access to GameData/EventWork (flags, vars), rules_dbg, the KeyInfo difficulty, field/event state.
"""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
from rrenv import skip_frames, no_skip, RENDER_TAIL  # noqa: E402,F401  (RR_SKIP_RENDER: draw only what is looked at)
import json, os, struct, subprocess, sys
sys.path.insert(0, f'{RR_RX}/tools')
from desmume.emulator import DeSmuME
from desmume.controls import Keys, keymask

RX = f'{RR_RX}'
B = RR_B
OUT = B + '/rules/out'
G_GAMESYSTEM = 0x021410F4
DBG_FIELDS = ('magic wild_starts last_area last_species last_block last_shiny last_static area_marked '
              'bag_refused last_refuse_msg released graved trainer_items_denied lose_kind blackouts '
              'nick_forced cmd_calls last_cmd last_arg last_gd').split()
DIFF_TABLE = {0x31239: 0, 0x15657: 1, 0x49589: 2}


def nm(elf, name):
    out = subprocess.run(['arm-none-eabi-nm', elf], capture_output=True, text=True).stdout
    for l in out.splitlines():
        a, t, n = l.split()
        if n == name:
            return int(a, 16)
    return None


class RT:
    def __init__(self, rom, tag, elf, name, record=False):
        # DeSmuME keeps battery saves in ~/.config/desmume/<rom name>.dsv: move an old one aside so
        # every run is a fresh game (never deleted: renamed to .dsv.bak.N)
        dsv = os.path.expanduser(f'{RR_DSV}/' + os.path.splitext(os.path.basename(rom))[0] + '.dsv')
        if os.path.exists(dsv):
            k = 0
            while os.path.exists(f'{dsv}.bak.{k}'):
                k += 1
            os.rename(dsv, f'{dsv}.bak.{k}')
            print('moved old battery save aside:', f'{dsv}.bak.{k}')
        self.emu = DeSmuME()
        self.emu.open(rom)
        self.emu.volume_set(0)
        self.m = self.emu.memory.unsigned
        q = json.load(open(f'{B}/qol/{tag}/qol_map.json'))
        self.sym = q['symbols']
        self.texts = q.get('texts', {})
        self.fdbg = nm(elf, 'follow_dbg')
        self.dir = os.path.join(OUT, name)
        os.makedirs(self.dir, exist_ok=True)
        self.frame = 0
        self.rec = os.path.join(self.dir, 'rec') if record else None
        if self.rec:
            os.makedirs(self.rec, exist_ok=True)
        self.log = open(os.path.join(self.dir, 'log.txt'), 'w')

    # --- input ---
    def step(self, n=1):
        ll = os.environ.get('FEEL_LL_FORCE')        # field-feel: force turbo.c's low-latency updates (2) / off (1)
        lla = (self.sym.get('lowlat_dbg', 0) & ~1) if ll and isinstance(getattr(self, 'sym', None), dict) else 0
        if self.rec:
            no_skip(self.emu)
        elif n > RENDER_TAIL:
            skip_frames(self.emu, n - RENDER_TAIL)
        for _ in range(n):
            if lla:
                self.emu.memory.unsigned[lla] = int(ll)
            self.emu.cycle(with_joystick=False)
            self.frame += 1
            if self.rec:
                self.emu.screenshot().save(os.path.join(self.rec, f'{self.frame:06d}.png'), compress_level=1)

    def hold(self, k, n):
        self.emu.input.keypad_add_key(keymask(getattr(Keys, 'KEY_' + k)))
        self.step(n)
        self.emu.input.keypad_rm_key(keymask(getattr(Keys, 'KEY_' + k)))

    def tap(self, k, n=1, idle=14):
        for _ in range(n):
            self.hold(k, 6)
            self.step(idle)

    def touch(self, x, y):
        self.emu.input.touch_set_pos(x, y)
        self.step(6)
        self.emu.input.touch_release()
        self.step(14)

    def shot(self, name):
        p = os.path.join(self.dir, name + '.png')
        self.emu.screenshot().save(p)
        self.say(f'shot {name} @{self.frame}')
        return p

    def say(self, *a):
        s = ' '.join(str(x) for x in a)
        print(s, flush=True)
        self.log.write(s + '\n')
        self.log.flush()

    def save(self, name):
        self.emu.savestate.save_file(os.path.join(OUT, name + '.dst'))

    def load(self, name):
        self.emu.savestate.load_file(os.path.join(OUT, name + '.dst'))

    # --- memory ---
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
        return self.r32(G_GAMESYSTEM)

    def gd(self):
        g = self.gsys()
        return self.r32(g + 0x1C) if 0x02000000 <= g < 0x02400000 else 0

    def ew(self):
        gd = self.gd()
        return self.r32(gd + 0x1AC) if gd else 0

    def flag(self, f):
        ew = self.ew()
        return self.r8(ew + 0x35E + (f >> 3)) >> (f & 7) & 1

    def set_flag(self, f, on=True):
        ew = self.ew()
        a = ew + 0x35E + (f >> 3)
        v = self.r8(a)
        self.w8(a, v | 1 << (f & 7) if on else v & ~(1 << (f & 7)))

    def var(self, v):
        return self.r16(self.ew() + 2 * (v - 0x4000))

    def set_var(self, v, x):
        self.w16(self.ew() + 2 * (v - 0x4000), x)

    def zone(self):
        gd = self.gd()
        return self.r16(gd + 0x114) if gd else None

    def event_running(self):
        g = self.gsys()
        return self.r32(g + 0x18) != 0 if g else True

    def pos(self):
        v = self.r32(self.fdbg + 8)
        return v & 0xFFFF, v >> 16

    def dbg(self):
        a = self.sym['rules_dbg']
        vals = [self.r32(a)] + [self.r16(a + 4 + 2 * i) for i in range(18)] + [self.r32(a + 40)]
        d = dict(zip(DBG_FIELDS, vals))
        d['ki'], d['difficulty'] = self.r32(a + 44), self.r32(a + 48)
        return d

    def stored_difficulty(self):
        """KeyInfo difficulty as saved (decoded like GetGameDifficulty) and the key slots' states"""
        ki = self.dbg()['ki']
        if not ki:
            return None
        key = self.r32(ki + 0x34)
        raw = self.r32(ki + 0x28) ^ key
        obtained = [self.r32(ki + 4 * i) ^ key for i in range(5)]
        unlocked = [self.r32(ki + 0x14 + 4 * i) ^ key for i in range(5)]
        return DIFF_TABLE.get(raw, 1), obtained, unlocked

    def tst(self):
        a = self.sym.get('rules_tst')
        if a is None:
            return {}
        names = 'magic cmd a b result party_count deaths boxes grave'.split()
        d = dict(zip(names, [self.r32(a + 4 * i) for i in range(len(names))]))
        base = a + 4 * len(names)
        d['party'] = [(self.r16(base + 4 * i), self.r16(base + 4 * i + 2)) for i in range(6)][:d['party_count'] if d['party_count'] <= 6 else 0]
        return d

    def test_cmd(self, cmd, a=0, b=0, frames=10):
        t = self.sym['rules_tst']
        self.w32(t + 8, a)
        self.w32(t + 12, b)
        self.w32(t + 4, cmd)
        self.step(frames)
        assert self.r32(t + 4) == 0, f'test cmd {cmd} not run'
        return self.r32(t + 16)

    def flags_str(self):
        names = ['release', 'grave', 'gameover', 'first', 'dupes', 'shiny', 'nick', 'statics', 'noitems',
                 'notritems', 'speed_off', 'turbo_off']
        return ' '.join(f'{n}={self.flag(0x5D0 + i)}' for i, n in enumerate(names))

    def areas(self):
        return [l for l in range(160) if self.var(0x41A0 + (l >> 4)) >> (l & 15) & 1]

    def field_ready(self):
        """field running, no event (script) running"""
        return self.zone() is not None and not self.event_running()

    def wait_field(self, max_frames=3000, tap=None, settle=30):
        """step (tapping `tap` every 20 frames) until the field is free for `settle` frames"""
        ok = 0
        for i in range(max_frames):
            if self.field_ready():
                ok += 1
                if ok >= settle:
                    return True
            else:
                ok = 0
            if ok < settle - RENDER_TAIL and i < max_frames - 6 - RENDER_TAIL:
                skip_frames(self.emu, 1)            # can't return within RENDER_TAIL frames: nobody looks
            if tap and i % 20 == 0 and not self.field_ready():
                self.hold(tap, 6)
            else:
                self.step()
        return False

    def goto(self, tx, tz, max_steps=120):
        stuck = 0
        for _ in range(max_steps):
            x, z = self.pos()
            if (x, z) == (tx, tz):
                return True
            dx, dz = tx - x, tz - z
            horiz = ('RIGHT' if dx > 0 else 'LEFT') if dx else None
            vert = ('DOWN' if dz > 0 else 'UP') if dz else None
            order = [d for d in ((horiz, vert) if abs(dx) >= abs(dz) else (vert, horiz)) if d]
            if stuck >= 2:
                side = {'UP': 'LEFT', 'DOWN': 'RIGHT', 'LEFT': 'UP', 'RIGHT': 'DOWN'}
                order = [side[order[0]]] * (stuck - 1) + order
            moved = False
            for d in order:
                # field-feel: hold until the tile changes (one step at any walk / run speed), not 16 frames
                self.emu.input.keypad_add_key(keymask(getattr(Keys, 'KEY_' + d)))
                for _i in range(24):
                    self.step(1)
                    if self.pos() != (x, z):
                        break
                self.emu.input.keypad_rm_key(keymask(getattr(Keys, 'KEY_' + d)))
                self.step(8)
                if self.pos() != (x, z):
                    moved = True
                    break
            stuck = 0 if moved else stuck + 1
            if stuck >= 12:
                break
        return self.pos() == (tx, tz)

    def face(self, d):
        self.hold(d, 3)
        self.step(10)

    # --- KeyInfo: difficulty stored in the save (SaveBlock 0x45 + 0x28) ---
    def difficulty(self):
        t = self.tst()
        if t.get('ki'):
            ki = t['ki']
            raw = self.r32(ki + 0x28) ^ self.r32(ki + 0x34)
            return DIFF_TABLE.get(raw, 1), t['difficulty']
        return None


def boot_to_menu(rt, max_taps=700):
    """power on -> new game -> tap A through the intro until the field (zone 427) is up"""
    rt.step(600)
    rt.tap('START')
    rt.step(100)
    rt.tap('A')
    rt.step(200)
    n = 0
    while rt.zone() != 427 and n < max_taps:
        rt.tap('A')
        n += 1
    rt.say('field (zone', rt.zone(), ') after', n, 'A taps, frame', rt.frame)
    return rt.zone() is not None
