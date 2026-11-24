"""shoot.py EMU ROM DSV OUTDIR SEQ... : Continue, then for each SEQ item (KEY[:WAIT] | T:x,y[:WAIT] | W:n | goto:x,z)
give it and wait (default 60 frames), screenshot NN_item.png; a contact sheet sheet.png at the end.
A state file OUTDIR/boot.state is reused when present (same ROM)."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image
import mh, flow

kind, rom, dsv, out = sys.argv[1:5]
os.makedirs(out, exist_ok=True)
E = mh.emu(kind, rom, dsv, tag='shoot_' + os.path.basename(out))
flow.start(E, out)
shots = []
for i, item in enumerate(sys.argv[5:]):
    flow.do(E, item)
    p = f'{out}/{i:02d}_{item.replace(":", "_").replace(",", "_")}.png'
    E.image().save(p)
    shots.append(p)
    print(item, 'pos', E.pos(), 'frame', E.frame, flush=True)
if shots:
    n = len(shots)
    cols = min(n, 6)
    rows = (n + cols - 1) // cols
    S = Image.new('RGB', (cols * 256, rows * 384))
    for i, p in enumerate(shots):
        S.paste(Image.open(p), ((i % cols) * 256, (i // cols) * 384))
    S.save(f'{out}/sheet.png')
