"""Gen 5 (B2/W2) data tables <-> JSON, lossless (encode(decode(x)) == x, checked by export_data.py).

Trainers   a/0/9/1 (trdata, 20 B; Redux also has 18 B records) + a/0/9/2 (party):
           trdata: u8 format (bit0 moves, bit1 held items), u8 class, u8 battle type, u8 party size,
                   u16 items[4], u32 AI flags, u8 heal, u8 money, [u16 prize item]
           party mon: u8 IV, u8 ability/gender, u8 level, u8 pad, u16 species, u16 form,
                      [u16 held item], [u16 moves[4]]
Encounters a/1/2/7: one or four seasons of 232 B: u8 rates[8] (grass, grass doubles, grass special,
           surf, surf special, fishing, fishing special, pad) + 56 slots of
           (u16 species | form << 11, u8 min level, u8 max level).
Names come from system text: species 0090, moves 0403, items 0064, trainer classes 0383,
trainer names 0382 (9-bit compressed strings).
"""
import struct
import gen5text as G

ENC_GROUPS = [('grass', 12), ('grass_doubles', 12), ('grass_special', 12), ('surf', 5),
              ('surf_special', 5), ('fishing', 5), ('fishing_special', 5)]


def _decompress9(chars):
    """0xF100 + bit-packed 9-bit chars (LSB first), terminated by 0x1FF."""
    bits, nbits, out = 0, 0, []
    for c in chars[1:]:
        bits |= c << nbits
        nbits += 16
        while nbits >= 9:
            v = bits & 0x1FF
            bits >>= 9
            nbits -= 9
            if v == 0x1FF:
                return ''.join(out)
            out.append(chr(v))
    return ''.join(out)


def name_list(bank_bytes):
    out = []
    for text, _ in G.decode(bank_bytes)[0]:
        chars = G.text_to_chars(text)
        if chars and chars[0] == 0xF100:
            out.append(_decompress9(chars))
        else:
            out.append(text)
    return out


class Names:
    def __init__(self, system_banks):
        b = system_banks
        self.species = name_list(b[90])
        self.moves = name_list(b[403])
        self.items = name_list(b[64])
        self.tclass = name_list(b[383])
        self.tname = name_list(b[382])

    @staticmethod
    def _fwd(table, i):
        if 0 <= i < len(table) and table.count(table[i]) == 1 and table[i]:
            return table[i]
        return f'#{i}'

    @staticmethod
    def _rev(table, v):
        if isinstance(v, int):
            return v
        if v.startswith('#'):
            return int(v[1:])
        return table.index(v)

    def sp(self, i): return self._fwd(self.species, i)
    def mv(self, i): return self._fwd(self.moves, i)
    def it(self, i): return self._fwd(self.items, i)
    def sp_id(self, v): return self._rev(self.species, v)
    def mv_id(self, v): return self._rev(self.moves, v)
    def it_id(self, v): return self._rev(self.items, v)


# ---- trainers -------------------------------------------------------------------------------------
def decode_trainers(trdata, trpoke, names):
    out = []
    for i, (td, tp) in enumerate(zip(trdata, trpoke)):
        if len(td) < 18:      # empty/odd record: keep verbatim
            out.append(dict(id=i, _raw_trdata=td.hex(), _raw_party=tp.hex()))
            continue
        fmt, cls, battle, count = td[0], td[1], td[2], td[3]
        items = list(struct.unpack_from('<4H', td, 4))
        ai = struct.unpack_from('<I', td, 12)[0]
        t = dict(id=i, name=names.tname[i] if i < len(names.tname) else '', format=fmt,
                 trainer_class=names._fwd(names.tclass, cls), battle_type=battle, party_size=count,
                 items=[names.it(x) for x in items], ai=ai, heal=td[16], money=td[17])
        if len(td) >= 20:
            t['prize'] = names.it(struct.unpack_from('<H', td, 18)[0])
        if len(td) not in (18, 20):
            t['_trdata_tail'] = td[20:].hex() if len(td) > 20 else None
            t['_trdata_len'] = len(td)
        per = 8 + (2 if fmt & 2 else 0) + (8 if fmt & 1 else 0)
        party = []
        for k in range(count):
            m = tp[k * per:(k + 1) * per]
            if len(m) < per:
                break
            iv, abil, lvl, pad, sp, form = struct.unpack_from('<BBBBHH', m, 0)
            mon = dict(species=names.sp(sp), level=lvl, iv=iv, ability_gender=abil, form=form)
            if pad:
                mon['pad'] = pad
            q = 8
            if fmt & 2:
                mon['item'] = names.it(struct.unpack_from('<H', m, q)[0])
                q += 2
            if fmt & 1:
                mon['moves'] = [names.mv(x) for x in struct.unpack_from('<4H', m, q)]
            party.append(mon)
        t['party'] = party
        if len(tp) != count * per:
            t['_party_extra'] = tp[count * per:].hex() if len(tp) > count * per else None
            t['_party_len'] = len(tp)
        out.append(t)
    return out


def encode_trainers(trainers, names):
    trdata, trpoke = [], []
    for t in trainers:
        if '_raw_trdata' in t:
            trdata.append(bytes.fromhex(t['_raw_trdata']))
            trpoke.append(bytes.fromhex(t['_raw_party']))
            continue
        td = struct.pack('<BBBB', t['format'], names._rev(names.tclass, t['trainer_class']), t['battle_type'],
                         t['party_size'])
        td += struct.pack('<4H', *[names.it_id(x) for x in t['items']])
        td += struct.pack('<IBB', t['ai'], t['heal'], t['money'])
        if 'prize' in t:
            td += struct.pack('<H', names.it_id(t['prize']))
        if t.get('_trdata_tail'):
            td += bytes.fromhex(t['_trdata_tail'])
        tp = b''
        for mon in t['party']:
            tp += struct.pack('<BBBBHH', mon['iv'], mon['ability_gender'], mon['level'], mon.get('pad', 0),
                              names.sp_id(mon['species']), mon['form'])
            if t['format'] & 2:
                tp += struct.pack('<H', names.it_id(mon['item']))
            if t['format'] & 1:
                tp += struct.pack('<4H', *[names.mv_id(x) for x in mon['moves']])
        if t.get('_party_extra'):
            tp += bytes.fromhex(t['_party_extra'])
        if '_party_len' in t:
            tp = tp[:t['_party_len']]
        trdata.append(td)
        trpoke.append(tp)
    return trdata, trpoke


# ---- encounters -----------------------------------------------------------------------------------
def decode_encounters(tables, names):
    out = []
    for i, d in enumerate(tables):
        seasons = []
        for s in range(0, len(d), 232):
            blk = d[s:s + 232]
            rates = list(blk[:8])
            sea = dict(rates=dict(zip([g for g, _ in ENC_GROUPS] + ['pad'], rates)))
            q = 8
            for g, cnt in ENC_GROUPS:
                slots = []
                for _ in range(cnt):
                    v, lo, hi = struct.unpack_from('<HBB', blk, q)
                    q += 4
                    slot = [names.sp(v & 0x7FF), lo, hi]
                    if v >> 11:
                        slot.append(v >> 11)    # form
                    slots.append(slot)
                sea[g] = slots
            seasons.append(sea)
        out.append(dict(id=i, seasons=seasons))
    return out


def encode_encounters(tables, names):
    out = []
    for t in tables:
        b = b''
        for sea in t['seasons']:
            b += bytes(sea['rates'][g] for g in [g for g, _ in ENC_GROUPS] + ['pad'])
            for g, cnt in ENC_GROUPS:
                for slot in sea[g]:
                    form = slot[3] if len(slot) > 3 else 0
                    b += struct.pack('<HBB', names.sp_id(slot[0]) | form << 11, slot[1], slot[2])
        out.append(b)
    return out


# ---- Pokémon personal data (76 B) ---------------------------------------------------------------
PERSONAL = [('hp', 'B'), ('atk', 'B'), ('def', 'B'), ('spe', 'B'), ('spa', 'B'), ('spd', 'B'),
            ('type1', 'B'), ('type2', 'B'), ('catch_rate', 'B'), ('stage', 'B'), ('ev_yield', 'H'),
            ('item1', 'H'), ('item2', 'H'), ('item3', 'H'), ('gender', 'B'), ('hatch_cycles', 'B'),
            ('friendship', 'B'), ('growth', 'B'), ('egg_group1', 'B'), ('egg_group2', 'B'),
            ('ability1', 'B'), ('ability2', 'B'), ('ability_hidden', 'B'), ('flee', 'B'),
            ('form_stats', 'H'), ('form_sprite', 'H'), ('form_count', 'B'), ('color', 'B'),
            ('base_exp', 'H'), ('height', 'H'), ('weight', 'H')]
PFMT = '<' + ''.join(t for _, t in PERSONAL)
PSIZE = struct.calcsize(PFMT)   # 0x28; then TM/HM bits (16 B), type tutors (u32), special tutors (16 B)


def decode_personal(entries, names, types):
    out = []
    for i, d in enumerate(entries):
        if len(d) != 76:
            out.append(dict(id=i, _raw=d.hex()))
            continue
        vals = struct.unpack_from(PFMT, d, 0)
        e = dict(id=i, name=names.sp(i) if i < len(names.species) else f'#{i}')
        for (k, _), v in zip(PERSONAL, vals):
            if k in ('type1', 'type2'):
                v = types[v] if v < len(types) else f'#{v}'
            elif k.startswith('item'):
                v = names.it(v)
            e[k] = v
        e['tm_hm'] = d[0x28:0x38].hex()
        e['type_tutors'] = d[0x38:0x3C].hex()
        e['tutors'] = d[0x3C:0x4C].hex()
        out.append(e)
    return out


def encode_personal(entries, names, types):
    out = []
    for e in entries:
        if '_raw' in e:
            out.append(bytes.fromhex(e['_raw']))
            continue
        vals = []
        for k, _ in PERSONAL:
            v = e[k]
            if k in ('type1', 'type2'):
                v = int(v[1:]) if isinstance(v, str) and v.startswith('#') else (types.index(v) if isinstance(v, str) else v)
            elif k.startswith('item'):
                v = names.it_id(v)
            vals.append(v)
        out.append(struct.pack(PFMT, *vals) + bytes.fromhex(e['tm_hm'] + e['type_tutors'] + e['tutors']))
    return out


# ---- learnsets / evolutions -----------------------------------------------------------------------
def decode_learnsets(entries, names):
    out = []
    for i, d in enumerate(entries):
        moves, q = [], 0
        while q + 4 <= len(d):
            mv, lvl = struct.unpack_from('<HH', d, q)
            q += 4
            if mv == 0xFFFF and lvl == 0xFFFF:
                break
            moves.append([lvl, names.mv(mv)])
        e = dict(id=i, name=names.sp(i) if i < len(names.species) else f'#{i}', moves=moves)
        if d[q:]:
            e['_tail'] = d[q:].hex()
        if q > len(d) or (q == len(d) and not (len(d) >= 4 and d[-4:] == b'\xff' * 4)):
            e['_no_term'] = True
        out.append(e)
    return out


def encode_learnsets(entries, names):
    out = []
    for e in entries:
        b = b''.join(struct.pack('<HH', names.mv_id(m), lvl) for lvl, m in e['moves'])
        if not e.get('_no_term'):
            b += b'\xff' * 4
        b += bytes.fromhex(e.get('_tail', ''))
        out.append(b)
    return out


def decode_evolutions(entries, names):
    out = []
    for i, d in enumerate(entries):
        evos = []
        for k in range(0, len(d) - len(d) % 6, 6):
            method, param, target = struct.unpack_from('<HHH', d, k)
            if method or param or target:
                evos.append([method, param, names.sp(target), k // 6])
        out.append(dict(id=i, name=names.sp(i), size=len(d), evolutions=evos))
    return out


def encode_evolutions(entries, names):
    out = []
    for e in entries:
        b = bytearray(e['size'])
        for method, param, target, slot in e['evolutions']:
            struct.pack_into('<HHH', b, slot * 6, method, param, names.sp_id(target))
        out.append(bytes(b))
    return out


# ---- moves / items (well-known fields decoded, rest kept as hex) --------------------------------
MOVE = [('type', 'B'), ('effect_category', 'B'), ('category', 'B'), ('power', 'B'), ('accuracy', 'B'),
        ('pp', 'B'), ('priority', 'b')]
MFMT = '<' + ''.join(t for _, t in MOVE)


def decode_moves(entries, names, types):
    out = []
    for i, d in enumerate(entries):
        e = dict(id=i, name=names.mv(i))
        for (k, _), v in zip(MOVE, struct.unpack_from(MFMT, d, 0)):
            e[k] = (types[v] if v < len(types) else f'#{v}') if k == 'type' else v
        e['_rest'] = d[struct.calcsize(MFMT):].hex()
        out.append(e)
    return out


def encode_moves(entries, names, types):
    out = []
    for e in entries:
        vals = []
        for k, _ in MOVE:
            v = e[k]
            if k == 'type':
                v = int(v[1:]) if isinstance(v, str) and v.startswith('#') else types.index(v)
            vals.append(v)
        out.append(struct.pack(MFMT, *vals) + bytes.fromhex(e['_rest']))
    return out


def decode_items(entries, names):
    return [dict(id=i, name=names.it(i), price=struct.unpack_from('<H', d, 0)[0] * 10 if len(d) >= 2 else None,
                 _rest=d[2:].hex()) for i, d in enumerate(entries)]


def encode_items(entries, names):
    return [struct.pack('<H', e['price'] // 10) + bytes.fromhex(e['_rest']) if e['price'] is not None
            else bytes.fromhex(e['_rest']) for e in entries]
