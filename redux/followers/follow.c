/* Following Pokémon for Pokémon Black 2 (USA/EU, IREO) / Blaze Black 2 Redux.
 *
 * Lives in ITCM (linked at the end of the game's ITCM block) and runs once per field frame from a
 * hook on FieldRoutine_Run's call to the actor-system update (OVL_36 0x0217FFAC).
 *
 * The follower is an ordinary field actor (move code 0) that this file walks along the player's
 * path step by step (trail_tick): one tile behind like HGSS, two for large 64x64 sprites.
 */
#include "follow.h"
#include "tpoke_table.h"   /* generated: species/gender/form -> obj code, from a/2/0/8 */
#include "zone_modes.h"
#include "talk.h"
#include "ballfx.h"    /* generated: HGSS follow mode per zone, from followers/zone_modes.json */

#define ZONE_PREVENT            0   /* no follower (comm rooms, battle facilities, ...) */
#define ZONE_HEIGHT_RESTRICT    1   /* interiors: no large (64x64) followers */
#define ZONE_ALLOW              2

static u32 zone_mode(u32 zone)
{
    if (zone >= ZONE_MODE_COUNT)
        return ZONE_ALLOW;
    return zone_mode_bits[zone / 4] >> (2 * (zone % 4)) & 3;
}

#define FOLLOW_UID      0xF8
/* Large followers also occupy the tile behind them (HGSS): a hidden collision box actor sits there,
 * so NPCs walk around both tiles and talking to it talks to the follower. */
#define TAIL_UID        0xF7
#define OBJ_COLLISION   0xB9    /* invisible collision box: no model, shadow or reflection */
#define AMF_NO_EFFECTS  0x800   /* no shadow / grass / reflection / footprints */
#define FLAG_PAIR       0x966   /* story partner active: hide ours */

/* TALK_SCRIPT (-D by build_followers.py): script id of talk.s, appended to common script 1230 */
#define AF_HIDDEN       0x4
#define AF_ANIM_PAUSED  0x10    /* what acmd 0x49/0x4A set/clear */
#define AF_PERSIST      0x20    /* survives seamless zone swaps */
#define AF_RAIL         0x2000
#define AMF_NO_SAVE     0x100000
#define IDLE_TICKS      4       /* field ticks (30/s) without movement before the walk cycle stops */

#define FIELD_GSYS(f)       (*(void **)((u8 *)(f) + 0x04))
#define FIELD_ACTORSYS(f)   (*(void **)((u8 *)(f) + 0x40))
#define FIELD_PLAYER(f)     (*(void **)((u8 *)(f) + 0x94))
#define FIELD_ZONE(f)       (*(u16 *)((u8 *)(f) + 0xE0))

#define ACMD_JUMP1      0x34    /* jump 1 tile, +dir */
#define ACMD_JUMP2      0x38    /* jump 2 tiles (the player's ledge jump), +dir */
#define WP_FAST         1       /* trail waypoint walked at the fast speed */
#define WP_JUMP         2       /* trail waypoint reached with a hop (down a ledge) */
/* Step speeds. The ReRedux speed module (qol/speed.c) sets follow_speed to 1 while its faster
 * walk (acmd 0x10, 4 updates per tile instead of 8) and run (0x58 at 3 updates instead of 4: 5, 5, 6
 * units) are on, so the follower keeps its spacing; 0 (no qol block, or speedups off) = vanilla B2 speeds.
 * Field updates are 30/s: frames per tile = 2 x updates. The follower starts each tile one update after
 * the player, so behind a running player it walks acmd 0x50 (3 updates: 5, 6, 5 units), i.e. the
 * player's 5, 5, 6 shifted by that update: both move by the same amount in every update and the gap
 * never wobbles (21 units). Walking, both move 4 units per update (2 in vanilla). */
u8 follow_speed;
#define ACMD_WALK       (follow_speed ? 0x10 : 0x0C)    /* one tile: 4 / 8 updates, +dir (0 up, 1 down, 2 left, 3 right) */
#define ACMD_WALK_FAST  (follow_speed ? 0x50 : 0x10)    /* 3 / 4 updates: behind a running player */
#define ACMD_CATCH_UP   (follow_speed ? 0x14 : 0x10)    /* 2 / 4 updates: fell behind a running player */
#define ACMD_RUN        0x58    /* the player's run, 4 dirs */
#define ACMD_RUN_UPHILL 0xA3
#define ACMD_SURF_FAST  0x10    /* player codes that count as fast steps for the trail */
/* Standing still: 1 (default) = step in place like HGSS followers (whose animation never stops),
 * at HGSS's pace; 0 = freeze walkers. Flying/floating sprites (scene node 11, B2's equivalent of
 * HGSS's "hover") always keep flapping. */
#ifndef IDLE_MODE
#define IDLE_MODE       1
#endif
#define ACTOR_SCENENODE(a)  (*((u8 *)(a) + 0xE4 + 3))       /* 11 = flying/floating Pokémon */

#define MV_NONE         0x00    /* the follower is driven step by step from here (trail_tick) */
#define AF_PASS_THROUGH 0x8000  /* the player walks through it */
#define TRAIL_MAX       8
#define ACTOR_WPOS_X(a)     (*(s32 *)((u8 *)(a) + 0x44))   /* world position, fx32 */
#define ACTOR_WPOS_Z(a)     (*(s32 *)((u8 *)(a) + 0x4C))
/* Sprite draw offset (s8, world units) the renderer adds to the actor's position; the actor gets
 * its initial value from the sprite config (copy at +0xE4: offX +13, offZ +15). WPosOffset (+0x50)
 * is not applied to these billboards. */
#define ACTOR_MODEL_OFS_X(a)    (*((s8 *)(a) + 0x7E))
#define ACTOR_MODEL_OFS_Y(a)    (*((s8 *)(a) + 0x7F))
#define ACTOR_MODEL_OFS_Z(a)    (*((s8 *)(a) + 0x80))
#define CONFIG_OFS_X(a)         (*((s8 *)(a) + 0xE4 + 13))
#define CONFIG_OFS_Y(a)         (*((s8 *)(a) + 0xE4 + 14))
#define CONFIG_OFS_Z(a)         (*((s8 *)(a) + 0xE4 + 15))
#define HALF_TILE       8       /* a tile is 16 units */
#define OFS_STEP        2       /* per tick, so the half-tile offset eases around corners */
/* B2's Pokémon billboards (OVL_36 0x02196CD5, a port of HGSS ov01_021F8D80/021F8FC0) already do
 * HGSS's 20-step idle cycle, its +-2 sideways shift and its bob. That function ends by storing the
 * sprite offset (WPosOffset, actor +0x50) it computed: x +-2 facing sideways; y +1.5 outside HGSS's
 * bob window and 0 inside it (a y above 1.5, i.e. a jump, is kept as it is); z -2 (B2's Pokémon stand
 * a little behind their tile). Unlike the draw offset above (+0x7E, which moves the shadow too), it
 * moves the sprite alone. build_followers.py points that store at follow_wofs_hook, which gives the
 * follower HGSS's bob instead: resting at WOFS_REST, 2 units lower inside the window. WOFS_REST puts
 * the feet of a sprite drawn to B2's Pokémon convention (lowest row 29 of 32; the player's is 30)
 * where the player's are, in the middle of the shadow: with B2's lift and z -2 it sat 4 px higher.
 * Flying/floating sprites (st.hover) keep floating: 0 inside the window, 2 above the shadow outside. */
#define FX_ONE          0x1000
#define WOFS_LIFT       0x1800                  /* B2's bob lift (1.5) */
#ifndef WOFS_REST
#define WOFS_REST       (-2 * FX_ONE)
#endif
#define WOFS_DIP        (2 * FX_ONE)            /* HGSS ov01_021F8D80 */
#define WOFS_HOVER      (2 * FX_ONE)

/* Size classes (build_followers.py, from the sprite): 0 small, 1 medium (Charizard, Venusaur...),
 * 2 large 64x64 sprite (Lugia...). */
#define SIZE_MEDIUM     1
#define SIZE_LARGE      2

static struct {
    u32 lead_pid;       /* personality of the party lead (0 until seen) */
    GPos fpos;          /* where the follower stood, visible, at the last tick (have_pos) */
    u8 have_pos, fdir;
    u16 fzone;
    u8 booted;          /* a follower was placed since power-on (Continue: not yet) */
    u8 waiting;         /* 1: hidden on the player's tile, appears on their first step */
    u8 size;            /* size class of the current sprite */
    u8 hover;           /* the current sprite flies/floats (tpoke_table hover bit) */
    s16 shadow;         /* its ground shadow's scale (fx16, tpoke_table bits 11-15; see shadow_apply) */
    u8 idle;            /* ticks with neither the player nor the follower moving */
    u8 in_jump;         /* 0, or how many tiles of the player's current ledge jump were queued */
    u8 qn;              /* trail: tiles the player left that the follower still has to walk */
    u8 why;             /* why there is no follower right now (WHY_*) */
    u8 recalling;       /* its Poké Ball recall is playing; the actor goes once it is done */
    u8 ball_next;       /* the next pop-in comes out of the Poké Ball (HGSS: after the bike, a warp
                           panel, or when the previous zone didn't allow it) */
    u8 seq, seq_t;      /* scripted sequence (SEQ_*) run by follow_tick instead of the trail */
    u8 hold;            /* a GameEvent waits in its first state for seq / talk_react */
    u8 hold_res;        /* what event_hold returns once that is over */
    u8 settle;          /* event_hold calls spent waiting for the actor to be rebuilt */
    u8 fly_slot;        /* party slot of the Fly user */
    u8 kind[TRAIL_MAX]; /* WP_FAST / WP_JUMP per waypoint */
    s32 pw[2], fw[2];   /* player / follower world x, z at the previous tick */
    s32 ofs[2];         /* extra draw offset x, z in units (medium followers sit half a tile back) */
    GPos spawn;
    GPos last;          /* the player's tile at the previous tick */
    GPos q[TRAIL_MAX];
} st;

/* Tiles behind the player along their path: 1 as in HGSS (medium ones are drawn half a tile
 * further back, so 1.5); large 64x64 sprites 2 so they don't cover the player.
 * -DFOLLOW_DISTANCE=n forces one distance for every species. */
static u32 follow_distance(void)
{
#ifdef FOLLOW_DISTANCE
    return FOLLOW_DISTANCE;
#else
    return st.size == SIZE_LARGE ? 2 : 1;
#endif
}

/* Ease the draw offset away from the player: half a tile for medium sprites (on top of the
 * renderer's own HGSS sideways shift), none for small and large ones. */
static void update_offset(void *fa, void *pl, int visible)
{
    s32 target[2] = {0, 0};
    if (visible && st.size == SIZE_MEDIUM) {
        s32 dx = ACTOR_WPOS_X(fa) - ACTOR_WPOS_X(pl);
        s32 dz = ACTOR_WPOS_Z(fa) - ACTOR_WPOS_Z(pl);
        /* Grid positions change at the start of a step. During a straight walk/run their
         * difference alternates between one and two tiles even though the world-space gap
         * is constant. Use that gap so the half-tile drawing offset stays steady. */
        const s32 limit = 32 * FX_ONE;
        if ((dx == 0) != (dz == 0) && dx >= -limit && dx <= limit && dz >= -limit && dz <= limit) {
            /* Never push it further "up" (away from the camera): that moves the billboard into
             * the scenery behind it (mailboxes, walls and signs hide it). */
            target[0] = dx < 0 ? -HALF_TILE : dx > 0 ? HALF_TILE : 0;
            target[1] = dz > 0 ? HALF_TILE : 0;
        }
    }
    for (u32 i = 0; i < 2; i++) {
        s32 d = target[i] - st.ofs[i];
        st.ofs[i] += d > OFS_STEP ? OFS_STEP : d < -OFS_STEP ? -OFS_STEP : d;
    }
    if (!visible) {
        st.ofs[0] = st.ofs[1] = 0;
    }
    s32 mx, my, mz, bx, bz;
    talk_offset(&mx, &my, &mz);     /* talk motions (hops, shakes...) */
    ballfx_offset(&bx, &bz);        /* large followers slide into their ball */
    ACTOR_MODEL_OFS_X(fa) = CONFIG_OFS_X(fa) + st.ofs[0] + mx + bx;
    ACTOR_MODEL_OFS_Y(fa) = CONFIG_OFS_Y(fa) + my;
    ACTOR_MODEL_OFS_Z(fa) = CONFIG_OFS_Z(fa) + st.ofs[1] + mz + bz;
}

/* Replaces the billboard update's `bl FldAct_SetWPosOffset` (OVL_36 0x02196DE4; every Pokémon
 * actor, every frame): the follower's bob, see WOFS_REST. A y below 0 is one of ours that B2 kept
 * (it keeps heights while the actor moves), above the lift a jump: both stay as they are. */
void follow_wofs_hook(void *actor, s32 *vec)
{
    if (*(u16 *)((u8 *)actor + 0x08) == FOLLOW_UID && vec[1] >= 0 && vec[1] <= WOFS_LIFT) {
        if (st.hover)
            vec[1] = vec[1] ? WOFS_HOVER : 0;
        else
            vec[1] = vec[1] ? WOFS_REST : WOFS_REST - WOFS_DIP;
    }
    FldAct_SetWPosOffset(actor, vec);
}

/* read by the emulator test harness: ticks, wanted obj, player x | z << 16, follower actor */
volatile u32 follow_dbg[8];   /* [4]: tail box x | z << 16; [5] ops run; [6] last op << 16 | result; [7] op trace */

/* FindFieldActor skips actors flagged not-interactable (0x800), so walk the actor array ourselves:
 * FieldActorSystem +0x04 capacity, +0x1C actors (stride 0x100); actor +0x00 flags (0x1 = in use),
 * +0x08 uid. Also counts the slots in use (+0x06 is not a live count). */
static void *find_follower(void *sys, u32 *count, void **tail)
{
    u16 cap = *(u16 *)((u8 *)sys + 0x04);
    u8 *a = *(u8 **)((u8 *)sys + 0x1C);
    void *found = 0;
    *count = 0;
    *tail = 0;
    for (u32 i = 0; i < cap; i++, a += 0x100) {
        if (!(*(u32 *)a & 1))
            continue;
        (*count)++;
        if (*(u16 *)(a + 0x08) == FOLLOW_UID)
            found = a;
        else if (*(u16 *)(a + 0x08) == TAIL_UID)
            *tail = a;
    }
    return found;
}

/* tpoke_table rows: species, gender (2 = any) | size class << 8 | hover << 10 | shadow << 11, form,
 * obj code, shiny obj code. Also sets st.size, st.hover and st.shadow for the sprite it returns.
 * shadow: how much smaller than the player's its shadow is drawn, in 1/32 steps (build_followers.py
 * SHADOW_SHRINK: 0 large, 5 medium, 10 small, 2 more when it hovers). */
#define SHADOW_STEP     (FX_ONE / 32)
static void set_class(u16 g)
{
    st.size = g >> 8 & 3;
    st.hover = g >> 10 & 1;
    st.shadow = FX_ONE - (g >> 11) * SHADOW_STEP;
}

/* The follower's shadow: the game gives every actor the same one (a 16x16 billboard drawn at the
 * actor's feet, created once per actor by the field-effect system). Its task's init and delete go
 * through the two functions below, which remember the follower's; shadow_apply scales that billboard
 * (about its centre, which stays under the feet) when it is created and when the sprite changes.
 * Nothing runs per frame. The effect system calls every task's delete when it is torn down. */
static u8 *shadow_work;

static void shadow_apply(void)
{
    u8 *w = shadow_work;
    if (!w)
        return;
    s16 s = st.shadow;
    BlActScene_SetObjectSize(*(void **)(*(u8 **)(w + 0x04) + 0x14), *(u16 *)(w + 0x14), &s, &s);
}

void follow_shadow_init(void *task, void *work)
{
    u8 *w = work;
    FieldEffect_ShadowInit(task, work);
    u8 *a = *(u8 **)(w + 0x08);
    if (a && *(u16 *)(a + 0x08) == FOLLOW_UID && *(u16 *)(w + 0x14) != 0xFFFF) {
        shadow_work = w;
        shadow_apply();
    }
}

void follow_shadow_delete(void *task, void *work)
{
    if (work == shadow_work)
        shadow_work = 0;
    FieldEffect_ShadowDelete(task, work);
}

static u16 lookup_obj(u32 species, u32 sex, u32 form, u32 shiny)
{
    const u16 *e = tpoke_table, *any = 0;
    shiny = shiny ? 4 : 3;
    for (u32 i = 0; i < TPOKE_COUNT; i++, e += 5) {
        if (e[0] != species)
            continue;
        u32 g = e[1] & 0xFF;
        if (e[2] == form && (g == 2 || g == sex)) {
            set_class(e[1]);
            return e[shiny];
        }
        if (!any && e[2] == 0)
            any = e;
    }
    if (!any)
        return 0;   /* species has no sprite */
    set_class(any[1]);
    return any[shiny];   /* unknown form: the base form's sprite */
}

/* obj code of the party lead's follower sprite (sets st.size), or 0 */
static u16 lead_obj(void *gd)
{
#ifdef FOLLOW_DEBUG_FORCE
    (void)gd;
    return lookup_obj(FOLLOW_DEBUG_FORCE, 0, 0, FOLLOW_DEBUG_SHINY);   /* showcase builds only */
#else
    /* the lead (talk.c, cached on a hash of the party's bytes); the sprite lookup is cached on the same
     * hash: the PokeParty_GetParam calls decrypt the whole Pokémon each time (emulator load per frame) */
    static u32 sig, valid;
    static u16 obj;
    static u8 size, hover;
    static s16 shadow;
    u32 slot;
    void *pk = talk_lead(gd, &slot);
    if (valid && sig == talk_lead_sig) {
        st.size = size;
        st.hover = hover;
        st.shadow = shadow;
        return obj;
    }
    if (pk)
        obj = lookup_obj(PokeParty_GetParam(pk, PF_SPECIES, 0), PokeParty_GetParam(pk, PF_SEX, 0),
                         PokeParty_GetParam(pk, PF_FORME, 0), PokeParty_IsRare(pk));
    else
#ifdef FOLLOW_DEBUG_SPECIES
        obj = lookup_obj(FOLLOW_DEBUG_SPECIES, 0, 0, FOLLOW_DEBUG_SHINY);   /* test builds: empty party */
#else
        obj = 0;
#endif
    sig = talk_lead_sig;
    valid = 1;
    size = st.size;
    hover = st.hover;
    shadow = st.shadow;
    return obj;
#endif
}

enum { WHY_SHOWN, WHY_OTHER, WHY_BIKE, WHY_SURF, WHY_ZONE };

/* obj code of the follower we want right now, or 0 for none (st.why says why) */
static u16 wanted_obj(void *field, void *gd, void *player_actor)
{
    st.why = WHY_OTHER;
    if (EventWork_FlagGet(GameData_GetEventWork(gd), FLAG_PAIR))
        return 0;
    u32 ex = FieldPlayer_GetExState(FIELD_PLAYER(field));   /* 1 cycling, 2 surfing, 3 diving */
    if (ex != 0) {
        st.why = ex == 1 ? WHY_BIKE : WHY_SURF;
        return 0;
    }
    if (CheckActorFlag(player_actor, AF_RAIL))               /* the trail is grid-only */
        return 0;
    u32 mode = zone_mode(FIELD_ZONE(field));
    st.why = WHY_ZONE;
    if (mode == ZONE_PREVENT)
        return 0;
    u16 obj = lead_obj(gd);
    if (mode == ZONE_HEIGHT_RESTRICT && st.size == SIZE_LARGE)
        return 0;   /* HGSS: too tall for interiors */
    st.why = obj ? WHY_SHOWN : WHY_OTHER;
    return obj;
}

static int same_tile(const GPos *a, const GPos *b)
{
    return a->x == b->x && a->z == b->z;
}

static void trail_reset(const GPos *player)
{
    st.qn = 0;
    st.last.x = player->x;
    st.last.y = player->y;
    st.last.z = player->z;
}

static void trail_shift(void)
{
    for (u32 i = 1; i < st.qn; i++) {
        st.q[i - 1].x = st.q[i].x;
        st.q[i - 1].y = st.q[i].y;
        st.q[i - 1].z = st.q[i].z;
        st.kind[i - 1] = st.kind[i];
    }
    st.qn--;
}

static void trail_push(const GPos *t, u32 kind)
{
    if (st.qn == TRAIL_MAX)
        trail_shift();
    st.q[st.qn].x = t->x;
    st.q[st.qn].y = t->y;
    st.q[st.qn].z = t->z;
    st.kind[st.qn] = kind;
    st.qn++;
}

static int adjacent(const GPos *a, const GPos *b)
{
    s32 dx = (s32)a->x - (s32)b->x, dz = (s32)a->z - (s32)b->z;
    return (dx < 0 ? -dx : dx) + (dz < 0 ? -dz : dz) == 1;
}

/* Hide and reappear behind the player on their next step (as after a warp). */
static void hide_until_step(void *fa, const GPos *p)
{
    st.have_pos = 0;
    SetActorHidden(fa, 1);
    st.waiting = 1;
    st.spawn.x = p->x;
    st.spawn.y = p->y;
    st.spawn.z = p->z;
}

/* Scripted sequences, one step per field tick (the trail is suspended meanwhile). */
enum { SEQ_NONE, SEQ_SURF, SEQ_SURF_WALK, SEQ_SURF_FACE, SEQ_SURF_JUMP, SEQ_RECALL, SEQ_RECALL_WAIT };
#define SEQ_TIMEOUT     150     /* ticks: never block an event for good */
#define ACMD_FACE       0x00    /* +dir */

static void seq_start(u32 seq)
{
    st.seq = seq;
    st.seq_t = 0;
}

static u32 dir_to(const GPos *from, const GPos *to)
{
    s32 dx = (s32)to->x - (s32)from->x, dz = (s32)to->z - (s32)from->z;
    return dz < 0 ? 0 : dz > 0 ? 1 : dx < 0 ? 2 : 3;
}

static void seq_tick(void *field, void *fa, void *pl, const GPos *p)
{
    if (!fa || ++st.seq_t > SEQ_TIMEOUT) {
        st.seq = SEQ_NONE;
        return;
    }
    GPos f;
    FldAct_GetGPos(fa, &f);
    switch (st.seq) {
    case SEQ_SURF:
        /* HGSS ov01_02205F00, after the hop and the cry: one step onto the player's tile... */
        if (talk_busy() || !FldAct_CanSetAcmd(fa))
            return;
        FldAct_SetAcmd(fa, ACMD_WALK + dir_to(&f, p));
        break;
    case SEQ_SURF_WALK:
        /* ...face the water... */
        if (!FldAct_CanSetAcmd(fa))
            return;
        FldAct_SetAcmd(fa, ACMD_FACE + GetActorFaceDir(pl));
        st.seq_t = 0;
        break;
    case SEQ_SURF_FACE:
        /* ...10 frames, then a 1-tile jump into it... */
        if (st.seq_t <= 10 || !FldAct_CanSetAcmd(fa))
            return;
        FldAct_SetAcmd(fa, ACMD_JUMP1 + GetActorFaceDir(pl));
        break;
    case SEQ_SURF_JUMP:
        /* ...and the Poké Ball burst (mode 2) where it lands; it stays hidden while surfing. The
         * actor is kept until the burst is over (follow_tick's recall path waits for it). */
        if (!FldAct_CanSetAcmd(fa))
            return;
        ballfx_start(field, fa, BALLFX_BURST, st.size == SIZE_LARGE);
        SetActorHidden(fa, 1);
        st.recalling = 1;
        st.seq = SEQ_NONE;
        return;
    case SEQ_RECALL:
        /* HGSS's recall task (ov01_02205D68): its current step ends first */
        if (!FldAct_CanSetAcmd(fa))
            return;
        ballfx_start(field, fa, BALLFX_RECALL, st.size == SIZE_LARGE);
        st.recalling = 1;
        break;
    case SEQ_RECALL_WAIT:
        if (ballfx_busy())
            return;
        st.recalling = 0;
        st.seq = SEQ_NONE;
        return;
    }
    st.seq++;
}

/* Walk the follower along the tiles the player left, keeping follow_distance() - 1 of them between
 * the two. If the player turns back onto the trail it is cut there; if they walk into the
 * follower (it is pass-through) the two swap places. */
static void trail_tick(void *fa, void *pl, const GPos *p)
{
    u32 dist = follow_distance();
    GPos f;
    FldAct_GetGPos(fa, &f);
    u16 pa = FldAct_GetAcmd(pl);
    int ledge = pa >= ACMD_JUMP2 && pa < ACMD_JUMP2 + 4;
    if (!ledge)
        st.in_jump = 0;
    if (!same_tile(&st.last, p) && !adjacent(&st.last, p)) {
        s32 dx = (s32)p->x - (s32)st.last.x, dz = (s32)p->z - (s32)st.last.z;
        if (ledge && ((dx == 0 && (dz == 2 || dz == -2)) || (dz == 0 && (dx == 2 || dx == -2)))) {
            /* ledge jump moved the player 2 tiles at once: the tile in front of the ledge, then a
             * hop onto the ledge tile (HGSS: one step to the edge, then the hop) */
            GPos mid = {(u16)(st.last.x + dx / 2), st.last.y, (u16)(st.last.z + dz / 2)};
            trail_push(&st.last, 0);
            trail_push(&mid, WP_JUMP);
            st.in_jump = 2;
            st.last.x = p->x;
            st.last.y = p->y;
            st.last.z = p->z;
        } else {
            hide_until_step(fa, p);   /* moved more than a tile (script, warp panel) */
            return;
        }
    }
    if (!same_tile(&st.last, p)) {
        u32 i;
        for (i = 0; i < st.qn && !same_tile(&st.q[i], p); i++)
            ;
        if (same_tile(p, &f)) {
            /* walked into the follower: swap places (it steps to where the player came from) */
            st.qn = 0;
            if (FldAct_CanSetAcmd(fa) && adjacent(&st.last, &f)) {
                s32 dx = (s32)st.last.x - (s32)f.x, dz = (s32)st.last.z - (s32)f.z;
                FldAct_SetAcmd(fa, ACMD_WALK + (dz < 0 ? 0 : dz > 0 ? 1 : dx < 0 ? 2 : 3));
            }
        } else if (i < st.qn) {
            st.qn = i;
        } else if (ledge) {
            /* ledge jump reported one tile at a time: the first tile is walked, the second hopped */
            trail_push(&st.last, st.in_jump ? WP_JUMP : 0);
            st.in_jump++;
        } else {
            /* with follow_speed the player's walk is 0x10 too (same speed as ACMD_WALK): not a fast step */
            int fast = (pa >= ACMD_RUN && pa < ACMD_RUN + 4) ||
                       (!follow_speed && pa >= ACMD_SURF_FAST && pa < ACMD_SURF_FAST + 4) ||
                       (pa >= ACMD_RUN_UPHILL && pa < ACMD_RUN_UPHILL + 4);
            trail_push(&st.last, fast ? WP_FAST : 0);
        }
        st.last.x = p->x;
        st.last.y = p->y;
        st.last.z = p->z;
    }
    while (st.qn >= dist && same_tile(&st.q[0], &f))
        trail_shift();      /* already there */
    if (st.qn < dist || !FldAct_CanSetAcmd(fa))
        return;
    GPos t = st.q[0];
    u32 kind = st.kind[0];
    u32 fast = kind & WP_FAST;
    u32 behind = st.qn > dist;                      /* catch up if it fell behind */
    trail_shift();
    if (!adjacent(&t, &f)) {
        hide_until_step(fa, p);   /* off the path */
        return;
    }
    s32 dx = (s32)t.x - (s32)f.x, dz = (s32)t.z - (s32)f.z;
    u32 dir = dz < 0 ? 0 : dz > 0 ? 1 : dx < 0 ? 2 : 3;
    if (kind & WP_JUMP)
        FldAct_SetAcmd(fa, ACMD_JUMP1 + dir);   /* hop down the ledge (8 frames, B2's jump arc) */
    else
        FldAct_SetAcmd(fa, (behind ? (fast ? ACMD_CATCH_UP : ACMD_WALK_FAST) : fast ? ACMD_WALK_FAST : ACMD_WALK) + dir);
}

/* Keep the large follower's tail box on the tile behind it: the tile it is leaving while it walks
 * (InitGPos), else the one opposite its facing. Created only outside scripts, like the follower. */
static void tail_tick(void *field, void *sys, void *fa, void *tail, u32 count, int event)
{
    if (!fa || st.size != SIZE_LARGE || st.waiting || CheckActorFlag(fa, AF_HIDDEN)) {
        if (tail)
            DeleteActor(tail);
        return;
    }
    GPos f, b;
    FldAct_GetGPos(fa, &f);
    GetActorInitGPos(fa, &b);
    if (same_tile(&b, &f)) {
        u32 dir = GetActorFaceDir(fa);
        b.x = f.x + (dir == 2 ? 1 : dir == 3 ? -1 : 0);
        b.z = f.z + (dir == 0 ? 1 : dir == 1 ? -1 : 0);
        b.y = f.y;
    }
    if (!tail) {
        if (event || count + 4 >= *(u16 *)((u8 *)sys + 0x04))
            return;
        tail = CreateNewActorByParam(sys, b.x, b.z, 0, TAIL_UID, OBJ_COLLISION, MV_NONE, FIELD_ZONE(field));
        if (!tail)
            return;
        SetActorFlag(tail, AF_PERSIST | AF_PASS_THROUGH);
        SetActorSCRID(tail, TALK_SCRIPT);
        SetActorMovementFlag(tail, AMF_NO_SAVE | AMF_NO_EFFECTS);
        SetActorHidden(tail, 1);
    }
    GPos t;
    FldAct_GetGPos(tail, &t);
    if (!same_tile(&t, &b) || t.y != b.y)
        SetActorGPos(tail, b.x, b.y, b.z, 0);
    follow_dbg[4] = b.x | (u32)b.z << 16;
}

/* kept out of line: the two entry points (hook, script command) must sit at the same addresses in
 * every build, so test builds can be poked into a running game */
__attribute__((noinline)) static void follow_tick(void *field)
{
    void *sys = FIELD_ACTORSYS(field);
    if (!sys || !FIELD_PLAYER(field))
        return;
    void *gsys = FIELD_GSYS(field);
    void *gd = GSYS_GetGameData(gsys);
    void *pl = FindPlayerFieldActor(sys);
    if (!pl)
        return;
#ifdef FOLLOW_TEST_BIKE
    static u32 ride;    /* test builds: get off the bike by itself after 5 s of riding */
    if (FieldPlayer_GetExState(FIELD_PLAYER(field)) != 1)
        ride = 0;
    else if (++ride == 150 && !GSYS_GetEventRunningFlag(gsys))
        Field_ToggleCycling(field);
#endif
    u32 count;
    void *tail;
    void *fa = find_follower(sys, &count, &tail);
    u16 obj = wanted_obj(field, gd, pl);
    /* HGSS resets the mood (talk.c) of a Pokémon that becomes the lead */
    u32 slot;
    void *lead = talk_lead(gd, &slot);
    static u32 pid, pid_sig, pid_valid;     /* cached on the party hash (lead_obj) */
    if (!pid_valid || pid_sig != talk_lead_sig) {
        pid = lead ? PokeParty_GetParam(lead, PF_PID, 0) : 0;
        pid_sig = talk_lead_sig;
        pid_valid = 1;
    }
    if (pid != st.lead_pid) {
        if (st.lead_pid && lead)
            PokeParty_SetParam(lead, PF_MOOD, 0);
        st.lead_pid = pid;
    }
    GPos p;
    FldAct_GetGPos(pl, &p);
    follow_dbg[0]++;
    follow_dbg[1] = obj;
    follow_dbg[2] = p.x | (u32)p.z << 16;
    follow_dbg[3] = 0;
    if (fa) {
        GPos f;
        FldAct_GetGPos(fa, &f);
        follow_dbg[3] = f.x | (u32)f.z << 16 | (u32)st.qn << 12 | (u32)st.waiting << 28;
    }

    if (fa)
        st.booted = 1;
    if (fa && GetActorMoveCode(fa) != MV_NONE) {
        DeleteActor(fa);      /* made by a build with the other movement mode: recreate */
        fa = 0;
        st.waiting = 0;
    }
    if (!obj) {
        /* HGSS recalls a visible follower into its ball when the player gets on the bike or starts
         * surfing, and when it walks into a zone that doesn't allow it; the actor stays until the
         * effect is over */
        if (fa && !st.recalling && !st.waiting && !CheckActorFlag(fa, AF_HIDDEN)
            && (st.why == WHY_BIKE || st.why == WHY_SURF || st.why == WHY_ZONE)) {
            ballfx_start(field, fa, BALLFX_RECALL, st.size == SIZE_LARGE);
            st.recalling = 1;
        }
        if (tail)
            DeleteActor(tail);
        if (st.recalling && fa && ballfx_busy())
            return;
        st.recalling = 0;
        if (st.why == WHY_BIKE || st.why == WHY_ZONE)
            st.ball_next = 1;   /* HGSS: back out of the ball (surfing ends with a plain pop-in) */
        else if (st.why == WHY_SURF)
            st.ball_next = 0;
        if (fa)
            DeleteActor(fa);
        st.waiting = 0;
        st.have_pos = 0;
        return;
    }
    int frozen = talk_tick(field, fa);    /* HGSS: the animation stops while its text shows */
    if (st.recalling && !st.seq && !ballfx_busy())
        st.recalling = 0;
    /* Cutscenes: the follower hides with the player (Fly's take-off, scripted disappearances) and
     * pops back out on their first step once they are visible again; so does a follower left
     * hidden by a recall that wasn't followed by a warp. */
    int pl_hidden = CheckActorFlag(pl, AF_HIDDEN);
    if (fa && !st.waiting && !st.seq && !ballfx_busy() && (pl_hidden || CheckActorFlag(fa, AF_HIDDEN)))
        hide_until_step(fa, &p);
    if (fa && st.seq)
        seq_tick(field, fa, pl, &p);
    else if (fa && !st.waiting)
        trail_tick(fa, pl, &p);   /* also during scripts, so it keeps up with scripted walks */
    if (fa && !st.waiting) {
        /* Idle: see IDLE_MODE. "Moving" = the player's or follower's world position changed
         * (acmd-driven steps don't set MovementFlags 0x10). */
        s32 pw0 = ACTOR_WPOS_X(pl), pw1 = ACTOR_WPOS_Z(pl), fw0 = ACTOR_WPOS_X(fa), fw1 = ACTOR_WPOS_Z(fa);
        int moving = pw0 != st.pw[0] || pw1 != st.pw[1] || fw0 != st.fw[0] || fw1 != st.fw[1];
        int pause = 0;
        if (moving) {
            st.idle = 0;
        } else if (st.idle < IDLE_TICKS) {
            st.idle++;
        } else if (IDLE_MODE == 0 && ACTOR_SCENENODE(fa) != 11) {
            pause = 1;      /* optional: walkers stand still (HGSS never stops the cycle) */
        }
        if (pause || frozen)
            SetActorFlag(fa, AF_ANIM_PAUSED);
        else
            ClearActorFlag(fa, AF_ANIM_PAUSED);
        st.pw[0] = pw0;
        st.pw[1] = pw1;
        st.fw[0] = fw0;
        st.fw[1] = fw1;
    }
    if (fa)
        update_offset(fa, pl, !st.waiting);
    int event = GSYS_GetEventRunningFlag(gsys);
    tail_tick(field, sys, fa, tail, count, event);
    /* HGSS's follower is a saved map object: after a battle, a menu or Continue it is simply there.
     * Ours is rebuilt with the field: put it back where it stood if the player hasn't moved (also
     * in the middle of an event, e.g. a field move picked in the party menu), or behind the player
     * after Continue. Otherwise (warps) it pops out on their first step. */
    int back = st.have_pos && st.fzone == FIELD_ZONE(field) && same_tile(&st.last, &p) && !pl_hidden;
    if (event && !(back && !fa)) {
        follow_dbg[3] = 0xE1;
        return;   /* otherwise never spawn or re-skin in the middle of a script */
    }
    if (!fa) {
        if (count + 4 >= *(u16 *)((u8 *)sys + 0x04)) {
            follow_dbg[3] = 0xE2;
            return;   /* leave slots for the map's own actors (the allocator has no NULL check) */
        }
        fa = CreateNewActorByParam(sys, p.x, p.z, GetActorFaceDir(pl), FOLLOW_UID, obj,
                                   MV_NONE, FIELD_ZONE(field));
        if (!fa) {
            follow_dbg[3] = 0xE3;
            return;
        }
        SetActorFlag(fa, AF_PERSIST | AF_PASS_THROUGH);
        SetActorSCRID(fa, TALK_SCRIPT);
        SetActorMovementFlag(fa, AMF_NO_SAVE);
        GPos at = st.fpos;
        u32 dir = st.fdir;
        if (!back && !st.booted && !pl_hidden) {
            dir = GetActorFaceDir(pl);
            at.x = p.x + (dir == 2 ? 1 : dir == 3 ? -1 : 0);
            at.z = p.z + (dir == 0 ? 1 : dir == 1 ? -1 : 0);
            at.y = p.y;
            back = ActorRouteCollCheck(pl, at.x, at.y, at.z, dir ^ 1) == 0;
        }
        st.booted = 1;
        if (back) {
            SetActorGPos(fa, at.x, at.y, at.z, dir);
            st.waiting = 0;
            trail_reset(&p);
            return;
        }
        SetActorGPos(fa, p.x, p.y, p.z, GetActorFaceDir(pl));
        SetActorHidden(fa, 1);
        st.waiting = 1;
        st.spawn.x = p.x;
        st.spawn.y = p.y;
        st.spawn.z = p.z;
        return;
    }
    if (FldAct_GetObjCode(fa) != obj) {
        FldAct_UpdateBlInfoForNewObjCode(fa, obj);  /* lead changed: re-skin silently, as HGSS */
        shadow_apply();     /* (B2 also rebuilds the actor's shadow task: follow_shadow_init scales that) */
        trail_reset(&p);
    }
    if (!st.waiting && !CheckActorFlag(fa, AF_HIDDEN)) {
        FldAct_GetGPos(fa, &st.fpos);
        st.fdir = GetActorFaceDir(fa);
        st.fzone = FIELD_ZONE(field);
        st.have_pos = 1;
    }
    GPos prev;
    GetActorInitGPos(pl, &prev);
    if (st.waiting == 1 && !same_tile(&p, &st.spawn) && !same_tile(&prev, &st.spawn)) {
        st.spawn.x = p.x;   /* warped (or moved by a script) while it waited: wait for a real step */
        st.spawn.y = p.y;
        st.spawn.z = p.z;
    }
    if (st.waiting == 1 && !pl_hidden && !same_tile(&p, &st.spawn)) {
        /* first step after spawning: pop out on the tile the player just left */
        SetActorGPos(fa, prev.x, prev.y, prev.z, GetActorFaceDir(pl));
        if (st.ball_next)
            ballfx_start(field, fa, BALLFX_RELEASE, st.size == SIZE_LARGE);   /* unhides it */
        else
            SetActorHidden(fa, 0);
        st.ball_next = 0;
        st.waiting = 0;
        trail_reset(&p);
    }
}

static void *visible_follower(void *field, void **fa)
{
    u32 count;
    void *tail;
    *fa = find_follower(FIELD_ACTORSYS(field), &count, &tail);
    if (!*fa || st.waiting || CheckActorFlag(*fa, AF_HIDDEN) || st.seq)
        return 0;
    return *fa;
}

/* Script ops run here (talk.h): Surf by the follower, recall. -> 1 when the script must wait */
static int wait_seq(void *vm, void *env)
{
    (void)vm;
    (void)env;
    return st.seq == SEQ_NONE;
}

static int follow_op(void *field, void *vm, u32 op, u32 arg, u16 *ret)
{
    void *fa;
    *ret = 0;
    if (!visible_follower(field, &fa))
        return 0;
    if (op == TALK_OP_SURF) {
        /* HGSS CallFieldTask_Surf: the follower is the user, visible, next to the player, who
         * walks: no cut-in; hop (two if Water: +1 mood), cry, then it jumps in (SEQ_SURF) */
        GPos p, f;
        FldAct_GetGPos(FindPlayerFieldActor(FIELD_ACTORSYS(field)), &p);
        FldAct_GetGPos(fa, &f);
        if (FieldPlayer_GetExState(FIELD_PLAYER(field)) != 0 || !adjacent(&p, &f)
            || !talk_react(field, fa, arg, TYPE_WATER, 1))
            return 0;
        *ret = 1;
        seq_start(SEQ_SURF);
    } else {
        seq_start(SEQ_RECALL);  /* HGSS: after the cut-in of a move used by another party member */
    }
    VM_SetNativeCallback(vm, wait_seq);
    return 1;
}

/* Field-move and warp GameEvents call event_hold in their first state and wait while it returns
 * HOLD_WAIT (HGSS's TaskManager_Call of the recall task or the emotion hop). */
enum { HOLD_GO, HOLD_WAIT, HOLD_REACTED };
enum { EV_WARP, EV_WARP_PAD, EV_FLY, EV_SWEET_SCENT };

__attribute__((noinline)) static int event_hold(void *field, u32 kind, u32 arg)
{
    if (st.hold) {
        if (st.seq || talk_busy())
            return HOLD_WAIT;
        st.hold = 0;
        return st.hold_res;
    }
    void *fa;
    if (!visible_follower(field, &fa)) {
        /* back from the party menu: follow_tick puts it back within a tick */
        if (!fa && st.have_pos && st.settle < 4) {
            st.settle++;
            return HOLD_WAIT;
        }
        st.settle = 0;
        return HOLD_GO;
    }
    st.settle = 0;
    st.hold_res = HOLD_GO;
    switch (kind) {
    case EV_WARP:
    case EV_WARP_PAD: {
        /* HGSS sub_02055DBC: the recall plays before the fade when the destination doesn't allow
         * the follower; warp panels (field_warp_tasks.c) always recall it, and it comes back out
         * of its ball on arrival */
        u32 mode = zone_mode(arg);
        int forbid = mode == ZONE_PREVENT || (mode == ZONE_HEIGHT_RESTRICT && st.size == SIZE_LARGE);
        if (!forbid && kind == EV_WARP)
            return HOLD_GO;
        if (!forbid)
            st.ball_next = 1;
        st.have_pos = 0;
        seq_start(SEQ_RECALL);
        break;
    }
    case EV_FLY: {
        /* HGSS sub_02067C30: a Fly user other than the lead -> recall; the lead itself hops (two if
         * Flying: +1 mood) and cries before the take-off */
        u32 lead;
        talk_lead(GSYS_GetGameData(FIELD_GSYS(field)), &lead);
        if (arg != lead)
            seq_start(SEQ_RECALL);
        else if (!talk_react(field, fa, arg, TYPE_FLYING, 1))
            return HOLD_GO;
        break;
    }
    case EV_SWEET_SCENT:
        /* HGSS Task_UseSweetScentInField: the follower as the user hops (two if Grass) instead
         * of the cut-in */
        if (FieldPlayer_GetExState(FIELD_PLAYER(field)) != 0 || !talk_react(field, fa, arg, TYPE_GRASS, 0))
            return HOLD_GO;
        st.hold_res = HOLD_REACTED;
        break;
    }
    st.hold = 1;
    return HOLD_WAIT;
}

/* Script command 0x89 (a free slot in the OVL_12 command table), used by talk.s:
 *     .hword 0x0089, OP, DEST_VAR, ARG      ; ARG is a constant or a variable
 * Op 0 is a probe (dest = arg + 1); talk.h has the others. Returns 1 when the script waits. */
int follow_script_cmd(void *vm, void *env)
{
    u32 op = VM_ReadU16(vm);
    u16 *dest = ScriptReadVar(vm, env);
    u32 arg = ScriptReadAny(vm, env);
    if (op == 0) {
        *dest = arg + 1;
        follow_dbg[0] = 0xC0DE0000 | arg;
#ifdef FOLLOW_TEST_BIKE
        if (arg == 7)   /* test builds: the probe toggles the bike (as using the Bicycle does) */
            Field_ToggleCycling(GSYS_GetField(FieldScriptEnv_GetGameSystem(env)));
#endif
        return 0;
    }
    if (op < TALK_OP_FIRST || op > TALK_OP_LAST)
        return 0;
    void *field = GSYS_GetField(FieldScriptEnv_GetGameSystem(env));
    u32 count;
    void *tail;
    void *fa = find_follower(FIELD_ACTORSYS(field), &count, &tail);
    u16 ret;
    int wait = op == TALK_OP_SURF || op == TALK_OP_RECALL ? follow_op(field, vm, op, arg, &ret)
                                                          : talk_op(field, fa, vm, op, arg, &ret);
    follow_dbg[5]++;
    follow_dbg[6] = op << 16 | ret;
    follow_dbg[7] = follow_dbg[7] << 4 | op;
    *dest = ret;
    return wait;
}

/* Replaces `bl Field_UpdateActors` (0x02180B00) in FieldRoutine_Run. */
void follow_hook_field_frame(void *field)
{
    Field_UpdateActors(field);
    ballfx_tick(field);
    follow_tick(field);
}

/* GameEvent wrappers (build_followers.py puts them in place of the vanilla callbacks; linked right
 * after the two entry points above, so their addresses don't change between builds). */
#define MAPCHANGE_FIELD(w)  (*(void **)((u8 *)(w) + 0x08))
#define MAPCHANGE_DEST(w)   (*(u16 *)((u8 *)(w) + 0x14))    /* destination zone */

/* doors, stairs, warp tiles (EventMapChangeWarp_CreateGrid / _CreateRail / _CreateFromEntity);
 * state 0 freezes the actors and starts the fade */
int follow_ev_warp(void *ev, int *state, void *work)
{
    if (*state == 0 && event_hold(MAPCHANGE_FIELD(work), EV_WARP, MAPCHANGE_DEST(work)) == HOLD_WAIT)
        return 0;
    return EventMapChangeWarp_Callback(ev, state, work);
}

int follow_ev_warp_pad(void *ev, int *state, void *work)
{
    if (*state == 0 && event_hold(MAPCHANGE_FIELD(work), EV_WARP_PAD, MAPCHANGE_DEST(work)) == HOLD_WAIT)
        return 0;
    return EventMapChangeWarpPad_Callback(ev, state, work);
}

/* Fly from the party menu: the event doesn't keep the user's slot (use +0, u16) */
void *follow_ev_fly_create(void *use, void *params)
{
    st.fly_slot = *(u16 *)use;
    return EventFly_Create(use, params);
}

int follow_ev_fly(void *ev, int *state, void *work)
{
    if (*state == 0 && event_hold(GSYS_GetField(*(void **)work), EV_FLY, st.fly_slot) == HOLD_WAIT)
        return 0;
    return EventFly_Callback(ev, state, work);
}

/* Sweet Scent (work +0 u8 user slot, 0xFF for Honey; +0xC field): states 0-4 are the HM pose and the
 * cut-in, 5 the effect */
int follow_ev_sweet_scent(void *ev, int *state, void *work)
{
    if (*state == 0 && *(u8 *)work < 6) {
        int r = event_hold(*(void **)((u8 *)work + 0x0C), EV_SWEET_SCENT, *(u8 *)work);
        if (r == HOLD_WAIT)
            return 0;
        if (r == HOLD_REACTED)
            *state = 5;
    }
    return EventSweetScent_Callback(ev, state, work);
}
