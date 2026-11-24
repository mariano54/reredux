"""ReRedux xmenu (xmenu.c): the X menu always opens with the cursor shown on POKÉMON, so X then A opens the party
(vanilla opens it with the cursor hidden: the first A only showed it). Also when the menu comes back after closing
an app (vanilla: on that app's item), wherever the layout puts the POKÉMON icon. No POKÉMON icon (no Pokémon yet):
vanilla. Touch input, the C-Gear, the Y item and the rest of the menu are unchanged. Always on: a menu default,
not a speed-up (no flag)."""

SYMS = {
    'xm_GetMenuCursor': 0x020173ED,         # ARM9 FUN_020173EC: GameData+0x1CB, the menu's remembered item
    'xm_MenuUpdateCursor': 0x021A07AD,      # OVL_36 FUN_021A07AC: move the cursor, light its icon
    'xm_ClactSetDrawEnable': 0x0204C125,    # ARM9 FUN_0204C124
    'xm_SubscreenMode': 0x021984CD,         # OVL_36 FUN_021984CC: the field subscreen's mode (1 = the menu)
    'xm_MenuSetCursorItem': 0x0219886D,     # OVL_36 FUN_0219886C(subscreen, id): cursor on that item
}

PATCHES = [
    # ov36 FUN_0219FA10 (the field menu's create), opened by X: cursor (0, 0), then `bl FUN_021A07AC`
    dict(where='ov36', addr=0x0219FB02, kind='bl', orig=0x021A07AD, target='xmenu_open',
         note='X menu: cursor shown on POKEMON'),
    # ... back from an app: `bl FUN_020173EC` (the remembered item) before FUN_021A04EC(menu, id)
    dict(where='ov36', addr=0x0219FB10, kind='bl', orig=0x020173ED, target='xmenu_hook',
         note='X menu after an app: cursor on POKEMON'),
    # ov12 FUN_0215AA74 (EventFieldMenu's return callback): `bl FUN_0219886C(subscreen, remembered item)`
    dict(where='ov12', addr=0x0215AA88, kind='bl', orig=0x0219886D, target='xmenu_back',
         note='X menu after an app: cursor on POKEMON (the event side)'),
]
