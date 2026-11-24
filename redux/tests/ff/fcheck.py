"""fcheck.py : follower checks shared by catch.py's POST step (integration QA, merged Redux 3.0).

actor(h, uid)              the field actor with that uid (0xF8 = the follower, 0xFF = the player)
measure(h, tag, label)     meas2.py's feet-vs-shadow measurement (same code), -> feet - shadow top rows
post_trace(h, frames)      per frame from the battle's end: event / field state, follower actor, its
                           WPosOffset y (+0x54, follow_wofs_hook's bob), model offset y (+0x7F)"""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os
from PIL import ImageChops

NODE11_KEEP = 0x02196D6A        # `beq` (node 11 never keeps its height): nop'd while measuring
FX = 0x1000


def actor(h, uid=0xF8):
    g = h.gsys()
    if not g:
        return None
    field = h.r32(g + 0x20)
    if not (0x02000000 <= field < 0x02400000):
        return None
    s = h.r32(field + 0x40)
    if not (0x02000000 <= s < 0x02400000):
        return None
    return h.find_actor(s, uid)


def scr(h):
    return h.emu.screenshot().convert('RGB').crop((0, 0, 256, 192))


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


def measure(h, tag, label, uid=0xF8, frames=40):
    a = actor(h, uid)
    if not a:
        print(tag, label, 'no actor')
        return None
    h.step(10)
    seq = []
    for k in range(frames // 2):
        h.step(2)
        seq.append(scr(h))
    i0 = scr(h)
    y0, z0 = h.r32(a + 0x54), h.r32(a + 0x4C)
    keep = h.r16(NODE11_KEEP)
    h.w16(NODE11_KEEP, 0x46C0)
    h.w32(a + 0x54, 80 << 12)
    h.step(20)
    i1 = scr(h)
    h.w32(a + 0x4C, z0 - (80 << 12))
    h.step(6)
    i2 = scr(h)
    h.w32(a + 0x4C, z0)
    h.w32(a + 0x54, y0)
    h.w16(NODE11_KEEP, keep)
    h.step(10)
    sm = diff(i0, i1)
    cs = clusters(sm)
    if not cs:
        print(tag, label, 'sprite not found')
        return None
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
    print(f'{tag} {label}: sprite x{x0}-{x1} rows {spr[0]}-{spr[-1]}; feet {hist}; shadow {sh}; feet - shadow top {gap}',
          flush=True)
    h.shot(label)
    return gap


def s32(v):
    return v - (1 << 32) if v & 0x80000000 else v


def post_trace(h, frames, recdir=None):
    """step `frames` frames; per frame (frame, field_ready, actor?, wofs y, model ofs y, brightness proxy)"""
    out = []
    if recdir:
        os.makedirs(recdir, exist_ok=True)
        for f in os.listdir(recdir):
            os.remove(os.path.join(recdir, f))
    for i in range(frames):
        h.step(1)
        a = actor(h)
        row = (h.frame, h.field_ready(), bool(a),
               s32(h.r32(a + 0x54)) if a else None,
               (h.m[a + 0x7F] - 256 if h.m[a + 0x7F] > 127 else h.m[a + 0x7F]) if a else None)
        out.append(row)
        if recdir:
            h.emu.screenshot().crop((0, 0, 256, 192)).save(f'{recdir}/{i:04d}.png', compress_level=1)
    return out
