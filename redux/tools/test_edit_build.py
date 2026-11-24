#!/usr/bin/env python3
"""End-to-end check of the source -> ROM pipeline: copy the exported Redux sources, make a few
edits (a longer dialogue line that forces the text archive to grow and later files to move, a
trainer level, an encounter level), build, and read the edits back from the new ROM."""
import json, os, shutil, struct, subprocess, sys
import ndsfs, romtool, gen5text as G, gen5data as D
import redux_rom as R

SRC = os.path.join(R.BUILD, 'src', 'redux')
TEST = os.path.join(R.BUILD, 'src', 'edit_test')
OUT = os.path.join(R.BUILD, 'out', 'edit_test.nds')
SUFFIX = ' EDIT TEST: appended so the text archive grows and later files must move.' * 8


def main():
    shutil.rmtree(TEST, ignore_errors=True)
    shutil.copytree(SRC, TEST)
    p = os.path.join(TEST, 'text', 'story', '0014.txt')
    lines = open(p, encoding='utf-8').read().split('\n')
    global LINE
    LINE = lines[0] + SUFFIX
    lines[0] = LINE
    open(p, 'w', encoding='utf-8').write('\n'.join(lines))
    p = os.path.join(TEST, 'data', 'trainers.json')
    t = json.load(open(p, encoding='utf-8'))
    t[50]['party'][0]['level'] = 99
    json.dump(t, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    p = os.path.join(TEST, 'data', 'encounters.json')
    e = json.load(open(p, encoding='utf-8'))
    e[3]['seasons'][0]['grass'][0][1] = 42
    json.dump(e, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), 'build_rom.py'),
                    '--src', TEST, '--out', OUT], check=True)

    o = ndsfs.Rom(os.path.join(R.BUILD, 'vanilla_rom', 'redux.nds'))
    n = ndsfs.Rom(OUT)
    ids = {q: i for i, q in o.paths.items()}
    get = lambda rom, q: ndsfs.narc(rom.file(ids[q]))
    checks = {}
    checks['text edit'] = G.decode(get(n, 'a/0/0/3')[14])[0][0][0] == LINE
    names = D.Names(get(n, 'a/0/0/2'))
    tr = D.decode_trainers(get(n, 'a/0/9/1'), get(n, 'a/0/9/2'), names)
    checks['trainer edit'] = tr[50]['party'][0]['level'] == 99
    enc = D.decode_encounters(get(n, 'a/1/2/7'), names)
    checks['encounter edit'] = enc[3]['seasons'][0]['grass'][0][1] == 42
    changed = {ids[q] for q in ('a/0/0/3', 'a/0/9/2', 'a/1/2/7')}
    checks['other files unchanged'] = all(bytes(o.file(f)) == bytes(n.file(f))
                                          for f in range(len(o.fat)) if f not in changed)
    checks['other story banks unchanged'] = all(a == b for i, (a, b) in
                                               enumerate(zip(get(o, 'a/0/0/3'), get(n, 'a/0/0/3'))) if i != 14)
    checks['arm9 unchanged'] = (o.m[o.arm9[0]:o.arm9[0] + o.arm9[1]] == n.m[n.arm9[0]:n.arm9[0] + n.arm9[1]])
    checks['header CRC valid'] = struct.unpack_from('<H', n.m, 0x15E)[0] == romtool.crc16(n.m[:0x15E])
    s3, e3 = n.fat[ids['a/0/0/3']]
    checks['text archive grew'] = e3 - s3 > o.fat[ids['a/0/0/3']][1] - o.fat[ids['a/0/0/3']][0]
    spans = sorted((s, e) for s, e in n.fat if e > s)
    checks['no overlapping files'] = all(e <= s2 for (s, e), (s2, _) in zip(spans, spans[1:]))
    for k, v in checks.items():
        print(f'{"PASS" if v else "FAIL"}  {k}')
    return 0 if all(checks.values()) else 1


if __name__ == '__main__':
    sys.exit(main())
