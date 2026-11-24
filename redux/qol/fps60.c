/* ReRedux 60 fps field (fps60.py, in the release ROMs).
 *
 * B2's field runs its logic and its 3D at 30 Hz: FieldRoutine_Run (frame A: input, actors, camera, then
 * Field_RenderStart = camera transform + 3D phase 1, the map blocks) and FieldRoutine_RunAltFrame
 * (frame B: map loaders, then 3D phase 2 = billboards, effects, 3D objects, weather + the swap request).
 * One picture is built over two frames and shown for two.
 *
 * Here the logic keeps its 30 Hz rhythm (nothing in Run / Alt changes order or count: events, scripts,
 * movement, the key latch, the camera transform once per update), and each frame draws a whole picture:
 *  - frame A (after Run's logic): the picture halfway between the previous update and this one. The
 *    camera (look-at position and target), every billboard actor (player, follower, NPCs: BlAct
 *    positions in the three field BlAct scenes), every 3D object drawn through GFL_G3DSysDrawObj /
 *    DrawObjBBoxCull (shadows, field effects, G3D objects, props) and the frame of every NNS animation
 *    of those models are put at the midpoint of the value they had in the last real picture and their
 *    current one, drawn, and put back.
 *  - frame B (Alt, after the loaders): the real picture of this update, recorded for the next midpoint.
 * The midpoint picture goes out a frame earlier than vanilla's (as turbo.c's low-latency updates do).
 *
 * Draws without side effects: the midpoint picture runs phase 2 a second time per update; its particle
 * call (GFL_PTC_Main = draw + calc of every SPL manager) only draws there, so particles still advance once
 * per update (the real picture's call). Checked in melonDS with the fieldpark test module: main RAM after
 * every update equal with the midpoint pictures on and off (fps60's own data aside).
 *
 * Not interpolated: sprite (billboard) animation frames, particles (SPL), weather, map-chunk positions
 * (static), 2D. A position that moved more than FPS60_MAXD per update (a warp, a new object in a reused
 * slot or a pooled effect re-used a tile away) is not interpolated (drawn where it is now).
 * Nothing moved since the last real picture (camera, billboards, 3D objects, animations; no particles,
 * no weather): no midpoint picture (the real one stays on screen, CPU saved).
 *
 * Cost. A whole picture is ~100-170 scanlines of the 263 (melonDS; more with its JIT). During the field's
 * draws NNS sends display lists with one GX-FIFO-mode DMA each (NNS_G3dGeUseFastDma: B2 otherwise feeds
 * them in 472-byte DMA chunks, one GXFIFO interrupt each; the GX DMA is channel 3, the lowest priority, so
 * it holds no other DMA back): about a quarter of a draw saved, same command stream (pictures identical).
 *
 * Time budget, per frame: the midpoint picture is drawn only when the scanlines left before the VBlank
 * cover the longest of the last FPS60_HIST draws + FPS60_MARGIN (else that one frame keeps the last
 * picture: nothing slows down; the next update draws its midpoint again if it fits). The real picture is
 * always drawn. Overruns of the game's own (a map block read from the card, a script: vanilla has the
 * same lag frames) cost nothing else. Only when the real picture itself doesn't fit twice within
 * FPS60_RL_WINDOW updates (a slow emulator) the updates are drawn as vanilla (phase 1 in Run, phase 2 in
 * Alt), timed: as soon as a whole picture fits in the Alt frame again (FPS60_OK_N updates in a row) the
 * 60 fps draws come back. R turbo draws as vanilla too. Vanilla drawing still records the real pictures,
 * so switching back is seamless. Only the first FPS60_WARM updates of a field (map load) don't count.
 * Re-phase on a new press (turbo.c): fps60_rephase_ok / fps60_rephase_alt.
 * Counters: fps60_dbg (frames by kind, overruns, fallback updates, scanlines per draw). */
#include "qol.h"
#include "speed.h"

void GFL_G3DSysResetGeometryCounter(void);
u32 GCTX_HIDGetHeldKeys(void);
void FieldCamera_CalcTransform(void *cam, u32 keys);
s32 Field_CalcDepthOfs(void *field);
void FieldG3D_RenderPhase1(void *field);
void FieldG3D_RenderPhase2(void *field);
void Field_RenderStart(void *field);
void BlActSys_Draw(void *sys, void *cam, void *light);
void NNS_G3dGlbSetBaseTrans(const s32 *v);
void NNS_G3dDraw(void *rnd);
int GSYS_GetEventRunningFlag(void *gsys);
u32 F60_PTC_ActiveCount(void);
u32 F60_PTC_DrawAll(void);
void F60_FieldPtcMain(void);

typedef struct { s32 x, y, z; } V3;

#define VCOUNT          (*(volatile u16 *)0x04000006)
#define VBLANK_COUNT    (*(volatile u32 *)0x027FFC3C)
#define EXMEMCNT        (*(volatile u16 *)0x04000204)
#define NNS_GE_FASTDMA  (*(volatile u32 *)0x0214697C)   /* NNS_G3dGeUseFastDma flag (NNS_G3dGeSendDL) */
#define FIELD_CAM(f)    (*(void **)((u8 *)(f) + 0x10))
#define FIELD_WEATHER(f) (*(u8 **)((u8 *)(f) + 0x20))
#define FIELD_G3DCAM(f) (*(u8 **)((u8 *)(f) + 0xB4))
#define FIELD_RENDER_MODE(f) (*(u32 *)((u8 *)(f) + 0x13C)) /* 0 field, 1 field cut-in, 2 encounter effect */
#define CAM_POS(c)      ((V3 *)((c) + 0x20))       /* G3DCamera: projection (0x20), look-at pos, up, target */
#define CAM_TGT(c)      ((V3 *)((c) + 0x38))
#define FPS60_MAXD      0x20000                     /* camera: 32 units (2 tiles) per update, farther = a cut */
#define FPS60_MAXD_OBJ  0xC000                      /* actors / 3D objects: 12 units (the bike: 8 per update) */
#define FPS60_ANM_MAXD  (4 << 12)                   /* animation frames per update */
#define RAM_OK(p)       ((u32)(p) - 0x02000000u < 0x400000u)

typedef struct {
    u8 want;            /* 60 fps on (tests may clear it) */
    u8 mode;            /* this update: 1 = 60 fps draws, 0 = vanilla */
    u8 drawing;         /* 0 none, 1 real picture (record), 2 midpoint picture */
    u8 have_cam;
    u32 run_frame;      /* qol frame of the last Run draw */
    u32 gen;            /* real pictures drawn / recorded */
    u32 mid_frames, real_frames, van_frames, same_frame;
    u32 late;           /* draws that ended after a VBlank had passed (frame overrun) */
    u16 vc_mid, vc_real;    /* VCOUNT at the end of the last midpoint / real draw */
    u16 vc_mid_max, vc_real_max;    /* most lines since the VBlank at the end of a draw (263: overran) */
    u32 vbl0;
    u32 objs, objs_mid, bl_mid, tab_full;   /* last real draw: 3D objects; last midpoint: moved ones */
    V3 cam_pos, cam_tgt;    /* camera of the last real picture */
    /* +84 */
    u32 overruns;       /* main-loop frames with a draw of ours that took 2+ VBlanks (counted only) */
    u16 cool, backoff;  /* cool: 1 while drawing as vanilla because real pictures don't fit; backoff unused */
    u32 near_late;      /* unused */
    u32 draw_frame;     /* qol frame of the last 60 fps draw */
    u32 vbl_prev;       /* VBlank count at the previous frame hook */
    u32 fallback;       /* updates drawn as vanilla because real pictures didn't fit */
    u32 ovr_gen;        /* gen at the last overrun */
    void *field;        /* the field of the last update: a new one (map change) restarts the warm-up */
    u32 warm_gen;       /* gen when this field started */
    u16 dl_mid, dl_real;            /* +120: scanlines the last midpoint / real draw took */
    u16 dl_mid_max, dl_real_max;
    u32 event_gen;                  /* +128: gen when an event (menu, script, warp) last ran */
    u32 ovr_ignored;                /* +132: overruns in a field's warm-up */
    /* +136 */
    u32 overloads;                  /* fallbacks to vanilla drawing started */
    u32 mid_skipped;                /* updates without a midpoint picture: nothing moved */
    u32 ptc_mid;                    /* midpoint pictures that drew particles without calculating them */
    u32 anm_mid;                    /* animations put at a half frame in the last midpoint picture */
    u32 rephased;                   /* Alt halves run by turbo.c's re-phase (no real picture) */
    u8 skip_alt;                    /* set by turbo.c: the next Alt half draws nothing */
    u8 nostatic;                    /* tests: 1 = always draw the midpoint picture */
    u8 noanm;                       /* tests: 1 = no animation interpolation */
    u8 nofast;                      /* tests: 1 = no GX-FIFO-mode display-list DMA */
    u32 near_gen[4];                /* unused */
    u8 near_i, pad2[3];
    u32 static_why;                 /* +180: what moved in the last checked update (bits, tests) */
    u32 vanilla_rec;                /* +184: real pictures recorded in vanilla drawing (turbo, fallback) */
    u32 mid_evstart;                /* +188: updates that started an event: no midpoint picture */
    u8 event_on;                    /* an event ran at the last Run */
    u8 render_mode;                 /* native field render mode; cut-ins have their own draw side effects */
    u8 pad3[2];
    u16 est_mid, est_real;          /* +196: scanlines the next midpoint / real draw is expected to take */
    u32 mid_late;                   /* +200: midpoint pictures left out: not enough time left in the frame */
    u32 real_late;                  /* +204: real pictures without enough time left */
    /* +208 */
    u16 dl_hist[4];                 /* the last whole draws (scanlines; 2 VBlanks or more: + 263 per VBlank) */
    u8 dl_i, ok_streak, rl_i, pad4;
    u32 rl_gen[2];                  /* +220: gens of the last two real pictures that didn't fit */
    u16 van_ph1, van_ph2;           /* +228: vanilla drawing: the last phase 1 (Run) / phase 2 (Alt) lines */
    u32 recovered;                  /* +232: fallbacks ended because whole pictures fit again */
    u32 van_upd;                    /* +236: updates in the current fallback */
} Fps60Dbg;
#define FPS60_WARM          30      /* updates */
#define FPS60_MARGIN        10      /* lines kept free after a draw (the rest of the main loop: ~5 lines) */
#define FPS60_HIST          4       /* draws the estimate looks back on */
#define FPS60_RL_WINDOW     30      /* two real pictures that don't fit within this many updates -> vanilla */
#define FPS60_OK_N          3       /* updates in a row with room for a whole picture -> 60 fps again */
#define FPS60_VAN_MAX       300     /* updates: try the 60 fps draws again after this long in any case */

Fps60Dbg fps60_dbg = {.want = 1};
u8 fps60_want = 1;          /* read by turbo.c (weak): no low-latency updates */

/* FRAME (core's hook: once per main-loop frame, after the procs): this frame had a draw of ours and took
 * 2+ VBlanks -> an overrun (counted; the time budget avoids the ones our draws would cause) */
void fps60_frame(void)
{
    Fps60Dbg *d = &fps60_dbg;
    u32 vbl = VBLANK_COUNT;
    int overran = vbl - d->vbl_prev >= 2 && d->draw_frame + 1 == qol_header.frames;
    d->vbl_prev = vbl;
    if (!overran)
        return;
    if (d->gen - d->warm_gen < FPS60_WARM) {
        d->ovr_ignored++;           /* a map load has its own spikes (vanilla too) */
        return;
    }
    d->overruns++;
    d->ovr_gen = d->gen;
}

static inline s32 mid1(s32 a, s32 b) { return a + ((b - a) >> 1); }

static int near_d(const V3 *a, const V3 *b, s32 m)
{
    s32 dx = a->x - b->x, dy = a->y - b->y, dz = a->z - b->z;
    return dx < m && dx > -m && dy < m && dy > -m && dz < m && dz > -m;
}

static int same3(const V3 *a, const V3 *b)
{
    return a->x == b->x && a->y == b->y && a->z == b->z;
}

static void midv(V3 *out, const V3 *last, const V3 *cur)
{
    out->x = mid1(last->x, cur->x);
    out->y = mid1(last->y, cur->y);
    out->z = mid1(last->z, cur->z);
}

/* --- 3D objects: GFL_G3DSysDrawObj / DrawObjBBoxCull's NNS_G3dGlbSetBaseTrans(&srt->trans) ------------ *
 * Keyed by the transform's address and its run of consecutive repeats (a caller drawing several objects
 * from one stack transform); open addressing, an entry belongs to the real picture `gen`. The entries of
 * the last real picture are also listed (ot_used) so that checks don't scan the whole table. */
#define OT_SIZE 512
#define OT_PROBE 12
typedef struct { const s32 *p; u16 occ; u16 gen; V3 v; } ObjEnt;
static ObjEnt ot[OT_SIZE];
static u16 ot_used[OT_SIZE];
static u16 ot_n;
static const s32 *ot_prev;
static u16 ot_occ;

static u32 ot_hash(const s32 *p, u32 occ)
{
    u32 h = ((u32)p >> 2) * 0x9E3779B1u + occ * 0x85EBCA77u;
    return h >> 23;     /* 9 bits */
}

void fps60_basetrans(const s32 *t)
{
    Fps60Dbg *d = &fps60_dbg;
    u32 occ, h, i;
    u16 g;
    if (!d->drawing) {
        NNS_G3dGlbSetBaseTrans(t);
        return;
    }
    occ = t == ot_prev ? ot_occ + 1u : 0u;
    ot_prev = t;
    ot_occ = occ;
    h = ot_hash(t, occ);
    g = (u16)d->gen;
    if (d->drawing == 1) {
        for (i = 0; i < OT_PROBE; i++) {
            u32 k = (h + i) & (OT_SIZE - 1);
            ObjEnt *e = &ot[k];
            if (e->gen != g) {
                e->p = t;
                e->occ = (u16)occ;
                e->gen = g;
                e->v = *(const V3 *)t;
                ot_used[ot_n++] = (u16)k;
                d->objs++;
                break;
            }
            if (e->p == t && e->occ == occ) {
                e->v = *(const V3 *)t;
                break;
            }
        }
        if (i == OT_PROBE)
            d->tab_full++;
        NNS_G3dGlbSetBaseTrans(t);
        return;
    }
    for (i = 0; i < OT_PROBE; i++) {
        ObjEnt *e = &ot[(h + i) & (OT_SIZE - 1)];
        if (e->gen != g)
            break;
        if (e->p == t && e->occ == occ) {
            const V3 *c = (const V3 *)t;
            if (!same3(&e->v, c) && near_d(&e->v, c, FPS60_MAXD_OBJ)) {
                V3 m;
                midv(&m, &e->v, c);
                d->objs_mid++;
                NNS_G3dGlbSetBaseTrans(&m.x);
                return;
            }
            break;
        }
    }
    NNS_G3dGlbSetBaseTrans(t);
}

/* did any recorded 3D object move since the last real picture? (its transform still holds the value) */
static int objs_moved(void)
{
    u16 g = (u16)fps60_dbg.gen;
    u32 i;
    for (i = 0; i < ot_n; i++) {
        const ObjEnt *e = &ot[ot_used[i]];
        if (e->gen == g && RAM_OK(e->p) && !same3(&e->v, (const V3 *)e->p))
            return 1;
    }
    return 0;
}

/* --- NNS animations of the drawn models (GFL's draw of a render object: NNS_G3dDraw(rnd)) ------------- *
 * NNSG3dRenderObj: +8 material, +0x10 joint, +0x18 visibility animation lists (NNSG3dAnmObj: +0 fx32 frame,
 * +8 resource (+4 u16 frame count), +0x10 next). Recorded per animation object in real pictures; in the
 * midpoint picture a frame that went forward by at most FPS60_ANM_MAXD is put halfway, then restored. */
#define AT_SIZE 256
#define AT_PROBE 8
#define ANM_STACK 48
typedef struct { const u8 *a; u16 gen; u16 pad; s32 f; } AnmEnt;
static AnmEnt at[AT_SIZE];
static u8 at_used[AT_SIZE];
static u16 at_n;
static u8 *anm_save_p[ANM_STACK];
static s32 anm_save_f[ANM_STACK];

static u32 at_hash(const void *p)
{
    return (((u32)p >> 2) * 0x9E3779B1u) >> 24;    /* 8 bits */
}

static AnmEnt *at_find(const u8 *a, int add)
{
    u16 g = (u16)fps60_dbg.gen;
    u32 h = at_hash(a), i;
    for (i = 0; i < AT_PROBE; i++) {
        u32 k = (h + i) & (AT_SIZE - 1);
        AnmEnt *e = &at[k];
        if (e->a == a && e->gen == g)
            return e;
        if (e->gen != g) {
            if (!add)
                return 0;
            e->a = a;
            e->gen = g;
            at_used[at_n++] = (u8)k;
            return e;
        }
    }
    return 0;
}

/* did any recorded animation frame change since the last real picture? */
static int anms_changed(void)
{
    u16 g = (u16)fps60_dbg.gen;
    u32 i;
    for (i = 0; i < at_n; i++) {
        const AnmEnt *e = &at[at_used[i]];
        if (e->gen == g && RAM_OK(e->a) && *(const s32 *)e->a != e->f)
            return 1;
    }
    return 0;
}

void fps60_nns_draw(u8 *rnd)
{
    Fps60Dbg *d = &fps60_dbg;
    u32 l, n = 0;
    if (!d->drawing || d->noanm || !RAM_OK(rnd)) {
        NNS_G3dDraw(rnd);
        return;
    }
    for (l = 0; l < 3; l++) {
        u8 *a = *(u8 **)(rnd + 8 + 8 * l);
        u32 k;
        for (k = 0; RAM_OK(a) && k < 16; k++, a = *(u8 **)(a + 0x10)) {
            AnmEnt *e;
            if (d->drawing == 1) {
                if ((e = at_find(a, 1)) != 0)
                    e->f = *(s32 *)a;
                continue;
            }
            e = at_find(a, 0);
            if (e && n < ANM_STACK) {
                s32 cur = *(s32 *)a, df = cur - e->f;
                if (df > 0 && df <= FPS60_ANM_MAXD) {
                    anm_save_p[n] = a;
                    anm_save_f[n] = cur;
                    n++;
                    *(s32 *)a = e->f + (df >> 1);
                }
            }
        }
    }
    NNS_G3dDraw(rnd);
    d->anm_mid += n;
    while (n--)
        *(s32 *)anm_save_p[n] = anm_save_f[n];
}

/* --- billboard actors: the three BlAct systems of the field (field +0xC0, +0xC4, +0xC8) -------------- *
 * BlActScene: +8 actors (0x1C bytes: u16 material | flags, +4 VecFx32 position, ... +0x18 flags),
 * +0xE slot count. An actor slot is free when its material index (low 14 bits) is 0x3FFF. A real picture
 * records every slot's material and, for the slots in use (listed in act[]), the position and a hash of
 * the whole slot. */
#define BL_SYS 3
#define BL_MAX 128          /* scene 0 holds 128 slots (80 and 40 in the others) */
#define BL_FREE 0x3FFF
typedef struct { void *sys; u16 n, gen; u16 na, pad; V3 v[BL_MAX]; u16 key[BL_MAX]; u32 hash[BL_MAX]; u8 act[BL_MAX]; } BlRec;
static BlRec blr[BL_SYS];
static V3 bl_save[BL_MAX];
static u8 bl_moved[BL_MAX];

static u32 bl_hash(const u8 *a)
{
    const u32 *w = (const u32 *)a;
    u32 h = 0x811C9DC5u, i;
    for (i = 0; i < 7; i++)
        h = (h ^ w[i]) * 0x01000193u;
    return h;
}

static BlRec *bl_rec(void *sys, int add)
{
    u32 i;
    for (i = 0; i < BL_SYS; i++)
        if (blr[i].sys == sys)
            return &blr[i];
    if (!add)
        return 0;
    for (i = 0; i < BL_SYS; i++)
        if (!blr[i].sys || blr[i].gen != (u16)fps60_dbg.gen) {
            blr[i].sys = sys;
            blr[i].n = 0;
            blr[i].na = 0;
            blr[i].gen = (u16)(fps60_dbg.gen - 1);
            return &blr[i];
        }
    return 0;
}

static u8 *bl_scene(void *sys)
{
    u8 *scene = sys ? *(u8 **)((u8 *)sys + 4) : 0;
    return RAM_OK(scene) ? scene : 0;
}

void fps60_blact_draw(void *sys, void *cam, void *light)
{
    Fps60Dbg *d = &fps60_dbg;
    u8 *scene, *act;
    u32 n, i, j, moved = 0;
    BlRec *r;
    if (!d->drawing || !(scene = bl_scene(sys)) || !(r = bl_rec(sys, d->drawing == 1))) {
        BlActSys_Draw(sys, cam, light);
        return;
    }
    act = *(u8 **)(scene + 8);
    n = *(u16 *)(scene + 0xE);
    if (n > BL_MAX)
        n = BL_MAX;
    if (d->drawing == 1) {
        u32 na = 0;
        for (i = 0; i < n; i++) {
            const u8 *a = act + 0x1C * i;
            u16 k = *(const u16 *)a & BL_FREE;
            r->key[i] = k;
            if (k == BL_FREE)
                continue;
            r->v[i] = *(const V3 *)(a + 4);
            r->hash[i] = bl_hash(a);
            r->act[na++] = (u8)i;
        }
        r->n = (u16)n;
        r->na = (u16)na;
        r->gen = (u16)d->gen;
        BlActSys_Draw(sys, cam, light);
        return;
    }
    if (r->gen != (u16)d->gen) {
        BlActSys_Draw(sys, cam, light);
        return;
    }
    for (j = 0; j < r->na; j++) {
        u8 *a;
        V3 *p;
        i = r->act[j];
        if (i >= n)
            continue;
        a = act + 0x1C * i;
        p = (V3 *)(a + 4);
        if ((*(u16 *)a & BL_FREE) == r->key[i] && !same3(p, &r->v[i]) && near_d(&r->v[i], p, FPS60_MAXD_OBJ)) {
            bl_save[moved] = *p;
            bl_moved[moved++] = (u8)i;
            midv(p, &r->v[i], p);
        }
    }
    BlActSys_Draw(sys, cam, light);
    for (j = 0; j < moved; j++)
        *(V3 *)(act + 0x1C * bl_moved[j] + 4) = bl_save[j];
    d->bl_mid += moved;
}

/* did any billboard actor change (any of its 0x1C bytes: position, material, flags; a slot taken or
 * freed) since the last real picture? */
static int bl_changed(u8 *field)
{
    u32 s, i;
    for (s = 0; s < BL_SYS; s++) {
        void *sys = *(void **)(field + 0xC0 + 4 * s);
        u8 *scene = bl_scene(sys), *act;
        BlRec *r;
        u32 n;
        if (!scene)
            continue;
        r = bl_rec(sys, 0);
        n = *(u16 *)(scene + 0xE);
        if (!r || r->gen != (u16)fps60_dbg.gen || n != r->n || n > BL_MAX)
            return 1;
        act = *(u8 **)(scene + 8);
        if (!RAM_OK(act))
            return 1;
        for (i = 0; i < n; i++) {
            const u8 *a = act + 0x1C * i;
            u16 k = *(const u16 *)a & BL_FREE;
            if (k != r->key[i] || (k != BL_FREE && bl_hash(a) != r->hash[i]))
                return 1;
        }
    }
    return 0;
}

/* --- the draws ---------------------------------------------------------------------------------------- */

/* scanlines from (vc0, vbl0) to now (a draw that crossed VBlanks: + 263 per extra VBlank) */
static u32 lines_since(u32 vc0, u32 vbl0)
{
    u32 vc = VCOUNT & 0x1FF;
    u32 dl = vc >= vc0 ? vc - vc0 : vc + 263 - vc0;
    u32 nv = VBLANK_COUNT - vbl0;
    if (nv > 1)
        dl += 263 * (nv - 1);
    return dl > 0xFFFF ? 0xFFFF : dl;
}

/* scanlines until the next VBlank starts (the main loop starts at the VBlank, line 192, unless the loop before
 * overran) */
static u32 lines_left(void)
{
    u32 vc = VCOUNT & 0x1FF;
    return vc >= 192 ? 263 - vc + 192 : 192 - vc;
}

/* the longest of the last FPS60_HIST whole draws */
static u32 est_draw(const Fps60Dbg *d)
{
    u32 i, m = 0;
    for (i = 0; i < FPS60_HIST; i++)
        if (d->dl_hist[i] > m)
            m = d->dl_hist[i];
    return m;
}

static void draw_stats(Fps60Dbg *d, int kind, u32 vbl, u32 vc0)
{
    u32 vc = VCOUNT & 0x1FF;
    u16 used = (u16)(vc >= 192 ? vc - 192 : vc + 263 - 192);     /* lines since the frame's VBlank */
    u16 dl = (u16)lines_since(vc0, vbl);
    d->draw_frame = qol_header.frames;
    if (VBLANK_COUNT != vbl) {
        d->late++;
        used = 263;
    }
    d->dl_hist[d->dl_i++ & (FPS60_HIST - 1)] = dl;
    d->est_mid = d->est_real = (u16)est_draw(d);
    if (kind == 1) {
        d->dl_real = dl;
        if (dl > d->dl_real_max)
            d->dl_real_max = dl;
        d->vc_real = (u16)vc;
        if (used > d->vc_real_max)
            d->vc_real_max = used;
    } else {
        d->dl_mid = dl;
        if (dl > d->dl_mid_max)
            d->dl_mid_max = dl;
        d->vc_mid = (u16)vc;
        if (used > d->vc_mid_max)
            d->vc_mid_max = used;
    }
}

static void record_cam(Fps60Dbg *d, u8 *field)
{
    u8 *cam = FIELD_G3DCAM(field);
    if (cam) {
        d->cam_pos = *CAM_POS(cam);
        d->cam_tgt = *CAM_TGT(cam);
        d->have_cam = 1;
    }
}

/* a new real picture: the recorded tables start over */
static void new_gen(Fps60Dbg *d)
{
    d->gen++;
    d->objs = 0;
    ot_n = 0;
    at_n = 0;
}

/* display lists in one GX-FIFO-mode DMA each while the field draws (see the top); returns the old flag */
static u32 fast_on(const Fps60Dbg *d)
{
    u32 old = NNS_GE_FASTDMA;
    if (!d->nofast)
        NNS_GE_FASTDMA = 1;
    return old;
}

/* Field_RenderStart (0x021800D4) [+ camera transform] + phase 1 + phase 2 (+ swap request) */
static void draw_all(u8 *field, int kind, int calc_cam)
{
    Fps60Dbg *d = &fps60_dbg;
    u8 *cam;
    V3 pos, tgt;
    int cam_mid = 0;
    u32 vbl = VBLANK_COUNT;
    u32 vc0 = VCOUNT & 0x1FF;
    u32 fast;
    GFL_G3DSysResetGeometryCounter();
    if (calc_cam) {
        FieldCamera_CalcTransform(FIELD_CAM(field), (u16)GCTX_HIDGetHeldKeys());
        *(s32 *)(field + 0x110) = Field_CalcDepthOfs(field);
    }
    cam = FIELD_G3DCAM(field);
    if (kind == 2 && cam && d->have_cam) {
        pos = *CAM_POS(cam);
        tgt = *CAM_TGT(cam);
        if (near_d(&d->cam_pos, &pos, FPS60_MAXD) && near_d(&d->cam_tgt, &tgt, FPS60_MAXD)) {
            midv(CAM_POS(cam), &d->cam_pos, &pos);
            midv(CAM_TGT(cam), &d->cam_tgt, &tgt);
            cam_mid = 1;
        }
    } else if (kind == 1) {
        record_cam(d, field);
    }
    if (kind == 1)
        new_gen(d);
    else {
        d->objs_mid = 0;
        d->anm_mid = 0;
    }
    d->drawing = (u8)kind;
    ot_prev = 0;
    ot_occ = 0;
    fast = fast_on(d);
    EXMEMCNT &= 0x7FFF;
    FieldG3D_RenderPhase1(field);
    EXMEMCNT |= 0x8000;
    EXMEMCNT &= 0x7FFF;
    FieldG3D_RenderPhase2(field);
    EXMEMCNT |= 0x8000;
    NNS_GE_FASTDMA = fast;
    d->drawing = 0;
    if (cam_mid) {
        *CAM_POS(cam) = pos;
        *CAM_TGT(cam) = tgt;
    }
    draw_stats(d, kind, vbl, vc0);
}

/* nothing that the midpoint picture would move has moved since the last real picture (bits in static_why
 * for tests: 1 camera, 2 billboards, 4 3D objects, 8 animations, 16 particles, 32 weather, 64 no record).
 * The cheap / most likely checks first; the first hit ends it. */
static int nothing_moved(Fps60Dbg *d, u8 *field)
{
    u8 *cam = FIELD_G3DCAM(field), *w = FIELD_WEATHER(field);
    u32 why = 0;
    if (!d->have_cam || !cam || d->gen == d->warm_gen)
        why |= 64;
    else if (!same3(&d->cam_pos, CAM_POS(cam)) || !same3(&d->cam_tgt, CAM_TGT(cam)))
        why |= 1;
    if (!why && F60_PTC_ActiveCount())
        why |= 16;
    if (!why && RAM_OK(w) && *(u16 *)(w + 8))
        why |= 32;                  /* a weather (FieldWeather +8: its id, 0 = none) */
    if (!why && anms_changed())
        why |= 8;
    if (!why && objs_moved())
        why |= 4;
    if (!why && bl_changed(field))
        why |= 2;
    d->static_why = why;
    return !why;
}

extern struct { u8 on, live; } turbo_dbg __attribute__((weak));

/* real pictures don't fit in the Alt frame: draw as vanilla (split) until a whole one fits again */
static void real_late(Fps60Dbg *d)
{
    d->real_late++;
    if (d->gen - d->warm_gen < FPS60_WARM || d->cool)
        return;
    if (d->rl_gen[0] && d->gen - d->rl_gen[(d->rl_i + 1) & 1] < FPS60_RL_WINDOW && d->rl_i) {
        d->cool = 1;
        d->ok_streak = 0;
        d->van_upd = 0;
        d->overloads++;
    }
    d->rl_gen[d->rl_i++ & 1] = d->gen;
}

/* FieldRoutine_Run's two `bl Field_RenderStart` (0x0217FF9A, 0x021800C4) -> here */
void fps60_run_render(u8 *field)
{
    Fps60Dbg *d = &fps60_dbg;
    int ev, ev_start;
    u32 render_mode = FIELD_RENDER_MODE(field);
    /* Only the ordinary field path has been made safe to draw twice. The cut-in path
     * (Pokédex receipt, HM scenes, etc.) calls draw-and-calculate particles separately,
     * and encounter effects also own their draw timing. Keep their native split draws. */
    d->mode = d->want && fps60_want && render_mode == 0 && !(&turbo_dbg && turbo_dbg.live);
    if (field != d->field || render_mode != d->render_mode || qol_header.frames - d->run_frame > 4) {
        /* a new field, or the field wasn't running (map change, menu, battle): warm up again */
        if (field != d->field) {
            d->cool = 0;
            d->rl_i = 0;
            d->rl_gen[0] = d->rl_gen[1] = 0;
        }
        d->field = field;
        d->gen++;                   /* the recorded positions are stale */
        d->warm_gen = d->gen;
        d->have_cam = 0;
    }
    d->render_mode = (u8)render_mode;
    d->run_frame = qol_header.frames;
    ev = QOL_GSYS && GSYS_GetEventRunningFlag(QOL_GSYS);
    if (ev)
        d->event_gen = d->gen;
    ev_start = ev && !d->event_on;     /* an event started in this update's event step (menu, script) */
    d->event_on = (u8)ev;
    if (d->mode && d->cool) {
        d->fallback++;
        d->van_upd++;
        d->mode = 0;
    }
    if (!d->mode) {
        u32 vc0 = VCOUNT & 0x1FF, vbl = VBLANK_COUNT, fast = fast_on(d);
        d->van_frames++;
        Field_RenderStart(field);
        NNS_GE_FASTDMA = fast;
        d->van_ph1 = (u16)lines_since(vc0, vbl);
        return;
    }
    /* the camera transform runs once per update in any case (vanilla: Field_RenderStart) */
    FieldCamera_CalcTransform(FIELD_CAM(field), (u16)GCTX_HIDGetHeldKeys());
    *(s32 *)(field + 0x110) = Field_CalcDepthOfs(field);
    if (ev_start) {
        /* the update that starts an event (X menu, a script) loads its graphics in the same frame: no
         * midpoint picture on top (it would overrun the frame and hold a picture / delay the sound) */
        d->mid_evstart++;
        return;
    }
    if (lines_left() < est_draw(d) + FPS60_MARGIN) {
        /* the logic took most of this frame (or it started late: a menu, a map block read): a whole
         * picture wouldn't fit before the VBlank (an overrun slows the game and delays the sound by a
         * frame); only this frame keeps the last picture */
        d->mid_late++;
        return;
    }
    if (!d->nostatic && nothing_moved(d, field)) {
        d->mid_skipped++;       /* the real picture stays on screen until the Alt half's */
        return;
    }
    d->mid_frames++;
    draw_all(field, 2, 0);
}

/* FieldRoutine_RunAltFrame's `bl FieldG3D_RenderPhase2` (0x02180182, between the EXMEMCNT writes) -> here */
void fps60_alt_render(u8 *field)
{
    Fps60Dbg *d = &fps60_dbg;
    if (d->skip_alt) {
        /* turbo.c's re-phase: this update's Run and its midpoint picture follow in this frame */
        d->skip_alt = 0;
        d->rephased++;
        return;
    }
    if (!d->mode) {
        /* vanilla drawing (turbo, fallback, tests): record this real picture all the same, so that the
         * first midpoint picture afterwards starts from it */
        u32 vc0 = VCOUNT & 0x1FF, vbl = VBLANK_COUNT, fast;
        if (d->cool) {
            /* back to 60 fps as soon as a whole picture (phase 1 + 2, as last measured) fits here again */
            u32 whole = (u32)d->van_ph1 + d->van_ph2;
            if (whole < est_draw(d))
                whole = est_draw(d);
            d->ok_streak = lines_left() >= whole + FPS60_MARGIN ? d->ok_streak + 1 : 0;
            if (d->ok_streak >= FPS60_OK_N || d->van_upd >= FPS60_VAN_MAX) {
                d->cool = 0;
                d->recovered++;
            }
        }
        record_cam(d, field);
        new_gen(d);
        d->drawing = 1;
        ot_prev = 0;
        ot_occ = 0;
        fast = fast_on(d);
        FieldG3D_RenderPhase2(field);
        NNS_GE_FASTDMA = fast;
        d->drawing = 0;
        d->van_ph2 = (u16)lines_since(vc0, vbl);
        d->vanilla_rec++;
        return;
    }
    if (d->run_frame == qol_header.frames) {
        d->same_frame++;        /* Run and Alt in one frame: Run's picture is this frame's */
        return;
    }
    if (lines_left() < est_draw(d) + FPS60_MARGIN)
        real_late(d);           /* drawn all the same (the update's picture can't be left out) */
    d->real_frames++;
    draw_all(field, 1, 0);
}

/* OVL_36 0x0218121E in FieldRenderPhase2_Fieldmap: `bl` GFL_PTC_Main's veneer -> here. The midpoint
 * picture draws the particles without advancing them (GFL_PTC_Main = draw + calc of every manager). */
void fps60_ptc(void)
{
    Fps60Dbg *d = &fps60_dbg;
    if (d->drawing == 2) {
        if (F60_PTC_ActiveCount()) {
            F60_PTC_DrawAll();
            d->ptc_mid++;
        }
        return;
    }
    F60_FieldPtcMain();
}

/* turbo.c's re-phase in this update's Alt frame: only while this update draws at 60 fps (a vanilla split
 * update can't take the next update's phase 1 in the same frame) */
int fps60_rephase_ok(void)
{
    const Fps60Dbg *d = &fps60_dbg;
    return d->mode && d->want && fps60_want && d->run_frame + 1 == qol_header.frames;
}

void fps60_rephase_alt(int on)
{
    fps60_dbg.skip_alt = (u8)on;
}

/* this update draws at 60 fps and nothing moved since the last real picture (turbo.c: a re-phase can be
 * paid back unseen) */
int fps60_static(void)
{
    const Fps60Dbg *d = &fps60_dbg;
    return d->mode && d->run_frame + 2 >= qol_header.frames && !d->static_why && !d->nostatic;
}
