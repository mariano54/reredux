#!/usr/bin/env python3
"""Check build/bin/blz against Nintendo's compressor without a ROM.

Untouched overlays are copied verbatim by Tinke, so a Redux file whose bytes are all copies has
exactly the size of the vanilla compressed file. blz must reproduce that size for every untouched
overlay whose image matches pokeblack2's SHA-1, and decompress its own output back to the image.

usage: blz_check.py            (from redux/tools)
"""
import os, subprocess, sys, tempfile
import redux_rom as R

BLZ = os.path.join(R.BUILD, 'bin', 'blz')
RAW_IN_VANILLA = {169}   # stored uncompressed by the vanilla build although compressible


def compress(data, tmp):
    i, o = os.path.join(tmp, 'i'), os.path.join(tmp, 'o')
    open(i, 'wb').write(data)
    subprocess.run([BLZ, '-e', i, o], check=True)
    c = open(o, 'rb').read()
    if c == data:
        return c, data   # stored raw
    subprocess.run([BLZ, '-d', o, i], check=True)
    return c, open(i, 'rb').read()


def main():
    rom = R.ReduxRom()
    fat = rom.fat()
    ok, bad, rt = 0, [], 0
    with tempfile.TemporaryDirectory() as tmp:
        for n in range(R.NUM_OVERLAYS):
            if not os.path.exists(os.path.join(R.BUILD, 'vanilla', f'overlay_{n}.json')):
                continue
            van = R.Vanilla(f'overlay_{n}')
            if not van.meta.get('verified') or n in RAW_IN_VANILLA or 205 <= n <= 207:
                continue   # 205-207: their FAT entries were copied from vanilla, sizes unknown
            _, s, e = fat[n]
            if any(rom.mask(s, e - s)):
                continue
            comp, back = compress(van.data, tmp)
            rt += back == van.data
            if len(comp) == e - s:
                ok += 1
            else:
                bad.append((n, len(comp) - (e - s)))
    print(f'size matches: {ok}/{ok + len(bad)}; round trips: {rt}/{ok + len(bad)}')
    if bad:
        print('mismatches (overlay: ours - Nintendo):', ' '.join(f'{n}:{d:+d}' for n, d in bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
