"""sndcheck.py A.json B.json : sound fates along two sweeps of the same scenario (A = the reference, e.g. Redux 1.4.1
or ReRedux before; B = the new ROM). A sequence instance runs from its START to the first STOP / STOPF / FREE of that
sequence: natural (freed after it ended), cut (force-stopped while playing: preempted by a new sound on its player,
lr 0206C187, or stopped, lr 0206C20D), fade (stopped with a fade while playing). Cries: a wave-out stop (WSTOP) of a
channel still busy = cut. Prints both sides' cuts by step and the (sequence, cause) cuts in B that A doesn't have
(exit 1 if any)."""
import json, sys, collections

CAUSE = {0x0206C187: 'preempt', 0x0206C20D: 'stop'}


def load(p):
    d = json.load(open(p))
    return d['_snd'], d.get('_steps', [])


def step_at(steps, fr):
    k = None
    for name, f in steps:
        if f <= fr:
            k = name
    return k


def fates(snd, steps):
    open_ = collections.defaultdict(list)
    inst = []
    for fr, kind, a in snd:
        if kind == 'START':
            d = dict(seq=a['seq'], start=fr, end=None, fate=None, step=step_at(steps, fr))
            open_[a['seq']].append(d)
            inst.append(d)
        elif kind in ('STOP', 'STOPF', 'FREE') and open_[a['seq']]:
            if kind == 'FREE' and a['lr'] != 0x0206C08D:
                continue                # the force stop's own free: counted at its STOP
            d = open_[a['seq']].pop(0)
            st = a['state']
            if kind == 'STOP':
                d['fate'] = ('cut:' + CAUSE.get(a['lr'], f'{a["lr"]:08X}')) if st == 1 else 'stopped-idle'
            elif kind == 'STOPF':
                d['fate'] = 'fade' if st == 1 and a['fade'] else 'stopped-idle'
            else:
                d['fate'] = 'natural'
            d['end'] = fr
        elif kind == 'WSTOP' and a.get('active') and a.get('busy'):
            inst.append(dict(seq=f'voice-ch{a["ch"]}', start=fr, end=fr, fate='cut:wave', step=step_at(steps, fr)))
    for d in inst:
        if d['fate'] is None:
            d['fate'], d['end'] = 'open', d['start']
    return inst


def is_cut(d):
    return d['fate'].startswith('cut') or d['fate'] == 'fade'


def main():
    A, B = (fates(*load(p)) for p in sys.argv[1:3])
    ca = collections.Counter((d['seq'], d['fate']) for d in A)
    cb = collections.Counter((d['seq'], d['fate']) for d in B)
    seqs = sorted({k[0] for k in ca} | {k[0] for k in cb}, key=str)
    print(f'{"seq":>10s}  {"fates in A":44s} fates in B')
    for s in seqs:
        fa = ', '.join(f'{f} {n}' for (q, f), n in sorted(ca.items(), key=str) if q == s)
        fb = ', '.join(f'{f} {n}' for (q, f), n in sorted(cb.items(), key=str) if q == s)
        print(f'{str(s):>10s}  {fa:44s} {fb}')
    for side, I in (('A', A), ('B', B)):
        for d in I:
            if is_cut(d):
                print(f'  {side} {d["fate"]:14s} seq {d["seq"]} at {d["start"]} after {d["end"] - d["start"]} f, step {d["step"]}')
    # a cut in B is fine only if A cuts the same sound in the same step at least as early (same or shorter play)
    bad = []
    for d in B:
        if not is_cut(d):
            continue
        same = [x for x in A if x['seq'] == d['seq'] and x['step'] == d['step']]
        if not any(is_cut(x) and x['end'] - x['start'] <= d['end'] - d['start'] + 1 for x in same):
            bad.append(d)
    for d in bad:
        print(f'SHORTER in B: seq {d["seq"]} {d["fate"]} after {d["end"] - d["start"]} f in step {d["step"]}; A:',
              [(x['fate'], x['end'] - x['start']) for x in A if x['seq'] == d['seq'] and x['step'] == d['step']])
    if bad:
        return 1
    print('no sound cut sooner in B')
    return 0


if __name__ == '__main__':
    sys.exit(main())
