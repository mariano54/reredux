"""sheet2.py DIR OUT.png [COLS] : contact sheet of DIR/*.png with both DS screens (256x384), labelled."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import glob, os, sys
from PIL import Image, ImageDraw
files = sorted(glob.glob(os.path.join(sys.argv[1], '*.png')))
cols = int(sys.argv[3]) if len(sys.argv) > 3 else 6
rows = (len(files) + cols - 1) // cols
sheet = Image.new('RGB', (cols * 256, rows * 396), 'white')
for i, f in enumerate(files):
    im = Image.open(f).convert('RGB')
    x, y = (i % cols) * 256, (i // cols) * 396
    sheet.paste(im, (x, y + 12))
    ImageDraw.Draw(sheet).text((x + 2, y), os.path.basename(f), fill='black')
sheet.save(sys.argv[2])
print(sys.argv[2], sheet.size)
