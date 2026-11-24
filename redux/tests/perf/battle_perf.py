"""Compare rendering optimizations in an unchanged battle scene. Same-ROM
savestate, copied QA battery save, fixed RTC/inputs, actual 3D swaps, screen and
battle-state hashes, and emulated ARM9 busy cycles. No animation interpolation.
"""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import rrenv
sys.path.insert(0, str(HERE))
from mlperf import Melon, Field


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--rom', required=True)
    ap.add_argument('--save', required=True, help='Route 19 QA battery save (never the player save)')
    ap.add_argument('--map', required=True, dest='mp')
    ap.add_argument('--out', required=True)
    ap.add_argument('--kind', choices=('fast-dma',), default='fast-dma')
    ap.add_argument('--mode', choices=('J', 'I'), default='J')
    ap.add_argument('--frames', type=int, default=1800)
    ap.add_argument('--encounter', choices=('wild', 'trainer'), default='wild')
    ap.add_argument('--move', type=int, choices=range(4), default=1)
    ap.add_argument('--capture', default='', help='Comma-separated zero-based sample frames to save')
    args = ap.parse_args()
    sym = json.loads(Path(args.mp).read_text())['symbols']
    capture = {int(i) for i in args.capture.split(',') if i}
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    before = hashlib.sha1(Path(args.save).read_bytes()).hexdigest()
    os.environ['ML_JIT'] = '1' if args.mode == 'J' else '0'
    m = Melon(str(Path(rrenv.RR_REAL_B) / 'perf-melon/libperf.dylib'), args.rom, args.save)
    m.set_rtc(2026, 10, 22, 12, 0)
    f = Field(m)
    m.step(400)
    for _ in range(300):
        m.hold('A', 6)
        m.step(10)
        if f.ready():
            break
    assert f.wait_ready(2000), 'Continue failed'
    m.step(60)

    def loaded():
        return m.r32(0x021DF2C0) == 0x021F4240 and 0x02000000 <= m.r32(0x021F4240) < 0x02400000

    m.L.ml_fb.restype = ctypes.POINTER(ctypes.c_uint32)

    def menu():
        c = m.L.ml_fb(1)[165 * 256 + 215]
        return all(abs(x-y) <= 4 for x, y in zip(((c >> 16) & 255, (c >> 8) & 255, c & 255),
                                                (112, 216, 48)))

    if args.encounter == 'trainer':
        m.hold('DOWN', 10)
        m.step(4)
    else:
        for i in range(600):
            m.hold('LEFT' if (i // 2) % 2 else 'RIGHT', 10)
            m.step(4)
            if loaded():
                break
    for _ in range(300):
        if menu():
            break
        m.hold('A' if args.encounter == 'trainer' else 'B', 6)
        m.step(14)
    assert menu(), 'Battle menu not reached'
    m.screenshot(str(out / 'menu.png'))
    state = str(out / 'menu.mlst')
    assert m.state_save(state) > 0
    ram = m.ram_bytes()
    candidates = [0x02000000+i-0x464 for i in range(0x464, len(ram), 4)
                  if ram[i:i+4] == struct.pack('<I', 0x0219BBED)]
    candidates = [p for p in candidates if m.r32(p + 0xC8) == p and m.r32(p + 0x1B0) == p]
    assert len(candidates) == 1, candidates
    wk = candidates[0]

    def battle_hash():
        if not loaded():
            return None
        regions = [(wk, 0x47C), (m.r32(wk + 8), 0xCC4)]
        for pc in (wk + 0xC8, wk + 0x1B0):
            for j in range(24):
                p = m.r32(pc + 0x84 + j * 4)
                if 0x02000000 <= p < 0x023FFE08:
                    regions.append((p, 0x1F8))
        h = hashlib.sha256()
        for p, n in sorted(set(regions)):
            h.update(bytes(m.ram[p & 0x3FFFFF:(p & 0x3FFFFF) + n]))
        return h.hexdigest()

    runs = []
    for on in (0, 1):
        assert m.state_load(state) == 0
        m.w8(sym['perf_dbg'] + 2, int(not on))
        m.w32(0x0214697C, on)
        m.step(4)   # framebuffers are not serialized in the state
        rows = []
        for i in range(args.frames):
            # Idle -> FIGHT -> selected move -> message advances.
            touch = 240 <= i < 246 or 306 <= i < 312
            x, y = ((128, 80) if i < 306 else
                    (60 + 130 * (args.move % 2), 55 + 50 * (args.move // 2)))
            keys = 2 if i >= 372 and i % 30 < 6 else 0
            before_swap, (t0, h0) = m.swapinfo()[2], m.a9()
            m.L.ml_frame(keys, int(touch), x, y)
            m.frame += 1
            t1, h1 = m.a9()
            rows.append(dict(i=i, swaps=m.swapinfo()[2] - before_swap,
                             busy_cycles=t1-t0-(h1-h0), pixels=[m.hash(), m.hash(1)],
                             battle_hash=battle_hash(), loops=m.r32(0x0209DA64)))
            if i in capture:
                m.screenshot(str(out / f'{"on" if on else "off"}-{i:04d}.png'))
        m.screenshot(str(out / ('on.png' if on else 'off.png')))
        runs.append(rows)
        print('completed', on, len(rows), flush=True)
    assert hashlib.sha1(Path(args.save).read_bytes()).hexdigest() == before
    result = dict(emulator='melonDS', jit=bool(m.jit_on()), kind=args.kind,
                  encounter=args.encounter, move=args.move,
                  save_sha1=before, rom=args.rom, runs=runs)
    (out / 'trace.json').write_text(json.dumps(result))
    averages = [sum(r['busy_cycles'] for r in rr) / len(rr) for rr in runs]
    last_hashes = [next((r['battle_hash'] for r in reversed(rr) if r['battle_hash']), None) for rr in runs]
    summary = dict(frames=args.frames, jit=result['jit'], kind=args.kind,
                   encounter=args.encounter, move=args.move,
                   differences={k: sum(a[k] != b[k] for a, b in zip(*runs))
                                for k in ('swaps', 'battle_hash', 'loops', 'pixels')},
                   different_screens=[sum(a['pixels'][s] != b['pixels'][s] for a, b in zip(*runs))
                                      for s in (0, 1)],
                   missing_swaps=[sum(r['swaps'] == 0 for r in rr) for rr in runs],
                   last_battle_equal=last_hashes[0] is not None and last_hashes[0] == last_hashes[1],
                   idle_busy_cycles=[sum(r['busy_cycles'] for r in rr[:240]) / 240 for rr in runs],
                   all_busy_cycles=averages, reduction_percent=100*(averages[0]-averages[1])/averages[0])
    (out / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
