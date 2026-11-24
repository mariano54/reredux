/* ReRedux debug FPS counter (fpscounter.py; --with fpscounter only, never in the release ROMs).
 *
 * Top-left corner of the top screen (main engine), refreshed every 60 VBlanks: "P U flags"
 *   P      3D swap requests per 60 emulated VBlanks: GFL_G3DSysCheckSwapBuffers calls that found a request
 *          (each one is a new 3D picture shown from the next VBlank on). 60 = a picture every frame (fps60),
 *          30 = vanilla's rhythm (fallback, standing still with nothing moving).
 *   U      field logic updates per second: FieldRoutine_Run calls (fps60_run_render, from fps60_dbg's counters;
 *          30 normally, 0 outside the field).
 *   flags  F fps60's fallback (vanilla drawing because real pictures don't fit) is on, T R turbo is on,
 *          L in-between pictures were left out this second for lack of time, S left out because nothing moved.
 *
 * This is NOT a host presentation counter: an emulator can skip rendering or repeat a displayed picture
 * while this still reads 60. It also cannot measure host frame pacing or controller/display latency.
 * U = 30 is the intended logic rate, not a rendering failure. A slow host stretches the 60-VBlank window
 * beyond one wall-clock second. Check the emulator and recorded output as well (tests/perf/presentation.py).
 *
 * Drawing: up to 10 16x16 OBJs (a 4x6 font at 2x), the last OAM entries (118..127, priority 0, palette 15),
 * written right after the main loop's VBlank wait, after the game's own VBlank work (its OAM transfer) -- so
 * every frame they are put back over whatever the game wrote there. The glyphs (4bpp, white + a black outline:
 * OBJ palette 15 colours 14 / 15; 2 KiB for all 16) live at the top of bank E (64 KiB main OBJ VRAM, 1D
 * mapping), the shown ones rewritten every VBlank: the field leaves that end free; a scene that uses it gets
 * some of it overwritten (debug build). Shown only while bank E is the main OBJ VRAM and OBJs are on in 1D
 * mapping (the field, most menus); elsewhere nothing is touched. Cost: ~200 stores per VBlank. */
#include "qol.h"

u32 GFL_G3DSysCheckSwapBuffers(void);
void FPSC_MainVBlank(void);

#define VBLANK_COUNT    (*(volatile u32 *)0x027FFC3C)
#define G3D_SYS         (*(u8 **)0x02141924)        /* GFL G3DSystem: +0x94 ReqSwapBuffers */
#define DISPCNT_A       (*(volatile u32 *)0x04000000)
#define VRAMCNT_E       (*(volatile u8 *)0x04000244)
#define OBJ_VRAM        0x06400000u
#define OBJ_PAL15       ((volatile u16 *)(0x05000200 + 15 * 32))
#define OAM             ((volatile u16 *)0x07000000)
#define RAM_OK(p)       ((u32)(p) - 0x02000000u < 0x400000u)

#define NG      16          /* glyphs: 0-9 F T L S */
#define NSPR    10
#define OAM0    (128 - NSPR)
#define G_F     10
#define G_T     11
#define G_L     12
#define G_S     13
#define WIN     60          /* VBlanks per reading */

/* fps60_dbg / turbo_dbg fields read by offset (fps60.c's layout, perf.py's F60 table) */
extern u8 fps60_dbg[] __attribute__((weak));
extern u8 turbo_dbg[] __attribute__((weak));
#define F60_U32(o)      (*(u32 *)(fps60_dbg + (o)))

/* 4x6 glyphs, a row per nibble (bit 3 = left), first row in the low nibble */
static const u32 font[NG] = {
    0x699996, 0x722262, 0xF84296, 0xE1161E, 0x22FA62, 0xE11E8F, 0x699E86, 0x44421F,
    0x699696, 0x617996, 0x888E8F, 0x44444E, 0xF88888, 0xE11687, 0, 0,
};

typedef struct {
    u32 swaps;          /* this window: swap requests issued */
    u32 vbl0;           /* VBlank count at the window's start */
    u32 upd0, late0, still0;    /* fps60 counters at the window's start */
    u8 pics, upd, flags, ready; /* the last reading (flags: 1 F, 2 T, 4 L, 8 S) */
    u8 glyph[NSPR];     /* what is shown (0xFF = nothing) */
    u8 inited, shown, off, pad;
    u32 readings;
} FpscDbg;

FpscDbg fpsc_dbg;
static u32 tiles[NG][32];  /* 16x16 4bpp: 128 bytes a glyph */

static u32 f60_updates(void)
{
    /* every fps60_run_render call ends in one of these counters: van_frames, mid_frames, mid_late, mid_skipped,
     * mid_evstart */
    return F60_U32(20) + F60_U32(12) + F60_U32(200) + F60_U32(140) + F60_U32(188);
}

/* the 4x6 font at 2x (8x12 white, cols 1..8, rows 1..12) + a 1-pixel black outline, in a 16x16 OBJ: 4 tiles in
 * 1D order (top-left, top-right, bottom-left, bottom-right), 8 rows of 8 nibbles each */
static void make_tiles(void)
{
    static u8 on[16][16];
    int g, x, y;
    for (g = 0; g < NG; g++) {
        for (y = 0; y < 16; y++)
            for (x = 0; x < 16; x++)
                on[y][x] = 0;
        for (y = 0; y < 12; y++)
            for (x = 0; x < 8; x++)
                if (font[g] >> (4 * (y >> 1)) & (8 >> (x >> 1)))
                    on[y + 1][x + 1] = 1;
        for (y = 0; y < 16; y++)
            for (x = 0; x < 16; x++) {
                u32 c = 0;
                if (on[y][x])
                    c = 15;
                else {
                    int dy, dx;
                    for (dy = -1; dy <= 1; dy++)
                        for (dx = -1; dx <= 1; dx++) {
                            int yy = y + dy, xx = x + dx;
                            if (yy >= 0 && yy < 16 && xx >= 0 && xx < 16 && on[yy][xx])
                                c = 14;
                        }
                }
                tiles[g][((y >> 3) * 2 + (x >> 3)) * 8 + (y & 7)] |= c << (4 * (x & 7));
            }
    }
}

static int put_num(u8 *out, int n, u32 v)
{
    u32 t = 0;
    if (v > 99)
        v = 99;
    while (v >= 10) {
        v -= 10;
        t++;
    }
    if (t)
        out[n++] = (u8)t;
    out[n++] = (u8)v;
    return n;
}

static void latch(FpscDbg *d, u32 vbl)
{
    u8 fl = 0;
    int n = 0, i;
    d->pics = (u8)(d->swaps > 255 ? 255 : d->swaps);
    d->swaps = 0;
    d->vbl0 = vbl;
    if (fps60_dbg) {
        u32 u = f60_updates(), late = F60_U32(200), still = F60_U32(140);
        d->upd = (u8)(u - d->upd0 > 255 ? 255 : u - d->upd0);
        if (*(u16 *)(fps60_dbg + 88))
            fl |= 1;
        if (late != d->late0)
            fl |= 4;
        if (still != d->still0)
            fl |= 8;
        d->upd0 = u;
        d->late0 = late;
        d->still0 = still;
    }
    if (turbo_dbg && turbo_dbg[0])
        fl |= 2;
    d->flags = fl;
    d->ready = 1;
    d->readings++;
    n = put_num(d->glyph, 0, d->pics);
    d->glyph[n++] = 0xFE;           /* a gap */
    n = put_num(d->glyph, n, d->upd);
    if (fl) {
        d->glyph[n++] = 0xFE;
        if (fl & 1) d->glyph[n++] = G_F;
        if (fl & 2) d->glyph[n++] = G_T;
        if (fl & 4) d->glyph[n++] = G_L;
        if (fl & 8) d->glyph[n++] = G_S;
    }
    for (i = n; i < NSPR; i++)
        d->glyph[i] = 0xFF;
}

/* TwlMain loop: `bl GFL_G3DSysCheckSwapBuffers` (0x02005176) -> here */
u32 fpsc_swap(void)
{
    u8 *g = G3D_SYS;
    if (RAM_OK(g) && *(u32 *)(g + 0x94) == 1)
        fpsc_dbg.swaps++;
    return GFL_G3DSysCheckSwapBuffers();
}

/* FRAME: nothing per frame (the counting is in the hooks); kept for the module's frame list */
void fpsc_frame(void)
{
}

/* TwlMain loop: the call after the VBlank wait (0x020051A4) -> the game's VBlank work, then the counter */
void fpsc_vblank(void)
{
    FpscDbg *d = &fpsc_dbg;
    u32 vbl, dc, s, stride, base, i, j;
    FPSC_MainVBlank();
    vbl = VBLANK_COUNT;
    if (!d->inited) {
        make_tiles();
        d->inited = 1;
        d->vbl0 = vbl;
        for (i = 0; i < NSPR; i++)
            d->glyph[i] = 0xFF;
        if (fps60_dbg) {
            d->upd0 = f60_updates();
            d->late0 = F60_U32(200);
            d->still0 = F60_U32(140);
        }
    }
    if (vbl - d->vbl0 >= WIN)
        latch(d, vbl);
    dc = DISPCNT_A;
    if (d->off || !d->ready || VRAMCNT_E != 0x82 || (dc & 0x1010) != 0x1010) {
        d->shown = 0;
        return;
    }
    /* 1D mapping: names count 32 << s bytes, a glyph takes 128 (aligned to a name); the glyphs end at the top of
     * bank E (or of what the names reach: 32 KiB with s = 0) */
    s = dc >> 20 & 3;
    stride = 128u > (32u << s) ? 128u : 32u << s;
    base = (s ? 0x10000u : 0x8000u) - NG * stride;
    OBJ_PAL15[14] = 0x0000;
    OBJ_PAL15[15] = 0x7FFF;
    {
        u32 x = 1;
        for (i = 0; i < NSPR; i++) {
            volatile u16 *o = OAM + 4 * (OAM0 + i);
            u8 g = d->glyph[i];
            if (g >= NG) {
                o[0] = 0x0200;      /* hidden */
                if (g == 0xFE)
                    x += 6;
                continue;
            }
            {
                /* the glyph's tiles, rewritten every VBlank (only the ones shown: a scene may reuse that VRAM) */
                volatile u32 *t = (volatile u32 *)(OBJ_VRAM + base + g * stride);
                const u32 *src = tiles[g];
                for (j = 0; j < 32; j++)
                    t[j] = src[j];
            }
            o[0] = 1;                       /* y, square, normal, 4bpp */
            o[1] = (u16)(x | 1u << 14);     /* 16x16 */
            o[2] = (u16)(((base + g * stride) >> (5 + s)) | 15u << 12);    /* priority 0, palette 15 */
            x += 10;
        }
    }
    d->shown = 1;
}
