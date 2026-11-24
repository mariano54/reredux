#!/usr/bin/env python3
"""recover_overlays.py N...: rebuild Redux overlay N from its literal bytes plus copies filled from
the vanilla ROM model, decompress, and report how it compares with vanilla.

Writes build/overlays/redux_overlay_N.bin (decompressed Redux overlay, at Redux's RAM base).
"""
import json, os, struct, sys
import redux_rom as R, overlays as O


def taint_decode(buf, hole):
    """BLZ decode that also returns a per-output-byte taint mask: 1 where the byte depends on a hole
    in the stream (an unfilled literal, a token with an unfilled byte, or a copy of tainted output)."""
    n = len(buf)
    bt, inc = struct.unpack('<II', buf[-8:])
    enc, hl = bt & 0xFFFFFF, bt >> 24
    out = bytearray(buf + bytes(inc))
    taint = bytearray(hole) + bytearray(inc)
    src, dst, lim = n - hl, len(out), n - enc
    flag_tainted = False
    while src > lim:
        src -= 1
        fl, flag_tainted = buf[src], bool(hole[src])
        for _ in range(8):
            if src <= lim:
                break
            if fl & 0x80:
                if src - 2 < lim:
                    break
                src -= 2
                v = buf[src] | buf[src + 1] << 8
                t = flag_tainted or hole[src] or hole[src + 1]
                disp, ln = (v & 0xFFF) + 3, (v >> 12) + 3
                for _ in range(ln):
                    if dst <= 0:
                        break
                    dst -= 1
                    ok = dst + disp < len(out)
                    out[dst] = out[dst + disp] if ok else 0
                    taint[dst] = 1 if (t or not ok or taint[dst + disp]) else 0
            elif dst > 0:
                src -= 1
                dst -= 1
                out[dst] = buf[src]
                taint[dst] = 1 if (flag_tainted or hole[src]) else 0
            fl = (fl << 1) & 0xFF
    return bytes(out), bytes(taint)


def recover(n, rom, fat, model):
    van = R.Vanilla(f'overlay_{n}')
    ent = rom.overlay_entry(n)
    ram = ent['ram'] if all(ent['known'][4:8]) else van.base
    shift = van.base - ram          # Redux bytes before vanilla's first byte (ov167: 0x180)
    _, s, e = fat[n]
    data = rom.read(s, e - s)
    m = rom.mask(s, e - s)
    unknown = [p for p in range(len(data)) if not m[p]]
    srcs = {p: S for p in unknown if (S := rom.source_offset(s + p)) is not None}
    filled, nf, nu = O.fill_model(data, unknown, srcs, model)
    holes = [p for p in unknown if model.byte(srcs.get(p, -1)) is None]
    hole_mask = bytearray(len(data))
    for p in holes:
        hole_mask[p] = 1
    _, bad = O.lenient_decode(filled)
    if bad >= 1 << 30:              # not compressed in Redux
        dec, taint, bad = filled, bytes(hole_mask), 0
    else:
        dec, taint = taint_decode(filled, hole_mask)
    k = min(len(van.data), len(dec) - shift)
    diff = sum(1 for i in range(k) if dec[shift + i] != van.data[i] and not taint[shift + i])
    res = dict(overlay=n, redux_ram=f'{ram:#010x}', file=len(data), literal=len(data) - len(unknown),
               filled=nf, holes=nu, bad_tokens=bad, size=len(dec), vanilla_size=len(van.data),
               front=shift, tainted_output=sum(taint), diff_vs_vanilla_clean=diff)
    os.makedirs(O.OUT, exist_ok=True)
    with open(os.path.join(O.OUT, f'redux_overlay_{n}.bin'), 'wb') as f:
        f.write(dec)
    with open(os.path.join(O.OUT, f'redux_overlay_{n}.taint'), 'wb') as f:
        f.write(taint)
    return res


def main():
    rom = R.ReduxRom()
    fat = rom.fat()
    model = O.VanillaModel(rom, fat)
    print(json.dumps({'arm9_piece': model.arm9}), flush=True)
    for a in sys.argv[1:]:
        print(json.dumps(recover(int(a), rom, fat, model)), flush=True)


if __name__ == '__main__':
    main()
