/* ReRedux xmenu: the X menu (the field menu on the touch screen) always opens with the cursor shown on POKÉMON,
 * so X then A opens the party. Always on (a menu default, not a speed-up).
 *
 * Vanilla (ov36): the menu's create function FUN_0219FA10 lays out its items (FUN_021A0274: up to six icons in a
 * 2 x 3 grid + the close button; menu+0x34 + i * 0x1C: +0 present, +8 item id; ids 1 POKÉMON, 2 POKÉDEX, 3 BAG,
 * 4 TRAINER, 5 SAVE, 6 OPTIONS, 7 empty, 8 the Subway's RETIRE). The layout depends on the place and progress
 * (FUN_021A01C4; e.g. no POKÉMON or POKÉDEX icon before the first Pokémon, flag 0x961), so POKÉMON is looked up
 * by id. menu+0x1E / +0x1F: the cursor's column / row; +0x2C: cursor shown (key mode); +0x124: the cursor's cell
 * actor; FUN_021A07AC moves the cursor and lights the cursor's icon (only when shown), unlighting the previous one.
 * Two ways in:
 *  - X (EventFieldMenu_Create first sets GFL_UI touch-or-key to touch): the cursor goes to slot 0 but stays
 *    hidden, and the first A (any key) only shows it; a second A opens the item.
 *  - back from an app (party, bag, ...): the cursor goes to the remembered item (GameData+0x1CB, FUN_020173EC,
 *    written by EventFieldMenu when an item is chosen), shown or hidden by the touch-or-key mode.
 * Here, when the menu holds POKÉMON:
 *  - X: ov36 0x0219FB02 `bl FUN_021A07AC` -> xmenu_open: cursor on POKÉMON and shown (as the first key press
 *    shows it, without its sound), then FUN_021A07AC lights it;
 *  - back from an app: ov36 0x0219FB10 `bl FUN_020173EC` -> xmenu_hook: POKÉMON's id instead of the remembered
 *    one (still read, and still written by vanilla), cursor shown; the vanilla code after it moves the cursor
 *    there, shows it and lights the icon;
 *  - and again a moment later, when EventFieldMenu's return callback (ov12 0x0215AA88 `bl FUN_0219886C`) puts
 *    the cursor on the event's remembered item: xmenu_back passes POKÉMON's id instead.
 * Without a POKÉMON icon both stay vanilla. Touch input is unchanged (a touch hides the cursor, as in vanilla). */
#include "qol.h"

u32 xm_GetMenuCursor(void *menu_save);          /* FUN_020173EC: GameData+0x1CB */
void xm_MenuUpdateCursor(u8 *menu);             /* FUN_021A07AC */
void xm_ClactSetDrawEnable(void *clact, u32 on);/* FUN_0204C124 */

#define ITEM_POKEMON    1
#define SLOTS           6
#define SLOT_SIZE       0x1C

typedef struct {
    u32 calls;          /* menu opens seen (both ways) */
    u8 last_saved;      /* the remembered id at the last open (0xFF: opened by X, not read) */
    u8 last_used;       /* the id the cursor was put on (0xFF: vanilla, X without POKÉMON) */
    u8 last_slot;       /* POKÉMON's slot (0xFF: none) */
    u8 last_way;        /* 1 X, 2 back from an app */
    u8 *menu;           /* the last menu (tests read its cursor) */
    u16 backs;          /* return callbacks seen (xmenu_back) */
    u8 last_back;       /* the id the last one put the cursor on */
    u8 pad;
} XmenuDbg;

XmenuDbg xmenu_dbg;

static u32 pokemon_slot(u8 *menu)
{
    u32 i;
    for (i = 0; i < SLOTS; i++) {
        u8 *s = menu + 0x34 + i * SLOT_SIZE;
        if (*(u32 *)s == 1 && *(u32 *)(s + 8) == ITEM_POKEMON)
            return i;
    }
    return 0xFF;
}

static void note(u8 *menu, u32 way, u32 saved, u32 used, u32 slot)
{
    xmenu_dbg.calls++;
    xmenu_dbg.menu = menu;
    xmenu_dbg.last_way = way;
    xmenu_dbg.last_saved = saved;
    xmenu_dbg.last_used = used;
    xmenu_dbg.last_slot = slot;
}

/* X: in FUN_0219FA10's "fresh open" branch (cursor 0,0 and dirty already set) */
void xmenu_open(u8 *menu)
{
    u32 slot = pokemon_slot(menu);
    if (slot != 0xFF) {
        menu[0x1E] = slot & 1;
        menu[0x1F] = slot >> 1;
        *(u32 *)(menu + 0x24) = 1;
        *(u32 *)(menu + 0x2C) = 1;
        xm_ClactSetDrawEnable(*(void **)(menu + 0x124), 1);
    }
    note(menu, 1, 0xFF, slot != 0xFF ? ITEM_POKEMON : 0xFF, slot);
    xm_MenuUpdateCursor(menu);
}

/* back from an app: the id the cursor goes to */
u32 xmenu_pick(void *menu_save, u8 *menu)
{
    u32 saved = xm_GetMenuCursor(menu_save), use = saved, slot = pokemon_slot(menu);
    if (slot != 0xFF) {
        use = ITEM_POKEMON;
        *(u32 *)(menu + 0x2C) = 1;
    }
    note(menu, 2, saved, use, slot);
    return use;
}

/* back from an app, a moment later: EventFieldMenu's return callback (ov12 FUN_0215AA74) puts the cursor on the item
 * the event remembers (FUN_0219886C(subscreen, id) -> FUN_021A04EC(menu, id) when the subscreen shows the menu) */
u32 xm_SubscreenMode(void *sub);                /* OVL_36 FUN_021984CC: 1 = the field menu */
void xm_MenuSetCursorItem(void *sub, u32 id);   /* OVL_36 FUN_0219886C */

void xmenu_back(void *sub, u32 id)
{
    if (xm_SubscreenMode(sub) == 1) {
        u8 *menu = *(u8 **)((u8 *)sub + 0x20);
        u32 slot = pokemon_slot(menu);
        if (slot != 0xFF) {
            *(u32 *)(menu + 0x2C) = 1;
            xmenu_dbg.last_saved = id;
            id = ITEM_POKEMON;
        }
        xmenu_dbg.backs++;
        xmenu_dbg.last_back = id;
    }
    xm_MenuSetCursorItem(sub, id);
}

/* ov36 0x0219FB10 (in FUN_0219FA10; r0 = the GameData menu-save struct, r4 = the menu):
 * `bl FUN_020173EC` -> here; the caller goes on with `adds r1, r0, #0; adds r0, r4, #0; bl FUN_021A04EC` */
__attribute__((naked)) void xmenu_hook(void)
{
    __asm__ volatile(
        ".syntax unified\n"
        "push {r4, lr}\n"
        "movs r1, r4\n"
        "ldr r3, =xmenu_pick\n"
        "blx r3\n"
        "pop {r4, pc}\n"
        ".ltorg\n"
        ".syntax divided\n");
}
