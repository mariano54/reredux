"""Shared helpers for the rules battle tests (bedroom test menu of rules_test.py)."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, subprocess, sys
from rt import RT, OUT

B = f'{RR_B}'
ROWS = ['KIT', 'PATRAT', 'SHINY', 'LILLIPUP', 'TRAINER', 'GIFT', 'ROUTE', 'HEAL']
F = dict(release=0x5D0, grave=0x5D1, gameover=0x5D2, first=0x5D3, dupes=0x5D4, shiny=0x5D5, nick=0x5D6,
         statics=0x5D7, noitems=0x5D8, notritems=0x5D9)


class T(RT):
    def __init__(self, lang, name, record=False):
        v = os.environ.get('RULES_VARIANT', 'rules_test')     # e.g. nohooks (build_nohooks.py)
        super().__init__(f'{B}/rules/rules_{lang}_{v}.nds', f'rules_{lang}_{v}',
                         f'{B}/rules/{lang}_follow.elf', name, record)
        self.lang = lang
        self.fails = []
        self.n = 0

    def snap(self, tag):
        self.n += 1
        return self.shot(f'{self.n:02d}_{tag}')

    def check(self, what, got, want):
        ok = got == want
        self.say(('OK  ' if ok else 'FAIL'), what, 'got', got, 'want', want)
        if not ok:
            self.fails.append(what)
        return ok

    def bed(self, row, settle=150):
        """walk to the bed, open the test menu, pick ROWS[row]"""
        if self.pos() != (13, 3):
            self.goto(13, 3)
        self.face('LEFT')
        self.tap('A')
        self.step(settle)
        for _ in range(ROWS.index(row)):
            self.tap('DOWN')
            self.step(10)
        self.tap('A')

    def wait_free(self, frames=3000, tap=None):
        return self.wait_field(frames, tap=tap, settle=40)

    # --- battle UI (bottom screen touch coordinates; detection by pixels of the full 256x384 shot) ---
    def ui(self):
        im = self.emu.screenshot().convert('RGB')
        p = im.getpixel
        if p((215, 357)) == (112, 216, 48):
            return 'menu'                     # FIGHT / BAG / RUN / POKEMON
        if p((128, 242))[0] > 200 and p((240, 212))[0] > 100 and p((240, 212))[1] < 40:
            return 'yesno'
        if p((40, 252)) == (24, 104, 96):
            return 'name'
        return None

    def until(self, want, frames=3000, tap='A', every=20):
        """step until ui() in want (tapping `tap` every `every` frames meanwhile) -> state or None.
        Waiting for only a yes/no (the battle's nickname question) with tap A: the text is advanced by touching the touch screen's empty top-left corner
        instead, so a yes/no that takes input a few frames before ui() sees it is never answered by the wait
        (an A there picked YES: timing-dependent, e.g. after battleexit / the capture fix moved the frames)."""
        for i in range(0, frames, every):
            s = self.ui()
            if s in want:
                return s
            if tap == 'A' and set(want) == {'yesno'} and i % (every * 2) == 0:
                self.emu.input.touch_set_pos(2, 2)
                self.step(4)
                self.emu.input.touch_release()
                self.step(every - 4)
            elif tap and i % (every * 2) == 0:
                self.tap(tap, idle=every - 6)
            else:
                self.step(every)
        return None

    def bag_use(self, pocket, slot=0, tag=''):
        """battle menu -> Bag -> pocket ('hp', 'balls') -> item slot -> USE"""
        self.touch(40, 165)
        self.step(60)
        self.touch(*{'hp': (65, 40), 'balls': (190, 40), 'status': (65, 115), 'battle': (190, 115)}[pocket])
        self.step(60)
        self.touch(65 + 125 * (slot % 2), 30 + 50 * (slot // 2))
        self.step(60)
        self.touch(128, 175)
        self.step(90)
        if tag:
            self.snap(tag)

    def bag_close(self):
        """refused item: Bag open on the item -> back to the battle menu"""
        self.tap('A')                           # dismiss the refusal message
        self.step(40)
        for _ in range(4):
            if self.ui() == 'menu':
                return True
            self.touch(232, 175)
            self.step(50)
        return self.ui() == 'menu'

    def run_away(self, tag=''):
        for _ in range(6):                      # "Can't escape!" -> the menu comes back: try again
            self.touch(128, 170)
            self.step(30)
            if tag:
                self.step(60)
                self.snap(tag)
                tag = ''
            if self.until({'menu'}, 400, tap='B') != 'menu':
                break
        return self.wait_free(2500, tap='B')

    def fight(self, move=0):
        self.touch(128, 95)
        self.step(40)
        self.touch(65 + 125 * (move % 2), 50 + 60 * (move // 2))

    def name_entry(self, letter=(113, 98)):
        """type one letter, OK"""
        self.touch(*letter)
        self.step(20)
        self.touch(200, 172)
        self.step(60)

    def finish(self):
        self.say('RESULT', 'PASS' if not self.fails else 'FAIL ' + ', '.join(self.fails))
        subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'r3_sheet.py'),
                        self.dir, os.path.join(OUT, os.path.basename(self.dir) + '_sheet.png')])


def both(rt, name):
    """both screens (256x384) for UI exploration"""
    return rt.shot(name)
