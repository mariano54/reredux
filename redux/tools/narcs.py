#!/usr/bin/env python3
"""Inspect Redux's data archives (NARC) from the decoded patch.

A NARC is: header, BTAF (start/end per subfile), BTNF, GMIF (concatenated subfile data). Subfiles
Redux rewrote are literal bytes in the patch, so they are fully known even without a ROM; unchanged
subfiles are copies from vanilla and stay unknown.

usage: narcs.py                 summary of every changed NARC
       narcs.py a/0/0/3 [out]   list subfiles of one NARC (and dump fully known ones to out/)
"""
import json, os, struct, sys
import redux_rom as R


def solve_count(rom, s, e):
    """Section headers are usually copied from vanilla (unknown), so solve for the subfile count:
    with a 16-byte NARC header, 12-byte BTAF header, 16-byte BTNF (no names) and 8-byte GMIF header,
    the last BTAF entry's end must equal the GMIF data size (= rest of the file, maybe padded)."""
    btaf = s + 16
    for count in range(1, (e - s) // 8):
        data = btaf + 12 + 8 * count + 16 + 8
        if data > e:
            break
        last = btaf + 12 + 8 * (count - 1)
        if not rom.known(last, 8):
            continue
        fs, fe = struct.unpack('<II', rom.read(last, 8))
        if fs <= fe and 0 <= (e - data) - fe <= 3:
            return count, data
    return None, None


def parse(rom, s, e):
    """Return (subfiles, info). subfiles = [(index, abs_start, abs_end, known_fraction)]."""
    btaf = s + 16
    if rom.known(btaf, 12) and rom.read(btaf, 4) == b'BTAF':
        bsize, count = struct.unpack('<II', rom.read(btaf + 4, 8))
        btnf = btaf + bsize
        if not rom.known(btnf + 4, 4):
            return None, 'BTNF size unknown'
        data = btnf + struct.unpack('<I', rom.read(btnf + 4, 4))[0] + 8
    else:
        count, data = solve_count(rom, s, e)
        if count is None:
            return None, 'layout not solved'
    out = []
    for i in range(count):
        a = btaf + 12 + 8 * i
        if not rom.known(a, 8):
            out.append((i, None, None, None))
            continue
        fs, fe = struct.unpack('<II', rom.read(a, 8))
        n = fe - fs
        k = sum(rom.mask(data + fs, n)) / n if n else 1.0
        out.append((i, data + fs, data + fe, k))
    return out, f'{count} subfiles'


def main():
    rom = R.ReduxRom()
    fat = rom.fat()
    if len(sys.argv) > 1:
        want = sys.argv[1].replace('/', '\\')
        outdir = sys.argv[2] if len(sys.argv) > 2 else None
        for name, s, e in fat:
            if name == want:
                subs, info = parse(rom, s, e)
                print(name, info)
                for i, a, b, k in subs or []:
                    if a is None:
                        print(f'  {i:4d} entry unknown')
                        continue
                    print(f'  {i:4d} {b - a:7d} B  known {k:6.1%}')
                    if outdir and k == 1.0:
                        os.makedirs(outdir, exist_ok=True)
                        with open(os.path.join(outdir, f'{i:04d}.bin'), 'wb') as f:
                            f.write(rom.read(a, b - a))
        return
    rows = []
    for name, s, e in fat[R.NUM_OVERLAYS:]:
        if e - s <= 0 or not any(rom.mask(s, e - s)):
            continue
        subs, info = parse(rom, s, e)
        if subs is None:
            rows.append((name, e - s, info, None, None, None))
            continue
        full = sum(1 for x in subs if x[3] == 1.0)
        part = sum(1 for x in subs if x[3] is not None and 0 < x[3] < 1)
        unk = sum(1 for x in subs if x[3] is None or x[3] == 0)
        rows.append((name, e - s, info, full, part, unk))
    print(f"{'file':24s} {'size':>10s}  {'info':18s} {'full':>6s} {'part':>6s} {'unknown':>8s}")
    for r in rows:
        print(f'{r[0]:24s} {r[1]:10d}  {r[2]:18s} {str(r[3]):>6s} {str(r[4]):>6s} {str(r[5]):>8s}')


if __name__ == '__main__':
    main()
