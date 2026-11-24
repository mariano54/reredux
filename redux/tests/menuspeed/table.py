"""table.py COL=FILE.json... [--md] : per-step table of ready (and first response) frames, mean over the phases,
one column per sweep JSON (same scenario), in the first column's step order."""
import json, sys

a = [x for x in sys.argv[1:] if not x.startswith('--')]
md = '--md' in sys.argv
cols = []
for x in a:
    name, f = x.split('=', 1)
    cols.append((name, json.load(open(f))))


def mean(v):
    v = [x for x in v if x is not None]
    return sum(v) / len(v) if v else None


def fmt(r):
    if r is None:
        return '-'
    rd, rs = mean(r['ready']), mean(r['resp'])
    return f'{rd:.1f}' if rd is not None else f'({rs})'


order = []
for _, d in cols:
    for k in d['_order']:
        if k not in order:
            order.append(k)
names = [c[0] for c in cols]
if md:
    print('| step | ' + ' | '.join(names) + ' |')
    print('|---|' + '---|' * len(names))
else:
    print(f'{"step":30s}' + ''.join(f'{n:>10s}' for n in names))
tot = [0.0] * len(cols)
for k in order:
    vals = [fmt(d.get(k)) for _, d in cols]
    for i, (_, d) in enumerate(cols):
        r = d.get(k)
        m = mean(r['ready']) if r else None
        tot[i] += m or 0
    if md:
        print(f'| {k} | ' + ' | '.join(vals) + ' |')
    else:
        print(f'{k:30s}' + ''.join(f'{v:>10s}' for v in vals))
if md:
    print('| **sum** | ' + ' | '.join(f'**{t:.0f}**' for t in tot) + ' |')
else:
    print(f'{"sum":30s}' + ''.join(f'{t:10.0f}' for t in tot))
