#!/usr/bin/env python3
"""Rebuild the vanilla arm9 as stored in the vanilla ROM (BLZ-compressed after the first 16 KiB).

Redux stores the arm9 decompressed, mostly as literal bytes, so the decompressed vanilla image
[0x02004000, 0x0209EC00) can be composed from:
  - pokeblack2 `main` (GAS build) over its range: this also reverts Redux's arm9 edits
  - inside the DSProt glue (0x020166F0-0x02016870), Redux's literal bytes where GAS has
    placeholders for the unresolved DSProt externs
  - everything else (secure area, crt0, libs after main, autoload blocks incl. ITCM): Redux's
    literal bytes, with ITCM from pokeblack2's `itcm`, and copied bytes resolved through the copy
    map (vanilla overlay pieces, or the raw arm9 head itself)
Compressing it with blz (start 0x4000) must give exactly 0x736A4 bytes: the vanilla
_start_ModuleParams records compressed_static_end = 0x020776A4 (pokeblack2 lib/asm/crt0.s).

usage: arm9model.py   -> build/vanilla/arm9_image.bin, build/vanilla/arm9_lz.bin, arm9_lz.json
"""
import json, os, subprocess
import redux_rom as R

RAM, ROM_OFF, END = 0x02004000, 0x4000, 0x0209EC00
COMPRESSED_END = 0x020776A4                 # vanilla _start_ModuleParams.compressed_static_end
DSPROT_GLUE = (0x020166F0, 0x02016870)
ITCM_DATA = 0x0209D760                       # ITCM autoload block 0x0209D740 + 0x20 (itcm.base 0x01FF8020)
BLZ = os.path.join(R.BUILD, 'bin', 'blz')


def build(rom, model=None, verbose=True):
    n = END - RAM
    red = rom.read(ROM_OFF, n)
    m = rom.mask(ROM_OFF, n)
    img = bytearray(n)
    have = bytearray(n)
    for i in range(n):
        if m[i]:
            img[i] = red[i]
            have[i] = 1
    main = R.Vanilla('main')
    mo = main.base - RAM
    for i, b in enumerate(main.data):
        a = main.base + i
        if DSPROT_GLUE[0] <= a < DSPROT_GLUE[1] and m[mo + i]:
            continue
        img[mo + i] = b
        have[mo + i] = 1
    itcm = R.Vanilla('itcm')
    io = ITCM_DATA - RAM
    img[io:io + len(itcm.data)] = itcm.data
    for i in range(len(itcm.data)):
        have[io + i] = 1
    # copied bytes outside main: follow the copy map
    raw_head = 0x4000
    for _ in range(3):
        for i in range(n):
            if have[i]:
                continue
            S = rom.source_offset(ROM_OFF + i)
            if S is None:
                continue
            b = None
            if ROM_OFF <= S < ROM_OFF + raw_head and have[S - ROM_OFF]:
                b = img[S - ROM_OFF]
            elif model is not None:
                b = model.byte(S)
            if b is not None:
                img[i] = b
                have[i] = 1
    holes = [i for i in range(n) if not have[i]]
    # a few bytes were copied from the compressed vanilla arm9 itself: iterate to a fixed point
    self_refs = {}
    for i in holes:
        S = rom.source_offset(ROM_OFF + i)
        if S is not None and ROM_OFF + raw_head <= S < ROM_OFF + COMPRESSED_END - RAM:
            self_refs[i] = S - ROM_OFF
    for _ in range(8):
        lz = compress(bytes(img))
        changed = False
        for i, q in self_refs.items():
            if q < len(lz) and img[i] != lz[q]:
                img[i] = lz[q]
                changed = True
        if not changed:
            break
    holes = [i for i in holes if i not in self_refs]
    return bytes(img), holes


def compress(img):
    os.makedirs(os.path.join(R.BUILD, 'vanilla'), exist_ok=True)
    src = os.path.join(R.BUILD, 'vanilla', 'arm9_image.bin')
    dst = os.path.join(R.BUILD, 'vanilla', 'arm9_lz.bin')
    open(src, 'wb').write(img)
    subprocess.run([BLZ, '-e', src, dst, '0x4000'], check=True)
    return open(dst, 'rb').read()


def main():
    import overlays as O
    rom = R.ReduxRom()
    model = O.VanillaModel(rom, rom.fat(), with_arm9=False)
    img, holes = build(rom, model)
    lz = compress(img)
    body_holes = [h for h in holes if h >= 0x4000]
    res = dict(image=len(img), holes=len(holes), holes_in_compressed_part=len(body_holes),
               hole_addrs=[hex(RAM + h) for h in body_holes[:64]], compressed=len(lz),
               expected=COMPRESSED_END - RAM, size_match=len(lz) == COMPRESSED_END - RAM)
    json.dump(res, open(os.path.join(R.BUILD, 'vanilla', 'arm9_lz.json'), 'w'), indent=1)
    print(json.dumps(res))


if __name__ == '__main__':
    main()
