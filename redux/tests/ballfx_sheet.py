#!/usr/bin/env python3
"""ballfx_sheet.py DIR FIRST LAST STEP OUT.png [x0 y0 x1 y1] [scale] : contact sheet of recorded frames
(numbered 000001.png ...), each cropped and labelled with its frame number."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '.')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, sys
from PIL import Image, ImageDraw
d, a, b, s, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
box = tuple(int(v) for v in sys.argv[6:10]) if len(sys.argv) >= 10 else (0, 0, 256, 192)
k = int(sys.argv[10]) if len(sys.argv) > 10 else 2
frames = list(range(a, b + 1, s))
w, h = (box[2] - box[0]) * k, (box[3] - box[1]) * k
cols = max(1, min(len(frames), 1600 // w))
rows = (len(frames) + cols - 1) // cols
sheet = Image.new('RGB', (cols * w, rows * (h + 12)), 'black')
dr = ImageDraw.Draw(sheet)
for i, f in enumerate(frames):
    p = os.path.join(d, f'{f:06d}.png')
    if not os.path.exists(p):
        continue
    im = Image.open(p).convert('RGB').crop(box).resize((w, h), Image.NEAREST)
    x, y = (i % cols) * w, (i // cols) * (h + 12)
    sheet.paste(im, (x, y + 12))
    dr.text((x + 2, y), str(f), fill='yellow')
sheet.save(out)
print(out, sheet.size)
