#!/usr/bin/env python3
"""Drive DeSmuME (py-desmume) with a button script; load/save states; take screenshots.

  emu_drive.py ROM [--import-sav SAV] [--export-sav SAV] [--load STATE] [--save STATE] [--shot OUT.png] [--shots DIR --every N] SEQ...

SEQ items (run in order):
  A, B, START, SELECT, UP, DOWN, LEFT, RIGHT, L, R, X, Y   tap (held 6 frames, then 14 idle)
  A*40          tap 40 times
  hold:UP:32    hold a key for 32 frames
  wait:300      run 300 idle frames
  touch:X:Y     tap the touch screen at (X, Y)
  shot:NAME     save a screenshot to NAME.png now (relative to --shots dir or cwd)
  peek:ADDR:N   print N bytes at hex ADDR
"""
import argparse, os, sys
from desmume.emulator import DeSmuME
from desmume.controls import Keys, keymask

KEYS = {k: getattr(Keys, 'KEY_' + k) for k in
        ['A', 'B', 'START', 'SELECT', 'UP', 'DOWN', 'LEFT', 'RIGHT', 'L', 'R', 'X', 'Y']}


class Driver:
    def __init__(self, emu, shots=None, every=0):
        self.emu, self.shots, self.every, self.frame = emu, shots, every, 0

    record = None     # directory: save every frame's top screen (for videos)

    def step(self, n=1):
        for _ in range(n):
            self.emu.cycle(with_joystick=False)
            self.frame += 1
            if self.record:
                self.emu.screenshot().crop((0, 0, 256, 192)).save(
                    os.path.join(self.record, f'{self.frame:06d}.png'), compress_level=1)
            if self.every and self.frame % self.every == 0:
                self.shot(f'f{self.frame:06d}')

    def shot(self, name):
        d = self.shots or '.'
        os.makedirs(d, exist_ok=True)
        self.emu.screenshot().save(os.path.join(d, name + '.png'))

    def hold(self, key, frames):
        self.emu.input.keypad_add_key(keymask(KEYS[key]))
        self.step(frames)
        self.emu.input.keypad_rm_key(keymask(KEYS[key]))

    pos_addr = None   # address of a u16 x, u16 z pair (the follower code's debug block)

    def pos(self):
        m = self.emu.memory.unsigned
        a = self.pos_addr
        return m[a] | m[a + 1] << 8, m[a + 2] | m[a + 3] << 8

    def goto(self, tx, tz, max_steps=200):
        """Greedy walk to grid (tx, tz): step along the axis with the larger distance; when a step
        doesn't move, try the other axis, then sidestep perpendicular."""
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
                self.hold(d, 16)
                self.step(4)
                if self.pos() != (x, z):
                    moved = True
                    break
            stuck = 0 if moved else stuck + 1
            if stuck >= 12:   # blocked (or a cutscene took over)
                break
        print('goto gave up at', self.pos(), 'target', (tx, tz))
        return False

    def run(self, item):
        if item.startswith('wait:'):
            self.step(int(item[5:]))
        elif item.startswith('hold:'):
            _, k, n = item.split(':')
            self.hold(k, int(n))
        elif item.startswith('touch:'):
            _, x, y = item.split(':')
            self.emu.input.touch_set_pos(int(x), int(y))
            self.step(6)
            self.emu.input.touch_release()
            self.step(14)
        elif item.startswith('shot:'):
            self.shot(item[5:])
        elif item.startswith('peek:'):
            _, a, n = item.split(':')
            a = int(a, 16)
            print(hex(a), bytes(self.emu.memory.unsigned[a + i] for i in range(int(n))).hex())
        elif item.startswith('goto:'):
            _, x, z = item.split(':')
            self.goto(int(x), int(z))
        else:
            k, _, n = item.partition('*')
            for _ in range(int(n or 1)):
                self.hold(k, 6)
                self.step(14)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('rom')
    ap.add_argument('seq', nargs='*')
    ap.add_argument('--load')
    ap.add_argument('--save')
    ap.add_argument('--shot')
    ap.add_argument('--shots')
    ap.add_argument('--every', type=int, default=0)
    ap.add_argument('--record', help='save every frame (top screen) to this directory')
    ap.add_argument('--pos-addr', help='hex address of the player u16 x, u16 z (for goto:X:Z)')
    ap.add_argument('--import-sav')
    ap.add_argument('--poke-file', action='append', default=[], help='HEXADDR:FILE, written after --load')
    ap.add_argument('--export-sav')
    a = ap.parse_args()
    emu = DeSmuME()
    emu.open(a.rom)
    emu.volume_set(0)
    if a.import_sav:
        assert emu.backup.import_file(a.import_sav), 'import failed'
    if a.load:
        emu.savestate.load_file(a.load)
    for pf in a.poke_file:
        addr, path = pf.split(':', 1)
        addr, blob = int(addr, 16), open(path, 'rb').read()
        for i, b in enumerate(blob):
            emu.memory.unsigned[addr + i] = b
        assert all(emu.memory.unsigned[addr + i] == blob[i] for i in range(0, len(blob), 97)), 'poke failed'
    d = Driver(emu, a.shots, a.every)
    if a.pos_addr:
        d.pos_addr = int(a.pos_addr, 16)
    if a.record:
        os.makedirs(a.record, exist_ok=True)
        d.record = a.record
    for item in a.seq:
        for part in item.split(','):
            if part:
                d.run(part)
    if a.save:
        emu.savestate.save_file(a.save)
    if a.export_sav:
        assert emu.backup.export_file(a.export_sav), 'export failed'
    if a.shot:
        emu.screenshot().save(a.shot)
    print('frames', d.frame)


if __name__ == '__main__':
    sys.exit(main())
