#!/usr/bin/env python3
"""desync.py ROM MAP STATE SCRIPT [A-knobs] [B-knobs] : logic-identity check for performance changes. Update-by-update
main RAM comparison of two melonDS runs of a ROM built with `--with fieldpark` (the ARM9 parks after every field
update; the keys of SCRIPT = K:N,.. (N updates each, K '' = none) are set while it is parked, so both runs see the same
keys in the same updates whatever their frame timing). STATE: e.g. one of build/perfstates/<sha1>/*.mlst made by
perf.py for that ROM. Knobs: comma list of SYM+OFF=VAL byte writes (fps60_dbg+0=0: 60 fps draws off,
fps60_dbg+159=1: no GX-FIFO DMA, perf_dbg+0=1: no HBlank gating) and 'jit' (JIT on).
Differences inside our own modules' data are dropped; the rest are listed as ranges with the updates they differ in,
and those inside the game's logic state (field actors, GameData window, GSYS, the field, GFL's RNG) are counted
first. Known timing-only differences: OS ticks, stacks, NNS / GX / DMA state, IRQ bookkeeping, and the play-time
seconds counter (the "playtime.c" work in the GameData window: it follows the real-time clock)."""
import ctypes, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rrenv  # noqa: E402
from mlperf import Melon, Field  # noqa: E402

LIB = os.environ.get('REDUX_PERF_LIB') or os.path.join(rrenv.RR_REAL_B, 'perf-melon', 'libperf.dylib')
KEYS = ['A', 'B', 'SELECT', 'START', 'RIGHT', 'LEFT', 'UP', 'DOWN', 'R', 'L', 'X', 'Y']
SIZE = 0x400000
OWN = ('fps60', 'fieldpark', 'perf_', 'bl_save', 'bl_moved', 'blr', 'ot', 'ot_', 'at', 'at_', 'anm_save', 'f60_')


def main():
    rom, mp, state, script = sys.argv[1:5]
    knA = sys.argv[5] if len(sys.argv) > 5 else ''
    knB = sys.argv[6] if len(sys.argv) > 6 else ''
    sym = json.load(open(mp))['symbols']
    P = sym['fieldpark_dbg']
    seq = []
    for it in script.split(','):
        k, n = it.split(':')
        v = 0
        for x in k.split('+'):
            if x:
                v |= 1 << KEYS.index(x)
        seq += [v] * int(n)
    regions = []

    def run(kn):
        os.environ['ML_JIT'] = '1' if 'jit' in kn.split(',') else '0'
        m = Melon(LIB, rom)
        assert m.state_load(state) == 0
        for x in kn.split(','):
            if '=' in x:
                k, v = x.split('=')
                s, o = k.split('+')
                m.w8(sym[s] + int(o), int(v))
        m.w8(P, 1)
        F = Field(m)
        f, gd = F.field(), F.gd()
        asys = m.r32(f + 0x40)
        gfl = m.r32(0x0209DA58 + 0x14)
        regions[:] = [('actors', m.r32(asys + 0x1C), m.r32(asys + 0x1C) + 0x100 * m.r16(asys + 4)),
                      ('gamedata', gd, gd + 0x10000), ('gsys', F.gsys(), F.gsys() + 0x100), ('field', f, f + 0x200),
                      ('rng', gfl, gfl + 0x18)]
        snaps, u, stuck = [], 0, 0
        m.keys = seq[0] if seq else 0
        while u < len(seq):
            m.step()
            if m.r8(P + 1):
                snaps.append(ctypes.string_at(m.ram, SIZE))
                u += 1
                m.keys = seq[u] if u < len(seq) else 0
                m.w8(P + 1, 0)
                stuck = 0
            else:
                stuck += 1
                if stuck > 600:
                    print('no park for 600 frames at update', u, '(a battle / an event?)')
                    break
        return snaps

    A, B = run(knA), run(knB)
    allsym = sorted((v & ~1, k) for k, v in sym.items())
    ivs = [(v, allsym[i + 1][0] if i + 1 < len(allsym) else v + 4) for i, (v, k) in enumerate(allsym) if k.startswith(OWN)]
    cnt, first, lastu = {}, {}, {}
    n = min(len(A), len(B))
    for i in range(n):
        ra, rb = A[i], B[i]
        if ra == rb:
            continue
        rng = []
        for blk in range(0, SIZE, 512):
            if ra[blk:blk + 512] == rb[blk:blk + 512]:
                continue
            for j in range(blk, blk + 512):
                if ra[j] != rb[j]:
                    a = 0x02000000 + j
                    if any(lo <= a < hi for lo, hi in ivs):
                        continue
                    if rng and a - rng[-1][1] <= 16:
                        rng[-1][1] = a
                    else:
                        rng.append([a, a])
        for a, b in rng:
            key = (a & ~0xF, b | 0xF)
            cnt[key] = cnt.get(key, 0) + 1
            first.setdefault(key, i)
            lastu[key] = i

    def region(a, b):
        return ','.join(nm for nm, lo, hi in regions if a < hi and b >= lo)
    print('updates compared %d (A %d, B %d) [%s] vs [%s]: differing ranges %d' % (n, len(A), len(B), knA, knB, len(cnt)))
    hits = [(k, region(*k)) for k in cnt if region(*k)]
    print('logic-state ranges differing:', len(hits), [('%08X' % k[0], r) for k, r in hits[:8]])
    if os.environ.get('DUMP'):
        lo, hi = (int(x, 16) for x in os.environ['DUMP'].split('-'))
        for i in range(n):
            x, y = A[i][lo - 0x02000000:hi - 0x02000000], B[i][lo - 0x02000000:hi - 0x02000000]
            if x != y:
                print('upd %3d A %s\n        B %s' % (i, x.hex(), y.hex()))
    for (a, b), c in sorted(cnt.items()):
        print('%08X-%08X %5d B  in %4d updates, first %d last %d %s' % (a, b, b - a + 1, c, first[(a, b)], lastu[(a, b)],
                                                                       region(a, b)))


if __name__ == '__main__':
    main()
