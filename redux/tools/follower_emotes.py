#!/usr/bin/env python3
"""HGSS emote balloons for the follower talk port (followers/emote.c).

  follower_emotes.py ROM HGSS_ROOT [--png OUT.png]   : print the member ids, optionally render them

emote_assets() builds one B2 balloon model per HGSS balloon frame: a copy of B2's own `!` model
(a/0/7/4 member 50: BMD0, one 16x16 4bpp texture with colour 0 transparent and an 8-colour
palette) whose texels / palette are replaced by the 16x16 bubble cropped out of HGSS's 32x32
`fuki_*` texture (a/1/0/3 members 2..15 = icons 0..13, frames .1 / .2). The 28 models are
appended to a/0/7/4 after whatever members it already has; model for icon i, frame f is
member first + 2 * i + f, and emote.c gets `first` as -DEMOTE_FIRST_MEMBER.
"""
import argparse, os, struct, sys
import ndsfs

B2_ARC = 'a/0/7/4'
B2_TEMPLATE = 50            # sisen_ef `!` balloon (768 bytes)
B2_TEXELS = 0x270           # 16x16 4bpp = 128 bytes
B2_PALETTE = 0x2F0          # 8 colours = 16 bytes
HGSS_ARC = os.path.join('files', 'a', '1', '0', '3')
HGSS_FIRST = 2              # fuki_heart; icons 0..13 = members 2..15
ICONS = 14
CROP_X, CROP_Y = 8, 15      # the bubble sits in x 8..23, y 15..30 of every 32x32 frame
KOMARI = 10                 # fuki_komari: its sweat drops fly outside the crop

# fuki_komari's drops are drawn back into the bubble's free top-left corner (crop coordinates,
# palette indices of fuki_komari: 1 light blue, 5 blue, 2 outline): frame 1 a drop inside the
# bubble, frame 2 the same drop one pixel higher, breaking through the outline.
KOMARI_DROPS = (
    {(2, 1): 5, (1, 2): 5, (2, 2): 1, (3, 2): 5, (1, 3): 5, (2, 3): 1, (3, 3): 5, (2, 4): 5},
    {(2, 0): 5, (1, 1): 5, (2, 1): 1, (3, 1): 5, (1, 2): 5, (2, 2): 1, (3, 2): 5, (2, 3): 5},
)


def _dict(t, off):
    """Nitro dictionary at t[off] -> [(name, entry bytes)]."""
    n = t[off + 1]
    at = off + 8 + 4 * (n + 1)
    unit = struct.unpack_from('<H', t, at)[0]
    data, names = at + 4, at + 4 + unit * n
    return [(t[names + 16 * i:names + 16 * i + 16].split(b'\0')[0].decode(), t[data + unit * i:data + unit * (i + 1)])
            for i in range(n)]


def _tex0(d):
    """-> (TEX0 offset, [(name, w, h, fmt, texel offset in d)], [(name, palette offset in d)])"""
    p = d.find(b'TEX0')
    assert p > 0, 'no TEX0'
    t = d[p:]
    tex_data = struct.unpack_from('<I', t, 0x14)[0]
    pal_data = struct.unpack_from('<I', t, 0x38)[0]
    texs = []
    for name, e in _dict(t, struct.unpack_from('<H', t, 0x0E)[0]):
        prm = struct.unpack_from('<I', e, 0)[0]
        texs.append((name, 8 << (prm >> 20 & 7), 8 << (prm >> 23 & 7), prm >> 26 & 7, p + tex_data + ((prm & 0xFFFF) << 3)))
    pals = [(name, p + pal_data + (struct.unpack_from('<H', e, 0)[0] << 3))
            for name, e in _dict(t, struct.unpack_from('<I', t, 0x34)[0])]
    return p, texs, pals


def _pixels(d, off, w, h):
    return [[d[off + (y * w + x) // 2] >> (4 * (x & 1)) & 15 for x in range(w)] for y in range(h)]


def hgss_frames(hgss_root):
    """-> [(icon, frame, 16x16 rows of palette indices, 16-byte palette)] for icons 0..13."""
    path = hgss_root if os.path.isfile(hgss_root) else os.path.join(hgss_root, HGSS_ARC)
    members = ndsfs.narc(open(path, 'rb').read())
    out = []
    for icon in range(ICONS):
        d = members[HGSS_FIRST + icon]
        assert d[:4] == b'BTX0', f'a/1/0/3[{HGSS_FIRST + icon}] is not a BTX0'
        _, texs, pals = _tex0(d)
        assert len(texs) == 2 and texs[0][0].startswith('fuki_') and len(pals) == 1, texs
        pal = d[pals[0][1]:pals[0][1] + 16]
        for f, (name, w, h, fmt, off) in enumerate(texs):
            assert (w, h, fmt) == (32, 32, 3), name
            px = _pixels(d, off, w, h)
            crop = [row[CROP_X:CROP_X + 16] for row in px[CROP_Y:CROP_Y + 16]]
            lost = sum(1 for row in px for v in row if v) - sum(1 for row in crop for v in row if v)
            if icon == KOMARI:
                for (x, y), v in KOMARI_DROPS[f].items():
                    crop[y][x] = v
            else:
                assert lost == 0, f'{name}: {lost} pixels outside the crop'
            assert max(max(r) for r in crop) < 8, f'{name} uses colours past B2\'s 8-colour palette'
            out.append((icon, f, crop, pal))
    return out


def balloon_model(template, crop, pal):
    """B2 member 50 with its 16x16 texels and 8-colour palette replaced."""
    m = bytearray(template)
    m[B2_TEXELS:B2_TEXELS + 128] = bytes(crop[y][x] | crop[y][x + 1] << 4 for y in range(16) for x in range(0, 16, 2))
    m[B2_PALETTE:B2_PALETTE + 16] = pal
    return bytes(m)


def check_template(t):
    assert t[:4] == b'BMD0' and len(t) == 768, 'a/0/7/4[50] is not the 768-byte balloon model'
    _, texs, pals = _tex0(t)
    assert [x[1:] for x in texs] == [(16, 16, 3, B2_TEXELS)], texs
    assert [x[1] for x in pals] == [B2_PALETTE], pals


def emote_assets(rom, hgss_root):
    """-> ({a/0/7/4 file id: new NARC bytes}, first member of the 28 models). `rom` is an ndsfs.Rom
    or build_followers.RomView (files changed by earlier steps, e.g. the Poke Ball effect's
    members); the models go after whatever members a/0/7/4 has. A ROM that already has them
    (built from a followers ROM) gets no change and their existing first member."""
    fid = next(f for f, p in rom.paths.items() if p == B2_ARC)
    raw = bytes(rom.file(fid))
    members = ndsfs.narc(raw)
    template = members[B2_TEMPLATE]
    check_template(template)
    models = [balloon_model(template, crop, pal) for _, _, crop, pal in hgss_frames(hgss_root)]
    for i in range(len(members) - len(models) + 1):
        if members[i] == models[0] and members[i:i + len(models)] == models:
            return {}, i
    first = len(members)
    out = ndsfs.pack_narc(members + models, ndsfs.narc_layout(raw))
    assert ndsfs.narc(out) == members + models
    return {fid: out}, first


def render(frames, out):
    """Contact sheet of the 28 cropped frames (8x zoom, grey background)."""
    from PIL import Image
    S = 8
    sheet = Image.new('RGB', (4 * 17 * S, 7 * 17 * S), (150, 160, 170))
    for k, (icon, f, crop, pal) in enumerate(frames):
        cols = [struct.unpack_from('<H', pal, 2 * i)[0] for i in range(8)]
        rgb = [((c & 31) * 255 // 31, (c >> 5 & 31) * 255 // 31, (c >> 10 & 31) * 255 // 31) for c in cols]
        ox, oy = (k % 4) * 17 * S, (k // 4) * 17 * S
        for y in range(16):
            for x in range(16):
                if crop[y][x]:
                    sheet.paste(rgb[crop[y][x]], (ox + x * S, oy + y * S, ox + (x + 1) * S, oy + (y + 1) * S))
    sheet.save(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('rom')
    ap.add_argument('hgss_root', help='HGSS decomp checkout (files/a/1/0/3) or the a/1/0/3 NARC itself')
    ap.add_argument('--png')
    a = ap.parse_args()
    files, first = emote_assets(ndsfs.Rom(a.rom), a.hgss_root)
    print(f'emote members {first}..{first + 2 * ICONS - 1} (EMOTE_FIRST_MEMBER={first})')
    if a.png:
        render(hgss_frames(a.hgss_root), a.png)


if __name__ == '__main__':
    sys.exit(main())
