/* ReRedux menuspeed: faster menus (menuspeed.py lists the sites; measurements in the README, "ReRedux: menus").
 *
 * Under the speed-ups flag 0x5DA (set = OFF), read every frame:
 *  - task menus (APP_TASKMENU, arm9: the party's / Bag's / Box's item menus, many yes/no's): a choice is taken
 *    after one short blink (4 frames: 2 lit, 2 flashed) instead of 16 frames of blinking;
 *  - the X menu: no wait for the close button's press animation, slides in / out in 3 updates instead of 4, a
 *    chosen item goes to the app in the same update (qol2_rtp.h's blink skip now jumps to state 8's code);
 *  - the field events that call an app from the X menu (EventFieldMenu, EventFieldAppCall, ov12) run their
 *    next state in the same update when a state only moved on (B2's own events return 0x21 for that), and the
 *    field's fade-out / fade-in around an app take 2 frames instead of 4;
 *  - per app, the waits that only let an animation finish (menuspeed_rtp.h), never while a cry plays.
 * No sound is cut: the sounds of a menu keep playing across these (tests/menuspeed: audio check vs Redux 1.4.1). */
#include "qol.h"
#include "speed.h"

void *GSYS_GetGameData(void *gsys);
void *GameData_GetEventWork(void *gd);
int EventWork_FlagGet(void *ew, u32 flag);
void GFL_FadeSet(u32 mode, u32 from, u32 to, s32 wait);
int ms_EvMenu(void *ev, u32 *seq, void *work);
int ms_EvAppCall(void *ev, u32 *seq, void *work);
int ms_VoicePlayingAny(void);

#define FLAG_SPEED_OFF  0x5DA

typedef struct {
    u8 override;        /* 0: flag 0x5DA decides (speed_dbg.override too); 1 force off; 2 force on */
    u8 on;
    u8 groups;          /* bit g toggles whenever runtime group g is switched */
    u8 voice;           /* a cry was playing this frame */
    u32 writes;         /* runtime patch entries written */
    u16 tm_short;       /* task-menu choices taken after the short blink */
    u16 chained;        /* event states run in the same update as the previous one */
    u16 fades;          /* field fades around an app at 2 frames */
    u16 ovl;            /* overlay loads seen */
    u16 repeat;         /* key-repeat defaults switched to 4 / 12 */
    u16 box2x;          /* Box animation steps run twice */
    u16 se_moved;       /* SEs played on another SE player instead of stopping the one playing */
    u16 pad;
} MsDbg;

MsDbg ms_dbg;
u8 ms_on = 1;

static int flag(u32 f)
{
    void *gsys = QOL_GSYS;
    void *gd;
    if (!gsys || !(gd = GSYS_GetGameData(gsys)))
        return 0;
    return EventWork_FlagGet(GameData_GetEventWork(gd), f);
}

/* --- runtime byte patches (menuspeed_rtp.h): as speed.c's qol_rtp_apply, every entry checked ------------ */
#define MS_GROUPS
#include "menuspeed_rtp.h"
#undef MS_GROUPS
static const Rtp mrtp[] = {
#include "menuspeed_rtp.h"
};
#define MRTP_COUNT (sizeof(mrtp) / sizeof(mrtp[0]))

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

static int apply(u32 g, u32 want)
{
    u32 i, todo = 0;
    for (i = 0; i < MRTP_COUNT; i++) {
        const Rtp *p = &mrtp[i];
        const u8 *cur = (const u8 *)p->addr;
        if (p->group != g || same(cur, want ? p->fast : p->van, p->len))
            continue;
        if (!same(cur, want ? p->van : p->fast, p->len))
            return 0;                   /* not loaded (another overlay there) */
        todo++;
    }
    if (!todo)
        return 0;
    for (i = 0; i < MRTP_COUNT; i++) {
        const Rtp *p = &mrtp[i];
        u8 *cur = (u8 *)p->addr;
        const u8 *src = want ? p->fast : p->van;
        u32 k;
        if (p->group != g || same(cur, src, p->len))
            continue;
        for (k = 0; k < p->len; k++)
            cur[k] = src[k];
        DC_FlushRange(cur, p->len);
        IC_InvalidateRange(cur, p->len);
        ms_dbg.writes++;
    }
    ms_dbg.groups ^= 1u << g;
    return 1;
}

static void update(void)
{
    MsDbg *d = &ms_dbg;
    u32 ov = d->override ? d->override : speed_dbg.override;
    u32 on = ov ? ov == 2 : !flag(FLAG_SPEED_OFF);
    u32 g;
    ms_on = d->on = on;
    d->voice = ms_VoicePlayingAny() != 0;
    for (g = 0; g < M_COUNT; g++)
        apply(g, g == M_OV207 ? on && !d->voice : on);
}

/* Held-key repeat (GFL UI key work, *(*0x02141884): +0x40 frames between repeats, +0x44 frames before the first):
 * B2's default 8 / 15 becomes 4 / 12 with the speed-ups on. Screens that set their own (the Bag 3 / 6, the Box 6 / 6)
 * keep theirs; anything else back to B2's default when the speed-ups are off. */
#define UI_SYS          (*(u8 **)0x02141884)
#define REP_VAN_SPEED   8
#define REP_VAN_WAIT    15
#define REP_SPEED       4
#define REP_WAIT        12

static void key_repeat(u32 on)
{
    u8 *ui = UI_SYS;
    u32 *k = ui ? *(u32 **)ui : 0;
    if ((u32)k < 0x02000000 || (u32)k >= 0x02400000)
        return;
    if (on && k[0x40 / 4] == REP_VAN_SPEED && k[0x44 / 4] == REP_VAN_WAIT) {
        k[0x40 / 4] = REP_SPEED;
        k[0x44 / 4] = REP_WAIT;
        ms_dbg.repeat++;
    } else if (!on && k[0x40 / 4] == REP_SPEED && k[0x44 / 4] == REP_WAIT) {
        k[0x40 / 4] = REP_VAN_SPEED;
        k[0x44 / 4] = REP_VAN_WAIT;
    }
}

void ms_frame(void)
{
    update();
    key_repeat(ms_on);
}

/* qol2.c's GFL_OvlLoad hook calls this right after an overlay load (weak there) */
void menuspeed_ovl_loaded(void)
{
    ms_dbg.ovl++;
    update();
}

/* --- task menus (arm9 APP_TASKMENU) ---------------------------------------------------------------------
 * FUN_0202DB70 (update) blinks a chosen item: lit / flashed every 4 / mode frames (`movs r0, #4; blx div`);
 * FUN_0202DBE4 (IsFinish) says done after 16 / mode frames (`movs r0, #16; blx div`). mode (work +0x14) is 1
 * (2 for the touch variant). -> 2 / mode and 4 / mode: one blink. */
static u32 div(u32 n, u32 d)
{
    u32 q = 0;
    if (!d)
        return n;
    while (n >= d) {
        n -= d;
        q++;
    }
    return q;
}

u32 ms_tm_period(u32 n, u32 mode)
{
    return div(ms_on ? n >> 1 : n, mode);
}

u32 ms_tm_total(u32 n, u32 mode)
{
    if (ms_on) {
        n >>= 2;
        ms_dbg.tm_short++;
    }
    return div(n, mode);
}

/* --- field events of the X menu: chained states ----------------------------------------------------------
 * GameSystem's event loop (FUN_02016D74) runs the current event again at once when its callback returns
 * neither 0 nor 1 (and resumes a finished event's parent in the same update). These wrappers return 2 when a
 * state only moved on (to the next state, or a child event it just started), so the next one runs now
 * instead of one 30 Hz update (2 frames) later. */
static int chain(int r, u32 s0, u32 s1, u32 ok)
{
    if (r == 0 && ms_on && s1 != s0 && s0 < 32 && (ok >> s0 & 1)) {
        ms_dbg.chained++;
        return 2;
    }
    return r;
}

/* EventFieldMenu (ov12 0x0215A874; work +0x14 = state): 1 menu result -> 2 chosen / 3 closed, 2 -> 5 (app
 * id), 5 -> 6 (EventFieldAppCall started), 6 (back from it) -> 1 / 3 / 4 / 7 / 9 */
int ms_ev_menu(void *ev, u32 *seq, void *work)
{
    u32 *st = (u32 *)((u8 *)work + 0x14);
    u32 s0 = *st;
    int r = ms_EvMenu(ev, seq, work);
    return chain(r, s0, *st, 1u << 1 | 1u << 2 | 1u << 5 | 1u << 6);
}

/* EventFieldAppCall (ov12 0x0215B50C; *seq = state): 0 -> 1 -> 6 (fade-out started) -> 7 (field close started)
 * -> 11 (app proc) -> 12 (wait for it) -> 13 -> 8 (field open started) -> 9 -> 10 (fade-in started) -> 1 -> 2 */
int ms_ev_appcall(void *ev, u32 *seq, void *work)
{
    u32 s0 = *seq;
    int r = ms_EvAppCall(ev, seq, work);
    return chain(r, s0, *seq, 1u << 0 | 1u << 1 | 1u << 6 | 1u << 7 | 1u << 8 | 1u << 9 | 1u << 10 | 1u << 12 |
                 1u << 13);
}

/* --- the field's fade-out / fade-in around an app ----------------------------------------------------------
 * ov36's fade events (FUN_021B8CD8 out, its fade-in twin) call GFL_FadeSet(3, 0 / 16, 16 / 0, -1): 4 frames.
 * When the event's parent is EventFieldAppCall, wait -3: 2 frames (still a fade). Every other field fade is
 * unchanged. */
static int in_appcall(void)
{
    u8 *gsys = QOL_GSYS;
    u8 *ev = gsys ? *(u8 **)(gsys + 0x18) : 0;
    u8 *parent = ev ? *(u8 **)ev : 0;
    if (!parent)
        return 0;
    return *(u32 *)(parent + 4) == ((u32)ms_ev_appcall | 1) || *(u32 *)(parent + 4) == ((u32)ms_EvAppCall | 1);
}

void ms_fieldfade(u32 mode, u32 from, u32 to, s32 wait)
{
    if (ms_on && wait == -1 && in_appcall()) {
        wait = -3;
        ms_dbg.fades++;
    }
    GFL_FadeSet(mode, from, to, wait);
}

/* --- sound effects: never cut by a quicker menu ---------------------------------------------------------------
 * Every SDAT SE player holds one sequence (B2: players 1, 2, 3, 5 share channels 12-15), and the menus' SEs (cursor,
 * decide, cancel, page, ...) all use player 1: a new SE stops the one still playing there. With the menus quicker,
 * the next input (and its SE) can come while the previous SE still plays, sooner than vanilla allowed. So, with the
 * speed-ups on, an SE for player 1 while player 1 still plays goes to the first idle one of players 2, 3, 5 instead
 * (both play to their end); with none idle, as vanilla. GFL_SndSEPlay / SEPlayEx (literals 0x0200625C / 0x02006264)
 * -> here; GFL_SndSEPlayCore (0x02006214) does the rest as before. Stopping "all SEs" and "is any SE playing" cover
 * every player, so nothing waits for or stops a moved SE differently. */
int ms_SeqPlayerIndex(u32 se);
int ms_PlayerActive(u32 idx);
void ms_SEPlayCore(u32 se, u32 vol);
void ms_SEPlayOnPlayer(u32 se, u32 idx);
void ms_SEPlayerVolume(u32 idx, u32 vol);

static const u8 se_alt[] = { 1, 2, 4 };     /* GFL player indices (SDAT player - 1) */

void ms_se_play(u32 se, u32 vol)
{
    if (ms_on && se >= 0x546 && se < 0x96F && ms_SeqPlayerIndex(se) == 0 && ms_PlayerActive(0)) {
        u32 i;
        for (i = 0; i < sizeof(se_alt); i++) {
            if (!ms_PlayerActive(se_alt[i])) {
                ms_SEPlayOnPlayer(se, se_alt[i]);
                if (vol < 0x80)
                    ms_SEPlayerVolume(se_alt[i], vol);
                ms_dbg.se_moved++;
                return;
            }
        }
    }
    ms_SEPlayCore(se, vol);
}

/* --- Box (ov255): its animation step (`blx r1; cmp r0, #0` at 0x021C2B04, r0 = arg, r1 = step) runs twice per frame
 * for the menu slide-in (0x021C0B45) and the tray scroll (0x021C054D) -- their SEs still end on their own -- and for
 * any other step only while no SE plays and no cry: the deposit / withdraw steps are followed by SEs that would
 * otherwise come sooner and cut the one before. -> its result, with the flags of `cmp r0, #0`. */
typedef int (*box_step)(void *arg);
int ms_SndActiveAny(void);

int ms_boxstep_c(void *arg, box_step fn)
{
    int r = fn(arg);
    if (r && ms_on && ((u32)fn == 0x021C0B45 || (u32)fn == 0x021C054D ||
                       (!ms_SndActiveAny() && !ms_VoicePlayingAny()))) {
        r = fn(arg);
        ms_dbg.box2x++;
    }
    return r;
}

__attribute__((naked)) void ms_boxstep(void)
{
    __asm__ volatile(
        ".syntax unified\n"
        "push {r4, lr}\n"
        "bl ms_boxstep_c\n"
        "cmp r0, #0\n"
        "pop {r4, pc}\n"
        ".syntax divided\n");
}

/* --- battle: the press flash of every bottom-screen button (ov168 FUN_021EF1B0: PalFadeReq 0 -> 8 -> 0, wait 0) and
 * the battle Bag's / party's fade-in (ov286 / ov287) -> wait -2 (4 steps per frame): the same flash, twice as fast.
 * PalFadeReq (0x02026FE4) takes stack arguments: lr and sp stay as they are, r12 is scratch. */
__attribute__((naked)) void ms_palfade(void)
{
    __asm__ volatile(
        ".syntax unified\n"
        "push {r0}\n"
        "ldr r0, =ms_on\n"
        "ldrb r0, [r0]\n"
        "cmp r0, #0\n"
        "beq 1f\n"
        "movs r3, #1\n"
        "mvns r3, r3\n"
        "1:\n"
        "ldr r0, =0x02026FE5\n"
        "mov ip, r0\n"
        "pop {r0}\n"
        "bx ip\n"
        ".ltorg\n"
        ".syntax divided\n");
}

/* --- list menus (arm9 BmpMenuList, bmp_menulist.c) ---------------------------------------------------------
 * The cursor shows and input is taken after the list header's "wait" (+0x30; halved in 30 Hz mode): 20 frames for
 * the field's script lists (Buy / Sell, the PC's lists, ...). BmpMenuList_Create 0x02025756
 * `ldr r1, [r4, #0x30]; cmp r1, #0` -> bl here: at most 4 (2 field updates). r4 = the list; r0, r2, r3 are free;
 * the caller branches on the flags of `cmp r1, #0`. */
__attribute__((naked)) void ms_mlwait(void)
{
    __asm__ volatile(
        ".syntax unified\n"
        "ldr r1, [r4, #0x30]\n"
        "ldr r2, =ms_on\n"
        "ldrb r2, [r2]\n"
        "cmp r2, #0\n"
        "beq 1f\n"
        "cmp r1, #4\n"
        "bls 1f\n"
        "movs r1, #4\n"
        "1:\n"
        "cmp r1, #0\n"
        "bx lr\n"
        ".ltorg\n"
        ".syntax divided\n");
}
