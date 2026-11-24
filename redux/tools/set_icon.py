"""Replace a ROM's DS icon (the 32x32 picture launchers and emulator ROM lists show) with an image,
e.g. the game's box art.

    python3 set_icon.py ROM IMAGE [--crop x0,y0,x1,y1] [--preview OUT.png]   # patches ROM in place

The image (or its crop) is scaled to 32x32 and reduced to 15 colours (index 0 is transparent). The
DS icon (banner +0x20 tiles, +0x220 palette) and, for DSi banners (version 0x103), all eight frames
of the animated icon are replaced; the banner CRCs are recomputed.
"""
import argparse, struct
from PIL import Image, ImageEnhance
from romtool import crc16

CRC_RANGES = {0x02: (0x20, 0x840), 0x04: (0x20, 0x940), 0x06: (0x20, 0xA40), 0x08: (0x1240, 0x23C0)}


def icon_data(img):
    """-> (512 bytes 4bpp tiled bitmap, 32 bytes BGR555 palette), preview image"""
    img = img.convert('RGB')
    img = ImageEnhance.Contrast(ImageEnhance.Color(img).enhance(1.3)).enhance(1.25)   # reads better at 32 px
    img = img.resize((32, 32), Image.LANCZOS)
    q = img.quantize(colors=15, method=Image.MEDIANCUT, dither=Image.NONE)
    pal = q.getpalette()[:45]
    px = q.load()
    bitmap = bytearray(512)
    for ty in range(4):
        for tx in range(4):
            for y in range(8):
                for x in range(0, 8, 2):
                    a = px[tx * 8 + x, ty * 8 + y] + 1
                    b = px[tx * 8 + x + 1, ty * 8 + y] + 1
                    bitmap[(ty * 4 + tx) * 32 + y * 4 + x // 2] = a | b << 4
    colours = [(0, 0, 0)] + [tuple(pal[i * 3:i * 3 + 3]) for i in range(15)]
    palette = b''.join(struct.pack('<H', r >> 3 | (g >> 3) << 5 | (b >> 3) << 10) for r, g, b in colours)
    return bytes(bitmap), palette, q.convert('RGB')


TITLE_SLOTS = {1: 6, 2: 7, 3: 8, 0x103: 8}    # banner version -> title languages (JA EN FR DE IT ES [ZH] [KO])


def set_icon(rom_path, img, preview=None, title=None):
    """title: replaces the banner title (up to 3 lines, e.g. 'Pokémon\\nGame\\nPublisher') in every
    language slot, so launchers show it whatever their language."""
    bitmap, palette, prev = icon_data(img)
    with open(rom_path, 'r+b') as f:
        off = struct.unpack('<I', f.read(0x6C)[0x68:0x6C])[0]
        f.seek(off)
        ver = struct.unpack('<H', f.read(2))[0]
        size = {1: 0x840, 2: 0x940, 3: 0xA40, 0x103: 0x23C0}[ver]
        f.seek(off)
        b = bytearray(f.read(size))
        b[0x20:0x220] = bitmap
        b[0x220:0x240] = palette
        if title:
            t = title.encode('utf-16-le')[:0xFE]
            for k in range(TITLE_SLOTS[ver]):
                b[0x240 + 0x100 * k:0x340 + 0x100 * k] = t.ljust(0x100, b'\0')
        if ver == 0x103:
            for k in range(8):
                b[0x1240 + 512 * k:0x1240 + 512 * (k + 1)] = bitmap
                b[0x2240 + 32 * k:0x2240 + 32 * (k + 1)] = palette
        for at, (s, e) in CRC_RANGES.items():
            if e <= size:
                struct.pack_into('<H', b, at, crc16(bytes(b[s:e])))
        f.seek(off)
        f.write(b)
    if preview:
        prev.resize((256, 256), Image.NEAREST).save(preview)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('rom')
    ap.add_argument('image')
    ap.add_argument('--crop', help='x0,y0,x1,y1 of the image to use')
    ap.add_argument('--preview', help='write the icon, enlarged, here')
    a = ap.parse_args()
    im = Image.open(a.image)
    if a.crop:
        im = im.crop(tuple(int(v) for v in a.crop.split(',')))
    set_icon(a.rom, im, a.preview)
    print('icon replaced in', a.rom)
