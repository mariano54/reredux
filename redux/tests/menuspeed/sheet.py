"""sheet.py DIR OUT.png [COLS] [SCALE] : contact sheet of DIR/*.png (sorted), labelled with the file names."""
import os, sys
from PIL import Image, ImageDraw

d, out = sys.argv[1:3]
cols = int(sys.argv[3]) if len(sys.argv) > 3 else 8
sc = float(sys.argv[4]) if len(sys.argv) > 4 else 0.5
fs = sorted(f for f in os.listdir(d) if f.endswith('.png'))
w, h = int(256 * sc), int(384 * sc)
rows = (len(fs) + cols - 1) // cols
S = Image.new('RGB', (cols * w, rows * (h + 12)), (255, 255, 255))
D = ImageDraw.Draw(S)
for i, f in enumerate(fs):
    im = Image.open(os.path.join(d, f)).convert('RGB').resize((w, h))
    x, y = (i % cols) * w, (i // cols) * (h + 12)
    S.paste(im, (x, y + 12))
    D.text((x + 2, y), f[:-4][:24], fill=(0, 0, 0))
S.save(out)
print(out, len(fs))
