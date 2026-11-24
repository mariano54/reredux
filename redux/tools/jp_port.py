"""Japanese Blaze Black 2 Redux: Redux (built on the US Black 2) with the Japanese Black 2's text, fonts and
text graphics.

Redux's code, data and scripts stay as they are (so everything Redux and the followers do keeps
working); what the player reads comes from the Japanese ROM: every text line Redux didn't touch is
the official Japanese (kanji) line, every line Redux added or changed is translated (work items
from `extract`, filled in by translators), and graphics/fonts that differ between the US and
Japanese releases are taken from the Japanese ROM unless Redux edited them.

    python3 jp_port.py extract US.nds JP.nds REDUX.nds WORKDIR    # -> WORKDIR/todo/*.json, glossary
    python3 jp_port.py build US.nds JP.nds REDUX.nds WORKDIR OUT.nds   # WORKDIR/tr/*.json -> ROM

Text banks (a/0/0/3 story, a/0/0/2 system): Japanese banks hold two sections (hiragana, kanji);
the US code reads one, so the result has the kanji one. Story banks line up with the US ones
(same ids); system banks too, except the alphabetical word dictionaries 113-157 (kept: the US
name-entry code searches them) and the English grammar banks 480-494, rebuilt from the Japanese
name banks they derive from.
"""
import json, os, re, struct, sys
import gen5text, ndsfs, romtool

SYS, STORY = 'a/0/0/2', 'a/0/0/3'
DICT_BANKS = range(113, 158)                 # US alphabetical dictionaries: keep English
KEEP_BANKS = {SYS: {369}, STORY: set()}      # staff credits (Redux adds its own; JP's are romaji too)
# US-only grammar banks -> the plain-name bank they are made from (Japanese has no articles/plurals)
GRAMMAR = {481: 64, 482: 64, 483: 90, 484: 93, 485: 383, 486: 90, 487: 374, 488: 403, 489: 398}
TRANSLATE_BANKS = {480}                      # month abbreviations: no Japanese bank to take them from
JP_DEX_BANKS = range(490, 495)               # the US game's own Japanese Pokédex text
# Pokédex labels (system 441): the Japanese bank has 2 lines fewer at its end (no Japanese height /
# weight label for foreign entries), so the DP alignment shifted the seasons and the per-language
# labels the US code indexes (a foreign entry's page read "ALT." / "몸무게"). Fixed map, US line -> what:
# 191-195 seasons, ??? (Japanese, same lines); 196-209 the per-language labels (US: they name the
# entry's language, Japanese たかさ / おもさ included); 210 "View Details" (Japanese 208).
DEX_LABELS = {(SYS, 441): {**{i: ('jp', i) for i in range(191, 196)}, **{i: ('keep', None) for i in range(196, 210)},
                           210: ('jp', 208)}}

BATCH = 220                                  # translation work items per file
TAG = re.compile(r'\{(?!U\+FFFF)[0-9A-F]{4}(?::[0-9,]*)?\}')
PAD = re.compile(r'(\{U\+FFFF\})+$')


def arc(rom, path):
    return next(f for f, p in rom.paths.items() if p == path)


def banks(rom, path, section=0):
    return [[t for t, _ in gen5text.decode(b)[section]] for b in ndsfs.narc(rom.file(arc(rom, path)))]


def blank(t):
    return not PAD.sub('', t).strip()


def skeleton(t):
    return tuple(sorted(TAG.findall(t)))


def plain(t):
    """Readable form of a line: trainer names are stored compressed (0xF100 + 9-bit packed chars)."""
    t = PAD.sub('', t)
    if not t.startswith('{U+F100}'):
        return t
    out, acc, bits = [], 0, 0
    for c in gen5text.text_to_chars(t)[1:]:
        acc |= c << bits
        bits += 16
        while bits >= 9:
            v = acc & 0x1FF
            if v == 0x1FF:
                return ''.join(map(chr, out))
            out.append(v)
            acc >>= 9
            bits -= 9
    return ''.join(map(chr, out))


def align(us, jp):
    """DP line alignment of two versions of a bank -> {us index: jp index}."""
    if len(us) == len(jp):
        return {i: i for i in range(len(us))}
    n, m = len(us), len(jp)
    NEG = -1e9
    dp = [[NEG] * (m + 1) for _ in range(n + 1)]
    bt = [[None] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0
    for i in range(n + 1):
        for j in range(m + 1):
            v = dp[i][j]
            if v == NEG:
                continue
            if i < n and j < m:
                s = 1.0 if skeleton(us[i]) == skeleton(jp[j]) else 0.2
                s += 0.5 if blank(us[i]) == blank(jp[j]) else -0.5
                if v + s > dp[i + 1][j + 1]:
                    dp[i + 1][j + 1], bt[i + 1][j + 1] = v + s, 'M'
            if i < n and v - 0.3 > dp[i + 1][j]:
                dp[i + 1][j], bt[i + 1][j] = v - 0.3, 'U'
            if j < m and v - 0.3 > dp[i][j + 1]:
                dp[i][j + 1], bt[i][j + 1] = v - 0.3, 'J'
    i, j, out = n, m, {}
    while i or j:
        t = bt[i][j]
        if t == 'M':
            i, j = i - 1, j - 1
            out[i] = j
        elif t == 'U':
            i -= 1
        else:
            j -= 1
    return out


class Port:
    def __init__(self, us, jp, rx):
        self.us, self.jp, self.rx = (ndsfs.Rom(p) for p in (us, jp, rx))
        self.text = {}
        for a in (SYS, STORY):
            self.text[a] = (banks(self.us, a), banks(self.rx, a),
                            [[t for t, _ in gen5text.decode(b)[-1]] for b in ndsfs.narc(self.jp.file(arc(self.jp, a)))])

    def reuse(self, a):
        """English line (plain) -> official Japanese line, from lines of aligned vanilla banks:
        {bank: {en: jp}} and the arc-wide first occurrence under None."""
        van, red, jpb = self.text[a]
        per = {None: {}}
        for b in range(min(len(van), len(jpb))):
            if a == SYS and (b in DICT_BANKS or b >= 480) or b in KEEP_BANKS[a]:
                continue
            m = align(van[b], jpb[b])
            d = per.setdefault(b, {})
            for i, j in m.items():
                e = plain(van[b][i])
                if e and not blank(jpb[b][j]):
                    d.setdefault(e, jpb[b][j])
                    per[None].setdefault(e, jpb[b][j])
        return per

    def plan(self, a):
        """-> per bank: list of ('jp', text) / ('keep', text) / ('tr', key) / ('derive', bank)"""
        van, red, jpb = self.text[a]
        reuse = self.reuse(a)
        out = []
        for b in range(len(red)):
            if a == SYS and (b in DICT_BANKS or b in JP_DEX_BANKS) or b in KEEP_BANKS[a]:
                out.append([('keep', t) for t in red[b]])
                continue
            if a == SYS and b in GRAMMAR:
                out.append([('derive', (GRAMMAR[b], i)) for i in range(len(red[b]))])
                continue
            v = van[b] if b < len(van) else []
            j = jpb[b] if b < len(jpb) and not (a == SYS and b in TRANSLATE_BANKS) else []
            m = align(v, j) if j else {}
            row = []
            fixed = DEX_LABELS.get((a, b), {})
            for i, t in enumerate(red[b]):
                if i in fixed and t == v[i]:
                    kind, k = fixed[i]
                    row.append(('keep', t) if kind == 'keep' else ('jp', j[k]))
                    continue
                if blank(t):
                    row.append(('keep', t))
                elif i < len(v) and t == v[i] and i in m:
                    row.append(('jp', j[m[i]]))
                elif plain(t) in reuse.get(b, {}):
                    row.append(('jp', reuse[b][plain(t)]))    # same line elsewhere in the bank
                elif len(plain(t)) >= 12 and plain(t) in reuse[None]:
                    row.append(('jp', reuse[None][plain(t)]))  # a sentence the game has elsewhere
                else:
                    row.append(('tr', f'{a[-1]}:{b}:{i}'))
            out.append(row)
        return out

    def glossary(self):
        """English -> official Japanese for short single-line entries of the aligned system banks."""
        van, red, jpb = self.text[SYS]
        g = {}
        for b in range(min(len(van), 480)):
            if b in DICT_BANKS or len(van[b]) != len(jpb[b]):
                continue
            for e, j in zip(van[b], jpb[b]):
                e2, j2 = PAD.sub('', e).strip(), PAD.sub('', j).strip()
                if e2 and j2 and len(e2) <= 24 and '\\n' not in e2 and '{' not in e2 and not e2.isdigit():
                    g.setdefault(e2, j2)
        return g


def cmd_extract(us, jp, rx, work):
    p = Port(us, jp, rx)
    os.makedirs(os.path.join(work, 'todo'), exist_ok=True)
    gl = p.glossary()
    terms = sorted(gl, key=len, reverse=True)
    json.dump(gl, open(os.path.join(work, 'glossary.json'), 'w'), ensure_ascii=False, indent=0)
    total = 0
    for a in (STORY, SYS):
        van, red, jpb = p.text[a]
        items = []
        for b, row in enumerate(p.plan(a)):
            for i, (kind, val) in enumerate(row):
                if kind != 'tr':
                    continue
                en = plain(red[b][i])
                it = {'id': val, 'en': en}
                if i < len(van[b]) and van[b][i] != red[b][i] and not blank(van[b][i]):
                    it['vanilla_en'] = plain(van[b][i])
                    if b < len(jpb) and i < len(jpb[b]) and len(van[b]) == len(jpb[b]):
                        it['vanilla_ja'] = PAD.sub('', jpb[b][i])
                ctx = [red[b][k] for k in (i - 1, i + 1) if 0 <= k < len(red[b]) and not blank(red[b][k])]
                it['context_en'] = ctx
                found = []
                for t in terms:
                    if len(t) >= 3 and not t.isupper() and t in en and not any(t in f for f, _ in found) \
                            and re.search(r'(?<![A-Za-z])' + re.escape(t) + r'(?![a-z])', en):
                        found.append((t, gl[t]))
                    if len(found) >= 12:
                        break
                it['terms'] = found
                items.append(it)
        total += len(items)
        k = 0
        for k in range(0, (len(items) + BATCH - 1) // BATCH):   # in game order, BATCH lines each
            json.dump(items[k * BATCH:(k + 1) * BATCH], open(os.path.join(work, 'todo', f'{a[-1]}_{k:02d}.json'), 'w'),
                      ensure_ascii=False, indent=1)
        print(a, len(items), 'lines to translate in', k + 1, 'batches')
    print('total', total, 'glossary', len(gl))


# ------------------------------------------------------------------------------------------ build

# Files the two releases differ in that Redux didn't touch, kept from Redux (= US): they are not
# what the player reads, or the US code depends on their layout.
KEEP_US = {
    'a/0/0/4',      # Pokémon sprites (7 regional touch-ups)
    'a/0/0/6',      # US-tuned data (1 byte in 201 members)
    'a/0/7/1',      # trainer sprites
    'a/1/1/2', 'a/1/1/3', 'a/1/1/4', 'a/1/1/5',   # screen layouts the US code builds on
    'a/2/1/5', 'a/2/2/5', 'a/2/6/9',
    'a/2/2/1',      # opening movie (a stub in the US game, which doesn't play it)
    'swan_sound_data.sdat',
    'dl_rom/child_r.srl', 'dl_rom/child2_r.srl',
}
# Archives both releases and Redux changed (or whose member counts differ, a/1/5/7): member by member
# (matched by member_map), Japanese members only where Redux kept the US one; (arc, member) -> how to
# combine the three versions
TILE_SPLICE = {('a/0/8/2', 51), ('a/1/2/5', 23)}     # type labels: Japanese sheet, Japanese Fairy label
MEMBER_MERGE = {'a/0/1/1', 'a/0/2/6', 'a/0/8/2', 'a/0/9/4', 'a/1/2/5', 'a/1/5/7', 'a/1/5/9'}
# members that stay Redux's although Redux kept the US one: the title screen's background map (a/0/2/6 NSCR 3)
# indexes the tile sheet NCGR 0, which Redux redrew (its logo); the Japanese map is laid out for the Japanese
# sheet and showed garbled blocks behind the logo
KEEP_RX_MEMBERS = {('a/0/2/6', 3)}
ITEMS, TRADES = 'a/0/2/4', 'a/1/6/3'
ITEM_SORT, TRADE_LANG = 15, 88           # byte offsets: alphabetical sort index, Pokémon language


def member_map(nu, nj):
    """US archive members -> the Japanese members holding the same resource: {us index: jp index}.
    Same count: index for index. Otherwise one release has members the other lacks (a/1/5/7, the
    Pokédex graphics: the US one has a Japanese type-label sheet the Japanese one doesn't, so every
    later member sits one index lower in it), and the members are matched by a DP alignment on their
    format (NCGR/NCLR/NCER/NSCR... magic), size and content; unmatched US members keep the US data."""
    n, m = len(nu), len(nj)
    if n == m:
        return {i: i for i in range(n)}

    def score(a, b):
        if a == b:
            return 4.0
        if a[:4] != b[:4]:
            return None                          # different kind of resource: never the same member
        if len(a) != len(b):
            return 1.0
        return 2.0 + sum(x == y for x, y in zip(a, b)) / len(a)

    NEG = -1e9
    dp = [[NEG] * (m + 1) for _ in range(n + 1)]
    bt = [[None] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0
    for i in range(n + 1):
        for j in range(m + 1):
            v = dp[i][j]
            if v == NEG:
                continue
            if i < n and j < m:
                s = score(nu[i], nj[j])
                if s is not None and v + s > dp[i + 1][j + 1]:
                    dp[i + 1][j + 1], bt[i + 1][j + 1] = v + s, 'M'
            if i < n and v > dp[i + 1][j]:
                dp[i + 1][j], bt[i + 1][j] = v, 'U'
            if j < m and v > dp[i][j + 1]:
                dp[i][j + 1], bt[i][j + 1] = v, 'J'
    i, j, out = n, m, {}
    while i or j:
        t = bt[i][j]
        if t == 'M':
            i, j = i - 1, j - 1
            out[i] = j
        elif t == 'U':
            i -= 1
        else:
            j -= 1
    return out


def lz_decode(d):
    t, n = d[0], d[1] | d[2] << 8 | d[3] << 16
    out, i = bytearray(), 4
    while len(out) < n:
        flags = d[i]
        i += 1
        for b in range(8):
            if len(out) >= n:
                break
            if not flags & (0x80 >> b):
                out.append(d[i])
                i += 1
                continue
            if t == 0x10:
                x = d[i] << 8 | d[i + 1]
                i += 2
                ln, disp = (x >> 12) + 3, (x & 0xFFF) + 1
            else:
                h = d[i] >> 4
                if h == 0:
                    ln, disp = ((d[i] & 0xF) << 4 | d[i + 1] >> 4) + 0x11, ((d[i + 1] & 0xF) << 8 | d[i + 2]) + 1
                    i += 3
                elif h == 1:
                    ln = ((d[i] & 0xF) << 12 | d[i + 1] << 4 | d[i + 2] >> 4) + 0x111
                    disp = ((d[i + 2] & 0xF) << 8 | d[i + 3]) + 1
                    i += 4
                else:
                    ln, disp = h + 1, ((d[i] & 0xF) << 8 | d[i + 1]) + 1
                    i += 2
            for _ in range(ln):
                out.append(out[-disp])
    return bytes(out)


def lz10_encode(d):
    """Greedy LZ10 (the DS BIOS format)."""
    out = bytearray([0x10, len(d) & 0xFF, len(d) >> 8 & 0xFF, len(d) >> 16 & 0xFF])
    i = 0
    while i < len(d):
        flag_at = len(out)
        out.append(0)
        for b in range(8):
            if i >= len(d):
                break
            best, bdisp = 0, 0
            for disp in range(1, min(i, 0x1000) + 1):
                ln = 0
                while ln < 18 and i + ln < len(d) and d[i + ln] == d[i + ln - disp]:
                    ln += 1
                if ln > best:
                    best, bdisp = ln, disp
                    if ln == 18:
                        break
            if best >= 3:
                out[flag_at] |= 0x80 >> b
                x = (best - 3) << 12 | (bdisp - 1)
                out += bytes([x >> 8, x & 0xFF])
                i += best
            else:
                out.append(d[i])
                i += 1
    return bytes(out + bytes(-len(out) % 4))


# フェアリー, drawn for this port in the style of the Japanese type labels (1-pixel strokes, 7 pixels
# high, drop shadow right/below; エ's shape for the small ェ, ノ's for フ, ノーマル's ー). '#' = text pixel,
# placed at label rows 4-10 from column 2 inside the 30x12 frame (columns 1-30, rows 2-13).
FAIRY_JP = ('#####.......#####.#..#.....',
            '....#...........#.#..#.....',
            '....#.........##..#..#.....',
            '...#...###....#...#..#.####',
            '...#....#.....#......#.....',
            '..#.....#....#......#......',
            '##....#####.#.....##.......')
LABEL_W, LABEL_H = 32, 16                       # one label = 4x2 tiles, 1D-mapped (8 consecutive tiles)


def label_pixels(data, b):
    """Block b of a 4bpp label sheet -> 16 rows of 32 palette indices."""
    px = [[0] * LABEL_W for _ in range(LABEL_H)]
    for t in range(8):
        for k in range(64):
            px[t // 4 * 8 + k // 8][t % 4 * 8 + k % 8] = data[(b * 8 + t) * 32 + k // 2] >> 4 * (k & 1) & 0xF
    return px


def label_tiles(px):
    out = bytearray(8 * 32)
    for t in range(8):
        for k in range(64):
            out[t * 32 + k // 2] |= px[t // 4 * 8 + k // 8][t % 4 * 8 + k % 8] << 4 * (k & 1)
    return bytes(out)


def fairy_label(ref):
    """The Japanese Fairy label in the colours of Redux's English one (ref: its 16x32 indices):
    frame, background, text and shadow indices are read from it."""
    frame, fill = ref[2][16], ref[3][16]
    glyph = [ref[y][x] for y in range(4, 12) for x in range(2, 30) if ref[y][x] not in (frame, fill)]
    text = ref[4][next(x for x in range(2, 30) if ref[4][x] not in (frame, fill))]   # top-left stroke
    shadow = next(c for c in glyph if c != text)
    px = [[0] * LABEL_W for _ in range(LABEL_H)]
    for y in range(2, 14):
        for x in range(1, 31):
            px[y][x] = frame if y in (2, 13) or x in (1, 30) else fill
    on = {(x + 2, y + 4) for y, row in enumerate(FAIRY_JP) for x, c in enumerate(row) if c == '#'}
    for x, y in on:
        px[y][x] = text
        for sx, sy in ((x + 1, y), (x, y + 1), (x + 1, y + 1)):
            if (sx, sy) not in on and 2 <= sx <= 29 and 3 <= sy <= 12:
                px[sy][sx] = shadow
    return px


def fairy_tiles(jp, rx, us):
    """Japanese type-label NCGR, with every label block Redux changed or added (its English FAIRY
    label) replaced by the Japanese フェアリー in Redux's colours."""
    comp = jp[:1] in (b'\x10', b'\x11') and jp[4:8] != b'RGCN'
    J, R, U = (lz_decode(x) if comp else x for x in (jp, rx, us))
    assert J[:4] == R[:4] == U[:4] == b'RGCN' and len(J) == len(U), 'unexpected tile sheets'
    tile_ofs = struct.unpack_from('<H', J, 0xC)[0] + 0x20
    jt, rt, ut = J[tile_ofs:], R[tile_ofs:], U[tile_ofs:]
    out = bytearray(jt[:len(ut)] + rt[len(ut):])
    bs = LABEL_W * LABEL_H // 2
    assert len(rt) % bs == 0, 'label sheet is not made of 32x16 labels'
    changed = [b for b in range(len(rt) // bs) if rt[b * bs:(b + 1) * bs] != ut[b * bs:(b + 1) * bs]]
    for b in changed:
        out[b * bs:(b + 1) * bs] = label_tiles(fairy_label(label_pixels(rt, b)))
    out = R[:tile_ofs] + bytes(out)                    # Redux's headers (sizes, tile count)
    return lz10_encode(out) if comp else out


def cmd_build(us_p, jp_p, rx_p, work, out_p):
    p = Port(us_p, jp_p, rx_p)
    tr = {}
    for f in sorted(os.listdir(os.path.join(work, 'tr'))):
        if f.endswith('.json'):
            tr.update(json.load(open(os.path.join(work, 'tr', f))))
    pu, pj, pr = ({pa: f for f, pa in r.paths.items()} for r in (p.us, p.jp, p.rx))
    files = {}
    missing = 0
    for a in (STORY, SYS):
        raw = p.rx.file(pr[a])
        nar = ndsfs.narc(raw)
        plan = p.plan(a)
        final = []
        for b, row in enumerate(plan):
            lines = []
            for kind, val in row:
                if kind in ('jp', 'keep'):
                    lines.append(val)
                elif kind == 'tr':
                    if val in tr:
                        lines.append(tr[val])
                    else:
                        missing += 1
                        lines.append(p.text[a][1][b][len(lines)])     # English until translated
                else:
                    lines.append(None)
            final.append(lines)
        for b, lines in enumerate(final):                # grammar banks: the Japanese plain names
            for i, t in enumerate(lines):
                if t is None:
                    src, k = plan[b][i][1]
                    lines[i] = final[src][k] if k < len(final[src]) else p.text[a][1][b][i]
        out = []
        for b, lines in enumerate(final):
            secs = gen5text.decode(nar[b])
            flags = [f for _, f in secs[0]]
            out.append(gen5text.encode([list(zip(lines, flags))], struct.unpack_from('<I', nar[b], 8)[0],
                                       gen5text.padding(nar[b])))
        files[pr[a]] = ndsfs.pack_narc(out, ndsfs.narc_layout(raw))
    print('text: untranslated lines left in English:', missing)

    for path in sorted(set(pu) & set(pj) & set(pr)):
        if path in (STORY, SYS) or path in KEEP_US:
            continue
        du, dj, dr = p.us.file(pu[path]), p.jp.file(pj[path]), p.rx.file(pr[path])
        if du == dj:
            continue
        nu, nj, nr = ndsfs.narc(du), ndsfs.narc(dj), ndsfs.narc(dr)
        if dr == du and (nu is None or nj is None or len(nu) == len(nj)):
            files[pr[path]] = dj                         # language asset Redux didn't touch
            continue
        if nu is None or nj is None or nr is None:
            continue
        merged = list(nr)
        if path in MEMBER_MERGE:
            for i, j in member_map(nu, nj).items():
                if i >= len(nr) or (path, i) in KEEP_RX_MEMBERS:
                    continue
                if (path, i) in TILE_SPLICE:
                    merged[i] = fairy_tiles(nj[j], nr[i], nu[i])
                elif nr[i] == nu[i] and nj[j] != nu[i]:
                    merged[i] = nj[j]
        elif path in (ITEMS, TRADES):
            off = ITEM_SORT if path == ITEMS else TRADE_LANG
            for i in range(min(len(nu), len(nj), len(nr))):
                if len(nr[i]) > off and nr[i][off] == nu[i][off] and nj[i][off] != nu[i][off]:
                    m = bytearray(nr[i])
                    m[off] = nj[i][off]
                    merged[i] = bytes(m)
        else:
            continue                                     # Redux's version (data, scripts, maps)
        if merged != nr:
            files[pr[path]] = ndsfs.pack_narc(merged, ndsfs.narc_layout(dr))
    print('files replaced or merged:', len(files))
    rom = romtool.build(rx_p, files=files)
    open(out_p, 'wb').write(rom)
    print('wrote', out_p)


if __name__ == '__main__':
    if sys.argv[1] == 'extract':
        cmd_extract(*sys.argv[2:6])
    elif sys.argv[1] == 'build':
        cmd_build(*sys.argv[2:7])
    else:
        sys.exit(__doc__)
