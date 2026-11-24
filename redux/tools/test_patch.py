#!/usr/bin/env python3
"""Tests for redux_patch.py.

1. vanilla + patch == Redux, semantically: every text line, NARC subfile, file, decompressed code
   module and overlay-table field (except the stored-compressed flag/size) matches redux.nds.
2. A synthetic modified base (vanilla + unrelated edits + edits that collide with Redux) keeps the
   base's own edits, applies Redux everywhere else, and reports exactly the colliding units.
"""
import json, os, shutil, struct, subprocess, sys
import ndsfs, gen5text as G, gen5data as D, redux_patch as P
import redux_rom as R

B = R.BUILD
VAN, RED = os.path.join(B, 'vanilla_rom', 'black2.nds'), os.path.join(B, 'vanilla_rom', 'redux.nds')
PATCH = os.path.join(B, 'patch_redux')
TOOLS = os.path.dirname(os.path.abspath(__file__))


def same_content(a_path, b_path, skip=()):
    a, b = ndsfs.Rom(a_path), ndsfs.Rom(b_path)
    ids = {p: i for i, p in a.paths.items()}
    bad = []
    for path, fid in ids.items():
        if path in skip:
            continue
        x, y = bytes(a.file(fid)), bytes(b.file(fid))
        if x == y:
            continue
        nx, ny = ndsfs.narc(x), ndsfs.narc(y)
        if nx is None or ny is None or len(nx) != len(ny):
            bad.append(path)
            continue
        for i, (s, t) in enumerate(zip(nx, ny)):
            if s != t and not (path in P.TEXT_ARCHIVES and G.decode(s) == G.decode(t)):
                bad.append(f'{path}[{i}]')
    for m in ['arm9'] + [f'overlay_{n}' for n in range(len(a.overlays()))]:
        da, ea = P.module_bytes(a, m)
        db, eb = P.module_bytes(b, m)
        if da != db:
            bad.append(m)
        elif ea and eb:
            fa, fb = struct.unpack('<8I', ea), struct.unpack('<8I', eb)
            if fa[:7] != fb[:7] or (fa[7] >> 24 & ~1) != (fb[7] >> 24 & ~1):   # ignore compressed flag+size
                bad.append(m + ' table entry')
    return bad


def run(*args):
    subprocess.run([sys.executable, os.path.join(TOOLS, args[0])] + list(args[1:]), check=True)


def main():
    out = os.path.join(B, 'out')
    os.makedirs(out, exist_ok=True)
    # 1. vanilla + patch
    vr = os.path.join(out, 'vanilla+redux.nds')
    P.apply(PATCH, VAN, vr)
    bad = same_content(vr, RED)
    print(('PASS' if not bad else 'FAIL') + f'  vanilla + patch == Redux ({len(bad)} mismatches {bad[:5]})')
    # 2. synthetic modified base, built through the named tree
    tree = os.path.join(B, 'named', 'modbase')
    shutil.rmtree(tree, ignore_errors=True)
    shutil.copytree(os.path.join(B, 'named', 'vanilla'), tree)
    man = json.load(open(os.path.join(tree, 'manifest.json')))
    by_slot = {(v[0], v[1]): k for k, v in man.items()}
    # (a) unrelated text edit: a story line Redux does not touch
    patch = json.load(open(os.path.join(PATCH, 'patch.json')))
    touched = {tuple(u['key']) for u in patch['units'] if u['kind'] == 'text'}
    sub_touched = {tuple(u['key']) for u in patch['units'] if u['kind'] == 'sub'}
    bank, line = next((b_, l) for b_ in range(5, 676) for l in range(3)
                      if ('a/0/0/3', b_, l) not in touched and ('a/0/0/3', b_) in by_slot and
                      any(u['key'][:2] == ['a/0/0/3', b_] for u in patch['units'] if u['kind'] == 'text'))
    p = os.path.join(tree, by_slot[('a/0/0/3', bank)])
    cb, cl = next((k[1], k[2]) for k in sorted(touched) if k[0] == 'a/0/0/3' and k[1] == bank)
    sec, pad = G.from_file(open(p, encoding='utf-8').read())
    sec[0][line] = ('MODBASE: my own line', sec[0][line][1])          # (a) Redux leaves this one
    sec[0][cl] = ('MODBASE: conflicting line', sec[0][cl][1])         # (b) Redux rewrites this one
    open(p, 'w', encoding='utf-8').write(G.to_file(sec, pad))
    # (c) trainer Redux leaves alone vs one it changes
    tp = os.path.join(tree, 'data', 'trainers.json')
    T = json.load(open(tp, encoding='utf-8'))
    free = next(t['id'] for t in T if ('a/0/9/1', t['id']) not in sub_touched and ('a/0/9/2', t['id']) not in sub_touched and t.get('party'))
    hit = next(t['id'] for t in T if ('a/0/9/2', t['id']) in sub_touched and t.get('party'))
    T[free]['party'][0]['level'] = 77
    T[hit]['party'][0]['level'] = 76
    json.dump(T, open(tp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    mb = os.path.join(out, 'modbase.nds')
    run('build_rom.py', '--src', tree, '--base', VAN, '--out', mb)
    res = os.path.join(out, 'modbase+redux.nds')
    stats, conflicts = P.apply(PATCH, mb, res, os.path.join(out, 'modbase+redux.md'))
    r = ndsfs.Rom(res)
    ids = {q: i for i, q in r.paths.items()}
    story = ndsfs.narc(r.file(ids['a/0/0/3']))
    names = D.Names(ndsfs.narc(r.file(ids['a/0/0/2'])))
    tr = D.decode_trainers(ndsfs.narc(r.file(ids['a/0/9/1'])), ndsfs.narc(r.file(ids['a/0/9/2'])), names)
    checks = {
        'own unrelated line kept': G.decode(story[bank])[0][line][0] == 'MODBASE: my own line',
        'own conflicting line kept': G.decode(story[bank])[0][cl][0] == 'MODBASE: conflicting line',
        'own trainer edit kept': tr[free]['party'][0]['level'] == 77,
        'conflicting trainer kept from base': tr[hit]['party'][0]['level'] == 76,
        'exactly the colliding units reported': sorted(map(tuple, (k for _, k in conflicts))) ==
            sorted([('a/0/0/3', cb, cl), ('a/0/9/2', hit)]),
        'everything else is Redux': not [x for x in same_content(res, RED)
                                         if x not in ('a/0/0/3[%d]' % bank, 'a/0/9/2[%d]' % hit,
                                                      'a/0/9/2[%d]' % free)],   # base-only edit, kept
    }
    # 3. code merge: base arm9 edited outside and inside a Redux range
    import romtool
    van_rom = ndsfs.Rom(VAN)
    va, _ = P.module_bytes(van_rom, 'arm9')
    unit = next(u for u in patch['units'] if u['kind'] == 'module' and u['key'] == ['arm9'])
    rs = unit['ranges']
    inside = rs[len(rs) // 2][0]
    outside = next(i for i in range(0x8000, len(va)) if not any(s <= i < e for s, e in rs))
    mod = bytearray(va)
    mod[inside] ^= 0xFF
    mod[outside] ^= 0xFF
    cb_ = os.path.join(out, 'codebase.nds')
    open(cb_, 'wb').write(romtool.build(VAN, arm9=bytes(mod)))
    res3 = os.path.join(out, 'codebase+redux.nds')
    _, conf3 = P.apply(PATCH, cb_, res3)
    ra, _ = P.module_bytes(ndsfs.Rom(res3), 'arm9')
    xa, _ = P.module_bytes(ndsfs.Rom(RED), 'arm9')
    others = [i for s, e in rs if not (s <= inside < e) for i in range(s, e)]
    checks.update({
        'code: base edit outside Redux ranges kept': ra[outside] == mod[outside],
        'code: colliding range kept from base': ra[inside] == mod[inside],
        'code: all other Redux ranges applied': all(ra[i] == xa[i] for i in others),
        'code: one module conflict reported': [k for k, _ in conf3] == ['module'],
    })
    for k, v in checks.items():
        print(('PASS' if v else 'FAIL') + '  ' + k)
    print('conflicts reported:', conflicts, conf3)
    return 0 if not bad and all(checks.values()) else 1


if __name__ == '__main__':
    sys.exit(main())
