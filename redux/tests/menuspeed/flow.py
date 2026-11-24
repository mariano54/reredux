"""flow.py : scripted input items shared by the menu-speed scripts (library).

Items: KEY[:WAIT] (KEY may be A+B), T:x,y[:WAIT] (touch), W:n (wait), goto:x,z (walk on the current map, BFS over its
permission grid), face:DIR. WAIT defaults to 60 frames."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B  # noqa: E402
import os, sys

BOOT_FRAMES = 30


def start(E, cache_dir=None, teleport=None):
    """Continue the battery save (or load cache_dir/boot.state made from the same ROM)"""
    st = None
    if cache_dir:
        st = os.path.join(cache_dir, f'boot_{E.kind}' + (f'_z{teleport[0]}_{teleport[1]}_{teleport[2]}' if teleport else '')
                          + '.state')
    if st and os.path.exists(st) and os.path.exists(st + '.rom') and open(st + '.rom').read() == _romkey(E):
        E.state_file_load(st)
        E.step(2)
        return True
    ok = E.boot_continue(teleport=teleport)
    E.step(BOOT_FRAMES)
    if st:
        tmp = f'{st}.{os.getpid()}'
        E.state_file_save(tmp)
        os.replace(tmp, st)
        open(tmp + '.rom', 'w').write(_romkey(E))
        os.replace(tmp + '.rom', st + '.rom')
    return ok


def _romkey(E):
    return f'{E.romkey}' if hasattr(E, 'romkey') else ''


def do(E, item):
    if item.startswith('W:'):
        E.step(int(item[2:]))
        return
    if item.startswith('goto:'):
        x, z = (int(v) for v in item[5:].split(','))
        return goto(E, x, z)
    if item.startswith('face:'):
        E.hold(item[5:], 2)
        E.step(20)
        return
    parts = item.split(':')
    wait = 60
    if parts[0] == 'T':
        x, y = (int(v) for v in parts[1].split(','))
        if len(parts) > 2:
            wait = int(parts[2])
        E.step(4, touch=(x, y))
        E.step(max(0, wait - 4))
        return
    if len(parts) > 1:
        wait = int(parts[1])
    E.step(4, tuple(parts[0].split('+')))
    E.step(max(0, wait - 4))


def goto(E, tx, tz, maxsteps=200):
    sys.path.insert(0, f'{RR_T}/qa')
    import perm
    from collections import deque
    blocked = set()
    for _ in range(maxsteps):
        zone, x, z = E.pos()
        if (x, z) == (tx, tz):
            E.step(10)
            return True
        perm.set_zone(zone)
        prev = {(x, z): None}
        dq = deque([(x, z)])
        while dq:
            c = dq.popleft()
            if c == (tx, tz):
                break
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (c[0] + dx, c[1] + dz)
                if n in prev or n in blocked or (n != (tx, tz) and not perm.walkable(*n)):
                    continue
                if abs(n[0] - x) > 60 or abs(n[1] - z) > 60:
                    continue
                prev[n] = c
                dq.append(n)
        if (tx, tz) not in prev:
            return False
        c = (tx, tz)
        while prev[c] != (x, z):
            c = prev[c]
        nx, nz = c
        d = 'RIGHT' if nx > x else 'LEFT' if nx < x else 'DOWN' if nz > z else 'UP'
        moved = False
        for _ in range(30):
            E.step(1, (d,))
            p = E.pos()
            if p and p[1:] != (x, z):
                moved = True
                break
        E.step(8)
        if not moved:
            blocked.add((nx, nz))
    return False


def battle_menu(E):
    """the battle's command menu (FIGHT / BAG / RUN / POKÉMON) is on the bottom screen (bfix drive.py ui())"""
    p = E.image().getpixel((215, 357))
    return all(abs(a - b) <= 10 for a, b in zip(p, (112, 216, 48)))


def to_r19(E):
    """from the Aspertia Pokémon Center to Route 19's grass (60, 695), as ff/catch.py walks it"""
    for d in ['DOWN'] * 4 + ['LEFT'] + ['DOWN'] * 4 + ['LEFT'] + ['DOWN'] * 4:
        if E.zone() != 435:
            break
        E.step(8, (d,))
        E.step(6)
    E.wait_field(1500, 30)
    goto(E, 52, 711)
    for _ in range(2):
        E.step(20, ('UP',))
        E.wait_field(3000, 40, tap='A')
    goto(E, 4, 2)
    for _ in range(2):
        E.step(20, ('UP',))
        E.wait_field(3000, 40, tap='A')
    goto(E, 60, 695)
    return E.pos()


def wild(E, maxtries=600):
    """walk left / right in the grass until a wild battle starts, then until its command menu is up"""
    if E.zone() == 435:
        print('to route 19:', to_r19(E), flush=True)
    for i in range(maxtries):
        E.step(10, ('RIGHT' if (i // 2) % 2 else 'LEFT',))
        E.step(4)
        if not E.field_ready() and E.zone() is not None:
            break
    for i in range(2000):
        E.step(1)
        if i % 10 == 0 and battle_menu(E):
            E.step(30)
            return battle_menu(E)
    return False
