/* ReRedux battleexit: a shorter black screen after a battle (battleexit.py lists the sites; the
 * timeline and measurements are in battleexit.py's docstring).
 *
 * Battle -> field, vanilla (wild win, DeSmuME): battle fade-out 16 f, then the battle waits for its BGM
 * fade-out (30 sound frames) before it tears down; EventBattleCall state 7 asks FieldSnd to pop the field
 * BGM with another 30-frame fade-out of the (already stopped) battle BGM, and state 9 waits for that pop,
 * so the screen stays black ~16 frames after the field is loaded. With the speed-ups on:
 *  - the battle's fade-out takes 8 frames (2 brightness steps per frame); its BGM keeps vanilla's 30-frame
 *    fade-out (10 frames cut the music off);
 *  - the field BGM pop skips its fade-out when no BGM is playing any more (nothing to hear; a BGM still
 *    playing, e.g. the victory music after a catch, keeps vanilla's 30-frame fade), so the pop
 *    happens while the field loads and the fade-in starts as soon as the field is ready;
 *  - EventBattleCall 9 -> 10 -> 11 and EventBGMFadeWait chain their steps in one 30 Hz event tick.
 * Field -> battle: the battle intro's white fade-in (16 steps, 2 frames each) runs at 1 frame per step.
 * Off (vanilla) while event flag 0x5DA is set, as the other speed-ups. */
#include "qol.h"
#include "speed.h"

void *GSYS_GetGameData(void *gsys);
void *GameData_GetEventWork(void *gd);
int EventWork_FlagGet(void *ew, u32 flag);
int bx_SndBGMIsPlaying(void);
void *bx_EventBGMFadePop_Create(void *gsys);
void *bx_GameEvent_GetData(void *ev);
void bx_FadeSet(u32 mode, u32 from, u32 to, s32 wait);
int bx_EventBattleCall_Callback(void *ev, u32 *seq, void *work);
int bx_EventBGMFadeWait_Callback(void *ev, u32 *seq, void *work);

#define FLAG_SPEED_OFF      0x5DA
#define BTL_FADE_STEP       2       /* vanilla 1: 16 frames */
#define INTRO_FADE_WAIT     0       /* vanilla 2 */

typedef struct {
    u8 override;        /* 0: flag 0x5DA decides (speed_dbg.override too); 1 force off; 2 force on */
    u8 on;
    u8 last_playing;    /* GFL_SndBGMIsPlaying() at the last post-battle pop */
    u8 pad;
    u16 fades, bgm_fades, pops, quick_pops, intro_fades, chained;
} BxDbg;

BxDbg bx_dbg;
static u8 bx_on = 1;

static int flag(u32 f)
{
    void *gsys = QOL_GSYS;
    void *gd;
    if (!gsys || !(gd = GSYS_GetGameData(gsys)))
        return 0;
    return EventWork_FlagGet(GameData_GetEventWork(gd), f);
}

void bx_frame(void)
{
    u32 ov = bx_dbg.override ? bx_dbg.override : speed_dbg.override;
    bx_on = bx_dbg.on = ov ? ov == 2 : !flag(FLAG_SPEED_OFF);
}

/* --- battle end (ov167 battle proc exit, 0x02199CD4) ------------------------------------------------- */

/* (state 0's GFL_SndBGMFadeOut(30) stays vanilla) */

/* state 1: the brightness level (wk+0x460, 0 .. -16) one step down per frame */
s32 bx_btl_fade_next(s32 cur)
{
    s32 n = cur - (bx_on ? BTL_FADE_STEP : 1);
    if (bx_on)
        bx_dbg.fades++;
    return n < -16 ? -16 : n;
}

/* 0x02199D66: `subs r0, r2, #1; str r0, [r4, r6]` -> bl here (r2 = level, r4 + r6 = its address; r0 is
 * set again by the next instruction) */
__attribute__((naked)) void bx_btl_fade_step(void)
{
    __asm__ volatile(
        ".syntax unified\n"
        "push {r1, r2, r3, lr}\n"
        "movs r0, r2\n"
        "ldr r3, =bx_btl_fade_next\n"
        "blx r3\n"
        "str r0, [r4, r6]\n"
        "pop {r1, r2, r3, pc}\n"
        ".ltorg\n"
        ".syntax divided\n");
}

/* --- EventBattleCall state 7 (ov12 0x02168D86): the field BGM pop --------------------------------------
 * The battle has faded its BGM out and stopped it; when nothing is playing, the pop's fade-out (30 sound
 * frames of silence, stretched by the field load's lag frames) is dropped. A BGM still playing keeps its
 * vanilla fade-out. */
void *bx_bgm_pop(void *gsys)
{
    void *ev = bx_EventBGMFadePop_Create(gsys);
    u8 *d = bx_GameEvent_GetData(ev);
    bx_dbg.pops++;
    bx_dbg.last_playing = bx_SndBGMIsPlaying();
    if (bx_on && !bx_dbg.last_playing) {
        /* fade-out frames (vanilla 0x1E) of nothing; the fade-in (+0xC) stays */
        *(u16 *)(d + 0xE) = 0;
        bx_dbg.quick_pops++;
    }
    return ev;
}

/* --- event ticks after the field is back -------------------------------------------------------------
 * Field events run at 30 Hz and each state step of EventBattleCall 9 -> 10 -> 11 and of EventBGMFadeWait
 * waits for the next tick (2 frames each). A callback result other than 0 (wait) and 1 (done) makes
 * GameSystem's event loop run the current event again at once, so these steps chain in one tick. */
int bx_battlecall(void *ev, u32 *seq, void *work)
{
    u32 s0 = *seq;
    int r = bx_EventBattleCall_Callback(ev, seq, work);
    if (r == 0 && bx_on && (s0 == 9 || s0 == 10) && *seq == s0 + 1) {
        bx_dbg.chained++;
        return 2;
    }
    return r;
}

int bx_fadewait(void *ev, u32 *seq, void *work)
{
    u32 s0 = *seq;
    int r = bx_EventBGMFadeWait_Callback(ev, seq, work);
    if (r == 0 && bx_on && s0 == 0 && *seq == 1) {
        bx_dbg.chained++;
        return 2;
    }
    return r;
}

/* --- battle intro fade-in (ov167 0x021D12F8: GFL_FadeSet(3 or 12, 16, 0, wait)) ------------------------ */
void bx_intro_fade(u32 mode, u32 from, u32 to, s32 wait)
{
    if (bx_on && wait == 2) {
        wait = INTRO_FADE_WAIT;
        bx_dbg.intro_fades++;
    }
    bx_FadeSet(mode, from, to, wait);
}
