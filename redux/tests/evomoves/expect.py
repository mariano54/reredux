"""expect.py : what the EVO/MOVES page should list, computed from a ROM's own data (a/0/1/9 evolutions, a/0/1/8
learnsets, a/0/1/6 personal for form entries), as evomoves.c does (family rows: root, then depth first; a second
method to the same species is a continuation row 0x8000 | evo index)."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import struct, sys
sys.path.insert(0, f'{RR_RX}/tools')
import ndsfs

ROM = f'{RR_B}/out/em_en.nds'
N = 650
_rom = ndsfs.Rom(ROM)
_fid = {v: k for k, v in _rom.paths.items()}
_evo_files = ndsfs.narc(_rom.file(_fid['a/0/1/9']))
_learn = ndsfs.narc(_rom.file(_fid['a/0/1/8']))
_pers = ndsfs.narc(_rom.file(_fid['a/0/1/6']))
EVO, FIRST = [], []
for s in range(N):
    FIRST.append(len(EVO))
    d = _evo_files[s]
    for k in range(0, len(d) - len(d) % 6, 6):
        m, p, t = struct.unpack_from('<HHH', d, k)
        if m and 0 < t < N:
            EVO.append((m, p, t))
FIRST.append(len(EVO))


def evos(s):
    return [(i, EVO[i]) for i in range(FIRST[s], FIRST[s + 1])]


def prevo(sp):
    for s in range(1, N):
        for i, (m, p, t) in evos(s):
            if t == sp:
                return s
    return -1


def family(species):
    if not 0 < species < N:
        return []
    root = species
    for _ in range(6):
        p = prevo(root)
        if p <= 0:
            break
        root = p
    rows = [root]

    def walk(sp, depth):
        if depth > 4:
            return
        ev = evos(sp)
        for k, (i, (m, p, t)) in enumerate(ev):
            if any(tt == t for _, (_, _, tt) in ev[:k]):
                continue
            rows.append(t)
            for j, (mm, pp, tt) in ev[k + 1:]:
                if tt == t:
                    rows.append(0x8000 | j)
            if t != sp:
                walk(t, depth + 1)
    walk(root, 0)
    return rows[:16]


def dat_id(species, form):
    d = _pers[species]
    form_stats, count = struct.unpack_from('<H', d, 0x1C)[0], d[0x20]
    if form_stats and form and form < count:
        return form_stats + form - 1
    return species


def learnset(species, form=0):
    if not 0 < species < N:
        return []
    d = _learn[dat_id(species, form)]
    out = []
    for k in range(0, len(d) - 3, 4):
        mv, lv = struct.unpack_from('<HH', d, k)
        if mv == 0xFFFF and lv == 0xFFFF:
            break
        out.append((lv, mv))
    return out[:32]


if __name__ == '__main__':
    for a in sys.argv[1:]:
        s, f = (list(map(int, a.split(':'))) + [0])[:2]
        print(s, f, 'family', family(s), 'dat', dat_id(s, f), 'learn', learnset(s, f))
