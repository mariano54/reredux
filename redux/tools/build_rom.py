#!/usr/bin/env python3
"""Build a ROM from editable sources.

  build_rom.py [--src DIR] [--base ROM] [--out ROM] [--check]

Sources (as written by export_text.py / export_scripts.py / export_data.py):
  DIR/text/{system,story}/NNNN.txt   message banks   (a/0/0/2, a/0/0/3)
  DIR/scripts/NNNN.s                 event scripts   (a/0/5/6)
  DIR/data/*.json                    trainers, encounters, personal, learnsets, evolutions, moves, items
Each archive is re-encoded, repacked with the base ROM's NARC layout and placed with romtool; files
that come out identical to the base are left untouched. --check asserts the result equals the base
(true for unedited sources).
"""
import argparse, glob, hashlib, json, os, sys
import ndsfs, romtool, gen5text as G, gen5script as S, gen5data as D
import redux_rom as R

DATA = {  # json name: (narc path(s), encoder(entries, names, types) -> list of subfiles)
    'encounters': ('a/1/2/7', lambda e, n, t: D.encode_encounters(e, n)),
    'personal': ('a/0/1/6', D.encode_personal),
    'learnsets': ('a/0/1/8', lambda e, n, t: D.encode_learnsets(e, n)),
    'evolutions': ('a/0/1/9', lambda e, n, t: D.encode_evolutions(e, n)),
    'moves': ('a/0/2/1', D.encode_moves),
    'items': ('a/0/2/4', lambda e, n, t: D.encode_items(e, n)),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', default=os.path.join(R.BUILD, 'src', 'redux'))
    ap.add_argument('--base', default=os.path.join(R.BUILD, 'vanilla_rom', 'redux.nds'))
    ap.add_argument('--out', default=os.path.join(R.BUILD, 'out', 'redux_built.nds'))
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    base = ndsfs.Rom(a.base)
    ids = {p: i for i, p in base.paths.items()}
    orig = lambda p: bytes(base.file(ids[p]))
    new = {}   # path -> list of subfiles
    manifest_path = os.path.join(a.src, 'manifest.json')
    if os.path.exists(manifest_path):
        return build_named(a, base, ids, orig, json.load(open(manifest_path)))

    def text_banks(kind, path):
        files = sorted(glob.glob(os.path.join(a.src, 'text', kind, '*.txt')))
        out = []
        for f in files:
            sec, pad = G.from_file(open(f, encoding='utf-8').read())
            out.append(G.encode(sec, 0, pad))
        return out

    new['a/0/0/2'] = text_banks('system', 'a/0/0/2')
    new['a/0/0/3'] = text_banks('story', 'a/0/0/3')
    new['a/0/5/6'] = [S.assemble_any(open(f).read(), R.BUILD)
                      for f in sorted(glob.glob(os.path.join(a.src, 'scripts', '*.s')))]
    # names/types for the data tables come from the (possibly edited) system text
    sysb = new['a/0/0/2']
    names = D.Names(sysb)
    types = D.name_list(sysb[398]) + ['Fairy']
    tr = json.load(open(os.path.join(a.src, 'data', 'trainers.json'), encoding='utf-8'))
    new['a/0/9/1'], new['a/0/9/2'] = D.encode_trainers(tr, names)
    for name, (path, enc) in DATA.items():
        new[path] = enc(json.load(open(os.path.join(a.src, 'data', f'{name}.json'), encoding='utf-8')), names, types)
    return finish(a, ids, orig, new)


def build_named(a, base, ids, orig, manifest):
    """Named tree (export_named.py): every file says which archive slot it fills."""
    import symbols as Y, export_named as N, catalog
    sym = Y.Symbols(Y.read_constants(a.src))
    import gen5zone as Z
    subs = {p: ndsfs.narc(orig(p)) for p in ('a/0/0/2', 'a/0/0/3', 'a/0/5/6', 'a/0/1/2', 'a/1/2/6',
                                              'a/0/0/9', 'a/0/0/8')}
    zones = bytearray(subs['a/0/1/2'][0])

    def place(p, i, data):
        lst = subs[p]
        while len(lst) <= i:
            lst.append(b'')
        lst[i] = data

    for rel, (archive, index, kind) in sorted(manifest.items()):
        path = os.path.join(a.src, rel)
        if kind == 'text':
            sec, pad = G.from_file(open(path, encoding='utf-8').read())
            place(archive, index, G.encode(sec, 0, pad))
        elif kind == 'script':
            place(archive, index, S.assemble_any(open(path).read(), R.BUILD, sym))
        elif kind == 'entities':
            place(archive, index, Z.encode(json.load(open(path, encoding='utf-8'))))
        elif kind == 'matrix':
            place(archive, index, Z.encode_matrix(json.load(open(path, encoding='utf-8'))))
        elif kind == 'blob':
            place(archive, index, open(path, 'rb').read())
        elif kind == 'zone':
            rec = N.zone_bytes(json.load(open(path, encoding='utf-8')))
            q = index * catalog.ZONE_SIZE
            if q >= len(zones):
                zones += bytes(q + catalog.ZONE_SIZE - len(zones))
            zones[q:q + catalog.ZONE_SIZE] = rec
    subs['a/0/1/2'] = [bytes(zones)]
    new = dict(subs)
    sysb = new['a/0/0/2']
    names = D.Names(sysb)
    types = D.name_list(sysb[398]) + ['Fairy']
    tr = json.load(open(os.path.join(a.src, 'data', 'trainers.json'), encoding='utf-8'))
    new['a/0/9/1'], new['a/0/9/2'] = D.encode_trainers(tr, names)
    for name, (path, enc) in DATA.items():
        new[path] = enc(json.load(open(os.path.join(a.src, 'data', f'{name}.json'), encoding='utf-8')), names, types)
    return finish(a, ids, orig, new)


def finish(a, ids, orig, new):
    files = {}
    for path, subs in new.items():
        old = orig(path)
        packed = ndsfs.pack_narc(subs, ndsfs.narc_layout(old))
        if packed != old:
            files[ids[path]] = packed
            print(f'changed: {path}')
    img = romtool.build(a.base, files)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, 'wb').write(img)
    sha = hashlib.sha1(img).hexdigest()
    print(f'wrote {a.out} sha1 {sha} ({len(files)} archives changed)')
    if a.check:
        want = hashlib.sha1(open(a.base, 'rb').read()).hexdigest()
        print('identical to base' if sha == want else 'DIFFERS from base')
        return 0 if sha == want else 1


if __name__ == '__main__':
    sys.exit(main())
