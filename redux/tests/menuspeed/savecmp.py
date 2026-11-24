"""savecmp.py A.json B.json : the game state at the end of two sweeps of the same scenario (CRC32 of every save block
of the RAM save buffer, sweep.py '_save'): which blocks differ. Blocks that change with time alone (play time, the
RTC-stamped records) are listed as such; any other difference (party, Bag, money, boxes, ...) fails (exit 1).
With the A_save.bin / B_save.bin next to the JSONs, the differing bytes of each block are shown."""
import json, os, sys

TIME = {29, 30, 51}     # blocks that differ with timing alone in identical flows (play time, misc time stamps)
FLAG_BYTE = (45, 0x419)  # EventWork's byte of flag 0x5DA (speed-ups off): the only difference of an on / off pair


def main():
    a, b = (json.load(open(p)) for p in sys.argv[1:3])
    sa, sb = a.get('_save'), b.get('_save')
    if not isinstance(sa, list) or not isinstance(sb, list):
        print('no save CRCs', type(sa), type(sb))
        return 1
    blocks = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'fastsave', 'blocks.json')))
    ba = bb = None
    pa, pb = (os.path.splitext(p)[0] + '_save.bin' for p in sys.argv[1:3])
    if os.path.exists(pa) and os.path.exists(pb):
        ba, bb = open(pa, 'rb').read(), open(pb, 'rb').read()
    bad = []
    for i, (x, y) in enumerate(zip(sa, sb)):
        if x == y:
            continue
        o, n = blocks[i]
        diff = ''
        kind = 'time' if i in TIME else 'STATE'
        if ba is not None:
            d = [k for k in range(n) if ba[o + k] != bb[o + k]]
            diff = f'{len(d)} bytes, at +{d[0]:#x}..+{d[-1]:#x}' if d else ''
            if d == [FLAG_BYTE[1]] and i == FLAG_BYTE[0] and (ba[o + d[0]] ^ bb[o + d[0]]) == 1 << (0x5DA & 7):
                kind = 'the speed-ups flag'
        if kind != 'STATE':
            print(f'block {i:2d} (+{o:#07x}, {n} bytes) differs [{kind}] {diff}')
            continue
        print(f'block {i:2d} (+{o:#07x}, {n} bytes) differs [{kind}] {diff}')
        if i not in TIME:
            bad.append(i)
    print('state equal' if not bad else f'STATE DIFFERS in blocks {bad}')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
