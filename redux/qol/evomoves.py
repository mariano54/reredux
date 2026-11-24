"""ReRedux evomoves (evomoves.c): an "EVO/MOVES" page in the Pokémon summary (party and PC, overlay 207) and in the
Pokédex entry: how the species evolves (its whole evolution family, each step with its method) and its level-up
learnset ("Lv. N  Move").

Summary: page 4 of the app's page cycle (STATUS, STATS, [RIBBONS,] EVO/MOVES; LEFT / RIGHT as for the other pages; not
for eggs). Top screen: the memo page's lined panel with the evolution family (pre-evolutions first, the shown species
in blue, each evolution with its method in words), the title bar label « EVO/MOVES » (JP ／しんか・わざ). Bottom screen:
the learnset in the info page's panel style (dark "Lv." column, light move column), moves the Pokémon knows in blue,
the next one it learns in red; the touch screen's arrows (or A, then UP / DOWN, B) scroll it. Data: the evolution graph
is baked from the ROM's a/0/1/9 at build time (HEADERS: evomoves_data.h); the learnset is read at run time with the
game's own loader (PML_LearnsetLvUpLoad, a/0/1/8, the form's entry); names come from the ROM's text banks through word
sets. Hook sites: pokeblack2 asm/overlay_207.s (see evomoves.c).

Graphics (files): the label (a copy of NSCR 67 with new tiles in NCGR 11), the bottom panel (NSCR 65 recomposed: eight
uniform rows, tiles added to NCGR 10), appended to a/0/7/7 as members 181 / 182.

Also the Pokédex INFO page's base stats (dexstats.c): its top screen shows the six base stats with value-coloured bars,
the total and the abilities of the form the entry shows (the DS_* lines; STATS_PAL appended to a/1/5/7)."""
import os, struct, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))

# --- B2 symbols (Black 2 IREO; W2 swan names, ARM9 -0x2C above 0x0201C000; verified in pokeblack2/asm) ------------------
SOURCES = ['evomoves.c', 'dexmoves.c', 'dexstats.c']

SYMS = {
    # text
    'em_PrintQue': 0x02021C7D,      # (que, bmp, x, y, str, font, color)
    'em_QueIdle': 0x02021C0D,       # (que) -> 1 when nothing is queued
    'em_QueBmpBusy': 0x02021C1D,    # (que, bmp) -> 1 while bmp still has prints queued
    'em_StrWidth': 0x02022889,      # GFL_FontGetBlockWidth(str, font, spacing)
    'em_WsCreate': 0x020241D5,      # GFL_WordSetSystemCreateDefault(heap)
    'em_WsFree': 0x02024275,
    'em_WsMsg': 0x02024341,         # GFL_WordSetLoadMsg(ws, idx, system bank, line)
    'em_WsSpecies': 0x020243D1,     # WordSet_LoadSpeciesName(ws, idx, species)
    'em_WsMove': 0x020244A5,        # (ws, idx, move)
    'em_WsItem': 0x020244B5,        # (ws, idx, item)
    'em_WsNumber': 0x0202451D,      # (ws, idx, value, digits, style, code)
    'em_WsFormat': 0x02024921,      # (ws, dst, src)
    'em_StrBufCreate': 0x02048531,  # (len, heap)
    'em_StrBufFree': 0x02048565,
    'em_MsgLoad': 0x0204898D,       # GFL_MsgDataLoadStrbufNew(msgdata, id)
    # windows / bitmaps / BG
    'em_WinCreate': 0x020480C1,     # BmpWin_CreateDynamic(frame, x, y, w, h, pal, dir)
    'em_WinFree': 0x02048211,
    'em_WinFlushChar': 0x02048245,
    'em_WinFlushMap': 0x0204826D,
    'em_WinFrame': 0x020484D5,
    'em_WinBmp': 0x020484F5,
    'em_BmpFill': 0x0204713D,       # GFL_BitmapFill(bmp, color)
    'em_BmpFillArea': 0x020470F9,   # GFL_BitmapFillArea(bmp, x, y, w, h, color)
    'em_BgLoadScr': 0x02044F91,     # GFL_BGSysLoadScr(frame): transfer the screen buffer
    'em_BgBufScr': 0x02045055,      # GFL_BGSysBufferScrDefault(frame, data, size)
    'em_BgQueue': 0x02045B7D,       # GFL_BGSysQueueScrLoad(frame)
    'em_BgScrArea': 0x020454D5,     # GFL_BGSysLoadScrArea(frame, x, y, w, h, data, sx, sy, sw, sh)
    'em_BgFillArea': 0x02045605,    # GFL_BGSysFillScrArea(frame, val, x, y, w, h, pal)
    'em_BgFill': 0x02045791,        # GFL_BGSysFillScrAsync(frame, val)
    'em_ReadNSCR': 0x0204B305,      # GFL_G2DIOReadNSCR(arc, file, comp, &scrdata, heap) -> buffer
    'em_HeapFree': 0x0203A24D,
    # data
    'em_LearnLoad': 0x02020261,     # PML_LearnsetLvUpLoad(species, form, buf): a/0/1/8
    'em_DatId': 0x02020481,         # PML_PersonalGetDatID(species, form)
    # input
    'em_KeyTrg': 0x0203DEFD,        # GCTX_HIDGetPressedKeys
    'em_KeyRep': 0x0203DF45,        # GCTX_HIDGetTypedKeys (with repeat; the summary's UP / DOWN / LEFT / RIGHT)
    'em_TouchTrg': 0x0203DAC9,      # (&x, &y) -> 1 on a new touch
    'em_TouchCont': 0x0203DA85,     # (&x, &y) -> 1 while touched
    # overlay 207 (summary)
    'em_CurPP': 0x021B4DDD,         # the shown Pokémon (PokeParty; PC ones converted)
    'em_PageRedraw': 0x021B49D1,
    'em_Input': 0x021B3FE1,         # input step (keys, then touch) when input is on
    'em_ExitFirst': 0x021B3EB9,     # first teardown call of the app's exit
    'em_InitBG': 0x021B342D,        # the app init's BG setup
    'em_P0Hide': 0x021B6CAD, 'em_P1Hide': 0x021B8BA5, 'em_P2Hide': 0x021B7EFD, 'em_P3Hide': 0x021B96B9,
    'em_P0Create': 0x021B6A61, 'em_P1Create': 0x021B8A9D, 'em_P2Create': 0x021B7DB1, 'em_P3Create': 0x021B9511,
    'em_P0FinOld': 0x021B6CD5, 'em_P1FinOld': 0x021B8BF5, 'em_P2FinOld': 0x021B7F21, 'em_P3FinOld': 0x021B9729,
    'em_P0FinNew': 0x021B6AD5, 'em_P1FinNew': 0x021B8B31, 'em_P2FinNew': 0x021B7E0D, 'em_P3FinNew': 0x021B9611,
    'em_P1Update': 0x021B85A1, 'em_P2Update': 0x021B7691,
    # ARM9: BG / bitmaps / fonts / messages / palettes (the Pokédex page builds its own layers)
    'em_BgOffset': 0x02044CFD,      # (frame, op, value): BG offset set
    'em_BgClear': 0x02045709,       # GFL_BGSysClearBG(frame)
    'em_BgPrio': 0x02044BD9,        # GFL_BGSysSetBGPriority(frame, prio)
    'em_BgOn': 0x02044C99,          # GFL_BGSysSetBGEnabled(frame, on)
    'em_BgLoadChar': 0x02045081,    # GFL_BGSysLoadChar(frame, data, size, tile)
    'em_BmpNew': 0x02046E29,        # GFL_BitmapCreate(w tiles, h tiles, bytes per tile, heap)
    'em_BmpFree': 0x02046EDD,
    'em_BmpPixels': 0x02046EF5,
    'em_BmpLoad': 0x02046F3D,       # GFL_G2DIOLoadBitmap(arc, file, comp, heap)
    'em_BmpCopy': 0x02046F19,       # GFL_BitmapCopy(src, dst)
    'em_FontNew': 0x02022D59,       # (arc, ..., heap)
    'em_FontFree': 0x02022DA9,
    'em_QueNew': 0x020219A9,        # print queue (size, heap)
    'em_QueFree': 0x02021A19,
    'em_QueClear': 0x02021C45,
    'em_QueRun': 0x02021A3D,
    'em_MsgNew': 0x0204875D,        # GFL_MsgSysLoadData(0, 2, bank, heap)
    'em_MsgFree': 0x020487D5,
    'em_ArcOpen': 0x0204AA31,       # GFL_ArcSysCreateFileHandle(arc, heap)
    'em_ArcClose': 0x0204AB0D,
    'em_PalLoad': 0x0204B125,       # (handle, NCLR file, engine 0/4, src, dst, size, heap)
    'em_MoveParam': 0x02021281,     # move data: 0 type, 2 category, 3 power, 4 accuracy, 5 PP
    'em_MoveNeverMiss': 0x0202174D, # the move never misses (accuracy "--")
    'em_HeapAlloc': 0x0203A1FD,     # GFL_HeapAllocate(heap, size, clear, file, line)
    'em_SaveCfg': 0x0201765D,       # (save, idx) -> value
    'em_SaveCfgSet': 0x02017645,    # (save, idx, value)
    # overlay 298 (Pokédex): page modules, the bottom bar, the header, fades, grids
    'dx_ModCreate': 0x0219FBC1, 'dx_ModFree': 0x0219FBED, 'dx_ModAlloc': 0x0219FCAD, 'dx_ModFreeData': 0x0219FCCD,
    'dx_Switch': 0x021A061D,        # create the page module for top+4
    'dx_BarUpdate': 0x021A19C5,     # the entry bar: LEFT / RIGHT walk the page buttons
    'dx_BarTouch': 0x021A14AD,      # the bar's touch action
    'dx_CurSpecies': 0x0219FD41, 'dx_NextSpecies': 0x0219FD4D, 'dx_PrevSpecies': 0x0219FD8D,
    'dx_BarMode': 0x021A1475, 'dx_BarSetup': 0x021A1455, 'dx_BarStart': 0x021A1479, 'dx_BarPage': 0x021A155D,
    'dx_BarEnable': 0x021A15E9, 'dx_BarCheck': 0x021A15B5, 'dx_BarAck': 0x021A1545, 'dx_BarExit': 0x021A148D,
    'dx_BarCheckGet': 0x021A15CD, 'dx_BtnPress': 0x021A0D91, 'dx_BtnShown': 0x021A0D21, 'dx_BtnEnable': 0x021A0D01,
    'dx_HdrState': 0x021A2321, 'dx_HdrIn': 0x021A2325, 'dx_HdrOut': 0x021A2335, 'dx_HdrFlush': 0x021A24AD,
    'dx_FadeNew': 0x0219FDC9, 'dx_FadeInit': 0x0219FE99, 'dx_FadeBind': 0x0219FE89, 'dx_FadeIn': 0x0219FE59,
    'dx_FadeBusy': 0x0219FE49, 'dx_FadeOut': 0x0219FE65, 'dx_FadeUpdate': 0x0219FDED, 'dx_FadeFree': 0x0219FDE5,
    'dx_GridLoad': 0x021A01C5, 'dx_GridFree': 0x021A02FD,
    'dx_Btn': 0x021A0DA9,           # (button manager, id) -> button (+0x18 x)
    'dx_BarDel': 0x021A16C5,        # free the bar of the current mode
    'em_BgPal': 0x02045321,         # GFL_BGSysUploadStdPalette(frame, data, size, offset)
    'em_DexOf': 0x0200D191,         # (save) -> Pokédex save data
    'em_DexCaught': 0x0200D661,     # PokeDex_IsCaught(dex, species)
    # the INFO page's base stats (dexstats.c)
    'ds_InfoMain': 0x021A25F9,      # INFO page module: main (module, state, work, data, ctx)
    'ds_InfoExit': 0x021A2571,      # ... exit
    'em_CharAlloc': 0x02044565,     # GFL BG char area: (frame, bytes, dir) -> first tile or -1
    'em_CharFree': 0x02044669,      # (frame, tile, bytes)
    'em_PersonalParam': 0x0201EF1D, # PML_PersonalGetParamSingle(species, form, param): 0-5 stats, 26-28 abilities
    'em_DexDraw': 0x0200D3C9,       # (dex, species, &sex, &rare, &form, heap): what the entry shows (FUN_021A3004)
    'em_HeapMaxAlloc': 0x02039F91,  # GFL_HeapGetHighestAllocatableSize(heap)
}

SUMMARY_BANK = 179
# word set slots in the method lines: 0 level / number, 1 item, 2 move, 3 species, 4 place
METHODS_EN = {
    'EVO_LV': 'Lv. {0202:0}',
    'EVO_FRIEND': 'High friendship',
    'EVO_FRIEND_DAY': 'Friendship, daytime',
    'EVO_FRIEND_NIGHT': 'Friendship, night',
    'EVO_TRADE': 'Trade',
    'EVO_TRADE_ITEM': 'Trade holding {0109:1}',
    'EVO_TRADE_MON': 'Trade for {0101:3}',
    'EVO_ITEM': '{0109:1}',
    'EVO_ATK_GT': 'Lv. {0202:0}, Atk higher',
    'EVO_ATK_EQ': 'Lv. {0202:0}, Atk = Def',
    'EVO_ATK_LT': 'Lv. {0202:0}, Def higher',
    'EVO_RANDOM': 'Lv. {0202:0}, random',
    'EVO_SHED': 'Lv. {0202:0}, free slot + Ball',
    'EVO_BEAUTY': 'High Beauty',
    'EVO_ITEM_M': '{0109:1}, male',
    'EVO_ITEM_F': '{0109:1}, female',
    'EVO_HOLD_DAY': 'Hold {0109:1}, daytime',
    'EVO_HOLD_NIGHT': 'Hold {0109:1}, night',
    'EVO_MOVE': 'Knows {0107:2}',
    'EVO_PARTY': '{0101:3} in party',
    'EVO_LV_M': 'Lv. {0202:0}, male',
    'EVO_LV_F': 'Lv. {0202:0}, female',
    'EVO_PLACE': 'Level up in {0105:4}',
    'EVO_UNKNOWN': '???',
    'EVO_NONE': 'Does not evolve',
    'EVO_LIST_LV': 'Lv. {0202:0}',
    'EVO_LIST_POS': '{0202:0}-{0202:1} of {0202:2}',
    'EVO_LIST_NONE': 'No level-up moves',
    'EVO_ROOT': '{0101:3}',
    'EVO_CHILD': '→ {0101:3}',
    'EVO_MOVENAME': '{0107:2}',
    'EVO_UP': '↑',
    'EVO_DOWN': '↓',
    'EVO_DEX_TITLE': 'EVO/MOVES',
    'EVO_DEX_LEARN': 'Level-up moves',
    'EVO_DEX_TYPE': '{0103:4}',
    'EVO_DEX_NUM': '{0202:0}',
    'EVO_DEX_DASH': '--',
    'EVO_DET_CAT': 'Category',
    'EVO_DET_POW': 'Power',
    'EVO_DET_ACC': 'Accuracy',
    'EVO_DET_PP': 'PP',
    'EVO_CAT_PHYS': 'Physical',
    'EVO_CAT_SPEC': 'Special',
    'EVO_CAT_STATUS': 'Status',
    'EVO_TYPE_FAIRY': 'Fairy',
    'DS_TITLE': 'Base stats',
    'DS_TOTAL': 'Total',
    'DS_HP': 'HP',
    'DS_ATK': 'Attack',
    'DS_DEF': 'Defense',
    'DS_SPA': 'Sp. Atk',
    'DS_SPD': 'Sp. Def',
    'DS_SPE': 'Speed',
    'DS_ABIL': 'Abilities',
    'DS_HIDDEN': 'Hidden',
}
METHODS_JA = {
    'EVO_LV': 'Ｌｖ．{0202:0}',
    'EVO_FRIEND': 'なつき度が　高い',
    'EVO_FRIEND_DAY': 'なつき度が　高い（昼）',
    'EVO_FRIEND_NIGHT': 'なつき度が　高い（夜）',
    'EVO_TRADE': '通信交換',
    'EVO_TRADE_ITEM': '{0109:1}を　持たせて　通信交換',
    'EVO_TRADE_MON': '{0101:3}と　通信交換',
    'EVO_ITEM': '{0109:1}',
    'EVO_ATK_GT': 'Ｌｖ．{0202:0}　こうげき＞ぼうぎょ',
    'EVO_ATK_EQ': 'Ｌｖ．{0202:0}　こうげき＝ぼうぎょ',
    'EVO_ATK_LT': 'Ｌｖ．{0202:0}　こうげき＜ぼうぎょ',
    'EVO_RANDOM': 'Ｌｖ．{0202:0}（ランダム）',
    'EVO_SHED': 'Ｌｖ．{0202:0}　あき＋ボール',
    'EVO_BEAUTY': 'うつくしさが　高い',
    'EVO_ITEM_M': '{0109:1}（オス）',
    'EVO_ITEM_F': '{0109:1}（メス）',
    'EVO_HOLD_DAY': '{0109:1}を　持って　昼',
    'EVO_HOLD_NIGHT': '{0109:1}を　持って　夜',
    'EVO_MOVE': '{0107:2}を　覚えている',
    'EVO_PARTY': '{0101:3}が　手持ちに　いる',
    'EVO_LV_M': 'Ｌｖ．{0202:0}（オス）',
    'EVO_LV_F': 'Ｌｖ．{0202:0}（メス）',
    'EVO_PLACE': '{0105:4}で　レベルアップ',
    'EVO_UNKNOWN': '？？？',
    'EVO_NONE': 'しんか　しない',
    'EVO_LIST_LV': 'Ｌｖ．{0202:0}',
    'EVO_LIST_POS': '{0202:0}－{0202:1}／{0202:2}',
    'EVO_LIST_NONE': 'レベルで　覚える　わざは　ない',
    'EVO_ROOT': '{0101:3}',
    'EVO_CHILD': '→{0101:3}',
    'EVO_MOVENAME': '{0107:2}',
    'EVO_UP': '↑',
    'EVO_DOWN': '↓',
    'EVO_DEX_TITLE': 'Evolution/進化・わざ',
    'EVO_DEX_LEARN': 'レベルで　覚える　わざ',
    'EVO_DEX_TYPE': '{0103:4}',
    'EVO_DEX_NUM': '{0202:0}',
    'EVO_DEX_DASH': '－－',
    'EVO_DET_CAT': 'ぶんるい',
    'EVO_DET_POW': 'いりょく',
    'EVO_DET_ACC': 'めいちゅう',
    'EVO_DET_PP': 'ＰＰ',
    'EVO_CAT_PHYS': 'ぶつり',
    'EVO_CAT_SPEC': 'とくしゅ',
    'EVO_CAT_STATUS': 'へんか',
    'EVO_TYPE_FAIRY': 'フェアリー',
    'DS_TITLE': '種族値',
    'DS_TOTAL': '合計',
    'DS_HP': 'ＨＰ',
    'DS_ATK': 'こうげき',
    'DS_DEF': 'ぼうぎょ',
    'DS_SPA': 'とくこう',
    'DS_SPD': 'とくぼう',
    'DS_SPE': 'すばやさ',
    'DS_ABIL': 'とくせい',
    'DS_HIDDEN': '夢特性',
}
TEXTS =[dict(bank=('system', SUMMARY_BANK), key=k, en=v, ja=METHODS_JA[k]) for k, v in METHODS_EN.items()]

# Gen 5 evolution methods -> (text key, word set slot of the parameter: 'lv', 'item', 'move', 'species', 'place', None)
METHODS = {
    1: ('EVO_FRIEND', None), 2: ('EVO_FRIEND_DAY', None), 3: ('EVO_FRIEND_NIGHT', None), 4: ('EVO_LV', 'lv'),
    5: ('EVO_TRADE', None), 6: ('EVO_TRADE_ITEM', 'item'), 7: ('EVO_TRADE_MON', 'species'), 8: ('EVO_ITEM', 'item'),
    9: ('EVO_ATK_GT', 'lv'), 10: ('EVO_ATK_EQ', 'lv'), 11: ('EVO_ATK_LT', 'lv'), 12: ('EVO_RANDOM', 'lv'),
    13: ('EVO_RANDOM', 'lv'), 14: ('EVO_LV', 'lv'), 15: ('EVO_SHED', 'lv'), 16: ('EVO_BEAUTY', None),
    17: ('EVO_ITEM_M', 'item'), 18: ('EVO_ITEM_F', 'item'), 19: ('EVO_HOLD_DAY', 'item'), 20: ('EVO_HOLD_NIGHT', 'item'),
    21: ('EVO_MOVE', 'move'), 22: ('EVO_PARTY', 'species'), 23: ('EVO_LV_M', 'lv'), 24: ('EVO_LV_F', 'lv'),
    25: ('EVO_PLACE', 'place'), 26: ('EVO_PLACE', 'place'), 27: ('EVO_PLACE', 'place'),
}
SLOT = {None: 0, 'lv': 1, 'item': 2, 'move': 3, 'species': 4, 'place': 5}
# Unova's places for the place methods (system bank 109 lines): magnetic field, Moss Rock, Ice Rock
PLACES = {25: 37, 26: 33, 27: 38}           # Chargestone Cave, Pinwheel Forest, Twist Mountain
N_SPECIES = 650


def _evo_table(ctx):
    import ndsfs
    entries = ndsfs.narc(ctx.rom.file(ctx.fid('a/0/1/9')))
    first, lst = [], []
    for s in range(N_SPECIES):
        first.append(len(lst))
        d = entries[s] if s < len(entries) else b''
        for k in range(0, len(d) - len(d) % 6, 6):
            m, p, t = struct.unpack_from('<HHH', d, k)
            if m and 0 < t < N_SPECIES:             # method 0 = an unused slot (Redux's Feebas has one)
                lst.append((m, p, t))
    first.append(len(lst))
    return first, lst


# widths the pages give (pixels of the game's main font): summary list move column, Pokédex move / type columns
MAX_W = {'move': 92, 'type': 64, 'species': 96, 'level': 44, 'ability': 84, 'stat label': 60, 'ability label': 48}


def check_texts(ctx):
    """the build's language: every character of our lines in the game's font, the names that go into fixed columns
    within their width (texts_check.py style)"""
    import ndsfs, gfx5, gen5text, gen5data, re as _re
    font = gfx5.Font(ndsfs.narc(ctx.rom.file(ctx.fid('a/0/2/3')))[0])
    banks = ndsfs.narc(ctx.rom.file(ctx.fid('a/0/0/2')))
    table = METHODS_JA if ctx.lang == 'jp' else METHODS_EN
    for k, v in table.items():
        plain = _re.sub(r'\{[0-9A-F]{4}:\d+\}', '', v).replace('\n', '')
        missing = [c for c in plain if ord(c) not in font.cmap]
        assert not missing, f'evomoves: {k}: {missing} not in the {ctx.lang} font'

    def clean(n):
        n = n.replace('{U+FFFF}', '')
        return _re.sub(r'\{U\+([0-9A-F]{4})\}', lambda mm: chr(int(mm.group(1), 16)), n)

    def widest(bank):
        names = [clean(n) for n in gen5data.name_list(banks[bank])]
        names = [n for n in names if n and not n.startswith('{')]
        return max((font.text(n)[1], n) for n in names if all(ord(c) in font.cmap for c in n))
    lv = font.text(_re.sub(r'\{0202:0\}', '100', table['EVO_LIST_LV']))[1]
    got = {'move': widest(403), 'type': widest(398), 'species': widest(90), 'level': (lv, '100'),
           'ability': widest(374),     # dexstats.c: two columns from x 62 and 148 (to 232)
           'stat label': max((font.text(table[k])[1], table[k]) for k in ('DS_HP', 'DS_ATK', 'DS_DEF', 'DS_SPA',
                                                                          'DS_SPD', 'DS_SPE')),
           'ability label': max((font.text(table[k])[1], table[k]) for k in ('DS_ABIL', 'DS_HIDDEN'))}
    for k, (w, n) in got.items():
        assert w <= MAX_W[k], f'evomoves: the widest {k} name {n!r} is {w} px (room {MAX_W[k]})'
    print('evomoves: widest names ' + ', '.join(f'{k} {w} px ({n})' for k, (w, n) in got.items()))


def HEADERS(ctx):
    """evomoves_data.h: the evolution graph (species -> its evolutions: method, parameter, target), the text ids of
    the methods, and the largest learnset file (the run-time buffer must hold it)"""
    import ndsfs
    first, lst = _evo_table(ctx)
    learn = ndsfs.narc(ctx.rom.file(ctx.fid('a/0/1/8')))
    biggest = max(len(d) for d in learn)
    assert biggest <= 0x100, f'evomoves: a learnset file has {biggest} bytes (buffer 256)'
    methods = sorted({m for m, _, _ in lst})
    unknown = [m for m in methods if m not in METHODS]
    if unknown:
        print('evomoves: warning: evolution methods without a text:', unknown)
    rows = []
    for m, p, t in lst:
        rows.append(f'{{{m}, {p}, {t}}}')
    meth = ['{0, 0}'] * 28
    for m, (key, slot) in METHODS.items():
        meth[m] = f'{{{ctx.text_id(key)}, {SLOT[slot]}}}'
    check_texts(ctx)
    dex_members = len(ndsfs.narc(ctx.rom.file(ctx.fid(DEX_ARC))))
    return {'evomoves_capsule.h': capsule_header(ctx.lang),
            'evomoves_data.h':
            '/* generated by qol/evomoves.py HEADERS from the ROM evolution data (a/0/1/9) */\n'
            f'#define EM_NSPECIES {N_SPECIES}\n#define EM_NEVO {len(lst)}\n'
            f'#define DX_PAL_FIRST {dex_members}    /* evomoves.py dex_palettes: a/1/5/7 members */\n'
            f'#define EM_PLACE_25 {PLACES[25]}\n#define EM_PLACE_26 {PLACES[26]}\n#define EM_PLACE_27 {PLACES[27]}\n'
            'typedef struct { u16 method, param, target; } EmEvo;\n'
            'typedef struct { u16 text; u8 slot, pad; } EmMethod;\n'
            f'static const u16 em_evo_first[EM_NSPECIES + 1] = {{{", ".join(map(str, first))}}};\n'
            f'static const EmEvo em_evo[EM_NEVO] = {{\n    ' + ',\n    '.join(rows) + '\n};\n'
            f'static const EmMethod em_methods[28] = {{{", ".join(meth)}}};\n'}


# --- patches (overlay 207) ------------------------------------------------------------------------------------------
LDR_PAGE_OLD = b'\xe0\x6d'                  # ldr r0, [r4, #0x5c]
LDR_PAGE_NEW = b'\xa0\x6d'                  # ldr r0, [r4, #0x58]
MOV_R0_R4 = b'\x20\x1c'                     # add r0, r4, #0


def _b(src, dst):
    off = dst - (src + 4)
    assert -2048 <= off // 2 < 1024 and not off & 1
    return struct.pack('<H', 0xE000 | ((off >> 1) & 0x7FF))


def _dispatch(addr, ldr, bhi, join, target, note):
    """a page jump table: `ldr r0, [r4, #page]; cmp r0, #3; bhi join; add r0, r0, r0` -> `mov r0, r4; bl target;
    b join` (target runs every case, ours included)"""
    return [
        dict(where='ov207', addr=addr, kind='bytes', expect=ldr, target=MOV_R0_R4, note=note + ': app'),
        dict(where='ov207', addr=addr + 2, kind='bl', expect=b'\x03\x28' + bhi, target=target, note=note),
        dict(where='ov207', addr=addr + 6, kind='bytes', expect=b'\x00\x18', target=_b(addr + 6, join),
             note=note + ': join'),
    ]


_BASE_PATCHES = (
    _dispatch(0x021B4A16, LDR_PAGE_OLD, b'\x24\xd8', 0x021B4A66, 'em_hide', 'page redraw: hide the old page') +
    _dispatch(0x021B4A66, LDR_PAGE_NEW, b'\x24\xd8', 0x021B4AB6, 'em_create', 'page redraw: create the new page') +
    _dispatch(0x021B4BBA, LDR_PAGE_OLD, b'\x24\xd8', 0x021B4C0A, 'em_finold', 'page change: finish the old page') +
    _dispatch(0x021B4C0A, LDR_PAGE_NEW, b'\x24\xd8', 0x021B4C5A, 'em_finnew', 'page change: show the new page') +
    _dispatch(0x021B32F2, LDR_PAGE_OLD, b'\x1d\xd8', 0x021B3334, 'em_update', 'main step: page update') + [
        dict(where='ov207', addr=0x021B32E8, kind='bl', orig=0x021B3FE1, target='em_input',
             note='main step: input (our page, RIGHT onto it)'),
        dict(where='ov207', addr=0x021B316A, kind='bl', orig=0x021B3EB9, target='em_exit',
             note='app exit: free our page'),
        dict(where='ov207', addr=0x021B2FF6, kind='bl', orig=0x021B342D, target='em_init',
             note='app init: our page state'),
        # Pokédex entry (overlay 298, dexmoves.c)
        dict(where='ov298', addr=0x021A0562, kind='bl', orig=0x021A061D, target='em_dx_switch',
             note='Pokédex entry: page module 5 = EVO/MOVES'),
        dict(where='ov298', addr=0x021A04AC, kind='bl', orig=0x021A061D, target='em_dx_first',
             note='Pokédex entry: first page module'),
        dict(where='ov298', addr=0x021A1434, kind='bl', orig=0x021A19C5, target='em_dx_bar',
             note='Pokédex entry bar: LEFT / RIGHT to and from EVO/MOVES'),
        dict(where='ov298', addr=0x021A0578, kind='bl', orig=0x021A14AD, target='em_dx_action',
             note='Pokédex entry: our page request as a page action'),
        dict(where='ov298', addr=0x021A1308, kind='bl', orig=0x021A16C5, target='em_dx_bardel',
             note='Pokédex bar freed: the EVO capsule off the bar BG'),
        dict(where='ov298', addr=0x021A145E, kind='bl', orig=0x021A16C5, target='em_dx_bardel',
             note='Pokédex bar mode change: the EVO capsule off the bar BG'),
        # the INFO page's module table (_021AC3D4: init, main, exit, input): base stats on its top screen (dexstats.c)
        dict(where='ov298', addr=0x021AC3D8, kind='ptr', orig=0x021A25F9, target='ds_main',
             note='Pokédex INFO page: main step + base stats'),
        dict(where='ov298', addr=0x021AC3DC, kind='ptr', orig=0x021A2571, target='ds_exit',
             note='Pokédex INFO page: exit (base stats freed)'),
    ])

# the entry bar's buttons make room for the EVO capsule (x 168 with four page capsules, the vanilla spacing of 32;
# after the three page capsules of the other layouts at the four-capsule positions): overlay 298's tables
BAR_MAIN = 0x021AC30C       # entry bar: 9 x (id, x u16, y u16, width, touch action, key action)
BAR_NOFORMS = 0x021AC248    # (x, y) per button when the FORMS page is off
BAR_NOAREA = 0x021AC224     # ... when the AREA page is off
# button order in the tables: back, X, checkbox, FORMS, CRY, AREA, INFO, DOWN, UP
_MAIN_X = [(0xE8, 0xEB), (0xD0, 0xD9), (0xB8, 0xCA), (0x90, 0x88), (0x70, 0x68), (0x50, 0x48), (0x30, 0x28), (0x18, 0x14)]
_MAIN_W = [(0x18, 0x15), (0x18, 0x12), (0x18, 0x0F)]
_ALT_X = {BAR_NOFORMS: [(4, 0x88, 0x70), (5, 0x60, 0x50), (6, 0x38, 0x30)],
          BAR_NOAREA: [(3, 0x88, 0x70), (4, 0x60, 0x50), (5, 0x60, 0x50), (6, 0x38, 0x30)]}
_NAMES = ['back', 'X', 'checkbox', 'FORMS', 'CRY', 'AREA', 'INFO', 'DOWN', 'UP']
BAR_LAYOUT = (
    [dict(where='ov298', addr=BAR_MAIN + 20 * i + 4, kind='u16', orig=a, target=b,
          note=f'Pokédex entry bar: {_NAMES[i]} x {a} -> {b}') for i, (a, b) in enumerate(_MAIN_X)] +
    [dict(where='ov298', addr=BAR_MAIN + 20 * i + 8, kind='u32', orig=a, target=b,
          note=f'Pokédex entry bar: {_NAMES[i]} touch width {a} -> {b}') for i, (a, b) in enumerate(_MAIN_W)] +
    [dict(where='ov298', addr=t + 4 * i, kind='u16', orig=a, target=b,
          note=f'Pokédex entry bar ({"no FORMS" if t == BAR_NOFORMS else "no AREA"}): {_NAMES[i]} x {a} -> {b}')
     for t, lst in _ALT_X.items() for i, a, b in lst])
PATCHES = list(_BASE_PATCHES) + BAR_LAYOUT


# --- graphics -------------------------------------------------------------------------------------------------------
SUMMARY_ARC = 'a/0/7/7'
LABEL_NCGR, LABEL_NSCR_STATUS = 11, 67
BOTTOM_NCGR, BOTTOM_NSCR_INFO = 10, 65
NEW_LABEL, NEW_BOTTOM = 181, 182            # members appended to a/0/7/7 (evomoves.c EM_FILE_*)

# the labels' 5-row pixel font (« STATUS », « RIBBONS »): '#' ink (1), 'o' blue (9)
GLYPHS = {
    '«': ['..#', '.#o', '#o.', '#o.', '.#o', '..#'],
    '»': ['#..', 'o#.', '.o#', '.o#', 'o#.', '#..'],
    'E': ['####', '#...', '###.', '#...', '####'],
    'V': ['#...#', 'o#.#o', '.#.#.', '.o#o.', '..#..'],
    'O': ['o##o', '#..#', '#..#', '#..#', 'o##o'],
    'M': ['#...#', '##.##', '#o#o#', '#...#', '#...#'],
    'S': ['o###', '#...', 'o##o', '...#', '###o'],
    '/': ['...#', '..o#', '.o#.', '#o..', '#...'],
}
LABEL_EN = 'EVO/MOVES'
LABEL_JA = '／しんか・わざ'
INK, AA, BG = 1, 9, 3


def _free_tiles(narc, g, start):
    import gfx5
    used = set()
    for m in narc:
        d, _ = gfx5.unpack(m)
        if d[:4] == b'RCSN':
            used |= {e & 0x3FF for e in gfx5.NSCR(d).m}
    return (t for t in range(start, g.ntiles()) if t not in used and not any(g.data[t * g.tb:(t + 1) * g.tb]))


def _tilize(img, g, s, pal, free, tx0=0, ty0=0, tw=32, th=24, reuse=True):
    """write the 8x8 cells of img (rows of palette indices) into NSCR s (tile cols tx0.., rows ty0..): an
    identical tile of g (also flipped) is reused, else a free tile gets the pixels"""
    import gfx5
    index = {}
    if reuse:
        for t in range(g.ntiles()):
            px = g.tile(t)
            for fl, q in ((0, px), (0x400, [r[::-1] for r in px]), (0x800, px[::-1]),
                          (0xC00, [r[::-1] for r in px[::-1]])):
                index.setdefault(tuple(map(tuple, q)), t | fl)
    new = 0
    for ty in range(ty0, ty0 + th):
        for tx in range(tx0, tx0 + tw):
            cell = tuple(tuple(img[ty * 8 + y][tx * 8:tx * 8 + 8]) for y in range(8))
            if cell not in index:
                t = next(free)
                g.set_tile(t, [list(r) for r in cell])
                index[cell] = t
                new += 1
            s.put(tx, ty, (pal << 12) | index[cell])
    return new


def _render(g, s):
    import gfx5
    img = [[0] * s.w for _ in range(s.h)]
    for ty in range(s.h // 8):
        for tx in range(s.w // 8):
            px = gfx5.tile_px(g, s.at(tx, ty))
            for y in range(8):
                img[ty * 8 + y][tx * 8:tx * 8 + 8] = px[y]
    return img


def label(ctx, narc):
    """« EVO/MOVES » (JP ／しんか・わざ) in the title bar: NSCR 67 (« STATUS ») with the label redrawn in new tiles"""
    import gfx5, ndsfs
    g_data, g_lz = gfx5.unpack(narc[LABEL_NCGR])
    s_data, s_lz = gfx5.unpack(narc[LABEL_NSCR_STATUS])
    g, s = gfx5.NCGR(g_data), gfx5.NSCR(s_data)
    img = _render(g, s)
    pal = s.at(22, 1) >> 12
    # clear the old label (x 160-255 of the bar's text rows 10-20) to the bar colour
    for y in range(10, 21):
        for x in range(160, 256):
            img[y][x] = BG
    if ctx.lang == 'jp':
        font = gfx5.Font(ndsfs.narc(ctx.rom.file(ctx.fid('a/0/2/3')))[1])
        px, w = font.text(LABEL_JA)
        x0 = 168
        for y, row in enumerate(px[:8]):
            for x, v in enumerate(row):
                if v == 1:
                    img[11 + y][x0 + x] = INK
    else:
        x = 176
        for ch in '««' + ' ' + LABEL_EN + ' ' + '»»':
            if ch == ' ':
                x += 3
                continue
            gl = GLYPHS[ch]
            top = 13 if ch in '«»' else 14
            for y, row in enumerate(gl):
                for xx, c in enumerate(row):
                    if c != '.':
                        img[top + y][x + xx] = INK if c == '#' else AA
            x += len(gl[0]) + 1
        assert x <= 252, f'evomoves: label too wide ({x})'
    free = _free_tiles(narc, g, 1)
    new = _tilize(img, g, s, pal, free, 20, 1, 12, 2)
    narc[LABEL_NCGR] = gfx5.pack(g.encode(), g_lz)
    print(f'evomoves: label {LABEL_JA if ctx.lang == "jp" else LABEL_EN}: {new} new tiles in NCGR {LABEL_NCGR}')
    return gfx5.pack(s.encode(), s_lz)


# bottom panel (NSCR 65, palette 0): 7 dark, 6 dark + line, 1 light, 2 light + line, 4 dark/light edge
DARK, DARK_LINE, LIGHT, LIGHT_LINE, EDGE = 7, 6, 1, 2, 4
ROWS, ROW_Y0, ROW_H = 8, 8, 16              # list rows: y 8 .. 136
SPLIT = 51                                  # the edge column between "Lv. N" (x < 51) and the move (x > 51)
LIST_RIGHT = 152                            # the light column ends here below the diagonal (the item box)
EXP_ROW_NSCR = 74                           # the stats page's panel: the same EXP strip without "EXP" and the bar


def bottom(ctx, narc):
    """the learnset panel: NSCR 65 (the info page's dex rows) with eight uniform rows from y 8 to 136, each a dark
    "Lv. N" column and a light move column from x 52 to the panel's diagonal edge (at most x 152, dark beyond),
    separated by the info rows' lines; the white box below stays (the list position goes there), the EXP strip
    under it is the stats page's (no "EXP" label or bar)"""
    import gfx5
    g_data, g_lz = gfx5.unpack(narc[BOTTOM_NCGR])
    s_data, s_lz = gfx5.unpack(narc[BOTTOM_NSCR_INFO])
    g, s = gfx5.NCGR(g_data), gfx5.NSCR(s_data)
    assert s.at(9, 4) & 0x3FF == 17 and s.at(10, 4) & 0x3FF == 14, 'evomoves: unexpected info panel graphics'
    s74 = gfx5.NSCR(gfx5.unpack(narc[EXP_ROW_NSCR])[0])
    src = _render(g, s)
    img = [r[:] for r in src]

    def diag(y):
        """x of the light column's right edge in the info panel at row y (the '4' before the 7e8e border)"""
        for x in range(90, 255):
            if src[y][x] == EDGE and src[y][x + 1] == DARK and src[y][x + 2] == 0xE:
                return x
        return None
    for k in range(ROWS):
        for ry in range(ROW_H):
            y = ROW_Y0 + k * ROW_H + ry
            sy = (ROW_Y0 if k == 0 else 24) + ry          # the info panel's first / second row as the pattern
            line = k > 0 and ry == 0
            d = diag(y)
            right = d if d is not None and d < LIST_RIGHT else LIST_RIGHT
            for x in range(0, right):
                if x < SPLIT:
                    img[y][x] = DARK_LINE if line else DARK
                elif x == SPLIT:
                    img[y][x] = EDGE
                else:
                    img[y][x] = LIGHT_LINE if line else LIGHT
            if right == LIST_RIGHT and (d is None or d > LIST_RIGHT):
                img[y][right] = EDGE
                # dark to the panel's own edge
                x = right + 1
                while x < 256 and src[y][x] in (LIGHT, LIGHT_LINE, 3):
                    img[y][x] = DARK_LINE if line else DARK
                    x += 1
    free = _free_tiles(narc, g, 1)
    new = _tilize(img, g, s, 0, free, 0, 0, 32, 24)
    for tx in range(20):                    # the EXP strip (tile row 19) as on the stats page, in palette 0
        s.put(tx, 19, s74.at(tx, 19) & 0xFFF)
    narc[BOTTOM_NCGR] = gfx5.pack(g.encode(), g_lz)
    print(f'evomoves: learnset panel: {new} new tiles in NCGR {BOTTOM_NCGR}')
    return gfx5.pack(s.encode(), s_lz)


# --- Pokédex: the bottom bar's EVO capsule (drawn on the bar's BG, dexmoves.c dx_capsule) ---------------------------
# The vanilla page capsules (32 x 24 at y 168, screen rows 169-191 = the bar's BG rows 0-22), copied pixel for pixel from
# the game's bar (active: INFO, inactive: FORMS) with their text removed, over the bar's own gradient.
CAPSULE_ON = [
    '00000000000000000000000000000000', '11111111111111111111111111111111', '22134444444444444444444444431222',
    '55146111111111111111111111641555', '71641555555555555555555555146177', '81331555555555555555555555133188',
    '91465555555555555555555555564199', 'a14155555555555555555555555141aa', '1641553435355454444534435551461b',
    '1331555455435454555545545551331c', '1465555455443454445545545555641d', '1415555455454454555545545555141d',
    '1465555455455454555545545555641e', '1331553435455354555534435551331f', '1641555555555555555555555551461f',
    'f14155555555555555555555555141ff', 'f14655555555555555555555555641ff', 'f13315555555555555555555551331ff',
    'f16415555555555555555555551461ff', 'ff146111111111111111111111641fff', 'ff134444444444444444444444431fff',
    'fff1111111111111111111111111ffff', 'ffffffffffffffffffffffffffffffff', 'ffffffffffffffffffffffffffffffff',
]
CAPSULE_ON_COLS = '606060 585858 505050 d0d0d8 f8f8f8 484848 989898 404040 383838 303030 282828 202020 181818 101010 ' \
                  '080808 000000'.split()
CAPSULE_OFF = [
    '00000000000000000000000000000000', '11122222222222222222222222221111', '33245555555555555555555555542333',
    '66250222222222222222222222052666', '72052888888888888888888888250277', '92442888888888888888888888244299',
    'a25088888888888888888888888052aa', '22528888888888888888888888825222', '2052885554454855085885805582502b',
    '2442885888585858585405858882442c', '2508885548585858585555805088052d', '2528885888585855885085888588252d',
    '2508885888585850485885888588052e', '24428858884548585858858550824428', '20528888888888888888888888825028',
    '82528888888888888888888888825288', '82508888888888888888888888805288', '82442888888888888888888888244288',
    '82052888888888888888888888250288', '88250222222222222222222222052888', '88245555555555555555555555542888',
    '88822222222222222222222222228888', '88888888888888888888888888888888', '88888888888888888888888888888888',
]
CAPSULE_OFF_COLS = '606060 585858 282828 505050 888888 b0b0b0 484848 404040 000000 383838 303030 202020 181818 101010 ' \
                   '080808'.split()
CAPSULE_TEXT_ROWS = 8           # glyph top (art row; screen y 177)
# the capsules' letters (6 rows; 2 = the text colour, 1 = its lighter edge), as in INFO / AREA / FORMS (EN) and
# Info. / Voice / Forme (JP)
CAP_GLYPHS = {
    'E': ['2222', '2...', '222.', '2...', '2...', '2222'],
    'V': ['2...2', '2...2', '1...1', '.2.2.', '.2.2.', '..2..'],
    'O': ['1221', '2..2', '2..2', '2..2', '2..2', '1221'],
    'e': ['2221', '2...', '221.', '2...', '2...', '2221'],    # JP: uppercase E in the Forme style
    'v': ['...', '...', '2.2', '2.2', '1.1', '.2.'],
    'o': ['...', '...', '121', '2.2', '2.2', '121'],
    '.': ['.', '.', '.', '.', '.', '2'],
}
CAP_TEXT = {'en': 'EVO', 'jp': 'evo.'}
# text colours: active (main, edge), inactive
CAP_INK = {'on': ('f8f8f8', 'd0d0d8'), 'off': ('b0b0b0', '888888')}
CAP_PALROWS = (9, 10, 11)       # main BG palette rows of the capsule's tile rows (free in every Pokédex screen)
CAP_TILE0 = 480                 # first tile in the bar BG's char block (tiles 5-511 are unused)


def capsule(lang):
    """-> (tiles: 24 x 32 bytes: active then inactive, each 3 tile rows x 4 tiles; palettes: 3 rows of 16 BGR555)"""
    def img(art, cols, ink):
        px = [[cols[int(ch, 16)] for ch in row] for row in art]
        bg = px[CAPSULE_TEXT_ROWS - 2][16]
        for y in range(CAPSULE_TEXT_ROWS, CAPSULE_TEXT_ROWS + 6):
            for x in range(6, 26):
                px[y][x] = bg
        text = CAP_TEXT[lang]
        w = sum(len(CAP_GLYPHS[c][0]) for c in text) + len(text) - 1
        x = 16 - (w + 1) // 2
        for c in text:
            g = CAP_GLYPHS[c]
            for y, row in enumerate(g):
                for xx, v in enumerate(row):
                    if v != '.':
                        px[CAPSULE_TEXT_ROWS + y][x + xx] = ink[0] if v == '2' else ink[1]
            x += len(g[0]) + 1
        return px
    on = img(CAPSULE_ON, CAPSULE_ON_COLS, CAP_INK['on'])
    off = img(CAPSULE_OFF, CAPSULE_OFF_COLS, CAP_INK['off'])
    pals, tiles = [], [[], []]
    for tr in range(3):
        cols = []
        for im in (on, off):
            for y in range(tr * 8, tr * 8 + 8):
                for c in im[y]:
                    if c not in cols:
                        cols.append(c)
        assert len(cols) <= 15, f'evomoves: capsule tile row {tr} has {len(cols)} colours'
        pals.append([0] + [_bgr(tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))) for c in cols] + [0] * (15 - len(cols)))
        for s, im in enumerate((on, off)):
            for tc in range(4):
                b = bytearray(32)
                for y in range(8):
                    for x in range(8):
                        v = cols.index(im[tr * 8 + y][tc * 8 + x]) + 1
                        b[y * 4 + x // 2] |= v << (4 * (x & 1))
                tiles[s].append(bytes(b))
    return b''.join(tiles[0] + tiles[1]), pals


def capsule_header(lang):
    t, pals = capsule(lang)
    words = struct.unpack(f'<{len(t) // 4}I', t)
    return ('/* generated by qol/evomoves.py: the Pokédex bar\'s EVO capsule (active, inactive: 3 x 4 tiles each) */\n'
            f'#define CAP_TILE0 {CAP_TILE0}\n'
            f'static const u8 cap_palrow[3] = {{{", ".join(map(str, CAP_PALROWS))}}};\n'
            'static const u32 cap_tiles[24 * 8] = {\n    ' +
            ',\n    '.join(', '.join(f'{w:#010x}' for w in words[i:i + 8]) for i in range(0, len(words), 8)) + '\n};\n'
            'static const u16 cap_pal[3][16] = {\n' +
            ''.join('    {' + ', '.join(f'{c:#06x}' for c in p) + '},\n' for p in pals) + '};\n')


# --- Pokédex: the EVO/MOVES page's palettes (a/1/5/7, appended; dexmoves.c DX_FILE_PAL_*) ---------------------------
DEX_ARC = 'a/1/5/7'
GREEN = {1: (0x29, 0x9C, 0x3E), 2: (0x3A, 0xBD, 0x52), 3: (0x1A, 0x6B, 0x29), 4: (0x1D, 0x4A, 0x22)}
# our boxes and text (the FORMS page's box: dark fill, gold border; white text): DX_FILE_PAL_BOX row 0
BOX_PAL = [(0, 0, 0), (0x29, 0x29, 0x31), (0xF6, 0xD5, 0x18), (0x83, 0x73, 0x18), (0xFF, 0xFF, 0xFF), (0x6A, 0x6A, 0x6A),
           (0x8B, 0xC5, 0xF6), (0x29, 0x52, 0x83), (0xF6, 0xD5, 0x18), (0x6A, 0x5A, 0x10), (0x5A, 0x5A, 0x5A),
           (0x39, 0x39, 0x41), (0xA4, 0xA4, 0xAC), (0, 0, 0), (0, 0, 0), (0, 0, 0)]
# the INFO page's base stats (dexstats.c K_*): the same box and text colours, the bars' track and six bar colours by
# value (< 50 red, < 70 orange, < 90 yellow, < 110 lime, < 130 green, 130+ teal; the modern games' / sites' scale)
STATS_PAL = [(0, 0, 0), (0x29, 0x29, 0x31), (0xF6, 0xD5, 0x18), (0x83, 0x73, 0x18), (0xFF, 0xFF, 0xFF),
             (0x6A, 0x6A, 0x6A), (0x6A, 0x5A, 0x10), (0x52, 0x52, 0x5A), (0x39, 0x39, 0x41), (0xA4, 0xA4, 0xAC),
             (0xF3, 0x44, 0x44), (0xFF, 0x7F, 0x0F), (0xFF, 0xDD, 0x57), (0xA0, 0xE5, 0x15), (0x23, 0xCD, 0x5E),
             (0x00, 0xC2, 0xB8)]


def _nclr_rows(d):
    off = struct.unpack_from('<H', d, 0xC)[0]
    return off + 8 + struct.unpack_from('<I', d, off + 0x14)[0]


def _bgr(c):
    r, g, b = c
    return (r >> 3) | (g >> 3) << 5 | (b >> 3) << 10


def _recolor(d, row, cols):
    """NCLR bytes with palette `row`'s colours replaced ({index: (r, g, b)})"""
    d = bytearray(d)
    base = _nclr_rows(d) + 32 * row
    for i, c in cols.items():
        struct.pack_into('<H', d, base + 2 * i, _bgr(c))
    return bytes(d)


def dex_palettes(ctx):
    """five NCLR members for a/1/5/7: the grids' theme row (bottom: NCLR 1 row 0, top: NCLR 2 row 0) and the header's
    (NCLR 4 row 0), each red turned green, our box / text palette (row 0) and the base stats' palette (row 0)"""
    import ndsfs
    fid = ctx.fid(DEX_ARC)
    raw = ctx.rom.file(fid)
    narc = ndsfs.narc(raw)
    first = len(narc)
    grid_cols = {k: GREEN[k] for k in (1, 2, 3)}
    new = [_recolor(narc[1], 0, grid_cols), _recolor(narc[2], 0, grid_cols), _recolor(narc[4], 0, GREEN),
           _recolor(narc[1], 0, dict(enumerate(BOX_PAL))), _recolor(narc[1], 0, dict(enumerate(STATS_PAL)))]
    print(f'evomoves: Pokédex palettes: a/1/5/7 members {first}-{first + len(new) - 1}')
    return {fid: ndsfs.pack_narc(narc + new, ndsfs.narc_layout(raw))}


def files(ctx):
    import ndsfs
    fid = ctx.fid(SUMMARY_ARC)
    raw = ctx.rom.file(fid)
    narc = ndsfs.narc(raw)
    assert len(narc) == NEW_LABEL, f'evomoves: a/0/7/7 has {len(narc)} members, expected {NEW_LABEL}'
    lab = label(ctx, narc)
    bot = bottom(ctx, narc)
    narc += [lab, bot]
    out = {fid: ndsfs.pack_narc(narc, ndsfs.narc_layout(raw))}
    out.update(dex_palettes(ctx))
    return out
