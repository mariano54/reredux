/* ReRedux speed-ups (speed.py lists the hook sites; research in build/research_speed.md).
 *
 * On unless the player turned them off: event flag 0x5DA set = speed-ups OFF (read every frame, so
 * the settings menu can toggle it at any time). Two kinds of change:
 *  - runtime byte patches (speed_rtp.h): walk/run speed, wait acmds, balloons, fades, doors, shop,
 *    heal, VM resume. Overlays are reloaded on every map change, so speed_frame() checks
 *    each patch group every frame and writes the fast bytes (speed-ups on) or the vanilla bytes (off)
 *    whenever its overlay is loaded, then flushes the caches for the written range.
 *  - redirected calls whose thunks check speed_on: VMSleep, script camera moves, scripted walks,
 *    FadeEx, battle message waits, door sequences (they gate the door prop speed-up).
 * Battle animations keep vanilla timing (no extra tick, no VM resume: both cut sounds off); battle
 * messages auto-advance after 0.75x the wait. The R turbo's battle tick is in turbo.c.
 * Text: new games start with text speed Fast (a static patch of the config defaults; the player's
 * option is respected, Normal/Slow keep their vanilla speeds). */
#include "qol.h"
#include "speed.h"

/* B2 (followers/syms.ld, speed.py SYMS) */
void *GSYS_GetGameData(void *gsys);
void *GameData_GetEventWork(void *gd);
int EventWork_FlagGet(void *ew, u32 flag);
void FieldScriptEnv_SetWaitCounter(void *env, u32 n);
u32 FldCam_MoveTo(void *cam, void *target, u32 frames);        /* EVCameraMoveTo / MoveToCommon */
u32 FldCam_Return(void *cam, void *target, u32 frames);        /* EVCameraReturn */
u32 FldCam_MoveToDefault(void *cam, u32 frames);               /* EVCameraMoveToDefault */
void FldAct_SetAcmd(void *actor, u32 code);
void GFL_FadeSet(u32 mode, u32 from, u32 to, s32 wait);
int DoorEnterSeq(void *ev, u32 *seq, void *work);
int DoorExitSeq(void *ev, u32 *seq, void *work);

#ifdef QOL_FOLLOWERS
extern u8 follow_speed;         /* followers/follow.c: walk / run acmds to match the player */
#endif

#define FLAG_SPEED_OFF  0x5DA

SpeedDbg speed_dbg;             /* override: test scripts poke 1 (force off) or 2 (force on) */
u8 speed_on = 1;

static int qol_flag(u32 flag)
{
    void *gsys = QOL_GSYS;
    void *gd;
    if (!gsys || !(gd = GSYS_GetGameData(gsys)))
        return 0;
    return EventWork_FlagGet(GameData_GetEventWork(gd), flag);
}

/* --- runtime byte patches --------------------------------------------------------------------------- */

enum { G_ARM9, G_OV36, G_OV36_DOOR, G_OV12, G_OV33, G_OV167, G_COUNT };

static const Rtp rtp[] = {
#include "speed_rtp.h"
};
#define RTP_COUNT (sizeof(rtp) / sizeof(rtp[0]))

typedef void (*cache_fn)(void *addr, u32 len);
#define DC_FlushRange       ((cache_fn)0x0207B0AC)     /* ARM; clean + invalidate */
#define IC_InvalidateRange  ((cache_fn)0x0207B0E8)     /* ARM */

static int same(const u8 *a, const u8 *b, u32 n)
{
    while (n--)
        if (*a++ != *b++)
            return 0;
    return 1;
}

/* Write group g's fast (want = 1) or vanilla bytes, if all of the group is one or the other
 * (shared with qol2.c: speed.h). */
int qol_rtp_apply(const Rtp *tab, u32 n, u32 g, u32 want)
{
    u32 i, todo = 0;
    /* Fast path (this runs for every group every frame: the full check cost ~15k ARM9 cycles per frame,
     * emulator load): look at the group's first entry only. Already the wanted bytes -> the group was
     * written whole (overlays load whole, so a reload shows in every entry) -> nothing to do; neither
     * -> not loaded. Only the other state needs the full check below. */
    static const Rtp *ftab[2];
    static u8 first[2][32];             /* per table: index of each group's first entry (0xFF none) */
    u32 t = ftab[0] == tab ? 0 : ftab[1] == tab ? 1 : !ftab[0] ? 0 : 1;
    if (ftab[t] != tab) {
        ftab[t] = tab;
        for (i = 0; i < 32; i++)
            first[t][i] = 0xFF;
        for (i = n; i-- > 0;)
            if (tab[i].group < 32)
                first[t][tab[i].group] = i;
    }
    i = g < 32 ? first[t][g] : 0xFF;
    if (i >= n)
        return 0;
    if (same((const u8 *)tab[i].addr, want ? tab[i].fast : tab[i].van, tab[i].len) ||
        !same((const u8 *)tab[i].addr, want ? tab[i].van : tab[i].fast, tab[i].len))
        return 0;
    for (i = 0; i < n; i++) {
        const Rtp *p = &tab[i];
        if (p->group != g)
            continue;
        const u8 *cur = (const u8 *)p->addr;
        if (same(cur, want ? p->fast : p->van, p->len))
            continue;
        if (!same(cur, want ? p->van : p->fast, p->len))
            return 0;                   /* not loaded (another overlay there, or a partial match) */
        todo++;
    }
    if (!todo)
        return 0;
    for (i = 0; i < n; i++) {
        const Rtp *p = &tab[i];
        u8 *cur = (u8 *)p->addr;
        const u8 *src = want ? p->fast : p->van;
        u32 k;
        if (p->group != g || same(cur, src, p->len))
            continue;
        for (k = 0; k < p->len; k++)
            cur[k] = src[k];
        DC_FlushRange(cur, p->len);
        IC_InvalidateRange(cur, p->len);
        speed_dbg.writes++;
    }
    return 1;
}

static void rtp_group(u32 g, u32 want)
{
    if (qol_rtp_apply(rtp, RTP_COUNT, g, want))
        speed_dbg.groups ^= 1u << g;    /* toggles each time a group changes state: for tests */
}

/* --- the VM resume patch: field scripts only -------------------------------------------------------
 * The ARM9 group (VM_Run: resume right after a wait) is shared by every GFL VM. It is meant for the field's
 * script VMs. In a battle it changed the effect VM's timing: the Poke Ball dropped short and wobbled in
 * mid-air, and sounds started (and were stopped) a frame early. So it is on only while the field is loaded
 * (overlay 36: FieldRoutine_Run's first words at 0x0217FF64) and the battle view is not (overlay 168:
 * BTLV_EFFECT_Main's literal 0x021DF2C0 = 0x021F4240). Battles, the evolution and every other proc keep
 * vanilla VM timing. */
#define FIELD_RUN_WORDS     ((const u32 *)0x0217FF64)
#define BTLV_EFFECT_LIT     (*(const u32 *)0x021DF2C0)
#define BTLV_EFFECT_WORK    0x021F4240

static int field_only(void)
{
    return FIELD_RUN_WORDS[0] == 0x1C0DB570 && FIELD_RUN_WORDS[1] == 0x68681C06 &&
           BTLV_EFFECT_LIT != BTLV_EFFECT_WORK;
}

/* --- per frame -------------------------------------------------------------------------------------- */

void speed_frame(void)
{
    u32 on = speed_dbg.override ? speed_dbg.override == 2 : !qol_flag(FLAG_SPEED_OFF);
    u32 g;
    speed_on = on;
#ifdef QOL_FOLLOWERS
    follow_speed = on;
#endif
    for (g = 0; g < G_COUNT; g++)
        rtp_group(g, g == G_OV36_DOOR ? on && qol_header.frames - speed_dbg.door_frame < 4
                     : g == G_ARM9 ? on && field_only() : on);
    speed_dbg.on = on;
}

/* --- script VM: VMSleep x0.625 (not right after SEPlay / BGMPlay / PVPlay) -------------------------- */

static u32 vm_u16(const u8 *p)
{
    return p[0] | p[1] << 8;
}

void vmsleep_c(void *env, u32 n, u8 *vm)
{
    const u8 *pc = *(const u8 **)(vm + 0x20);       /* after VMSleep's argument */
    if (speed_on && n > 2) {
        u32 prev4 = vm_u16(pc - 8), prev6 = vm_u16(pc - 10);
        if (prev4 != 0xA6 && prev4 != 0x98 && prev6 != 0xAB)
            n = (n * 5 + 4) >> 3;
    }
    FieldScriptEnv_SetWaitCounter(env, n);
}

/* OVL_12 0x021541AE (VMSleep cmd): `bl SetWaitCounter(env, n)` -> here; r5 = the VM */
__attribute__((naked)) void vmsleep_hook(void)
{
    __asm__ volatile(
        ".syntax unified\n"
        "movs r2, r5\n"
        "ldr r3, =vmsleep_c\n"
        "bx r3\n"
        ".ltorg\n"
        ".syntax divided\n");
}

/* --- script camera moves x0.69 ---------------------------------------------------------------------- */

static u32 cam_frames(u32 f)
{
    if (!speed_on || f <= 1)
        return f;
    f = (f * 11 + 8) >> 4;
    return f ? f : 1;
}

u32 speed_cam_move_to(void *cam, void *target, u32 frames)
{
    return FldCam_MoveTo(cam, target, cam_frames(frames));
}

u32 speed_cam_return(void *cam, void *target, u32 frames)
{
    return FldCam_Return(cam, target, cam_frames(frames));
}

u32 speed_cam_default(void *cam, u32 frames)
{
    return FldCam_MoveToDefault(cam, cam_frames(frames));
}

/* --- scripted walks (move lists run by FieldAcmdTCB): 8 -> 6 updates, 4 -> 3 ------------------------
 * Only the table-driven acmds (0x4C, 0x50) end exactly on the tile for these counts. */
void speed_acmd_commit(void *actor, u32 code)
{
    if (speed_on) {
        if (code >= 0x0C && code < 0x10)
            code += 0x4C - 0x0C;
        else if (code >= 0x10 && code < 0x14)
            code += 0x50 - 0x10;
    }
    FldAct_SetAcmd(actor, code);
}

/* --- FadeEx (script cmd 0xB3): wait w -> w / 2 for 1 <= w <= 255 ------------------------------------ */
void speed_fadeex(u32 mode, u32 from, u32 to, s32 w)
{
    if (speed_on && w >= 1 && w <= 255)
        w >>= 1;
    GFL_FadeSet(mode, from, to, w);
}

/* --- door sequences: the door prop anims run at 2x while one of these is active ---------------------- */
void ls_door_enter(void *ev, u32 *seq, void *work) __attribute__((weak));     /* loadspeed.c: early BGM */

int speed_door_enter(void *ev, u32 *seq, void *work)
{
    speed_dbg.door_frame = qol_header.frames;
    if (ls_door_enter)
        ls_door_enter(ev, seq, work);
    return DoorEnterSeq(ev, seq, work);
}

void ls_door_exit(void *ev, u32 *seq, void *work) __attribute__((weak));      /* loadspeed.c: camera trace */
int ls_door_exit_ret(u32 s0, u32 *seq, int r) __attribute__((weak));         /* loadspeed.c: chained steps */

int speed_door_exit(void *ev, u32 *seq, void *work)
{
    u32 s0 = *seq;
    int r;
    speed_dbg.door_frame = qol_header.frames;
    if (ls_door_exit)
        ls_door_exit(ev, seq, work);
    r = DoorExitSeq(ev, seq, work);
    return ls_door_exit_ret ? ls_door_exit_ret(s0, seq, r) : r;
}

/* --- battle messages: the auto-advance wait (80 frames for most messages) x0.75 ----------------------
 * except "X used the Poke Ball!": the ball is thrown when that message ends, so the capture keeps its
 * vanilla timeline. The battle view's effect VM (work at 0x021F4240, +0x188 the VM, its context +0x2C,
 * whose u16 +0x258 is the effect FUN_021E0EE8 started last) is then on effect 566 (the throw). */
#define EFF_BALL_THROW      566

static int ram_ptr(const void *p)
{
    return (u32)p >= 0x02000000 && (u32)p < 0x02400000;
}

static u32 btlv_last_effect(void)
{
    if (BTLV_EFFECT_LIT != BTLV_EFFECT_WORK)
        return 0;
    const u8 *w = *(const u8 **)BTLV_EFFECT_WORK;
    const u8 *vm = ram_ptr(w) ? *(const u8 **)(w + 0x188) : 0;
    const u8 *ctx = ram_ptr(vm) ? *(const u8 **)(vm + 0x2C) : 0;
    return ram_ptr(ctx) ? *(const u16 *)(ctx + 0x258) : 0;
}

u32 speed_msgwait(u32 w)
{
    return speed_on && btlv_last_effect() != EFF_BALL_THROW ? w - (w >> 2) : w;
}

/* OVL_167 0x021D2EA4 (`adds r0, r4, #0; adds r0, #20` before storing r6 as the page/end wait) */
__attribute__((naked)) void speed_msgwait_hook(void)
{
    __asm__ volatile(
        ".syntax unified\n"
        "push {r1, r2, r3, lr}\n"
        "movs r0, r6\n"
        "ldr r3, =speed_msgwait\n"
        "blx r3\n"
        "movs r6, r0\n"
        "adds r0, r4, #0\n"
        "adds r0, #20\n"
        "pop {r1, r2, r3, pc}\n"
        ".ltorg\n"
        ".syntax divided\n");
}
