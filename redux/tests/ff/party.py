"""party.py : change the party lead's species in RAM (test harness; h = h.H). The record stays a valid
encrypted Gen 5 Pokémon (blocks shuffled by the PID, LCG-encrypted with the checksum), so the follower
code's party hash changes and it re-skins the follower as after a lead swap."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import struct

ORDERS = ['ABCD', 'ABDC', 'ACBD', 'ACDB', 'ADBC', 'ADCB', 'BACD', 'BADC', 'BCAD', 'BCDA', 'BDAC', 'BDCA',
          'CABD', 'CADB', 'CBAD', 'CBDA', 'CDAB', 'CDBA', 'DABC', 'DACB', 'DBAC', 'DBCA', 'DCAB', 'DCBA']


def lcg_xor(data, seed):
    out = bytearray(data)
    s = seed
    for i in range(0, len(out) - 1, 2):
        s = (s * 0x41C64E6D + 0x6073) & 0xFFFFFFFF
        struct.pack_into('<H', out, i, struct.unpack_from('<H', out, i)[0] ^ (s >> 16))
    return out


def lead_addr(h, slot=0):
    party = h.r32(h.gd() + 0x194)
    return party + 8 + 0xDC * slot


def read_box(h, a):
    return bytes(h.m[a + i] for i in range(0x88))


def set_species(h, species, form=0, slot=0):
    """-> old species. Retries a few frames later if the record doesn't decrypt to its checksum right now
    (seen once: the game was in the middle of rewriting it)."""
    for i in range(10):
        try:
            return _set_species(h, species, form, slot)
        except AssertionError:
            if i == 9:
                raise
            h.step(1)


def _set_species(h, species, form, slot):
    a = lead_addr(h, slot)
    raw = read_box(h, a)
    pid, flags, chk = struct.unpack_from('<IHH', raw, 0)
    assert not flags & 3, 'record is decrypted right now'
    dec = lcg_xor(raw[8:], chk)
    assert sum(struct.unpack('<64H', dec)) & 0xFFFF == chk, \
        f'checksum mismatch: not a party record at {a:#x} (pid {pid:#x} flags {flags:#x} chk {chk:#x})'
    order = ORDERS[((pid & 0x3E000) >> 0xD) % 24]
    ba, bb = 0x20 * order.index('A'), 0x20 * order.index('B')
    old = struct.unpack_from('<H', dec, ba)[0]
    struct.pack_into('<H', dec, ba, species)
    dec[bb + 0x18] = dec[bb + 0x18] & 7 | form << 3
    chk = sum(struct.unpack('<64H', dec)) & 0xFFFF
    enc = lcg_xor(dec, chk)
    h.w16(a + 6, chk)
    for i, v in enumerate(enc):
        h.w8(a + 8 + i, v)
    return old
