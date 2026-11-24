#!/usr/bin/env python3
"""solve_overlay.py N...: recover Redux overlay N (vanilla-model fills + hole solver) into
build/overlays/redux_overlay_N.bin and report how far it differs from vanilla."""
import json, os, sys, time
import redux_rom as R, overlays as O, blzsolve


def solve(n, rom, fat, model):
    van = R.Vanilla(f'overlay_{n}')
    ent = rom.overlay_entry(n)
    ram = ent['ram'] if all(ent['known'][4:8]) else van.base
    shift = van.base - ram
    name, s, e = fat[n]
    data = rom.read(s, e - s)
    m = rom.mask(s, e - s)
    unknown = [p for p in range(len(data)) if not m[p]]
    srcs = {p: S for p in unknown if (S := rom.source_offset(s + p)) is not None}
    filled, nf, nu = O.fill_model(data, unknown, srcs, model)
    known = bytearray(m)
    for p in unknown:
        S = srcs.get(p)
        if S is not None and model.byte(S) is not None:
            known[p] = 1
    total = len(data) + int.from_bytes(filled[-4:], 'little')
    exp, ok = bytearray(total), bytearray(total)
    for i, b in enumerate(van.data):
        if 0 <= shift + i < total:
            exp[shift + i] = b
            ok[shift + i] = 1
    t = time.time()
    out, inferred = blzsolve.Solver(filled, known, exp, ok).decode()
    diff = sum(1 for i in range(total) if ok[i] and out[i] != exp[i])
    res = dict(overlay=n, redux_ram=f'{ram:#010x}', size=total, holes=nu, inferred=len(inferred),
               diff_vs_vanilla=diff, new_front=shift, seconds=round(time.time() - t, 1))
    os.makedirs(O.OUT, exist_ok=True)
    with open(os.path.join(O.OUT, f'redux_overlay_{n}.bin'), 'wb') as f:
        f.write(out)
    with open(os.path.join(O.OUT, f'redux_overlay_{n}.json'), 'w') as f:
        json.dump({'ram': ram, 'inferred_stream_bytes': inferred}, f)
    return res


def main():
    rom = R.ReduxRom()
    fat = rom.fat()
    model = O.VanillaModel(rom, fat)
    for a in sys.argv[1:]:
        print(json.dumps(solve(int(a), rom, fat, model)), flush=True)


if __name__ == '__main__':
    main()
