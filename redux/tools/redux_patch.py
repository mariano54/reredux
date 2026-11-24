#!/usr/bin/env python3
"""Redux as a *semantic* patch that can be applied on top of an already-modified Black 2.

  redux_patch.py make  VANILLA.nds REDUX.nds PATCHDIR
  redux_patch.py apply PATCHDIR BASE.nds OUT.nds [--report report.md]

A patch is a list of units, each with its vanilla and Redux value:
  text     (archive, bank, line)    one message line (a/0/0/2, a/0/0/3); lines Redux added too
  zone     (zone id)                48-byte zone header record (a/0/1/2)
  sub      (archive, index)         any other NARC subfile (a script, a trainer, a Pokémon, ...)
  file     (path)                   a non-NARC file
  module   (arm9 | overlay N)       decompressed code module (+ overlay table entry), with the
                                    byte ranges that differ so a conflict can still be merged
Apply does a three-way merge per unit: base == vanilla -> take Redux; base == Redux -> nothing to
do; otherwise keep the base and report a conflict (for modules: apply every Redux byte range whose
base bytes are still vanilla, report the rest).
"""
import argparse, hashlib, json, os, struct, subprocess, sys, tempfile
import ndsfs, romtool, gen5text as G
import redux_rom as R

TEXT_ARCHIVES = ('a/0/0/2', 'a/0/0/3')
ZONE_ARCHIVE, ZONE_SIZE = 'a/0/1/2', 48
BLZ = os.path.join(R.BUILD, 'bin', 'blz')


# ---- helpers ----------------------------------------------------------------------------------------
def blz(mode, data):
    with tempfile.TemporaryDirectory() as t:
        i, o = os.path.join(t, 'i'), os.path.join(t, 'o')
        open(i, 'wb').write(data)
        subprocess.run([BLZ, mode, i, o], check=True, capture_output=True)
        return open(o, 'rb').read()


def module_bytes(rom, which):
    """Decompressed code module and (for overlays) its table entry."""
    if which == 'arm9':
        data = bytes(rom.m[rom.arm9[0]:rom.arm9[0] + rom.arm9[1]])
        # vanilla stores arm9 BLZ-compressed (footer at the end); Redux stores it decompressed
        if data[-8:] != bytes(8) and struct.unpack_from('<I', data, len(data) - 4)[0] < 0x100000 \
                and (struct.unpack_from('<I', data, len(data) - 8)[0] >> 24) in range(8, 12):
            try:
                return blz('-d', data), None
            except subprocess.CalledProcessError:
                pass
        return data, None
    n = int(which.split('_')[1])
    ent = rom.overlays()[n]
    data = bytes(rom.file(ent['file_id']))
    if ent['compressed']:
        data = blz('-d', data)
    o = rom.ovt9[0] + 32 * n
    return data, bytes(rom.m[o:o + 32])


def ranges(a, b):
    out, i = [], 0
    n = min(len(a), len(b))
    while i < n:
        if a[i] != b[i]:
            j = i
            while j < n and a[j] != b[j]:
                j += 1
            out.append((i, j))
            i = j
        else:
            i += 1
    return out


class Store:
    """Large payloads live in PATCHDIR/blobs/<sha1>.bin; small ones inline as hex."""
    def __init__(self, d):
        self.d = d
        os.makedirs(os.path.join(d, 'blobs'), exist_ok=True)

    def put(self, data):
        if data is None:
            return None
        if len(data) <= 256:
            return {'hex': data.hex()}
        h = hashlib.sha1(data).hexdigest()
        p = os.path.join(self.d, 'blobs', h + '.bin')
        if not os.path.exists(p):
            open(p, 'wb').write(data)
        return {'blob': h}

    def get(self, ref):
        if ref is None:
            return None
        if 'hex' in ref:
            return bytes.fromhex(ref['hex'])
        return open(os.path.join(self.d, 'blobs', ref['blob'] + '.bin'), 'rb').read()


# ---- make ---------------------------------------------------------------------------------------------
def make(vanilla_path, redux_path, out):
    v, x = ndsfs.Rom(vanilla_path), ndsfs.Rom(redux_path)
    vids = {p: i for i, p in v.paths.items()}
    xids = {p: i for i, p in x.paths.items()}
    st = Store(out)
    units = []
    for path, fid in sorted(xids.items()):
        vf = bytes(v.file(vids[path])) if path in vids else b''
        xf = bytes(x.file(fid))
        if vf == xf:
            continue
        vn, xn = ndsfs.narc(vf) if vf else [], ndsfs.narc(xf)
        if xn is None:
            units.append(dict(kind='file', key=[path], vanilla=st.put(vf), redux=st.put(xf)))
            continue
        if path in TEXT_ARCHIVES:
            for i in range(len(xn)):
                vb = vn[i] if i < len(vn) else None
                if vb == xn[i]:
                    continue
                vl = G.decode(vb)[0] if vb else []
                xl = G.decode(xn[i])[0]
                for k in range(max(len(vl), len(xl))):
                    a = vl[k] if k < len(vl) else None
                    b = xl[k] if k < len(xl) else None
                    if a != b:
                        units.append(dict(kind='text', key=[path, i, k], vanilla=a, redux=b))
                units.append(dict(kind='textmeta', key=[path, i], vanilla_lines=len(vl), redux_lines=len(xl),
                                  redux_pad=G.padding(xn[i]).hex() if G.padding(xn[i]) is not None else None))
            continue
        if path == ZONE_ARCHIVE:
            vz, xz = vn[0], xn[0]
            for z in range(max(len(vz), len(xz)) // ZONE_SIZE):
                a, b = vz[z * ZONE_SIZE:(z + 1) * ZONE_SIZE] or None, xz[z * ZONE_SIZE:(z + 1) * ZONE_SIZE] or None
                if a != b:
                    units.append(dict(kind='zone', key=[z], vanilla=st.put(a), redux=st.put(b)))
            continue
        for i in range(max(len(vn), len(xn))):
            a = vn[i] if i < len(vn) else None
            b = xn[i] if i < len(xn) else None
            if a != b:
                units.append(dict(kind='sub', key=[path, i], vanilla=st.put(a), redux=st.put(b)))
    # code
    mods = ['arm9'] + [f'overlay_{n}' for n in range(len(x.overlays()))]
    for m in mods:
        vd, vo = module_bytes(v, m)
        xd, xo = module_bytes(x, m)
        if vd == xd and vo == xo:
            continue
        units.append(dict(kind='module', key=[m], vanilla=st.put(vd), redux=st.put(xd),
                          vanilla_ovt=vo.hex() if vo else None, redux_ovt=xo.hex() if xo else None,
                          ranges=ranges(vd, xd), vanilla_len=len(vd), redux_len=len(xd)))
    json.dump(dict(format=1, vanilla_sha1=hashlib.sha1(open(vanilla_path, 'rb').read()).hexdigest(),
                   redux_sha1=hashlib.sha1(open(redux_path, 'rb').read()).hexdigest(), units=units),
              open(os.path.join(out, 'patch.json'), 'w'), indent=0)
    kinds = {}
    for u in units:
        kinds[u['kind']] = kinds.get(u['kind'], 0) + 1
    print(f'{out}: {len(units)} units {kinds}')


# ---- apply --------------------------------------------------------------------------------------------
def apply(patch_dir, base_path, out_path, report=None):
    p = json.load(open(os.path.join(patch_dir, 'patch.json')))
    st = Store(patch_dir)
    base = ndsfs.Rom(base_path)
    ids = {q: i for i, q in base.paths.items()}
    narcs, raw_files = {}, {}
    get_narc = lambda path: narcs.setdefault(path, ndsfs.narc(bytes(base.file(ids[path]))))
    texts = {}       # (path, bank) -> list of (text, flags)
    stats = {'applied': 0, 'already': 0, 'conflict': 0}
    conflicts = []

    def decide(kind, key, cur, van, red):
        if cur == red:
            stats['already'] += 1
            return red
        if cur == van:
            stats['applied'] += 1
            return red
        stats['conflict'] += 1
        conflicts.append((kind, key))
        return cur

    def bank(path, i):
        if (path, i) not in texts:
            n = get_narc(path)
            texts[(path, i)] = list(G.decode(n[i])[0]) if i < len(n) and n[i] else []
        return texts[(path, i)]

    zones = None
    modules, ovt = {}, {}
    for u in p['units']:
        k = u['kind']
        if k == 'text':
            path, i, line = u['key']
            b = bank(path, i)
            van = tuple(u['vanilla']) if u['vanilla'] else None
            red = tuple(u['redux']) if u['redux'] else None
            cur = tuple(b[line]) if line < len(b) else None
            res = decide('text', u['key'], cur, van, red)
            if res is not None:
                while len(b) <= line:
                    b.append(('', 0))
                b[line] = res
            elif cur is not None:
                b[line] = None      # Redux deleted this line (and the base had not changed it)
        elif k == 'zone':
            if zones is None:
                zones = bytearray(get_narc(ZONE_ARCHIVE)[0])
            z = u['key'][0]
            q = z * ZONE_SIZE
            cur = bytes(zones[q:q + ZONE_SIZE]) or None
            res = decide('zone', u['key'], cur, st.get(u['vanilla']), st.get(u['redux']))
            if res is not None:
                if len(zones) < q + ZONE_SIZE:
                    zones += bytes(q + ZONE_SIZE - len(zones))
                zones[q:q + ZONE_SIZE] = res
        elif k == 'sub':
            path, i = u['key']
            n = get_narc(path)
            cur = n[i] if i < len(n) else None
            res = decide('sub', u['key'], cur, st.get(u['vanilla']), st.get(u['redux']))
            if res is not None:
                while len(n) <= i:
                    n.append(b'')
                n[i] = res
        elif k == 'file':
            path = u['key'][0]
            cur = bytes(base.file(ids[path]))
            raw_files[path] = decide('file', u['key'], cur, st.get(u['vanilla']), st.get(u['redux']))
        elif k == 'module':
            m = u['key'][0]
            cur, cur_ovt = module_bytes(base, m)
            van, red = st.get(u['vanilla']), st.get(u['redux'])
            if cur == red:
                stats['already'] += 1
                continue
            if cur == van:
                stats['applied'] += 1
                modules[m] = red
                if u['redux_ovt']:
                    ovt[m] = bytes.fromhex(u['redux_ovt'])
                continue
            # partial merge: Redux byte ranges whose base bytes are still vanilla
            if u['ranges'] is not None and len(cur) == len(van):
                # common prefix byte ranges, then Redux's extra tail (e.g. the arm9 footer)
                merged, bad = bytearray(cur) + red[len(van):], []
                for s, e in u['ranges']:
                    if cur[s:e] == van[s:e]:
                        merged[s:e] = red[s:e]
                    elif cur[s:e] != red[s:e]:
                        bad.append([s, e])
                modules[m] = bytes(merged)
                if u['redux_ovt'] and u['redux_ovt'] != u['vanilla_ovt']:
                    bad.append('overlay table entry')
                stats['applied' if not bad else 'conflict'] += 1
                if bad:
                    conflicts.append(('module', [m, f'{len(bad)} ranges kept from base']))
            else:
                stats['conflict'] += 1
                conflicts.append(('module', [m, 'size/layout differs; kept base']))
    # re-encode text banks
    for (path, i), lines in texts.items():
        while lines and lines[-1] is None:
            lines.pop()
        if None in lines:   # a deletion in the middle can only come from a conflict elsewhere; keep slot
            lines = [l if l is not None else ('', 0) for l in lines]
        n = get_narc(path)
        old = n[i] if i < len(n) else b''
        pad = G.padding(old) if old else None
        new = G.encode([lines], 0, pad)
        if new != old:
            while len(n) <= i:
                n.append(b'')
            n[i] = new
    if zones is not None:
        narcs[ZONE_ARCHIVE] = [bytes(zones)]
    files = {}
    for path, subs in narcs.items():
        old = bytes(base.file(ids[path]))
        packed = ndsfs.pack_narc(subs, ndsfs.narc_layout(old))
        if packed != old:
            files[ids[path]] = packed
    for path, data in raw_files.items():
        if data != bytes(base.file(ids[path])):
            files[ids[path]] = data
    # code: modules are written decompressed; overlay table entries updated accordingly
    arm9 = None
    ovt9 = bytearray(base.m[base.ovt9[0]:base.ovt9[0] + base.ovt9[1]])
    for m, data in modules.items():
        if m == 'arm9':
            arm9 = data
            continue
        n = int(m.split('_')[1])
        ent = bytearray(ovt.get(m, ovt9[32 * n:32 * n + 32]))
        struct.pack_into('<I', ent, 8, len(data))          # ram size = decompressed image
        flags = struct.unpack_from('<I', ent, 28)[0]
        struct.pack_into('<I', ent, 28, flags & ~(1 << 24) & ~0xFFFFFF)   # stored uncompressed
        ovt9[32 * n:32 * n + 32] = ent
        files[struct.unpack_from('<I', ent, 24)[0]] = data
    img = romtool.build(base_path, files, arm9=arm9, ovt9=bytes(ovt9) if modules else None)
    open(out_path, 'wb').write(img)
    lines = [f'# Redux patch applied to {os.path.basename(base_path)}\n\n',
             f"applied {stats['applied']}, already present {stats['already']}, conflicts {stats['conflict']}\n\n"]
    if conflicts:
        lines.append('| kind | key |\n|---|---|\n')
        lines += [f'| {k} | {json.dumps(key, ensure_ascii=False)} |\n' for k, key in conflicts]
    if report:
        open(report, 'w', encoding='utf-8').writelines(lines)
    print(''.join(lines[:2]).strip())
    return stats, conflicts


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    m = sub.add_parser('make')
    m.add_argument('vanilla'); m.add_argument('redux'); m.add_argument('out')
    a_ = sub.add_parser('apply')
    a_.add_argument('patch'); a_.add_argument('base'); a_.add_argument('out'); a_.add_argument('--report')
    a = ap.parse_args()
    if a.cmd == 'make':
        os.makedirs(a.out, exist_ok=True)
        make(a.vanilla, a.redux, a.out)
    else:
        apply(a.patch, a.base, a.out, a.report)


if __name__ == '__main__':
    main()
