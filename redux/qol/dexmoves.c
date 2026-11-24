/* ReRedux evomoves, Pokédex side: an EVO/MOVES page in a species' Pokédex entry (overlay 298), after INFO / AREA / CRY /
 * FORMS. Top screen: the evolution family (as on the summary page); bottom screen: the level-up learnset with each move's
 * type and power, scrolled by the touch screen's arrows (or L / R).
 *
 * The entry screen (overlay 298) runs one "page module" at a time: a table of five functions (init, main, exit, input,
 * draw) created by FUN_021A061C from the page number in top+4 (1 INFO .. 4 FORMS), each module setting up its own BG
 * layers, fading in, running and fading out again; the framework keeps the bottom bar (BG1 + OBJ buttons, overlay 298's
 * button manager) and the top header (BG1 of the top screen, a label printed from a message bank). The bar turns touches
 * and keys into actions: 6-9 open page 1-4, 1/2 leave the entry, 0xC/0xD (UP/DOWN keys) the next/previous species; the
 * module gets every action through its input function and ends itself when it should, the framework then creates the
 * next one. LEFT/RIGHT walk the page buttons (FUN_021A19C4, bar+0x14 = page index 0-3).
 * Page 5 (bar index 4) is this module (dx_tbl). Hooks (evomoves.py): FUN_021A061C's calls (em_dx_switch: page 5 -> our
 * module), the bar's page walk (em_dx_bar: LEFT on INFO, RIGHT on FORMS (or on CRY without FORMS) -> our page; LEFT /
 * RIGHT on our page -> FORMS (CRY) / INFO), the action read in the page loop (em_dx_action: our page request becomes a
 * page action that ends the current module; em_dx_switch then takes page 5 instead). The header label and both grids
 * use our green theme (evomoves.py adds the palettes to a/1/5/7). */
#include "qol.h"
#include "qol_texts.h"
#include "evomoves_data.h"
#include "evomoves.h"
#include "evomoves_capsule.h"

/* overlay 298 */
void *dx_ModCreate(const void *tbl, void *work, u32 heap);
void dx_ModFree(void *module);
void *dx_ModAlloc(void *module, u32 size, u32 heap);
void dx_ModFreeData(void *module);
void dx_Switch(void *top, void *work);
void dx_BarUpdate(void *bar);
u32 dx_BarTouch(void *bar);
u32 dx_CurSpecies(void *ctx);
void dx_NextSpecies(void *ctx);
void dx_PrevSpecies(void *ctx);
u32 dx_BarMode(void *bar);
void dx_BarSetup(void *bar, u32 mode, u32 page, u32 many);
void dx_BarStart(void *bar, u32 v);
void dx_BarPage(void *bar, u32 page);
void dx_BarEnable(void *bar, u32 on);
void dx_BarCheck(void *bar, u32 v);
void dx_BarAck(void *bar);
void dx_BarExit(void *bar, u32 v);
u32 dx_BarCheckGet(void *bar);
void dx_BtnPress(void *mgr, u32 id);
u32 dx_BtnShown(void *mgr, u32 id);
void dx_BtnEnable(void *mgr, u32 id, u32 on);
u32 dx_HdrState(void *hdr);
void dx_HdrIn(void *hdr);
void dx_HdrOut(void *hdr);
void dx_HdrFlush(void *hdr);
void *dx_FadeNew(u32 heap);
void dx_FadeInit(void *f);
void dx_FadeBind(u32 screen, void *f);
void dx_FadeIn(void *f);
u32 dx_FadeBusy(void *f);
void dx_FadeOut(void *f);
void dx_FadeUpdate(void *top, void *bottom);
void dx_FadeFree(void *f);
void *dx_GridLoad(u32 heap, u32 theme, u32 frame, u32 palrow, u32 palrow2);
void dx_GridFree(void *g);
/* ARM9 */
void em_BgOffset(u32 frame, u32 op, s32 v);
void em_BgClear(u32 frame);
void em_BgPrio(u32 frame, u32 prio);
void em_BgOn(u32 frame, u32 on);
void em_BgLoadChar(u32 frame, const void *data, u32 size, u32 tile);
void *em_BmpNew(u32 w, u32 h, u32 bpt, u32 heap);
void em_BmpFree(void *bmp);
void *em_BmpPixels(void *bmp);
void *em_BmpLoad(u32 arc, u32 file, u32 comp, u32 heap);
void em_BmpCopy(void *src, void *dst);
void *em_FontNew(u32 arc, u32 a, u32 b, u32 c, u32 heap);
void em_FontFree(void *font);
void *em_QueNew(u32 size, u32 heap);
void em_QueFree(void *que);
void em_QueClear(void *que);
void em_QueRun(void *que);
void *em_MsgNew(u32 a, u32 b, u32 bank, u32 heap);
void em_MsgFree(void *msg);
void *em_ArcOpen(u32 arc, u32 heap);
void em_ArcClose(void *h);
void em_PalLoad(void *h, u32 file, u32 engine, u32 src, u32 dst, u32 size, u32 heap);
u32 em_MoveParam(u32 move, u32 param);
void *em_HeapAlloc(u32 heap, u32 size, u32 clear, const char *file, u32 line);
u32 em_SaveCfg(void *save, u32 idx);
void em_SaveCfgSet(void *save, u32 idx, u32 v);
void *em_DexOf(void *save);
u32 em_DexCaught(void *dex, u32 species);

#define PAD_R       0x0100
#define PAD_L       0x0200
#define PAD_RIGHT   0x0010
#define PAD_LEFT    0x0020

#define DX_PAGE     5           /* top+4 */
#define DX_IDX      4           /* bar+0x14 */
#define DEX_ARC     0x9D        /* a/1/5/7 */
#define FONT_ARC    0x17
#define SYSTEM_BANK_SUMMARY 179
#define BANK_TYPES  398
#define BTN_INFO    7
#define BTN_CRY     9
#define BTN_FORMS   10
#define SE_PAGE     0x548
#define SE_SCROLL   0x54C
#define PALROW      14          /* our text / box palette row (free on both screens in every entry page) */

/* evomoves.py: palettes appended to a/1/5/7 */
#define DX_FILE_PAL_BOTTOM  DX_PAL_FIRST        /* the grid's theme row (0) for the bottom screen (from NCLR 1) */
#define DX_FILE_PAL_TOP     (DX_PAL_FIRST + 1)  /* ... the top screen (NCLR 2) */
#define DX_FILE_PAL_HDR     (DX_PAL_FIRST + 2)  /* the header (NCLR 4 row 0) */
#define DX_FILE_PAL_BOX     (DX_PAL_FIRST + 3)  /* our boxes and text (row 0) */

/* colours of DX_FILE_PAL_BOX */
#define K_FILL      1
#define K_BORDER    2
#define K_BORDER2   3
#define K_WHITE     4
#define K_SHADOW    5
#define K_HI        6
#define K_HI_SH     7
#define K_GOLD      8
#define K_GOLD_SH   9
#define K_LINE      10
#define K_FILL2     11
#define K_GREY      12
#define C_NORMAL    COL(K_WHITE, K_SHADOW, 0)
#define C_HI        COL(K_HI, K_HI_SH, 0)
#define C_GOLD      COL(K_GOLD, K_GOLD_SH, 0)
#define C_DIM       COL(K_GREY, K_SHADOW, 0)

/* the two content layers: BG2 of each screen, a bitmap of 30 x 21 tiles at tile (1, 3) on top / (1, 0) on the bottom */
#define TOP_FRAME   6
#define BOT_FRAME   2
#define CW          30
#define CH          21
#define TOP_TY      3
#define BOT_TY      0
#define LROWS       8           /* learnset rows on the bottom */
#define EROWS       9           /* family lines on the top */

typedef struct {
    u32 magic;          /* 'DXMV' */
    u8 state, end, shown, pending;
    u16 species;
    u8 nlearn, scroll, nfam, lines;
    u16 inits, exits, injects, switches, redraws, scrolls, inputs, bars;
    u16 last_action, overflow, caps, caught;
    void *ctx;          /* the page module's context (tests: the species list at +0x18, count +0x1C, index +0x20) */
} DxDbg;
DxDbg dx_dbg = { 0x564D5844 };

typedef struct {
    u16 heap;
    void *ctx;
    void *fade_top, *fade_bot;
    void *grid_top, *grid_bot;
    void *font, *msg, *que;
    void *bmp_top, *bmp_bot;
    u8 drawn, caught;
} DxWork;

static const u16 dx_zero_tile[16];
static u16 dx_map[CW * CH];

/* em_dx_*: our page request (LEFT / RIGHT onto the page), injected as a page action of another page */
static struct {
    u8 req;             /* a key asked for our page: next action read injects one */
    u8 go;              /* page action injected: em_dx_switch takes page 5 when top+4 == go_page */
    u8 go_page;
} dx_nav;

#define CTX_SAVE(c)     (*(void **)((u8 *)(c) + 0x00))
#define CTX_BAR(c)      (*(void **)((u8 *)(c) + 0x10))
#define CTX_HDR(c)      (*(void **)((u8 *)(c) + 0x14))
#define CTX_COUNT(c)    (*(u16 *)((u8 *)(c) + 0x1C))
#define BAR_MODE(b)     (*(u32 *)((u8 *)(b) + 0x10))
#define BAR_PAGE(b)     (*(u32 *)((u8 *)(b) + 0x14))
#define BAR_MGR(b)      (*(void **)((u8 *)(b) + 0x2C))
#define HDR_HEAP(h)     (*(u16 *)((u8 *)(h) + 0x00))
#define HDR_FONT(h)     (*(void **)((u8 *)(h) + 0x04))
#define HDR_BMP(h)      (*(void **)((u8 *)(h) + 0x18))
#define HDR_QUE(h)      (*(void **)((u8 *)(h) + 0x2C))
#define HDR_DIRTY(h)    (*(u32 *)((u8 *)(h) + 0x30))
#define TOP_PAGE(t)     (*(u32 *)((u8 *)(t) + 0x04))
#define WORK_HEAP(w)    (*(u16 *)((u8 *)(w) + 0x00))
#define WORK_MOD(w)     (*(void **)((u8 *)(w) + 0x20))
#define WORK_MODMEM(w)  (*(void **)((u8 *)(w) + 0x24))
#define MOD_DATA(m)     (*(void **)((u8 *)(m) + 0x10))

/* --- drawing ------------------------------------------------------------------------------------------------------- */

static void *dx_fmt(DxWork *w, void *ws, u32 id)
{
    void *src = em_MsgLoad(w->msg, id), *dst;
    if (!ws)
        return src;
    dst = em_StrBufCreate(160, w->heap);
    em_WsFormat(ws, dst, src);
    em_StrBufFree(src);
    return dst;
}

static u32 dx_put(DxWork *w, void *bmp, void *str, s32 x, s32 y, u32 color, u32 align)
{
    u32 width = em_StrWidth(str, w->font, 0);
    if (align == 1)
        x -= (s32)width;
    else if (align == 2)
        x -= (s32)width / 2;
    em_PrintQue(w->que, bmp, x, y, str, w->font, color);
    em_StrBufFree(str);
    return width;
}

/* the FORMS page's box look: a dark box with a gold double border, corners cut */
static void dx_box(void *bmp, u32 x, u32 y, u32 wd, u32 ht)
{
    em_BmpFillArea(bmp, x + 1, y, wd - 2, ht, K_BORDER2);
    em_BmpFillArea(bmp, x, y + 1, wd, ht - 2, K_BORDER2);
    em_BmpFillArea(bmp, x + 1, y + 1, wd - 2, ht - 2, K_BORDER);
    em_BmpFillArea(bmp, x + 2, y + 2, wd - 4, ht - 4, K_FILL);
}

/* the family's lines (as dx_draw_top lays them out; a method too wide for its name's line takes its own) */
static DxWork *dx_cur;
static u32 dx_top_lines(void)
{
    DxWork *w = dx_cur;
    u32 r, line = 0, text, mw, name_end;
    void *ws, *str;
    for (r = 0; r < em_dbg.nfam && line < EROWS; r++) {
        EmFam *f = &em_fam[r];
        s32 right = CW * 8 - 10;
        name_end = 8;
        if (!f->cont) {
            ws = em_WsCreate(w->heap);
            em_WsSpecies(ws, 3, f->species);
            str = dx_fmt(w, ws, f->depth ? TXT_EVO_CHILD : TXT_EVO_ROOT);
            name_end = 8 + (f->depth > 1 ? (f->depth - 1) * 16 : 0) + em_StrWidth(str, w->font, 0);
            em_StrBufFree(str);
            em_WsFree(ws);
        }
        if (f->evo >= 0) {
            ws = em_method_ws_heap(w->heap, f->evo, &text);
            str = dx_fmt(w, ws, text);
            mw = em_StrWidth(str, w->font, 0);
            em_StrBufFree(str);
            em_WsFree(ws);
            if (!f->cont && (s32)(name_end + 8 + mw) > right)
                line++;
        }
        line++;
    }
    if (line > EROWS)
        line = EROWS;
    return line < 2 ? 2 : line;
}

static void dx_draw_top(DxWork *w)
{
    void *bmp = w->bmp_top, *ws, *str;
    u32 r, line = 0, text, mw, name_end;
    dx_cur = w;
    em_BmpFill(bmp, 0);
    if (!w->caught) {                           /* seen only: as the INFO page, no data (the name and ???) */
        dx_box(bmp, 0, 4, CW * 8, 2 * 16 + 12);
        ws = em_WsCreate(w->heap);
        em_WsSpecies(ws, 3, em_dbg.species);
        dx_put(w, bmp, dx_fmt(w, ws, TXT_EVO_ROOT), 8, 10, C_HI, 0);
        em_WsFree(ws);
        dx_put(w, bmp, dx_fmt(w, 0, TXT_EVO_UNKNOWN), CW * 8 - 10, 10 + 16, C_DIM, 1);
        dx_dbg.lines = 0;
        return;
    }
    dx_box(bmp, 0, 4, CW * 8, dx_top_lines() * 16 + 12);
    for (r = 0; r < em_dbg.nfam && line < EROWS; r++) {
        EmFam *f = &em_fam[r];
        s32 y = 10 + line * 16, right = CW * 8 - 10;
        name_end = 8;
        if (!f->cont) {
            ws = em_WsCreate(w->heap);
            em_WsSpecies(ws, 3, f->species);
            str = dx_fmt(w, ws, f->depth ? TXT_EVO_CHILD : TXT_EVO_ROOT);
            name_end = 8 + (f->depth > 1 ? (f->depth - 1) * 16 : 0);
            name_end += dx_put(w, bmp, str, name_end, y, f->species == em_dbg.species ? C_HI : C_NORMAL, 0);
            em_WsFree(ws);
        }
        if (f->evo < 0) {
            if (em_dbg.nfam == 1)
                dx_put(w, bmp, dx_fmt(w, 0, TXT_EVO_NONE), right, y, C_DIM, 1);
            line++;
            continue;
        }
        ws = em_method_ws_heap(w->heap, f->evo, &text);
        str = dx_fmt(w, ws, text);
        mw = em_StrWidth(str, w->font, 0);
        if (!f->cont && (s32)(name_end + 8 + mw) > right) {
            line++;
            if (line >= EROWS) {
                em_StrBufFree(str);
                em_WsFree(ws);
                dx_dbg.overflow++;
                break;
            }
            y = 10 + line * 16;
        }
        dx_put(w, bmp, str, right, y, C_GOLD, 1);
        em_WsFree(ws);
        line++;
    }
    if (r < em_dbg.nfam)
        dx_dbg.overflow += em_dbg.nfam - r;
    dx_dbg.lines = line;
}

#define LV_R    44      /* right edge of the level */
#define MOVE_X  52
#define TYPE_X  150
#define POW_R   228

static void dx_draw_bottom(DxWork *w)
{
    void *bmp = w->bmp_bot, *ws;
    u32 k, last;
    em_BmpFill(bmp, 0);
    dx_box(bmp, 0, 4, CW * 8, (LROWS + 1) * 16 + 12);
    /* title row: "Level-up moves", the position and the arrows */
    em_BmpFillArea(bmp, 2, 6 + 16, CW * 8 - 4, 1, K_LINE);
    dx_put(w, bmp, dx_fmt(w, 0, TXT_EVO_DEX_LEARN), 8, 7, C_GOLD, 0);
    if (em_dbg.nlearn > LROWS && w->caught) {
        last = em_dbg.scroll + LROWS;
        if (last > em_dbg.nlearn)
            last = em_dbg.nlearn;
        ws = em_WsCreate(w->heap);
        em_WsNumber(ws, 0, em_dbg.scroll + 1, 2, 0, 1);
        em_WsNumber(ws, 1, last, 2, 0, 1);
        em_WsNumber(ws, 2, em_dbg.nlearn, 2, 0, 1);
        dx_put(w, bmp, dx_fmt(w, ws, TXT_EVO_LIST_POS), CW * 8 - 26, 7, C_NORMAL, 1);
        em_WsFree(ws);
        dx_put(w, bmp, dx_fmt(w, 0, TXT_EVO_UP), CW * 8 - 22, 7, em_dbg.scroll ? C_GOLD : C_DIM, 0);
        dx_put(w, bmp, dx_fmt(w, 0, TXT_EVO_DOWN), CW * 8 - 12, 7,
               em_dbg.scroll + LROWS < em_dbg.nlearn ? C_GOLD : C_DIM, 0);
    }
    if (!w->caught) {
        dx_put(w, bmp, dx_fmt(w, 0, TXT_EVO_UNKNOWN), MOVE_X, 7 + 16, C_DIM, 0);
        return;
    }
    if (!em_dbg.nlearn)
        dx_put(w, bmp, dx_fmt(w, 0, TXT_EVO_LIST_NONE), MOVE_X, 7 + 16, C_DIM, 0);
    for (k = 0; k < LROWS && em_dbg.scroll + k < em_dbg.nlearn; k++) {
        u32 i = em_dbg.scroll + k, mv = em_learn[2 * i], y = 7 + 16 * (k + 1), pow;
        if (k & 1)
            em_BmpFillArea(bmp, 2, y - 1, CW * 8 - 4, 16, K_FILL2);
        ws = em_WsCreate(w->heap);
        em_WsNumber(ws, 0, em_learn[2 * i + 1], 3, 0, 1);
        dx_put(w, bmp, dx_fmt(w, ws, TXT_EVO_LIST_LV), LV_R, y, C_NORMAL, 1);
        em_WsMove(ws, 2, mv);
        dx_put(w, bmp, dx_fmt(w, ws, TXT_EVO_MOVENAME), MOVE_X, y, C_NORMAL, 0);
        if (em_MoveParam(mv, 0) < 17) {
            em_WsMsg(ws, 4, BANK_TYPES, em_MoveParam(mv, 0));
            dx_put(w, bmp, dx_fmt(w, ws, TXT_EVO_DEX_TYPE), TYPE_X, y, C_HI, 0);
        } else {                                    /* Redux's Fairy (17) has no name in bank 398 */
            dx_put(w, bmp, dx_fmt(w, 0, TXT_EVO_TYPE_FAIRY), TYPE_X, y, C_HI, 0);
        }
        pow = em_MoveParam(mv, 3);
        if (pow > 1) {
            em_WsNumber(ws, 0, pow, 3, 0, 1);
            dx_put(w, bmp, dx_fmt(w, ws, TXT_EVO_DEX_NUM), POW_R, y, C_NORMAL, 1);
        } else {
            dx_put(w, bmp, dx_fmt(w, 0, TXT_EVO_DEX_DASH), POW_R, y, C_DIM, 1);
        }
        em_WsFree(ws);
    }
}

static void dx_redraw(DxWork *w, u32 data)
{
    if (data) {
        em_dbg.species = dx_CurSpecies(w->ctx);
        w->caught = em_DexCaught(em_DexOf(CTX_SAVE(w->ctx)), em_dbg.species) != 0;
        dx_dbg.caught = w->caught;
        em_dbg.form = 0;
        em_dbg.level = 0;
        em_family(em_dbg.species);
        em_learnset(em_dbg.species, 0);
        em_dbg.next = 0xFF;
        em_dbg.scroll = 0;
        dx_dbg.species = em_dbg.species;
        dx_dbg.nlearn = em_dbg.nlearn;
        dx_dbg.nfam = em_dbg.nfam;
        dx_draw_top(w);
    }
    dx_dbg.scroll = em_dbg.scroll;
    dx_draw_bottom(w);
    dx_dbg.pending = 1;
    dx_dbg.redraws++;
}

/* when both bitmaps are printed: their tiles to BG2 of each screen (tile 1 on), the maps once */
static void dx_flush(DxWork *w)
{
    u32 i;
    if (!dx_dbg.pending || em_QueBmpBusy(w->que, w->bmp_top) || em_QueBmpBusy(w->que, w->bmp_bot))
        return;
    em_BgLoadChar(TOP_FRAME, em_BmpPixels(w->bmp_top), CW * CH * 32, 1);
    em_BgLoadChar(BOT_FRAME, em_BmpPixels(w->bmp_bot), CW * CH * 32, 1);
    if (!w->drawn) {
        em_BgLoadChar(TOP_FRAME, dx_zero_tile, 32, 0);
        em_BgLoadChar(BOT_FRAME, dx_zero_tile, 32, 0);
        for (i = 0; i < CW * CH; i++)
            dx_map[i] = (PALROW << 12) | (1 + i);
        em_BgScrArea(TOP_FRAME, 1, TOP_TY, CW, CH, dx_map, 0, 0, CW, CH);
        em_BgScrArea(BOT_FRAME, 1, BOT_TY, CW, CH, dx_map, 0, 0, CW, CH);
        em_BgQueue(TOP_FRAME);
        em_BgQueue(BOT_FRAME);
        w->drawn = 1;
    }
    dx_dbg.pending = 0;
}

/* the header: our label in the green theme (as FUN_021A2400 prints the pages' labels) */
static void dx_label(DxWork *w)
{
    void *hdr = CTX_HDR(w->ctx), *h, *bmp, *str;
    h = em_ArcOpen(DEX_ARC, w->heap);
    em_PalLoad(h, DX_FILE_PAL_HDR, 4, 0, 0x1A0, 0x20, w->heap);
    em_ArcClose(h);
    bmp = em_BmpLoad(DEX_ARC, 0xE, 0, w->heap);
    em_BmpCopy(bmp, HDR_BMP(hdr));
    em_BmpFree(bmp);
    str = em_MsgLoad(w->msg, TXT_EVO_DEX_TITLE);
    em_PrintQue(HDR_QUE(hdr), HDR_BMP(hdr), 0x18, 5, str, HDR_FONT(hdr), 0xF7 << 6);
    em_StrBufFree(str);
    HDR_DIRTY(hdr) = 1;
    dx_HdrFlush(hdr);
}

/* --- the module ---------------------------------------------------------------------------------------------------- */

static u32 dx_init(void *module, u32 *state, void *work, void *data, void *ctx)
{
    u32 heap = WORK_HEAP(work);
    DxWork *w = dx_ModAlloc(module, sizeof(DxWork), heap);
    u32 i;
    for (i = 0; i < sizeof(DxWork); i++)
        ((u8 *)w)[i] = 0;
    w->heap = heap;
    w->ctx = ctx;
    w->fade_top = dx_FadeNew(heap);
    w->fade_bot = dx_FadeNew(heap);
    dx_FadeInit(w->fade_top);
    dx_FadeInit(w->fade_bot);
    dx_FadeBind(0, w->fade_top);
    dx_FadeBind(1, w->fade_bot);
    dx_dbg.inits++;
    dx_dbg.end = 0;
    dx_dbg.state = 0;
    return 1;
}

static void dx_setup(DxWork *w)
{
    void *ctx = w->ctx, *bar = CTX_BAR(ctx), *hdr = CTX_HDR(ctx), *h;
    u32 f;
    for (f = 0; f < 8; f++)
        if (f != 1 && f != 5) {
            em_BgOffset(f, 0, 0);
            em_BgOffset(f, 3, 0);
            em_BgClear(f);
        }
    em_BgPrio(BOT_FRAME, 1);
    em_BgPrio(0, 3);
    em_BgPrio(TOP_FRAME, 1);
    em_BgPrio(4, 3);
    /* the bar: our page index (no page button lit), every page button touchable */
    if (dx_BarMode(bar) != 2) {
        dx_BarSetup(bar, 0, DX_IDX, CTX_COUNT(ctx) > 1);
        dx_BarStart(bar, 0);
    } else {
        dx_BarPage(bar, DX_IDX);
    }
    dx_BarEnable(bar, 0);
    dx_BarCheck(bar, em_SaveCfg(CTX_SAVE(ctx), 0x14));
    for (f = BTN_INFO; f <= BTN_FORMS; f++)
        dx_BtnEnable(BAR_MGR(bar), f, 1);
    /* grids (INFO's theme), then our green over their palette rows; our box / text row */
    w->grid_bot = dx_GridLoad(w->heap, 0, 0, 2, 3);
    w->grid_top = dx_GridLoad(w->heap, 0, 4, 1, 2);
    h = em_ArcOpen(DEX_ARC, w->heap);
    em_PalLoad(h, DX_FILE_PAL_BOTTOM, 0, 0, 2 * 32, 0x20, w->heap);
    em_PalLoad(h, DX_FILE_PAL_BOTTOM, 0, 0, 3 * 32, 0x20, w->heap);
    em_PalLoad(h, DX_FILE_PAL_TOP, 4, 0, 1 * 32, 0x20, w->heap);
    em_PalLoad(h, DX_FILE_PAL_TOP, 4, 0, 2 * 32, 0x20, w->heap);
    em_PalLoad(h, DX_FILE_PAL_BOX, 0, 0, PALROW * 32, 0x20, w->heap);
    em_PalLoad(h, DX_FILE_PAL_BOX, 4, 0, PALROW * 32, 0x20, w->heap);
    em_ArcClose(h);
    em_BgOn(TOP_FRAME, 1);
    em_BgOn(BOT_FRAME, 1);
    em_BgOn(4, 1);
    em_BgOn(0, 1);
    /* text */
    w->font = em_FontNew(FONT_ARC, 0, 1, 0, w->heap);
    w->msg = em_MsgNew(0, 2, SYSTEM_BANK_SUMMARY, w->heap);
    w->que = em_QueNew(0x1000, w->heap);
    w->bmp_top = em_BmpNew(CW, CH, 0x20, w->heap);
    w->bmp_bot = em_BmpNew(CW, CH, 0x20, w->heap);
    if (dx_HdrState(hdr) != 2) {
        dx_label(w);
        dx_HdrIn(hdr);
    }
    dx_redraw(w, 1);
}

static u32 dx_main(void *module, u32 *state, void *work, void *data, void *ctx)
{
    DxWork *w = MOD_DATA(module);
    void *bar = CTX_BAR(ctx), *hdr = CTX_HDR(ctx);
    u32 done = 0;
    w->ctx = ctx;
    dx_dbg.ctx = ctx;
    switch (*state) {
    case 0:                                         /* set up, print */
        dx_setup(w);
        *state = 1;
        break;
    case 1:                                         /* printed: show, fade in */
        if (!dx_dbg.pending) {
            dx_FadeIn(w->fade_top);
            dx_FadeIn(w->fade_bot);
            *state = 2;
        }
        break;
    case 2:                                         /* faded in, bar and header ready: input on */
        if (!dx_FadeBusy(w->fade_top) && dx_BarMode(bar) == 2 && dx_HdrState(hdr) == 2) {
            dx_BarAck(bar);
            dx_BarEnable(bar, 1);
            *state = 3;
        }
        break;
    case 3:                                         /* running */
        if (dx_dbg.end) {
            dx_FadeOut(w->fade_top);
            dx_FadeOut(w->fade_bot);
            dx_HdrOut(hdr);
            if (dx_dbg.end == 2)
                dx_BarExit(bar, 0);
            *state = 4;
        } else {
            u32 rep = em_KeyRep(), tx, ty;
            s32 d = 0;
            if (rep & PAD_L)
                d = -LROWS;
            else if (rep & PAD_R)
                d = LROWS;
            else if (em_TouchTrg(&tx, &ty) && ty >= 8 && ty < 160 && tx >= 8 && tx < 248) {
                if (ty < 28 && tx >= 200)                   /* the arrows */
                    d = tx < 224 ? -LROWS : LROWS;
                else if (ty >= 28)                          /* the list: upper / lower half */
                    d = ty < 92 ? -LROWS : LROWS;
            }
            if (d && w->caught) {
                s32 s = (s32)em_dbg.scroll + d, max = (s32)em_dbg.nlearn - LROWS;
                if (max < 0)
                    max = 0;
                if (s < 0)
                    s = 0;
                if (s > max)
                    s = max;
                if ((u32)s != em_dbg.scroll) {
                    em_dbg.scroll = s;
                    dx_redraw(w, 0);
                    dx_dbg.scrolls++;
                    GFL_SndSEPlay(SE_SCROLL);
                }
            }
        }
        break;
    case 4:                                         /* faded out */
        if (!dx_FadeBusy(w->fade_top) && !dx_FadeBusy(w->fade_bot) && !dx_HdrState(hdr) &&
            (dx_dbg.end != 2 || !dx_BarMode(bar)))
            *state = 5;
        break;
    case 5:
        done = 1;
        break;
    }
    if (*state >= 1)
        em_QueRun(w->que);
    dx_flush(w);
    dx_FadeUpdate(w->fade_top, w->fade_bot);
    dx_dbg.state = *state;
    return done;
}

static u32 dx_exit(void *module, u32 *state, void *work, void *data, void *ctx)
{
    DxWork *w = MOD_DATA(module);
    if (w) {
        if (w->que) {
            em_QueClear(w->que);
            em_QueFree(w->que);
        }
        if (w->bmp_top)
            em_BmpFree(w->bmp_top);
        if (w->bmp_bot)
            em_BmpFree(w->bmp_bot);
        if (w->msg)
            em_MsgFree(w->msg);
        if (w->font)
            em_FontFree(w->font);
        if (w->grid_top)
            dx_GridFree(w->grid_top);
        if (w->grid_bot)
            dx_GridFree(w->grid_bot);
        dx_FadeFree(w->fade_bot);
        dx_FadeFree(w->fade_top);
        dx_ModFreeData(module);
    }
    dx_dbg.exits++;
    dx_dbg.shown = 0;
    return 1;
}

/* the bar's actions (as INFO's input): pages / leave end the module, UP / DOWN the next / previous species */
static void dx_input(void *module, u32 *state, void *work, void *data, void *ctx, u32 action)
{
    DxWork *w = MOD_DATA(module);
    void *bar = CTX_BAR(ctx);
    u32 before;
    dx_dbg.inputs++;
    dx_dbg.last_action = action;
    switch (action) {
    case 1: case 2:
        dx_dbg.end = 2;
        break;
    case 6: case 7: case 8: case 9:
        dx_dbg.end = 1;
        break;
    case 3: case 4:
        dx_BarAck(bar);
        break;
    case 5:
        em_SaveCfgSet(CTX_SAVE(ctx), 0x14, dx_BarCheckGet(bar));
        dx_BarAck(bar);
        break;
    case 0xC: case 0xD:
        before = dx_CurSpecies(ctx);
        if (action == 0xC)
            dx_NextSpecies(ctx);
        else
            dx_PrevSpecies(ctx);
        if (w && *state == 3 && dx_CurSpecies(ctx) != before)
            dx_redraw(w, 1);
        break;
    }
}

static const void *const dx_tbl[5] = { dx_init, dx_main, dx_exit, dx_input, 0 };

/* --- hooks --------------------------------------------------------------------------------------------------------- */

/* FUN_021A061C (create the page module for top+4): page 5 -> ours, as the original does for 1-4 */
void em_dx_switch(void *top, void *work)
{
    u32 heap = WORK_HEAP(work);
    void *mem;
    if (dx_nav.go && TOP_PAGE(top) == dx_nav.go_page)
        TOP_PAGE(top) = DX_PAGE;
    dx_nav.go = 0;
    dx_nav.req = 0;
    if (TOP_PAGE(top) != DX_PAGE) {
        dx_Switch(top, work);
        return;
    }
    if (WORK_MOD(work))
        dx_ModFree(WORK_MOD(work));
    if (WORK_MODMEM(work))
        em_HeapFree(WORK_MODMEM(work));
    mem = em_HeapAlloc(heap, 4, 1, "dexmoves", 0);
    *(u16 *)mem = heap;
    WORK_MODMEM(work) = mem;
    WORK_MOD(work) = dx_ModCreate(dx_tbl, mem, heap);
    dx_dbg.switches++;
    dx_dbg.shown = 1;
}

/* the entry's first module (FUN_021A061C when the entry opens) */
void em_dx_first(void *top, void *work)
{
    dx_nav.go = dx_nav.req = 0;
    if (TOP_PAGE(top) == DX_PAGE)
        TOP_PAGE(top) = 1;
    dx_Switch(top, work);
}

/* --- the bar's EVO capsule ------------------------------------------------------------------------------------------
 * The entry bar's page buttons are OBJs of overlay 298's button manager (9 at most); ours is drawn on the bar's BG
 * (bottom BG1: rows 21-23 of tiles 1-3, palette 13; tiles 5-511 of its char block are unused): 4 x 3 tiles from
 * evomoves_capsule.h (the vanilla capsule, active / inactive), palette rows 9-11, 32 px right of the last page
 * capsule (evomoves.py moves the bar's buttons to make room). It is put back each frame if the bar's BG was redrawn,
 * and taken off when the entry bar is freed or the bar changes mode. */
void em_BgPal(u32 frame, const void *data, u32 size, u32 offset);
void *dx_Btn(void *mgr, u32 id);
void dx_BarDel(void *bar);

#define BAR_SCREEN  ((volatile u16 *)0x06001000)    /* bottom BG1's screen (base 2) */
#define BG_PAL      ((volatile u16 *)0x05000000)    /* bottom BG palettes */
#define CAP_ROW     21

static struct {
    u8 on, x, active;
} dx_cap;

static u32 dx_cap_entry(u32 tr, u32 tc, u32 active)
{
    return (cap_palrow[tr] << 12) | (CAP_TILE0 + (active ? 0 : 12) + tr * 4 + tc);
}

static void dx_cap_map(u32 xt, s32 active)
{
    u16 map[12];
    u32 tr, tc;
    for (tr = 0; tr < 3; tr++)
        for (tc = 0; tc < 4; tc++)
            map[tr * 4 + tc] = active < 0 ? 0xD001 + tr : dx_cap_entry(tr, tc, active);
    em_BgScrArea(1, xt, CAP_ROW, 4, 3, map, 0, 0, 4, 3);
    em_BgQueue(1);
}

static void dx_cap_off(void)
{
    if (dx_cap.on)
        dx_cap_map(dx_cap.x, -1);
    dx_cap.on = 0;
}

/* the capsule's x (tiles): right of the last page capsule shown */
static u32 dx_cap_x(void *mgr)
{
    u32 id, x = 0;
    for (id = BTN_INFO; id <= BTN_FORMS; id++)
        if (dx_BtnShown(mgr, id)) {
            s16 bx = *(s16 *)((u8 *)dx_Btn(mgr, id) + 0x18);
            if (bx + 32 > (s32)x)
                x = bx + 32;
        }
    return x >> 3;
}

static void dx_cap_update(void *bar)
{
    void *mgr = BAR_MGR(bar);
    u32 xt = dx_cap_x(mgr), active = BAR_PAGE(bar) == DX_IDX, tr;
    if (xt < 4 || xt > 28)
        return;
    if (!dx_cap.on || dx_cap.x != xt || BAR_SCREEN[CAP_ROW * 32 + xt] != dx_cap_entry(0, 0, dx_cap.active) ||
        BG_PAL[cap_palrow[0] * 16 + 1] != cap_pal[0][1] || BG_PAL[cap_palrow[2] * 16 + 1] != cap_pal[2][1]) {
        if (dx_cap.on && dx_cap.x != xt)
            dx_cap_off();
        em_BgLoadChar(1, cap_tiles, sizeof(cap_tiles), CAP_TILE0);
        for (tr = 0; tr < 3; tr++)
            em_BgPal(1, cap_pal[tr], 32, cap_palrow[tr] * 32);
        dx_cap_map(xt, active);
        dx_cap.on = 1;
        dx_cap.x = xt;
        dx_cap.active = active;
        dx_dbg.caps++;
    } else if (dx_cap.active != active) {
        dx_cap_map(xt, active);
        dx_cap.active = active;
    }
}

/* the bar of the current mode is freed (mode change, the Pokédex closing): the capsule off first */
void em_dx_bardel(void *bar)
{
    if (BAR_MODE(bar) == 0)
        dx_cap_off();
    dx_cap.on = 0;
    dx_BarDel(bar);
}

/* the bar's page walk (FUN_021A19C4, entry mode): LEFT / RIGHT to and from our page, our capsule */
void em_dx_bar(void *bar)
{
    u32 rep = em_KeyRep(), idx = BAR_PAGE(bar), tx, ty;
    void *mgr = BAR_MGR(bar);
    dx_dbg.bars++;
    if (BAR_MODE(bar) == 0 && mgr) {
        dx_cap_update(bar);
        if (idx != DX_IDX && !dx_nav.go && dx_cap.on && em_TouchTrg(&tx, &ty) && ty >= 168 &&
            tx >= dx_cap.x * 8u && tx < dx_cap.x * 8u + 32) {
            dx_nav.req = 1;
            GFL_SndSEPlay(SE_PAGE);
            return;
        }
    }
    if (BAR_MODE(bar) == 0 && mgr && (rep & (PAD_LEFT | PAD_RIGHT)) && !dx_nav.go) {
        u32 forms = dx_BtnShown(mgr, BTN_FORMS);
        if (idx == DX_IDX) {
            if (rep & PAD_RIGHT)
                dx_BtnPress(mgr, BTN_INFO);
            else
                dx_BtnPress(mgr, forms ? BTN_FORMS : BTN_CRY);
            return;
        }
        if ((idx == 0 && (rep & PAD_LEFT)) || (idx == 3 && (rep & PAD_RIGHT)) ||
            (idx == 2 && (rep & PAD_RIGHT) && !forms)) {
            dx_nav.req = 1;
            GFL_SndSEPlay(SE_PAGE);
            return;
        }
    }
    dx_BarUpdate(bar);
}

/* the action read in the page loop (FUN_021A14AC there): our request -> another page's action */
u32 em_dx_action(void *bar)
{
    u32 a = dx_BarTouch(bar);
    if (!a && dx_nav.req) {
        u32 idx = BAR_PAGE(bar);
        dx_nav.req = 0;
        a = idx == 0 ? 7 : 6;                       /* any page but the current one ends its module */
        dx_nav.go = 1;
        dx_nav.go_page = a - 5;
        dx_dbg.injects++;
    }
    return a;
}
