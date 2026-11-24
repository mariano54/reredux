#!/usr/bin/env python3
"""Overworld Pokémon sprites for followers: B2W2 NSBTX codec + Pokémon Essentials sheet converter.

B2 field Pokémon sprites (a/0/4/8, registry a/0/4/7, species table a/2/0/8) are BTX0 files with one
4bpp (16-colour, index 0 transparent) texture per frame and one palette:
  ctrl 14: 8 textures 32x32  = up0 up1 down0 down1 left0 left1 right0 right1
  ctrl 13: 6 textures (32x32 or 64x64) = up0 up1 down0 down1 left0 left1 (right = mirrored left)
Essentials "Following Pokémon" sheets are 4x4 grids (rows down, left, right, up; 4 frames each),
upscaled 2x. Credits for those sheets: see followers/CREDITS.md.

Needs Pillow (run with the emulator venv's python).
"""
import struct
from PIL import Image

DIRS_DS = ('up', 'down', 'left', 'right')
ROWS_ESS = {'down': 0, 'left': 1, 'right': 2, 'up': 3}


# ---------------------------------------------------------------- BTX0
def _dict(t, off):
    count = t[off + 1]
    p = off + 4 + 8 + 4 * count
    usz = struct.unpack_from('<H', t, p)[0]
    p += 4
    ents = [bytes(t[p + i * usz:p + (i + 1) * usz]) for i in range(count)]
    p += usz * count
    names = [bytes(t[p + i * 16:p + (i + 1) * 16]).rstrip(b'\0').decode('latin1') for i in range(count)]
    return list(zip(names, ents))


def btx_layout(data):
    """-> (textures [(name, w, h, abs_offset)], palettes [(name, abs_offset)])"""
    assert data[:4] == b'BTX0'
    t0 = struct.unpack_from('<I', data, 0x10)[0]
    t = data[t0:]
    assert t[:4] == b'TEX0'
    texinfo = struct.unpack_from('<H', t, 0x0E)[0]
    texdata = struct.unpack_from('<I', t, 0x14)[0]
    palinfo = struct.unpack_from('<I', t, 0x34)[0]
    paldata = struct.unpack_from('<I', t, 0x38)[0]
    texs = []
    for n, e in _dict(t, texinfo):
        p0 = struct.unpack_from('<I', e, 0)[0]
        w, h, fmt = 8 << ((p0 >> 20) & 7), 8 << ((p0 >> 23) & 7), (p0 >> 26) & 7
        assert fmt == 3, 'expected 4bpp textures'
        texs.append((n, w, h, t0 + texdata + ((p0 & 0xFFFF) << 3)))
    pals = [(n, t0 + paldata + (struct.unpack_from('<H', e, 0)[0] << 3)) for n, e in _dict(t, palinfo)]
    return texs, pals


def btx_decode(data):
    """-> (frames [list of rows of indices], palette [(r,g,b)] * 16)"""
    texs, pals = btx_layout(data)
    po = pals[0][1]
    pal = []
    for i in range(16):
        c = struct.unpack_from('<H', data, po + 2 * i)[0]
        pal.append(((c & 31) << 3, (c >> 5 & 31) << 3, (c >> 10 & 31) << 3))
    frames = []
    for n, w, h, off in texs:
        px = []
        for y in range(h):
            row = []
            for x in range(0, w, 2):
                b = data[off + (y * w + x) // 2]
                row += [b & 15, b >> 4]
            px.append(row)
        frames.append(px)
    return frames, pal


def btx_encode(template, frames, pal):
    """Copy of `template` with its textures and palette replaced (same count and sizes)."""
    texs, pals = btx_layout(template)
    assert len(frames) == len(texs), (len(frames), len(texs))
    out = bytearray(template)
    for (n, w, h, off), px in zip(texs, frames):
        assert len(px) == h and len(px[0]) == w
        for y in range(h):
            for x in range(0, w, 2):
                out[off + (y * w + x) // 2] = (px[y][x] & 15) | (px[y][x + 1] & 15) << 4
    po = pals[0][1]
    for i in range(16):
        r, g, b = pal[i] if i < len(pal) else (0, 0, 0)
        struct.pack_into('<H', out, po + 2 * i, (r >> 3) | (g >> 3) << 5 | (b >> 3) << 10)
    return bytes(out)


def texel_key(frames):
    """Identity of a sprite's up/down frames (textures 0 and 2), for matching HGSS files."""
    return tuple(tuple(map(tuple, frames[i])) for i in (0, 2))


def palette_bytes(data, n=0):
    """Raw 32-byte palette `n` of a BTX0."""
    po = btx_layout(data)[1][n][1]
    return bytes(data[po:po + 32])


def btx_set_palette(data, pal):
    """Copy of `data` with palette 0 replaced (32 raw bytes, or a list of 16 (r, g, b))."""
    po = btx_layout(data)[1][0][1]
    if not isinstance(pal, (bytes, bytearray)):
        pal = b''.join(struct.pack('<H', (r >> 3) | (g >> 3) << 5 | (b >> 3) << 10) for r, g, b in pal)
    out = bytearray(data)
    out[po:po + 32] = pal
    return bytes(out)


def colour_map(normal_path, shiny_path):
    """{normal rgb5 colour: shiny colour} by pixel correspondence of two same-layout sheets."""
    a, b = Image.open(normal_path).convert('RGBA'), Image.open(shiny_path).convert('RGBA')
    if a.size != b.size:
        return None
    votes = {}
    for ca, cb in zip(a.getdata(), b.getdata()):
        if ca[3] and cb[3]:
            ka = (ca[0] >> 3 << 3, ca[1] >> 3 << 3, ca[2] >> 3 << 3)
            kb = (cb[0] >> 3 << 3, cb[1] >> 3 << 3, cb[2] >> 3 << 3)
            v = votes.setdefault(ka, {})
            v[kb] = v.get(kb, 0) + 1
    return {k: max(v, key=v.get) for k, v in votes.items()} or None


def map_palette(pal, cmap):
    """Shiny palette for a game palette: each colour -> shiny colour of the nearest sheet colour."""
    keys = list(cmap)
    out = [pal[0]]
    for c in pal[1:]:
        k = min(keys, key=lambda k: sum((x - y) ** 2 for x, y in zip(k, c)))
        out.append(cmap[k])
    return out


def render(frames, pal, scale=2):
    """Frames side by side as an RGBA image (index 0 transparent) for eyeballing."""
    w, h = len(frames[0][0]), len(frames[0])
    im = Image.new('RGBA', (w * len(frames), h), (255, 0, 255, 255))
    for i, px in enumerate(frames):
        for y in range(h):
            for x in range(w):
                if px[y][x]:
                    im.putpixel((i * w + x, y), pal[px[y][x]] + (255,))
    return im.resize((im.width * scale, im.height * scale), Image.NEAREST)


# ---------------------------------------------------------------- Essentials sheets
def _downscale(cell):
    """2x nearest downscale, choosing the pixel phase that keeps 2x2 blocks uniform."""
    w, h = cell.size
    px = cell.load()
    best = None
    for oy in (0, 1):
        for ox in (0, 1):
            bad = sum(1 for y in range(oy, h - 1, 2) for x in range(ox, w - 1, 2)
                      if not (px[x, y] == px[x + 1, y] == px[x, y + 1] == px[x + 1, y + 1]))
            if best is None or bad < best[0]:
                best = (bad, ox, oy)
    _, ox, oy = best
    out = Image.new('RGBA', (w // 2, h // 2))
    for y in range(h // 2):
        for x in range(w // 2):
            c = px[min(w - 1, 2 * x + ox), min(h - 1, 2 * y + oy)]
            out.putpixel((x, y), c if c[3] >= 128 else (0, 0, 0, 0))
    return out


def sheet_frames(path, cols=(0, 1)):
    """Essentials sheet -> {dir: [RGBA frame, RGBA frame]} at native size."""
    im = Image.open(path).convert('RGBA')
    cw, ch = im.width // 4, im.height // 4
    out = {}
    for d, r in ROWS_ESS.items():
        out[d] = [_downscale(im.crop((c * cw, r * ch, (c + 1) * cw, (r + 1) * ch))) for c in cols]
    return out


def fit(frame, size):
    """Place a native frame on a size x size canvas: centred horizontally, bottom-aligned."""
    if frame.width == size and frame.height == size:
        return frame
    c = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    c.paste(frame, ((size - frame.width) // 2, size - frame.height))
    return c


def quantize(frames, ncol=15):
    """RGBA frames -> (index frames, palette); index 0 = transparent, at most ncol colours."""
    colours = {}
    for f in frames:
        for c in f.getdata():
            if c[3]:
                k = (c[0] >> 3 << 3, c[1] >> 3 << 3, c[2] >> 3 << 3)
                colours[k] = colours.get(k, 0) + 1
    keys = sorted(colours, key=lambda k: -colours[k])
    if len(keys) <= ncol:
        pal = keys
        lut = {k: i + 1 for i, k in enumerate(keys)}
        mapc = lambda k: lut[k]
    else:
        # median-cut over the opaque pixels of all frames together
        strip = Image.new('RGB', (len(keys), 1))
        strip.putdata(keys)
        q = strip.quantize(colors=ncol, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
        qp = q.getpalette()[:3 * ncol]
        pal = [(qp[3 * i] >> 3 << 3, qp[3 * i + 1] >> 3 << 3, qp[3 * i + 2] >> 3 << 3) for i in range(ncol)]
        lut = {k: q.getpixel((i, 0)) + 1 for i, k in enumerate(keys)}
        mapc = lambda k: lut[k]
    out = []
    for f in frames:
        w, h = f.size
        d = list(f.getdata())
        rows = []
        for y in range(h):
            row = []
            for x in range(w):
                c = d[y * w + x]
                row.append(mapc((c[0] >> 3 << 3, c[1] >> 3 << 3, c[2] >> 3 << 3)) if c[3] else 0)
            rows.append(row)
        out.append(rows)
    return out, [(0, 0, 0)] + list(pal) + [(0, 0, 0)] * (15 - len(pal))


def shiny_palette(index_frames, shiny_rgba, pal):
    """Palette for the shiny sheet: for each index, the most common shiny colour at its pixels."""
    votes = [dict() for _ in range(16)]
    for px, f in zip(index_frames, shiny_rgba):
        d = list(f.getdata())
        w = f.width
        for y, row in enumerate(px):
            for x, i in enumerate(row):
                c = d[y * w + x]
                if i and c[3]:
                    k = (c[0] >> 3 << 3, c[1] >> 3 << 3, c[2] >> 3 << 3)
                    votes[i][k] = votes[i].get(k, 0) + 1
    return [max(v, key=v.get) if v else pal[i] for i, v in enumerate(votes)]


def ds_frames(fr, size, mirrored):
    """{dir: [f0, f1]} -> DS texture order (8 frames, or 6 when right is mirrored)."""
    dirs = DIRS_DS[:3] if mirrored else DIRS_DS
    return [fit(f, size) for d in dirs for f in fr[d]]
