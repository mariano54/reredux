"""meas.py : frame-exact menu timings (library).

A step = an input (key or touch) given in a settled state S, then a probe input (the next input of the flow).
  resp  = frames from the first frame the input is held to the first picture that differs from the same frames
          without the input (both screens; deterministic emulation from the same savestate)
  ready = the earliest frame (same origin) at which the probe input, held 4 frames, changes the picture within W
          frames compared to not giving it: the game took the next input
Both are averaged over PHASES start frames (S, S+1: 30 Hz loops). After a step the flow goes on from the input's own
trace at ready + margin (a settled state again). Sound events (SE / sequence start, force stop, free) are logged along
the flow (melonDS hooks; DeSmuME exec callbacks)."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
import os, sys

HOLD = 4
W = 40


def _press(E, inp, n):
    if isinstance(inp, tuple):
        E.step(n, touch=inp)
    elif inp:
        E.step(n, tuple(inp.split('+')))
    else:
        E.step(n)


def trace(E, inp, n, hold=HOLD):
    """hashes of n frames from the current state, inp held for the first `hold` frames (None: no input)"""
    out = []
    for i in range(n):
        _press(E, inp if i < hold else None, 1)
        out.append(E.hash())
    return out


def probe_ok(E, probe, ref, k, hold=HOLD):
    """from the state at trace frame k (current): does the probe change the picture vs ref[k:]?"""
    for i in range(hold + W):
        _press(E, probe if i < hold else None, 1)
        if k + i >= len(ref):
            return None
        if i and E.hash() != ref[k + i]:            # i = 0: the first picture after a load is stale
            return True
    return False


def measure(E, inp, probe, n=360, coarse=4, phases=2, hold=HOLD):
    """E in the settled state S (saved in slot 0 by the caller). -> dict(resp=[..per phase], ready=[..])"""
    res = dict(resp=[], ready=[])
    for p in range(phases):
        E.sload(0)
        E.step(p)
        E.ssave(1)
        ctl = trace(E, None, n)
        E.sload(1)
        tr = trace(E, inp, n, hold)
        resp = next((i for i in range(1, n) if tr[i] != ctl[i]), None)     # frame 0 after a load: stale picture
        res['resp'].append(resp)
        if probe is None:
            res['ready'].append(None)
            continue
        cur = [None]                                        # trace frame of the state in slot 2

        def at(k):
            """the input's trace at frame k (slot 2 caches the latest)"""
            if cur[0] is not None and cur[0] <= k:
                E.sload(2)
                E.step(k - cur[0])
            else:
                E.sload(1)
                _press(E, inp, min(hold, k))
                E.step(k - min(hold, k))
            E.ssave(2)
            cur[0] = k

        def ok(k):
            at(k)
            return probe_ok(E, probe, tr, k, hold)

        last = n - hold - W - 1
        k = max(resp if resp is not None else 0, hold)
        prev, found = None, None
        while k <= last:
            if not ok(k):
                prev, k = k, k + coarse
                continue
            # accepted: it counts only if the probe is taken from here on (an input taken by the screen that is
            # being left, e.g. B by the X menu before the app starts, is not "ready")
            bad = next((c for c in (k + coarse, k + 2 * coarse, k + 4 * coarse, k + 8 * coarse, k + 16 * coarse)
                        if c <= last and not ok(c)), None)
            if bad is None:
                found = k
                break
            prev, k = bad, bad + coarse
        if found is not None and prev is not None and coarse > 1:
            cur[0] = None
            for kk in range(prev + 1, found):
                if ok(kk):
                    found = kk
                    break
        res['ready'].append(found)
    return res


def advance(E, inp, frames, hold=HOLD):
    """from slot 0: give inp and run `frames` frames in all; the new settled state goes to slot 0"""
    E.sload(0)
    _press(E, inp, min(hold, frames))
    E.step(max(0, frames - hold))
    E.ssave(0)


def mean(v):
    v = [x for x in v if x is not None]
    return sum(v) / len(v) if v else None


# --- sound events -----------------------------------------------------------------------------------------------
SND = {0x0206DA38: 'START', 0x0206C33C: 'STOP', 0x0206C1F0: 'STOPF', 0x0206C3B8: 'FREE', 0x02006214: 'SE',
       0x020069F4: 'VOICE', 0x0206BC1C: 'WSTOP', 0x02006228: 'SEIDX'}


def snd_hooks(E):
    E.hook(*SND)


def snd_events(E):
    """[(frame, kind, args)] since the last call. STOP of an active sequence (state 1) = a cut (see bfix drive.py)"""
    out = []
    for fr, pc, r0, r1, r2, r3, lr, m2c, m38, s4, raw in E.hooks():
        k = SND.get(pc)
        if k is None:
            continue
        if k == 'START':
            out.append((fr, k, dict(seq=s4 & 0xFFFF, player=r1, lr=lr)))
        elif k in ('STOP', 'STOPF', 'FREE'):
            out.append((fr, k, dict(seq=m38 & 0xFFFF, state=m2c & 0xFF, fade=r1, lr=lr)))
        elif k == 'SE':
            out.append((fr, k, dict(se=r0, player=r1 if r1 < 0x80000000 else -1, lr=lr)))
        elif k == 'VOICE':
            out.append((fr, k, dict(mons=r0, form=r1, lr=lr)))
        elif k == 'WSTOP' and raw is not None:     # wave-out (cry) channel stop: [r0] & 15 channel, [r0+8] active
            out.append((fr, k, dict(ch=raw[12] & 15, active=int(raw[13] != 0), busy=int(raw[14] >> 31), lr=lr)))
        else:
            out.append((fr, k, dict(r0=r0, lr=lr)))
    return out
