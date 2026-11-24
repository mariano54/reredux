"""Rebuild an NDS ROM from a base ROM plus replaced files; ARM9 overlay / autoload helpers.

Regions (header, arm9, overlay tables, every FAT file, arm7, FNT, FAT, banner) are laid out in the
base ROM's order. A region keeps its original offset while nothing before it changed size; after a
change, regions move to the next 0x200 boundary. FAT entries, header pointers, the header CRC16 and
the "used ROM size" field are updated; the rest of the image keeps the base ROM's fill.
"""
import os, struct, subprocess, tempfile
import ndsfs

BLZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'build', 'bin', 'blz')


def blz_decode(data):
    """Nintendo BLZ (overlay / arm9) decompression via build/bin/blz (tools/blz.c)."""
    with tempfile.TemporaryDirectory() as t:
        i, o = os.path.join(t, 'in'), os.path.join(t, 'out')
        open(i, 'wb').write(data)
        subprocess.run([BLZ, '-d', i, o], check=True)
        return open(o, 'rb').read()


class OverlayTable:
    """The ARM9 overlay table of `rom` plus the changed files dict `files` ({file id: bytes}, as
    romtool.build takes). load() returns an overlay's decompressed image; store() puts a patched
    image back **uncompressed** (compressed flag and size cleared/updated in the table). Several
    steps may patch the same overlay: load() returns the latest stored version."""

    def __init__(self, rom, files, ovt=None):
        self.rom, self.files = rom, files
        self.ovt = bytearray(ovt if ovt is not None else rom.m[rom.ovt9[0]:rom.ovt9[0] + rom.ovt9[1]])

    def entry(self, ov_id):
        """-> (table index, [id, ram, ram_size, bss, sinit, sinit_end, file_id, size|flags])"""
        for e in range(len(self.ovt) // 32):
            f = list(struct.unpack_from('<8I', self.ovt, 32 * e))
            if f[0] == ov_id:
                return e, f
        raise KeyError(f'no overlay {ov_id}')

    def ram(self, ov_id):
        return self.entry(ov_id)[1][1]

    def size(self, ov_id):
        return self.entry(ov_id)[1][2]

    def load(self, ov_id, ram=None):
        e, f = self.entry(ov_id)
        assert ram is None or f[1] == ram, f'overlay {ov_id} at {f[1]:#x}, expected {ram:#x}'
        code = bytes(self.files[f[6]]) if f[6] in self.files else bytes(self.rom.file(f[6]))
        if f[7] >> 24 & 1:
            code = blz_decode(code)
        assert len(code) == f[2], f'overlay {ov_id} size mismatch'
        return bytearray(code)

    def store(self, ov_id, img):
        e, f = self.entry(ov_id)
        assert len(img) == f[2], f'overlay {ov_id}: image size changed'
        f[7] = len(img)              # stored uncompressed (compressed flag clear)
        struct.pack_into('<8I', self.ovt, 32 * e, *f)
        self.files[f[6]] = bytes(img)

    def bytes(self):
        return bytes(self.ovt)


AUTOLOAD_MAGIC = struct.pack('<II', 0xDEC00621, 0x2106C0DE)


def module_params(arm9):
    """Offset of the SDK module params in an (uncompressed) arm9 image:
    [autoload list, list end, autoload data start, bss start, bss end, compressed end, ...]"""
    i = arm9.find(AUTOLOAD_MAGIC)
    assert i >= 0x1C, 'no module params'
    p = i - 0x1C
    assert struct.unpack_from('<I', arm9, p + 0x14)[0] == 0, 'arm9 is compressed'
    return p


def autoloads(arm9, ram):
    """-> [(ram address, size, sinit table, bss size, file offset of the data)] (TWL SDK list:
    four words per entry; the segments' data follow each other from 'autoload data start')."""
    p = module_params(arm9)
    al, ale, src = struct.unpack_from('<3I', arm9, p)
    out = []
    for o in range(al, ale, 16):
        a, s, sinit, bss = struct.unpack_from('<4I', arm9, o - ram)
        out.append((a, s, sinit, bss, src - ram))
        src += s
    assert src == al, 'autoload data does not end at the list'
    return out


def add_autoload(arm9, ram, addr, blob, bss=0):
    """Append an autoload segment (copied to `addr` by crt0 before main, data cache flushed and
    instruction cache invalidated for main-RAM targets) at the end of the autoload list."""
    p = module_params(arm9)
    al, ale = struct.unpack_from('<2I', arm9, p)
    assert all(a != addr for a, *_ in autoloads(arm9, ram)), f'autoload at {addr:#x} already present'
    ins, lend = al - ram, ale - ram
    entry = struct.pack('<4I', addr, len(blob), 0, bss)
    out = bytearray(arm9[:ins] + blob + arm9[ins:lend] + entry + arm9[lend:])
    struct.pack_into('<2I', out, p, al + len(blob), ale + len(blob) + 16)
    return bytes(out)


def crc16(data, crc=0xFFFF):
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def twl_area(m):
    """[start, end) of a DSi-enhanced ROM's TWL-only area (arm9i/arm7i), or None."""
    u = lambda o: struct.unpack_from('<I', m, o)[0]
    if m[0x12] not in (2, 3):
        return None
    spans = [(u(0x1C0), u(0x1C0) + u(0x1CC)), (u(0x1D0), u(0x1D0) + u(0x1DC))]
    spans = [(a, b) for a, b in spans if 0x8000 <= a < b <= len(m)]
    if not spans:
        return None
    start = struct.unpack_from('<H', m, 0x92)[0] * 0x80000
    return (min([start] + [a for a, _ in spans]) if start else min(a for a, _ in spans),
            max(max(b for _, b in spans), u(0x210)))


def build(base_path, files=None, arm9=None, ovt9=None):
    """files: {file id: new bytes}; arm9 / ovt9: new arm9 / overlay table bytes. Returns the new
    ROM image. Regions never move into the DSi-only (TWL) area; ones that would are placed after it."""
    files = files or {}
    rom = ndsfs.Rom(base_path)
    m = rom.m
    u32 = lambda o: struct.unpack_from('<I', m, o)[0]
    regions = []   # (orig_offset, size, kind, key)
    regions.append((u32(0x20), u32(0x2C), 'hdr', (0x20, 0x2C)))     # arm9
    regions.append((u32(0x30), u32(0x3C), 'hdr', (0x30, 0x3C)))     # arm7
    regions.append((u32(0x40), u32(0x44), 'hdr', (0x40, 0x44)))     # FNT
    regions.append((u32(0x48), u32(0x4C), 'hdr', (0x48, 0x4C)))     # FAT
    if u32(0x54):
        regions.append((u32(0x50), u32(0x54), 'hdr', (0x50, 0x54)))  # overlay table 9
    if u32(0x5C):
        regions.append((u32(0x58), u32(0x5C), 'hdr', (0x58, 0x5C)))  # overlay table 7
    if u32(0x68):
        ver = struct.unpack_from('<H', m, u32(0x68))[0]
        regions.append((u32(0x68), {1: 0x840, 2: 0x940, 3: 0xA40, 0x103: 0x23C0}.get(ver, 0x840), 'banner', None))
    for fid, (s, e) in enumerate(rom.fat):
        if e > s:
            regions.append((s, e - s, 'file', fid))
    regions.sort()
    content = {}
    for off, size, kind, key in regions:
        if kind == 'file' and key in files:
            content[(off, kind, key)] = files[key]
        elif kind == 'hdr' and key == (0x20, 0x2C) and arm9 is not None:
            content[(off, kind, key)] = arm9
        elif kind == 'hdr' and key == (0x50, 0x54) and ovt9 is not None:
            content[(off, kind, key)] = ovt9
        else:
            content[(off, kind, key)] = None
    out = bytearray(m[:])
    header_end = regions[0][0]
    pos = header_end
    shift = False
    fat = list(rom.fat)
    hdr_updates = {}
    banner_at = u32(0x68)
    twl = twl_area(m)
    for i, (off, size, kind, key) in enumerate(regions):
        data = content[(off, kind, key)]
        new_size = len(data) if data is not None else size
        if shift or off < pos:
            start = (pos + 0x1FF) & ~0x1FF
            shift = True
        else:
            start = off
        if twl and start < twl[1] and start + new_size > twl[0] and not (off >= twl[0] and not shift):
            start = (twl[1] + 0x1FF) & ~0x1FF   # jump over the DSi area instead of overwriting it
        src = data if data is not None else m[off:off + size]
        if shift:
            out[start:start + new_size] = src
        elif data is not None:
            out[start:start + new_size] = src
        if kind == 'file':
            fat[key] = (start, start + new_size)
        elif kind == 'hdr':
            hdr_updates[key] = (start, new_size)
        elif kind == 'banner':
            banner_at = start          # moves with the regions before it (header 0x68 must follow)
        if new_size != size:
            shift = True
        pos = start + new_size
    # clear stale bytes after the last region (keeping the DSi area) with the base ROM's fill
    if shift:
        fill = m[len(m) - 1]
        keep = twl if twl and twl[0] >= pos else None
        if keep:
            out[pos:keep[0]] = bytes([fill]) * (keep[0] - pos)
            out[keep[1]:] = bytes([fill]) * (len(out) - keep[1])
        elif not (twl and pos > twl[1]):
            out[pos:] = bytes([fill]) * (len(out) - pos)
        else:
            out[pos:] = bytes([fill]) * (len(out) - pos)
    # FAT
    fat_off = hdr_updates.get((0x48, 0x4C), (u32(0x48), 0))[0]
    for fid, (s, e) in enumerate(fat):
        struct.pack_into('<II', out, fat_off + 8 * fid, s, e)
    for (o_off, o_size), (start, size) in hdr_updates.items():
        struct.pack_into('<I', out, o_off, start)
        struct.pack_into('<I', out, o_size, size)
    if u32(0x68):
        struct.pack_into('<I', out, 0x68, banner_at)   # icon / title (launchers and ROM lists read it)
    if shift:
        struct.pack_into('<I', out, 0x80, pos)      # total used ROM size
    struct.pack_into('<H', out, 0x15E, crc16(out[:0x15E]))
    return bytes(out)
