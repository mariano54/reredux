"""r3_sheet.py DIR OUT.png [FIRST LAST] : tile the top screens of DIR/*.png (sorted) into a contact sheet."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '.')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import glob, os, sys
from PIL import Image, ImageDraw
files = sorted(glob.glob(os.path.join(sys.argv[1], '*.png')))
if len(sys.argv) > 4:
    files = files[int(sys.argv[3]):int(sys.argv[4])]
cols = 6
rows = (len(files) + cols - 1) // cols
sheet = Image.new('RGB', (cols * 256, rows * 204), 'white')
for i, f in enumerate(files):
    im = Image.open(f).crop((0, 0, 256, 192))
    x, y = (i % cols) * 256, (i // cols) * 204
    sheet.paste(im, (x, y + 12))
    ImageDraw.Draw(sheet).text((x + 2, y), os.path.basename(f), fill='black')
sheet.save(sys.argv[2])
