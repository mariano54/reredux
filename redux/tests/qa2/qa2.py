"""qa2.py : library for the extended QA pass (build/scripts/qa2/t_*.py), on top of build/scripts/qa/qa.py.

ROM kinds: 'qa2' = build/qa2/roms/qa2_LANG.nds (build_qa2.py: release modules + rules_test + qol2_test),
'rel' = the release ROM build/out/redux3_LANG.nds. Output build/qa2/<name>/, states build/qa2/states/,
results build/qa2/results.jsonl. Every run gets its own ROM symlink (own DeSmuME battery save).

Extras: script(lines) runs any script commands through the bed test menu's CUSTOM row (bedroom only);
q2 mailbox helpers (language + dex, bike); rules_tst helpers (flags, vars, items); turbo / follower
state readers; rec_frames() to record frames for ballfx_sheet.py."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import json, os, sys
S = f'{RR_T}'
sys.path.insert(0, S + '/qa')
sys.path.insert(0, S + '/qa2')
import qa
B = f'{RR_B}'
qa.QA_DIR = B + '/qa2'
qa.ROMS = B + '/qa2/roms'
qa.STATES = B + '/qa2/states'
_orig_paths = qa.rom_paths


def rom_paths(rom, lang):
    if rom == 'qa2':
        return f'{qa.ROMS}/qa2_{lang}.nds', f'qa2_{lang}', f'{qa.ROMS}/qa2_{lang}.elf'
    return _orig_paths(rom, lang)


qa.rom_paths = rom_paths
from desmume.controls import Keys, keymask
ROWS = ['KIT', 'PATRAT', 'SHINY', 'LILLIPUP', 'TRAINER', 'GIFT', 'ROUTE', 'HEAL', 'CUSTOM']
MARK = b'QA2SCRPT'
END = ['    WorkSetConst 0x8024, 0', '    RTFinishSubEvents', '    ActorUnlockAll', '    VMHalt']
FLAGS = qa.FLAGS
V_DIFF, V_LIMIT, V_CITY, V_DONE, V_DEATHS = 0x4198, 0x4199, 0x419A, 0x4197, 0x41AA


def km(k):
    return keymask(getattr(Keys, 'KEY_' + k))


def assemble(lines):
    sys.path.insert(0, RR_RX + '/tools')
    import gen5script
    return gen5script.assemble('\n'.join(lines) + '\n', gen5script.defsets(B)[None])


def Q2(name, lang='en', rom='qa2', **kw):
    base = qa.QAR(name, lang, rom, **kw)
    base.__class__ = type('Q2', (base.__class__, Q2Mixin), {})
    for f in os.listdir(base.dir):          # shots of an earlier run of this test
        if f.endswith('.png'):
            os.remove(os.path.join(base.dir, f))
    return base


class Q2Mixin:
    # --- custom scripts (bedroom bed menu, row CUSTOM) ---
    def script(self, lines, settle=150, end=True, wait=True):
        """run script commands (gen5script listing lines, no labels across the fragment boundary) from
        the bed menu: they replace the CUSTOM row's buffer in the loaded bed script -> True if found"""
        code = assemble(list(lines) + (END if end else []))
        assert len(code) <= 2048 + 14, len(code)
        if self.pos() != (13, 3):
            self.goto(13, 3)
        self.face('LEFT')
        self.tap('A')
        self.step(settle)
        hits = self.find(MARK)
        for a in hits:
            for i, b in enumerate(code):
                self.w8(a - 6 + i, b)
        self.say('script: buffer hits', [hex(a) for a in hits], 'bytes', len(code))
        for _ in range(ROWS.index('CUSTOM')):
            self.tap('DOWN')
            self.step(10)
        self.tap('A')
        if wait:
            self.wait_free(3000, tap='B')
        return bool(hits)

    def wild(self, species, level=5, flags=0):
        """script wild battle (CallWildBattle: a static encounter) from the bed menu; returns when it started"""
        self.script([f'    CallWildBattle {species}, {level}, {flags}', '    WildBattleIsVictory 0x8010',
                     '    StackPush 0x8010', '    StackPushConst 1', '    StackCmp 1', '    VMJumpIf 255, @w_lose',
                     '    CallWildBattleEnd', '    VMJump @w_end', 'w_lose:', '    CallWildLose', 'w_end:'], wait=False)
        return self.until({'menu'}, 3000, tap='B') == 'menu'

    def txt(self, key):
        return self.texts[key][2]

    def dbg2(self):
        """rules_dbg's later fields"""
        a = self.sym['rules_dbg'] & ~1
        return dict(views=self.r32(a + 52), limit_blocks=self.r32(a + 56), faint_marks=self.r32(a + 60),
                    items_saved=self.r32(a + 64))

    # --- mailboxes ---
    def q2(self, cmd, a=0, b=0, c=0):
        return self.q2cmd(cmd, a, b, c)

    def set_lang(self, slot, lang):
        return self.q2cmd(3, slot, lang)

    def bike(self):
        return self.q2cmd(4)

    def party_n(self):
        return self.q2cmd(5)

    def setflag(self, f, on=1):
        self.test_cmd(3, f, int(bool(on)))

    def setvar(self, v, x):
        self.test_cmd(4, v, x)

    def give(self, item, n=1):
        return self.test_cmd(2, item, n)

    # --- state readers ---
    def turbo(self):
        t = self.sym['turbo_dbg'] & ~1
        return dict(on=self.r8(t), live=self.r8(t + 1), overrun=self.r8(t + 2), field=self.r32(t + 16),
                    battle=self.r32(t + 20), why=self.r8(t + 24))

    def follower(self):
        """(wanted obj, (x, z) of the follower actor or None, raw word 3)"""
        obj = self.r32(self.fdbg + 4)
        v = self.r32(self.fdbg + 12)
        pos = (v & 0xFFF, v >> 16 & 0xFFF) if v and v not in (0xE1, 0xE2, 0xE3) else None
        return obj, pos, v

    def keyinfo(self):
        """KeyInfo (SaveBlock 0x45 + 0x28) decoded: difficulty, city, chamber, obtained/unlocked slots"""
        ki = self.dbg()['ki']
        if not ki:
            return None
        key = self.r32(ki + 0x34)
        dec = lambda off: self.r32(ki + off) ^ key
        diff = {0x31239: 0, 0x15657: 1, 0x49589: 2}.get(dec(0x28), 1)
        tab = lambda a, n: [self.r32(a + 4 * i) for i in range(n)]
        city_t, cham_t = tab(0x0208F9F8, 2), tab(0x0208FA0C, 3)
        obt_t, unl_t = tab(0x0208FA18, 5), tab(0x0208FA2C, 5)
        city = city_t.index(dec(0x2C)) if dec(0x2C) in city_t else 0
        cham = cham_t.index(dec(0x30)) if dec(0x30) in cham_t else 0
        obt = [int(dec(4 * i) == obt_t[i]) for i in range(5)]
        unl = [int(dec(0x14 + 4 * i) == unl_t[i]) for i in range(5)]
        return dict(difficulty=diff, city=city, chamber=cham, obtained=obt, unlocked=unl)

    def rules_flags(self):
        return {k: self.flag(v) for k, v in FLAGS.items()}

    def player_actor(self):
        """the player's field actor (uid 0xFF) or 0: GSYS +0x20 field, field +0x40 actor system (+4 count,
        +0x1C actors, stride 0x100; actor +0 flags bit 0 in use, +8 uid)"""
        g = self.gsys()
        f = self.r32(g + 0x20) if g else 0
        if not (0x02000000 <= f < 0x02400000):
            return 0
        sys_ = self.r32(f + 0x40)
        if not (0x02000000 <= sys_ < 0x02400000):
            return 0
        n, base = self.r16(sys_ + 4), self.r32(sys_ + 0x1C)
        for i in range(min(n, 128)):
            a = base + 0x100 * i
            if self.r32(a) & 1 and self.r16(a + 8) == 0xFF:
                return a
        return 0

    def wpos(self):
        """player world x, z in tiles (fx32 world units: 16 per tile)"""
        a = self.player_actor()
        if not a:
            return None
        sx = lambda v: v - (1 << 32) if v & 0x80000000 else v
        return sx(self.r32(a + 0x44)) / 65536.0, sx(self.r32(a + 0x4C)) / 65536.0

    def move_measure(self, d, frames, keys=(), rec=None, every=2):
        """hold d (+keys) for `frames`; per frame: world position and turbo state -> dict(frames/tile over the
        moving frames, tiles, turbo frames, overrun drops (turbo on, extra tick skipped), extra field ticks)"""
        for k in (d,) + tuple(keys):
            self.emu.input.keypad_add_key(km(k))
        t0 = self.turbo()
        v0 = self.r32(0x027FFC3C)
        p0 = self.wpos()
        dist, on, overruns, last, first_mv, last_mv = 0.0, 0, 0, p0, None, None
        for i in range(frames):
            self.step(1)
            if rec and i % every == 0:
                self.emu.screenshot().save(os.path.join(rec, f'{self.frame:06d}.png'), compress_level=1)
            p = self.wpos()
            t = self.turbo()
            if p and last:
                dd = abs(p[0] - last[0]) + abs(p[1] - last[1])
                if dd > 0:
                    dist += dd
                    first_mv = i if first_mv is None else first_mv
                    last_mv = i
            last = p
            if t['on']:
                on += 1
                overruns += t['overrun']
        for k in (d,) + tuple(keys):
            self.emu.input.keypad_rm_key(km(k))
        v1 = self.r32(0x027FFC3C)
        self.step(20)
        t1 = self.turbo()
        span = (last_mv - first_mv) if first_mv is not None else 0
        return dict(fpt=round(span / (dist - 1 / 16), 2) if dist > 0.5 else None, tiles=round(dist, 2),
                    turbo_frames=on, overrun_frames=overruns, extra_field=t1['field'] - t0['field'],
                    vblanks=v1 - v0)

    def turbo_set(self, on):
        """tap R until turbo_dbg.on == on (R only toggles where turbo can run)"""
        for _ in range(3):
            if self.turbo()['on'] == on:
                return True
            self.tap('R')
            self.step(10)
        return self.turbo()['on'] == on

    def field_yesno(self):
        """the field YES/NO box (top screen, right edge) is up"""
        p = self.emu.screenshot().convert('RGB').getpixel
        return p((250, 110)) == (248, 248, 248) and p((253, 110)) == (0, 0, 0)

    def pages_until_yesno(self, tag=None, n=24, wait=90):
        """A through message pages until the field YES/NO shows -> pages pressed (None: never)"""
        for i in range(n):
            if self.field_yesno():
                return i
            if tag:
                self.snap(f'{tag}_{i}')
            self.tap('A')
            self.step(wait)
        return i if self.field_yesno() else None

    def rec_frames(self, path):
        os.makedirs(path, exist_ok=True)
        self.rec = path

    def hold_keys(self, keys, n):
        for k in keys:
            self.emu.input.keypad_add_key(km(k))
        self.step(n)
        for k in keys:
            self.emu.input.keypad_rm_key(km(k))
