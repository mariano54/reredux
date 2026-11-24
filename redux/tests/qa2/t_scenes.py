"""t_scenes.py LANG SPEED [SCENE..] : later story scenes started by their own triggers (QA2 ROM, from
qa2_LANG_def_bedroom + the kit's 2 Dragonite as the party). For each scene: set its trigger var, script-warp next to
the trigger, step onto it; then A every 20 frames (B in battles is not needed: scenes only) until the field is free;
shots every 60 frames. SPEED on (speed-ups) / off (speed_dbg.override = 1, vanilla timing) to compare: a scene that
finishes with speed-ups off but not on would be a speed-up desync. Logs MEAS scene frames. Shots
build/qa2/scenes_LANG_SPEED/, sheet build/qa2/scenes_LANG_SPEED_sheet.png (top screens)."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qa2 import Q2
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'qa'))
import perm

# name: (zone, trigger rect x, z, w, h, var, value)
SCENES = {
    'sewers': (495, 49, 9, 4, 1, 16563, 0),
    'frigate': (553, 9, 8, 5, 1, 16629, 0),
    'chasm': (231, 61, 37, 1, 1, 16496, 1),
    'virbank': (448, 195, 649, 1, 4, 16556, 0),
    'driftveil': (97, 5, 51, 4, 1, 16569, 0),
    'opelucid': (120, 440, 173, 1, 5, 16597, 0),
}
lang, speed = sys.argv[1], sys.argv[2]
names = sys.argv[3:] or list(SCENES)
q = Q2(f'scenes_{lang}_{speed}' + ''.join('_' + p for p in sys.argv[3:]), lang)   # scenes given: own run dir (rr.py splits)


def approach(zone, x, z, w, h):
    """a walkable tile next to the trigger rect, and the direction into it"""
    perm.set_zone(zone)
    walk = lambda a, b: perm.cls(a, b) is not None and perm.cls(a, b) not in (1, 0x3D, 0x41, 0xDE, 0x73)
    rect = {(x + i, z + k) for i in range(w) for k in range(h)}
    for (tx, tz) in sorted(rect):
        for dx, dz, d in ((0, 1, 'UP'), (0, -1, 'DOWN'), (1, 0, 'LEFT'), (-1, 0, 'RIGHT')):
            p = (tx + dx, tz + dz)
            if p not in rect and walk(*p) and walk(tx, tz):
                return p, d
    return (None, None), None


res = {}
for name in names:
    zone, x, z, w, h, var, val = SCENES[name]
    q.load('def_bedroom')
    q.step(10)
    if speed == 'off':
        q.speed_override(1)
    q.bed('KIT')
    q.step(200)
    q.wait_free(2000, tap='B')
    (ax, az), d = approach(zone, x, z, w, h)
    q.say(name, 'approach', (ax, az), d)
    if d is None:
        q.check(f'{name}: approach tile found', False, True)
        continue
    q.script([f'    WorkSetConst {var:#x}, {val}', '    PlayerEnableRunningShoes', f'    MapChangeWarp {zone}, {ax}, {az}, 0'])
    q.step(40)
    q.say(name, 'zone', q.zone(), 'pos', q.pos())
    q.snap(f'{name}_00_arrived')
    f0 = q.frame
    q.hold(d, 10)
    started = None
    for i in range(30):
        q.step(2)
        if q.event_running():
            started = q.frame
            break
    shots, done = 0, None
    for i in range(15000):
        if not q.event_running():
            done = q.frame
            break
        if i % 60 == 0 and shots < 24:
            shots += 1
            q.snap(f'{name}_{shots:02d}')
        if i % 20 == 0:
            if q.ui() == 'menu':                # a scripted battle: Dragon Claw (+ the first target)
                q.fight(0)
                q.step(40)
                q.touch(65, 50)
            else:
                q.hold('A', 4)
        else:
            q.step(1)
        if q.zone() is None:
            break
    q.step(30)
    q.snap(f'{name}_99_end')
    frames = (done - started) if started and done else None
    res[name] = dict(started=started is not None, frames=frames, zone_end=q.zone(), pos=q.pos())
    q.say('MEAS', name, speed, res[name])
    q.check(f'{name}: scene started by the trigger', started is not None, True)
    q.check(f'{name}: scene finished, field free', done is not None, True)
q.result(dict(scenes=res))
q.sheet(both=False)
