"""ballgap.py RECDIR... : rows of field between the Poké Ball and its shadow during the wobbles.
Per frame: the shadow = dark grey pixels (40..100, near-neutral) in x 100-220, y 60-170; above the
shadow's top row at its centre column, count field rows (green) up to the ball. The wobble phase =
the last 60% of the frames where a shadow and the ball's red are both seen. Prints gap histogram."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import sys, os, collections
from PIL import Image


def grey(c):
    return 40 <= c[0] <= 100 and abs(c[0] - c[1]) < 12 and abs(c[1] - c[2]) < 12


def green(c):
    return c[1] > c[0] + 40 and c[1] > c[2]


for d in sys.argv[1:]:
    gaps, names = [], []
    for f in sorted(x for x in os.listdir(d) if x.endswith('.png')):
        px = Image.open(os.path.join(d, f)).convert('RGB').load()
        pts = [(x, y) for y in range(60, 170) for x in range(100, 220, 1) if grey(px[x, y])]
        if len(pts) < 20:
            continue
        top = min(y for x, y in pts)
        xs = [x for x, y in pts if y <= top + 1]
        cx = sorted(xs)[len(xs) // 2]
        red = any(px[x, y][0] > 180 and px[x, y][1] < 100 for y in range(max(40, top - 40), top) for x in range(cx - 10, cx + 10))
        if not red:
            continue
        g = 0
        y = top - 1
        while y > 40 and green(px[cx, y]):
            g += 1
            y -= 1
        gaps.append(g)
        names.append(f)
    tail = gaps[len(gaps) * 2 // 5:]
    if os.environ.get('VERBOSE'):      # frames of the wobble phase with a gap of 2+ rows
        print(d, 'gap>=2 frames:', [(n, g) for n, g in zip(names[len(gaps) * 2 // 5:], tail) if g >= 2])
    print(f'{d}: {len(gaps)} frames with ball+shadow; wobble-phase gap rows {sorted(collections.Counter(tail).items())}')
