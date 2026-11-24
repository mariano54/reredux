"""Paired fast display-list DMA benchmark of one ROM/state with the
stock or FIFO-triggered SDK transfer. Each worker is a separate emulator process. Full
screen hashes are captured alongside CPU cycles, swaps, and missed draws.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import rrenv
sys.path.insert(0, str(HERE))
import perf


def sha1(p):
    h = hashlib.sha1()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def worker(rom, mp, state, spot, mode, off, out):
    import mlperf
    sym = json.loads(Path(mp).read_text())['symbols']
    pixels = []
    original = mlperf.Melon

    class Captured(original):
        def state_load(self, path):
            result = super().state_load(path)
            self.w8(sym['perf_dbg'] + 2, off)
            self.w32(0x0214697C, int(not off))
            self.step(4)  # rebuild framebuffers not serialized in the state
            return result

        def hash(self, screen=0):
            v = super().hash(screen)
            pixels.append([v, super().hash(1)])
            return v

    mlperf.Melon = Captured
    data = perf.w_run(rom, mp, state, spot, mode)
    data.update(pixels=pixels, stock_dma=bool(off))
    Path(out).write_text(json.dumps(data))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--rom', required=True)
    ap.add_argument('--map', required=True, dest='mp')
    ap.add_argument('--out', required=True)
    ap.add_argument('--spots', default='r20_long_aut,castelia')
    ap.add_argument('--modes', default='JI')
    ap.add_argument('--jobs', type=int, default=2)
    ap.add_argument('--worker', nargs=4, metavar=('STATE', 'SPOT', 'MODE', 'OFF'))
    args = ap.parse_args()
    if args.worker:
        state, spot, mode, off = args.worker
        worker(args.rom, args.mp, state, spot, mode, int(off), args.out)
        return
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    sh = sha1(args.rom)
    states = Path(rrenv.RR_REAL_B) / 'perfstates' / sh[:12]
    states.mkdir(parents=True, exist_ok=True)
    spots = args.spots.split(',')
    for spot in spots:
        state = states / (spot + '.mlst')
        if not state.exists():
            subprocess.run([rrenv.RR_PY, str(HERE / 'perf.py'), '--worker', 'gen', args.rom,
                            spot, str(state), str(out / ('gen_' + spot + '.json'))], check=True,
                           stdout=subprocess.DEVNULL)
    jobs = []
    for spot in spots:
        for mode in args.modes:
            for off in (1, 0):
                name = f'{spot}_{mode}_{off}'
                jobs.append((name, [rrenv.RR_PY, str(Path(__file__).resolve()), '--rom', args.rom,
                                    '--map', args.mp, '--out', str(out / (name + '.json')), '--worker',
                                    str(states / (spot + '.mlst')), spot, mode, str(off)]))
    running = []
    while jobs or running:
        while jobs and len(running) < args.jobs:
            name, command = jobs.pop(0)
            log = open(out / (name + '.log'), 'w')
            running.append((name, subprocess.Popen(command, stdout=log, stderr=log), log))
        name, proc, log = running.pop(0)
        status = proc.wait()
        log.close()
        if status:
            raise RuntimeError(f'{name} failed; see its log')
    summary = {}
    for spot in spots:
        for mode in args.modes:
            a = json.loads((out / f'{spot}_{mode}_1.json').read_text())
            b = json.loads((out / f'{spot}_{mode}_0.json').read_text())
            ca = sum(r['cyc'] for r in a['rows']) / a['frames']
            cb = sum(r['cyc'] for r in b['rows']) / b['frames']
            summary[f'{spot}/{mode}'] = dict(frames=a['frames'], old_cycles=ca, new_cycles=cb,
                reduction_percent=100 * (ca-cb) / ca,
                different_images=sum(x != y for x, y in zip(a['pixels'], b['pixels'])),
                lag=[sum(r['lag'] for r in data['rows']) for data in (a, b)],
                f60=[data['f60'] for data in (a, b)])
    report = dict(rom=str(Path(args.rom).resolve()), sha1=sh, summary=summary)
    (out / 'summary.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
