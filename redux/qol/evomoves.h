/* ReRedux evomoves: shared by evomoves.c (summary page) and dexmoves.c (Pokédex page): the family / learnset data
 * (evomoves.c) and the B2 text helpers both use. */
#ifndef EVOMOVES_H
#define EVOMOVES_H

#define MAX_LEARN   32
#define MAX_FAM     16

typedef struct {
    u16 species;
    u8 depth;
    u8 cont;            /* 1: another method for the row above's species (no name) */
    s16 evo;            /* em_evo index, -1 for the root */
} EmFam;

typedef struct {
    u32 magic;          /* 'EVMV' */
    u8 on;              /* page 4 created */
    u8 shown;           /* page 4 on screen (finnew done) */
    u8 listmode;        /* A pressed: cursor in the learnset */
    u8 cursor;
    u8 scroll;
    u8 nlearn;
    u8 next;            /* learnset index of the next move to learn (0xFF none) */
    u8 nfam;            /* family rows */
    u8 lines;           /* evo window lines used (wrapped methods take two) */
    u8 overflow;        /* family rows that didn't fit */
    u8 known;           /* learnset entries the Pokémon knows */
    u8 pending;         /* list window reprinted, char transfer waiting for the print queue */
    u16 species, form, level;
    u16 creates, finnews, hides, finolds, inits, exits, scrolls, enters, flushes, rights;
    u16 fam[MAX_FAM];   /* family rows: species (0x8000 | evo index for a continuation row) */
    u16 learn_lv[MAX_LEARN], learn_mv[MAX_LEARN];
} EmDbg;

extern EmDbg em_dbg;
extern EmFam em_fam[MAX_FAM];
extern u16 em_learn[MAX_LEARN * 2 + 2];    /* (move, level) pairs */

void em_family(u32 species);                /* -> em_fam, em_dbg.nfam / .fam / .overflow */
void em_learnset(u32 species, u32 form);    /* -> em_learn, em_dbg.nlearn / .next (by em_dbg.level) */
void *em_method_ws_heap(u32 heap, u32 e, u32 *text);   /* word set for evolution e's method line */

/* B2 (evomoves.py SYMS) */
void em_PrintQue(void *que, void *bmp, s32 x, s32 y, void *str, void *font, u32 color);
u32 em_QueIdle(void *que);
u32 em_QueBmpBusy(void *que, void *bmp);
u32 em_StrWidth(void *str, void *font, u32 spacing);
void *em_WsCreate(u32 heap);
void em_WsFree(void *ws);
void em_WsMsg(void *ws, u32 idx, u32 bank, u32 line);
void em_WsSpecies(void *ws, u32 idx, u32 species);
void em_WsMove(void *ws, u32 idx, u32 move);
void em_WsItem(void *ws, u32 idx, u32 item);
void em_WsNumber(void *ws, u32 idx, u32 value, u32 digits, u32 style, u32 code);
void em_WsFormat(void *ws, void *dst, void *src);
void *em_StrBufCreate(u32 len, u32 heap);
void em_StrBufFree(void *str);
void *em_MsgLoad(void *msgdata, u32 id);
void em_BmpFill(void *bmp, u32 color);
void em_BmpFillArea(void *bmp, u32 x, u32 y, u32 w, u32 h, u32 color);
void em_BgLoadScr(u32 frame);
void em_BgQueue(u32 frame);
void em_BgScrArea(u32 frame, u32 x, u32 y, u32 w, u32 h, void *data, u32 sx, u32 sy, u32 sw, u32 sh);
void em_BgFill(u32 frame, u32 val);
void em_HeapFree(void *p);
u32 em_KeyTrg(void);
u32 em_KeyRep(void);
u32 em_TouchTrg(u32 *x, u32 *y);
void GFL_SndSEPlay(u32 se);

#define COL(l, s, b)    (((l) << 10) | ((s) << 5) | (b))

#endif
