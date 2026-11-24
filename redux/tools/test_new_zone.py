#!/usr/bin/env python3
"""End-to-end check of new_zone.py: add a town to a copy of the Redux tree, warp to it from
Accumula Town, build, and read the new zone back from the ROM."""
import json, os, shutil, struct, subprocess, sys
import ndsfs, gen5text as G, gen5zone as Z, gen5data as D
import redux_rom as R

TOOLS = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(R.BUILD, 'named', 'redux')
TREE = os.path.join(R.BUILD, 'named', 'newzone_test')
OUT = os.path.join(R.BUILD, 'out', 'newzone_test.nds')


def main():
    shutil.rmtree(TREE, ignore_errors=True)
    shutil.copytree(SRC, TREE)
    subprocess.run([sys.executable, os.path.join(TOOLS, 'new_zone.py'), TREE, '--from', '400',
                    '--name', 'Pokegen Town'], check=True)
    new = next(f for f in os.listdir(os.path.join(TREE, 'zones')) if f.endswith('_pokegen_town'))
    zid = int(new.split('_')[0])
    # warp from Accumula Town (zone 400) to the new town
    p = os.path.join(TREE, 'zones', '400_accumula_town', 'entities.json')
    e = json.load(open(p, encoding='utf-8'))
    w = dict(e['warps'][0])
    w.update(dest_zone=zid, dest_warp=0)
    w.pop('dest_zone_name', None)
    e['warps'].append(w)
    json.dump(e, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    subprocess.run([sys.executable, os.path.join(TOOLS, 'build_rom.py'), '--src', TREE, '--out', OUT], check=True)

    r = ndsfs.Rom(OUT)
    ids = {q: i for i, q in r.paths.items()}
    get = lambda q: ndsfs.narc(r.file(ids[q]))
    zt = get('a/0/1/2')[0]
    rec = zt[zid * 48:(zid + 1) * 48]
    script, text, ents, matrix, loc = (struct.unpack_from('<H', rec, 6)[0], struct.unpack_from('<H', rec, 10)[0],
                                       struct.unpack_from('<H', rec, 0x16)[0], struct.unpack_from('<H', rec, 4)[0],
                                       rec[0x1A])
    locs = D.name_list(get('a/0/0/2')[109])
    acc = Z.decode(get('a/1/2/6')[struct.unpack_from('<H', zt, 400 * 48 + 0x16)[0]])
    checks = {
        'zone table grew by one': len(zt) // 48 == zid + 1,
        'location name': locs[loc] == 'Pokegen Town',
        'own script file': script == len(get('a/0/5/6')) - 1,
        'own text bank': G.decode(get('a/0/0/3')[text])[0][0][0] == 'Pokegen Town: new zone text.',
        'own entity file with template warps': Z.decode(get('a/1/2/6')[ents])['warps'] != [],
        'own matrix': matrix == len(get('a/0/0/9')) - 1,
        'warp from Accumula Town': any(x['dest_zone'] == zid for x in acc['warps']),
    }
    for k, v in checks.items():
        print(('PASS' if v else 'FAIL') + '  ' + k)
    return 0 if all(checks.values()) else 1


if __name__ == '__main__':
    sys.exit(main())
