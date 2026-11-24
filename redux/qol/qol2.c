/* ReRedux qol2: more "slow game" fixes (qol2.py lists the sites; spec build/research_qol2.md).
 *
 * Gating:
 *  - everything below rides on the speed-ups flag 0x5DA (set = OFF), like speed.c, except
 *  - auto-run: flag 0x5DC (set = auto-run OFF, so new and old saves get it ON);
 *  - quick Surf: flag 0x5DE (a script edit, qol2.py; quick save 0x5DD is in fastsave.c);
 *  - static (qol2.py): boot / title / C-Gear prompt (no save is loaded yet), Battle Style "Set" for
 *    new games, the "1, 2, and... Ta-da!" text pauses.
 * Two kinds of change, as in speed.c:
 *  - runtime byte patches (qol2_rtp.h, written by speed.c's qol_rtp_apply) for overlays that come and
 *    go. They are checked every frame AND right after every overlay load (GFL_OvlLoad hook), so an
 *    overlay that runs in the frame it is loaded (encounter effect, Pokédex registration, ...)
 *    starts with the right bytes;
 *  - redirected calls whose thunks check qol2_on: 3D cut-ins 2x, wipes /2.
 * (No sound may be cut off, so these stay vanilla: the capture / level-up / move-learned jingles (the A/B
 * skip cut them), the evolution and egg-hatch scenes (the A-skip left their sound effects out and cut their
 * music short), the PC's Box animations (x2 cut its sounds).) */
#include "qol.h"
#include "speed.h"

void *GSYS_GetGameData(void *gsys);
void *GameData_GetEventWork(void *gd);
int EventWork_FlagGet(void *ew, u32 flag);
void speed_frame(void);
int q2_FieldEffectCallback(void *ev, u32 *seq, void *work);
int q2_FS_LoadOverlay(u32 target, u32 id);

extern u32 turbo_dbg __attribute__((weak));     /* turbo.c TurboDbg: byte 1 = live (2x field this frame) */
#define TURBO_LIVE (&turbo_dbg ? ((const u8 *)&turbo_dbg)[1] : 0)

#define FLAG_SPEED_OFF      0x5DA
#define FLAG_AUTORUN_OFF    0x5DC
#define FLAG_QUICKSAVE      0x5DD

typedef struct {
    u8 override;        /* 0: flags decide; 1: force off; 2: force on (tests; speed_dbg.override too) */
    u8 on;              /* speed-ups on (0x5DA clear) */
    u8 autorun;         /* auto-run on (0x5DC clear) */
    u8 quicksave;       /* 0x5DD set */
    u32 groups;         /* bit g toggles whenever runtime group g is switched */
    u32 ovl_loads;      /* overlay loads seen */
    u16 evo_skips, egg_skips, me_skips, ci_extra_lo;
    u32 ci_extra;       /* extra cut-in callback calls */
    u32 wipes;          /* wipes halved */
    u32 save_steps;     /* extra save steps */
    u32 box_extra;      /* extra Box animation steps */
    u16 qsaves, pad;
    u32 turn_skips;     /* auto-run: runs started without the turn on the spot */
} Qol2Dbg;

Qol2Dbg qol2_dbg;
u8 qol2_on = 1;

#define QOL2_GROUPS
#include "qol2_rtp.h"           /* enum of the groups */
#undef QOL2_GROUPS
static const Rtp q2rtp[] = {
#include "qol2_rtp.h"
};
#define Q2RTP_COUNT (sizeof(q2rtp) / sizeof(q2rtp[0]))

static int flag(u32 f)
{
    void *gsys = QOL_GSYS;
    void *gd;
    if (!gsys || !(gd = GSYS_GetGameData(gsys)))
        return 0;
    return EventWork_FlagGet(GameData_GetEventWork(gd), f);
}

static void q2_update(void)
{
    Qol2Dbg *d = &qol2_dbg;
    u32 ov = d->override ? d->override : speed_dbg.override;
    u32 on = ov ? ov == 2 : !flag(FLAG_SPEED_OFF);
    u32 ar = d->override ? d->override == 2 : !flag(FLAG_AUTORUN_OFF);
    u32 g;
    qol2_on = d->on = on;
    d->autorun = ar;
    d->quicksave = flag(FLAG_QUICKSAVE);
    for (g = 0; g < Q_COUNT; g++)
        if (qol_rtp_apply(q2rtp, Q2RTP_COUNT, g, g == Q_OV36_AUTORUN ? ar : on))
            d->groups ^= 1u << g;
}

void qol2_frame(void)
{
    q2_update();
}

/* arm9 GFL_OvlLoad 0x0203CE82: `bl FS_LoadOverlay(target, id)` -> here: patch the new overlay at once */
extern void menuspeed_ovl_loaded(void) __attribute__((weak));

int qol2_ovl_load(u32 target, u32 id)
{
    int r = q2_FS_LoadOverlay(target, id);
    if (r) {
        qol2_dbg.ovl_loads++;
        speed_frame();          /* speed.c's groups (idempotent) */
        q2_update();
        if (menuspeed_ovl_loaded)
            menuspeed_ovl_loaded();     /* menuspeed.c's groups */
    }
    return r;
}

/* (evolution / egg hatch: no A-skip any more. Skipping the evolution flicker or the egg wobble left their
 * sound effects out and cut the scene's music short; B still cancels an evolution, as in vanilla.) */

/* --- 3D cut-ins (Fly, HM cut-ins, trainer VS cut-in): play loop at 2x ------------------------------- *
 * ov36 EventFieldEffect_Create's callback literal -> here. Not while the R turbo already runs the
 * field at 2x (no 4x). */
int qol2_ci2x(void *ev, u32 *seq, void *work)
{
    int r = q2_FieldEffectCallback(ev, seq, work);
    if (r == 0 && *seq == 9 && qol2_on && !TURBO_LIVE) {
        r = q2_FieldEffectCallback(ev, seq, work);
        qol2_dbg.ci_extra++;
    }
    return r;
}

/* --- wipes: GFL_WipeSet div (frames per step) halved --------------------------------------------------
 * arm9 0x020279B8 (after GFL_WipeSet's push {r4-r7, lr}; sub sp, #0x24): `ldr r5, [sp, #0x3C]; adds r4,
 * r0, #0` -> bl here. The caller's div is at [sp, #0x38] here (bl leaves sp as it was); r0-r3 are live. */
__attribute__((naked)) void qol2_wipe_hook(void)
{
    __asm__ volatile(
        ".syntax unified\n"
        "adds r4, r0, #0\n"
        "ldr r5, =qol2_on\n"
        "ldrb r5, [r5]\n"
        "cmp r5, #0\n"
        "beq 1f\n"
        "ldr r5, [sp, #0x38]\n"
        "cmp r5, #4\n"
        "blt 1f\n"
        "adds r5, #1\n"
        "lsrs r5, r5, #1\n"
        "str r5, [sp, #0x38]\n"
        "ldr r5, =qol2_dbg\n"
        "push {r0}\n"
        "ldr r0, [r5, #0x18]\n"         /* qol2_dbg.wipes */
        "adds r0, #1\n"
        "str r0, [r5, #0x18]\n"
        "pop {r0}\n"
        "1:\n"
        "ldr r5, [sp, #0x3C]\n"
        "bx lr\n"
        ".ltorg\n"
        ".syntax divided\n");
}

/* (save steps per update and quick save moved to fastsave.c; save_steps / qsaves stay 0) */

/* (Box animations 2x removed: the PC's sounds were cut off; qol2_dbg.box_extra stays 0) */

/* --- auto-run: no turn on the spot before running off in a new direction -----------------------------
 * FUN_0219BBA8 (player standing, a direction held that it doesn't face): vanilla turns on the spot first
 * (an 8-frame turn; a tap shorter than that only turns) unless B is held with the Running Shoes. With
 * auto-run, running is "B not held", so the turn only comes with B held (walking), as in vanilla.
 * Exception: toward the follower's tile a tap still turns (it's pass-through, so walking into it doesn't
 * turn you to face it; this keeps talking to it as before). -> 1: move at once, 0: turn first. */
void *GSYS_GetField(void *gsys);
void FldAct_GetGPos(void *actor, void *out);

static int follower_on(u32 x, u32 z)
{
    void *gsys = QOL_GSYS;
    u8 *field = gsys ? GSYS_GetField(gsys) : 0;
    u8 *sys = field ? *(u8 **)(field + 0x40) : 0;
    u8 *base;
    u32 i, n;
    if (!sys)
        return 0;
    base = *(u8 **)(sys + 0x1C);
    n = *(u16 *)(sys + 0x04);
    for (i = 0; base && i < n; i++) {
        u8 *a = base + i * 0x100;
        if ((*(u32 *)a & 1) && *(u16 *)(a + 0x08) == 0xF8 && !(*(u32 *)a & 4)) {
            u16 g[3];
            FldAct_GetGPos(a, g);
            return g[0] == x && g[2] == z;
        }
    }
    return 0;
}

#define PAD_B               2

int qol2_turn_skip(u8 *in, void *actor)
{
    u32 b_held = *(u32 *)(in + 4) & PAD_B;
    u32 dir = *(u16 *)(in + 8);
    u16 g[3];
    if (!qol2_dbg.autorun)
        return b_held != 0;         /* vanilla */
    if (b_held)
        return 0;                   /* walking: turn first */
    FldAct_GetGPos(actor, g);
    if (dir < 4 && follower_on(g[0] + (dir == 3) - (dir == 2), g[2] + (dir == 1) - (dir == 0)))
        return 0;
    qol2_dbg.turn_skips++;
    return 1;
}

/* ov36 0x0219BBDC (r4 = input: +4 held keys, +8 direction; r5 = player actor):
 * `ldr r1, [r4, #4]; movs r0, #2` -> bl here; the caller goes on with `tst r0, r1; bne move` */
__attribute__((naked)) void qol2_turn_hook(void)
{
    __asm__ volatile(
        ".syntax unified\n"
        "push {r4, lr}\n"
        "movs r0, r4\n"
        "movs r1, r5\n"
        "ldr r3, =qol2_turn_skip\n"
        "blx r3\n"
        "lsls r1, r0, #1\n"
        "movs r0, #2\n"
        "pop {r4, pc}\n"
        ".ltorg\n"
        ".syntax divided\n");
}
