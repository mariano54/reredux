"""catch.py ROM TAG [frames] : Continue (smoke save), walk to Route 19's grass, wild battle, throw the first
Poké Ball, record the top screen every frame (build/ff_integ/out/TAG/rec) until the menu / yes-no comes back.
Works on vanilla Redux too (player position from the player actor). The encounter loop waits for the
battle itself (no fixed frame counts), so RNG shifts (battleexit, turbo) only move when it starts.
Env: SAV (battery copy in build/ff_integ/sav/), THROWS, PREWAIT, EFFDBG=hex|auto (auto: turbo_dbg from
QOLMAP=qol_map.json), TURBO=1 (R in the battle before the first throw; turbo_dbg checked),
POST=field (finish the battle, trace the follower's bob from the first field frames, feet vs shadow
before / after: fcheck.py); the fix-float agent's probes (FLAGS, NOEXTRA, TRACE, MSGFULL, ...) unchanged."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import sys, os
from collections import deque
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, f'{RR_T}/qa')
import perm                      # read-only: map permission grids of the named Redux tree
from h import H, FF
from desmume.controls import Keys, keymask

rom, tag = sys.argv[1:3]
nrec = int(sys.argv[3]) if len(sys.argv) > 3 else 900
h = H(rom, tag, FF + '/sav/' + os.environ.get('SAV', 'rel_en_smoke_en.dsv'))


def pos():
    field = h.r32(h.gsys() + 0x20)
    a = h.find_actor(h.r32(field + 0x40), 0xFF) if field else None
    if not a:
        return (-1, -1)
    return (h.s32(a + 0x44) >> 16, h.s32(a + 0x4C) >> 16)


def path(tx, tz, blocked):
    perm.set_zone(h.zone())
    s = pos()
    prev = {s: None}
    dq = deque([s])
    while dq:
        c = dq.popleft()
        if c == (tx, tz):
            break
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (c[0] + dx, c[1] + dz)
            if n in prev or n in blocked or (n != (tx, tz) and not perm.walkable(*n)):
                continue
            if abs(n[0] - s[0]) > 80 or abs(n[1] - s[1]) > 80:
                continue
            prev[n] = c
            dq.append(n)
    if (tx, tz) not in prev:
        return None
    out, c = [], (tx, tz)
    while c != s:
        out.append(c)
        c = prev[c]
    return out[::-1]


def nav(tx, tz):
    blocked = set()
    for _ in range(5):
        p = path(tx, tz, blocked)
        if p is None:
            print('no path', pos(), (tx, tz))
            return False
        ok = True
        for nx, nz in p:
            x, z = pos()
            d = 'RIGHT' if nx > x else 'LEFT' if nx < x else 'DOWN' if nz > z else 'UP'
            h.emu.input.keypad_add_key(keymask(getattr(Keys, 'KEY_' + d)))
            for i in range(30):
                h.step(1)
                if pos() != (x, z):
                    break
            h.emu.input.keypad_rm_key(keymask(getattr(Keys, 'KEY_' + d)))
            if pos() != (nx, nz):
                h.step(8)
                if pos() == (nx, nz):
                    continue
                blocked.add((nx, nz))
                ok = False
                break
        if ok or pos() == (tx, tz):
            h.step(8)
            return pos() == (tx, tz)
    return pos() == (tx, tz)


def wait_field_tap(n=3000):
    ok = 0
    for i in range(n):
        if h.field_ready():
            ok += 1
            if ok >= 40:
                return True
        else:
            ok = 0
        if i % 20 == 0 and not h.field_ready():
            h.hold('A', 6)
        else:
            h.step()
    return False


def ui():
    p = h.emu.screenshot().convert('RGB').getpixel
    if p((215, 357)) == (112, 216, 48):
        return 'menu'
    if p((128, 242))[0] > 200 and p((240, 212))[0] > 100 and p((240, 212))[1] < 40:
        return 'yesno'
    return None


def touch(x, y):
    h.emu.input.touch_set_pos(x, y)
    h.step(6)
    h.emu.input.touch_release()
    h.step(14)


TDBG = None                                     # turbo_dbg (QOLMAP=build/qol/LANG/qol_map.json; EFFDBG=auto)
if os.environ.get('QOLMAP'):
    import json
    TDBG = json.load(open(os.environ['QOLMAP']))['symbols'].get('turbo_dbg')
print(tag, 'field', h.cont(), h.zone(), pos())
h.step(int(os.environ.get('PREWAIT', '0')))     # other RNG / encounter
for it in filter(None, os.environ.get('FLAGS', '').split(',')):     # e.g. FLAGS=5DA=1 (speed-ups off)
    f, v = it.split('=')
    f, v = int(f, 16), int(v)
    ew = h.r32(h.gd() + 0x1AC)
    a = ew + 0x35E + (f >> 3)
    h.w8(a, h.r8(a) | 1 << (f & 7) if v else h.r8(a) & ~(1 << (f & 7)))
    print(tag, 'flag', hex(f), '=', v)
if os.environ.get('NOEXTRA'):          # turbo.c battle extra-tick countdown held at 0: no extra tick
    _nx = int(os.environ["NOEXTRA"], 16) if os.environ["NOEXTRA"] != "1" else 0x021FE8A0
    h.hooks.append(lambda hh: hh.w8(_nx + 3, 0))
trace = []
if os.environ.get('TRACE'):            # effect VM commands (VM_Control's dispatch `blx r2`, table _021F30B4)
    def _tr(addr, size):
        r = h.emu.memory.register_arm9
        if r.r3 == 0x021F30B4:
            trace.append((h.frame, r.r4, h.m[0x021FE89C], r.r2))
        return True
    h.emu.memory.register_exec(0x020159CE, _tr, 2)

    def _eff(addr, size):           # FUN_021E0EE8 (effect start): r3 = effect number
        r = h.emu.memory.register_arm9
        trace.append((h.frame, 1000 + r.r3, h.m[0x021FE89C], 0))
        return True
    h.emu.memory.register_exec(0x021E0EE8, _eff, 2)
effstate = []
if os.environ.get('EFFDBG'):           # per frame: turbo_dbg.extra_battle (addr EFFDBG), effect VM state, effect no
    tdbg = TDBG if os.environ['EFFDBG'] == 'auto' else int(os.environ['EFFDBG'], 16)

    def _eff_state(hh):
        w = hh.r32(0x021F4240)
        vm = hh.r32(w + 0x188) if 0x02000000 <= w < 0x02400000 else 0
        st = hh.r8(vm + 0x19) if 0x02000000 <= vm < 0x02400000 else -1
        ctx = hh.r32(vm + 0x2C) if st >= 0 else 0
        eff = hh.r16(ctx + 0x258) if 0x02000000 <= ctx < 0x02400000 else -1
        effstate.append((hh.frame, hh.r32(tdbg + 0x14), st, eff))
    h.hooks.append(_eff_state)
if os.environ.get('MSGFULL'):          # MSGFULL=ADDR of speed_msgwait (thumb): it returns the wait unchanged
    h.w16(int(os.environ['MSGFULL'], 16) & ~1, 0x4770)
if os.environ.get('PAGEFULL'):         # the 0xFF page wait back to 80
    def _pg(hh):
        if hh.r8(0x021D2E90) == 0xFF and hh.r8(0x021D2E96) == 0x3C:
            hh.w8(0x021D2E96, 0x50)
    h.hooks.append(_pg)
if os.environ.get('NOP1'):             # VM_Run resume-after-wait patch (speed P1) undone: `adds r0, r0, #1`
    h.hooks.append(lambda hh: (hh.w8(0x02015956, 0x40), hh.w8(0x02015957, 0x1C)))
if os.environ.get('DRAWEXTRA'):        # turbo_draw_gate: the extra tick draws too
    h.w16(0x021FDF76, 0x46C0)
for d in ['DOWN'] * 4 + ['LEFT'] + ['DOWN'] * 4 + ['LEFT'] + ['DOWN'] * 4:
    if h.zone() != 435:
        break
    h.hold(d, 8)
    h.step(6)
h.wait_field(1500, 30)
print(tag, 'outside', h.zone(), pos())
nav(52, 711)
for _ in range(2):
    h.hold('UP', 20)
    wait_field_tap()
nav(4, 2)
for _ in range(2):
    h.hold('UP', 20)
    wait_field_tap()
print(tag, 'route 19?', h.zone(), pos())
nav(60, 695)
if os.environ.get('POST'):
    import fcheck
    h.hold('LEFT', 3)                   # face left: the follower comes up beside the player
    h.wait_field(300, 30)
    print(tag, 'pre gap', fcheck.measure(h, tag, 'pre_field'))
inb = False
for i in range(600):
    h.hold('RIGHT' if (i // 2) % 2 else 'LEFT', 10)
    h.step(4)
    if not h.field_ready() and h.zone() is not None:
        # an event / battle: wait for the battle menu
        for k in range(150):
            h.step(20)
            if ui() == 'menu':
                inb = True
                break
            if k % 2 == 0:
                h.hold('A', 4)
        if inb:
            break
print(tag, 'battle menu', inb, 'frame', h.frame)
h.shot('menu', top=False)
if os.environ.get('TURBO') and TDBG:    # R in the battle: turbo on (2x battle), checked in turbo_dbg
    xb0 = h.r32(TDBG + 0x14)
    h.hold('R', 4)
    h.step(30)
    print(tag, 'turbo on', h.r8(TDBG), 'live', h.r8(TDBG + 1), 'extra battle ticks +', h.r32(TDBG + 0x14) - xb0)
f00 = h.frame
for k in range(int(os.environ.get('THROWS', '1'))):
    if ui() != 'menu':
        break
    touch(40, 165)
    h.step(60)
    touch(190, 40)
    h.step(60)
    touch(65, 30)
    h.step(60)
    h.rec = h.dir + ('/rec' if k == 0 else f'/rec{k}')
    os.makedirs(h.rec, exist_ok=True)
    for f in os.listdir(h.rec):
        os.remove(os.path.join(h.rec, f))
    f0 = h.frame
    late = int(os.environ.get('LATEOFF', '-1'))     # speed-ups off (flag 0x5DA) LATEOFF frames after USE
    touch(128, 175)
    for i in range(nrec):
        if i == late:
            ew = h.r32(h.gd() + 0x1AC)
            h.w8(ew + 0x35E + (0x5DA >> 3), h.r8(ew + 0x35E + (0x5DA >> 3)) | 1 << (0x5DA & 7))
            print(tag, 'speed-ups off at', i)
        h.step(1)
        if i > 120 and i % 10 == 0 and ui() in ('menu', 'yesno'):
            break
    h.rec = None
    print(tag, 'throw', k, 'USE at', f0, 'end', h.frame, 'frames', h.frame - f0, 'state', ui(), flush=True)
    if ui() == 'yesno':
        break
f0 = f00
if trace:
    with open(h.dir + '/trace.txt', 'w') as f:
        for fr, cmd, nd, fn in trace:
            if fr >= f0:
                f.write(f'{fr - f0} {cmd} {nd} {fn:#x}\n')
    print(tag, 'trace lines', sum(1 for t in trace if t[0] >= f0))
if effstate:
    with open(h.dir + '/effstate.txt', 'w') as f:
        last = None
        for fr, xb, st, eff in effstate:
            if fr >= f0 and (st, eff) != last:
                f.write(f'{fr - f0} extra {xb} vm {st} eff {eff}\n')
                last = (st, eff)
        f.write(f'end extra {effstate[-1][1]}\n')

# --- POST=field: finish the battle (B through nickname / dex; RUN if the foe broke free), trace the follower
# from the battle's end into the field (WPosOffset y every frame, first 90 field frames recorded to rec_post/);
# feet vs shadow at the same grass tile before the battle (pre_field) and after (post_field)
if os.environ.get('POST'):
    import fcheck
    if os.environ.get('TURBO') and TDBG:
        print(tag, 'turbo before the battle end', h.r8(TDBG), 'extra battle ticks', h.r32(TDBG + 0x14))
    recp = h.dir + '/rec_post'
    os.makedirs(recp, exist_ok=True)
    for f in os.listdir(recp):
        os.remove(os.path.join(recp, f))
    rows, k, fready, nrec_post = [], 0, 0, 0
    while k < 6000 and fready < 90:
        if not fcheck.actor(h) and ui() == 'menu':
            touch(128, 170)                     # RUN
            k += 20
            continue
        if k % 20 == 0 and not h.field_ready():
            h.hold('B', 2)
            k += 2
        rows += fcheck.post_trace(h, 1)
        if rows[-1][2] and nrec_post < 90:
            h.emu.screenshot().crop((0, 0, 256, 192)).save(f'{recp}/{nrec_post:03d}.png', compress_level=1)
            nrec_post += 1
        if rows[-1][2] and rows[-1][1]:
            fready += 1
        k += 1
    first = next((i for i, r in enumerate(rows) if r[2]), None)
    print(tag, 'post: field', h.field_ready(), 'zone', h.zone(), 'frames to field', k)
    if first is None:
        print(tag, 'post: FAIL no follower actor after the battle')
    else:
        seg = rows[first:first + 90]
        ys = sorted(set(r[3] for r in seg))
        mo = sorted(set(r[4] for r in seg))
        fr0 = next((i for i, r in enumerate(rows) if r[1]), None)
        print(tag, 'post: follower actor from frame', rows[first][0], 'field ready from',
              rows[fr0][0] if fr0 is not None else None,
              'wofs y (units)', [y / fcheck.FX for y in ys], 'model ofs y', mo)
        print(tag, 'post: first 12 frames', [(r[0] - rows[first][0], int(r[1]), r[3] / fcheck.FX) for r in seg[:12]])
        ok = set(ys) <= {-0x2000, -0x4000} or set(ys) <= {0, 0x2000}
        print(tag, 'post: bob values', 'OK' if ok else 'FAIL', [y / fcheck.FX for y in ys])
    h.wait_field(600, 30)
    print(tag, 'post gap', fcheck.measure(h, tag, 'post_field'))
