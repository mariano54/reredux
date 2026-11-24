/* ReRedux fast save: the menu save (start menu -> Save) in less time (fastsave.py lists the sites).
 *
 * Gating: everything rides on the speed-ups flag 0x5DA (set = OFF, read by speed.c into speed_on),
 * except quick save (flag 0x5DD, opt-in: no question and no yes/no).
 *
 * How B2 saves (GFL backup engine, arm9 0x0203B9BC; EventSave state 9 calls one step per update):
 *  1. compare: every block of flash copy [sd+0] is read back (256-byte card reads, 2 KB per step) and
 *     compared with RAM to find the blocks that changed: ~150 KB, ~50-80 frames in DeSmuME;
 *  2. each changed block (data + u16 counter + u16 CRC16) is written whole to one copy, then the CRC
 *     table, the header (save counter) and the commit byte; then the same to the other copy. Card
 *     writes are verified (read back) by the SDK; a 256-byte page takes ~1-2 frames.
 * What this module changes (B2's write order, both copies, CRCs, counters and the verify stay):
 *  - known contents: per block (data, for the compare) and per 256-byte page of both copies (data +
 *    footer, for the writes), as two 32-bit hashes. Known = read whole at load (the loader reads both
 *    copies), compared equal with the card, or written by a save that completed both copies (and RAM
 *    still hashes the same). Forgotten: a block or page written by anything else (format, link saves,
 *    other writers: every card write is checked, fs_guard), a save that fails or is cancelled, and
 *    everything when copy [sd+0]'s CRC table / header / commit byte isn't what the last save wrote
 *    (read back at every save start: an emulator savestate loaded without its save file, ...).
 *  - compare (state 1): a known block whose RAM hash matches is unchanged without reading the card; a
 *    known block that hashes differently is changed (B2 would find that too); unknown blocks are
 *    compared with the card as before.
 *  - writes (state 3/4): a changed block's pages that the target copy already holds are left out;
 *    the rest go as one card write per run of pages, ascending (the last page, with the counter and
 *    CRC, always goes). The bytes in flash end up exactly as with the whole-block write.
 *  - the save step runs for ~0.5 frame per update (~2 frames while comparing with the card);
 *  - the save messages print at once; the yes/no's choice doesn't blink; the progress dots fill as
 *    soon as the write is done; no wait for the save jingle (it keeps playing); "X saved the game."
 *    stays 15 updates (0.5 s; A/B still close it);
 *  - quick save (0x5DD): no question, no yes/no.
 * Not gated (a fix, not a speed-up): New Game over another game's save. B2 refuses that game's saves
 * ("There is already a saved game file. It is impossible to save.") until the card is erased at the
 * title; here the first save asks to overwrite the old save instead (fs_ow_check). */
#include "qol.h"
#include "qol_texts.h"
#include "speed.h"

/* B2 (fastsave.py SYMS) */
int fs_CardRead(u32 src, void *dst, u32 len, void *cb);
u32 fs_CardWrite(u32 dst, const void *src, u32 len, void *cb);
int fs_CardWriteDone(u32 lock, u32 *ok, void *cb);
int fs_CompareBlock(void *sd, u32 idx, u32 which, u32 *remain, u32 *budget, u32 *offs, u32 *yield);
u32 fs_WriteBlock(void *sd, u32 idx, u32 status, u32 pass);
int fs_EngineStep(void *sd, u32 *out);
int fs_SaveAsyncMain(void *gd);
int fs_GetMsgSpeed(void);
int fs_SEIsPlaying(u32 se);
int fs_PanelDone(void *fsub);
void fs_GaugeAllDots(void *panel);
void fs_PrintMsg(void *work, u32 msg);
int fs_MsgWait(void *work);
void fs_SaveYesNoCreate(void *work);
int fs_SaveYesNoPoll(void *work);
int fs_SaveIsOverwrite(void *sc);
void *GSYS_GetGameData(void *gsys);
void *GameData_GetEventWork(void *gd);
int EventWork_FlagGet(void *ew, u32 flag);

extern u8 speed_on __attribute__((weak));       /* speed.c: speed-ups on (flag 0x5DA clear) */
#define ON              (&speed_on ? speed_on : 1)
#define FLAG_QUICKSAVE  0x5DD

#define TICK            REG16(0x04000100)              /* TM0: the OS tick, 33.5 MHz / 64 (523 656 Hz) */
#define STEP_TICKS      4400                            /* ~0.5 frame of save steps per update ... */
#define CMP_TICKS       17000                           /* ... ~2 frames while comparing with the card */

#define NBLK            96
#define PAGE            256
#define NPG             640                             /* pages per copy (0x26000 / 256 = 608) */
#define NSEG            24
#define FOOT_MAX        0xC0
#define BIT(a, i)       ((a)[(i) >> 5] & 1u << ((i) & 31))
#define SET(a, i)       ((a)[(i) >> 5] |= 1u << ((i) & 31))
#define CLR(a, i)       ((a)[(i) >> 5] &= ~(1u << ((i) & 31)))

typedef struct {
    u32 magic;          /* "FSV1" */
    u16 step_ticks;     /* save steps per update: for up to this many TM0 ticks (tests may change it) */
    u16 cmp_ticks;      /* the same while the engine compares with the card (state 1) */
    u16 pad0;
    u8 tracked;         /* inside EventSave's engine step (AECC) */
    u8 in_write;        /* inside a tracked block write: its flash write is expected */
    /* counters (tests) */
    u32 skipped;        /* blocks found unchanged without reading the card */
    u32 changed;        /* blocks found changed without reading the card */
    u32 compared;       /* blocks compared with the card (vanilla) */
    u32 verified;       /* ... of which equal and stable: now known */
    u32 promoted;       /* written blocks known after a complete save */
    u32 dropped;        /* written blocks not promoted (RAM changed during the save) */
    u32 guard;          /* blocks dropped by an untracked flash write */
    u32 resets;         /* table resets (new SaveData / copy, speed-ups off) */
    u32 saves;          /* tracked saves completed */
    u32 steps;          /* engine step calls by fs_savestep */
    u32 updates;        /* fs_savestep calls (updates) */
    u32 max_ticks;      /* longest fs_savestep (TM0 ticks) */
    u32 seeded;         /* loads that made every block known */
    u32 stale;          /* saves that found copy [sd+0]'s footer changed (emulator savestate, ...) */
    u32 pg_written;     /* pages written by block writes */
    u32 pg_skipped;     /* pages of written blocks left out (known equal in that copy) */
    u32 segs;           /* card writes started for blocks */
    /* the table */
    u8 noq;             /* quick save: the question was not printed */
    u8 qs;              /* quick save: the yes/no was not created */
    u16 pad;
    void *sd;           /* SaveData the table describes ... */
    u32 base;           /* ... and its flash copy [sd+0] */
    u32 base1;          /* its copy [sd+4] */
    s32 cmp_idx;        /* block whose full compare started with hash c1/c2 */
    u32 c1, c2;
    u32 foot_len;       /* CRC table + header + commit byte at the end of copy [sd+0]: ... */
    u8 foot[FOOT_MAX];  /* ... as known (read at load, written by the last complete save) */
    u32 valid[NBLK / 32], pend[NBLK / 32];
    u32 h1[NBLK], h2[NBLK], p1[NBLK], p2[NBLK];
    /* pages (256 bytes, each in one block: data + counter/CRC) of both copies, known like blocks */
    u32 kv[2][NPG / 32], pv[2][NPG / 32];
    u32 k1[2][NPG], k2[2][NPG], q1[2][NPG], q2[2][NPG];
    /* the block write in progress, as card writes of its changed pages */
    u32 seg_n, seg_i;
    void *seg_cb;
    u32 seg_dst[NSEG], seg_src[NSEG], seg_len[NSEG];
    /* New Game over another game's save (fs_ow_check) */
    u8 ow;              /* the overwrite question is up / was answered YES */
    u8 pad2[3];
    u32 ow_asked, ow_yes, ow_no;
} FsDbg;

FsDbg fs_dbg = {0x31565346, STEP_TICKS, CMP_TICKS};
#define T fs_dbg

static int flag(u32 f)
{
    void *gsys = QOL_GSYS;
    void *gd;
    if (!gsys || !(gd = GSYS_GetGameData(gsys)))
        return 0;
    return EventWork_FlagGet(GameData_GetEventWork(gd), f);
}

/* --- the block table of a SaveData --------------------------------------------------------------- */
#define SD32(sd, o)     (*(u32 *)((u8 *)(sd) + (o)))

static u32 nblocks(void *sd)
{
    u32 n = *(u32 *)(SD32(sd, 0x2C) + 4);
    return n <= NBLK ? n : 0;
}

static u32 *blk(void *sd, u32 i)        /* -> {id, size, offset} */
{
    return (u32 *)(*(u32 *)(SD32(sd, 0x2C) + 0x14) + 12 * i);
}

static void words(const u32 *p, u32 n, u32 a, u32 c, u32 *o1, u32 *o2)
{
    while (n--) {
        u32 w = *p++;
        a = (a ^ w) * 0x01000193u;
        c = c + w;
        c = (c << 13 | c >> 19) * 0x9E3779B1u;
    }
    *o1 = a;
    *o2 = c;
}

/* two independent 32-bit hashes of a block's data (sizes and offsets are multiples of 4); each step is
 * a bijection of the word, so a single changed word always changes both */
static void hash(void *sd, u32 i, u32 *o1, u32 *o2)
{
    u32 *b = blk(sd, i);
    words((const u32 *)(SD32(sd, 0x34) + b[2]), b[1] >> 2, 0x811C9DC5u ^ b[1], 0x2545F491u + i, o1, o2);
}

/* page pg of a copy image at img (save buffer or the loader's copy), up to its block's end (copy offset) */
static void phash(const u8 *img, u32 pg, u32 end, u32 *o1, u32 *o2)
{
    u32 a = pg * PAGE, e = a + PAGE < end ? a + PAGE : end;
    words((const u32 *)(img + a), (e - a) >> 2, 0x811C9DC5u ^ pg, 0x2545F491u + e - a, o1, o2);
}

/* every page of every block of copy c: known as in img */
static void pages_seed(void *sd, u32 c, const u8 *img)
{
    u32 i, n = nblocks(sd), pg;
    for (i = 0; i < n; i++) {
        u32 *b = blk(sd, i), end = b[2] + b[1] + 4;
        for (pg = b[2] / PAGE; pg * PAGE < end && pg < NPG; pg++) {
            phash(img, pg, end, &T.k1[c][pg], &T.k2[c][pg]);
            SET(T.kv[c], pg);
            CLR(T.pv[c], pg);
        }
    }
}

/* flash [a, a+len) of copy c changes: its pages are unknown */
static void pages_drop(u32 c, u32 a, u32 len)
{
    u32 pg;
    for (pg = a / PAGE; pg * PAGE < a + len && pg < NPG; pg++) {
        CLR(T.kv[c], pg);
        CLR(T.pv[c], pg);
    }
}

static void reset(void *sd)
{
    u32 k;
    for (k = 0; k < NBLK / 32; k++)
        T.valid[k] = T.pend[k] = 0;
    for (k = 0; k < NPG / 32; k++)
        T.kv[0][k] = T.kv[1][k] = T.pv[0][k] = T.pv[1][k] = 0;
    T.seg_n = 0;
    T.sd = sd;
    T.base = sd ? SD32(sd, 0) : 0;
    T.base1 = sd ? SD32(sd, 4) : 0;
    T.cmp_idx = -1;
    T.foot_len = 0;
    T.resets++;
}

/* the end of copy [sd+0] (CRC table, header with the save counter, commit byte) in RAM */
static u8 *foot_ram(void *sd, u32 *len)
{
    u32 n = 0x10 + SD32(sd, 0x140);
    *len = n <= FOOT_MAX ? n : 0;
    return (u8 *)SD32(sd, 0x34) + SD32(sd, 0x30) - n;
}

static void foot_keep(void *sd)
{
    u32 n, i;
    const u8 *p = foot_ram(sd, &n);
    for (i = 0; i < n; i++)
        T.foot[i] = p[i];
    T.foot_len = n;
}

/* a save starts: is copy [sd+0] still what the table knows? Its last bytes change with every save
 * (save counter, every block's CRC); if flash changed behind our back (an emulator savestate loaded
 * without its save file, ...), forget everything: this save compares with the card. */
static u8 foot_buf[FOOT_MAX];

static void foot_check(void *sd)
{
    u32 n = T.foot_len, i;
    if (T.sd != sd || !n)
        return;
    if (fs_CardRead(SD32(sd, 0) + SD32(sd, 0x30) - n, foot_buf, n, 0))
        for (i = 0; i < n && foot_buf[i] == T.foot[i]; i++)
            ;
    else
        i = 0;
    if (i != n) {
        reset(sd);
        T.stale++;
    }
}

/* the table is about this SaveData's copy [sd+0]; anything else starts a new one */
static int adopt(void *sd)
{
    if (!nblocks(sd))
        return 0;
    if (T.sd != sd || T.base != SD32(sd, 0) || T.base1 != SD32(sd, 4))
        reset(sd);
    return 1;
}

/* --- arm9 0x0203B1AE (the two-copy load, FUN_0203B170): `bl FUN_0203BFF8` reads copy [sd+0] whole into
 * the save buffer -> right after it, RAM = that copy, block by block: they are all known. (The loader
 * may then take some blocks from the other copy; those hash differently and get written, as B2's
 * compare would decide.) Only the main data's load (B170's 3rd argument 0, not FUN_0203B018's 1). */
int fs_load_read(u32 src, void *dst, u32 len, void *cb, void *sd, u32 kind)
{
    u32 i, n;
    int r = fs_CardRead(src, dst, len, cb);
    if (kind != 0 || (n = nblocks(sd)) == 0 || len != SD32(sd, 0x30) || SD32(sd, 0) == SD32(sd, 4))
        return r;
    if (!r) {                               /* a failed read: know nothing */
        if (T.sd == sd)
            reset(sd);
        return r;
    }
    if (src == SD32(sd, 0) && dst == (void *)SD32(sd, 0x34)) {     /* copy [sd+0] -> the save buffer */
        reset(sd);
        for (i = 0; i < n; i++) {
            hash(sd, i, &T.h1[i], &T.h2[i]);
            SET(T.valid, i);
        }
        pages_seed(sd, 0, dst);
        foot_keep(sd);
        T.seeded++;
    } else if (src == SD32(sd, 4) && T.sd == sd)                    /* copy [sd+4] -> a scratch buffer */
        pages_seed(sd, 1, dst);
    return r;
}

__attribute__((naked)) void fs_load_tramp(void)
{
    __asm__ volatile(
        ".syntax unified\n"
        "push {r4, r5, r6, lr}\n"
        "ldr r6, [sp, #0x38]\n"         /* FUN_0203B170's [sp, #0x28]: its 3rd argument */
        "sub sp, #8\n"
        "str r5, [sp]\n"                /* r5 = sd in FUN_0203B170 */
        "str r6, [sp, #4]\n"
        "bl fs_load_read\n"
        "add sp, #8\n"
        "pop {r4, r5, r6, pc}\n"
        ".syntax divided\n");
}

/* --- arm9 0x0203BA4A (engine state 1): `bl FUN_0203B81C` = compare block idx with the card --------- *
 * -> 1 changed, 2 same, 0 not finished (card budget used up; resumed next call with *remain != 0) */
int fs_cmp(void *sd, u32 idx, u32 which, u32 *remain, u32 *budget, u32 *offs, u32 *yield)
{
    u32 a, c;
    int r;
    if (!T.tracked || !ON || !adopt(sd) || idx >= nblocks(sd))
        return fs_CompareBlock(sd, idx, which, remain, budget, offs, yield);
    if (*remain == 0) {                     /* a block starts */
        hash(sd, idx, &a, &c);
        if (BIT(T.valid, idx)) {
            if (a == T.h1[idx] && c == T.h2[idx]) {
                T.skipped++;
                return 2;
            }
            CLR(T.valid, idx);
            T.changed++;
            return 1;
        }
        T.cmp_idx = idx;
        T.c1 = a;
        T.c2 = c;
        T.compared++;
    }
    r = fs_CompareBlock(sd, idx, which, remain, budget, offs, yield);
    if (r && T.cmp_idx == (s32)idx) {
        T.cmp_idx = -1;
        if (r == 2) {                       /* equal to the card: known if RAM didn't move meanwhile */
            hash(sd, idx, &a, &c);
            if (a == T.c1 && c == T.c2) {
                T.h1[idx] = a;
                T.h2[idx] = c;
                SET(T.valid, idx);
                T.verified++;
            }
        }
    }
    return r;
}

/* --- arm9 0x0203BAC2 (engine state 3): `bl FUN_0203B92C` = CRC + start writing block idx to the copy
 * given by its status (1: [sd+0], 2: [sd+4]) -> the card lock id, as before */
u32 fs_wblock(void *sd, u32 idx, u32 status, u32 pass)
{
    u32 r, a, c;
    u32 base = status == 2 ? SD32(sd, 4) : SD32(sd, 0);
    if (T.sd == sd && base == T.base && idx < NBLK) {
        CLR(T.valid, idx);                  /* its contents in copy [sd+0] are about to change */
        CLR(T.pend, idx);
    }
    if (T.tracked && ON && adopt(sd) && idx < nblocks(sd) && base == T.base) {
        hash(sd, idx, &a, &c);
        T.p1[idx] = a;
        T.p2[idx] = c;
        SET(T.pend, idx);
        T.in_write = 1;
    }
    r = fs_WriteBlock(sd, idx, status, pass);
    T.in_write = 0;
    return r;
}

/* --- arm9 0x0203C07C (entry of the card write used by every GFL backup write) -> fs_write_tramp ------
 * Any flash write except the tracked block write drops the known blocks it overlaps. */
void fs_guard(u32 dst, u32 src, u32 len)
{
    u32 i, n;
    if (T.in_write || !T.sd)
        return;
    if (dst + len > T.base && dst < T.base + 0x26000)
        pages_drop(0, dst > T.base ? dst - T.base : 0, dst + len - (dst > T.base ? dst : T.base));
    if (dst + len > T.base1 && dst < T.base1 + 0x26000)
        pages_drop(1, dst > T.base1 ? dst - T.base1 : 0, dst + len - (dst > T.base1 ? dst : T.base1));
    n = nblocks(T.sd);
    for (i = 0; i < n; i++) {
        u32 *b = blk(T.sd, i);
        u32 a = T.base + b[2], e = a + b[1] + 4;
        if (dst < e && a < dst + len && (BIT(T.valid, i) || BIT(T.pend, i))) {
            CLR(T.valid, i);
            CLR(T.pend, i);
            T.guard++;
        }
    }
}

__attribute__((naked)) void fs_write_tramp(void)
{
    __asm__ volatile(
        ".syntax unified\n"
        "push {r0-r4, lr}\n"
        "ldr r4, =fs_guard\n"
        "blx r4\n"
        "ldr r0, [sp, #20]\n"
        "mov lr, r0\n"
        "pop {r0-r4}\n"
        "add sp, #4\n"
        /* the 12 bytes the jump replaced */
        "push {r4-r7, lr}\n"
        "sub sp, #0x1c\n"
        "adds r5, r0, #0\n"
        "adds r6, r1, #0\n"
        "adds r7, r2, #0\n"
        "str r3, [sp, #0x14]\n"
        "ldr r0, =0x0203C089\n"         /* next: blx OS_GetLockID (no arguments) */
        "bx r0\n"
        ".ltorg\n"
        ".syntax divided\n");
}

/* --- arm9 0x0203B97E (FUN_0203B92C, after the CRC): `bl FUN_0203C07C(dst, src, size + 4, cb)` writes the
 * whole block -> only its pages that differ from what that copy is known to hold (the last page, with
 * the block's counter and CRC, always differs), one card write per run of pages, chained by fs_seg_poll.
 * Unknown pages are written; every page written is known after the save completes. Same bytes end up
 * in flash as with the whole write; the order within the block stays ascending, the verify stays. */
static int seg_plan(u32 dst, u32 src, u32 len)
{
    void *sd = T.sd;
    u32 buf = SD32(sd, 0x34), off = src - buf, c, i, n, pg, end, a1, a2, run = 0;
    u32 *b = 0;
    if (dst - off == T.base)
        c = 0;
    else if (dst - off == T.base1)
        c = 1;
    else
        return 0;
    n = nblocks(sd);
    for (i = 0; i < n; i++)
        if (blk(sd, i)[2] == off) {
            b = blk(sd, i);
            break;
        }
    if (!b || len != b[1] + 4 || off % PAGE)
        return 0;
    end = off + len;
    T.seg_n = 0;
    for (pg = off / PAGE; pg * PAGE < end; pg++) {
        if (pg >= NPG)
            return 0;
        phash((const u8 *)buf, pg, end, &a1, &a2);
        if (BIT(T.kv[c], pg) && a1 == T.k1[c][pg] && a2 == T.k2[c][pg]) {
            run = 0;
            T.pg_skipped++;
            continue;
        }
        CLR(T.kv[c], pg);                   /* written now, known when the save completes */
        SET(T.pv[c], pg);
        T.q1[c][pg] = a1;
        T.q2[c][pg] = a2;
        T.pg_written++;
        if (run) {
            T.seg_len[T.seg_n - 1] += (pg + 1) * PAGE < end ? PAGE : end - pg * PAGE;
            continue;
        }
        if (T.seg_n == NSEG)
            return 0;
        T.seg_dst[T.seg_n] = dst - off + pg * PAGE;
        T.seg_src[T.seg_n] = buf + pg * PAGE;
        T.seg_len[T.seg_n] = (pg + 1) * PAGE < end ? PAGE : end - pg * PAGE;
        T.seg_n++;
        run = 1;
    }
    return T.seg_n != 0;
}

static u32 seg_start(void)
{
    u32 lock;
    u32 i = T.seg_i;
    T.in_write = 1;
    lock = fs_CardWrite(T.seg_dst[i], (const void *)T.seg_src[i], T.seg_len[i], T.seg_cb);
    T.in_write = 0;
    T.segs++;
    return lock;
}

u32 fs_seg_write(u32 dst, const void *src, u32 len, void *cb)
{
    u32 r;
    T.seg_n = 0;
    if (T.tracked && ON && T.sd && seg_plan(dst, (u32)src, len)) {
        T.seg_i = 0;
        T.seg_cb = cb;
        return seg_start();
    }
    T.seg_n = 0;
    if (T.tracked && ON && T.sd) {          /* not planned: the whole block, nothing known about it */
        u32 off = (u32)src - SD32(T.sd, 0x34);
        if (dst - off == T.base)
            pages_drop(0, off, len);
        else if (dst - off == T.base1)
            pages_drop(1, off, len);
        T.in_write = 1;
    }
    r = fs_CardWrite(dst, src, len, cb);
    T.in_write = 0;
    return r;
}

/* --- arm9 0x0203BB08 (engine state 4): `bl FUN_0203C11C(lock, &ok, cb)` = block write done? ---------- *
 * -> while pages of the block remain: start the next run (its lock id where the engine keeps it). */
int fs_seg_poll(u32 lock, u32 *ok, void *cb)
{
    int r = fs_CardWriteDone(lock, ok, cb);
    if (r == 1 && T.seg_n) {
        if (*ok == 1 && T.seg_i + 1 < T.seg_n) {
            T.seg_i++;
            *(u16 *)(*(u8 **)0x0214185C + 0x20C) = seg_start();
            return 0;
        }
        T.seg_n = 0;                        /* done, or failed (the engine sees ok = 0) */
    }
    return r;
}

/* --- arm9 0x0203AEE0 (FUN_0203AECC, SaveControl's async step): `bl FUN_0203B9BC` -------------------- *
 * The menu save and the other async saves of the main data. A complete save (state 11: both copies
 * written and committed) makes its written blocks known, if RAM still hashes the same. */
int fs_engine(void *sd, u32 *out)
{
    int r;
    u32 i, n, a, c;
    u8 st = *((u8 *)sd + 0x18);
    if (st == 0) {                          /* a save starts */
        for (i = 0; i < NBLK / 32; i++)
            T.pend[i] = 0;
        for (i = 0; i < NPG / 32; i++)
            T.pv[0][i] = T.pv[1][i] = 0;
        T.cmp_idx = -1;
        T.seg_n = 0;
        if (!ON && T.sd)
            reset(0);
        else
            foot_check(sd);
    }
    T.tracked = 1;
    r = fs_EngineStep(sd, out);
    T.tracked = 0;
    if (r == 2 && *((u8 *)sd + 0x18) == 11 && T.sd == sd && T.base == SD32(sd, 0)) {
        n = nblocks(sd);
        for (i = 0; i < n; i++)
            if (BIT(T.pend, i)) {
                CLR(T.pend, i);
                hash(sd, i, &a, &c);
                if (a == T.p1[i] && c == T.p2[i]) {
                    T.h1[i] = a;
                    T.h2[i] = c;
                    SET(T.valid, i);
                    T.promoted++;
                } else
                    T.dropped++;
            }
        for (i = 0; i < n; i++) {           /* pages written in either copy */
            u32 *b = blk(sd, i), end = b[2] + b[1] + 4, pg, k;
            for (pg = b[2] / PAGE; pg * PAGE < end && pg < NPG; pg++)
                for (k = 0; k < 2; k++)
                    if (BIT(T.pv[k], pg)) {
                        CLR(T.pv[k], pg);
                        phash((const u8 *)SD32(sd, 0x34), pg, end, &a, &c);
                        if (a == T.q1[k][pg] && c == T.q2[k][pg]) {
                            T.k1[k][pg] = a;
                            T.k2[k][pg] = c;
                            SET(T.kv[k], pg);
                        }
                    }
        }
        foot_keep(sd);
        T.saves++;
    } else if (r == 3) {
        for (i = 0; i < NBLK / 32; i++)
            T.pend[i] = 0;
        for (i = 0; i < NPG / 32; i++)
            T.pv[0][i] = T.pv[1][i] = 0;
    }
    return r;
}

/* --- ov12 0x02163D06 (EventSave state 9): `bl FUN_02017850` = one save step per update -------------- *
 * -> steps until done / error, for up to step_ticks (~0.5 frame: card writes run on the ARM7; polling
 * again soon starts the next one soon) or cmp_ticks (~2 frames) while blocks are compared with the
 * card (such a step reads 2 KB, ~0.8 frame). TM0 runs freely (16 bits, wraps every 125 ms). */
int fs_savestep(void *gd)
{
    u32 t = TICK, dt = 0, u, lim;
    int r;
    T.updates++;
    do {
        r = fs_SaveAsyncMain(gd);
        T.steps++;
        u = TICK;
        dt += (u - t) & 0xFFFF;
        t = u;
        lim = T.sd && *((u8 *)T.sd + 0x18) == 1 ? T.cmp_ticks : T.step_ticks;
    } while (ON && r < 2 && dt < lim);
    if (dt > T.max_ticks)
        T.max_ticks = dt;
    return r;
}

/* --- save texts at once: ov12 0x02163F7E (FUN_02163F50, every EventSave message) `bl FUN_02017BCC` - */
int fs_msg_speed(void)
{
    int s = fs_GetMsgSpeed();
    return ON ? -127 : s;                   /* < 0: -s characters per frame */
}

/* --- ov12 0x02163D56 (state 10): `bl FUN_02198B28` = wait until the 10 progress dots are lit -------- */
int fs_gauge(u8 *fsub)
{
    u8 *panel;
    if (ON && (panel = *(u8 **)(fsub + 0x20)) != 0 && *(u32 *)(panel + 0x110) && *(u16 *)(panel + 0x124) < 10) {
        fs_GaugeAllDots(panel);             /* the write is done: light them all */
        *(u16 *)(panel + 0x124) = 10;
    }
    return fs_PanelDone(fsub);
}

/* --- ov12 0x02163DE6 (state 12): `bl FUN_020062C4(0x558)` = wait for the save jingle ---------------- */
int fs_se_wait(u32 se)
{
    return ON ? 0 : fs_SEIsPlaying(se);
}

/* --- ov12 0x02163E32 (state 16, the "saved" box): `ldr r0, [r1, #0x4c]; cmp r0, #150` -------------- *
 * -> cmp against fs_hold (15 updates = 0.5 s with speed-ups, else 150); A/B still close it at once */
u8 fs_hold = 150;

void fs_frame(void)
{
    fs_hold = ON ? 15 : 150;
}

__attribute__((naked)) void fs_hold_cmp(void)
{
    __asm__ volatile(
        ".syntax unified\n"
        "ldr r0, [r1, #0x4c]\n"
        "ldr r2, =fs_hold\n"
        "ldrb r2, [r2]\n"
        "cmp r0, r2\n"                  /* flags for the following bcc; r2 is dead there */
        "bx lr\n"
        ".ltorg\n"
        ".syntax divided\n");
}

/* --- quick save (flag 0x5DD): no question (state 2 / 3), no yes/no (state 3 / 4) ------------------- */
void fs_question(void *work, u32 msg)
{
    T.ow = 0;                               /* a save starts (state 2) */
    T.noq = flag(FLAG_QUICKSAVE);
    if (!T.noq)
        fs_PrintMsg(work, msg);
}

int fs_question_wait(void *work)
{
    return T.noq && !T.ow ? 0 : fs_MsgWait(work);
}

void fs_qs_create(void *work)
{
    T.qs = flag(FLAG_QUICKSAVE) && !T.ow;   /* the overwrite question always gets its yes/no */
    T.noq = 0;
    if (!T.qs)
        fs_SaveYesNoCreate(work);
}

int fs_qs_poll(void *work)
{
    u8 *yn;
    int r;
    if (T.qs) {
        T.qs = 0;
        return 0;                           /* YES */
    }
    /* answered (the decide SE played): skip the choice's blink (+1 counts it up to 16) */
    if (ON && (yn = *(u8 **)(*(u8 **)((u8 *)work + 0x1C) + 0x40)) != 0 && *(u32 *)(yn + 0xC))
        yn[1] = 0x40;
    r = fs_SaveYesNoPoll(work);
    if (r == 1 && T.ow) {                   /* NO to the overwrite: the old save stays, nothing written */
        T.ow = 0;
        T.ow_no++;
    }
    return r;
}

/* --- New Game over another game's save: ov12 0x02163C44 (EventSave state 4, YES): `bl FUN_0200746C` --
 * FUN_0200746C(SaveControl) = new game (+0, set by the title's New Game, cleared by the first complete
 * save) && a save was loaded from the card at boot (+1) -> B2 prints bank 208 msg 8 "There is already a
 * saved game file. It is impossible to save." and closes: that game can never be saved until the card is
 * erased at the title (Up + SELECT + B). Instead: the first time, ask TXT_FS_OVERWRITE with a yes/no
 * (state 3 -> 4 again); YES -> +1 = 0, i.e. the save runs exactly as the first save of a new game on an
 * empty card (New Game marked every block changed; both copies, CRCs, the footer and the commit are
 * written as always, and fastsave's table follows the card as for any save); NO -> state 0x11 (closes,
 * the old save is untouched). A Continue'd game has +0 = 0 and a new game on an empty card +1 = 0, so
 * neither ever sees the question.
 * -> 0: save (state 5); 2: handled here (the trampoline returns from EventSave_Update) */
int fs_ow_check(void *work, u32 *state)
{
    u8 *sc = *(u8 **)work;
    if (!fs_SaveIsOverwrite(sc)) {
        T.ow = 0;
        return 0;
    }
    if (T.ow) {                             /* YES to the overwrite question */
        T.ow = 0;
        T.ow_yes++;
        sc[1] = 0;
        return 0;
    }
    T.ow = 1;
    T.ow_asked++;
    fs_PrintMsg(work, TXT_FS_OVERWRITE);
    *state = 3;                             /* wait for the text, then the yes/no (state 4) */
    return 2;
}

__attribute__((naked)) void fs_ow_tramp(void)
{
    __asm__ volatile(
        ".syntax unified\n"
        "push {lr}\n"
        "adds r0, r4, #0\n"             /* EventSave work */
        "adds r1, r5, #0\n"             /* &state */
        "bl fs_ow_check\n"
        "pop {r1}\n"
        "cmp r0, #2\n"
        "bne 1f\n"
        "ldr r1, =0x02163E93\n"         /* EventSave_Update's exit: mov r0, #2; pop {r3-r7, pc} */
        "1:\n"
        "bx r1\n"
        ".ltorg\n"
        ".syntax divided\n");
}
