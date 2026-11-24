/* ReRedux rules (rules.py): Nuzlocke rules, species limit, no items in battle, Challenge Mode by
 * default, the city (Black City / White Forest) and script command 0x91 for the intro menu (menu.py).
 * The Key System is out of play: no keys are unlocked and Unova Link refuses difficulty / city changes
 * (rules.py ov332 patches). Spec: build/research_rules.md.
 *
 * Hooks (rules.py PATCHES):
 *   arm9  0x02010246  new save: KeyInfo_Init -> rules_keyinfo_init (Challenge Mode, Challenge Key)
 *   ov12  0x02168690  wild battle start (EventWildBattleCall_CreateCore) -> rules_wild_start
 *   ov286 0x021F6522  battle Bag "use item" check -> rules_bag_gate_veneer
 *   ov167 0x021B91C0  trainer AI item slots -> rules_trainer_item
 *   ov166 0x0219CF7A  after the battle party is copied back -> rules_after_sync_veneer
 *   ov166 0x0219D102  "give a nickname?" answer after a catch -> rules_nick_veneer
 *   ov12  0x0215A172  whiteout kind -> rules_lose_kind (3 = game over, ov295 shows bank 42 line 4)
 *   ov12  0x0215A10E  whiteout warp -> rules_blackout (soft reset on game over)
 *   ov12  script command table slot 0x91 -> rules_script_cmd */
#include "rules.h"
#include "qol_texts.h"

#define G_GAMESYSTEM (*(void *volatile *)0x021410F4)   /* g_GameSystem (GameSystem_Init 0x020167E2) */

RulesDbg rules_dbg = { .magic = 0x454C5552, .difficulty = 0xFF };
u8 g_catch_block;
static u8 g_game_over;
static u8 faint_n;                      /* Pokémon marked dead in the running battle (rules_faint) */

void *rules_gd(void)
{
    void *g = G_GAMESYSTEM;
    return g ? GSYS_GetGameData(g) : 0;
}

int rules_flag(void *gd, u32 flag)
{
    return gd && EventWork_FlagGet(GameData_GetEventWork(gd), flag);
}

/* Area = the location (place name) id; same-named places merged: Victory Road 134 -> 40,
 * Mistralton Cave 74 -> 54. All Hidden Grottos are location 143 (one area). */
static u32 area_of(void *gd)
{
    u32 loc = ZoneData_GetPlaceNameID(PlayerState_GetZoneID(GameData_GetPlayerState(gd)));
    if (loc == 134)
        loc = 40;
    else if (loc == 74)
        loc = 54;
    return loc;
}

static u16 *area_word(void *gd, u32 loc)
{
    return EventWork_GetWkPtr(GameData_GetEventWork(gd), RV_AREAS + (loc >> 4));
}

static int area_used(void *gd, u32 loc)
{
    return loc < RULES_AREAS && (*area_word(gd, loc) >> (loc & 15) & 1);
}

/* Encounters only count once the player can catch: any Poke Ball in the Bag. */
static int has_balls(void *gd)
{
    void *bag = GameData_GetBag(gd);
    u32 i;
    for (i = 1; i <= 16; i++)                      /* Master Ball .. Cherish Ball */
        if (BagSave_GetItemCountByID(bag, i, HEAP_FIELD))
            return 1;
    for (i = 492; i <= 500; i++)                   /* Fast Ball .. Park Ball */
        if (BagSave_GetItemCountByID(bag, i, HEAP_FIELD))
            return 1;
    return BagSave_GetItemCountByID(bag, 576, HEAP_FIELD) != 0;   /* Dream Ball */
}

/* ---- new save: Challenge Mode ---------------------------------------------------------------- */

void KeyInfo_Init(void *ki);

/* No key is obtained or unlocked: the Key System is out of play (difficulty and city are chosen in the
 * intro menu; Unova Link's difficulty / city handlers refuse changes, rules.py ov332 patches). */
void rules_keyinfo_init(void *ki)
{
    KeyInfo_Init(ki);
    SetGameDifficulty(ki, 2);
    rules_dbg.ki = (u32)ki;
}

/* ---- script command 0x91: RulesCmd op, dest var, arg (var or const) -------------------------- */

int rules_script_cmd(void *vm, void *env)
{
    u32 op = VM_ReadU16(vm);
    u16 *dest = ScriptReadVar(vm, env);
    u32 arg = ScriptReadAny(vm, env);
    void *gd = GSYS_GetGameData(FieldScriptEnv_GetGameSystem(env));
    void *ki = getKeyInfoSaveBlk(GameData_GetSaveControl(gd));
    rules_dbg.cmd_calls++;
    rules_dbg.ki = (u32)ki;
    rules_dbg.last_cmd = op;
    rules_dbg.last_arg = arg;
    switch (op) {
    case 0:                             /* apply difficulty arg (0 Easy, 1 Normal, 2 Challenge); no keys */
        if (arg > 2)
            arg = 2;
        SetGameDifficulty(ki, arg);
        *dest = rules_dbg.difficulty = GetGameDifficulty(ki);
        break;
    case 1:                             /* current difficulty */
        *dest = GetGameDifficulty(ki);
        break;
    case 2:                             /* area used? (arg = location id, 0 = here) */
        *dest = area_used(gd, arg ? arg : area_of(gd));
        break;
    case 3:                             /* game over from a script */
        GFL_HIDDoSoftReset(0);
        break;
    case 4:                             /* this area's id */
        *dest = area_of(gd);
        break;
    case 5:                             /* apply the city arg (0 Black City + Black Tower, 1 White Forest +
                                         * White Treehollow), as Unova Link's City Key setting does */
        KeyInfo_SetCity(ki, arg ? 1 : 0);
        *dest = KeyInfo_GetCity(ki);
        {   /* what the game-start event does with it (ov35 FUN_0217CBEC -> FUN_0217ED20 +
             * OV12_FUN_0215CD58): the map variant state {1, city} and the two zone switches */
            u16 *mr = GameData_GetMapVariant(gd);
            mr[0] = 1;
            mr[1] = *dest;
            MapVariant_Set(0, *dest);
            MapVariant_Set(1, *dest);
        }
        break;
    }
    return 0;
}

/* ---- species limit: the party or the PC (not the graveyard box) holds that species / line ----- */

#include "rules_family.h"               /* generated by rules.py HEADERS: rules_family[species] */

static u32 family_of(u32 sp)
{
    return sp < RULES_FAMILY_N ? rules_family[sp] : sp;
}

static int limit_match(u32 a, u32 b, u32 mode)
{
    return a && (mode == 1 ? a == b : family_of(a) == family_of(b));
}

/* -> 1 if a non-egg Pokémon of species sp (mode 1) or of its evolution line (mode 2) is owned */
static int owns_species(void *gd, u32 sp, u32 mode)
{
    void *party = GameData_GetParty(gd), *acc = GameData_GetBoxSaveAccessor(gd);
    int i, n = PokeParty_GetPkmCount(party);
    u32 b, boxes, skip;
    for (i = 0; i < n && i < 6; i++) {
        void *pp = PokeParty_GetPkm(party, i);
        if (limit_match(PokeParty_GetParam(pp, PARAM_SPECIES, 0), sp, mode) &&
            !PokeParty_GetParam(pp, PARAM_EGG, 0))
            return 1;
    }
    boxes = BoxSaveAccessor_GetAvailableBoxCount(acc);
    if (boxes > 24)
        boxes = 24;
    skip = rules_flag(gd, RF_RELEASE) && rules_flag(gd, RF_GRAVEYARD) && boxes ? boxes - 1 : 0xFF;
    for (b = 0; b < boxes; b++) {
        u8 *box;
        if (b == skip)
            continue;                   /* the graveyard box doesn't count */
        box = BoxSaveAccessor_GetBox(acc, b);
        for (i = 0; i < 30; i++) {
            void *ppp = box + 0x88 * i;
            if (limit_match(PokePasoParam_GetParam(ppp, PARAM_SPECIES, 0), sp, mode) &&
                !PokePasoParam_GetParam(ppp, PARAM_EGG, 0))
                return 1;
        }
    }
    return 0;
}

/* ---- wild battle start: area / dupes / shiny / species limit -------------------------------- */

void FUN_02168EFC(void *setup, u32 z);

void rules_wild_start(void *setup, u32 z, u8 *work)
{
    void *gd, *pp;
    u32 sp, loc, limit;
    int shiny, is_static;
    FUN_02168EFC(setup, z);             /* the replaced call */
    g_catch_block = CATCH_OK;
    faint_n = 0;
    gd = GSYS_GetGameData(*(void **)work);
    rules_dbg.wild_starts++;
    rules_dbg.last_gd = (u32)gd;
    limit = *EventWork_GetWkPtr(GameData_GetEventWork(gd), RV_SPECIES_LIMIT);
    if (limit > 2)
        limit = 0;
    if (!rules_flag(gd, RF_FIRST) && !rules_flag(gd, RF_DUPES) && !limit)
        return;
    pp = PokeParty_GetPkm(BtlSetup_GetParty(setup, 1), 0);
    sp = PokeParty_GetParam(pp, PARAM_SPECIES, 0);
    shiny = PokeParty_IsRare(pp);
    is_static = work[8];                /* EventWildBattleCall_CreateStatic (scripts, grottos) */
    loc = area_of(gd);
    rules_dbg.last_species = sp;
    rules_dbg.last_shiny = shiny;
    rules_dbg.last_static = is_static;
    rules_dbg.last_area = loc;
    if (shiny && rules_flag(gd, RF_SHINY))
        goto out;                       /* shiny clause: always catchable, area not used */
    if (limit && owns_species(gd, sp, limit)) {
        g_catch_block = limit == 1 ? CATCH_LIMIT : CATCH_LINE;  /* every wild battle, statics too; */
        rules_dbg.limit_blocks++;
        goto out;                       /* like the dupes clause the area is not used */
    }
    if (is_static && !rules_flag(gd, RF_STATICS))
        goto out;                       /* statics and grottos don't count */
    if (rules_flag(gd, RF_DUPES) && PokeDex_IsCaught(GameData_GetPokedex(gd), sp)) {
        g_catch_block = CATCH_DUPE;     /* dupes clause: can't catch, area not used */
        goto out;
    }
    if (rules_flag(gd, RF_FIRST) && loc < RULES_AREAS && has_balls(gd)) {
        u16 *w = area_word(gd, loc);
        u16 bit = 1 << (loc & 15);
        if (*w & bit)
            g_catch_block = CATCH_AREA;
        else {
            *w |= bit;
            rules_dbg.area_marked++;
        }
    }
out:
    rules_dbg.last_block = g_catch_block;
}

/* ---- battle Bag: refuse balls (area used / dupe) and non-ball items ------------------------- */

/* -> 0 allow, else the system bank 1 message to show (the Bag stays open) */
u32 rules_bag_gate(u8 *param, u8 *bagwork)
{
    u32 msg = 0;
    if (bagwork[0x533] == 2) {          /* Poke Balls pocket */
        if (param[0x29]) {              /* wild battle */
            if (g_catch_block == CATCH_AREA)
                msg = TXT_RULES_CATCH_AREA;
            else if (g_catch_block == CATCH_DUPE)
                msg = TXT_RULES_CATCH_DUPE;
            else if (g_catch_block == CATCH_LIMIT)
                msg = TXT_RULES_CATCH_LIMIT;
            else if (g_catch_block == CATCH_LINE)
                msg = TXT_RULES_CATCH_LINE;
        }
    } else if (rules_flag(rules_gd(), RF_NOITEMS))
        msg = TXT_RULES_NO_ITEMS;
    if (msg) {
        rules_dbg.bag_refused++;
        rules_dbg.last_refuse_msg = msg;
    }
    return msg;
}

/* Called by `bl` from FUN_021F644C 0x021F6522 (r4 = param, r5 = bagwork; that function pushed
 * {r4, r5, r6, lr}). Allowed: the two replaced instructions (r0 = param + 0x29), back. Refused:
 * the function's own refusal epilogue (message into the Bag's strbuf, refresh, state 0xD, 0xE). */
__asm__(
"   .section .text.rules_bag_gate_veneer, \"ax\", %progbits\n"
"   .thumb\n"
"   .syntax unified\n"
"   .align 1\n"
"   .global rules_bag_gate_veneer\n"
"   .thumb_func\n"
"   .type rules_bag_gate_veneer, %function\n"
"rules_bag_gate_veneer:\n"
"   push {lr}\n"
"   movs r0, r4\n"
"   movs r1, r5\n"
"   bl rules_bag_gate\n"
"   cmp r0, #0\n"
"   bne 1f\n"
"   movs r0, r4\n"
"   adds r0, #0x29\n"
"   pop {pc}\n"
"1: movs r1, r0\n"
"   add sp, #4\n"
"   ldr r0, [r5, #0xc]\n"
"   ldr r2, [r5, #0x14]\n"
"   ldr r3, =GFL_MsgDataLoadStrbuf\n"
"   blx r3\n"
"   movs r0, r5\n"
"   ldr r3, =BagBattle_Refresh\n"
"   blx r3\n"
"   movs r1, #0xd\n"
"   movs r0, #0x53\n"
"   lsls r0, r0, #4\n"
"   adds r0, #1\n"                  /* 0x531 */
"   strb r1, [r5, r0]\n"
"   movs r0, #0xe\n"
"   pop {r4, r5, r6, pc}\n"
"   .pool\n"
"   .size rules_bag_gate_veneer, . - rules_bag_gate_veneer\n"
);

/* ---- trainers' items ------------------------------------------------------------------------- */

u32 BattleTrainerItem_Get(void *main, u32 client, u32 i);

u32 rules_trainer_item(void *main, u32 client, u32 i)
{
    u32 item = BattleTrainerItem_Get(main, client, i);
    if (item && rules_flag(rules_gd(), RF_NOTRAINERITEMS)) {
        rules_dbg.trainer_items_denied++;
        return 0;
    }
    return item;
}

/* ---- after the battle: release / graveyard the fainted --------------------------------------- */

void pokerusSpread(void *party);

/* ---- strict deaths: a player Pokémon that faints in a battle counts as dead even if revived ---- *
 * OVL_167 ServerControl_CheckFainted -> FUN_0219CB8C (only for the player's own Pokémon in local wild /
 * trainer battles) -> 0x0219CBA8 `bl FUN_0219CBB0` (the fainting friendship loss) -> rules_faint: the
 * Pokémon's personality value is recorded; after the battle (rules_after_sync) it is released like one
 * at 0 HP. The marks are cleared after every battle and at every wild battle start. */
#define FAINT_MARKS 12
static u32 faint_pid[FAINT_MARKS];
static u8 faint_n;

void FUN_0219CBB0(void *main, void *bpp, u32 amount);
u32 BPP_GetID(void *bpp);
void *PokeCon_GetBPP(void *pokecon, u32 id);
void *BPP_GetSrcData(void *bpp);

void rules_faint(void *main, void *bpp, u32 amount)
{
    void *pp;
    FUN_0219CBB0(main, bpp, amount);    /* the replaced call */
    pp = BPP_GetSrcData(PokeCon_GetBPP((u8 *)main + 0x1B0, BPP_GetID(bpp)));
    if (pp && faint_n < FAINT_MARKS) {
        u32 pid = PokeParty_GetParam(pp, 0, 0), k;
        for (k = 0; k < faint_n && faint_pid[k] != pid; k++)
            ;
        if (k == faint_n)
            faint_pid[faint_n++] = pid;
        rules_dbg.faint_marks++;
    }
}

static int marked(void *pp)
{
    u32 pid = PokeParty_GetParam(pp, 0, 0), k;
    for (k = 0; k < faint_n; k++)
        if (faint_pid[k] == pid)
            return 1;
    return 0;
}

/* party = the real party (synced from the battle), p = overlay 166's {GameData, setup} */
void rules_after_sync(void *party, void **p)
{
    void *gd = p[0], *ew;
    int i, n, grave, strict, alive = 0;
    pokerusSpread(party);               /* the replaced call */
    g_catch_block = CATCH_OK;
    if (!rules_flag(gd, RF_RELEASE) || howManyPokesAreAbleToFight(party) == 0) {
        faint_n = 0;                    /* a wipe: whiteout / game over decide, nobody is released */
        return;
    }
    ew = GameData_GetEventWork(gd);
    grave = rules_flag(gd, RF_GRAVEYARD);
    n = PokeParty_GetPkmCount(party);
    for (i = 0; i < n; i++) {           /* the party must keep one living, never fainted Pokémon */
        void *pp = PokeParty_GetPkm(party, i);
        if (!PokeParty_GetParam(pp, PARAM_EGG, 0) && PokeParty_GetParam(pp, PARAM_HP, 0) && !marked(pp))
            alive++;
    }
    strict = alive > 0;                 /* else: only the ones at 0 HP go (the revived one won the battle) */
    for (i = n - 1; i >= 0; i--) {
        void *pp = PokeParty_GetPkm(party, i);
        u32 item;
        if (PokeParty_GetParam(pp, PARAM_EGG, 0))
            continue;
        if (PokeParty_GetParam(pp, PARAM_HP, 0) && !(strict && marked(pp)))
            continue;
        item = PokeParty_GetParam(pp, PARAM_HELD_ITEM, 0);
        if (item && BagSave_AddItem(GameData_GetBag(gd), item, 1, HEAP_FIELD)) {
            PokeParty_SetParam(pp, PARAM_HELD_ITEM, 0);    /* its held item goes to the Bag */
            rules_dbg.items_saved++;
        }
        if (grave) {                    /* the last unlocked box; full -> released */
            void *acc = GameData_GetBoxSaveAccessor(gd);
            u32 n = BoxSaveAccessor_GetAvailableBoxCount(acc);
            if (n && BoxSaveAccessor_InsertPkmCore(acc, n - 1, pp))
                rules_dbg.graved++;
        }
        PokeParty_RemovePkm(party, i);
        rules_dbg.released++;
        (*EventWork_GetWkPtr(ew, RV_DEATHS))++;
    }
    faint_n = 0;
}

/* bl from 0x0219CF7A (r0 = party, r5 = {GameData, setup}) */
__asm__(
"   .section .text.rules_after_sync_veneer, \"ax\", %progbits\n"
"   .thumb\n"
"   .syntax unified\n"
"   .align 1\n"
"   .global rules_after_sync_veneer\n"
"   .thumb_func\n"
"   .type rules_after_sync_veneer, %function\n"
"rules_after_sync_veneer:\n"
"   push {lr}\n"
"   movs r1, r5\n"
"   bl rules_after_sync\n"
"   pop {pc}\n"
"   .size rules_after_sync_veneer, . - rules_after_sync_veneer\n"
);

/* bl from 0x02168690 (r0 = setup, r1 = 0, r4 = the event work) */
__asm__(
"   .section .text.rules_wild_start_veneer, \"ax\", %progbits\n"
"   .thumb\n"
"   .syntax unified\n"
"   .align 1\n"
"   .global rules_wild_start_veneer\n"
"   .thumb_func\n"
"   .type rules_wild_start_veneer, %function\n"
"rules_wild_start_veneer:\n"
"   push {lr}\n"
"   movs r2, r4\n"
"   bl rules_wild_start\n"
"   pop {pc}\n"
"   .size rules_wild_start_veneer, . - rules_wild_start_veneer\n"
);

/* ---- always nickname a catch ----------------------------------------------------------------- */

u32 rules_nick_answer(u8 *work)
{
    u32 a = *(u32 *)(work + 0x28);      /* overlay 297's yes/no: 1 = name it */
    if (a != 1 && rules_flag(rules_gd(), RF_NICKNAME)) {
        rules_dbg.nick_forced++;
        return 1;
    }
    return a;
}

/* egg hatch (ov307): "nickname the hatched Pokémon?" -> FUN_021DE72C: 1 YES (state 0xE: fade, name entry),
 * 0 NO (state 0x12: fade, end), else still asking. With always nickname, NO also opens the name entry
 * (the question stays, as for catches). */
int EggHatch_YesNo(void *a, void *b);

int rules_egg_nick(void *a, void *b)
{
    int r = EggHatch_YesNo(a, b);
    if (r == 0 && rules_flag(rules_gd(), RF_NICKNAME)) {
        rules_dbg.nick_forced++;
        return 1;
    }
    return r;
}

/* replaces `ldr r0, [r4, #0x28]; mov r1, #0` at 0x0219D102 (r4 = work); returns r0 = answer, r1 = 0 */
__asm__(
"   .section .text.rules_nick_veneer, \"ax\", %progbits\n"
"   .thumb\n"
"   .syntax unified\n"
"   .align 1\n"
"   .global rules_nick_veneer\n"
"   .thumb_func\n"
"   .type rules_nick_veneer, %function\n"
"rules_nick_veneer:\n"
"   push {lr}\n"
"   movs r0, r4\n"
"   bl rules_nick_answer\n"
"   movs r1, #0\n"
"   pop {pc}\n"
"   .size rules_nick_veneer, . - rules_nick_veneer\n"
);

/* ---- game over ------------------------------------------------------------------------------- */

u32 IsReturnLocationNonLeaguePokeCen(void *gd);
void *EventMapChangeBlackout_CreateExternal(void *gsys);

u32 rules_lose_kind(void *gd)
{
    u32 kind = IsReturnLocationNonLeaguePokeCen(gd);
    g_game_over = 0;
    if (rules_flag(gd, RF_GAMEOVER)) {
        g_game_over = 1;
        kind = 3;                       /* ov295 shows bank 42 line kind + 1 = 4 */
    }
    rules_dbg.lose_kind = kind;
    return kind;
}

void *rules_blackout(void *gsys)
{
    rules_dbg.blackouts++;
    if (g_game_over) {
        g_game_over = 0;
        GFL_HIDDoSoftReset(0);          /* back to the title, nothing saved; does not return */
    }
    return EventMapChangeBlackout_CreateExternal(gsys);
}

/* ---- script list menus: 7 visible rows in the intro settings menu ----------------------------
 * ov12 0x02155458 (list menu setup, FUN_021553F4): visible rows = min(items, 6), scrolling when more.
 * B2's scrolling list mis-restores a start cursor beyond the 4th row (the cursor then can't move), and
 * the intro menu's main page has 7 rows (menu.py), so there the limit is 7: no scrolling. */
u32 rules_list_max(void)
{
    void *gd = rules_gd();
    if (gd && !*EventWork_GetWkPtr(GameData_GetEventWork(gd), RV_MENU_DONE) &&
        PlayerState_GetZoneID(GameData_GetPlayerState(gd)) == 427)
        return 7;
    return 6;
}

/* bl from 0x02155458 (r0 = item count) -> r1 = visible rows, r3 = 1 if the list scrolls; the patch's
 * next instruction branches to 0x02155468 (r0 / r1 / r3 as the replaced code left them; r2 is free).
 * The window height follows r1; the BmpMenuList's own visible-line count is the header template's
 * 6 (_0216C9C0 + 2, copied to the caller's sp + 0x14), so a 7-row list also gets 7 there. */
__asm__(
"   .section .text.rules_list_rows_veneer, \"ax\", %progbits\n"
"   .thumb\n"
"   .syntax unified\n"
"   .align 1\n"
"   .global rules_list_rows_veneer\n"
"   .thumb_func\n"
"   .type rules_list_rows_veneer, %function\n"
"rules_list_rows_veneer:\n"
"   push {r0, r2, lr}\n"
"   bl rules_list_max\n"
"   movs r1, r0\n"
"   pop {r0, r2}\n"
"   movs r3, #0\n"
"   cmp r0, r1\n"
"   bls 1f\n"
"   movs r3, #1\n"
"   pop {pc}\n"
"1: movs r1, r0\n"
"   cmp r1, #6\n"
"   bls 2f\n"
"   add r2, sp, #0x18\n"           /* 7 rows: the list header (caller's sp + 0x14) line count = 7 too */
"   strh r1, [r2, #2]\n"
"2: pop {pc}\n"
"   .size rules_list_rows_veneer, . - rules_list_rows_veneer\n"
);

/* ---- settings view: SELECT in the free field shows every setting (menu.py, common script 1230) - */

#include "rules_view.h"                 /* RULES_VIEW_SCRIPT (rules.py HEADERS) */
void *FieldEventCheck_Rest(void *field, void *gsys, void *fplayer);
void *EventScriptCall_Create(void *gsys, u32 scr, void *actor, u32 heap);
u32 GCTX_HIDGetPressedKeys(void);
int FieldMenuAllowed(void);

#define PAD_SELECT      4
#define REQ_IDLE        0x100           /* request bit: the player can act and pressed none of A, X, Y */

/* the event check's last step found nothing: SELECT -> the settings view (once the intro menu ran) */
void *rules_view_check(void *field, void *gsys, void *fplayer, u32 req)
{
    void *ev = FieldEventCheck_Rest(field, gsys, fplayer);
    void *gd;
    if (ev || !(req & REQ_IDLE) || !(GCTX_HIDGetPressedKeys() & PAD_SELECT) || !FieldMenuAllowed())
        return ev;
    gd = GSYS_GetGameData(gsys);
    if (!gd || !*EventWork_GetWkPtr(GameData_GetEventWork(gd), RV_MENU_DONE))
        return ev;
    rules_dbg.views++;
    return EventScriptCall_Create(gsys, RULES_VIEW_SCRIPT, 0, HEAP_FIELD);
}

/* bl from OVL_36 0x02181840 in FUN_021814DC (push {r3-r7, lr}; sub sp, #0x70): r0 field, r1 gsys,
 * r2 player; the request built by FUN_02181CD4 is at sp + 0x30, its bit field at sp + 0x6C */
__asm__(
"   .section .text.rules_view_veneer, \"ax\", %progbits\n"
"   .thumb\n"
"   .syntax unified\n"
"   .align 1\n"
"   .global rules_view_veneer\n"
"   .thumb_func\n"
"   .type rules_view_veneer, %function\n"
"rules_view_veneer:\n"
"   ldr r3, [sp, #0x6c]\n"
"   push {lr}\n"
"   bl rules_view_check\n"
"   pop {pc}\n"
"   .size rules_view_veneer, . - rules_view_veneer\n"
);
