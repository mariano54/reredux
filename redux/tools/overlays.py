#!/usr/bin/env python3
"""Recover Redux's (BLZ-compressed) overlays and diff them against vanilla.

Redux's compressed overlay files are partly literal bytes and partly copies of the *vanilla
compressed* file. We rebuild the vanilla compressed file by compressing the GAS-built vanilla image
with tools/blz.c, locate it in the vanilla ROM from the copy offsets, fill the copied bytes, and
decompress. If blz.c reproduces Nintendo's compressor, decompression succeeds and the result differs
from vanilla only where Redux changed something.

usage: overlays.py [N ...]
"""
import bisect, collections, json, os, struct, subprocess, sys
import redux_rom as R

BLZ = os.path.join(R.BUILD, 'bin', 'blz')
OUT = os.path.join(R.BUILD, 'overlays')


def blz(mode, data):
    os.makedirs(OUT, exist_ok=True)
    i, o = os.path.join(OUT, 'tmp.in'), os.path.join(OUT, 'tmp.out')
    open(i, 'wb').write(data)
    r = subprocess.run([BLZ, mode, i, o], capture_output=True, text=True)
    if r.returncode:
        return None, r.stderr.strip()
    return open(o, 'rb').read(), None


def lenient_decode(buf):
    """BLZ decode that clamps out-of-range tokens instead of failing; returns (out, bad_tokens)."""
    n = len(buf)
    bt, inc = struct.unpack('<II', buf[-8:])
    enc, hl = bt & 0xFFFFFF, bt >> 24
    if not (8 <= hl <= enc <= n) or inc > 4 * n:
        return bytes(buf), 1 << 30   # footer is not a BLZ footer
    out = bytearray(buf + bytes(inc))
    src, dst, lim, bad = n - hl, len(out), n - enc, 0
    while src > lim:
        src -= 1
        fl = buf[src]
        for _ in range(8):
            if src <= lim:
                break
            if fl & 0x80:
                if src - 2 < lim:
                    bad += 1
                    break
                src -= 2
                v = buf[src] | buf[src + 1] << 8
                disp, ln = (v & 0xFFF) + 3, (v >> 12) + 3
                for _ in range(ln):
                    if dst <= 0:
                        break
                    dst -= 1
                    if dst + disp < len(out):
                        out[dst] = out[dst + disp]
                    else:
                        bad += 1
            elif dst > 0:
                src -= 1
                dst -= 1
                out[dst] = buf[src]
            fl = (fl << 1) & 0xFF
    return bytes(out), bad + abs(dst - 0 if dst > 0 else 0)


class VanillaModel:
    """Byte-exact pieces of the vanilla ROM we can rebuild: every overlay at its vanilla offset
    (BLZ-compressed with blz.c, or raw where vanilla stored it raw) and the arm9's raw head.

    Vanilla offsets come from Redux's own copy instructions: the first copied bytes of each Redux
    overlay file point at the start of the same vanilla file (all 0x200-aligned). A file is
    trusted only when its size fits the gap to the next file exactly."""
    def __init__(self, rom, fat, with_arm9=True):
        have = {int(f[8:-2]) for f in os.listdir(os.path.join(R.PB2, 'asm'))
                if f.startswith('overlay_') and f.endswith('.s')}
        starts = {}
        for n in range(R.NUM_OVERLAYS):
            _, s, e = fat[n]
            c = collections.Counter()
            for p in range(min(e - s, 4096)):
                if not rom.known(s + p):
                    S = rom.source_offset(s + p)
                    if S is not None and (S - p) % 0x200 == 0:
                        c[S - p] += 1
            if c:
                starts[n] = c.most_common(1)[0][0]
        self.pieces = []   # (vanilla_start, bytes)
        self.layout = {}
        align = lambda x: (x + 0x1FF) & ~0x1FF
        # overlays with no start evidence (Redux rewrote their head, e.g. 167): previous start + size
        for n in range(1, R.NUM_OVERLAYS):
            if n not in starts and n - 1 in starts and n - 1 in have:
                v = R.Vanilla(f'overlay_{n - 1}')
                c, _ = blz('-e', v.data)
                nxt = starts[n - 1] + align(len(c))
                if n + 1 not in starts or nxt < starts[n + 1]:
                    starts[n] = nxt
        for n in sorted(starts):
            if n not in have:
                continue
            van = R.Vanilla(f'overlay_{n}')
            if not van.meta.get('verified'):
                self.layout[n] = (starts[n], 'unverified-image')   # e.g. DSProt-encrypted code
                continue
            nxt = min((starts[m] for m in starts if starts[m] > starts[n]), default=None)
            comp, _ = blz('-e', van.data)
            gap = nxt - starts[n] if nxt else None
            _, s, e = fat[n]
            untouched = not any(rom.mask(s, e - s))
            if untouched:
                # Tinke copies untouched files verbatim: the size must match exactly
                if len(comp) == e - s:
                    data, kind = comp, 'blz'
                elif len(van.data) == e - s:
                    data, kind = van.data, 'raw'
                else:
                    self.layout[n] = (starts[n], 'blz-size-mismatch')
                    continue
            elif gap is None or align(len(comp)) == gap:
                data, kind = comp, 'blz~'    # Redux changed the file; only the gap can be checked
            elif align(len(van.data)) == gap:
                data, kind = van.data, 'raw~'
            else:
                self.layout[n] = (starts[n], 'gap-mismatch')
                continue
            self.layout[n] = (starts[n], kind)
            self.pieces.append((starts[n], data))
        main = R.Vanilla('main')   # arm9 raw head (vanilla arm9 is BLZ-compressed after 16 KiB)
        head = 0x02008000 - main.base
        self.pieces.append((R.ARM9_ROM + (main.base - R.ARM9_RAM), main.data[:head]))
        self.pieces.sort()
        self._starts = [p[0] for p in self.pieces]
        self.arm9 = None
        if with_arm9:
            # the whole compressed vanilla arm9 (see arm9model.py); replaces the raw-head piece
            import arm9model
            img, holes = arm9model.build(rom, self)
            lz = arm9model.compress(img)
            self.arm9 = dict(size=len(lz), size_match=len(lz) == arm9model.COMPRESSED_END - R.ARM9_RAM,
                             holes=len(holes))
            if self.arm9['size_match']:
                self.pieces = [p for p in self.pieces if p[0] >= 0x10000] + [(R.ARM9_ROM, lz)]
        self.pieces.sort()
        self._starts = [p[0] for p in self.pieces]

    def byte(self, off):
        i = bisect.bisect_right(self._starts, off) - 1
        if i >= 0:
            s, d = self.pieces[i]
            if off - s < len(d):
                return d[off - s]
        return None


def fill_model(data0, unknown, srcs, model):
    data = bytearray(data0)
    filled = unfilled = 0
    for p in unknown:
        S = srcs.get(p)
        b = None if S is None else model.byte(S)
        if b is None:
            unfilled += 1
        else:
            data[p] = b
            filled += 1
    return bytes(data), filled, unfilled


def fill(data0, unknown, srcs, comp, vstart):
    """Fill copied bytes: q = S - vstart into our vanilla compressed file. A copy whose source we
    could not decode inherits the shift of the nearest decoded byte before it."""
    data = bytearray(data0)
    filled = unfilled = 0
    shift = None
    for p in unknown:
        S = srcs.get(p)
        if S is not None:
            shift = S - vstart - p
        q = None if shift is None else p + shift
        if q is not None and 0 <= q < len(comp):
            data[p] = comp[q]
            filled += 1
        else:
            unfilled += 1
    return bytes(data), filled, unfilled


def recover(rom, fat, n, ram_shift=0):
    """ram_shift: Redux RAM base - vanilla RAM base (ov167 grew 0x180 at the front)."""
    name, s, e = fat[n]
    van = R.Vanilla(f'overlay_{n}')
    data = rom.read(s, e - s)
    mask = rom.mask(s, e - s)
    unknown = [p for p in range(len(data)) if not mask[p]]
    srcs = {}
    deltas = collections.Counter()
    for p in unknown:
        S = rom.source_offset(s + p)
        if S is not None:
            srcs[p] = S
            deltas[S - p] += 1
    comp, err = blz('-e', van.data)
    res = dict(overlay=n, file=len(data), unknown=len(unknown), vanilla_image=len(van.data),
               vanilla_compressed=len(comp) if comp else None)
    if comp is None or not deltas:
        res['error'] = err or 'no copies'
        return res, None
    # vanilla files are 0x200-aligned in the ROM; try every aligned start near the main copy offset
    centre = deltas.most_common(1)[0][0]
    best = None
    for vstart in range((centre - 0x1000) & ~0x1FF, centre + 0x1000, 0x200):
        cand, filled, unfilled = fill(data, unknown, srcs, comp, vstart)
        dec, bad = lenient_decode(cand)
        off = -ram_shift
        k = min(len(dec) - off, len(van.data))
        diff = sum(1 for i in range(k) if dec[off + i] != van.data[i]) if k > 0 else len(van.data)
        if best is None or diff < best[0]:
            best = (diff, vstart, filled, unfilled, dec, bad)
    if best is None:
        res['error'] = 'no start decodes'
        return res, None
    diff, vstart, filled, unfilled, dec, bad = best
    res.update(vstart=vstart, filled=filled, unfilled=unfilled, decompressed=len(dec), bad_tokens=bad, diff_vs_vanilla=diff)
    return res, dec


def main():
    rom = R.ReduxRom()
    fat = rom.fat()
    ns = [int(x) for x in sys.argv[1:]] or [255]
    for n in ns:
        van = R.Vanilla(f'overlay_{n}')
        ent = rom.overlay_entry(n)
        ram = ent['ram'] if all(ent['known'][4:8]) else van.base
        res, dec = recover(rom, fat, n, ram - van.base)
        res['redux_ram'] = f'{ram:#010x}'
        if dec is not None:
            open(os.path.join(OUT, f'redux_overlay_{n}.bin'), 'wb').write(dec)
        print(json.dumps(res))


if __name__ == '__main__':
    main()
