#!/usr/bin/env python3
"""Scaffold a new zone (town, route, building) in a named source tree.

  new_zone.py TREE --from TEMPLATE_ZONE --name "Location Name" [--keep-npcs]

Creates zones/NNN_<name>/ with the next free zone id and fresh slots of its own:
  zone.json      copy of the template's header with new script/text/entities/matrix/location ids
  events.s       one empty script (scr_0) to start from
  text.txt       one placeholder line
  entities.json  the template's warps (and furniture/NPCs/triggers with --keep-npcs)
  matrix.json    copy of the template's map matrix (point cells at new map models in maps/models/)
The location name is appended to text/system/0109_location_names.txt. The init ("level") script is
shared with the template, like Redux's Faraway Island shares Pledge Grove's. The zone is unreachable
until a warp somewhere points at it: add {"dest_zone": NNN, "dest_warp": 0, ...} to an existing
zone's entities.json. Rebuild with build_rom.py --src TREE.
"""
import argparse, json, os, re, shutil, sys
import catalog


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('tree')
    ap.add_argument('--from', dest='template', required=True, help='zone id or folder name, e.g. 400 or 400_accumula_town')
    ap.add_argument('--name', required=True)
    ap.add_argument('--keep-npcs', action='store_true')
    a = ap.parse_args()
    tree = a.tree
    man_path = os.path.join(tree, 'manifest.json')
    man = json.load(open(man_path))
    zones_dir = os.path.join(tree, 'zones')
    folders = sorted(os.listdir(zones_dir))
    if a.template.isdigit():
        tpl = next(f for f in folders if f.startswith(f'{int(a.template):03d}_'))
    else:
        tpl = a.template
    tdir = os.path.join(zones_dir, tpl)
    tz = json.load(open(os.path.join(tdir, 'zone.json'), encoding='utf-8'))

    def next_index(archive):
        return 1 + max(v[1] for v in man.values() if v[0] == archive)

    zid = next_index('a/0/1/2')
    slug = f'{zid:03d}_{catalog.ident(a.name).lower() or "zone"}'
    ndir = os.path.join(zones_dir, slug)
    os.makedirs(ndir)
    # location name: first id above every one a zone uses (a u8 in the zone header); the bank may
    # already be longer (Redux pads it), so overwrite that entry or append
    import gen5text as G
    used = max(json.load(open(os.path.join(zones_dir, f, 'zone.json'), encoding='utf-8'))['location_id']
               for f in folders)
    loc_id = used + 1
    if loc_id > 255:
        sys.exit('location names are a u8 in the zone header: no free id')
    loc_path = os.path.join(tree, 'text', 'system', '0109_location_names.txt')
    sec, pad = G.from_file(open(loc_path, encoding='utf-8').read())
    while len(sec[0]) <= loc_id:
        sec[0].append(('', 0))
    sec[0][loc_id] = (a.name, sec[0][loc_id][1])
    open(loc_path, 'w', encoding='utf-8').write(G.to_file(sec, pad))
    script, text = next_index('a/0/5/6'), next_index('a/0/0/3')
    ents, matrix = next_index('a/1/2/6'), next_index('a/0/0/9')
    z = dict(tz, id=zid, location=a.name, location_id=loc_id, script=script, text=text, entities=ents,
             matrix=matrix, encounter=None)
    json.dump(z, open(os.path.join(ndir, 'zone.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    open(os.path.join(ndir, 'events.s'), 'w').write('.script scr_0\n.header_end\nscr_0:\n    VMHalt\n')
    open(os.path.join(ndir, 'text.txt'), 'w', encoding='utf-8').write(f'{a.name}: new zone text.\n')
    by_slot = {(v[0], v[1]): k for k, v in man.items()}     # shared files live with their first zone
    e = json.load(open(os.path.join(tree, by_slot[('a/1/2/6', tz['entities'])]), encoding='utf-8'))
    if '_raw' in e:
        e = dict(furniture=[], npcs=[], warps=[], triggers=[], tail='')
    if not a.keep_npcs:
        e['furniture'], e['npcs'], e['triggers'] = [], [], []
        e.pop('init_offset', None)
    json.dump(e, open(os.path.join(ndir, 'entities.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    shutil.copy(os.path.join(tree, by_slot[('a/0/0/9', tz['matrix'])]), os.path.join(ndir, 'matrix.json'))
    man.update({
        f'zones/{slug}/zone.json': ['a/0/1/2', zid, 'zone'],
        f'zones/{slug}/events.s': ['a/0/5/6', script, 'script'],
        f'zones/{slug}/text.txt': ['a/0/0/3', text, 'text'],
        f'zones/{slug}/entities.json': ['a/1/2/6', ents, 'entities'],
        f'zones/{slug}/matrix.json': ['a/0/0/9', matrix, 'matrix'],
    })
    json.dump(man, open(man_path, 'w'), indent=1, sort_keys=True)
    print(f'created zones/{slug}: zone {zid}, location {loc_id} "{a.name}", script {script}, text {text}, '
          f'entities {ents}, matrix {matrix} (template {tpl})')


if __name__ == '__main__':
    main()
