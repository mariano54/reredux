#!/usr/bin/env python3
"""Headless boot test with DeSmuME (py-desmume): run a ROM, press buttons on a schedule, save
screenshots. Needs `pip install py-desmume pillow` (run with that interpreter).

  boot_test.py ROM OUTDIR [--frames N]

Default schedule: let the intro play, tap START/A through the title screen and into the menu,
saving a screenshot every few seconds. Exit code 1 if the screen never changes (no boot).
"""
import argparse, hashlib, os, sys
from desmume.emulator import DeSmuME
from desmume.controls import Keys, keymask

# (frame, key) taps; ~60 frames per second
TAPS = [(600, 'START'), (700, 'A'), (900, 'START'), (1000, 'A'), (1200, 'A'), (1400, 'A'), (1600, 'A'),
        (1800, 'A'), (2000, 'A'), (2200, 'A'), (2400, 'A'), (2600, 'A')]
SHOTS = [120, 300, 500, 650, 800, 1000, 1300, 1600, 2000, 2400, 2800]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('rom')
    ap.add_argument('out')
    ap.add_argument('--frames', type=int, default=2900)
    ap.add_argument('--every', type=int, default=0, help='also save a screenshot every N frames')
    a = ap.parse_args()
    global SHOTS
    if a.every:
        SHOTS = sorted(set(SHOTS) | set(range(a.every, a.frames, a.every)))
    os.makedirs(a.out, exist_ok=True)
    emu = DeSmuME()
    emu.open(a.rom)
    emu.volume_set(0)
    taps = {f: k for f, k in TAPS}
    held = None
    hashes = set()
    for f in range(a.frames):
        if held and f == held[0]:
            emu.input.keypad_rm_key(keymask(getattr(Keys, 'KEY_' + held[1])))
            held = None
        if f in taps:
            emu.input.keypad_add_key(keymask(getattr(Keys, 'KEY_' + taps[f])))
            held = (f + 6, taps[f])
        emu.cycle(with_joystick=False)
        if f in SHOTS:
            img = emu.screenshot()
            img.save(os.path.join(a.out, f'frame_{f:05d}.png'))
            hashes.add(hashlib.sha1(img.tobytes()).hexdigest())
    print(f'{a.rom}: {len(SHOTS)} screenshots, {len(hashes)} distinct')
    return 0 if len(hashes) > 2 else 1


if __name__ == '__main__':
    sys.exit(main())
