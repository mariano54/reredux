"""t_newgame.py STAGE ROM QMAP LANG NAME : the first save of a new game (B2 formats the save: FUN_0203ADB4, then writes
everything). STAGE save: no battery, A through the intro to the settings menu, Start the adventure!, A until the
first save completes; the battery must hold the RAM buffer exactly (both copies, CRCs). STAGE boot: cold boot,
Continue, every block as saved."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import sys, os, json
from fs import F, FS
import sav

stage, rom, qmap, lang, name = sys.argv[1:6]
tag = f'fs_{name}'
BLK = sav.load_blocks()
DBG = 'skipped changed compared verified promoted dropped guard resets saves steps updates max_ticks seeded stale pg_written pg_skipped segs'.split()
STATE = os.path.join(FS, 'out', name, 'ng_state.json')


def dbg(f):
    a = f.sym.get('fs_dbg')
    return {k: f.r32((a & ~1) + 12 + 4 * i) for i, k in enumerate(DBG)} if a else {}


if stage == 'save':
    f = F(rom, tag, name, dsv=None, qmap=qmap)
    ev = []
    f.hook(0x0203ADB4, lambda a, s: ev.append((f.frame, 'format')))
    f.hook(0x0201782C, lambda a, s: ev.append((f.frame, 'save start', hex(f.r.lr))))
    st = {}

    def eng(a, s):
        v = f.r8(f.r.r0 + 0x18)
        if st.get('last') != v:
            ev.append((f.frame, 'engine', v))
            st['last'] = v
    f.hook(0x0203B9BC, eng)
    f.step(600)
    f.tap('START')
    f.step(100)
    snap = {}
    n = 0
    while n < 400 and not snap:     # title -> New Game: B2 writes the whole new save at once
        f.tap('A')
        n += 1
        sc = f.r32(0x02140F60)
        sd = f.r32(sc + 0x10) if sc else 0
        if sd and sum(1 for e in ev if e[1] == 'engine' and e[2] == 10) >= 2 and f.r8(sd + 0x18) == 11:
            ev.append((f.frame, 'engine', 11))
            buf, size = f.r32(sd + 0x34), f.r32(sd + 0x30)
            snap['ram'] = bytes(f.m[buf: buf + size])
            snap['frame'] = f.frame
    f.say('events', [e for e in ev if e[1] != 'engine' or e[2] in (0, 1, 2, 10, 11)][:40])
    f.say('fs_dbg', dbg(f))
    f.check('the new-game save ran and completed', bool(snap), True)
    f.shot('after_first_save')
    if snap:
        exp = os.path.join(f.dir, 'battery_ng.sav')
        if os.path.exists(exp):
            os.remove(exp)
        f.emu.backup.export_file(exp)
        c = sav.check(exp, snap['ram'])
        f.say('battery', json.dumps(c))
        for cp in 'AB':
            f.check(f'copy {cp}: every block == RAM', c[cp]['diff'], [])
            f.check(f'copy {cp}: CRCs valid', c[cp]['bad'], [])
            f.check(f'copy {cp}: CRC table/header/commit == RAM', c[cp]['foot_eq_ram'], True)
        open(os.path.join(f.dir, 'ram_ng.bin'), 'wb').write(snap['ram'])
        start = [e[0] for e in ev if e[1] == 'engine' and e[2] == 0]
        done = [e[0] for e in ev if e[1] == 'engine' and e[2] == 11]
        f.say('MEAS first save: start f', start[:1], 'engine done f', done[:1])
        json.dump(dict(zone=f.zone(), fails=f.fails, start=start[:1], done=done[:1], dbg=dbg(f)), open(STATE, 'w'))
    f.step(30)
    f.close()
    print('RESULT', 'PASS' if not f.fails else 'FAIL', '(save stage)')
else:
    st = json.load(open(STATE))
    ram = open(os.path.join(FS, 'out', name, 'ram_ng.bin'), 'rb').read()
    g = F(rom, tag, name + '_boot', keep=True, qmap=qmap)
    # the new-game save happens at the end of the intro's naming: Continue resumes the intro (opening flight,
    # settings menu), so the field is never free without input -> only the GameSystem must come up
    g.boot_continue(maxf=4000)
    g.check('Continue loads the save (GameSystem up)', g.gsys() != 0, True)
    sc = g.r32(0x02140F60)
    sd = g.r32(sc + 0x10)
    buf, size = g.r32(sd + 0x34), g.r32(sd + 0x30)
    cur = bytes(g.m[buf: buf + size])
    diff = [i for i, (o, s) in enumerate(BLK) if cur[o:o + s] != ram[o:o + s]]
    g.say('blocks differing after Continue (the game rewrites some on Continue):', diff, 'zone', g.zone())
    g.check('boxes / bag / party blocks (1-26) as saved', [i for i in diff if 1 <= i <= 26], [])
    g.shot('continue')
    g.close()
    fails = st['fails'] + g.fails
    print('FAILS', fails)
    print('RESULT', 'PASS' if not fails else 'FAIL')
