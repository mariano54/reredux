#!/usr/bin/env python3
"""show_func.py ADDR [module]: side-by-side vanilla/Redux disassembly of one function (U = unknown byte)."""
import sys, bisect
import redux_rom as R, diffutil as D, arm9_changes as A
addr = int(sys.argv[1], 16); mod = sys.argv[2] if len(sys.argv) > 2 else 'main'
rom = R.ReduxRom(); van = R.Vanilla(mod)
off = (lambda a: R.ARM9_ROM + a - R.ARM9_RAM) if mod == 'main' else (lambda a: R.ARM9_ROM + (A.ITCM_IN_ARM9 - R.ARM9_RAM) + (a - A.ITCM_RAM))
red, known, unv = A.redux_view(rom, van, off)
fs = R.functions(mod); st = [f[0] for f in fs]; k = st.index(addr); end = st[k + 1]; mode = fs[k][2]
i0, i1 = addr - van.base, end - van.base
v = D.disasm(van.data[i0:i1], addr, mode); r = {l[0]: l for l in D.disasm(red[i0:i1], addr, mode)}
for a, hx, ins in v:
    rr = r.get(a)
    u = ''.join('U' if not known[a - van.base + j] else '.' for j in range(len(hx.replace(' ', '')) // 2))
    mark = '  ' if rr and rr[1] == hx else '>>'
    print(f'{mark} {a:08X} {hx:>9} {ins:<34} | {rr[1] if rr else "":>9} {rr[2] if rr else ""}  {u if "U" in u else ""}')
