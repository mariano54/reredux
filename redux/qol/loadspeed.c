/* ReRedux loadspeed: shorter loading and music waits on warps (loadspeed.py lists the sites and the
 * measurements; harness build/scripts/warpspeed/).
 *
 * The card timing (ROM header, static) is in loadspeed.py. The code here, under the speed-ups flag
 * 0x5DA (set = OFF):
 *  - BGM change on a warp (FUN_0202FFC8, "prepare": fade the field BGM out, load the next one): the
 *    fade-out is 30 sound frames instead of 60. The sound driver only counts main-loop frames, which
 *    nearly stop while the map loads, so vanilla's 60-frame fade ran on ~35 frames after the new map
 *    was ready (a black or frozen screen). The music still fades out completely before the next BGM
 *    starts (never cut);
 *  - entering a door: the same BGM request is made when the door starts to open (DoorEnterSeq state
 *    0, from speed.c's DoorEnterSeq wrapper) instead of after the walk-in (state 6, which is then
 *    skipped for that door), so the fade runs during the door animation;
 *  - coming out of a door (DoorExitSeq, still black): state 10 waits for the camera trace (the camera
 *    following the player a few updates late) to replay its queue and stop, one entry per 30 Hz
 *    update (12 frames). The player stands still and the screen is black, so the queue holds his
 *    position only: the trace is stopped at once, as the end of that replay does (FUN_021866D8);
 *  - event steps of the map change chained in one update (chain(), below).
 * Always on (same results, faster code): the Pokémon / record crypto loops and the gate sign re-layout
 * (bottom of this file). */
#include "qol.h"
#include "speed.h"

void *GSYS_GetGameData(void *gsys);
void *GameData_GetEventWork(void *gd);
int EventWork_FlagGet(void *ew, u32 flag);
void ls_SendRequest(void *fs, u32 cmd, u32 bgm, u32 fade_out, u32 fade_in);
void ls_BGMPrepare(void *fs, void *gd, u32 zone, u32 season);
int ls_XfadeCallback(void *ev, u32 *seq, void *work);
int ls_SndWaitCallback(void *ev, u32 *seq, void *work);
int ls_FieldOpenCallback(void *ev, u32 *seq, void *work);
int ls_MapCoreCallback(void *ev, u32 *seq, void *work);

#define FLAG_SPEED_OFF  0x5DA
#define PREP_FADE       30      /* vanilla 60 */

typedef struct {
    u8 override;        /* 0: flag 0x5DA decides (speed_dbg.override too); 1 force off; 2 force on */
    u8 on;
    u16 fades;          /* BGM prepare requests shortened */
    u16 early;          /* door BGM requests made at the door's start */
    u16 skipped;        /* their state-6 duplicates skipped */
    u16 early_zone, prep_zone;  /* last early request's zone, last state-6 call's zone (tests) */
    u16 trace_stops;    /* door exits whose camera trace was stopped at once */
    u16 chained;        /* event steps run in the same update as the previous one */
    u16 relayouts;      /* gate sign bitmaps re-laid out without divisions */
    u16 pad;
} LsDbg;

LsDbg ls_dbg;
static u8 ls_on = 1;
static void *ls_door_work;      /* the DoorEnterSeq work whose BGM request was made early */

static int flag(u32 f)
{
    void *gsys = QOL_GSYS;
    void *gd;
    if (!gsys || !(gd = GSYS_GetGameData(gsys)))
        return 0;
    return EventWork_FlagGet(GameData_GetEventWork(gd), f);
}

void ls_frame(void)
{
    u32 ov = ls_dbg.override ? ls_dbg.override : speed_dbg.override;
    ls_on = ls_dbg.on = ov ? ov == 2 : !flag(FLAG_SPEED_OFF);
}

/* arm9 0x0202FFFA, FUN_0202FFC8 (BGM prepare for a warp): `bl FieldSnd_SendRequest(fs, 6, bgm, 60, 0)` */
void ls_prepare_req(void *fs, u32 cmd, u32 bgm, u32 fade_out, u32 fade_in)
{
    if (ls_on && fade_out > PREP_FADE) {
        fade_out = PREP_FADE;
        ls_dbg.fades++;
    }
    ls_SendRequest(fs, cmd, bgm, fade_out, fade_in);
}

/* DoorEnterSeq (ov36 0x0219F5DC) work: +0 its parameters (+8 GameData, +0x20 destination zone, +0x45
 * season), +4 FieldSnd. Called by speed.c's wrapper before every step of the sequence. */
void ls_door_enter(void *ev, u32 *seq, void *work)
{
    u8 *w = work, *p;
    (void)ev;
    if (*seq != 0 || ls_door_work == work)
        return;                     /* not the start, or state 0 again: requested already */
    ls_door_work = 0;               /* a new door sequence */
    if (!ls_on)
        return;
    p = *(u8 **)w;
    ls_door_work = work;
    ls_dbg.early++;
    ls_dbg.early_zone = *(u16 *)(p + 0x20);
    ls_BGMPrepare(*(void **)(w + 4), *(void **)(p + 8), *(u16 *)(p + 0x20), p[0x45]);
}

void ls_door_prep_c(void *fs, void *gd, u32 zone, u32 season, void *work)
{
    ls_dbg.prep_zone = zone;
    if (work == ls_door_work) {
        ls_door_work = 0;           /* made at the door's start */
        ls_dbg.skipped++;
        return;
    }
    ls_BGMPrepare(fs, gd, zone, season);
}

/* ov36 0x0219F74A, DoorEnterSeq state 6: `bl FUN_0202FFC8(fs, gd, zone, season)`; r4 = the work */
__attribute__((naked)) void ls_door_prep_hook(void)
{
    __asm__ volatile(
        ".syntax unified\n"
        "push {r4, lr}\n"
        "bl ls_door_prep_c\n"
        "pop {r4, pc}\n"
        ".syntax divided\n");
}

/* DoorExitSeq (ov36 0x0219F380) work: +0 its parameters (+0xC the field map; field map +0x10 the camera;
 * camera +0xEC the trace: +0x28 on, +0x2C stop requested, +0x10 filled). Called by speed.c's wrapper
 * before every step. State 10 waits until the trace is off. */
void ls_door_exit(void *ev, u32 *seq, void *work)
{
    u8 *p, *fm, *cam, *tr;
    (void)ev;
    if (!ls_on || *seq != 10)
        return;
    p = *(u8 **)work;
    fm = *(u8 **)(p + 0xC);
    cam = fm ? *(u8 **)(fm + 0x10) : 0;
    tr = cam ? *(u8 **)(cam + 0xEC) : 0;
    if (tr && *(u32 *)(tr + 0x28) && *(u32 *)(tr + 0x2C)) {
        *(u32 *)(tr + 0x4) = *(u32 *)(tr + 0x8);   /* read index caught up with the write index */
        *(u32 *)(tr + 0x2C) = 0;    /* = FUN_021866D8, the end of the replay */
        *(u32 *)(tr + 0x28) = 0;
        *(u32 *)(tr + 0x10) = 0;
        ls_dbg.trace_stops++;
    }
}

/* --- entering a building: the fade-in's last steps (ov36 0x021B8E10, GameEvent callback) ---------------
 * After the crossfade from the frozen outside picture to the inside (state 1) come six one-update steps:
 * 2 LCD setup, 3 BG affine reset, 4 (once the field map is ready) the touch screen's palettes, 5 its
 * tiles, 6 its map, 7 done: 12 frames with the player still frozen. A callback result of 2 makes the
 * event loop run the event again at once, so steps 2-6 follow each other in one update (the touch
 * screen gets palettes, tiles and map in the same frame). */
int ls_xfade(void *ev, u32 *seq, void *work)
{
    u32 s0 = *seq;
    int r = ls_XfadeCallback(ev, seq, work);
    if (r == 0 && ls_on && s0 >= 2 && s0 <= 6 && *seq == s0 + 1) {
        ls_dbg.chained++;
        return 2;
    }
    return r;
}

/* --- one 30 Hz event update per state: chain the steps of the map change ------------------------------
 * GameSystem's event loop (FUN_02016D74) runs the current event again at once when its callback returns
 * neither 0 (wait) nor 1 (done) -- B2's own events return 0x21 for that -- and resumes a finished event's
 * parent in the same update. These wrappers return 2 when a step only moved to the next state, so its
 * code runs now instead of one update (2 frames) later:
 *  - EventFieldSndWait (after a warp, waits for the BGM change; 0 -> 1 = done);
 *  - EventFieldOpen (1 -> 2: the field is ready -> done);
 *  - EventMapChangeCore (1 -> 2/3 overlay + zone setup, 2 -> 3, 3 -> 4 field open, 4 -> 5 sound wait);
 *  - DoorExitSeq (0 -> 10 -> 1, still black: the camera trace, then the fade-in starts; speed.c). */
static int chain(int r, u32 s0, u32 s1, u32 ok)
{
    if (r == 0 && ls_on && s1 != s0 && (ok >> s0 & 1)) {
        ls_dbg.chained++;
        return 2;
    }
    return r;
}

int ls_sndwait(void *ev, u32 *seq, void *work)
{
    u32 s0 = *seq;
    return chain(ls_SndWaitCallback(ev, seq, work), s0, *seq, 1u << 0);
}

int ls_fieldopen(void *ev, u32 *seq, void *work)
{
    u32 s0 = *seq;
    return chain(ls_FieldOpenCallback(ev, seq, work), s0, *seq, 1u << 1);
}

int ls_mapcore(void *ev, u32 *seq, void *work)
{
    u32 s0 = *seq;
    return chain(ls_MapCoreCallback(ev, seq, work), s0, *seq, 1u << 1 | 1u << 2 | 1u << 3 | 1u << 4);
}

/* speed.c's DoorExitSeq wrapper, after the step */
int ls_door_exit_ret(u32 s0, u32 *seq, int r)
{
    return chain(r, s0, *seq, 1u << 0 | 1u << 10);
}

/* --- route gates: the electronic sign's bitmap re-layout without divisions (always on; same result) ----
 * Entering a gate, ov12 FUN_0216A0B8 renders the sign's text and copies the tiled bitmap into another layout
 * with FUN_0216A004: for every byte i, four library divisions (i / (Wt * r), i % (Wt * r), then / and % r):
 * 15 frames in melonDS. ls_bmp_relayout walks the same index with counters. dst[i] = src[((q1 / 8) * Wt + q2)
 * * D + (q1 % 8) * r + k] with D = depth byte, r = D / 8, Wt = width / 8, q1 = i / (Wt * r), q2 = i % (Wt * r)
 * / r, k = i % r, for i < Wt * (height / 8) * D. GflBitmap: +0 data, +4 width, +6 height, +8 depth. */
void ls_BmpRelayout(void *src_bmp, void *dst_bmp);

void ls_bmp_relayout(void *src_bmp, void *dst_bmp)
{
    const u8 *a = src_bmp;
    u32 wt = *(const u16 *)(a + 4) >> 3, ht = *(const u16 *)(a + 6) >> 3, d = a[8], r = d >> 3;
    s32 n = (s32)(wt * ht * d), i;
    const u8 *src = *(u8 *const *)src_bmp;
    u8 *dst = *(u8 **)dst_bmp;
    u32 q1 = 0, q2 = 0, k = 0;
    if (!wt || !r) {
        ls_BmpRelayout(src_bmp, dst_bmp);      /* degenerate: the original (divides by zero) */
        return;
    }
    for (i = 0; i < n; i++) {
        dst[i] = src[((q1 >> 3) * wt + q2) * d + (q1 & 7) * r + k];
        if (++k == r) {
            k = 0;
            if (++q2 == wt) {
                q2 = 0;
                q1++;
            }
        }
    }
    ls_dbg.relayouts++;
}

/* --- Pokémon / record data crypto, ARM loops (always on; same results) -----------------------------
 * B2 XORs Pokémon data (PML, 0x80 + 0x54 bytes per Pokémon) and the trainer records (0x1D8 bytes) with
 * the LCG stream s = s * 0x41C64E6D + 0x6073 (high halfwords), calling a Thumb function per halfword,
 * and sums the data for the checksums the same way. Entering a Pokémon Center the game checks every
 * medal: it reads all 720 box slots (two parameters each, every read decrypts and re-encrypts that
 * Pokémon) and ~105 records (each read decrypts and re-encrypts the whole record block): 15 frames in
 * melonDS. These loops do the same work 3-4x faster. Entries (ARM; the Thumb entries jump here):
 *   ls_crypt(data, size, seed)  = 0x0201ECDC (Pokémon) and 0x0204411C (records); returns the last
 *                                 halfword written (data when size < 2), as the originals
 *   ls_sum16(data, size)        = 0x0201ED28: u16 sum of the halfwords (the Pokémon checksum)
 *   ls_sum8(data, size)         = 0x02044100: sum of the bytes (the records checksum) */
__asm__(
    ".section .text.ls_crypt, \"ax\", %progbits\n"
    ".arm\n"
    ".align 2\n"
    /* ls_crypt(r0 data, r1 size, r2 seed): two halfwords per word when data is 4-aligned */
    ".global ls_crypt\n"
    ".type ls_crypt, %function\n"
    "ls_crypt:\n"
    "    movs r1, r1, lsr #1\n"          /* halfwords */
    "    bxeq lr\n"
    "    push {r4, r5}\n"
    "    ldr r3, =0x41C64E6D\n"
    "    ldr r12, =0x6073\n"
    "    tst r0, #2\n"
    "    bne 3f\n"
    "1:  cmp r1, #2\n"
    "    blo 3f\n"
    "    mla r2, r3, r2, r12\n"
    "    mov r4, r2, lsr #16\n"
    "    mla r2, r3, r2, r12\n"
    "    mov r5, r2, lsr #16\n"
    "    orr r4, r4, r5, lsl #16\n"
    "    ldr r5, [r0]\n"
    "    eor r5, r5, r4\n"
    "    str r5, [r0], #4\n"
    "    mov r5, r5, lsr #16\n"          /* the last halfword written */
    "    sub r1, r1, #2\n"
    "    b 1b\n"
    "3:  cmp r1, #0\n"                   /* the rest (or all of it, unaligned) one halfword at a time */
    "    beq 4f\n"
    "    mla r2, r3, r2, r12\n"
    "    ldrh r5, [r0]\n"
    "    eor r5, r5, r2, lsr #16\n"
    "    strh r5, [r0], #2\n"
    "    sub r1, r1, #1\n"
    "    b 3b\n"
    "4:  mov r0, r5, lsl #16\n"          /* the last halfword written, as the original */
    "    mov r0, r0, lsr #16\n"
    "    pop {r4, r5}\n"
    "    bx lr\n"
    ".ltorg\n"
    ".size ls_crypt, . - ls_crypt\n"
    /* ls_sum16(r0 data, r1 size): u16 sum of the halfwords */
    ".global ls_sum16\n"
    ".type ls_sum16, %function\n"
    "ls_sum16:\n"
    "    mov r2, #0\n"
    "    movs r1, r1, lsr #1\n"
    "    beq 4f\n"
    "    tst r0, #2\n"
    "    bne 3f\n"
    "1:  cmp r1, #2\n"
    "    blo 3f\n"
    "    ldr r3, [r0], #4\n"
    "    add r2, r2, r3, lsr #16\n"
    "    mov r3, r3, lsl #16\n"
    "    add r2, r2, r3, lsr #16\n"
    "    sub r1, r1, #2\n"
    "    b 1b\n"
    "3:  cmp r1, #0\n"
    "    beq 4f\n"
    "    ldrh r3, [r0], #2\n"
    "    add r2, r2, r3\n"
    "    sub r1, r1, #1\n"
    "    b 3b\n"
    "4:  mov r0, r2, lsl #16\n"
    "    mov r0, r0, lsr #16\n"
    "    bx lr\n"
    ".size ls_sum16, . - ls_sum16\n"
    /* ls_sum8(r0 data, r1 size): sum of the bytes */
    ".global ls_sum8\n"
    ".type ls_sum8, %function\n"
    "ls_sum8:\n"
    "    mov r2, #0\n"
    "    tst r0, #3\n"
    "    bne 3f\n"
    "1:  cmp r1, #4\n"
    "    blo 3f\n"
    "    ldr r3, [r0], #4\n"
    "    and r12, r3, #0xFF\n"
    "    add r2, r2, r12\n"
    "    and r12, r3, #0xFF00\n"
    "    add r2, r2, r12, lsr #8\n"
    "    and r12, r3, #0xFF0000\n"
    "    add r2, r2, r12, lsr #16\n"
    "    add r2, r2, r3, lsr #24\n"
    "    sub r1, r1, #4\n"
    "    b 1b\n"
    "3:  cmp r1, #0\n"
    "    beq 4f\n"
    "    ldrb r3, [r0], #1\n"
    "    add r2, r2, r3\n"
    "    sub r1, r1, #1\n"
    "    b 3b\n"
    "4:  mov r0, r2\n"
    "    bx lr\n"
    ".size ls_sum8, . - ls_sum8\n"
    ".thumb\n"
    ".text\n");
