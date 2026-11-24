"""ReRedux rules (rules.c): Nuzlocke rules, species limit, no items in battle, Challenge Mode by
default, the city, and the RulesCmd script command (0x91) the intro menu (menu.py) uses. Spec:
build/research_rules.md.

Saved flags 0x5D0-0x5DE and vars 0x4197-0x419A, 0x41A0-0x41AA (rules.h); all off on a new game except
the difficulty (Challenge). Hooks: see rules.c. Key System out of play: no key is unlocked (new save,
RulesCmd 0); Unova Link's difficulty and City Key handlers (overlay 332) answer "key not unlocked" to
every change (the chamber keys from the Underground Ruins still work there). Species limit:
rules_family.h (HEADERS) maps every species to its evolution family, from the ROM's evolution data."""

# flags / vars (keep in sync with rules.h; menu.py imports these)
FLAGS = dict(release=0x5D0, graveyard=0x5D1, gameover=0x5D2, first=0x5D3, dupes=0x5D4, shiny=0x5D5,
             nickname=0x5D6, statics=0x5D7, noitems=0x5D8, notraineritems=0x5D9,
             speed_off=0x5DA, turbo_off=0x5DB,
             autorun_off=0x5DC, quicksave=0x5DD, quicksurf=0x5DE)     # qol2.c / qol2.py
VAR_MENU_DONE, VAR_DIFFICULTY, VAR_SPECIES_LIMIT, VAR_CITY = 0x4197, 0x4198, 0x4199, 0x419A
RV_DEATHS = 0x41AA                   # Pokémon lost to the rules (shown by the settings view)
RULES_CMD = 0x91                     # script command id (free slot of the OVL_12 command table)
SCRIPT_CMD_TABLE, SCRIPT_CMD_PERMS = 0x0216B538, 0x0216B1F0

SYMS = {
    # ARM9
    'GameData_GetSaveControl': 0x02017935,
    'GameData_GetPlayerState': 0x020171F5,
    'PlayerState_GetZoneID': 0x02017545,
    'ZoneData_GetPlaceNameID': 0x02018C81,
    'GameData_GetPokedex': 0x0200D191,
    'GameData_GetBoxSaveAccessor': 0x02017365,
    'EventWork_FlagSet': 0x020191D9,
    'EventWork_FlagReset': 0x02019201,
    'EventWork_GetWkPtr': 0x02019295,
    'getKeyInfoSaveBlk': 0x020104A5,
    'KeyInfo_Init': 0x02010475,
    'KeyInfo_SetObtained': 0x020104B1,
    'KeyInfo_SetUnlocked': 0x020104E1,
    'SetGameDifficulty': 0x02010515,
    'GetGameDifficulty': 0x02010529,
    'PokeDex_IsCaught': 0x0200D661,
    'PokeParty_RemovePkm': 0x0201FDA9,
    'howManyPokesAreAbleToFight': 0x0201FE31,
    'BoxSaveAccessor_InsertPkmCore': 0x020077E9,
    'BoxSaveAccessor_GetAvailableBoxCount': 0x02007969,
    'BoxSaveAccessor_GetBox': 0x02007E15,
    'PokePasoParam_GetParam': 0x0201CD89,
    'KeyInfo_SetCity': 0x02010551,                 # KeyInfo +0x2C (2 values): Unova Link's City Key
    'KeyInfo_GetCity': 0x02010565,
    'GameData_GetMapVariant': 0x02017215,          # FUN_02017214: {u16 set, u16 city} (ov35 FUN_0217ED20)
    'MapVariant_Set': 0x020187B1,                  # FUN_020187B0(i, city), i = 0, 1 (OV12_FUN_0215CD58)
    'GCTX_HIDGetPressedKeys': 0x0203DEFD,
    'FieldMenuAllowed': 0x02027ACD,                # FUN_02027ACC: checked before the X menu / Y item
    # OVL_12
    'EventScriptCall_Create': 0x0215366D,          # (gsys, script id, actor, heap) -> GameEvent
    'FieldEventCheck_Rest': 0x02176EC5,            # FUN_02176EC4: the event check's last step
    'BtlSetup_GetParty': 0x02017D11,
    'BagSave_AddItem': 0x02008269,
    'GFL_MsgDataLoadStrbuf': 0x02048839,
    'GFL_HIDDoSoftReset': 0x0203D4F9,
    'pokerusSpread': 0x02020649,
    # OVL_12
    'FUN_02168EFC': 0x02168EFD,
    'IsReturnLocationNonLeaguePokeCen': 0x0215A095,
    'EventMapChangeBlackout_CreateExternal': 0x0215A76D,
    # OVL_167
    'BattleTrainerItem_Get': 0x0219D89D,
    'FUN_0219CBB0': 0x0219CBB1,                    # friendship loss of a fainted player Pokémon
    'BPP_GetID': 0x021BAC41,
    'PokeCon_GetBPP': 0x0219D21D,                  # (main + 0x1B0, id)
    'BPP_GetSrcData': 0x021BB045,                  # -> its PokemonParam
    # OVL_307 (egg hatch)
    'EggHatch_YesNo': 0x021DE72D,                  # FUN_021DE72C: the nickname question's answer
    # OVL_286
    'BagBattle_Refresh': 0x021F4C25,
}

PATCHES = [
    dict(where='ov12', addr=SCRIPT_CMD_TABLE + 4 * RULES_CMD, kind='ptr', orig=0, target='rules_script_cmd',
         note='script command 0x91 RulesCmd'),
    dict(where='ov12', addr=SCRIPT_CMD_PERMS + RULES_CMD, kind='u8', orig=0, target=7,
         note='script command 0x91: allowed in every script context'),
    dict(where='arm9', addr=0x02010246, kind='bl', orig=0x02010475, target='rules_keyinfo_init',
         note='new save: Challenge Mode + Challenge Key'),
    dict(where='ov12', addr=0x02168690, kind='bl', orig=0x02168EFD, target='rules_wild_start_veneer',
         note='wild battle start: area / dupes / shiny'),
    dict(where='ov286', addr=0x021F6522, kind='bl', expect=bytes.fromhex('201c2930'),
         target='rules_bag_gate_veneer', note='battle Bag: refuse balls / items'),
    dict(where='ov167', addr=0x021B91C0, kind='bl', orig=0x0219D89D, target='rules_trainer_item',
         note='trainer AI items'),
    dict(where='ov166', addr=0x0219CF7A, kind='bl', orig=0x02020649, target='rules_after_sync_veneer',
         note='after battle: release / graveyard'),
    dict(where='ov307', addr=0x021DDE58, kind='bl', orig=0x021DE72D, target='rules_egg_nick',
         note='egg hatch: always nickname'),
    dict(where='ov167', addr=0x0219CBA8, kind='bl', orig=0x0219CBB1, target='rules_faint',
         note='a player Pokémon fainted: mark it (strict release)'),
    dict(where='ov166', addr=0x0219D102, kind='bl', expect=bytes.fromhex('a06a0021'),
         target='rules_nick_veneer', note='catch: always nickname'),
    dict(where='ov12', addr=0x0215A172, kind='bl', orig=0x0215A095, target='rules_lose_kind',
         note='whiteout kind: 3 = game over'),
    dict(where='ov12', addr=0x0215A10E, kind='bl', orig=0x0215A76D, target='rules_blackout',
         note='whiteout warp: soft reset on game over'),
    dict(where='ov295', addr=0x0219D534, kind='bytes', expect=bytes.fromhex('201c391c'),
         target=bytes.fromhex('411c201c'), note='whiteout text: bank 42 line kind + 1'),
    # script list menus: up to 7 rows without scrolling in the intro settings menu (rules_list_max)
    dict(where='ov12', addr=0x02155458, kind='bl', expect=bytes.fromhex('06210628'),
         target='rules_list_rows_veneer', note='list menu: visible rows (7 in the intro menu)'),
    dict(where='ov12', addr=0x0215545C, kind='bytes', expect=bytes.fromhex('00d8'), target=bytes.fromhex('04e0'),
         note='list menu: b 0x02155468 after the rows veneer'),
    # field event check (FUN_021814DC): its fallback step -> rules_view_veneer (SELECT: settings view)
    dict(where='ov36', addr=0x02181840, kind='bl', orig=0x02176EC5, target='rules_view_veneer',
         note='SELECT in the free field: settings view'),
    # Unova Link Key System (ov332): the difficulty / City Key "set" handlers (r5 = the picked value; the
    # current value already returned 1) refuse every change: 2 ("You cannot select this item until it's
    # been unlocked with the ... Key") for values that have a key (Easy, Challenge; White Forest), 1 (no
    # change, no message) for the others (Normal; Black City), which have no key message.
    #   movs r0, #2|#1; cmp r5, #1; bne 1f; movs r0, #1|#2; 1: add sp, #4; pop {r3-r6, pc}
    dict(where='ov332', addr=0x021C4994, kind='bytes', expect=bytes.fromhex('032d3ada002d02d0022d09d0'),
         target=bytes.fromhex('0220012d00d1012001b078bd'), note='Unova Link: difficulty changes refused'),
    dict(where='ov332', addr=0x021C4AA8, kind='bytes', expect=bytes.fromhex('022d53da206852f641ff42f6'),
         target=bytes.fromhex('0120012d00d1022001b078bd'), note='Unova Link: City Key changes refused'),
]


def HEADERS(ctx):
    """rules_family.h: species -> evolution family id, the smallest species id of its evolution graph
    (pre-evolutions, babies, branches and Shedinja join their line; forms share the species id)"""
    import ndsfs, struct
    entries = ndsfs.narc(ctx.rom.file(ctx.fid('a/0/1/9')))
    n = 650                                         # species 0..649 (form entries follow)
    parent = list(range(n))

    def root(x):
        while parent[x] != x:
            x = parent[x]
        return x
    for s in range(1, n):
        d = entries[s]
        for k in range(0, len(d) - len(d) % 6, 6):
            method, param, target = struct.unpack_from('<HHH', d, k)
            if method and 0 < target < n:
                a, b = root(s), root(target)
                if a != b:
                    parent[max(a, b)] = min(a, b)
    fam = [root(s) for s in range(n)]
    rows = [', '.join(str(v) for v in fam[i:i + 16]) for i in range(0, n, 16)]
    # the settings view's event script: menu.py appends it as the next entry of common script 1230
    # (global ids 2000 + entry)
    view = ndsfs.narc(ctx.rom.file(ctx.fid('a/0/5/6')))[1230]
    k = 0
    while struct.unpack_from('<H', view, 4 * k)[0] != 0xFD13:
        k += 1
    return {'rules_family.h': '/* generated by qol/rules.py HEADERS from the ROM evolution data (a/0/1/9) */\n'
            f'#define RULES_FAMILY_N {n}\nstatic const u16 rules_family[RULES_FAMILY_N] = {{\n    ' +
            ',\n    '.join(rows) + '\n};\n',
            'rules_view.h': f'/* generated by qol/rules.py HEADERS: menu.py settings view (common script 1230) */\n'
                            f'#define RULES_VIEW_SCRIPT {2000 + k}\n'}


TEXTS = [
    dict(bank=('system', 1), key='RULES_CATCH_AREA',
         en="You already had this area's\nencounter! It can't be caught.",
         ja='この　場所では　もう\nポケモンに　出会っている！'),
    dict(bank=('system', 1), key='RULES_CATCH_DUPE',
         en="You've already caught this species!\nIt can't be caught. (Dupes clause)",
         ja='この　ポケモンは　もう　つかまえた！\nボールは　投げられない！'),
    dict(bank=('system', 1), key='RULES_CATCH_LIMIT',
         en="You already have this species!\nIt can't be caught. (Species limit)",
         ja='この　しゅるいの　ポケモンは\nもう　持っている！'),
    dict(bank=('system', 1), key='RULES_CATCH_LINE',
         en="You already have a Pokémon of this\nevolution line! (Species limit)",
         ja='この　ポケモンの　進化の　なかまを\nもう　持っている！'),
    dict(bank=('system', 1), key='RULES_NO_ITEMS',
         en="The rules of this adventure don't\nallow items in battle!",
         ja='この　冒険の　ルールで\n勝負中に　道具は　使えない！'),
    dict(bank=('system', 42), key='RULES_GAME_OVER', id=4,
         en='{0100:1} has no Pokémon left\nthat can fight...\n\nThe adventure is over.',
         ja='戦える　ポケモンが　もう　いない……\n\n{0100:1}の　冒険は\nここで　終わった'),
]
