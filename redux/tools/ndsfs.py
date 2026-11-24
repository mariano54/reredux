"""Minimal NDS ROM filesystem reader: header, arm9/arm7, overlay table, FNT/FAT, NARC subfiles."""
import mmap, struct


class Rom:
    def __init__(self, path):
        self._f = open(path, 'rb')
        self.m = mmap.mmap(self._f.fileno(), 0, access=mmap.ACCESS_READ)
        u = lambda o: struct.unpack('<I', self.m[o:o + 4])[0]
        self.arm9 = (u(0x20), u(0x2C))      # rom offset, size
        self.arm9_ram = u(0x28)
        self.arm7 = (u(0x30), u(0x3C))
        self.fnt = (u(0x40), u(0x44))
        self.fat_ = (u(0x48), u(0x4C))
        self.ovt9 = (u(0x50), u(0x54))
        n = self.fat_[1] // 8
        self.fat = [struct.unpack('<II', self.m[self.fat_[0] + 8 * i:self.fat_[0] + 8 * i + 8]) for i in range(n)]
        self.paths = self._walk()

    def overlays(self):
        """[(id, ram, ram_size, bss, file_id, flags, compressed)]"""
        out = []
        o, size = self.ovt9
        for i in range(size // 32):
            f = struct.unpack('<8I', self.m[o + 32 * i:o + 32 * i + 32])
            out.append(dict(id=f[0], ram=f[1], ram_size=f[2], bss=f[3], file_id=f[6],
                            csize=f[7] & 0xFFFFFF, compressed=bool(f[7] >> 24 & 1)))
        return out

    def file(self, fid):
        s, e = self.fat[fid]
        return self.m[s:e]

    def _walk(self):
        """file id -> path, from the FNT."""
        base = self.fnt[0]
        paths = {}

        def dir_(did, prefix):
            off, first = struct.unpack('<IH', self.m[base + 8 * did:base + 8 * did + 6])
            p, fid = base + off, first
            while True:
                b = self.m[p]
                p += 1
                if b == 0:
                    break
                ln, isdir = b & 0x7F, b & 0x80
                name = self.m[p:p + ln].decode('latin-1')
                p += ln
                if isdir:
                    sub = struct.unpack('<H', self.m[p:p + 2])[0] & 0xFFF
                    p += 2
                    dir_(sub, prefix + name + '/')
                else:
                    paths[fid] = prefix + name
                    fid += 1
        dir_(0, '')
        return paths


def narc_layout(data):
    """Everything needed to repack a NARC byte-exactly: header, BTNF blob, the original gaps
    between subfiles and the original size fields (Redux's tools left some of them stale)."""
    hs = struct.unpack('<H', data[12:14])[0]
    p = hs
    bsize, count = struct.unpack('<II', data[p + 4:p + 12])
    ents = [struct.unpack('<II', data[p + 12 + 8 * i:p + 20 + 8 * i]) for i in range(count)]
    btnf_at = p + bsize
    btnf_size = struct.unpack('<I', data[btnf_at + 4:btnf_at + 8])[0]
    gmif_at = btnf_at + btnf_size
    d = gmif_at + 8
    gaps, prev = [], 0
    for s_, e_ in ents:
        gaps.append(bytes(data[d + prev:d + s_]) if s_ >= prev else None)
        prev = max(prev, e_)
    return dict(header=bytes(data[:hs]), btaf_head=bytes(data[p:p + 12]), btnf=bytes(data[btnf_at:gmif_at]),
                gmif_size=struct.unpack('<I', data[gmif_at + 4:gmif_at + 8])[0], gaps=gaps,
                sizes=[e_ - s_ for s_, e_ in ents], tail=bytes(data[d + prev:]),
                ents=ents)


def pack_narc(files, layout):
    """Inverse of narc(). With unchanged subfile sizes the original bytes are reproduced exactly;
    otherwise subfiles are 4-byte aligned (0xFF fill) and all size fields recomputed."""
    same = [len(f) for f in files] == layout['sizes']
    if same and all(g is not None for g in layout['gaps']):
        body = bytearray()
        for f, g in zip(files, layout['gaps']):
            body += g + f
        ents = layout['ents']
        body += layout['tail']
        btaf = layout['btaf_head'] + b''.join(struct.pack('<II', *e) for e in ents)
        gmif = b'GMIF' + struct.pack('<I', layout['gmif_size']) + bytes(body)
        return layout['header'] + btaf + layout['btnf'] + gmif
    body, ents = bytearray(), []
    for f in files:
        if len(body) % 4:
            body += b'\xff' * (4 - len(body) % 4)
        ents.append((len(body), len(body) + len(f)))
        body += f
    if len(body) % 4:
        body += b'\xff' * (4 - len(body) % 4)
    btaf = b'BTAF' + struct.pack('<II', 12 + 8 * len(files), len(files)) + b''.join(struct.pack('<II', *e) for e in ents)
    gmif = b'GMIF' + struct.pack('<I', 8 + len(body)) + bytes(body)
    hdr = bytearray(layout['header'])
    struct.pack_into('<I', hdr, 8, len(hdr) + len(btaf) + len(layout['btnf']) + len(gmif))
    return bytes(hdr) + btaf + layout['btnf'] + gmif


def narc(data):
    """List of subfile bytes, or None if not a NARC."""
    if data[:4] != b'NARC':
        return None
    hs = struct.unpack('<H', data[12:14])[0]
    p = hs
    assert data[p:p + 4] == b'BTAF'
    bsize, count = struct.unpack('<II', data[p + 4:p + 12])
    ents = [struct.unpack('<II', data[p + 12 + 8 * i:p + 20 + 8 * i]) for i in range(count)]
    p += bsize
    assert data[p:p + 4] == b'BTNF'
    p += struct.unpack('<I', data[p + 4:p + 8])[0]
    assert data[p:p + 4] == b'GMIF'
    d = p + 8
    return [bytes(data[d + s:d + e]) for s, e in ents]
