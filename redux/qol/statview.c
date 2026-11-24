/* ReRedux statview: IVs and EVs as two extra columns on the summary screen's stats page (statview.py lists the
 * hook sites and the graphics change).
 *
 * The summary app (overlay 207) draws the stats page in StatsDraw (0x021B8F10): for each of HP, Attack, Defense,
 * Sp. Atk, Sp. Def, Speed it reads the value with PokeParty_GetParam (0xA0-0xA6), registers it in a word set and
 * prints it right-aligned in that row's window ("cur / max" for HP); the stat names get the nature colours; then
 * the Ability box (label, name, description). statview.py widens the six row windows to the screen edge and
 * redraws the page's panel (full width, "IV" / "EV" column headers above it). Here the redirected print calls
 *   - print the HP row compact (cur right-aligned at 0x4D, "/" at 0x4F, max right-aligned at 0x69, the stats'
 *     column), and after each row's value its IV (right edge 0x8C) and EV (right edge 0xB2) in the same window,
 *     colour and font,
 *   - SELECT on the stats page toggles the Ability box between the ability and the totals: "Totals" on the tab,
 *     the IV total in the ability name's place, Hidden Power's type and the EV total with what's left of 510 in
 *     the description's place.
 * Values come from the game's own getter on the Pokémon the page shows (party, or the PC Pokémon the app
 * converted). The Ability box choice is kept while flipping through Pokémon and pages, reset when the app
 * starts. Eggs: no IVs / EVs, no toggle. Overlay 207 isn't used in battle, so nothing there changes. */
#include "qol.h"
#include "qol_texts.h"

/* ARM9 / OVL_207 (statview.py SYMS, followers/syms.ld) */
u32 PokeParty_GetParam(void *pp, u32 id, void *extra);
void GFL_SndSEPlay(u32 se);
u32 sv_KeyTrg(void);
u32 sv_KeyMode(u32 a, u32 b, u32 c, u32 d);
void *sv_WsCreate(u32 heap);
void sv_WsFree(void *ws);
void sv_WsNumber(void *ws, u32 idx, u32 value, u32 digits, u32 style, u32 code);
void sv_WsBankWord(void *ws, u32 idx, u32 bank, u32 id);
void sv_PrintQue(void *que, void *bmp, u32 x, u32 y, void *str, void *font, u32 color);
void *sv_CurPP(void *app);
void sv_StatsDraw(void *app, void *page);
u32 sv_Keys(void *app);
void sv_PageRedraw(void *app);
void sv_PrintMsg(void *app, void *win, u32 msg, u32 x, u32 y, u32 color);
void sv_PrintWsRight(void *app, void *win, void *ws, u32 msg, u32 x, u32 y, u32 color);
void *sv_StrBufCreate(u32 len, u32 heap);
void sv_StrBufFree(void *str);
void *sv_MsgLoad(void *msgdata, u32 id);
void sv_WsFormat(void *ws, void *dst, void *src);

#define PAD_SELECT      0x0004
#define PARAM_EV_HP     0x0D        /* HP, Atk, Def, Spe, SpA, SpD */
#define PARAM_IV_HP     0x46
#define PARAM_EGG       0x4C
#define TYPE_NAMES_BANK 398
#define SE_PAGE         0x665       /* the summary's page-change sound */
#define APP_HEAP(app)   (*(u16 *)(app))
#define APP_MSG(app)    (*(void **)((u8 *)(app) + 0x7C))     /* bank 179 */
#define APP_FONT(app)   (*(void **)((u8 *)(app) + 0x80))
#define APP_QUE(app)    (*(void **)((u8 *)(app) + 0x84))
#define APP_PAGE(app)   (*(u32 *)((u8 *)(app) + 0x58))
#define APP_KEYMODE(app) (*(u8 *)((u8 *)(app) + 0x1C))
#define PAGE_STATS      1
#define MSG_VAL_ATK     0x78        /* the rows' number lines: Attack, Defense, Sp. Atk, Sp. Def, Speed */
/* window x (the row windows start at screen x 64) */
#define X_HP_CUR        0x4D        /* right edge of the current HP */
#define X_HP_SLASH      0x4F
#define X_STAT          0x69        /* right edge of the stats (and of the max HP) */
#define X_IV            0x8C        /* right edge of the IV column (header "IV" in the panel above) */
#define X_EV            0xB2        /* right edge of the EV column */

enum { SV_ABILITY, SV_TOTALS, SV_MODES };

typedef struct {
    u32 magic;          /* 'STVW' */
    u8 mode;            /* Ability box: ability / totals (kept while the app runs) */
    u8 cur;             /* 1 while a non-egg stats page is drawn (IV / EV columns on) */
    u8 hp_type;         /* Hidden Power type of the last drawn page (1 Fighting .. 16 Dark) */
    u8 rows;            /* IV / EV rows printed on the last drawn page (6) */
    u8 ivs[6];          /* last drawn page, summary row order HP, Atk, Def, SpA, SpD, Spe */
    u16 evs[6];
    u16 iv_total, ev_total;
    u16 draws, toggles, inits;
} SvDbg;
SvDbg sv_dbg = { 0x57565453 };

static void *sv_app;
static u8 sv_cur_mode;  /* the Ability box mode of the page being drawn */

/* summary row (HP, Atk, Def, SpA, SpD, Spe) -> IV / EV param index (HP, Atk, Def, Spe, SpA, SpD) */
static const u8 param_of_row[6] = { 0, 1, 2, 4, 5, 3 };

static u32 sv_iv(void *pp, u32 i)
{
    return PokeParty_GetParam(pp, PARAM_IV_HP + i, 0);
}

static u32 sv_ev(void *pp, u32 i)
{
    return PokeParty_GetParam(pp, PARAM_EV_HP + i, 0);
}

static u32 sv_iv_total(void *pp)
{
    u32 i, t = 0;
    for (i = 0; i < 6; i++)
        t += sv_iv(pp, i);
    return t;
}

static u32 sv_ev_total(void *pp)
{
    u32 i, t = 0;
    for (i = 0; i < 6; i++)
        t += sv_ev(pp, i);
    return t;
}

static u32 sv_hidden_power_type(void *pp)
{
    u32 i, bits = 0;
    for (i = 0; i < 6; i++)
        bits |= (sv_iv(pp, i) & 1) << i;
    return bits * 15 / 63 + 1;
}

/* app init (bl sv_KeyMode): new summary -> the ability */
u32 statview_init(u32 a, u32 b, u32 c, u32 d)
{
    sv_dbg.mode = SV_ABILITY;
    sv_dbg.inits++;
    return sv_KeyMode(a, b, c, d);
}

/* the app's key handler (bl sv_Keys): SELECT on the stats page toggles the Ability box */
u32 statview_keys(void *app)
{
    if (APP_PAGE(app) == PAGE_STATS && (sv_KeyTrg() & PAD_SELECT) &&
        !PokeParty_GetParam(sv_CurPP(app), PARAM_EGG, 0)) {
        sv_dbg.mode = (sv_dbg.mode + 1) % SV_MODES;
        sv_dbg.toggles++;
        sv_PageRedraw(app);
        GFL_SndSEPlay(SE_PAGE);
        APP_KEYMODE(app) = 0;
        return 1;
    }
    return sv_Keys(app);
}

/* stats page text (bl sv_StatsDraw in StatsPage_Draw) */
void statview_draw(void *app, void *page)
{
    void *pp = sv_CurPP(app);
    sv_app = app;
    sv_dbg.cur = APP_PAGE(app) == PAGE_STATS && !PokeParty_GetParam(pp, PARAM_EGG, 0);
    sv_cur_mode = sv_dbg.cur ? sv_dbg.mode : SV_ABILITY;
    if (sv_dbg.cur) {
        u32 r;
        for (r = 0; r < 6; r++) {
            sv_dbg.ivs[r] = sv_iv(pp, param_of_row[r]);
            sv_dbg.evs[r] = sv_ev(pp, param_of_row[r]);
        }
        sv_dbg.iv_total = sv_iv_total(pp);
        sv_dbg.ev_total = sv_ev_total(pp);
        sv_dbg.hp_type = sv_hidden_power_type(pp);
        sv_dbg.rows = 0;
        sv_dbg.draws++;
    }
    sv_StatsDraw(app, page);
    sv_dbg.cur = 0;
    sv_cur_mode = SV_ABILITY;
}

/* one number, right-aligned at x in the row's window (as StatsDraw prints the stats) */
static void sv_number(void *app, void *win, u32 msg, u32 value, u32 x, u32 y, u32 color)
{
    void *ws = sv_WsCreate(APP_HEAP(app));
    sv_WsNumber(ws, 0, value, 3, 1, 1);
    sv_PrintWsRight(app, win, ws, msg, x, y, color);
    sv_WsFree(ws);
}

/* after a row's stat: its IV and EV columns */
static void sv_columns(void *app, void *win, u32 msg, u32 row, u32 y, u32 color)
{
    if (!sv_dbg.cur)
        return;
    sv_number(app, win, msg, sv_dbg.ivs[row], X_IV, y, color);
    sv_number(app, win, msg, sv_dbg.evs[row], X_EV, y, color);
    sv_dbg.rows++;
}

/* HP row: current HP, "/", max HP (+ the HP IV / EV) */
void statview_hp_cur(void *app, void *win, void *ws, u32 msg, u32 x, u32 y, u32 color)
{
    sv_PrintWsRight(app, win, ws, msg, X_HP_CUR, y, color);
}

void statview_hp_slash(void *app, void *win, u32 msg, u32 x, u32 y, u32 color)
{
    sv_PrintMsg(app, win, msg, X_HP_SLASH, y, color);
}

void statview_hp_max(void *app, void *win, void *ws, u32 msg, u32 x, u32 y, u32 color)
{
    sv_PrintWsRight(app, win, ws, msg, X_STAT, y, color);
    sv_columns(app, win, msg, 0, y, color);
}

/* Attack .. Speed rows (msg 0x78-0x7C in summary row order) */
void statview_row(void *app, void *win, void *ws, u32 msg, u32 x, u32 y, u32 color)
{
    sv_PrintWsRight(app, win, ws, msg, x, y, color);
    if (msg >= MSG_VAL_ATK && msg < MSG_VAL_ATK + 5)
        sv_columns(app, win, msg, msg - MSG_VAL_ATK + 1, y, color);
}

/* Ability tab -> "Totals" */
void statview_label(void *app, void *win, u32 msg, u32 x, u32 y, u32 color)
{
    sv_PrintMsg(app, win, sv_cur_mode == SV_TOTALS ? TXT_SV_TOTALS : msg, x, y, color);
}

/* one of our bank-179 lines with the totals registered: 0 IV total, 1 Hidden Power type, 2 EV total, 3 EVs left */
static void sv_print_own(void *bmp, u32 msg, u32 x, u32 y, u32 color)
{
    void *app = sv_app;
    void *ws = sv_WsCreate(APP_HEAP(app));
    u32 ev = sv_dbg.ev_total;
    sv_WsNumber(ws, 0, sv_dbg.iv_total, 3, 0, 1);        /* left-aligned, no padding */
    sv_WsBankWord(ws, 1, TYPE_NAMES_BANK, sv_dbg.hp_type);
    sv_WsNumber(ws, 2, ev, 3, 0, 1);
    sv_WsNumber(ws, 3, ev < 510 ? 510 - ev : 0, 3, 0, 1);
    /* as the app's own word-set print (0x021B4F44), with room for two lines (it has 16 characters) */
    void *src = sv_MsgLoad(APP_MSG(app), msg), *dst = sv_StrBufCreate(96, APP_HEAP(app));
    sv_WsFormat(ws, dst, src);
    sv_PrintQue(APP_QUE(app), bmp, x, y, dst, APP_FONT(app), color);
    sv_StrBufFree(src);
    sv_StrBufFree(dst);
    sv_WsFree(ws);
}

/* Ability description (x 5, y 0x11) -> Hidden Power type, EV total and what's left of 510 */
void statview_desc(void *que, void *bmp, u32 x, u32 y, void *str, void *font, u32 color)
{
    if (sv_cur_mode == SV_TOTALS)
        sv_print_own(bmp, TXT_SV_TOTALS_DESC, x, y, color);
    else
        sv_PrintQue(que, bmp, x, y, str, font, color);
}

/* Ability name (x 0x41, y 1) -> the IV total */
void statview_name(void *que, void *bmp, u32 x, u32 y, void *str, void *font, u32 color)
{
    if (sv_cur_mode == SV_TOTALS)
        sv_print_own(bmp, TXT_SV_TOTALS_NAME, x, y, color);
    else
        sv_PrintQue(que, bmp, x, y, str, font, color);
}
