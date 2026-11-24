"""Access to the partially decoded Redux ROM (see decode_patch.sh) and vanilla modules.

A byte of the Redux ROM is *known* when known0 == known1 at that offset (Redux wrote it);
otherwise it was copied from the vanilla ROM, whose bytes we only have where pokeblack2
can reassemble them.
"""
import json, mmap, os, re, struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BUILD = os.path.join(ROOT, 'build')
PB2 = os.environ.get('POKEBLACK2', os.path.join(BUILD, 'ext', 'pokeblack2'))

ARM9_ROM, ARM9_RAM = 0x4000, 0x02004000
FAT_OFF, FAT_SIZE = 0x38B000, 0x14B0   # from the Redux header (known bytes)
OVT_OFF = 0x9EE00                      # arm9 overlay table in the Redux ROM
NUM_OVERLAYS = 344


def _map(path):
    f = open(path, 'rb')
    return f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)


class ReduxRom:
    def __init__(self):
        self._f0, self.k0 = _map(os.path.join(BUILD, 'rom', 'known0.nds'))
        self._f1, self.k1 = _map(os.path.join(BUILD, 'rom', 'known1.nds'))
        self._copymap = None

    def known(self, off, n=1):
        return self.k0[off:off + n] == self.k1[off:off + n]

    def mask(self, off, n):
        a, b = self.k0[off:off + n], self.k1[off:off + n]
        return bytes(x == y for x, y in zip(a, b))

    def read(self, off, n):
        """Redux bytes; unknown positions read as 0x00."""
        return self.k0[off:off + n]

    def u32(self, off):
        return struct.unpack('<I', self.k0[off:off + 4])[0]

    def source_offset(self, off):
        """Vanilla ROM offset a copied byte came from (exact, from the xdelta copy instructions),
        or None if Redux wrote the byte."""
        if self._copymap is None:
            from copymap import CopyMap
            self._copymap = CopyMap()
        return self._copymap.source(off)

    # --- filesystem -------------------------------------------------------------
    def fat(self):
        """[(name, start, end)] with the few partially-copied entries patched from neighbours."""
        n = FAT_SIZE // 8
        ent = [list(struct.unpack('<II', self.k0[FAT_OFF + 8 * i:FAT_OFF + 8 * i + 8])) for i in range(n)]
        ent[0][0] = 0xA1A00                      # first overlay follows the 0x200-aligned overlay table
        ent[206] = [ent[205][1], ent[205][1]]    # 205..207 copied from vanilla FAT: treat as one block
        ent[205][1] = ent[207][1]
        ent[207][0] = ent[207][1]
        p = ent[n - 1][0]                         # last file runs until the 0xFF padding
        pad = b'\xff' * 4096
        while not (self.k0[p:p + 4096] == pad and self.k1[p:p + 4096] == pad):
            p += 4096
        ent[n - 1][1] = p
        names = [l.strip() for l in open(os.path.join(PB2, 'black2.en', 'files.txt'))]
        out = []
        for i, (s, e) in enumerate(ent):
            out.append((f'overlay_{i}' if i < NUM_OVERLAYS else names[i - NUM_OVERLAYS], s, e))
        return out

    def overlay_entry(self, i):
        a = OVT_OFF + 32 * i
        f = struct.unpack('<8I', self.k0[a:a + 32])
        return dict(id=f[0], ram=f[1], ram_size=f[2], bss=f[3], sinit=f[4], sinit_end=f[5],
                    file_id=f[6], flags=f[7], known=self.mask(a, 32))


class Vanilla:
    """Images assembled by build_vanilla.py."""
    def __init__(self, module):
        d = os.path.join(BUILD, 'vanilla')
        self.meta = json.load(open(os.path.join(d, module + '.json')))
        self.data = open(os.path.join(d, module + '.bin'), 'rb').read()
        self.base = self.meta['base']

    def at(self, addr, n=1):
        i = addr - self.base
        return self.data[i:i + n] if 0 <= i and i + n <= len(self.data) else None


def functions(module):
    """[(addr, name, mode)] from pokeblack2 func_start macros + `name: ; 0xADDR` lines."""
    text = open(os.path.join(PB2, 'asm', module + '.s'), errors='replace').read()
    out = []
    for m in re.finditer(r'^\s*(thumb|arm|non_word_aligned_thumb)_func_start\s+(\w+)\s*\n(?:.*\n){0,3}?\2:\s*;\s*0x([0-9A-Fa-f]{8})', text, re.M):
        out.append((int(m.group(3), 16), m.group(2), 'arm' if m.group(1) == 'arm' else 'thumb'))
    return sorted(out)


def names():
    """placeholder/addr -> best known name (W2->B2 transfer)."""
    path = os.path.join(ROOT, 'data', 'b2_names_w2transfer.tsv')
    out = {}
    for line in open(path):
        p = line.rstrip('\n').split('\t')
        if p[0] == 'segment':
            continue
        out[(p[0], int(p[1], 16))] = p[3]
    return out
