"""sav.py : B2 battery-save checks (library + CLI).  sav.py FILE.dsv [RAMSNAP.bin]
Layout (from the GFL backup code): copies at 0 and 0x26000, each 0x25FA4 bytes: 73 blocks (table from a RAM
dump: BLOCKS), every block = data + u16 counter + u16 CRC16 at off+size; CRC table (u16 per block) at 0x25F00,
header at 0x25F94 (save counter u32, size u32, magic u32, ? u16, CRC of the CRC table u16), commit byte 0x25FA3."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import struct, sys, json, os

COPY = (0, 0x26000)
SIZE = 0x25FA4
FOOT = 0x25F00
BLOCKS = None


def load_blocks():
    global BLOCKS
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'blocks.json')
    BLOCKS = json.load(open(p))
    return BLOCKS


def crc16(data, init=0xFFFF):
    c = init
    for b in data:
        c ^= b << 8
        for _ in range(8):
            c = ((c << 1) ^ 0x1021) & 0xFFFF if c & 0x8000 else (c << 1) & 0xFFFF
    return c


def raw(path):
    d = open(path, 'rb').read()
    return d[:0x80000]


def check(path, snap=None, quiet=False):
    """-> dict: per copy: blocks with bad CRC, header counter; if snap (RAM buffer bytes): blocks whose data differs
    from RAM in each copy"""
    blocks = BLOCKS or load_blocks()
    d = raw(path)
    out = {}
    for ci, base in enumerate(COPY):
        bad, cnt, diff = [], {}, []
        for i, (off, size) in enumerate(blocks):
            data = d[base + off: base + off + size]
            ctr, crc = struct.unpack_from('<HH', d, base + off + size)
            cnt[i] = ctr
            if crc16(data) != crc:
                bad.append(i)
            tab = struct.unpack_from('<H', d, base + FOOT + 2 * i)[0]
            if tab != crc:
                bad.append(('tab', i))
            if snap is not None and snap[off: off + size] != data:
                diff.append(i)
        hdr = d[base + 0x25F94: base + 0x25FA4]
        counter = struct.unpack_from('<I', hdr, 0)[0]
        out['AB'[ci]] = dict(bad=bad, counter=counter, commit=d[base + SIZE - 1], diff=diff,
                             tabcrc_ok=crc16(d[base + FOOT: base + FOOT + 2 * len(blocks)]) ==
                             struct.unpack_from('<H', hdr, 0xE)[0])
        if snap is not None:
            out['AB'[ci]]['foot_eq_ram'] = d[base + FOOT: base + SIZE] == snap[FOOT:SIZE]
    return out


if __name__ == '__main__':
    snap = open(sys.argv[2], 'rb').read() if len(sys.argv) > 2 else None
    print(json.dumps(check(sys.argv[1], snap), indent=1))
