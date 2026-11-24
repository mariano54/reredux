"""flowrun.py : run a scenario's steps (scen.py) on a driver (mh.py), measuring each step (library for sweep.py and
the t_*.py tests).

  run(E, steps, phases=2, margin=30, odir=None, log=print, measure=True) -> dict
E must be in the scenario's start state (saved in slot 0 by run). Steps:
  ('name', INPUT, PROBE[, N])   measured (meas.measure: resp / ready over `phases` start frames; N = trace length),
                                then the flow goes on along the input's own trace until ready + margin
                                (measure=False: ready is not probed; the flow goes on after N or 120 frames)
  ('=', INPUT, FRAMES)          given, then FRAMES frames in all       ('=goto', x, z) / ('=face', DIR)
  ('=hold', KEY, FRAMES, NAME)  KEY held: the frames the game's key repeat fires and the picture changes
  ('=wild',)                    Route 19's grass until a wild battle's command menu
Result: {step: {resp, ready}}, _order, _steps [(step, frame)], _snd (meas.snd_events of the flow), _hold, _save
(CRC32 per save block of the RAM save buffer at the end; _save_bin = its bytes)."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
import json, os, sys, time, zlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mh, meas, flow

HERE = os.path.dirname(os.path.abspath(__file__))


def save_blocks(E):
    """(CRC32 per save block, raw bytes) of the RAM save buffer (SaveControl *0x02140F60 +0x10: +0x34 buffer, +0x30
    size; block table: ../fastsave/blocks.json)"""
    sc = E.r32(0x02140F60)
    sd = E.r32(sc + 0x10) if mh.ram_ok(sc) else 0
    buf, size = (E.r32(sd + 0x34), E.r32(sd + 0x30)) if mh.ram_ok(sd) else (0, 0)
    if not mh.ram_ok(buf) or not 0 < size <= 0x40000:
        return None, b''
    blocks = json.load(open(os.path.join(HERE, '..', 'fastsave', 'blocks.json')))
    data = E.read(buf, size)
    return [zlib.crc32(data[o:o + k]) for o, k in blocks], data


def set_flag(E, f, on=True):
    """event flag f in the live game data (EventWork +0x35E bit array)"""
    gd = E.gd()
    ew = E.r32(gd + 0x1AC)
    a = ew + 0x35E + (f >> 3)
    v = E.r8(a)
    E.w8(a, v | 1 << (f & 7) if on else v & ~(1 << (f & 7)))


def run(E, steps, phases=2, margin=30, odir=None, log=print, measure=True):
    E.ssave(0)
    res = dict(_order=[], _steps=[])
    snd = []
    n = 0
    if odir:
        os.makedirs(odir, exist_ok=True)

    def shot(tag):
        if odir:
            E.image().save(f'{odir}/{n:02d}_{tag.replace(" ", "_").replace("/", "_")}.png')

    for st in steps:
        if st[0] in ('=', '=goto', '=hold', '=wild', '=face'):
            E.sload(0)
            E.hooks()
            if st[0] == '=':
                if st[1] is not None:
                    meas._press(E, st[1], meas.HOLD)
                    E.step(max(0, st[2] - meas.HOLD))
                else:
                    E.step(st[2])
            elif st[0] == '=goto':
                if not flow.goto(E, st[1], st[2]):
                    log('goto failed', st, E.pos())
            elif st[0] == '=face':
                E.step(2, (st[1],))
                E.step(20)
            elif st[0] == '=wild':
                log('wild battle menu', flow.wild(E))
            else:
                key, frames, hname = st[1:4]
                bit = 1 << mh.KEYS.index(key)
                reps, hashes = [], []
                for f in range(frames):
                    E.step(1, (key,))
                    ui = E.r32(0x02141884)
                    kw = E.r32(ui) if mh.ram_ok(ui) else 0
                    if mh.ram_ok(kw) and E.r32(kw + 0x14) & bit:
                        reps.append(f)
                    hashes.append(E.hash())
                E.step(30)
                res.setdefault('_hold', {})[hname] = dict(
                    repeat=reps, changes=[f for f in range(1, frames) if hashes[f] != hashes[f - 1]])
                n += 1
                shot(f'hold_{hname}')
                log(f'hold {hname}: repeat at {reps}')
            snd += meas.snd_events(E)
            E.ssave(0)
            continue
        sname, inp, probe = st[:3]
        nf = st[3] if len(st) > 3 else 360
        t = time.time()
        if measure:
            r = meas.measure(E, inp, probe, phases=phases, n=nf)
        else:
            r = dict(resp=[None], ready=[None])
        rs = meas.mean(r['resp'])
        key, k = sname, 2
        while key in res:
            key = f'{sname}#{k}'
            k += 1
        res[key] = r
        res['_order'].append(key)
        E.sload(0)
        E.hooks()
        if measure:
            fr = int((r['ready'][0] if r['ready'][0] is not None else (rs or 0) + 120) + margin)
        else:
            fr = nf if len(st) > 3 else 120
        res['_steps'].append((key, E.frame))
        meas._press(E, inp, meas.HOLD)
        E.step(max(0, fr - meas.HOLD))
        snd += meas.snd_events(E)
        E.ssave(0)
        n += 1
        shot(key)
        log(f'{key:28s} resp {r["resp"]} ready {r["ready"]}  ({time.time() - t:.0f}s)')
    res['_snd'] = snd
    E.sload(0)
    try:
        res['_save'], res['_save_bin'] = save_blocks(E)
    except Exception as e:                      # noqa: BLE001
        res['_save'], res['_save_bin'] = f'error {e}', b''
    return res
