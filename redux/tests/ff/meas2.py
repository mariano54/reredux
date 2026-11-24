"""meas2.py ROM ELF TAG : Continue (smoke save, Pokémon Center), measure the follower's feet vs. its
shadow beside the player indoors (not for large sprites), then outside (Aspertia) to the player's right,
below and above him, and record a walk. Prints foot rows over the bob cycle - shadow top row.
Shots: ff/out/TAG/."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from h import H, FF
from PIL import ImageChops

rom, elf, tag = sys.argv[1:4]
h = H(rom, tag, FF + '/sav/' + os.environ.get('SAV', 'rel_en_smoke_en.dsv'), elf)
ok = h.cont()
if os.environ.get('SPECIES'):       # shadow work: another lead (party.py), re-skinned in place
    from party import set_species
    set_species(h, int(os.environ['SPECIES']))
    h.step(30)
print(tag, 'field', ok, h.zone(), h.pos(), h.fpos())
NODE11_KEEP = 0x02196D6A        # `beq` (node 11 never keeps its height): nop'd while measuring


def scr():
    return h.emu.screenshot().convert('RGB').crop((0, 0, 256, 192))


def actor(uid):
    field = h.r32(h.gsys() + 0x20)
    return h.find_actor(h.r32(field + 0x40), uid)


def clusters(mask, x0=0, x1=256, minpx=2):
    px = mask.load()
    rows = [y for y in range(192) if sum(1 for x in range(x0, x1) if px[x, y]) >= minpx]
    out, cur = [], []
    for y in rows:
        if cur and y > cur[-1] + 2:
            out.append(cur)
            cur = []
        cur.append(y)
    if cur:
        out.append(cur)
    return out


def diff(a, b):
    return ImageChops.difference(a, b).convert('L').point(lambda v: 255 if v > 8 else 0)


def measure(label, uid=0xF8, frames=40):
    a = actor(uid)
    if not a:
        print(label, 'no actor')
        return
    h.step(10)
    # foot rows over the bob cycle (darkest outline pixel), in the sprite's columns found below
    seq = []
    for k in range(frames // 2):
        h.step(2)
        seq.append(scr())
    i0 = scr()
    y0, z0 = h.r32(a + 0x54), h.r32(a + 0x4C)
    keep = h.r16(NODE11_KEEP)
    h.w16(NODE11_KEEP, 0x46C0)
    h.w32(a + 0x54, 80 << 12)
    h.step(20)
    i1 = scr()
    h.w32(a + 0x4C, z0 - (80 << 12))
    h.step(6)
    i2 = scr()
    h.w32(a + 0x4C, z0)
    h.w32(a + 0x54, y0)
    h.w16(NODE11_KEEP, keep)
    h.step(10)
    sm = diff(i0, i1)
    cs = clusters(sm)
    if not cs:
        print(label, 'sprite not found')
        return
    spr = cs[-1]
    bb = sm.crop((0, spr[0], 256, spr[-1] + 1)).getbbox()
    x0, x1 = bb[0], bb[2]
    shc = [c for c in clusters(diff(i1, i2), x0, x1, 3) if c[-1] >= spr[-1] - 12 and c[0] <= spr[-1] + 14]
    sh = (shc[-1][0], shc[-1][-1]) if shc else None
    feet = []
    for im in seq:
        d = diff(im, i1).crop((x0, 0, x1, 192))
        c = clusters(d, 0, x1 - x0, 2)
        c = [k for k in c if k[-1] >= spr[0]]
        if c:
            feet.append(c[-1][-1])
    hist = sorted((r, feet.count(r)) for r in set(feet))
    gap = [r - sh[0] for r, _ in hist] if sh else None
    print(f'{tag} {label}: sprite x{x0}-{x1} rows {spr[0]}-{spr[-1]}; feet {hist}; shadow {sh}; feet - shadow top {gap}', flush=True)
    h.shot(label)
    px = i0.load()
    pf = max((y for y in range(40, 160) for x in range(121, 136) if sum(px[x, y]) < 120), default=None)
    if sh and pf and abs(pf - sh[0]) < 12:
        print(f'{tag} {label}: player feet {pf} - shadow top (same row) {pf - sh[0]}')
    return gap


def one_tile(d, after=4):
    """field-feel: hold d until the tile changes (one step at 16/8/4 frames per tile), not 8 frames"""
    from desmume.controls import Keys, keymask
    p = h.pos()
    h.emu.input.keypad_add_key(keymask(getattr(Keys, 'KEY_' + d)))
    for _ in range(20):
        h.step(1)
        if h.pos() != p:
            break
    h.emu.input.keypad_rm_key(keymask(getattr(Keys, 'KEY_' + d)))
    h.step(after)


def walk(d, tiles):
    for _ in range(tiles):
        one_tile(d, 4)
    h.step(30)


large = h.r16(actor(0xF8) + 0xE4 + 7) & 0xFF == 2 if actor(0xF8) else True
if actor(0xF8):
    h.hold('LEFT', 3)
    h.step(30)
    measure('pc_left')
for d in ['DOWN'] * 4 + ['LEFT'] + ['DOWN'] * 4 + ['LEFT'] + ['DOWN'] * 4 + ['RIGHT'] * 3 + ['DOWN'] * 4:
    if h.zone() != 435:
        break
    one_tile(d, 6)
print(tag, 'exit at', h.pos())
h.wait_field(1500, 30)
print(tag, 'outside', h.zone(), h.pos(), h.fpos())
walk('RIGHT', 4)
measure('out_left')            # follower left of the player, facing right
walk('DOWN', 2)
measure('out_above')           # behind the player, facing down
walk('RIGHT', 2)
walk('UP', 2)
measure('out_below')           # below the player, facing up
walk('LEFT', 1)
measure('out_right')           # right of the player, facing left
h.rec = h.dir + '/rec'
os.makedirs(h.rec, exist_ok=True)
for f in os.listdir(h.rec):
    os.remove(os.path.join(h.rec, f))
walk('RIGHT', 3)
walk('DOWN', 2)
h.rec = None
print(tag, 'done', h.zone(), h.pos(), h.fpos())
