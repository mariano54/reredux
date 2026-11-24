/* ReRedux evomoves, Pokédex side: the species' BASE STATS on the top screen of the entry's INFO page (overlay 298).
 *
 * Vanilla INFO leaves its top screen empty (the page's grid) until a foreign-language entry is chosen: then overlay 296's
 * second info panel shows that entry there (its BG layers 6 and 7 on, the grid layer 4 scrolled to the panel's frame).
 * We put a box in the FORMS / EVO page style on that empty screen: the six base stats of the form the entry shows (the
 * number and a bar coloured by the value), their total, the abilities and the hidden ability, read with the game's own
 * personal-data accessor (a/0/1/6, Redux's values). Species only seen show "???" as INFO does.
 *
 * Layer: sub BG2 (GFL frame 6, the foreign panel's card layer, off while no foreign entry is shown). Our tiles come from
 * frame 6's own char allocator (after the panel's); our map is written straight into BG2's screen in VRAM while we are
 * shown (GFL's copy of the card's map stays in its screen buffer): a foreign entry gets the card's map back from that
 * buffer (GFL_BGSysLoadScr), so its card and text are untouched; so does the entry's exit. Hooks (evomoves.py): INFO's
 * module table (main, exit) -> ds_main / ds_exit. */
#include "qol.h"
#include "qol_texts.h"
#include "evomoves_data.h"
#include "evomoves.h"

/* B2 (evomoves.py SYMS) */
u32 ds_InfoMain(void *module, u32 *state, void *work, void *data, void *ctx);
u32 ds_InfoExit(void *module, u32 *state, void *work, void *data, void *ctx);
s32 em_CharAlloc(u32 frame, u32 size, u32 dir);
void em_CharFree(u32 frame, u32 tile, u32 size);
u32 em_PersonalParam(u32 species, u32 form, u32 param);
void em_DexDraw(void *dex, u32 species, u32 *sex, u32 *rare, u32 *form, u32 heap);
u32 em_HeapMaxAlloc(u32 heap);
u32 dx_CurSpecies(void *ctx);
void em_BgOn(u32 frame, u32 on);
void em_BgLoadChar(u32 frame, const void *data, u32 size, u32 tile);
void *em_BmpNew(u32 w, u32 h, u32 bpt, u32 heap);
void em_BmpFree(void *bmp);
void *em_BmpPixels(void *bmp);
void *em_QueNew(u32 size, u32 heap);
void em_QueFree(void *que);
void em_QueClear(void *que);
void em_QueRun(void *que);
void *em_MsgNew(u32 a, u32 b, u32 bank, u32 heap);
void em_MsgFree(void *msg);
void *em_ArcOpen(u32 arc, u32 heap);
void em_ArcClose(void *h);
void em_PalLoad(void *h, u32 file, u32 engine, u32 src, u32 dst, u32 size, u32 heap);
u32 em_SaveCfg(void *save, u32 idx);
void *em_DexOf(void *save);
u32 em_DexCaught(void *dex, u32 species);

#define DEX_ARC     0x9D        /* a/1/5/7 */
#define SYSTEM_BANK_SUMMARY 179
#define BANK_ABILITIES 374
#define FRAME       6           /* sub BG2 */
#define BGCNT       REG16(0x0400100C)
#define DISPCNT_B   REG32(0x04001000)
#define SCR_VRAM    ((volatile u16 *)(0x06200000 + ((BGCNT >> 8) & 0x1F) * 0x800))     /* BG2's screen (2 KB) */
#define PALROW      14
#define DS_FILE_PAL (DX_PAL_FIRST + 4)  /* evomoves.py dex_palettes: our stats palette */
#define INFO_FONT(d)    (*(void **)((u8 *)(d) + 0x110))
#define INFO_LANG(d)    (*(u32 *)((u8 *)(d) + 0x98))    /* the foreign entry shown (6: none) */
#define WORK_HEAP(w)    (*(u16 *)((u8 *)(w) + 0x00))
#define CTX_SAVE(c)     (*(void **)((u8 *)(c) + 0x00))

/* the bitmap: 30 x 20 tiles at tile (1, 3) of the top screen */
#define CW          30
#define CH          20
#define TX          1
#define TY          3
#define NTILES      (CW * CH + 1)   /* + a blank tile for the rest of the map */

/* colours of DS_FILE_PAL (evomoves.py STATS_PAL) */
#define K_FILL      1
#define K_BORDER    2           /* gold: the border and the labels */
#define K_BORDER2   3
#define K_WHITE     4
#define K_SHADOW    5
#define K_GOLD_SH   6
#define K_LINE      7           /* the separator lines and the bars' track */
#define K_FILL2     8
#define K_GREY      9
#define K_BAR0      10          /* 10-15: bar colours, low to high */
#define C_NORMAL    COL(K_WHITE, K_SHADOW, 0)
#define C_GOLD      COL(K_BORDER, K_GOLD_SH, 0)
#define C_DIM       COL(K_GREY, K_SHADOW, 0)

/* layout (bitmap pixels): rows of 16 from y 5 (title, HP .. Speed, abilities, hidden ability) */
#define BOX_Y       2
#define BOX_H       156
#define ROW(k)      (5 + 16 * (k))
#define LABEL_X     8
#define VAL_R       88
#define BAR_X       96
#define BAR_W       136
#define BAR_FULL    180         /* a stat of 180 or more fills the bar */
#define RIGHT       232
#define AB1_X       62
#define AB2_X       148

typedef struct {
    u32 magic;          /* 'DSTA' */
    u8 on, ready, shown, pending;
    u8 caught, foreign, holds, fail;
    u16 species, form;
    u16 stats[6];       /* HP, Atk, Def, SpA, SpD, Spe (as shown) */
    u16 abil[3];
    u16 total;
    u16 setups, exits, redraws, flushes, shows, hides;
    s16 tile;           /* first allocated tile in frame 6 */
    u16 maps, restores;     /* our map written to VRAM / the card's map put back */
    u32 heap_free;      /* largest allocatable block before our setup */
    u32 heap_after;
} DsDbg;
DsDbg ds_dbg = { 0x41545344 };

static struct {
    u16 heap;
    void *data, *font, *msg, *que, *bmp;
} ds;

/* personal params: base stats in the summary's order (HP, Attack, Defense, Sp. Atk, Sp. Def, Speed) */
static const u8 ds_param[6] = { 0, 1, 2, 4, 5, 3 };
static const u16 ds_label[6] = { TXT_DS_HP, TXT_DS_ATK, TXT_DS_DEF, TXT_DS_SPA, TXT_DS_SPD, TXT_DS_SPE };

static void *ds_fmt(void *ws, u32 id)
{
    void *src = em_MsgLoad(ds.msg, id), *dst;
    if (!ws)
        return src;
    dst = em_StrBufCreate(64, ds.heap);
    em_WsFormat(ws, dst, src);
    em_StrBufFree(src);
    return dst;
}

static void ds_put(void *str, s32 x, s32 y, u32 color, u32 right)
{
    if (right)
        x -= (s32)em_StrWidth(str, ds.font, 0);
    em_PrintQue(ds.que, ds.bmp, x, y, str, ds.font, color);
    em_StrBufFree(str);
}

static void ds_num(void *ws, u32 v, s32 x, s32 y, u32 color)
{
    em_WsNumber(ws, 0, v, 3, 0, 1);
    ds_put(ds_fmt(ws, TXT_EVO_DEX_NUM), x, y, color, 1);
}

static void ds_word(void *ws, u32 abil, s32 x, s32 y)
{
    em_WsMsg(ws, 4, BANK_ABILITIES, abil);
    ds_put(ds_fmt(ws, TXT_EVO_DEX_TYPE), x, y, C_NORMAL, 0);
}

static u32 ds_grade(u32 v)
{
    return v < 50 ? 0 : v < 70 ? 1 : v < 90 ? 2 : v < 110 ? 3 : v < 130 ? 4 : 5;
}

static void ds_draw(void *ctx)
{
    void *bmp = ds.bmp, *ws;
    u32 k, sex, rare, form = 0, sp = dx_CurSpecies(ctx), total = 0, n;
    void *dex = em_DexOf(CTX_SAVE(ctx));
    ds_dbg.species = sp;
    ds_dbg.caught = em_DexCaught(dex, sp) != 0;
    em_DexDraw(dex, sp, &sex, &rare, &form, ds.heap);       /* the form INFO shows (FUN_021A3004 asks the same) */
    ds_dbg.form = form;
    em_BmpFill(bmp, 0);
    /* the box (the FORMS / EVO pages' look), the lines under the title and above the abilities, shaded rows */
    em_BmpFillArea(bmp, 1, BOX_Y, CW * 8 - 2, BOX_H, K_BORDER2);
    em_BmpFillArea(bmp, 0, BOX_Y + 1, CW * 8, BOX_H - 2, K_BORDER2);
    em_BmpFillArea(bmp, 1, BOX_Y + 1, CW * 8 - 2, BOX_H - 2, K_BORDER);
    em_BmpFillArea(bmp, 2, BOX_Y + 2, CW * 8 - 4, BOX_H - 4, K_FILL);
    for (k = 2; k <= 8; k += 2)
        if (k != 7)
            em_BmpFillArea(bmp, 2, ROW(k) - 1, CW * 8 - 4, 16, K_FILL2);
    em_BmpFillArea(bmp, 2, ROW(1) - 1, CW * 8 - 4, 1, K_LINE);
    em_BmpFillArea(bmp, 2, ROW(7) - 1, CW * 8 - 4, 1, K_LINE);
    ws = em_WsCreate(ds.heap);
    ds_put(ds_fmt(0, TXT_DS_TITLE), LABEL_X, ROW(0), C_GOLD, 0);
    for (k = 0; k < 6; k++) {
        u32 y = ROW(1 + k), v = 0, w;
        ds_put(ds_fmt(0, ds_label[k]), LABEL_X, y, C_NORMAL, 0);
        em_BmpFillArea(bmp, BAR_X, y + 4, BAR_W, 6, K_LINE);
        if (!ds_dbg.caught) {
            ds_put(ds_fmt(0, TXT_EVO_UNKNOWN), VAL_R, y, C_DIM, 1);
            ds_dbg.stats[k] = 0;
            continue;
        }
        v = em_PersonalParam(sp, form, ds_param[k]);
        ds_dbg.stats[k] = v;
        total += v;
        ds_num(ws, v, VAL_R, y, C_NORMAL);
        w = (v < BAR_FULL ? v : BAR_FULL) * BAR_W / BAR_FULL;
        if (v && !w)
            w = 1;
        em_BmpFillArea(bmp, BAR_X, y + 4, w, 6, K_BAR0 + ds_grade(v));
    }
    /* the total, right in the title row */
    if (ds_dbg.caught) {
        em_WsNumber(ws, 0, total, 4, 0, 1);
        n = 0;
        {
            void *str = ds_fmt(ws, TXT_EVO_DEX_NUM);
            n = em_StrWidth(str, ds.font, 0);
            ds_put(str, RIGHT, ROW(0), C_NORMAL, 1);
        }
    } else {
        void *str = ds_fmt(0, TXT_EVO_UNKNOWN);
        n = em_StrWidth(str, ds.font, 0);
        ds_put(str, RIGHT, ROW(0), C_DIM, 1);
    }
    ds_put(ds_fmt(0, TXT_DS_TOTAL), RIGHT - n - 6, ROW(0), C_GOLD, 1);
    ds_dbg.total = total;
    /* abilities: the two (one when both are the same), then the hidden ability */
    ds_put(ds_fmt(0, TXT_DS_ABIL), LABEL_X, ROW(7), C_GOLD, 0);
    ds_put(ds_fmt(0, TXT_DS_HIDDEN), LABEL_X, ROW(8), C_GOLD, 0);
    for (k = 0; k < 3; k++)
        ds_dbg.abil[k] = ds_dbg.caught ? em_PersonalParam(sp, form, 26 + k) : 0;  /* bytes 0x18-0x1A */
    if (!ds_dbg.caught) {
        ds_put(ds_fmt(0, TXT_EVO_UNKNOWN), AB1_X, ROW(7), C_DIM, 0);
        ds_put(ds_fmt(0, TXT_EVO_UNKNOWN), AB1_X, ROW(8), C_DIM, 0);
    } else {
        if (ds_dbg.abil[0])
            ds_word(ws, ds_dbg.abil[0], AB1_X, ROW(7));
        if (ds_dbg.abil[1] && ds_dbg.abil[1] != ds_dbg.abil[0])
            ds_word(ws, ds_dbg.abil[1], ds_dbg.abil[0] ? AB2_X : AB1_X, ROW(7));
        if (ds_dbg.abil[2])
            ds_word(ws, ds_dbg.abil[2], AB1_X, ROW(8));
        else
            ds_put(ds_fmt(0, TXT_EVO_DEX_DASH), AB1_X, ROW(8), C_DIM, 0);
    }
    em_WsFree(ws);
    ds_dbg.pending = 1;
    ds_dbg.redraws++;
}

/* printed: the tiles to VRAM (the map once, at setup) */
static void ds_flush(void)
{
    if (!ds_dbg.pending || em_QueBmpBusy(ds.que, ds.bmp))
        return;
    em_BgLoadChar(FRAME, em_BmpPixels(ds.bmp), CW * CH * 32, ds_dbg.tile + 1);
    ds_dbg.pending = 0;
    ds_dbg.ready = 1;
    ds_dbg.flushes++;
}

/* our map into BG2's screen (VRAM only; GFL's buffer keeps the card's) */
static u16 ds_entry(u32 x, u32 y)
{
    u32 t = ds_dbg.tile;
    if (x >= TX && x < TX + CW && y >= TY && y < TY + CH)
        t += 1 + (y - TY) * CW + (x - TX);
    return (PALROW << 12) | t;
}

static void ds_map(void)
{
    volatile u16 *scr = SCR_VRAM;
    u32 x, y;
    for (y = 0; y < 32; y++)
        for (x = 0; x < 32; x++)
            scr[y * 32 + x] = ds_entry(x, y);
    ds_dbg.maps++;
}

/* the card's map back (from GFL's screen buffer of frame 6) */
static void ds_unmap(void)
{
    em_BgLoadScr(FRAME);
    ds_dbg.restores++;
}

static void ds_free(void)
{
    if (ds.que) {
        em_QueClear(ds.que);
        em_QueFree(ds.que);
    }
    if (ds.bmp)
        em_BmpFree(ds.bmp);
    if (ds.msg)
        em_MsgFree(ds.msg);
    if (ds_dbg.tile >= 0)
        em_CharFree(FRAME, ds_dbg.tile, NTILES * 32);
    ds.que = ds.bmp = ds.msg = 0;
    ds_dbg.tile = -1;
    ds_dbg.on = ds_dbg.ready = ds_dbg.pending = 0;
}

/* after INFO's own setup (state 0): our tiles, map, palette, bitmap, print queue; then the first drawing */
static void ds_setup(void *work, void *data, void *ctx)
{
    void *h;
    static const u32 zero[8];
    ds.heap = WORK_HEAP(work);
    ds.data = data;
    ds.font = INFO_FONT(data);
    ds_dbg.tile = -1;
    ds_dbg.shown = ds_dbg.ready = ds_dbg.pending = ds_dbg.holds = 0;
    ds_dbg.setups++;
    ds_dbg.heap_free = em_HeapMaxAlloc(ds.heap);
    if (!ds.font || ds_dbg.heap_free < CW * CH * 32 + 0x3000) {     /* never short the entry's own allocations */
        ds_dbg.fail = 1;
        return;
    }
    ds_dbg.tile = em_CharAlloc(FRAME, NTILES * 32, 0);
    if (ds_dbg.tile < 0 || ds_dbg.tile + NTILES > 1024) {
        if (ds_dbg.tile >= 0)
            em_CharFree(FRAME, ds_dbg.tile, NTILES * 32);
        ds_dbg.tile = -1;
        ds_dbg.fail = 2;
        return;
    }
    ds.bmp = em_BmpNew(CW, CH, 0x20, ds.heap);
    ds.que = em_QueNew(0x1000, ds.heap);
    ds.msg = em_MsgNew(0, 2, SYSTEM_BANK_SUMMARY, ds.heap);
    ds_dbg.heap_after = em_HeapMaxAlloc(ds.heap);
    em_BgLoadChar(FRAME, zero, 32, ds_dbg.tile);
    h = em_ArcOpen(DEX_ARC, ds.heap);
    em_PalLoad(h, DS_FILE_PAL, 4, 0, PALROW * 32, 0x20, ds.heap);
    em_ArcClose(h);
    ds_dbg.on = 1;
    ds_dbg.fail = 0;
    ds_draw(ctx);
}

/* every INFO frame (after its own step): print, flush, a new species, shown unless a foreign entry is */
static void ds_frame(void *data, void *ctx)
{
    u32 foreign = INFO_LANG(data) != 6;
    em_QueRun(ds.que);
    ds_flush();
    if (!ds_dbg.pending && dx_CurSpecies(ctx) != ds_dbg.species)
        ds_draw(ctx);
    ds_dbg.foreign = foreign;
    if (ds_dbg.ready && !foreign) {
        volatile u16 *scr = SCR_VRAM;
        if (!ds_dbg.shown || scr[0] != ds_entry(0, 0) || scr[TY * 32 + TX] != ds_entry(TX, TY) ||
            scr[23 * 32 + 31] != ds_entry(31, 23))
            ds_map();                                   /* first, or GFL put the card's map back meanwhile */
        if (!ds_dbg.shown || !(DISPCNT_B & (1 << 10))) {
            em_BgOn(FRAME, 1);
            if (!ds_dbg.shown)
                ds_dbg.shows++;
            ds_dbg.shown = 1;
        }
    } else if (ds_dbg.shown) {
        ds_unmap();                                     /* the foreign panel's card layer as it was */
        if (!foreign)
            em_BgOn(FRAME, 0);
        ds_dbg.shown = 0;
        ds_dbg.hides++;
    }
}

u32 ds_main(void *module, u32 *state, void *work, void *data, void *ctx)
{
    u32 st = *state, r;
    if (st == 1 && ds_dbg.on && !ds_dbg.ready && ds_dbg.holds < 30) {
        /* first picture: INFO fades in once ours is printed too (at most 30 frames later) */
        ds_dbg.holds++;
        em_QueRun(ds.que);
        ds_flush();
        return 0;
    }
    r = ds_InfoMain(module, state, work, data, ctx);
    if (st == 0 && *state != 0)
        ds_setup(work, data, ctx);
    if (ds_dbg.on && ds.data == data)
        ds_frame(data, ctx);
    return r;
}

u32 ds_exit(void *module, u32 *state, void *work, void *data, void *ctx)
{
    if (ds_dbg.on && ds.data == data) {
        if (ds_dbg.shown) {
            ds_unmap();
            em_BgOn(FRAME, 0);
            ds_dbg.shown = 0;
        }
        ds_free();
    }
    ds.data = 0;
    ds_dbg.exits++;
    return ds_InfoExit(module, state, work, data, ctx);
}
