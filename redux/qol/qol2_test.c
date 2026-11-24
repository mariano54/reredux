/* ReRedux qol2: test helper (qol2_test.py, built only with --with qol2_test / --only).
 * q2tst: a mailbox for the emulator tests (build/scripts/qol2/, build/scripts/qa2/):
 *   1 slot a: param b -> result          2 slot a: param b = c (PokeParty_SetParam fixes the checksum)
 *   3 slot a: language b (PF_Region 0xC) through SetParam, then register the Pokémon as caught in the
 *     Pokédex (addPkmToDex, which records its language: the dex's foreign-language entries)
 *   4 get on / off the bike (Field_ToggleCycling, as using the Bicycle does) -> result = ex state
 *   5 party count -> result          6 Bag count of item a -> result
 *   7 species a..b registered as caught (party slot 1's species set to each, then restored), national Pokédex on
 *     (the evomoves Pokédex sweep) */
#include "rules.h"

void addPkmToDex(void *dex, void *pp);
void PokeDex_SetNationalObtained(void *dex);
void *GSYS_GetField(void *gsys);
void Field_ToggleCycling(void *field);
u32 FieldPlayer_GetExState(void *fplayer);

#define PF_REGION 0xC

typedef struct {
    u32 magic;          /* 'Q2TS' */
    u32 cmd, a, b, c, result;
} Q2Tst;

Q2Tst q2tst = { 0x53543251 };

void qol2_test_frame(void)
{
    void *gd = rules_gd(), *party;
    if (!gd || !q2tst.cmd)
        return;
    party = GameData_GetParty(gd);
    if (q2tst.cmd == 4) {
        void *gsys = *(void **)0x021410F4, *field = GSYS_GetField(gsys);
        if (field) {
            Field_ToggleCycling(field);
            q2tst.result = 1;
        } else {
            q2tst.result = 0;
        }
    } else if (q2tst.cmd == 5) {
        q2tst.result = PokeParty_GetPkmCount(party);
    } else if (q2tst.cmd == 6) {        /* Bag: count of item a */
        q2tst.result = BagSave_GetItemCountByID(GameData_GetBag(gd), q2tst.a, HEAP_FIELD);
    } else if (q2tst.cmd == 7 && PokeParty_GetPkmCount(party) > 1) {   /* species a..b caught (slot 1), national */
        void *pp = PokeParty_GetPkm(party, 1), *dex = GameData_GetPokedex(gd);
        u32 s, keep = PokeParty_GetParam(pp, 5, 0);
        for (s = q2tst.a; s <= q2tst.b; s++) {
            PokeParty_SetParam(pp, 5, s);
            addPkmToDex(dex, pp);
        }
        PokeParty_SetParam(pp, 5, keep);
        PokeDex_SetNationalObtained(dex);
        q2tst.result = q2tst.b - q2tst.a + 1;
    } else if (q2tst.a < (u32)PokeParty_GetPkmCount(party)) {
        void *pp = PokeParty_GetPkm(party, q2tst.a);
        if (q2tst.cmd == 1)             /* slot a: param b -> result */
            q2tst.result = PokeParty_GetParam(pp, q2tst.b, 0);
        else if (q2tst.cmd == 2)        /* slot a: param b = c */
            PokeParty_SetParam(pp, q2tst.b, q2tst.c);
        else if (q2tst.cmd == 3) {      /* slot a: language b, registered in the Pokédex */
            PokeParty_SetParam(pp, PF_REGION, q2tst.b);
            addPkmToDex(GameData_GetPokedex(gd), pp);
            q2tst.result = PokeParty_GetParam(pp, PF_REGION, 0);
        }
    }
    q2tst.cmd = 0;
}
