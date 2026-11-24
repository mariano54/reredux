/* ReRedux rules (rules.c, menu.py): saved flags/vars and the B2 functions they use.
 * Storage (build/research_rules.md 0.1): flags 0x5D0-0x5DB, vars 0x4197-0x41AA, all unused by B2
 * and Redux, zero on a new game. The intro menu (menu.py, zone 427 scr_29) sets them once. */
#ifndef RULES_H
#define RULES_H
#include "qol.h"

#define RF_RELEASE      0x5D0   /* Nuzlocke: fainted Pokemon are released after the battle */
#define RF_GRAVEYARD    0x5D1   /* ... put in the graveyard box instead (with RF_RELEASE) */
#define RF_GAMEOVER     0x5D2   /* whiteout = game over (soft reset to the title, nothing saved) */
#define RF_FIRST        0x5D3   /* only the first wild encounter per area may be caught */
#define RF_DUPES        0x5D4   /* species already caught can't be caught, don't use the area */
#define RF_SHINY        0x5D5   /* shinies are always catchable and don't use the area */
#define RF_NICKNAME     0x5D6   /* always nickname catches and gifts */
#define RF_STATICS      0x5D7   /* static / Hidden Grotto battles count as the area's encounter */
#define RF_NOITEMS      0x5D8   /* no items from the Bag in battle (Poke Balls still allowed) */
#define RF_NOTRAINERITEMS 0x5D9 /* trainers don't use items */
#define RF_SPEED_OFF    0x5DA   /* QoL speed-ups OFF (read by speed.c; clear = on) */
#define RF_TURBO_OFF    0x5DB   /* turbo button OFF (read by turbo.c; clear = on) */
#define RF_AUTORUN_OFF  0x5DC   /* auto-run OFF (read by qol2.c; clear = on) */
#define RF_QUICKSAVE    0x5DD   /* quick save: no yes/no (qol2.c) */
#define RF_QUICKSURF    0x5DE   /* quick Surf: no yes/no (script 1243, qol2.py) */

#define RV_MENU_DONE    0x4197  /* 1 once the intro menu was confirmed */
#define RV_DIFFICULTY   0x4198  /* menu choice 0 Easy / 1 Normal / 2 Challenge */
#define RV_AREAS        0x41A0  /* 0x41A0-0x41A9: area-used bitmap, bit L of location id L */
#define RV_DEATHS       0x41AA  /* Pokemon lost to the rules */
#define RV_SPECIES_LIMIT 0x4199 /* species limit: 0 off, 1 same species, 2 same evolution line */
#define RV_CITY         0x419A  /* menu choice: 0 Black City (Black 2's own), 1 White Forest (RulesCmd 5) */
#define RULES_AREAS     160

/* g_catch_block: why Poke Balls are refused in the running wild battle */
#define CATCH_OK        0
#define CATCH_AREA      1       /* this area's encounter was used */
#define CATCH_DUPE      2       /* species already caught */
#define CATCH_LIMIT     3       /* species limit: that species is in the party / PC */
#define CATCH_LINE      4       /* species limit: a member of its evolution line is in the party / PC */

/* B2 (followers/syms.ld, qol_syms.ld, rules.py SYMS) */
void *GSYS_GetGameData(void *gsys);
void *GameData_GetEventWork(void *gd);
void *GameData_GetParty(void *gd);
void *GameData_GetBag(void *gd);
void *GameData_GetSaveControl(void *gd);
void *GameData_GetPlayerState(void *gd);
void *GameData_GetPokedex(void *gd);
void *GameData_GetBoxSaveAccessor(void *gd);
u32 PlayerState_GetZoneID(void *ps);
u32 ZoneData_GetPlaceNameID(u32 zone);
int EventWork_FlagGet(void *ew, u32 flag);
void EventWork_FlagSet(void *ew, u32 flag);
void EventWork_FlagReset(void *ew, u32 flag);
u16 *EventWork_GetWkPtr(void *ew, u32 var);
void *getKeyInfoSaveBlk(void *sc);
void KeyInfo_Init(void *ki);
void KeyInfo_SetObtained(void *ki, u32 slot);
void KeyInfo_SetUnlocked(void *ki, u32 slot);
void SetGameDifficulty(void *ki, u32 d);
u32 GetGameDifficulty(void *ki);
int PokeDex_IsCaught(void *dex, u32 species);
u32 PokeParty_GetParam(void *pp, u32 id, void *extra);
void PokeParty_SetParam(void *pp, u32 id, u32 value);
int PokeParty_IsRare(void *pp);
int PokeParty_GetPkmCount(void *party);
void *PokeParty_GetPkm(void *party, int i);
void PokeParty_RemovePkm(void *party, int i);
int howManyPokesAreAbleToFight(void *party);
int BoxSaveAccessor_InsertPkmCore(void *acc, u32 box, void *ppp);
u32 BoxSaveAccessor_GetAvailableBoxCount(void *acc);
void *BoxSaveAccessor_GetBox(void *acc, u32 box);
u32 PokePasoParam_GetParam(void *ppp, u32 id, void *extra);
void KeyInfo_SetCity(void *ki, u32 v);
u16 *GameData_GetMapVariant(void *gd);          /* FUN_02017214 */
void MapVariant_Set(u32 i, u32 v);              /* FUN_020187B0 */
u32 KeyInfo_GetCity(void *ki);
void *BtlSetup_GetParty(void *setup, u32 side);
u32 BagSave_GetItemCountByID(void *bag, u32 item, u32 heap);
int BagSave_AddItem(void *bag, u32 item, u32 count, u32 heap);
void GFL_HIDDoSoftReset(u32 mode);
u32 VM_ReadU16(void *vm);
u16 *ScriptReadVar(void *vm, void *env);
u32 ScriptReadAny(void *vm, void *env);
void *FieldScriptEnv_GetGameSystem(void *env);

#define PARAM_SPECIES   5
#define PARAM_HELD_ITEM 6
#define PARAM_EGG       0x4C
#define PARAM_HP        0xA0
#define HEAP_FIELD      0x15

/* rules.c */
void *rules_gd(void);                  /* GameData via g_GameSystem, NULL before the game runs */
int rules_flag(void *gd, u32 flag);
extern u8 g_catch_block;

/* test/debug counters (peeked by the build/scripts/rules tests; symbol rules_dbg in qol_map.json) */
typedef struct {
    u32 magic;              /* 'RULE' */
    u16 wild_starts, last_area, last_species, last_block, last_shiny, last_static;
    u16 area_marked, bag_refused, last_refuse_msg, released, graved, trainer_items_denied;
    u16 lose_kind, blackouts, nick_forced, cmd_calls, last_cmd, last_arg;
    u32 last_gd;
    u32 ki;                 /* KeyInfo seen by the new-save init / RulesCmd */
    u32 difficulty;         /* GetGameDifficulty after RulesCmd 0 (0xFF: not run) */
    u32 views;              /* settings views started with SELECT */
    u32 limit_blocks;       /* wild battles where the species limit refused the balls */
    u32 faint_marks;        /* player Pokémon marked dead when they fainted (strict release) */
    u32 items_saved;        /* held items moved to the Bag before a release */
} RulesDbg;
extern RulesDbg rules_dbg;

#endif
