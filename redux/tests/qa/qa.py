"""qa.py : DeSmuME driver for the Redux 3.0 final integration QA (library), on top of qol2/qt.py (Q) and
rules/tcommon.py (battle UI helpers).

QA(name, lang, rom='rel'|'test', run=None, keep_save=False)
  rel  : the release ROM build/out/redux3_LANG.nds (qol_map build/qol/LANG/, follower ELF build/redux3/LANG_follow.elf)
  test : build/qa/roms/qa_test_LANG.nds = the release follower ROM + every release module + rules_test + qol2_test
         (build/scripts/qa/build_test.py; qol_map build/qol/qa_test_LANG/)
Every run opens its own symlink build/qa/roms/<rom>_LANG_<run>.nds so DeSmuME's battery save
(<battery dir>/<that name>.dsv) is per run; an old one is moved aside (never deleted) unless keep_save.
Output: build/qa/<name>/ (log.txt, NN_tag.png shots), states build/qa/states/<rom>_LANG_<state>.dst,
results build/qa/results.jsonl, contact sheets build/qa/<name>_sheet.png."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import json, os, subprocess, sys
S = f'{RR_T}'
sys.path.insert(0, S + '/qol2')
sys.path.insert(0, S + '/rules')
import rt as RTM
from rt import RT
import qt
import tcommon

B = f'{RR_B}'
QA_DIR = B + '/qa'
ROMS = QA_DIR + '/roms'
STATES = QA_DIR + '/states'
FLAGS = dict(release=0x5D0, grave=0x5D1, gameover=0x5D2, first=0x5D3, dupes=0x5D4, shiny=0x5D5, nick=0x5D6,
             statics=0x5D7, noitems=0x5D8, notritems=0x5D9, speed_off=0x5DA, turbo_off=0x5DB,
             autorun_off=0x5DC, quicksave=0x5DD, quicksurf=0x5DE)


def rom_paths(rom, lang):
    if rom == 'rel':
        return f'{B}/out/redux3_{lang}.nds', lang, f'{B}/redux3/{lang}_follow.elf'
    return f'{ROMS}/qa_test_{lang}.nds', f'qa_test_{lang}', f'{ROMS}/qa_test_{lang}.elf'


class QA(qt.Q):
    def __init__(self, name, lang='en', rom='rel', run=None, keep_save=False, record=False):
        os.makedirs(ROMS, exist_ok=True)
        os.makedirs(STATES, exist_ok=True)
        run = run or name
        target, tag, elf = rom_paths(rom, lang)
        link = f'{ROMS}/{rom}_{lang}_{run}.nds'
        if not os.path.lexists(link):
            os.symlink(target, link)
        RTM.OUT = QA_DIR
        if keep_save:
            from desmume.emulator import DeSmuME
            self.emu = DeSmuME()
            self.emu.open(link)
            self.emu.volume_set(0)
            self.m = self.emu.memory.unsigned
            qm = json.load(open(f'{B}/qol/{tag}/qol_map.json'))
            self.sym, self.texts = qm['symbols'], qm.get('texts', {})
            self.fdbg = RTM.nm(elf, 'follow_dbg')
            self.dir = os.path.join(QA_DIR, name)
            os.makedirs(self.dir, exist_ok=True)
            self.frame, self.rec = 0, None
            self.log = open(os.path.join(self.dir, 'log.txt'), 'w')
        else:
            RT.__init__(self, link, tag, elf, name, record)
            self.dir = os.path.join(QA_DIR, name)
        self.lang, self.kind, self.romkind = lang, rom, rom
        self.cpokes, self.events, self.fails, self.n = [], [], [], 0
        self.say('rom', link, '->', target)

    @staticmethod
    def dsv(rom, lang, run):
        return os.path.expanduser(f'{RR_DSV}/{rom}_{lang}_{run}.dsv')

    def save(self, name):
        self.emu.savestate.save_file(f'{STATES}/{self.romkind}_{self.lang}_{name}.dst')
        self.say('state saved', name)

    def load(self, name, rom=None):
        self.emu.savestate.load_file(f'{STATES}/{rom or self.romkind}_{self.lang}_{name}.dst')
        self.say('state loaded', name)

    def keyinfo(self):
        """KeyInfo (SaveBlock 0x45 + 0x28) decoded: difficulty, city (0 Black City), chamber, obtained/unlocked
        key slots (0 Easy, 1 Challenge, 2 City, 3/4 chamber keys)"""
        ki = self.dbg()['ki']
        if not ki:
            return None
        key = self.r32(ki + 0x34)
        dec = lambda off: self.r32(ki + off) ^ key
        tab = lambda a, n: [self.r32(a + 4 * i) for i in range(n)]
        city_t, cham_t, obt_t, unl_t = tab(0x0208F9F8, 2), tab(0x0208FA0C, 3), tab(0x0208FA18, 5), tab(0x0208FA2C, 5)
        return dict(difficulty={0x31239: 0, 0x15657: 1, 0x49589: 2}.get(dec(0x28), 1),
                    city=city_t.index(dec(0x2C)) if dec(0x2C) in city_t else 0,
                    chamber=cham_t.index(dec(0x30)) if dec(0x30) in cham_t else 0,
                    obtained=[int(dec(4 * i) == obt_t[i]) for i in range(5)],
                    unlocked=[int(dec(0x14 + 4 * i) == unl_t[i]) for i in range(5)])

    def flags(self, *names):
        return {k: self.flag(FLAGS[k]) for k in (names or FLAGS)}

    def result(self, extra=None):
        self.say('RESULT', 'PASS' if not self.fails else 'FAIL ' + ', '.join(self.fails))
        with open(os.path.join(QA_DIR, 'results.jsonl'), 'a') as f:
            f.write(json.dumps(dict(test=os.path.basename(self.dir), lang=self.lang, rom=self.romkind,
                                    fails=self.fails, **(extra or {}))) + '\n')
        return not self.fails

    def sheet(self, src=None, out=None, both=False):
        src = src or self.dir
        out = out or os.path.join(QA_DIR, os.path.basename(src.rstrip('/')) + '_sheet.png')
        script = os.path.join(S, 'qa', 'sheet.py')
        subprocess.run([sys.executable, script, src, out] + (['--both'] if both else []))
        self.say('sheet', out)
        return out

    # --- driving ---------------------------------------------------------------------------------
    def free_for(self, frames=3000, tap='A', settle=40):
        """tap `tap` every 20 frames while an event runs, until the field is free for `settle` frames"""
        return self.wait_field(frames, tap=tap, settle=settle)

    def walk(self, d, tiles=1, frames=8):
        """hold a direction for `tiles` * frames (auto-run: 8 f/tile)"""
        self.hold(d, tiles * frames)
        self.step(6)

    def ram_word(self, a):
        return self.r32(a)

    def path(self, tx, tz, extra_block=()):
        """BFS on the matrix-0 permission map (perm.py) from the player's tile to (tx, tz) -> [(x, z), ...]"""
        import perm
        from collections import deque
        perm.set_zone(self.zone())
        s = self.pos()
        prev = {s: None}
        dq = deque([s])
        while dq:
            c = dq.popleft()
            if c == (tx, tz):
                break
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (c[0] + dx, c[1] + dz)
                if n in prev or n in extra_block:
                    continue
                if n != (tx, tz) and not perm.walkable(*n):
                    continue
                if abs(n[0] - s[0]) > 80 or abs(n[1] - s[1]) > 80:
                    continue
                prev[n] = c
                dq.append(n)
        if (tx, tz) not in prev:
            return None
        out, c = [], (tx, tz)
        while c != s:
            out.append(c)
            c = prev[c]
        return out[::-1]

    def nav(self, tx, tz, tries=4):
        """walk the BFS path tile by tile (holding the direction until the tile changes); a tile that can't
        be entered (NPC, event) is avoided on the next try -> reached?"""
        blocked = set()
        for _ in range(tries):
            p = self.path(tx, tz, blocked)
            if p is None:
                self.say('nav: no path to', (tx, tz), 'from', self.pos(), 'blocked', sorted(blocked))
                return False
            ok = True
            for nx, nz in p:
                x, z = self.pos()
                d = 'RIGHT' if nx > x else 'LEFT' if nx < x else 'DOWN' if nz > z else 'UP'
                self.emu.input.keypad_add_key(qt.RTM.keymask(getattr(qt.RTM.Keys, 'KEY_' + d)))
                for i in range(30):
                    self.step(1)
                    if self.pos() != (x, z):
                        break
                self.emu.input.keypad_rm_key(qt.RTM.keymask(getattr(qt.RTM.Keys, 'KEY_' + d)))
                if self.pos() != (nx, nz):
                    if self.event_running():
                        self.say('nav: event at', self.pos())
                        return False
                    self.step(8)
                    if self.pos() == (nx, nz):
                        continue
                    blocked.add((nx, nz))
                    ok = False
                    break
            if ok or self.pos() == (tx, tz):
                self.step(8)
                return self.pos() == (tx, tz)
        return self.pos() == (tx, tz)


def QAR(*a, **kw):
    """QA + the rules tests' battle helpers (bed menu, ui(), until(), bag_use(), run_away(), fight(), name_entry())"""
    class _QAR(QA, tcommon.T):
        def ui(self):
            s = tcommon.T.ui(self)
            if s is None:
                # tcommon's yes/no test reads a pixel of the white "YES" glyph (EN only); the layout check
                # (red band, dark button interiors) works in both languages
                p = self.emu.screenshot().convert('RGB').getpixel
                if p((240, 212)) == (128, 8, 8) and p((128, 212)) == (32, 32, 32) and p((128, 270)) == (32, 32, 32):
                    return 'yesno'
            return s
    return _QAR(*a, **kw)
