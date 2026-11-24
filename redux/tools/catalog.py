"""Names for everything in a B2W2 ROM: zones, archives and constant tables.

  zones      a/0/1/2 (ARCID_ZONEDATA): 48-byte records; u16 @0x06 event script, @0x08 init script,
             @0x0A story text bank, @0x14 low 13 bits encounter table (0x1FFF = none),
             u8 @0x1A location name (system text 0109)
  archives   ARCID_* names from swan/data/arcid_def.h (a/X/Y/Z = arc id XYZ)
  constants  SPECIES_*, MOVE_*, ITEM_*, ABILITY_*, TYPE_*, TRCLASS_*, TRAINER_* from system text,
             made unique (a clash gets the id appended)
"""
import os, re, struct
import ndsfs, gen5data as D
import redux_rom as R

ZONE_SIZE = 48


def ident(s):
    s = s.replace('♀', '_F').replace('♂', '_M').replace('é', 'E').replace('É', 'E')
    s = re.sub(r'\{[^}]*\}', '', s)
    s = re.sub(r'[^0-9A-Za-z]+', '_', s).strip('_').upper()
    return s


def constants(prefix, names, skip_zero=True):
    """[(name, id)] unique identifiers; empty/placeholder names become PREFIX_<id>."""
    out, seen = {}, {}
    for i, n in enumerate(names):
        base = ident(n)
        if not base or (skip_zero and i == 0) or set(base) <= {'_'}:
            base = f'{i}'
        name = f'{prefix}_{base}'
        if name in seen:
            name = f'{name}_{i}'
        seen[name] = i
        out[i] = name
    return out


def arc_names():
    swan = os.environ.get('REDUX_SWAN') or os.path.join(R.BUILD, 'ext', 'swan')
    path = os.path.join(swan, 'data', 'arcid_def.h')
    out = {}
    if os.path.exists(path):
        for m in re.finditer(r'#define ARCID_(\w+)\s+(\d+)', open(path).read()):
            n = int(m.group(2))
            out[f'a/{n // 100}/{n // 10 % 10}/{n % 10}'] = m.group(1).lower()
    return out


class Catalog:
    def __init__(self, rom_path):
        rom = ndsfs.Rom(rom_path)
        ids = {p: i for i, p in rom.paths.items()}
        self.rom, self.ids = rom, ids
        sysb = ndsfs.narc(rom.file(ids['a/0/0/2']))
        self.names = D.Names(sysb)
        self.locations = D.name_list(sysb[109])
        z = ndsfs.narc(rom.file(ids['a/0/1/2']))[0]
        self.zones = []
        for i in range(len(z) // ZONE_SIZE):
            q = i * ZONE_SIZE
            enc = struct.unpack_from('<H', z, q + 0x14)[0] & 0x1FFF
            loc = z[q + 0x1A]
            lname = self.locations[loc] if loc < len(self.locations) else f'loc{loc}'
            self.zones.append(dict(id=i, location=lname, slug=f'{i:03d}_{ident(lname).lower() or "zone"}',
                                   script=struct.unpack_from('<H', z, q + 6)[0],
                                   init_script=struct.unpack_from('<H', z, q + 8)[0],
                                   text=struct.unpack_from('<H', z, q + 10)[0],
                                   encounter=None if enc == 0x1FFF else enc))
        self.arcs = arc_names()
        n = self.names
        self.const = {
            'species': constants('SPECIES', n.species),
            'move': constants('MOVE', n.moves),
            'item': constants('ITEM', n.items),
            'ability': constants('ABILITY', D.name_list(sysb[374])),
            'type': constants('TYPE', D.name_list(sysb[398]) + ['Fairy'], skip_zero=False),
            'trclass': constants('TRCLASS', n.tclass, skip_zero=False),
            'trainer': {i: f'TRAINER_{i:03d}_{ident(t) or "X"}' for i, t in enumerate(n.tname)},
        }

    def owners(self):
        """script file -> ('events'|'init', zone), story text bank -> zone (first zone using it)."""
        scripts, texts = {}, {}
        for z in self.zones:
            scripts.setdefault(z['script'], ('events', z))
            scripts.setdefault(z['init_script'], ('init', z))
            texts.setdefault(z['text'], z)
        return scripts, texts
