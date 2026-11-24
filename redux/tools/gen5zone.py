"""Zone entities (a/1/2/6, ARCID_ZONE_ENTITIES) <-> JSON, lossless. Layout from swan
field/field_eventdata.h; the zone header's u16 @0x16 selects the entity file.

  u32 init_offset (= end of the entity arrays - 4 in vanilla), u8 counts[4]
  furniture[n]  20 B: u16 script, condition, interactibility, is_rail; s32 x, z, y
  npcs[n]       36 B: u16 uid, model, move_code, ev_type, spawn_flag, script, direction,
                      param0..2, area_w, area_h; u32 is_rail;
                      grid: u16 x, u16 z, s32 y   |  rail: s16 line, front, side, pad
  warps[n]      20 B: u16 dest_zone, dest_warp; u8 direction, transition; u16 is_rail,
                      x; s16 y; u16 z, w, h, unk
  triggers[n]   22 B: u16 script, value, var, unk6, unk8, x, z, w, h; s16 y; u16 unk
  tail          everything after the arrays (init-script conditions), kept as hex
`dest_zone_name` in warps is informational and ignored when encoding.
"""
import struct

FURN = ('<HHHHiii', ('script', 'condition', 'interactibility', 'is_rail', 'x', 'z', 'y'))
NPC = ('<HHHHHHHHHHHHI', ('uid', 'model', 'move_code', 'ev_type', 'spawn_flag', 'script', 'direction',
                          'param0', 'param1', 'param2', 'area_w', 'area_h', 'is_rail'))
WARP = ('<HHBBHHhHHHH', ('dest_zone', 'dest_warp', 'direction', 'transition', 'is_rail', 'x', 'y', 'z',
                         'w', 'h', 'unk'))
TRIG = ('<HHHHHHHHHhH', ('script', 'value', 'var', 'unk6', 'unk8', 'x', 'z', 'w', 'h', 'y', 'unk'))
SIZES = (20, 36, 20, 22)


def decode(d, zone_names=None):
    if len(d) < 8:
        return {'_raw': d.hex()}
    off, nf, nn, nw, nt = struct.unpack_from('<IBBBB', d, 0)
    if 8 + sum(n * s for n, s in zip((nf, nn, nw, nt), SIZES)) > len(d):
        return {'_raw': d.hex(), '_note': 'counts exceed file size (as shipped); kept verbatim'}
    q, out = 8, {}

    def take(fmt, names, n):
        nonlocal q
        items = []
        for _ in range(n):
            items.append(dict(zip(names, struct.unpack_from(fmt, d, q))))
            q += struct.calcsize(fmt)
        return items

    out['furniture'] = take(*FURN, nf)
    npcs = []
    for _ in range(nn):
        e = dict(zip(NPC[1], struct.unpack_from(NPC[0], d, q)))
        p = q + 28
        if e['is_rail']:
            e['rail'] = dict(zip(('line', 'front', 'side', 'pad'), struct.unpack_from('<hhhh', d, p)))
        else:
            e['grid'] = dict(zip(('x', 'z', 'y'), struct.unpack_from('<HHi', d, p)))
        npcs.append(e)
        q += 36
    out['npcs'] = npcs
    out['warps'] = take(*WARP, nw)
    if zone_names:
        for w in out['warps']:
            if w['dest_zone'] < len(zone_names):
                w['dest_zone_name'] = zone_names[w['dest_zone']]
    out['triggers'] = take(*TRIG, nt)
    if off != q - 4:
        out['init_offset'] = off           # only when it is not the usual "end of arrays - 4"
    out['tail'] = d[q:].hex()
    return out


def decode_matrix(d):
    """Map matrix (a/0/0/9): u32 has_zones, u16 width, u16 height, u32 map model id per cell
    (0xFFFFFFFF = empty), then (if has_zones) u16 zone id per cell. Rows are lists."""
    if len(d) < 8:
        return {'_raw': d.hex()}
    kind, w, h = struct.unpack_from('<IHH', d, 0)
    n = w * h
    need = 8 + 4 * n + (2 * n if kind else 0)
    if kind not in (0, 1) or len(d) < need:
        return {'_raw': d.hex()}
    maps = list(struct.unpack_from(f'<{n}I', d, 8))
    out = dict(width=w, height=h, maps=[[None if v == 0xFFFFFFFF else v for v in maps[r * w:(r + 1) * w]]
                                        for r in range(h)])
    if kind:
        zones = list(struct.unpack_from(f'<{n}H', d, 8 + 4 * n))
        out['zones'] = [zones[r * w:(r + 1) * w] for r in range(h)]
    if len(d) > need:
        out['tail'] = d[need:].hex()
    return out


def encode_matrix(m):
    if '_raw' in m:
        return bytes.fromhex(m['_raw'])
    w, h = m['width'], m['height']
    b = struct.pack('<IHH', 1 if 'zones' in m else 0, w, h)
    b += b''.join(struct.pack('<I', 0xFFFFFFFF if v is None else v) for row in m['maps'] for v in row)
    if 'zones' in m:
        b += b''.join(struct.pack('<H', v) for row in m['zones'] for v in row)
    return b + bytes.fromhex(m.get('tail', ''))


def encode(e):
    if '_raw' in e:
        return bytes.fromhex(e['_raw'])
    body = b''
    for f in e['furniture']:
        body += struct.pack(FURN[0], *[f[k] for k in FURN[1]])
    for n in e['npcs']:
        body += struct.pack(NPC[0], *[n[k] for k in NPC[1]])
        body += (struct.pack('<hhhh', *[n['rail'][k] for k in ('line', 'front', 'side', 'pad')]) if n['is_rail']
                 else struct.pack('<HHi', *[n['grid'][k] for k in ('x', 'z', 'y')]))
    for w in e['warps']:
        body += struct.pack(WARP[0], *[w[k] for k in WARP[1]])
    for t in e['triggers']:
        body += struct.pack(TRIG[0], *[t[k] for k in TRIG[1]])
    off = e.get('init_offset', 8 + len(body) - 4)
    head = struct.pack('<IBBBB', off, len(e['furniture']), len(e['npcs']), len(e['warps']), len(e['triggers']))
    return head + body + bytes.fromhex(e['tail'])
