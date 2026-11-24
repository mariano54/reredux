"""profsum.py PROF.txt [NAMES.json] [N] : cycles per function (PC samples bucketed to the function starts of the
pokeblack2 disassembly; overlays by address only) from a libbf ml_prof_dump."""
import bisect, json, os, re, sys
from pathlib import Path
prof = sys.argv[1]
names = json.load(open(sys.argv[2])) if len(sys.argv) > 2 and sys.argv[2].endswith('.json') else {}
N = int(sys.argv[-1]) if sys.argv[-1].isdigit() else 40
ASM = os.path.join(os.environ.get('POKEBLACK2') or str(Path(__file__).resolve().parents[2] / 'build/ext/pokeblack2'), 'asm')
starts = {}
for f in os.listdir(ASM):
    if not f.endswith('.s'):
        continue
    mod = f[:-2]
    for l in open(os.path.join(ASM, f)):
        m = re.match(r'\s+(thumb|arm)_func_start FUN_([0-9A-F]{8})', l)
        if m:
            starts.setdefault(int(m.group(2), 16), set()).add(mod)
ks = sorted(starts)
tot = {}
other = halt = 0
for l in open(prof):
    a, c = l.split()
    if a == 'other':
        other = int(c)
        continue
    if a == 'halt':
        halt = int(c)
        continue
    pc, c = int(a, 16), int(c)
    i = bisect.bisect_right(ks, pc) - 1
    k = ks[i] if i >= 0 else 0
    tot[k] = tot.get(k, 0) + c
allc = sum(tot.values()) + other
print(f'busy {allc} other {other} halt {halt}  ({allc / max(1, allc + halt) * 100:.0f}% busy)')
for k, c in sorted(tot.items(), key=lambda x: -x[1])[:N]:
    mods = ','.join(sorted(starts.get(k, ())))[:40]
    print(f'{k:08X} {c:10d} {c / allc * 100:5.1f}%  {names.get(f"{k:08X}", "")}  [{mods}]')
