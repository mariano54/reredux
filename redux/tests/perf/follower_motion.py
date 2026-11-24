"""Replay the medium-follower tile-boundary wobble in the actual game.

Supply a disposable QA battery save with a living party, never a player save.
The harness copies it through mlperf, cold boots the supplied ROM, moves the
party to a Floccesy street, and changes only the in-memory lead to Charizard.
It records world positions AND the renderer's extra offsets: world positions
alone missed this regression. No emulator state from another ROM is loaded.

Run once with --run and once without it. The old build fails both cases.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / 'ff')]
from mlperf import Melon, Field, teleport
from party import set_species


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--rom', required=True, type=Path)
    ap.add_argument('--lib', required=True, type=Path)
    ap.add_argument('--save', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--species', type=int, default=6)
    args = ap.parse_args()
    os.environ.setdefault('ML_JIT', '1')
    m = Melon(str(args.lib), str(args.rom), str(args.save))
    f = Field(m)
    m.set_rtc(2026, 10, 15, 12, 0)
    assert teleport(m, f, 439, 114, 661, 16, 1), 'QA save did not reach the field'

    class Memory:
        def __getitem__(self, address):
            return m.r8(address)

    h = SimpleNamespace(gd=f.gd, m=Memory(), r32=m.r32, w8=m.w8,
                        w16=m.w16, step=m.step)
    set_species(h, args.species)
    ew = m.r32(f.gd() + 0x1AC)
    for flag in (0x963, 0x5DC):  # Running Shoes, autorun off
        address = ew + 0x35E + (flag >> 3)
        m.w8(address, m.r8(address) | (1 << (flag & 7)))
    m.step(40)
    assert f.actor(0xF8), 'No follower: fixture must have a living party'

    def actor(uid):
        a = f.actor(uid)
        assert a, f'Actor {uid:#x} disappeared'
        raw = m.r8(a + 0x7E)
        offset = raw - 256 if raw >= 128 else raw
        return dict(x=m.s32(a + 0x44) / 4096,
                    wx=m.s32(a + 0x50) / 4096, mx=offset,
                    z=m.s32(a + 0x4C) / 4096,
                    grid_x=m.r16(a + 0x3C))

    rows = []
    for frame in range(90):
        m.keys = (16 | (2 if args.run else 0)) if frame < 70 else 0
        m.step()
        p, q = actor(0xFF), actor(0xF8)
        rows.append(dict(frame=frame, player=p, follower=q,
                         physical_gap=p['x'] - q['x'],
                         visual_gap=p['x'] + p['wx'] + p['mx'] -
                                    q['x'] - q['wx'] - q['mx']))
    # Let the follower catch up after spawning and ease into its intended offset.
    # Then cover several tile boundaries at a steady physical separation.
    sample = rows[24:64]
    physical = [r['physical_gap'] for r in sample]
    visual = [r['visual_gap'] for r in sample]
    report = dict(rom_sha1=hashlib.sha1(args.rom.read_bytes()).hexdigest(),
                  save_sha1=hashlib.sha1(args.save.read_bytes()).hexdigest(),
                  running=args.run, species=args.species, rows=rows,
                  physical_range=[min(physical), max(physical)],
                  visual_range=[min(visual), max(visual)])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    assert sample[-1]['player']['x'] > sample[0]['player']['x'] + 32, 'Blocked QA route'
    assert all(r['player']['z'] == r['follower']['z'] for r in sample), 'Follower not aligned'
    assert max(physical) == min(physical), 'Fixture has not reached steady movement'
    assert max(visual) == min(visual), f'Follower drawing wobbles: {min(visual)}..{max(visual)}'
    print('PASS: steady physical and drawn gap', physical[0], visual[0])


if __name__ == '__main__':
    main()
