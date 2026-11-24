#!/usr/bin/env python3
"""Export a ROM as a *named* source tree (organized by zone, symbolic scripts, labeled banks).

  export_named.py ROM OUTDIR

  OUTDIR/manifest.json                 relative path -> [archive, index, kind]
  OUTDIR/constants/*.txt               SPECIES_/ITEM_/MOVE_/TRAINER_/ZONE_... (frozen at export)
  OUTDIR/zones/NNN_location/zone.json  zone header (editable fields + raw record)
                           events.s    event script (symbolic, message text as comments)
                           init.s      init ("level") script
                           text.txt    the zone's story text bank
  OUTDIR/scripts/common/NNNN.s         scripts no zone header points at (global/shared)
  OUTDIR/text/story/NNNN.txt           story banks no zone owns
  OUTDIR/text/system/NNNN[_label].txt  system banks (species, moves, items, ... labeled)
  OUTDIR/data/*.json                   trainers, encounters, personal, learnsets, evolutions, moves, items
Everything rebuilds byte-exact with build_rom.py --src OUTDIR (checked here for scripts/text).
"""
import json, os, struct, sys
import ndsfs, catalog, symbols as Y, gen5text as G, gen5script as S, gen5data as D, gen5zone as Z, export_data
import redux_rom as R

SYSTEM_LABELS = {64: 'items', 90: 'species', 109: 'location_names', 374: 'abilities', 382: 'trainer_names',
                 383: 'trainer_classes', 398: 'types', 403: 'moves'}
ZONE_FIELDS = (('area', 0x02, 'H'), ('matrix', 0x04, 'H'), ('script', 0x06, 'H'), ('init_script', 0x08, 'H'),
               ('text', 0x0A, 'H'), ('entities', 0x16, 'H'), ('location_id', 0x1A, 'B'))


def zone_json(rec, z):
    enc = struct.unpack_from('<H', rec, 0x14)[0]
    return dict(id=z['id'], location=z['location'], location_id=rec[0x1A],
                area=struct.unpack_from('<H', rec, 0x02)[0], matrix=struct.unpack_from('<H', rec, 0x04)[0],
                script=z['script'],
                init_script=z['init_script'], text=z['text'], entities=struct.unpack_from('<H', rec, 0x16)[0],
                encounter=None if enc & 0x1FFF == 0x1FFF else enc & 0x1FFF, raw=rec.hex())


def zone_bytes(j):
    rec = bytearray.fromhex(j['raw'])
    for name, off, fmt in ZONE_FIELDS:
        struct.pack_into('<' + fmt, rec, off, j[name])
    enc = struct.unpack_from('<H', rec, 0x14)[0]
    struct.pack_into('<H', rec, 0x14, (enc & ~0x1FFF) | (0x1FFF if j['encounter'] is None else j['encounter']))
    return bytes(rec)


def main(rom_path, out):
    cat = catalog.Catalog(rom_path)
    rom, ids = cat.rom, cat.ids
    get = lambda p: ndsfs.narc(rom.file(ids[p]))
    consts = dict(cat.const)
    consts['zone'] = {z['id']: 'ZONE_' + z['slug'].upper() for z in cat.zones}
    Y.write_constants(out, consts)
    sym = Y.Symbols(Y.read_constants(out))
    manifest = {}

    def put(rel, data, archive, index, kind, mode='w'):
        p = os.path.join(out, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, mode, encoding='utf-8') as f:
            f.write(data)
        manifest[rel] = [archive, index, kind]

    story, system, scripts = get('a/0/0/3'), get('a/0/0/2'), get('a/0/5/6')
    zrec = get('a/0/1/2')[0]
    owners, text_owner = cat.owners()
    lines_of = lambda bank: [t for t, _ in G.decode(story[bank])[0]] if bank < len(story) else None
    # zones
    for z in cat.zones:
        d = f"zones/{z['slug']}"
        rec = zrec[z['id'] * catalog.ZONE_SIZE:(z['id'] + 1) * catalog.ZONE_SIZE]
        put(f'{d}/zone.json', json.dumps(zone_json(rec, z), ensure_ascii=False, indent=1) + '\n',
            'a/0/1/2', z['id'], 'zone')
    # scripts
    for i, data in enumerate(scripts):
        o = owners.get(i)
        if o:
            rel = f"zones/{o[1]['slug']}/{o[0]}.s"
            msgs = lines_of(o[1]['text'])
        else:
            rel, msgs = f'scripts/common/{i:04d}.s', None
        txt, _ = S.decompile_best(data, R.BUILD, sym.with_messages(msgs))
        assert S.assemble_any(txt, R.BUILD, sym) == data, i
        put(rel, txt, 'a/0/5/6', i, 'script')
    # zone entities (NPCs, warps, triggers, furniture): file chosen by zone header @0x16
    ents = get('a/1/2/6')
    slugs = [z['slug'] for z in cat.zones]
    ent_owner = {}
    for z in cat.zones:
        ent_owner.setdefault(struct.unpack_from('<H', zrec, z['id'] * catalog.ZONE_SIZE + 0x16)[0], z)
    for i, d in enumerate(ents):
        z = ent_owner.get(i)
        rel = f"zones/{z['slug']}/entities.json" if z else f'entities/common/{i:04d}.json'
        put(rel, json.dumps(Z.decode(d, slugs), ensure_ascii=False, indent=1) + '\n', 'a/1/2/6', i, 'entities')
    # map matrices (zone header @0x04) and map models (binary, e.g. from CTRMap)
    mat_owner = {}
    for z in cat.zones:
        mat_owner.setdefault(struct.unpack_from('<H', zrec, z['id'] * catalog.ZONE_SIZE + 0x04)[0], z)
    for i, d in enumerate(get('a/0/0/9')):
        z = mat_owner.get(i)
        rel = f"zones/{z['slug']}/matrix.json" if z else f'maps/matrices/{i:04d}.json'
        put(rel, json.dumps(Z.decode_matrix(d)) + '\n', 'a/0/0/9', i, 'matrix')
    for i, d in enumerate(get('a/0/0/8')):
        p = os.path.join(out, f'maps/models/{i:04d}.bin')
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, 'wb').write(d)
        manifest[f'maps/models/{i:04d}.bin'] = ['a/0/0/8', i, 'blob']
    # text
    for i, b in enumerate(story):
        z = text_owner.get(i)
        rel = f"zones/{z['slug']}/text.txt" if z else f'text/story/{i:04d}.txt'
        put(rel, G.to_file(G.decode(b), G.padding(b)), 'a/0/0/3', i, 'text')
    for i, b in enumerate(system):
        label = SYSTEM_LABELS.get(i)
        put(f"text/system/{i:04d}{'_' + label if label else ''}.txt", G.to_file(G.decode(b), G.padding(b)),
            'a/0/0/2', i, 'text')
    # data tables (same JSON as export_data.py)
    tables, _ = export_data.export(rom_path, '_tmp_named')
    for name, ents in tables.items():
        put(f'data/{name}.json', json.dumps(ents, ensure_ascii=False, indent=1) + '\n', name, None, 'data')
    with open(os.path.join(out, 'manifest.json'), 'w') as f:
        json.dump(manifest, f, indent=1, sort_keys=True)
    print(f'{out}: {len(manifest)} files ({sum(1 for v in manifest.values() if v[2] == "script")} scripts, '
          f'{len(cat.zones)} zones)')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
