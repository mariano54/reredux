/* ReRedux rules: test helper (rules_test.py, built only with --with rules_test / --only).
 * rules_tst: a mailbox the emulator test scripts (build/scripts/rules/) poke, and a state snapshot
 * they read: party species/HP, Pokemon lost to the rules, Pokemon in the graveyard box. */
#include "rules.h"

void *BoxSaveAccessor_GetBox(void *acc, u32 box);
u32 PokePasoParam_GetParam(void *ppp, u32 id, void *extra);

typedef struct {
    u32 magic;          /* 'TEST' */
    u32 cmd, a, b, result;
    u32 party_count, deaths, boxes, grave;
    u16 party[6][2];    /* species, hp */
} RulesTst;

RulesTst rules_tst = { 0x54534554 };

void rules_test_frame(void)
{
    void *gd = rules_gd(), *party, *ew, *acc, *box;
    int i, n;
    if (!gd)
        return;
    party = GameData_GetParty(gd);
    ew = GameData_GetEventWork(gd);
    n = PokeParty_GetPkmCount(party);
    if (n < 0 || n > 6)
        return;
    rules_tst.party_count = n;
    for (i = 0; i < 6; i++) {
        void *pp = i < n ? PokeParty_GetPkm(party, i) : 0;
        rules_tst.party[i][0] = pp ? PokeParty_GetParam(pp, PARAM_SPECIES, 0) : 0;
        rules_tst.party[i][1] = pp ? PokeParty_GetParam(pp, PARAM_HP, 0) : 0;
    }
    rules_tst.deaths = *EventWork_GetWkPtr(ew, RV_DEATHS);
    acc = GameData_GetBoxSaveAccessor(gd);
    rules_tst.boxes = BoxSaveAccessor_GetAvailableBoxCount(acc);
    if (rules_tst.boxes && rules_tst.boxes <= 24) {
        box = BoxSaveAccessor_GetBox(acc, rules_tst.boxes - 1);
        for (i = n = 0; i < 30; i++)
            if (PokePasoParam_GetParam((u8 *)box + 0x88 * i, PARAM_SPECIES, 0))
                n++;
        rules_tst.grave = n;
    }
    switch (rules_tst.cmd) {
    case 0:
        return;
    case 1:                             /* party slot a: HP = b */
        if (rules_tst.a < (u32)PokeParty_GetPkmCount(party))
            PokeParty_SetParam(PokeParty_GetPkm(party, rules_tst.a), PARAM_HP, rules_tst.b);
        break;
    case 2:                             /* add item a x b */
        rules_tst.result = BagSave_AddItem(GameData_GetBag(gd), rules_tst.a, rules_tst.b, HEAP_FIELD);
        break;
    case 3:                             /* flag a = b */
        if (rules_tst.b)
            EventWork_FlagSet(ew, rules_tst.a);
        else
            EventWork_FlagReset(ew, rules_tst.a);
        break;
    case 4:                             /* var a = b */
        *EventWork_GetWkPtr(ew, rules_tst.a) = rules_tst.b;
        break;
    }
    rules_tst.cmd = 0;
}
