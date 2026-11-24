"""Small Gen 5 graphics helpers for the qol modules' data-file edits: LZ10 (decode/encode), NCGR tile sheets
(4 / 8 bpp, tiled), NSCR tile maps, NCLR palettes and the Gen 5 NFTR fonts (glyphs only).

    data, packed = unpack(member)          # LZ10/LZ11 -> plain (packed tells how it was stored)
    g = NCGR(data); px = g.tile(i); g.set_tile(i, px); g.encode()
    s = NSCR(data); s.at(tx, ty) / s.put(tx, ty, entry); s.encode()
    f = Font(nftr); px, (left, width, advance) = f.glyph('A')   # 2 bpp: 0 clear, 1 ink, 2 shadow, 3 ...
"""
import struct


# --- LZ10 ---------------------------------------------------------------------------------------

def lz_decode(d):
    t, n = d[0], d[1] | d[2] << 8 | d[3] << 16
    out, i = bytearray(), 4
    while len(out) < n:
        flags = d[i]
        i += 1
        for b in range(8):
            if len(out) >= n:
                break
            if not flags & (0x80 >> b):
                out.append(d[i])
                i += 1
                continue
            if t == 0x10:
                x = d[i] << 8 | d[i + 1]
                i += 2
                ln, disp = (x >> 12) + 3, (x & 0xFFF) + 1
            else:
                h = d[i] >> 4
                if h == 0:
                    ln, disp = ((d[i] & 0xF) << 4 | d[i + 1] >> 4) + 0x11, ((d[i + 1] & 0xF) << 8 | d[i + 2]) + 1
                    i += 3
                elif h == 1:
                    ln = ((d[i] & 0xF) << 12 | d[i + 1] << 4 | d[i + 2] >> 4) + 0x111
                    disp = ((d[i + 2] & 0xF) << 8 | d[i + 3]) + 1
                    i += 4
                else:
                    ln, disp = h + 1, ((d[i] & 0xF) << 8 | d[i + 1]) + 1
                    i += 2
            for _ in range(ln):
                out.append(out[-disp])
    return bytes(out)


def lz10_encode(d):
    """LZ10 (DS BIOS format), longest match within 4 KiB via a 3-byte prefix index (fast enough for 32 KiB).
    The match displacement is >= 2: some decoders (VRAM-safe ones) can't copy from the byte just written."""
    d = bytes(d)
    out = bytearray([0x10, len(d) & 0xFF, len(d) >> 8 & 0xFF, len(d) >> 16 & 0xFF])
    heads = {}
    i, n = 0, len(d)

    def add(p):
        if p + 3 <= n:
            heads.setdefault(d[p:p + 3], []).append(p)

    while i < n:
        flag_at = len(out)
        out.append(0)
        for b in range(8):
            if i >= n:
                break
            best, bdisp = 0, 0
            for p in reversed(heads.get(d[i:i + 3], ())):
                disp = i - p
                if disp > 0x1000:
                    break
                if disp < 2:
                    continue
                ln = 3
                while ln < 18 and i + ln < n and d[i + ln] == d[p + ln]:
                    ln += 1
                if ln > best:
                    best, bdisp = ln, disp
                    if ln == 18:
                        break
            if best >= 3:
                out[flag_at] |= 0x80 >> b
                x = (best - 3) << 12 | (bdisp - 1)
                out += bytes([x >> 8, x & 0xFF])
                for k in range(best):
                    add(i + k)
                i += best
            else:
                out.append(d[i])
                add(i)
                i += 1
    return bytes(out + bytes(-len(out) % 4))


MAGICS = (b'RGCN', b'RCSN', b'RLCN', b'RECN', b'RNAN', b'RTFN')


def unpack(m):
    """NARC member -> (plain data, was LZ-compressed)"""
    if m[:1] in (b'\x10', b'\x11') and bytes(m[4:8]) not in MAGICS:
        return lz_decode(m), True
    return bytes(m), False


def pack(data, packed):
    return lz10_encode(data) if packed else data


# --- NCGR / NSCR / NCLR -------------------------------------------------------------------------

class NCGR:
    def __init__(self, d):
        self.raw = bytes(d)
        off = struct.unpack_from('<H', d, 0xC)[0]
        assert d[off:off + 4] == b'RAHC', 'NCGR: no CHAR section'
        self.off = off
        self.bpp = 4 if struct.unpack_from('<I', d, off + 0xC)[0] == 3 else 8
        self.size = struct.unpack_from('<I', d, off + 0x18)[0]
        self.doff = off + 8 + struct.unpack_from('<I', d, off + 0x1C)[0]
        self.data = bytearray(d[self.doff:self.doff + self.size])
        self.tb = 32 if self.bpp == 4 else 64

    def ntiles(self):
        return len(self.data) // self.tb

    def tile(self, t):
        b = self.data[t * self.tb:(t + 1) * self.tb]
        if self.bpp == 8:
            return [list(b[y * 8:y * 8 + 8]) for y in range(8)]
        return [[(b[y * 4 + x // 2] >> (4 * (x & 1))) & 15 for x in range(8)] for y in range(8)]

    def set_tile(self, t, px):
        if self.bpp == 8:
            b = bytes(v for row in px for v in row)
        else:
            b = bytearray(32)
            for y in range(8):
                for x in range(8):
                    b[y * 4 + x // 2] |= (px[y][x] & 15) << (4 * (x & 1))
        assert t < self.ntiles(), f'NCGR: tile {t} beyond the sheet ({self.ntiles()})'
        self.data[t * self.tb:(t + 1) * self.tb] = b

    def encode(self):
        assert len(self.data) == self.size, 'NCGR: size changed'
        return self.raw[:self.doff] + bytes(self.data) + self.raw[self.doff + self.size:]


class NSCR:
    def __init__(self, d):
        self.raw = bytes(d)
        off = struct.unpack_from('<H', d, 0xC)[0]
        assert d[off:off + 4] == b'NRCS', 'NSCR: no SCRN section'
        self.off = off
        self.w, self.h = struct.unpack_from('<HH', d, off + 8)
        self.size = struct.unpack_from('<I', d, off + 0x10)[0]
        self.m = list(struct.unpack_from(f'<{self.size // 2}H', d, off + 0x14))

    def at(self, tx, ty):
        return self.m[ty * (self.w // 8) + tx]

    def put(self, tx, ty, e):
        self.m[ty * (self.w // 8) + tx] = e

    def encode(self):
        d = bytearray(self.raw)
        struct.pack_into(f'<{len(self.m)}H', d, self.off + 0x14, *self.m)
        return bytes(d)


def tile_px(ncgr, e):
    """8x8 pixels of tile-map entry e (flips applied; palette indices without the entry's palette row)"""
    px = ncgr.tile(e & 0x3FF)
    if e & 0x800:
        px = px[::-1]
    if e & 0x400:
        px = [row[::-1] for row in px]
    return [list(r) for r in px]


def nclr(d):
    """-> [(r, g, b)] (8-bit) of every colour in the palette section"""
    off = struct.unpack_from('<H', d, 0xC)[0]
    size = struct.unpack_from('<I', d, off + 0x10)[0]
    doff = off + 8 + struct.unpack_from('<I', d, off + 0x14)[0]
    n = min(size, len(d) - doff) // 2
    out = []
    for i in range(n):
        c = struct.unpack_from('<H', d, doff + 2 * i)[0]
        out.append(((c & 31) * 255 // 31, (c >> 5 & 31) * 255 // 31, (c >> 10 & 31) * 255 // 31))
    return out


# --- NFTR (Gen 5) -------------------------------------------------------------------------------

class Font:
    """Gen 5 NFTR: each glyph record is (left, width, advance) followed by the 2 bpp cell bitmap."""

    def __init__(self, d):
        self.d = d = bytes(d)
        finf = struct.unpack_from('<H', d, 0xC)[0]
        cglp, _cwdh, cmap = struct.unpack_from('<III', d, finf + 0x10)
        self.cw, self.ch = d[cglp], d[cglp + 1]
        self.gsize = struct.unpack_from('<H', d, cglp + 2)[0]
        self.bpp = d[cglp + 6]
        self.gdata = cglp + 8
        self.cmap = {}
        p = cmap
        while p and p + 12 <= len(d):
            first, last, typ, nxt = struct.unpack_from('<HHHxxI', d, p)
            q = p + 12
            if typ == 0:
                base = struct.unpack_from('<H', d, q)[0]
                for c in range(first, last + 1):
                    self.cmap[c] = base + c - first
            elif typ == 1:
                for c in range(first, last + 1):
                    g = struct.unpack_from('<H', d, q + 2 * (c - first))[0]
                    if g != 0xFFFF:
                        self.cmap[c] = g
            else:
                for k in range(struct.unpack_from('<H', d, q)[0]):
                    c, g = struct.unpack_from('<HH', d, q + 2 + 4 * k)
                    self.cmap[c] = g
            p = nxt

    def glyph(self, ch):
        g = self.cmap[ord(ch)]
        rec = self.d[self.gdata + g * self.gsize:self.gdata + (g + 1) * self.gsize]
        wid, bits = tuple(rec[:3]), rec[3:]
        px = []
        for y in range(self.ch):
            row = []
            for x in range(self.cw):
                i = (y * self.cw + x) * self.bpp
                row.append((bits[i >> 3] >> (8 - self.bpp - (i & 7))) & ((1 << self.bpp) - 1))
            px.append(row)
        return px, wid

    def text(self, s):
        """-> (rows of pixel values, width): s drawn left to right with each glyph's advance"""
        glyphs = [self.glyph(c) for c in s]
        w = sum(a for _, (_, _, a) in glyphs)
        out = [[0] * w for _ in range(self.ch)]
        x = 0
        for px, (left, gw, adv) in glyphs:
            for y in range(self.ch):
                for xx in range(self.cw):
                    if px[y][xx] and 0 <= x + left + xx < w:
                        out[y][x + left + xx] = px[y][xx]
            x += adv
        return out, w
