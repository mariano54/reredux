"""labelsheet.py OUT.png IMG LABEL [IMG LABEL ..] : both-screen shots side by side (2x), each with its label"""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import sys
from PIL import Image, ImageDraw
out = sys.argv[1]
pairs = list(zip(sys.argv[2::2], sys.argv[3::2]))
S, cols = 2, 6
w, h = 256 * S, 384 * S + 18
rows = (len(pairs) + cols - 1) // cols
sheet = Image.new('RGB', (cols * (w + 6), rows * (h + 6)), (255, 255, 255))
d = ImageDraw.Draw(sheet)
for k, (p, label) in enumerate(pairs):
    im = Image.open(p).convert('RGB').resize((w, 384 * S), Image.NEAREST)
    x, y = (k % cols) * (w + 6), (k // cols) * (h + 6)
    d.text((x + 4, y + 3), label, fill=(0, 0, 0))
    sheet.paste(im, (x, y + 18))
sheet.save(out)
print('wrote', out)
