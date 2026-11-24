"""ReRedux statview (statview.c): IVs and EVs as two columns to the right of the stats on the summary's stats page
(party and PC summaries, overlay 207; not used in battle): stat name | stat | IV | EV, the HP row as a compact
"cur/max". SELECT on that page toggles the Ability box between the ability and the totals (IV total, Hidden Power's
type, EV total and what's left of 510). Values: PokeParty_GetParam on the Pokémon the page shows. Hook sites from
pokeblack2 asm/overlay_207.s (StatsDraw 0x021B8F10, app key handler 0x021B400C, app init 0x021B2F80).

Graphics (files): the stats page's panel (a/0/7/7: NCGR 12, NSCR 75) loses its cut top-right corner, so every row
runs to the screen edge, and the dark band above it gets the column headers ("IV" / "EV", JP 個体値 / 努力値) in
the game's small font (a/0/2/3 font 1) in the stat names' white. The six row windows (overlay 207's window table)
are widened from 14 / 16 tiles to 23 (to x 248, past the EV column's right edge 242). Not 24: the page's 13 windows
share the top text layer's char area (frame 4: 0x6000 bytes, 768 tiles) and 24-tile rows needed 774, so the last
window (the move description, 96 tiles) was never created (NULL) and the page's hide freed a NULL window: a data abort
on hardware and in melonDS (DeSmuME has no MPU and read on). With 23: 762 tiles."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))

SYMS = {
    'sv_KeyTrg': 0x0203DEFD,        # ARM9 GCTX_HIDGetPressedKeys (trigger)
    'sv_KeyMode': 0x0203D555,       # ARM9 key/touch mode getter (called by the app init)
    'sv_WsCreate': 0x020241D5,      # ARM9 GFL_WordSetSystemCreateDefault(heap)
    'sv_WsFree': 0x02024275,        # ARM9 GFL_WordSetSystemFree
    'sv_WsNumber': 0x0202451D,      # ARM9 WordSetNumber(ws, idx, value, digits, style, code)
    'sv_WsBankWord': 0x02024341,    # ARM9 word set: register line `id` of system bank `bank`
    'sv_PrintQue': 0x02021C7D,      # ARM9 print queue: (que, bmp, x, y, str, font, color)
    'sv_CurPP': 0x021B4DDD,         # OVL_207 the shown Pokémon (PokeParty; PC ones converted)
    'sv_StatsDraw': 0x021B8F11,     # OVL_207 stats page text
    'sv_Keys': 0x021B400D,          # OVL_207 key handler (UP/DOWN Pokémon, LEFT/RIGHT page, B, X, Y)
    'sv_PageRedraw': 0x021B49D1,    # OVL_207 recreate the page (as after UP/DOWN)
    'sv_PrintMsg': 0x021B4EC5,      # OVL_207 (app, win, msg, x, y, color): bank 179 line
    'sv_PrintWsRight': 0x021B5041,  # OVL_207 (app, win, ws, msg, x, y, color): expanded, right-aligned
    'sv_StrBufCreate': 0x02048531,  # ARM9 GFL_StrBufCreate(len, heap)
    'sv_StrBufFree': 0x02048565,    # ARM9 GFL_StrBufFree
    'sv_MsgLoad': 0x0204898D,       # ARM9 GFL_MsgDataLoadStrbufNew(msgdata, id)
    'sv_WsFormat': 0x02024921,      # ARM9 GFL_WordSetFormatStrbuf(ws, dst, src)
}

SUMMARY_BANK = 179                  # the summary's message bank (the app's msg data)
# word set: 0 IV total, 1 Hidden Power type, 2 EV total, 3 EVs left of 510
TEXTS = [
    dict(bank=('system', SUMMARY_BANK), key='SV_TOTALS', en='Totals', ja='ごうけい'),
    dict(bank=('system', SUMMARY_BANK), key='SV_TOTALS_NAME', en='IV total {0202:0}', ja='個体値　{0202:0}'),
    dict(bank=('system', SUMMARY_BANK), key='SV_TOTALS_DESC',
         en='Hidden Power: {0103:1}\nEV total {0202:2} ({0202:3} left)',
         ja='めざめるパワー：{0103:1}\n努力値　{0202:2}（のこり　{0202:3}）'),
]

PRINT_MSG, PRINT_WS_R, PRINT_QUE = 0x021B4EC5, 0x021B5041, 0x02021C7D
WIN_TABLE = 0x021BB14E              # stats page windows: (x, y, w, h) in tiles; 0 HP row, 2-6 Attack .. Speed


ROW_W = 23
# the stats page's window table (x, y, w, h) after our widths: all 13 windows must fit frame 4's char area at once
STATS_WINDOWS = [(8, 4, ROW_W, 2), (17, 6, 6, 1)] + [(8, y, ROW_W, 2) for y in (7, 9, 11, 13, 15)] + \
    [(6, 18, 20, 6), (10, 6, 14, 2), (10, 8, 14, 2), (10, 10, 14, 2), (1, 13, 30, 6), (4, 20, 24, 4)]
FRAME4_TILES = 0x6000 // 32
assert sum(w * h for _, _, w, h in STATS_WINDOWS) <= FRAME4_TILES - 2, 'statview: the stats page windows overflow frame 4'
assert 0xB2 + 1 <= ROW_W * 8, 'statview: the EV column past the row windows'


def _p(addr, orig, target, note):
    return dict(where='ov207', addr=addr, kind='bl', orig=orig, target=target, note=note)


def _w(i, old, new):
    return dict(where='ov207', addr=WIN_TABLE + 4 * i + 2, kind='u8', orig=old, target=new,
                note=f'stats window {i}: width {old} -> {new} tiles (to the screen edge)')


PATCHES = [
    _p(0x021B2FBC, 0x0203D555, 'statview_init', 'summary init: the ability in the Ability box'),
    _p(0x021B3FFA, 0x021B400D, 'statview_keys', 'summary keys: SELECT on the stats page'),
    _p(0x021B8C96, 0x021B8F11, 'statview_draw', 'stats page draw'),
    # StatsDraw: the HP row compact + its IV / EV
    _p(0x021B8F74, PRINT_WS_R, 'statview_hp_cur', 'HP current'),
    _p(0x021B8F8E, PRINT_MSG, 'statview_hp_slash', 'HP "/"'),
    _p(0x021B8FC8, PRINT_WS_R, 'statview_hp_max', 'HP max + IV / EV'),
    # StatsDraw: each row's value + its IV / EV
    _p(0x021B9026, PRINT_WS_R, 'statview_row', 'Attack + IV / EV'),
    _p(0x021B9084, PRINT_WS_R, 'statview_row', 'Defense + IV / EV'),
    _p(0x021B90E2, PRINT_WS_R, 'statview_row', 'Sp. Atk + IV / EV'),
    _p(0x021B9140, PRINT_WS_R, 'statview_row', 'Sp. Def + IV / EV'),
    _p(0x021B91A0, PRINT_WS_R, 'statview_row', 'Speed + IV / EV'),
    # StatsDraw: the Ability box
    _p(0x021B91BA, PRINT_MSG, 'statview_label', 'Ability tab -> Totals'),
    _p(0x021B9206, PRINT_QUE, 'statview_desc', 'ability description -> Hidden Power, EV total'),
    _p(0x021B924E, PRINT_QUE, 'statview_name', 'ability name -> IV total'),
    # the row windows to x 248 (x 8 + 23 tiles; the EV column ends at window x 0xB2 = 178 < 184)
    _w(0, 16, ROW_W), _w(2, 14, ROW_W), _w(3, 14, ROW_W), _w(4, 14, ROW_W), _w(5, 14, ROW_W), _w(6, 14, ROW_W),
]

# --- the panel graphics ---------------------------------------------------------------------------------------------
SUMMARY_ARC, PANEL_NCGR, PANEL_NSCR = 'a/0/7/7', 12, 75
FONT_ARC, SMALL_FONT = 'a/0/2/3', 1
HEADERS = {'en': ('IV', 'EV'), 'jp': ('個体値', '努力値')}
HEADER_CENTERS = (198, 233)         # screen x: centres of the IV (right edge 204) and EV (right edge 242) columns
HEADER_ROW = 3                      # tile row of the dark band between the title bar and the panel (y 24-31)
DARK, INK, SHADOW = 7, 15, 3        # panel palette: band navy, white (stat names), grey shadow


def panel(ctx):
    """-> a/0/7/7 bytes with the stats page's panel to the screen edge and the IV / EV headers"""
    import ndsfs, gfx5
    fid = ctx.fid(SUMMARY_ARC)
    raw = ctx.rom.file(fid)
    narc = ndsfs.narc(raw)
    g_data, g_lz = gfx5.unpack(narc[PANEL_NCGR])
    s_data, s_lz = gfx5.unpack(narc[PANEL_NSCR])
    g, s = gfx5.NCGR(g_data), gfx5.NSCR(s_data)
    assert g.bpp == 4 and s.w == 256 and (s.at(26, 4), s.at(27, 4), s.at(25, 3)) == (44, 22, 18), \
        'statview: unexpected stats panel graphics'
    # 1. panel rows (tile rows 4-16) to the screen edge: the light tile of each row repeated; the band above dark
    for ty in range(4, 17):
        for tx in range(21, 32):
            s.put(tx, ty, s.at(20, ty))
    dark = s.at(20, 3)
    assert dark & 0x3FF == 1
    for ty in range(1, 4):
        for tx in range(23, 32):
            s.put(tx, ty, dark)
    # 2. headers in the small font, drawn into new tiles of the band
    used = set()
    for i, m in enumerate(narc):
        d, _ = gfx5.unpack(m)
        if d[:4] == b'RCSN':
            used |= {e & 0x3FF for e in gfx5.NSCR(d).m}
    free = (t for t in range(64, g.ntiles()) if t not in used and not any(g.data[t * 32:t * 32 + 32]))
    font = gfx5.Font(ndsfs.narc(ctx.rom.file(ctx.fid(FONT_ARC)))[SMALL_FONT])
    band = [[DARK] * 256 for _ in range(8)]
    for text, cx in zip(HEADERS[ctx.lang], HEADER_CENTERS):
        px, w = font.text(text)
        x0 = cx - w // 2
        for y in range(8):
            for x in range(w):
                v = px[y][x]
                if v:
                    band[y][x0 + x] = INK if v == 1 else SHADOW
    changed = []
    for tx in range(32):
        cell = [row[tx * 8:tx * 8 + 8] for row in band]
        if any(v != DARK for row in cell for v in row):
            t = next(free)
            g.set_tile(t, cell)
            s.put(tx, HEADER_ROW, (dark & 0xF000) | t)
            changed.append(tx)
    narc[PANEL_NCGR] = gfx5.pack(g.encode(), g_lz)
    narc[PANEL_NSCR] = gfx5.pack(s.encode(), s_lz)
    print(f'statview: stats panel to the screen edge, headers {HEADERS[ctx.lang]} in tile columns {changed}')
    return {fid: ndsfs.pack_narc(narc, ndsfs.narc_layout(raw))}


def files(ctx):
    return panel(ctx)
