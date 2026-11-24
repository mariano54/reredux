"""perm.py : walkability of map tiles from the map permission grids (named tree build/named/redux).

A map model file (a/0/0/8, magic 'WB'/'GC') has a permission section: u16 32, u16 32, then 32x32 tiles of 8
bytes; u16 at +4 is the collision class (0 walkable, 1 wall; 2 = flowers / decoration, walkable; 0x1E, 0x1F, 3
walkable edges/bridges; 4 tall grass; 0x73 ledge (one-way, treated as blocked); 0x3D / 0x41 / 0xDE water and
fountain = blocked). A zone's map matrix (zone header +4, a/0/0/9) gives the model per 32x32 cell; world tile =
cell * 32 + grid tile (calibrated in Aspertia against the player positions seen in DeSmuME).
set_zone(z) selects the zone's matrix (default: matrix 0, the overworld)."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import json, os, struct
N = f'{RR_B}/named/redux'
WALK = {0, 2, 3, 4, 0x1E, 0x1F}
_manifest = None
_matrix_cache = {}
_cache = {}
_cur = [0]


def _matrix(idx):
    global _manifest
    if idx not in _matrix_cache:
        if _manifest is None:
            _manifest = json.load(open(N + '/manifest.json'))
        rel = next(k for k, v in _manifest.items() if v[0] == 'a/0/0/9' and v[1] == idx)
        _matrix_cache[idx] = json.load(open(os.path.join(N, rel)))
    return _matrix_cache[idx]


def set_zone(zone):
    """use zone's map matrix for the following lookups"""
    if zone is None:
        return
    d = [p for p in os.listdir(N + '/zones') if p.startswith(f'{zone:03d}_')]
    if d:
        _cur[0] = json.load(open(f'{N}/zones/{d[0]}/zone.json'))['matrix']


def _grid(cx, cz):
    m = _matrix(_cur[0])
    key = (_cur[0], cx, cz)
    if key not in _cache:
        mid = m['maps'][cz][cx] if 0 <= cz < m['height'] and 0 <= cx < m['width'] else None
        if mid is None:
            _cache[key] = None
        else:
            d = open(f'{N}/maps/models/{mid:04d}.bin', 'rb').read()
            o = struct.unpack_from('<I', d, 8)[0]
            _cache[key] = d[o + 4:o + 4 + 0x2000]
    return _cache[key]


def cls(x, z):
    if x < 0 or z < 0:
        return None
    p = _grid(x // 32, z // 32)
    if p is None:
        return None
    return struct.unpack_from('<H', p, ((z % 32) * 32 + x % 32) * 8 + 4)[0]


def walkable(x, z):
    return cls(x, z) in WALK
