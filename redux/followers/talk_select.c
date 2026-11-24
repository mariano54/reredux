/* Picking what the follower does when you talk to it: HGSS ov02_0224EF94 / ov02_0224F058 /
 * ov02_0224F108 (build/hgss_talk/SPEC.md §2), with Black 2 sources for the situation
 * (build/hgss_parity/SPEC_talk_b2.md) and tools/follower_talk.py's translation of the lists. */
#include "follow.h"
#include "talk.h"

enum { H_RECORDS, H_MOTIONS, H_GENERIC, H_LISTS, H_ZONE_LIST, H_ZONE_ROLE, H_ZONE_BADGE, H_SPECIES, H_NZONES, H_NSPECIES };

#define ENTRY_SIZE      20
#define GENERIC_COUNT   70
#define LIST_COUNT      30
#define CHUNK           10      /* entries read at a time */

#define COND_BADGE          0x8000  /* entry +0x12 (follower_talk.py): has badge n */
#define COND_BADGE_OF_ZONE  0x80FF  /*   the badge of this zone's gym */
#define COND_ITEM           0x4000  /*   has item n in the bag */

#define HEAP_FIELD      0x15
#define HIDDEN_ITEMS    ((const u8 *)0x0216CE44)    /* OVL_12: {u16 flag, u8 count, u8 respawn, u16 zone, x, z} */
#define HIDDEN_COUNT    213
#define HIDDEN_FLAG     0xB04

static struct {
    u8 has_item, item_class, hp_band, status, level_class, type1, type2, friendship;
    u8 nature_class, gender, group, nearby, hidden, weather, tile, enc_tile, time, facing;
    s8 mood;
    u8 role, badge;
} sit;

static void *field_gd(void *field)
{
    return GSYS_GetGameData(*(void **)((u8 *)field + 0x04));
}

/* HGSS nature classes (ov02_02253AC0), by nature id */
static const u8 nature_class[25] = {4, 5, 4, 4, 1, 4, 3, 2, 1, 2, 5, 6, 3, 1, 1, 3, 6, 3, 5, 6, 2, 2, 1, 3, 6};
/* HGSS type classes by B2 type id (no ??? type in Gen 5) */
static const u8 type_class[17] = {1, 7, 10, 8, 9, 13, 12, 14, 17, 2, 3, 5, 4, 11, 6, 15, 16};
/* HGSS status values by B2 status enum (none, paralysis, sleep, freeze, burn, poison) */
static const u8 status_class[6] = {1, 4, 8, 3, 2, 5};

/* HGSS item class of a held item: Items 4, Medicine 2, Balls 1, TM 7, Berries 6, Mail 5, Battle 3 */
static u32 item_class(u32 item)
{
    switch (GetItemParam(item, 5, HEAP_FIELD)) {   /* bag pocket */
    case 1: return 2;
    case 2: return 7;
    case 3: return 6;
    case 4: return 8;
    }
    switch (GetItemParam(item, 15, HEAP_FIELD)) {  /* item type */
    case 3: return 3;
    case 4: return 1;
    case 5: return 5;
    }
    return 4;
}

/* B2 tile class -> follower_talk.py's tile groups: 1 grass, 2 very tall grass, 3 puddle,
 * 4 shallow water, 5 ice, 6 sand */
static u32 tile_group(u32 cls)
{
    switch (cls) {
    case 0x04: case 0x05: case 0x21: return 1;
    case 0x06: case 0x07: case 0x22: case 0x08: case 0x09: return 2;
    case 0x17: case 0x1C: return 3;
    case 0x14: case 0x15: return 4;
    case 0x10: case 0x18: return 5;
    case 0x0B: case 0x0C: case 0x23: return 6;
    }
    return 0;
}

static void build(void *field, void *fa, void *pk, const u32 *hdr)
{
    void *gd = field_gd(field);
    u32 zone = *(u16 *)((u8 *)field + 0xE0);
    u32 item = PokeParty_GetParam(pk, PF_ITEM, 0);
    sit.has_item = item != 0;
    sit.item_class = item ? item_class(item) : 8;
    u32 hp = PokeParty_GetParam(pk, PF_NOW_HP, 0), mx = PokeParty_GetParam(pk, PF_MAX_HP, 0);
    u32 pct = mx ? 100 * hp / mx : 0;
    sit.hp_band = pct == 100 ? 1 : pct >= 75 ? 2 : pct >= 50 ? 3 : pct >= 25 ? 4 : 5;
    u32 status = PokeParty_GetParam(pk, PF_STATUS, 0);
    sit.status = status < 6 ? status_class[status] : 1;
    sit.level_class = PokeParty_GetParam(pk, PF_LEVEL, 0) + 2 >= 50 ? 4 : 6;
    u32 t1 = PokeParty_GetParam(pk, PF_TYPE1, 0), t2 = PokeParty_GetParam(pk, PF_TYPE2, 0);
    sit.type1 = t1 < 17 ? type_class[t1] : 0;
    sit.type2 = t2 < 17 ? type_class[t2] : 0;
    sit.friendship = PokeParty_GetParam(pk, PF_FRIENDSHIP, 0);
    u32 nature = PokeParty_GetParam(pk, PF_NATURE, 0);
    sit.nature_class = nature < 25 ? nature_class[nature] : 0;
    sit.gender = PokeParty_GetParam(pk, PF_SEX, 0) == 0 ? 1 : 2;
    u32 species = PokeParty_GetParam(pk, PF_SPECIES, 0);
    sit.group = 0;
    if (species >= 1 && species <= hdr[H_NSPECIES])
        GFL_ArcSysReadRange(&sit.group, TALK_ARC, TALK_DAT, hdr[H_SPECIES] + species - 1, 1);
    sit.mood = (s8)PokeParty_GetParam(pk, PF_MOOD, 0);

    /* map objects in the 3x3 around the player, not counting us, the player or hidden ones */
    void *sys = *(void **)((u8 *)field + 0x40);
    void *pl = FindPlayerFieldActor(sys);
    GPos p;
    FldAct_GetGPos(pl, &p);
    u16 cap = *(u16 *)((u8 *)sys + 0x04);
    u8 *a = *(u8 **)((u8 *)sys + 0x1C);
    sit.nearby = 0;
    for (u32 i = 0; i < cap; i++, a += 0x100) {
        u32 flags = *(u32 *)a;
        u16 uid = *(u16 *)(a + 0x08), obj = *(u16 *)(a + 0x0C);
        if (!(flags & 1) || (flags & 4) || uid >= 0xF7)
            continue;
        if (obj == 0x6C || obj == 0x6D || (obj >= 0x2003 && obj <= 0x2005))
            continue;   /* cut trees and boulders */
        s32 dx = (s32)*(u16 *)(a + 0x3C) - p.x, dz = (s32)*(u16 *)(a + 0x40) - p.z;
        if (dx >= -1 && dx <= 1 && dz >= -1 && dz <= 1)
            sit.nearby++;
    }

    void *ew = GameData_GetEventWork(gd);
    sit.hidden = 0;
    const u8 *h = HIDDEN_ITEMS;
    for (u32 i = 0; i < HIDDEN_COUNT; i++, h += 10)
        if ((h[4] | h[5] << 8) == zone && !EventWork_FlagGet(ew, HIDDEN_FLAG + (h[0] | h[1] << 8)))
            sit.hidden++;

    u32 w = *(u16 *)(*(u8 **)((u8 *)field + 0x20) + 0x0C);
    sit.weather = w == 0 ? 1 : w == 2 ? 3 : 0;
    u32 attr = GetCachedTileUnderActor(fa);
    sit.tile = tile_group(attr & 0xFFFF);
    sit.enc_tile = (attr >> 16 & 4) && !(attr >> 16 & 2) ? 1 : 2;
    sit.time = DayPeriod_Now(GameData_GetSeason(gd)) + 1;
    static const u8 facing[4] = {3, 4, 2, 1};
    sit.facing = facing[GetActorFaceDir(fa) & 3];

    sit.role = sit.badge = 0;
    sit.badge = 0xFF;
    if (zone < hdr[H_NZONES]) {
        GFL_ArcSysReadRange(&sit.role, TALK_ARC, TALK_DAT, hdr[H_ZONE_ROLE] + zone, 1);
        GFL_ArcSysReadRange(&sit.badge, TALK_ARC, TALK_DAT, hdr[H_ZONE_BADGE] + zone, 1);
    }
}

static int band_mood(u32 b, s32 m)
{
    switch (b) {
    case 1: return m == 127;
    case 2: return m >= 100 && m <= 126;
    case 3: return m >= 50 && m <= 99;
    case 4: return m >= 30 && m <= 49;
    case 5: return m >= -29 && m <= 29;
    case 6: return m >= -49 && m <= -30;
    case 7: return m >= -126 && m <= -50;
    case 8: return m == -127;
    case 9: return m >= 0;
    case 10: return m <= -1;
    }
    return 1;
}

static int band_friend(u32 b, u32 f)
{
    switch (b) {
    case 1: return f == 255;
    case 2: return f >= 200 && f <= 254;
    case 3: return f >= 150 && f <= 199;
    case 4: return f >= 90 && f <= 149;
    case 5: return f >= 60 && f <= 89;
    case 6: return f >= 30 && f <= 59;
    case 7: return f >= 1 && f <= 29;
    case 8: return f == 0;
    case 9: return f >= 90;
    case 10: return f < 60;
    }
    return 1;
}

static int group_ok(u32 want, u32 g)
{
    if (want <= 0xF9) return g == want;
    if (want == 0xFA) return g <= 19;
    if (want == 0xFB) return g <= 130;
    if (want == 0xFC) return g >= 140 && g <= 149;
    if (want == 0xFD) return g >= 160;
    if (want == 0xFE) return g >= 220;
    return 0;
}

static int flag_ok(void *field, u32 c)
{
    void *gd = field_gd(field);
    if (c & COND_BADGE) {
        u32 n = c == COND_BADGE_OF_ZONE ? sit.badge : c & 0xFF;
        return n < 8 && isBadgeObtained(GameData_GetBadges(gd), n);
    }
    if (c & COND_ITEM)
        return BagSave_GetItemCountByID(GameData_GetBag(gd), c & 0x3FFF, HEAP_FIELD) != 0;
    return EventWork_FlagGet(GameData_GetEventWork(gd), c);
}

/* ov02_0224F108: the chance roll first (one RNG call per live entry), then every condition;
 * a 0 field means "don't care" */
static int check(void *field, const u8 *e)
{
    if (GFL_RandomLC(100) >= e[0x11])
        return 0;
    u32 flag = e[0x12] | e[0x13] << 8;
    if (flag && !flag_ok(field, flag))
        return 0;
    u32 v = e[0x03] & 0x1F;
    if (v && !(v == 9 ? sit.has_item : v == sit.item_class))
        return 0;
    if (e[0x00] && e[0x00] != sit.hp_band)
        return 0;
    v = e[0x02] >> 5;
    if (v && !(v == 7 ? sit.status != 1 : v == sit.status))
        return 0;
    u16 wa = e[0x0A] | e[0x0B] << 8;
    v = wa & 7;
    if (v && !(v == 5 ? sit.nearby >= 5 : v == sit.nearby))
        return 0;
    v = e[0x10] >> 5;
    if (v && !(v == 4 ? sit.hidden >= 4 : v == sit.hidden))
        return 0;
    v = e[0x10] >> 1 & 3;
    if (v && v != sit.level_class)
        return 0;           /* (can never match, as in HGSS) */
    if (e[0x10] >> 3 & 3)
        return 0;           /* obstacle conditions always fail in HGSS */
    v = e[0x04] & 0x1F;
    if (v && v != sit.type1 && v != sit.type2)
        return 0;
    u16 w8 = e[0x08] | e[0x09] << 8;
    v = w8 & 7;
    if (v && v != sit.weather)
        return 0;
    v = e[0x0E] | e[0x0F] << 8;
    if (v && v != sit.tile)
        return 0;
    if (e[0x05] && e[0x05] != sit.enc_tile)
        return 0;
    v = e[0x0C] | e[0x0D] << 8;     /* place role (follower_talk.py) */
    if (v && v != sit.role)
        return 0;
    v = wa >> 3 & 7;
    if (v && v != sit.time)
        return 0;
    if (!band_mood(e[0x01] & 0xF, sit.mood))
        return 0;
    if (e[0x04] >> 5)
        return 0;           /* Pokéathlon (none in Unova) */
    if (!band_friend(e[0x01] >> 4, sit.friendship))
        return 0;
    v = e[0x02] & 7;
    if (v && v != sit.nature_class)
        return 0;
    if (e[0x06] && !group_ok(e[0x06], sit.group))
        return 0;
    if (e[0x07])
        return 0;           /* Shiny Leaf (none in Unova) */
    v = e[0x02] >> 3 & 3;
    if (v && v != sit.gender)
        return 0;
    v = w8 >> 13;
    if (v && v != sit.facing)
        return 0;
    return 1;
}

/* Scan entries [from, to) of the list at ofs; -> record id of the first that passes, or 0 */
static u32 scan(void *field, u32 ofs, u32 from, u32 to)
{
    u8 buf[CHUNK * ENTRY_SIZE];
    for (u32 i = from; i < to; i += CHUNK) {
        u32 n = to - i < CHUNK ? to - i : CHUNK;
        GFL_ArcSysReadRange(buf, TALK_ARC, TALK_DAT, ofs + i * ENTRY_SIZE, n * ENTRY_SIZE);
        for (u32 j = 0; j < n; j++) {
            const u8 *e = buf + j * ENTRY_SIZE;
            u32 rec = (e[0x0A] | e[0x0B] << 8) >> 6;
            if (rec && check(field, e))
                return rec;
        }
    }
    return 0;
}

u32 talk_select(void *field, void *fa, void *pk, const u32 *hdr)
{
    build(field, fa, pk, hdr);
    u32 zone = *(u16 *)((u8 *)field + 0xE0);
    u8 list = 0xFF;
    if (zone < hdr[H_NZONES])
        GFL_ArcSysReadRange(&list, TALK_ARC, TALK_DAT, hdr[H_ZONE_LIST] + zone, 1);
    u32 rec = scan(field, hdr[H_GENERIC], 0, 12);           /* generic 30..41: urgent ones */
    if (!rec && list != 0xFF)
        rec = scan(field, hdr[H_LISTS] + list * LIST_COUNT * ENTRY_SIZE, 0, LIST_COUNT);
    if (!rec)
        rec = scan(field, hdr[H_GENERIC], 12, GENERIC_COUNT);   /* generic 42..99 (99 = catch-all) */
    return rec;
}

/* HGSS FollowMonFacePlayer: turn instantly toward the player */
void talk_face_player(void *field, void *fa)
{
    void *pl = FindPlayerFieldActor(*(void **)((u8 *)field + 0x40));
    GPos p, f;
    FldAct_GetGPos(pl, &p);
    FldAct_GetGPos(fa, &f);
    s32 dx = (s32)p.x - f.x, dz = (s32)p.z - f.z;
    s32 ax = dx < 0 ? -dx : dx, az = dz < 0 ? -dz : dz;
    if (!ax && !az)
        return;
    SetActorFaceDir(fa, az >= ax ? (dz < 0 ? 0 : 1) : (dx < 0 ? 2 : 3));
}
