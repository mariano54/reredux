"""HGSS "talk to your following Pokémon" data for Black 2 (followers/talk.c).

Reads HeartGold/SoulSilver's own talk data from a pokeheartgold decomp checkout (nothing from HGSS is
committed here):
  files/a/2/2/0  NARC 222  condition lists: member 0 generic (70 entries), member mapsec+1 (30 each)
  files/a/2/2/1  NARC 223  talk records (52 bytes)
  files/a/2/2/2  NARC 224  motion scripts (80 bytes)
  files/a/2/3/1  NARC 233  species group bytes
  files/msgdata/msg/msg_0265.json  the 759 talk lines
and translates it to Unova with followers/talk_mapping.json (zones -> HGSS location lists and roles,
event flags -> badges / items, HGSS-only lines disabled, Gen 5 species groups, Musical props for
accessories). Formats and the selection algorithm: build/hgss_talk/SPEC.md and talk.c.
"""
import json, os, re, struct

HERE = os.path.dirname(os.path.abspath(__file__))
MAPPING = os.path.join(HERE, '..', 'followers', 'talk_mapping.json')

ENTRY, RECORD, MOTION = 20, 52, 80
GENERIC = 70
LIST = 30
COND_BADGE, COND_BADGE_OF_ZONE, COND_ITEM = 0x8000, 0x80FF, 0x4000   # entry +0x12 in our data

# HGSS tile behaviours in the lists -> our tile groups (talk_select.c tile_group() maps B2 tile
# classes to the same groups). Behaviours 48/49 (Olivine's pier edges) have no Unova counterpart.
TILE_GROUPS = {2: 1, 3: 2, 22: 3, 23: 4, 32: 5, 33: 6}   # grass, very tall grass, puddle, shallows, ice, sand

# lines of ours, appended after the HGSS ones. B2 gives Musical props instead of Fashion Case
# accessories (its own prop gift script prints those messages); a prop can't be owned twice, which
# takes the place of HGSS's "the Fashion Case is full".
EXTRA_LINES = {
    'TALK_MSG_PROP_OWNED': r"{0100:2} received the\n{010A:1}!{BE00}\nBut it's already in the Prop Case!",
}


def read_narc(path):
    data = open(path, 'rb').read()
    assert data[:4] == b'NARC', path
    off = struct.unpack_from('<H', data, 0xC)[0]
    size, n = struct.unpack_from('<IH', data, off + 4)
    fat = [struct.unpack_from('<II', data, off + 12 + 8 * i) for i in range(n)]
    off += size
    off += struct.unpack_from('<I', data, off + 4)[0]
    return [data[off + 8 + s:off + 8 + e] for s, e in fat]


STRVAR = {(1, 0): '{0102:0}', (3, 2): '{0100:2}', (8, 4): '{0109:4}'}


def b2_text(t):
    """HGSS message -> our gen5text syntax (escaped newlines, B2 control codes)."""
    t = t.replace('{YESNO 0}', '').replace('’', "'")
    t = re.sub(r'\{STRVAR_1 (\d+), (\d+), 0\}', lambda m: STRVAR[int(m.group(1)), int(m.group(2))], t)
    assert '{STRVAR' not in t and '{' not in re.sub(r'\{01\d\d:\d\}', '', t), t
    # \r: wait, scroll one line; \f: wait, new page
    return t.replace('\r', '{BE00}\\n').replace('\f', '{BE01}\\n').replace('\n', '\\n')


class TalkData:
    def __init__(self, hgss_root, tile_map, weather_ok=(1, 3), translations=None):
        """tile_map: HGSS tile behaviour -> B2 tile class (entries with an unmapped tile are disabled).
        translations: {'f:<index in texts()>': text} for another language (jp_port.py's follower file)."""
        self.translations = translations or {}
        a = os.path.join(hgss_root, 'files', 'a')
        self.lists = read_narc(os.path.join(a, '2', '2', '0'))
        self.records = read_narc(os.path.join(a, '2', '2', '1'))
        self.motions = read_narc(os.path.join(a, '2', '2', '2'))
        self.groups = read_narc(os.path.join(a, '2', '3', '1'))[0]
        msgs = json.load(open(os.path.join(hgss_root, 'files', 'msgdata', 'msg', 'msg_0265.json')))['messages']
        self.lines = [b2_text(''.join(m['en_US']) if isinstance(m['en_US'], list) else m['en_US']) for m in msgs]
        self.map = json.load(open(MAPPING))
        self.tile_map = tile_map
        self.weather_ok = weather_ok
        assert len(self.lists[0]) == GENERIC * ENTRY and all(len(r) == RECORD for r in self.records)
        self.stats = {'disabled': 0}

    def texts(self):
        lines = self.lines + list(EXTRA_LINES.values())
        return [self.translations.get(f'f:{i}', t) for i, t in enumerate(lines)]

    def extra_ids(self):
        """talk.s placeholder -> index of its line in texts()"""
        return {k: len(self.lines) + i for i, k in enumerate(EXTRA_LINES)}

    def _entry(self, raw, member, ev):
        e = bytearray(raw)
        if (struct.unpack_from('<H', e, 0x0A)[0] >> 6) == 0:
            return bytes(e)
        m = self.map
        off = lambda: struct.pack_into('<H', e, 0x0A, struct.unpack_from('<H', e, 0x0A)[0] & 0x3F)
        disabled = [member, ev] in m['disabled']
        mapid1, tile, flag = struct.unpack_from('<H', e, 0x0C)[0], struct.unpack_from('<H', e, 0x0E)[0], struct.unpack_from('<H', e, 0x12)[0]
        if mapid1:
            role = m['map_roles'].get(str(mapid1 - 1), 0)
            disabled |= role == 0
            struct.pack_into('<H', e, 0x0C, role)
        if tile:
            disabled |= tile not in self.tile_map
            struct.pack_into('<H', e, 0x0E, self.tile_map.get(tile, 0))
        if flag:
            c = m['flags'].get(str(flag), 'drop')
            if c == 'per_entry':
                c = next(x['cond'] for x in m['entry_flags'] if x['member'] == member and x['eval'] == ev)
            if c == 'drop':
                disabled = True
                v = 0
            elif c == 'true':
                v = 0
            elif 'badge' in c:
                v = COND_BADGE | c['badge']
            elif 'badge_of_zone' in c:
                v = COND_BADGE_OF_ZONE
            else:
                v = COND_ITEM | c['item']
            struct.pack_into('<H', e, 0x12, v)
        if e[0x07] or e[0x04] >> 5:     # Shiny Leaf / Pokéathlon conditions: nothing like them in B2
            disabled = True
        w = struct.unpack_from('<H', e, 0x08)[0]
        if (w & 7) and (w & 7) not in self.weather_ok:
            disabled = True
        for p in m['patches']:
            if p['member'] == member and ev in p['evals'] and 'weather' in p['add']:
                struct.pack_into('<H', e, 0x08, (w & ~7) | p['add']['weather'])
        if disabled:
            off()
            self.stats['disabled'] += 1
        return bytes(e)

    def blob(self, text_base, nzones):
        """-> data member bytes. text_base: text id of HGSS line 1 in the bank."""
        m = self.map
        used = sorted({v[0] for v in m['zones'].values() if v[0] >= 0})
        index = {mem: i for i, mem in enumerate(used)}
        generic = b''.join(self._entry(self.lists[0][i * ENTRY:(i + 1) * ENTRY], 0, 30 + i) for i in range(GENERIC))
        lists = b''
        for mem in used:
            raw = self.lists[mem]
            assert len(raw) == LIST * ENTRY
            lists += b''.join(self._entry(raw[i * ENTRY:(i + 1) * ENTRY], mem, i) for i in range(LIST))
        zl, zr, zb = bytearray([0xFF] * nzones), bytearray(nzones), bytearray([0xFF] * nzones)
        for z, (mem, role, badge) in m['zones'].items():
            z = int(z)
            if z < nzones:
                zl[z] = index[mem] if mem >= 0 else 0xFF
                zr[z] = role
                zb[z] = badge if badge >= 0 else 0xFF
        recs = b''
        for ri, r in enumerate(self.records):
            r = bytearray(r)
            for s in range(5):
                mid = struct.unpack_from('<H', r, s * 8 + 2)[0]
                if struct.unpack_from('<H', r, s * 8)[0] != 0xFFFF and mid:
                    struct.pack_into('<H', r, s * 8 + 2, text_base + mid - 1)
            prop = m['props'].get(str(ri + 1))
            r[0x32] = prop + 1 if r[0x32] and prop is not None else 0
            r[0x33] = 0     # Shiny Leaf records are never selected
            recs += bytes(r)
        motions = b''.join(mo.ljust(MOTION, b'\xff')[:MOTION] for mo in self.motions)
        species = bytearray(self.groups[:493])
        for s, g in sorted(m['species'].items(), key=lambda x: int(x[0])):
            s = int(s)
            species += bytes(s - 1 - len(species)) if len(species) < s - 1 else b''
            species.append(g)
        parts = [recs, motions, generic, lists, bytes(zl), bytes(zr), bytes(zb), bytes(species)]
        hdr_len = 4 * (len(parts) + 2)
        out, ofs = b'', []
        for p in parts:
            ofs.append(hdr_len + len(out))
            out += p + bytes(-len(p) % 4)
        return struct.pack(f'<{len(parts) + 2}I', *ofs, nzones, len(species)) + out
