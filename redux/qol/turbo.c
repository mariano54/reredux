/* ReRedux turbo: press R in the field or in a battle to switch 2x game speed on / off (a short SE
 * says which). Sound is not sped up: music, SEs and cries are clocked by the ARM7 and GFL_SndUpdate
 * still runs once per frame, so waits on sound and VBlank fades stay real time.
 *  - field: Field_CallRoutines runs FieldRoutine_Run and FieldRoutine_RunAltFrame in the same frame
 *    (one full 30 Hz field tick per displayed frame; research_speed.md section 3.2).
 *  - battle (standalone battles only, not link/Wi-Fi): the battle main loop runs twice per frame,
 *    the first time without the 3D draw (section 3.3), but only while no sound effect, cry or jingle
 *    plays: an extra tick then would start the next sound, or stop the playing one, before its end. So
 *    turbo cuts no sound; the silent stretches of a battle (text, menus, gauges) run at 2x.
 * Not available while event flag 0x5DB is set, while a GFL_NET system exists (wireless, IR, Wi-Fi,
 * Union Room), while the game saves; the extra tick is skipped on battle frames with a new button
 * press or touch (no double confirm).
 * Frames that take two VBlanks (heavy maps: in DeSmuME every turbo frame in Castelia does) are only
 * counted (turbo_dbg.overrun / overruns): such a frame runs two ticks in two VBlanks, i.e. normal speed,
 * and skipping the next frame's extra tick (the earlier "overrun guard", which never fired because it
 * read the main-loop counter at 0x0209DA64 instead of the VBlank count) only made turbo slower.
 * The same field hook also runs the low-latency field updates (speed-ups on, turbo off; see "field"). */
#include "qol.h"
#include "speed.h"

void *GSYS_GetGameData(void *gsys);
void *GameData_GetEventWork(void *gd);
int EventWork_FlagGet(void *ew, u32 flag);
void GFL_SndSEPlay(u32 se);
int FieldRoutine_RunAltFrame(void *gsys, void *field);
u32 GFL_PTC_ActiveCount(void);
void GFL_PTC_CalcAll(void);

#define FLAG_TURBO_OFF      0x5DB
#define FIELD_ROUTINE_RUN   0x0217FF65u     /* FieldRoutine_Run (OVL_36) */
#define BTL_MAINLOOP_LOCAL  0x0219BBEDu     /* standalone battle main loop (OVL_167); comm ones stay 1x */
#define HID                 (*(u8 **)0x02141884)
#define TOUCH               (*(u8 **)0x0214188C)
#define GFL_NET             (*(void **)0x021418B0)
/* the hardware VBlank count (OS_GetVBlankCount: HW_VBLANK_COUNT_BUF, bumped by the VBlank interrupt; the
 * counter at 0x0209DA64 counts main-loop frames) */
#define VBLANK_COUNT        (*(volatile u32 *)0x027FFC3C)
#define GD_SAVING           0x1C0           /* u8 in GameData: async save running (0x0201782C) */
#define PAD_R               0x100
#define SE_TURBO_ON         0x54D           /* SEQ_SE_DECIDE2 */
#define SE_TURBO_OFF        0x551           /* SEQ_SE_CANCEL1 */

typedef struct {
    u8 on;              /* toggled by R */
    u8 live;            /* on and allowed this frame */
    u8 overrun;         /* the last main-loop frame took 2+ VBlanks (counted only, see the top) */
    u8 pad0;
    u32 field_frame;    /* qol frame of the last field routine call */
    u32 battle_frame;   /* qol frame of the last battle main-loop call */
    u32 vbl;            /* VBlank count at the previous frame hook */
    u32 extra_field;    /* compressed field ticks so far */
    u32 extra_battle;   /* extra battle ticks so far */
    u8 why;             /* bit 0 flag 0x5DB, 1 net, 2 saving */
    u8 pad[3];
    u32 overruns;       /* turbo frames that took 2+ VBlanks */
    u32 sound_waits;    /* battle frames without the extra tick because a sound played */
} TurboDbg;

TurboDbg turbo_dbg;
u8 turbo_nodraw;
static void lowlat_frame(void);
int GSYS_GetEventRunningFlag(void *gsys);        /* set during the battle's extra tick: BTLV_EFFECT_Main skips its draw half */

static int flag_set(void *gd, u32 flag)
{
    return gd && EventWork_FlagGet(GameData_GetEventWork(gd), flag);
}

static u32 kp_trigger(void)
{
    u8 *hid = HID;
    u8 *kp = hid ? *(u8 **)hid : 0;
    return kp ? *(u16 *)(kp + 0x1C) : 0;
}

void turbo_frame(void)
{
    TurboDbg *t = &turbo_dbg;
    u32 now = qol_header.frames;
    u32 vbl = VBLANK_COUNT;
    void *gsys = QOL_GSYS;
    void *gd = gsys ? GSYS_GetGameData(gsys) : 0;
    t->overrun = vbl - t->vbl >= 2;
    t->vbl = vbl;
    t->why = flag_set(gd, FLAG_TURBO_OFF) | (GFL_NET != 0) << 1 | (gd && *((u8 *)gd + GD_SAVING)) << 2;
    if (t->why & 1) {
        t->on = 0;
    } else if ((kp_trigger() & PAD_R) && !(t->why & 2) &&
               (now - t->field_frame <= 2 || now - t->battle_frame <= 2)) {
        t->on ^= 1;
        GFL_SndSEPlay(t->on ? SE_TURBO_ON : SE_TURBO_OFF);
    }
    if (t->overrun && t->live)
        t->overruns++;
    t->live = t->on && !t->why;
    lowlat_frame();
}

/* --- field ------------------------------------------------------------------------------------------ *
 * B2 splits each 30 Hz field update over two frames: FieldRoutine_Run (input, actors, camera, 3D render
 * phase 1) and FieldRoutine_RunAltFrame (map loaders, 3D render phase 2 + swap request). What an update
 * shows reaches the screen the frame after the Alt frame's swap: 3-4 frames after a key went down.
 *
 * Low-latency field updates (speed-ups on, turbo off): Run and Alt run back to back in the first frame
 * of an update and its second frame is idle (no field routine), so the swap, and the picture, come a
 * frame earlier. The update rate stays 30 Hz: every combined update is followed by one idle frame. Events / scripts (GSYS_Update runs them when GameData's skip counter +0x1CE is 0, before
 * the field routine) and the HID 30 fps key latch (it latches when its phase hid+0x3E becomes even; Run
 * zeroes it) keep their vanilla once-per-update rhythm: after Run + Alt the counter is set to 1 (the idle
 * frame skips events, as vanilla's Alt frame does) and the idle frame resets it to 0 (what Alt's
 * GameData_ResetSkipFrame did).
 *
 * Both schedules show every update for 2 frames; switching keeps that:
 *  - combined -> split (an update that ended late, VCOUNT >= LL_LATE_LINE or a VBlank already passed:
 *    the next one might overrun its frame and hold a picture 3 frames): the next frame runs the next
 *    update's Run at once, instead of idling (events and the key latch are armed for it as turbo does);
 *    its Alt-frame swap then comes 2 frames after the combined update's.
 *  - split -> combined (after LL_COOL..LL_COOL_MAX split updates, doubling after every late one; reset
 *    in a new zone): at an Alt frame, the next frame idles (skip counter 1, latch phase 2 so the
 *    latch happens a frame later, with the update) and the combined update follows.
 * Only a combined update that overruns its frame outright (no warning) holds one picture 3 frames.
 *
 * Re-phase on a new press: a key that goes down in the idle frame of a combined update would wait for
 * the next update (the key latch, events and the update all come a frame later: 0-1 frame, 0.5 on
 * average). When the player stands still and a new press (any key but R) shows up in the idle frame,
 * the update runs in that frame instead: turbo_skip_hook (GSYS_Update's GameData_Is30FPSSkipFrame call,
 * before the events) latches the keys at once (what GFL_HIDUpdateKeypad does when its phase is even),
 * lets the events run, and the field routine call then runs the combined update. Order and count stay
 * vanilla (events -> Run -> Alt once per update); only this update comes a frame early, so the 30 Hz
 * cadence moves a frame earlier (the last picture is shown 1 frame). That frame is paid back once the
 * player stands still with no key held and no event runs: one idle frame more (a picture held 3 frames
 * where nothing moves), so the game never runs ahead by more than one frame (debt 0 / 1) and the update
 * count per second stays 30. */
#define VCOUNT          (*(volatile u16 *)0x04000006)
#define GD_SKIP         0x1CE           /* u8: GameData_Is30FPSSkipFrame counter */
#define GD_ZONE         0x114           /* u16: current zone */
#define FIELD_ROUTINE_ALT   0x0218011Du /* FieldRoutine_RunAltFrame (OVL_36) */
#define LL_LATE_LINE    160             /* a frame's work starts at VBlank (line 192): >= 160 = < 32 lines left */
#define LL_COOL         30              /* split updates before trying combined ones again (1 s) ... */
#define LL_COOL_MAX     900             /* ... doubling after every late one, up to 30 s */
/* The predictable spike: the map streams the next 32x32-tile blocks in the Alt half of the update in
 * which the player (camera) crosses the middle of a block (world x or z = 512 k + 256 units), enough
 * to overrun a combined update in towns (measured in melonDS: Floccesy, Virbank). So the update before
 * such a crossing hands over to split updates (seamless, as above), and split -> combined waits until
 * no crossing is near. */
#define LL_BLOCK        512
#define LL_LINE         256
#define LL_NEAR         16              /* units: within a tile of the line counts as crossing */
#define LL_COOL_LINE    6               /* split updates after a crossing hand-over */
#define FIELD_ACTORSYS(f)   (*(void **)((u8 *)(f) + 0x40))
void *FindPlayerFieldActor(void *sys);

extern u8 speed_on __attribute__((weak));       /* speed.c: speed-ups flag 0x5DA clear */
extern u8 fps60_want __attribute__((weak));     /* fps60.c: no combined updates */
int fps60_rephase_ok(void) __attribute__((weak));        /* fps60.c: this update draws at 60 fps */
void fps60_rephase_alt(int on) __attribute__((weak));    /* fps60.c: the next Alt half draws nothing */
int fps60_static(void) __attribute__((weak));            /* fps60.c: nothing moved in this update */

typedef struct {
    u8 force;           /* tests: 0 speed-ups decide, 1 force off, 2 force on (never falls back) */
    u8 mode;            /* 1: combined updates; 0: vanilla split */
    u8 active;          /* the last update was combined: the next frame idles if within 2 VBlanks */
    u8 near;            /* a block-middle crossing is near (set by every Run) */
    u32 vbl0;           /* VBlank count when the last combined update started */
    u32 busy, idle, late, switches;
    u16 cool, backoff;  /* split updates left before switching back; next cooldown */
    u16 zone, handovers;    /* handovers: combined -> split before a crossing */
    s32 px, pz;         /* the player's world position after the last Run */
    u32 late_idle;      /* idle frames that came only after another VBlank (overrun after the check) */
    /* +0x2C: re-phase on a new press (see above) */
    u8 rephase;         /* set by turbo_skip_hook: this frame's field call runs the update */
    u8 debt;            /* 1: the cadence runs a frame early (one re-phase not paid back yet) */
    u8 repay;           /* this frame is the extra idle frame that pays the debt back */
    u8 still;           /* the player didn't move in the last update */
    u32 rephases, repays, stale;    /* stale: a re-phase whose field call didn't come (counted only) */
    u8 *field;          /* the field of the last routine call */
    s32 py;             /* the player's height after the last Run */
    u8 why;             /* the last new press that didn't re-phase: 1 not the idle frame of a combined
                         * update, 2 debt / player moving, 3 late / not allowed, 4 no Run next (0 = done) */
    u8 rph_off;         /* tests: 1 = no re-phase */
    u8 rephase60;       /* fps60 re-phase: the Alt half ran in turbo_skip_hook, Run comes this frame */
    u8 repay60;         /* split updates: the next Run frame is the extra idle frame (pays the debt) */
    u32 runs;           /* FieldRoutine_Run calls (tests: one per field update) */
    u32 rephases60;     /* fps60 re-phases (also counted in rephases) */
} LowLat;

LowLat lowlat_dbg = {0, 0, 0, 1, 0, 0, 0, 0, 0, 0, LL_COOL, 0xFFFF, 0, 0, 0, 0};

typedef int (*field_fn)(void *gsys, void *field);

/* does [p, p + ahead * v] (fx32) come within LL_NEAR units of a block-middle line (512 k + 256)? */
static int near_line(s32 p, s32 v, s32 ahead)
{
    s32 a = p >> 12, b = (p + ahead * v) >> 12;
    s32 lo = (a < b ? a : b) - LL_NEAR - LL_LINE, hi = (a < b ? b : a) + LL_NEAR - LL_LINE;
    return ((hi >> 9) << 9) >= lo;      /* a multiple of 512 (LL_BLOCK) in [lo, hi] */
}

/* updates the player's position / step (per field update) and says whether a crossing is near */
static int crossing_near(LowLat *L, u8 *field, s32 ahead)
{
    void *sys = FIELD_ACTORSYS(field);
    u8 *pl = sys ? FindPlayerFieldActor(sys) : 0;
    s32 x, z, vx, vz;
    L->still = 0;
    if (!pl)
        return 1;
    x = *(s32 *)(pl + 0x44);
    z = *(s32 *)(pl + 0x4C);
    vx = x - L->px;
    vz = z - L->pz;
    L->px = x;
    L->pz = z;
    if (vx > 0x40000 || vx < -0x40000 || vz > 0x40000 || vz < -0x40000)
        vx = vz = 0;                /* warped */
    L->still = !vx && !vz && *(s32 *)(pl + 0x48) == L->py;
    L->py = *(s32 *)(pl + 0x48);
    return near_line(x, vx, ahead) || near_line(z, vz, ahead);
}

static int lowlat_allowed(const TurboDbg *t)
{
    const LowLat *L = &lowlat_dbg;
    if (L->force)
        return L->force == 2;
    if (&fps60_want && fps60_want)
        return 0;
    return &speed_on && speed_on && !t->live && !(t->why & 6);  /* no wireless / Wi-Fi, not while saving */
}

#define GSYS_FIELD(g)       (*(u8 **)((u8 *)(g) + 0x20))
#define FIELD_ROUTINES      ((const u32 *)0x021C9FD4)  /* OVL_36: {Run, Alt} per field routine index (+0xD4) */
#define PAD_REPHASE         0xEFF       /* every key but R (turbo); L too (the "L=A" button mode) */
int GameData_Is30FPSSkipFrame(void *gd);

/* end of every main-loop frame (turbo_frame) */
static void lowlat_frame(void)
{
    LowLat *L = &lowlat_dbg;
    if (L->rephase) {
        /* the events of a re-phased frame ran but no field routine followed (they changed the proc):
         * vanilla would have run them next frame; start over with split updates */
        L->rephase = 0;
        L->active = 0;
        L->mode = 0;
        L->stale++;
    }
    if (L->rephase60) {
        /* Alt N and the events of N + 1 ran, Run N + 1 didn't come (counted only: it runs at the next
         * routine call, parity and skip counter are set for it) */
        L->rephase60 = 0;
        L->stale++;
    }
}

/* the player stands, nothing holds a key, no event (or, with the 60 fps draws, nothing moved): paying a
 * re-phase back (a picture held a frame longer) can't be seen on the player or the camera */
static int repay_ok(void *gsys, const LowLat *L)
{
    u8 *kp = *(u8 **)HID;
    if (!L->still || *(u32 *)(kp + 0x18) || *(u32 *)(kp + 0x30))
        return 0;
    /* with the 60 fps draws: nothing on screen moved in this update (an open text box, a menu) */
    return (&fps60_static && fps60_static()) || !GSYS_GetEventRunningFlag(gsys);
}

/* the field routine call that comes later in this frame is the normal Run of the field we know */
static int field_runs_next(void *gsys, const LowLat *L)
{
    u8 *f = L->field;
    return f && GSYS_FIELD(gsys) == f && *(u32 *)(f + 0xD4) < 64 &&
           FIELD_ROUTINES[*(u32 *)(f + 0xD4) * 2 + (f[0xD9] & 1)] == FIELD_ROUTINE_RUN;
}

/* GFL_HIDUpdateKeypad's latch (when its phase is even): the keys gathered since the last latch become the
 * 30 fps held / trigger / repeat keys */
static void latch_keys(void)
{
    u8 *kp = *(u8 **)HID;
    *(u32 *)(kp + 0x28) = *(u32 *)(kp + 0x34);
    *(u32 *)(kp + 0x24) = *(u32 *)(kp + 0x30);
    *(u32 *)(kp + 0x2C) = *(u32 *)(kp + 0x38);
    *(u32 *)(kp + 0x34) = 0;
    *(u32 *)(kp + 0x30) = 0;
    *(u32 *)(kp + 0x38) = 0;
}

/* Re-phase with the 60 fps draws (fps60.c, split updates: Run frame = logic + midpoint picture, Alt frame =
 * loaders + real picture). A new press in the Alt frame of update N: the Alt half runs here, before the
 * events, without its picture (fps60_rephase_alt), then the keys are latched, the events of update N + 1 run
 * and the field routine call runs N + 1's Run with its midpoint picture. Order and count as vanilla
 * (Alt N -> events N + 1 -> Run N + 1), a frame early. A vanilla split update (turbo, fallback) can't do
 * this: its Alt half's phase 2 and the next Run's phase 1 would share one swap. */
static int rephase60(u8 *gd, int r)
{
    TurboDbg *t = &turbo_dbg;
    LowLat *L = &lowlat_dbg;
    void *gsys = QOL_GSYS;
    u8 *f = L->field;
    L->why = 5;
    if (L->rph_off || L->rephase || L->rephase60 || L->repay || L->repay60 || L->debt || !L->still)
        return r;
    if (!gsys || !HID || !f || t->live || (t->why & 6) || qol_header.frames - t->field_frame != 1)
        return r;
    if (GSYS_FIELD(gsys) != f || *(u32 *)(f + 0xD4) >= 64 ||
        FIELD_ROUTINES[*(u32 *)(f + 0xD4) * 2 + (f[0xD9] & 1)] != FIELD_ROUTINE_ALT)
        return r;
    L->why = 0;
    fps60_rephase_alt(1);
    *(u32 *)(f + 0xDC) += 1;        /* Field_CallRoutines counts every routine call */
    FieldRoutine_RunAltFrame(gsys, f);  /* always 0; resets the skip counter (GameData_ResetSkipFrame) */
    fps60_rephase_alt(0);
    f[0xD9] = 0;                    /* the routine call this frame is the next update's Run */
    latch_keys();
    gd[GD_SKIP] = 1;                /* as after a call that returned 0 */
    L->rephase60 = 1;
    L->debt = 1;
    L->rephases++;
    L->rephases60++;
    return 0;
}

/* ARM9 0x020169C2 in GSYS_Update: `bl GameData_Is30FPSSkipFrame` (0 = run the events this frame) -> here */
int turbo_skip_hook(u8 *gd)
{
    TurboDbg *t = &turbo_dbg;
    LowLat *L = &lowlat_dbg;
    void *gsys = QOL_GSYS;
    int r = GameData_Is30FPSSkipFrame(gd);
    if (!r || !(kp_trigger() & PAD_REPHASE))
        return r;
    if (&fps60_rephase_ok && fps60_rephase_ok())
        return rephase60(gd, r);
    L->why = 1;
    if (L->rph_off || !L->mode || !L->active || L->rephase || L->repay || !gsys || !HID)
        return r;
    L->why = 2;
    if (L->debt || !L->still)
        return r;
    L->why = 3;
    if (qol_header.frames - t->field_frame != 1 || VBLANK_COUNT - L->vbl0 >= 2 || !lowlat_allowed(t))
        return r;
    L->why = 4;
    if (!field_runs_next(gsys, L))
        return r;
    L->why = 0;
    latch_keys();
    gd[GD_SKIP] = 1;            /* as after a call that returned 0 */
    L->rephase = 1;
    L->debt = 1;
    L->rephases++;
    return 0;
}

int turbo_field_call(void *gsys, u8 *field, field_fn fn)
{
    TurboDbg *t = &turbo_dbg;
    LowLat *L = &lowlat_dbg;
    u8 *gd = GSYS_GetGameData(gsys);
    u32 vbl = VBLANK_COUNT;
    int res;
    t->field_frame = qol_header.frames;
    L->field = field;
    if (gd && *(u16 *)(gd + GD_ZONE) != L->zone) {
        L->zone = *(u16 *)(gd + GD_ZONE);
        L->backoff = LL_COOL;
        if (L->cool > LL_COOL)
            L->cool = LL_COOL;
    }
    if ((u32)fn != FIELD_ROUTINE_RUN) {
        L->active = 0;
        L->rephase = 0;
        L->repay = 0;
        L->rephase60 = 0;
        L->repay60 = 0;
        if ((u32)fn != FIELD_ROUTINE_ALT) {
            L->mode = 0;
            return fn(gsys, field);
        }
        /* the Alt frame of a split update: switch to combined updates after it? */
        res = fn(gsys, field);
        if (res == 0 && gd && !L->mode && !L->cool && (!L->near || L->force) && lowlat_allowed(t)) {
            L->mode = 1;
            L->active = 1;          /* the next frame idles ... */
            L->vbl0 = vbl;
            gd[GD_SKIP] = 1;        /* ... without events (the idle frame resets the counter) */
            HID[0x3E] = 2;          /* ... and latches keys a frame later, with the combined update */
            L->switches++;
        } else if (res == 0 && gd && L->debt && repay_ok(gsys, L) && !t->live && !(t->why & 6)) {
            /* split updates (60 fps draws): pay a re-phase back with an extra idle frame before the next
             * Run (no events then: the counter Alt reset is set again; the key latch a frame later) */
            L->debt = 0;
            L->repay60 = 1;
            L->repays++;
            gd[GD_SKIP] = 1;
            HID[0x3E] = 2;
        }
        return res;
    }
    if (L->repay60) {
        /* the extra idle frame: no Run (no picture either: the last one stays on screen) */
        L->repay60 = 0;
        L->idle++;
        gd[GD_SKIP] = 0;
        field[0xD9] = 1;            /* the caller flips the parity: a Run frame again next time */
        return 0;
    }
    L->rephase60 = 0;
    if (L->active && L->rephase) {
        /* re-phased (turbo_skip_hook: keys latched, events ran): the combined update runs now */
        L->rephase = 0;
    } else if (L->active) {
        /* the idle frame of a combined update. Also when that update overran its frame after the late
         * check (a VBlank between the check and the end of the main loop: the events of this frame were
         * skipped and the keys not latched): the update then took 3 frames, but events and keys stay
         * in step. */
        L->active = 0;
        L->idle++;
        if (vbl - L->vbl0 >= 2)
            L->late_idle++;
        field[0xD9] = 1;            /* the caller flips the parity: a Run frame again next time */
        if (L->repay) {
            L->repay = 0;
        } else if (L->debt && repay_ok(gsys, L) && lowlat_allowed(t)) {
            /* pay a re-phase back: one more idle frame, without events (the counter isn't reset: the
             * next GameData_Is30FPSSkipFrame returns non-zero) and with the key latch a frame later */
            L->debt = 0;
            L->repay = 1;
            L->repays++;
            L->active = 1;
            HID[0x3E] = 2;
            return 0;
        }
        gd[GD_SKIP] = 0;
        if (!lowlat_allowed(t))
            L->mode = 0;            /* a split update starts next frame */
        return 0;
    }
    L->active = 0;
    L->repay = 0;
    L->runs++;
    res = fn(gsys, field);
    if (res != 0) {
        L->mode = 0;
        return res;
    }
    L->near = crossing_near(L, field, 3);
    if (t->live) {
        /* R turbo: one full update every frame */
        L->mode = 0;
        FieldRoutine_RunAltFrame(gsys, field);  /* always returns 0 */
        field[0xD9] = 1;        /* the caller flips the parity: the next frame is a Run frame again */
        /* FieldRoutine_Run zeroed the HID 30 fps latch phase; at 1 the next GFL_HIDUpdate latches keys */
        HID[0x3E] = 1;
        t->extra_field++;
        return 0;
    }
    if (!L->mode || !gd || !lowlat_allowed(t)) {
        L->mode = 0;
        if (L->cool)
            L->cool--;
        return 0;               /* split: the Alt half runs next frame */
    }
    FieldRoutine_RunAltFrame(gsys, field);
    field[0xD9] = 1;
    L->busy++;
    if (VBLANK_COUNT != vbl || (VCOUNT & 0x1FF) >= LL_LATE_LINE) {
        L->late++;
        if (L->force != 2) {
            /* back to split updates; the next one starts next frame: events (the counter stays 0, as
             * Alt left it) and the key latch (phase 1 -> even next frame) are armed for it */
            L->mode = 0;
            HID[0x3E] = 1;
            L->cool = L->backoff;
            L->backoff = L->backoff >= LL_COOL_MAX / 2 ? LL_COOL_MAX : L->backoff * 2;
            return 0;
        }
    } else if (L->near && L->force != 2) {
        /* a block-middle crossing within the next updates: hand over to split updates now */
        L->handovers++;
        L->mode = 0;
        HID[0x3E] = 1;
        L->cool = LL_COOL_LINE;
        return 0;
    }
    gd[GD_SKIP] = 1;            /* the idle frame skips events, like vanilla's Alt frame */
    L->active = 1;
    L->vbl0 = vbl;
    return 0;
}

/* OVL_36 0x021803C2 in Field_CallRoutines: `blx r2; adds r6, r0, #0` -> bl here (r0 gsys, r1 field,
 * r2 routine); the caller keeps the routine's result in r6 */
__attribute__((naked)) void turbo_call(void)
{
    __asm__ volatile(
        ".syntax unified\n"
        "push {r4, lr}\n"
        "ldr r4, =turbo_field_call\n"
        "blx r4\n"
        "movs r6, r0\n"
        "pop {r4, pc}\n"
        ".ltorg\n"
        ".syntax divided\n");
}

/* --- battle ----------------------------------------------------------------------------------------- */

typedef int (*btl_loop)(void *wk);

/* --- battle sounds (B2 GFL / NNS state) -------------------------------------------------------------
 * SE players: NNS players 1-5 (GFL_SndSEIsPlaying 0x02006294 reads player i + 1), u16 count of playing
 * sequences at 0x0214932C + 0x24 * player. Cries: PokeVoice slots at 0x0213B27C (0x34 bytes, +0 = 1 while
 * playing; slot count u16 at 0x0213B31A, at most 2). Jingles (level-up, capture, move learned, ...): GFL's
 * BGM stack level (0x0209DA74) above the battle's own level (the field BGM stays pushed under the battle
 * BGM; a jingle pushes the battle BGM). */
#define NNS_PLAYER_SEQS(p)  (*(volatile const u16 *)(0x0214932C + 0x24 * (p)))
#define VOICE_PLAYING(i)    (*(volatile const u32 *)(0x0213B27C + 0x34 * (i)))
#define VOICE_SLOTS         (*(volatile const u16 *)0x0213B31A)
#define BGM_LEVEL           (*(volatile const u32 *)0x0209DA74)

static u32 btl_bgm_level;   /* the BGM stack level when the battle started */

static int btl_sound_busy(void)
{
    u32 i, n = VOICE_SLOTS;
    for (i = 1; i <= 5; i++)
        if (NNS_PLAYER_SEQS(i))
            return 1;
    for (i = 0; i < n && i < 2; i++)
        if (VOICE_PLAYING(i) == 1)
            return 1;
    return BGM_LEVEL > btl_bgm_level;
}

int turbo_battle_tick(void *wk, btl_loop fn)
{
    TurboDbg *t = &turbo_dbg;
    if (qol_header.frames - t->battle_frame > 2)
        btl_bgm_level = BGM_LEVEL;      /* a new battle: its BGM level */
    t->battle_frame = qol_header.frames;
    if ((u32)fn == BTL_MAINLOOP_LOCAL && t->live) {
        u8 *touch = TOUCH;
        if ((kp_trigger() & ~PAD_R) || (touch && *(u16 *)(touch + 0x60))) {
            /* a new press this frame: no extra tick (no double confirm) */
        } else if (btl_sound_busy()) {
            t->sound_waits++;
        } else {
            int r;
            turbo_nodraw = 1;
            r = fn(wk);
            turbo_nodraw = 0;
            t->extra_battle++;
            if (r)
                return r;       /* the battle ended in the extra tick */
        }
    }
    return fn(wk);
}

/* OVL_167 0x02199C18 in the battle proc main: `adds r0, r5, #0; blx r1` (r1 = main-loop fn) -> bl here */
__attribute__((naked)) void turbo_battle_hook(void)
{
    __asm__ volatile(
        ".syntax unified\n"
        "push {r4, lr}\n"
        "movs r0, r5\n"
        "ldr r4, =turbo_battle_tick\n"
        "blx r4\n"
        "pop {r4, pc}\n"
        ".ltorg\n"
        ".syntax divided\n");
}

/* OVL_168 0x021DF284, start of BTLV_EFFECT_Main's draw half (`bl GFL_G3DSysReset`) -> bl here. In the
 * extra tick: particle calc only, then return from BTLV_EFFECT_Main (its frame: push {r3, r4, r5, lr}). */
__attribute__((naked)) void turbo_draw_gate(void)
{
    __asm__ volatile(
        ".syntax unified\n"
        "ldr r3, =turbo_nodraw\n"
        "ldrb r3, [r3]\n"
        "cmp r3, #0\n"
        "bne 1f\n"
        "ldr r3, =0x02049A99\n"         /* GFL_G3DSysReset, returns to BTLV_EFFECT_Main */
        "bx r3\n"
        "1:\n"
        "ldr r3, =GFL_PTC_ActiveCount\n"
        "blx r3\n"
        "cmp r0, #0\n"
        "beq 2f\n"
        "ldr r3, =GFL_PTC_CalcAll\n"
        "blx r3\n"
        "2:\n"
        "pop {r3, r4, r5, pc}\n"
        ".ltorg\n"
        ".syntax divided\n");
}
