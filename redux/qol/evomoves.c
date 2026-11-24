/* ReRedux evomoves: the EVO/MOVES page of the Pokémon summary (overlay 207): the species' evolution family with each
 * method (top screen) and its level-up learnset (bottom screen). evomoves.py lists the data, texts and graphics.
 *
 * The summary app keeps its page in app+0x58 (0 STATUS, 1 STATS, 2 RIBBONS, 3 the STATS page's move selection) and the
 * page shown so far in app+0x5C. A page has five steps, each called through a jump table on one of the two fields:
 *   hide     (PageRedraw 0x021B49D0, old page)  frees its windows
 *   create   (PageRedraw, new page)             creates its windows and prints into them (print queue)
 *   finold   (page change 0x021B4AFC, old page) clears its screens, hides its OBJs, its page button off
 *   finnew   (page change, new page)            loads its panels (BG 2 bottom, 6 top, 5 the title label), shows the windows
 *   update   (main step 0x021B3208, page shown) per frame
 * evomoves.py replaces each jump table by a call to em_hide / em_create / em_finold / em_finnew / em_update, which run
 * the original case for pages 0-3 and ours for page 4 (EM_PAGE). em_input runs before the app's input step: RIGHT on
 * the last page (STATS, or RIBBONS when the Pokémon has ribbons) goes to page 4, LEFT there goes back, A / the touch
 * screen scroll the learnset; everything else (UP / DOWN: the next Pokémon, B, X, the touch buttons) stays the app's.
 * UP / DOWN skip eggs on every page but STATUS, so page 4 never shows an egg (and RIGHT is refused on an egg).
 *
 * Screens (as the STATUS page): frame 4 top text, 5 top title bar, 6 top panel (the STATUS page's lined memo panel), 1
 * bottom text, 2 bottom panel (evomoves.py's learnset panel, a/0/7/7 member 182); the label « EVO/MOVES » is member
 * 181's title bar rows. Windows use the font palette row 14 (BG palette 0xE) like every summary window. */
#include "qol.h"
#include "qol_texts.h"
#include "evomoves_data.h"
#include "evomoves.h"

u32 PokeParty_GetParam(void *pp, u32 id, void *extra);
void *em_WinCreate(u32 frame, u32 x, u32 y, u32 w, u32 h, u32 pal, u32 dir);
void em_WinFree(void *win);
void em_WinFlushChar(void *win);
void em_WinFlushMap(void *win);
u32 em_WinFrame(void *win);
void *em_WinBmp(void *win);
void em_BgBufScr(u32 frame, void *data, u32 size);
void em_BgFillArea(u32 frame, u32 val, u32 x, u32 y, u32 w, u32 h, u32 pal);
void *em_ReadNSCR(u32 arc, u32 file, u32 comp, void **scr, u32 heap);
void em_LearnLoad(u32 species, u32 form, void *buf);
void *em_CurPP(void *app);
void em_PageRedraw(void *app);
void em_Input(void *app);
void em_ExitFirst(void *app);
void em_InitBG(void *app);
#define PAGE_FN(n) void em_P##n##Hide(void *, void *); void em_P##n##Create(void *, void *); \
    void em_P##n##FinOld(void *, void *); void em_P##n##FinNew(void *, void *);
PAGE_FN(0)
PAGE_FN(1)
PAGE_FN(2)
PAGE_FN(3)
void em_P1Update(void *app, void *page);
void em_P2Update(void *app, void *page);

#define PAD_A       0x0001
#define PAD_B       0x0002
#define PAD_RIGHT   0x0010
#define PAD_LEFT    0x0020
#define PAD_UP      0x0040
#define PAD_DOWN    0x0080
#define PAD_R       0x0100
#define PAD_L       0x0200

#define P_SPECIES   0x05
#define P_MOVE1     0x36
#define P_EGG       0x4C
#define P_FORM      0x6F
#define P_LEVEL     0x9E

#define SE_PAGE     0x665
#define SE_CURSOR   0x54C
#define SE_ENTER    0x548
#define SE_LEAVE    0x551

#define EM_PAGE     4
#define SUMMARY_ARC 0x4D        /* a/0/7/7 */
#define EM_FILE_LABEL 181
#define EM_FILE_PANEL 182
#define BANK_PLACES 109

#define APP_HEAP(a)     (*(u16 *)(a))
#define APP_PARAM(a)    (*(u8 **)((u8 *)(a) + 0x08))
#define APP_KEYMODE(a)  (*(u8 *)((u8 *)(a) + 0x1C))
#define APP_EGG(a)      (*(u32 *)((u8 *)(a) + 0x38))
#define APP_RIBBONS(a)  (*(u32 *)((u8 *)(a) + 0x40))
#define APP_INPUT(a)    (*(u32 *)((u8 *)(a) + 0x44))
#define APP_PAGE(a)     (*(u32 *)((u8 *)(a) + 0x58))
#define APP_SHOWN(a)    (*(u32 *)((u8 *)(a) + 0x5C))
#define APP_MSG(a)      (*(void **)((u8 *)(a) + 0x7C))
#define APP_FONT(a)     (*(void **)((u8 *)(a) + 0x80))
#define APP_QUE(a)      (*(void **)((u8 *)(a) + 0x84))
#define APP_P0(a)       (*(void **)((u8 *)(a) + 0x8C))
#define APP_P1(a)       (*(void **)((u8 *)(a) + 0x90))
#define APP_P2(a)       (*(void **)((u8 *)(a) + 0x94))
#define P0_MEMO_SCR(p)  (*(u8 **)((u8 *)(p) + 0x5C))    /* NNSG2dScreenData of the STATUS page's top panel */
#define PARAM_MODE(p)   ((p)[0x0D])                     /* 2: choosing a move to forget (page 3 only) */

#define C_TEXT          COL(1, 2, 0)        /* dark grey */
#define C_BLUE          COL(5, 6, 0)
#define C_RED           COL(3, 4, 0)
#define C_WHITE         COL(15, 2, 0)       /* on the dark column (the info page's labels) */
#define C_CURSOR_BG     6                   /* light blue bar behind the list cursor */

/* windows */
#define W_EVO   0       /* top: frame 4, x 1, y 5, 30 x 16 tiles: 8 rows of 16 px (the memo panel's rows) */
#define W_LIST  1       /* bottom: frame 1, x 0, y 1, 19 x 16 tiles: 8 rows (the learnset panel's rows) */
#define W_POS   2       /* bottom: frame 1, x 2, y 17, 17 x 2 tiles: the white box (list position) */
#define W_N     3
static const u8 win_geo[W_N][5] = { {4, 1, 5, 30, 16}, {1, 0, 1, 19, 16}, {1, 2, 17, 17, 2} };

#define LIST_ROWS   8
#define LIST_LV_R   48      /* right edge of "Lv. N" (window x) */
#define LIST_MOVE_X 55
#define EVO_ROWS    8
#define EVO_X0      8       /* root name (window x; the window starts at screen x 8) */
#define EVO_INDENT  16
#define EVO_RIGHT   228     /* right edge of the methods (screen x; the first row: 216) */
#define DET_VAL_X   80      /* move details: value column, second column, right edge (window x) */
#define DET_COL2_X  132
#define DET_RIGHT   212
#define BANK_TYPES  398
#define BANK_MOVE_DESC 402

EmDbg em_dbg = { 0x564D5645 };

static void *em_win[W_N];
static void *em_buf_label, *em_buf_panel;
static u8 *em_scr_label, *em_scr_panel;     /* NNSG2dScreenData */
u16 em_learn[MAX_LEARN * 2 + 2];     /* the learnset file (move, level) pairs */
static u16 em_learn_raw[0x80];
EmFam em_fam[MAX_FAM];
static u16 em_moves[4];
static void *em_desc;           /* move descriptions (list mode), freed with the page */
u32 em_MoveParam(u32 move, u32 param);
u32 em_MoveNeverMiss(u32 move);
void *em_MsgNew(u32 a, u32 b, u32 bank, u32 heap);
void em_MsgFree(void *msg);

/* --- text ---------------------------------------------------------------------------------------------------------- */

/* format line `id` of the summary bank with the word set (NULL: none) -> new StrBuf */
static void *em_fmt(void *app, void *ws, u32 id)
{
    void *src = em_MsgLoad(APP_MSG(app), id);
    void *dst;
    if (!ws)
        return src;
    dst = em_StrBufCreate(160, APP_HEAP(app));
    em_WsFormat(ws, dst, src);
    em_StrBufFree(src);
    return dst;
}

/* print str at x (align 0: left edge, 1: right edge, 2: centre at x) -> width; frees str */
static u32 em_put(void *app, u32 w, void *str, s32 x, s32 y, u32 color, u32 align)
{
    u32 width = em_StrWidth(str, APP_FONT(app), 0);
    if (align == 1)
        x -= (s32)width;
    else if (align == 2)
        x -= (s32)width / 2;
    em_PrintQue(APP_QUE(app), em_WinBmp(em_win[w]), x, y, str, APP_FONT(app), color);
    em_StrBufFree(str);
    return width;
}

/* the method line of evolution e, in a word set the caller frees */
void *em_method_ws_heap(u32 heap, u32 e, u32 *text)
{
    const EmEvo *v = &em_evo[e];
    void *ws = em_WsCreate(heap);
    u32 m = v->method, slot = 0;
    *text = TXT_EVO_UNKNOWN;
    if (m < 28 && em_methods[m].text) {
        *text = em_methods[m].text;
        slot = em_methods[m].slot;
    }
    switch (slot) {
    case 1: em_WsNumber(ws, 0, v->param, 3, 0, 1); break;
    case 2: em_WsItem(ws, 1, v->param); break;
    case 3: em_WsMove(ws, 2, v->param); break;
    case 4: em_WsSpecies(ws, 3, v->param); break;
    case 5: em_WsMsg(ws, 4, BANK_PLACES, m == 25 ? EM_PLACE_25 : m == 26 ? EM_PLACE_26 : EM_PLACE_27); break;
    }
    return ws;
}

static void *em_method_ws(void *app, u32 e, u32 *text)
{
    return em_method_ws_heap(APP_HEAP(app), e, text);
}

/* --- data ---------------------------------------------------------------------------------------------------------- */

static s32 em_prevo(u32 sp)
{
    u32 s, i;
    for (s = 1; s < EM_NSPECIES; s++)
        for (i = em_evo_first[s]; i < em_evo_first[s + 1]; i++)
            if (em_evo[i].target == sp)
                return s;
    return -1;
}

static void em_fam_add(u32 species, u32 depth, u32 cont, s32 evo)
{
    EmFam *f;
    if (em_dbg.nfam >= MAX_FAM) {
        em_dbg.overflow++;
        return;
    }
    f = &em_fam[em_dbg.nfam];
    f->species = species;
    f->depth = depth;
    f->cont = cont;
    f->evo = evo;
    em_dbg.fam[em_dbg.nfam] = cont ? 0x8000 | evo : species;
    em_dbg.nfam++;
}

/* the species' evolutions below `sp` (depth first, methods to the same species as continuation rows) */
static void em_fam_walk(u32 sp, u32 depth)
{
    u32 i, j;
    if (depth > 4)
        return;
    for (i = em_evo_first[sp]; i < em_evo_first[sp + 1]; i++) {
        u32 t = em_evo[i].target, dup = 0;
        for (j = em_evo_first[sp]; j < i; j++)
            if (em_evo[j].target == t)
                dup = 1;
        if (dup)
            continue;
        em_fam_add(t, depth + 1, 0, i);
        for (j = i + 1; j < em_evo_first[sp + 1]; j++)
            if (em_evo[j].target == t)
                em_fam_add(t, depth + 1, 1, j);
        if (t != sp)
            em_fam_walk(t, depth + 1);
    }
}

void em_family(u32 species)
{
    u32 root = species, k;
    s32 p;
    em_dbg.nfam = 0;
    em_dbg.overflow = 0;
    if (!species || species >= EM_NSPECIES)
        return;
    for (k = 0; k < 6 && (p = em_prevo(root)) > 0; k++)
        root = p;
    em_fam_add(root, 0, 0, -1);
    em_fam_walk(root, 0);
}

void em_learnset(u32 species, u32 form)
{
    u32 i, n = 0;
    em_learn_raw[0] = 0xFFFF;
    em_learn_raw[1] = 0xFFFF;
    if (species && species < EM_NSPECIES)
        em_LearnLoad(species, form, em_learn_raw);
    for (i = 0; i + 1 < 0x80 && n < MAX_LEARN; i += 2) {
        if (em_learn_raw[i] == 0xFFFF && em_learn_raw[i + 1] == 0xFFFF)
            break;
        em_learn[2 * n] = em_learn_raw[i];
        em_learn[2 * n + 1] = em_learn_raw[i + 1];
        em_dbg.learn_mv[n] = em_learn_raw[i];
        em_dbg.learn_lv[n] = em_learn_raw[i + 1];
        n++;
    }
    em_dbg.nlearn = n;
    em_dbg.next = 0xFF;
    for (i = 0; i < n; i++)
        if (em_learn[2 * i + 1] > em_dbg.level) {
            em_dbg.next = i;
            break;
        }
}

static u32 em_knows(u32 move)
{
    u32 i;
    for (i = 0; i < 4; i++)
        if (em_moves[i] == move)
            return 1;
    return 0;
}

/* --- drawing ------------------------------------------------------------------------------------------------------- */

static void em_draw_evo(void *app)
{
    u32 r, line = 0;
    em_BmpFill(em_WinBmp(em_win[W_EVO]), 0);
    for (r = 0; r < em_dbg.nfam && line < EVO_ROWS; r++) {
        EmFam *f = &em_fam[r];
        s32 right = (line == 0 ? 216 : EVO_RIGHT) - 8;              /* the memo panel's cut corner */
        u32 name_end = EVO_X0, mw, text;
        void *ws, *str;
        if (!f->cont) {
            ws = em_WsCreate(APP_HEAP(app));
            em_WsSpecies(ws, 3, f->species);
            str = em_fmt(app, ws, f->depth ? TXT_EVO_CHILD : TXT_EVO_ROOT);
            name_end = EVO_X0 + (f->depth > 1 ? (f->depth - 1) * EVO_INDENT : 0);
            name_end += em_put(app, W_EVO, str, name_end, line * 16 + 3,
                               f->species == em_dbg.species ? C_BLUE : C_TEXT, 0);
            em_WsFree(ws);
        }
        if (f->evo < 0) {
            if (em_dbg.nfam == 1) {         /* no family: "Does not evolve" */
                str = em_fmt(app, 0, TXT_EVO_NONE);
                em_put(app, W_EVO, str, right, line * 16 + 3, C_TEXT, 1);
            }
            line++;
            continue;
        }
        ws = em_method_ws(app, f->evo, &text);
        str = em_fmt(app, ws, text);
        mw = em_StrWidth(str, APP_FONT(app), 0);
        if (!f->cont && (s32)(name_end + 8 + mw) > right) {
            line++;                         /* the method on its own line */
            if (line >= EVO_ROWS) {
                em_StrBufFree(str);
                em_WsFree(ws);
                em_dbg.overflow++;
                break;
            }
            right = EVO_RIGHT - 8;
        }
        em_put(app, W_EVO, str, right, line * 16 + 3, C_TEXT, 1);
        em_WsFree(ws);
        line++;
    }
    if (r < em_dbg.nfam)
        em_dbg.overflow += em_dbg.nfam - r;
    em_dbg.lines = line;
}

static void em_draw_list(void *app)
{
    void *bmp = em_WinBmp(em_win[W_LIST]);
    u32 k;
    em_BmpFill(bmp, 0);
    if (!em_dbg.nlearn) {
        em_put(app, W_LIST, em_fmt(app, 0, TXT_EVO_LIST_NONE), LIST_MOVE_X - 4, 1, C_TEXT, 0);
    }
    for (k = 0; k < LIST_ROWS && em_dbg.scroll + k < em_dbg.nlearn; k++) {
        u32 i = em_dbg.scroll + k, mv = em_learn[2 * i], color;
        void *ws = em_WsCreate(APP_HEAP(app));
        if (em_dbg.listmode && i == em_dbg.cursor)
            em_BmpFillArea(bmp, LIST_MOVE_X - 3, k * 16 + 1, 152 - (LIST_MOVE_X - 3) - 1, 15, C_CURSOR_BG);
        em_WsNumber(ws, 0, em_learn[2 * i + 1], 3, 0, 1);
        em_put(app, W_LIST, em_fmt(app, ws, TXT_EVO_LIST_LV), LIST_LV_R, k * 16 + 2, C_WHITE, 1);
        em_WsMove(ws, 2, mv);
        color = em_knows(mv) ? C_BLUE : i == em_dbg.next ? C_RED : C_TEXT;
        em_put(app, W_LIST, em_fmt(app, ws, TXT_EVO_MOVENAME), LIST_MOVE_X, k * 16 + 2, color, 0);
        em_WsFree(ws);
    }
}

static void em_draw_pos(void *app)
{
    void *ws;
    u32 last = em_dbg.scroll + LIST_ROWS;
    em_BmpFill(em_WinBmp(em_win[W_POS]), 0);
    if (em_dbg.nlearn <= LIST_ROWS)
        return;
    if (last > em_dbg.nlearn)
        last = em_dbg.nlearn;
    ws = em_WsCreate(APP_HEAP(app));
    em_WsNumber(ws, 0, em_dbg.scroll + 1, 2, 0, 1);
    em_WsNumber(ws, 1, last, 2, 0, 1);
    em_WsNumber(ws, 2, em_dbg.nlearn, 2, 0, 1);
    em_put(app, W_POS, em_fmt(app, ws, TXT_EVO_LIST_POS), 68, 0, C_TEXT, 2);
    em_WsFree(ws);
    if (em_dbg.scroll > 0)
        em_put(app, W_POS, em_fmt(app, 0, TXT_EVO_UP), 2, 0, C_TEXT, 0);
    if (em_dbg.scroll + LIST_ROWS < em_dbg.nlearn)
        em_put(app, W_POS, em_fmt(app, 0, TXT_EVO_DOWN), 134, 0, C_TEXT, 1);
}

/* --- resources ----------------------------------------------------------------------------------------------------- */

static void em_load(void *app)
{
    if (!em_buf_label)
        em_buf_label = em_ReadNSCR(SUMMARY_ARC, EM_FILE_LABEL, 0, (void **)&em_scr_label, APP_HEAP(app));
    if (!em_buf_panel)
        em_buf_panel = em_ReadNSCR(SUMMARY_ARC, EM_FILE_PANEL, 0, (void **)&em_scr_panel, APP_HEAP(app));
}

static void em_free_windows(void)
{
    u32 w;
    for (w = 0; w < W_N; w++)
        if (em_win[w]) {
            em_WinFree(em_win[w]);
            em_win[w] = 0;
        }
}

static void em_reset(void)
{
    u32 w;
    for (w = 0; w < W_N; w++)
        em_win[w] = 0;
    em_buf_label = em_buf_panel = 0;
    em_desc = 0;
    em_scr_label = em_scr_panel = 0;
    em_dbg.on = em_dbg.shown = em_dbg.listmode = em_dbg.pending = 0;
}

/* --- page 4 steps -------------------------------------------------------------------------------------------------- */

static void em_page_create(void *app)
{
    void *pp = em_CurPP(app);
    u32 w, i, known = 0;
    em_load(app);
    em_free_windows();
    for (w = 0; w < W_N; w++)
        em_win[w] = em_WinCreate(win_geo[w][0], win_geo[w][1], win_geo[w][2], win_geo[w][3], win_geo[w][4], 0xE, 1);
    em_dbg.species = PokeParty_GetParam(pp, P_SPECIES, 0);
    em_dbg.form = PokeParty_GetParam(pp, P_FORM, 0);
    em_dbg.level = PokeParty_GetParam(pp, P_LEVEL, 0);
    for (i = 0; i < 4; i++)
        em_moves[i] = PokeParty_GetParam(pp, P_MOVE1 + i, 0);
    em_family(em_dbg.species);
    em_learnset(em_dbg.species, em_dbg.form);
    for (i = 0; i < em_dbg.nlearn; i++)
        known += em_knows(em_learn[2 * i]);
    em_dbg.known = known;
    em_dbg.listmode = 0;
    /* start with the next move to learn on the list's second row */
    em_dbg.scroll = 0;
    if (em_dbg.next != 0xFF && em_dbg.next > 1)
        em_dbg.scroll = em_dbg.next - 1;
    if (em_dbg.nlearn > LIST_ROWS && em_dbg.scroll > em_dbg.nlearn - LIST_ROWS)
        em_dbg.scroll = em_dbg.nlearn - LIST_ROWS;
    if (em_dbg.nlearn <= LIST_ROWS)
        em_dbg.scroll = 0;
    em_dbg.cursor = em_dbg.scroll;
    em_draw_evo(app);
    em_draw_list(app);
    em_draw_pos(app);
    em_dbg.on = 1;
    em_dbg.creates++;
}

static void em_page_hide(void *app)
{
    if (em_desc) {
        em_MsgFree(em_desc);
        em_desc = 0;
    }
    em_free_windows();
    em_dbg.on = 0;
    em_dbg.shown = 0;
    em_dbg.listmode = 0;
    em_dbg.pending = 0;
    em_dbg.hides++;
}

static void em_page_finold(void *app)
{
    em_BgFillArea(1, 0, 0, 0, 0x13, 0x15, 0x10);
    em_BgQueue(1);
    em_BgFill(4, 0);
    em_BgQueue(4);
    em_dbg.finolds++;
}

static void em_page_finnew(void *app)
{
    u32 w;
    u8 *memo = P0_MEMO_SCR(APP_P0(app));
    if (em_scr_panel) {
        em_BgScrArea(2, 0, 0, 32, 24, em_scr_panel + 0xC, 0, 0, 32, 32);
        em_BgQueue(2);
    }
    if (memo) {
        em_BgBufScr(6, memo + 0xC, *(u32 *)(memo + 8));
        em_BgQueue(6);
    }
    if (em_scr_label) {
        em_BgScrArea(5, 0, 0, 32, 3, em_scr_label + 0xC, 0, 0, 32, 32);
        em_BgQueue(5);
    }
    for (w = 0; w < W_N; w++)
        if (em_win[w]) {
            em_WinFlushChar(em_win[w]);
            em_WinFlushMap(em_win[w]);
            em_BgLoadScr(em_WinFrame(em_win[w]));
        }
    em_dbg.shown = 1;
    em_dbg.finnews++;
}

static void em_page_update(void *app)
{
    if (em_dbg.pending && em_win[W_LIST] && !em_QueBmpBusy(APP_QUE(app), em_WinBmp(em_win[W_LIST])) &&
        !em_QueBmpBusy(APP_QUE(app), em_WinBmp(em_win[W_POS])) &&
        !em_QueBmpBusy(APP_QUE(app), em_WinBmp(em_win[W_EVO]))) {
        em_WinFlushChar(em_win[W_LIST]);
        em_WinFlushChar(em_win[W_POS]);
        em_WinFlushChar(em_win[W_EVO]);
        em_dbg.pending = 0;
        em_dbg.flushes++;
    }
}

/* list mode: the top shows the move under the cursor (as the STATS page's move details): name, type, category, PP,
 * power, accuracy, description (system bank 402) */
static void em_draw_detail(void *app)
{
    void *ws, *str;
    u32 mv = em_learn[2 * em_dbg.cursor], v, cat;
    em_BmpFill(em_WinBmp(em_win[W_EVO]), 0);
    ws = em_WsCreate(APP_HEAP(app));
    em_WsMove(ws, 2, mv);
    em_put(app, W_EVO, em_fmt(app, ws, TXT_EVO_MOVENAME), EVO_X0, 3, C_BLUE, 0);
    if (em_MoveParam(mv, 0) < 17) {
        em_WsMsg(ws, 4, BANK_TYPES, em_MoveParam(mv, 0));
        em_put(app, W_EVO, em_fmt(app, ws, TXT_EVO_DEX_TYPE), 216 - 8, 3, C_TEXT, 1);
    } else {                                        /* Redux's Fairy (17) has no name in bank 398 */
        em_put(app, W_EVO, em_fmt(app, 0, TXT_EVO_TYPE_FAIRY), 216 - 8, 3, C_TEXT, 1);
    }
    cat = em_MoveParam(mv, 2);
    em_put(app, W_EVO, em_fmt(app, 0, TXT_EVO_DET_CAT), EVO_X0, 16 + 3, C_TEXT, 0);
    em_put(app, W_EVO, em_fmt(app, 0, cat == 1 ? TXT_EVO_CAT_PHYS : cat == 2 ? TXT_EVO_CAT_SPEC : TXT_EVO_CAT_STATUS),
           DET_VAL_X, 16 + 3, C_TEXT, 0);
    em_put(app, W_EVO, em_fmt(app, 0, TXT_EVO_DET_PP), DET_COL2_X, 16 + 3, C_TEXT, 0);
    em_WsNumber(ws, 0, em_MoveParam(mv, 5), 3, 0, 1);
    em_put(app, W_EVO, em_fmt(app, ws, TXT_EVO_DEX_NUM), DET_RIGHT, 16 + 3, C_TEXT, 1);
    em_put(app, W_EVO, em_fmt(app, 0, TXT_EVO_DET_POW), EVO_X0, 32 + 3, C_TEXT, 0);
    v = em_MoveParam(mv, 3);
    if (v > 1) {
        em_WsNumber(ws, 0, v, 3, 0, 1);
        em_put(app, W_EVO, em_fmt(app, ws, TXT_EVO_DEX_NUM), DET_VAL_X, 32 + 3, C_TEXT, 0);
    } else {
        em_put(app, W_EVO, em_fmt(app, 0, TXT_EVO_DEX_DASH), DET_VAL_X, 32 + 3, C_TEXT, 0);
    }
    em_put(app, W_EVO, em_fmt(app, 0, TXT_EVO_DET_ACC), DET_COL2_X, 32 + 3, C_TEXT, 0);
    v = em_MoveParam(mv, 4);
    if (v && !em_MoveNeverMiss(mv)) {
        em_WsNumber(ws, 0, v, 3, 0, 1);
        em_put(app, W_EVO, em_fmt(app, ws, TXT_EVO_DEX_NUM), DET_RIGHT, 32 + 3, C_TEXT, 1);
    } else {
        em_put(app, W_EVO, em_fmt(app, 0, TXT_EVO_DEX_DASH), DET_RIGHT, 32 + 3, C_TEXT, 1);
    }
    em_WsFree(ws);
    if (!em_desc)
        em_desc = em_MsgNew(0, 2, BANK_MOVE_DESC, APP_HEAP(app));
    str = em_MsgLoad(em_desc, mv);
    em_put(app, W_EVO, str, EVO_X0, 48 + 3, C_TEXT, 0);
}

static void em_redraw_list(void *app)
{
    em_draw_list(app);
    em_draw_pos(app);
    if (em_dbg.listmode)
        em_draw_detail(app);
    else
        em_draw_evo(app);
    em_dbg.pending = 1;
}

/* --- dispatchers (the app's page jump tables) ---------------------------------------------------------------------- */

void em_hide(void *app)
{
    switch (APP_SHOWN(app)) {
    case 0: em_P0Hide(app, APP_P0(app)); break;
    case 1: em_P1Hide(app, APP_P1(app)); break;
    case 2: em_P2Hide(app, APP_P2(app)); break;
    case 3: em_P3Hide(app, APP_P1(app)); break;
    case EM_PAGE: em_page_hide(app); break;
    }
}

void em_create(void *app)
{
    switch (APP_PAGE(app)) {
    case 0: em_P0Create(app, APP_P0(app)); break;
    case 1: em_P1Create(app, APP_P1(app)); break;
    case 2: em_P2Create(app, APP_P2(app)); break;
    case 3: em_P3Create(app, APP_P1(app)); break;
    case EM_PAGE: em_page_create(app); break;
    }
}

void em_finold(void *app)
{
    switch (APP_SHOWN(app)) {
    case 0: em_P0FinOld(app, APP_P0(app)); break;
    case 1: em_P1FinOld(app, APP_P1(app)); break;
    case 2: em_P2FinOld(app, APP_P2(app)); break;
    case 3: em_P3FinOld(app, APP_P1(app)); break;
    case EM_PAGE: em_page_finold(app); break;
    }
}

void em_finnew(void *app)
{
    switch (APP_PAGE(app)) {
    case 0: em_P0FinNew(app, APP_P0(app)); break;
    case 1: em_P1FinNew(app, APP_P1(app)); break;
    case 2: em_P2FinNew(app, APP_P2(app)); break;
    case 3: em_P3FinNew(app, APP_P1(app)); break;
    case EM_PAGE: em_page_finnew(app); break;
    }
}

void em_update(void *app)
{
    switch (APP_SHOWN(app)) {
    case 0: break;                                  /* FUN_021B696C: bx lr */
    case 1: case 3: em_P1Update(app, APP_P1(app)); break;
    case 2: em_P2Update(app, APP_P2(app)); break;
    case EM_PAGE: em_page_update(app); break;
    }
}

/* --- input --------------------------------------------------------------------------------------------------------- */

static void em_go(void *app, u32 page)
{
    APP_PAGE(app) = page;
    em_PageRedraw(app);
    GFL_SndSEPlay(SE_PAGE);
    APP_KEYMODE(app) = 0;
}

static u32 em_last_page(void *app)
{
    return APP_RIBBONS(app) ? 2 : 1;
}

/* scroll so that learnset row i is visible */
static void em_show_row(u32 i)
{
    if (i < em_dbg.scroll)
        em_dbg.scroll = i;
    else if (i >= em_dbg.scroll + LIST_ROWS)
        em_dbg.scroll = i - LIST_ROWS + 1;
}

static u32 em_scroll_by(void *app, s32 d)
{
    s32 s = (s32)em_dbg.scroll + d, max = (s32)em_dbg.nlearn - LIST_ROWS;
    if (max < 0)
        max = 0;
    if (s < 0)
        s = 0;
    if (s > max)
        s = max;
    if ((u32)s == em_dbg.scroll)
        return 0;
    em_dbg.scroll = s;
    em_dbg.scrolls++;
    em_redraw_list(app);
    GFL_SndSEPlay(SE_CURSOR);
    return 1;
}

static u32 em_keys(void *app)
{
    u32 rep = em_KeyRep(), trg = em_KeyTrg(), tx, ty;
    if (APP_PAGE(app) != EM_PAGE) {
        if ((rep & PAD_RIGHT) && APP_PAGE(app) == em_last_page(app) && APP_PAGE(app) == APP_SHOWN(app) &&
            !APP_EGG(app) && PARAM_MODE(APP_PARAM(app)) != 2) {
            em_dbg.rights++;
            em_go(app, EM_PAGE);
            return 1;
        }
        return 0;
    }
    if (!em_dbg.shown)
        return 0;
    if (em_dbg.listmode) {
        if (trg & (PAD_A | PAD_B)) {
            em_dbg.listmode = 0;
            em_redraw_list(app);
            GFL_SndSEPlay(SE_LEAVE);
        } else if (rep & (PAD_UP | PAD_DOWN)) {
            u32 c = em_dbg.cursor;
            if ((rep & PAD_UP) && c > 0)
                c--;
            if ((rep & PAD_DOWN) && c + 1 < em_dbg.nlearn)
                c++;
            if (c != em_dbg.cursor) {
                em_dbg.cursor = c;
                em_show_row(c);
                em_redraw_list(app);
                GFL_SndSEPlay(SE_CURSOR);
            }
        } else if (em_TouchTrg(&tx, &ty) && tx < 152 && ty >= 8 && ty < 136) {
            u32 i = em_dbg.scroll + (ty - 8) / 16;
            if (i < em_dbg.nlearn && i != em_dbg.cursor) {
                em_dbg.cursor = i;
                em_redraw_list(app);
                GFL_SndSEPlay(SE_CURSOR);
            }
        }
        return 1;                           /* the list has the keys (B leaves it) */
    }
    if (rep & PAD_LEFT) {
        em_go(app, em_last_page(app));
        return 1;
    }
    if (rep & PAD_RIGHT)
        return 1;
    if (rep & (PAD_L | PAD_R)) {
        em_scroll_by(app, (rep & PAD_L) ? -LIST_ROWS : LIST_ROWS);
        return 1;
    }
    if ((trg & PAD_A) && em_dbg.nlearn) {
        em_dbg.listmode = 1;
        em_dbg.cursor = em_dbg.next != 0xFF ? em_dbg.next : em_dbg.scroll;
        em_show_row(em_dbg.cursor);
        em_dbg.enters++;
        em_redraw_list(app);
        GFL_SndSEPlay(SE_ENTER);
        return 1;
    }
    if (em_TouchTrg(&tx, &ty)) {
        if (ty >= 136 && ty < 152 && tx >= 16 && tx < 152)     /* the white box: its arrows */
            return em_scroll_by(app, tx < 84 ? -LIST_ROWS : LIST_ROWS) | 1;
        if (tx < 152 && ty >= 8 && ty < 136) {                  /* a row: the cursor there */
            u32 i = em_dbg.scroll + (ty - 8) / 16;
            if (i < em_dbg.nlearn) {
                em_dbg.listmode = 1;
                em_dbg.cursor = i;
                em_dbg.enters++;
                em_redraw_list(app);
                GFL_SndSEPlay(SE_ENTER);
                return 1;
            }
        }
    }
    return 0;
}

/* main step: bl em_Input (the app's input step: keys, then the touch buttons; only while input is on and the print
 * queue is idle) */
void em_input(void *app)
{
    if (APP_INPUT(app) == 1 && em_QueIdle(APP_QUE(app)) == 1 && em_keys(app))
        return;
    em_Input(app);
}

/* app init: bl em_InitBG */
void em_init(void *app)
{
    em_reset();
    em_dbg.inits++;
    em_InitBG(app);
}

/* app exit: bl em_ExitFirst */
void em_exit(void *app)
{
    if (em_desc)
        em_MsgFree(em_desc);
    em_desc = 0;
    em_free_windows();
    if (em_buf_label)
        em_HeapFree(em_buf_label);
    if (em_buf_panel)
        em_HeapFree(em_buf_panel);
    em_reset();
    em_dbg.exits++;
    em_ExitFirst(app);
}
