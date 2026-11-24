"""t_battle.py LANG : battle summary unaffected: smoke battery save -> Route 19 grass -> wild battle -> POKEMON -> lead ->
Summary, SELECT / RIGHT / SELECT there (shots); statview's code must not run (exec hooks on statview_keys/draw),
then back out and run away; field again."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, f'{RR_T}/qa')
import perm
from collections import deque
from sv import SV, B

lang = sys.argv[1]
q = SV(f'sv_battle_{lang}', f'{B}/out/sv_{lang}.nds', f'sv_{lang}', f'{B}/statview_integ/dsv/rel_{lang}_smoke_{lang}.dsv',
       elf=f'{B}/redux3/{lang}_follow.elf')
hits = []
for name in ('statview_keys', 'statview_draw', 'statview_init'):
    q.emu.memory.register_exec(q.sym_addr(name), (lambda n: lambda a, s: hits.append((q.frame, n)))(name), 2)


def path(tx, tz, extra_block=()):
    perm.set_zone(q.zone())
    s = q.pos()
    prev = {s: None}
    dq = deque([s])
    while dq:
        c = dq.popleft()
        if c == (tx, tz):
            break
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (c[0] + dx, c[1] + dz)
            if n in prev or n in extra_block or (n != (tx, tz) and not perm.walkable(*n)):
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


def nav(tx, tz, tries=4):
    from desmume.controls import Keys, keymask
    blocked = set()
    for _ in range(tries):
        p = path(tx, tz, blocked)
        if p is None:
            q.say('nav: no path', (tx, tz), q.pos())
            return False
        ok = True
        for nx, nz in p:
            x, z = q.pos()
            d = 'RIGHT' if nx > x else 'LEFT' if nx < x else 'DOWN' if nz > z else 'UP'
            q.emu.input.keypad_add_key(keymask(getattr(Keys, 'KEY_' + d)))
            for i in range(30):
                q.step(1)
                if q.pos() != (x, z):
                    break
            q.emu.input.keypad_rm_key(keymask(getattr(Keys, 'KEY_' + d)))
            if q.pos() != (nx, nz):
                if q.event_running():
                    return False
                q.step(8)
                if q.pos() == (nx, nz):
                    continue
                blocked.add((nx, nz))
                ok = False
                break
        if ok or q.pos() == (tx, tz):
            q.step(8)
            return q.pos() == (tx, tz)
    return q.pos() == (tx, tz)


def ui():
    p = q.emu.screenshot().convert('RGB').getpixel
    return 'menu' if p((215, 357)) == (112, 216, 48) else None


q.boot_continue()
q.say('pos', q.pos(), 'zone', q.zone())
# Pokémon Center -> Aspertia -> gate -> Route 19 (t_smoke.py's way)
for x in (9, 8, 7, 6, 5, 4):
    nav(x, 16)
    q.hold('DOWN', 30)
    q.wait_field(2000)
    if q.zone() != 435:
        break
q.say('outside?', q.zone(), q.pos())
for tx, tz in ((52, 711), (4, 2)):
    nav(tx, tz)
    for _ in range(2):
        q.hold('UP', 20)
        q.wait_field(3000, tap='A', settle=40)
q.say('route 19?', q.zone(), q.pos())
nav(60, 695)
w0 = q.r16(q.sym_addr('rules_dbg') + 4)
started = False
for i in range(400):
    q.hold('RIGHT' if (i // 2) % 2 else 'LEFT', 10)
    q.step(4)
    if q.r16(q.sym_addr('rules_dbg') + 4) > w0:
        started = True
        break
q.say('wild_starts moved', started)
for i in range(200):
    if ui() == 'menu':
        break
    if i % 2 == 0:
        q.tap('A', idle=14)
    else:
        q.step(20)
q.check('battle menu', ui(), 'menu')
q.snap('battle_menu')
h0 = len(hits)
q.touch(215, 170)                    # POKEMON
q.step(60)
q.snap('battle_party')
q.touch(64, 30)                      # the lead
q.step(60)
q.snap('battle_lead')
for it in ('summary', 'SELECT', 'RIGHT', 'SELECT', 'DOWN', 'SELECT'):
    if it == 'summary':
        q.touch(128, 140)
        q.step(40)
        q.touch(64, 170)
    else:
        q.tap(it)
    q.step(60)
    q.snap('b_' + it)
q.check('statview code never ran in battle', hits[h0:], [])
for _ in range(4):
    q.tap('B')
    q.step(40)
q.snap('back')
for i in range(80):
    if ui() == 'menu':
        q.touch(128, 175)            # RUN
        q.step(120)
    elif q.field_ready():
        break
    else:
        q.tap('B', idle=30)
q.check('field after running away', q.wait_field(3000, tap='B', settle=30), True)
q.snap('field')
q.result()
q.sheet()
