"""sheet.py DIR OUT.png [--both] [--cols N] : contact sheet of DIR/*.png (sorted), top screens or both screens."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import argparse, glob, os
from PIL import Image, ImageDraw

ap = argparse.ArgumentParser()
ap.add_argument('src')
ap.add_argument('out')
ap.add_argument('--both', action='store_true')
ap.add_argument('--cols', type=int, default=0)
a = ap.parse_args()
files = sorted(f for f in glob.glob(os.path.join(a.src, '*.png')))
if not files:
    raise SystemExit('no shots in ' + a.src)
h = 384 if a.both else 192
cols = a.cols or (8 if a.both else 6)
rows = (len(files) + cols - 1) // cols
sheet = Image.new('RGB', (cols * 256, rows * (h + 12)), 'white')
d = ImageDraw.Draw(sheet)
for i, f in enumerate(files):
    im = Image.open(f).convert('RGB')
    im = im.crop((0, 0, 256, min(h, im.size[1])))
    x, y = (i % cols) * 256, (i // cols) * (h + 12)
    sheet.paste(im, (x, y + 12))
    d.text((x + 2, y), os.path.basename(f)[:40], fill='black')
sheet.save(a.out)
print('sheet', a.out, len(files), 'shots')
