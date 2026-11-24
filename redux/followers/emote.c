/* HGSS emote balloons that Black 2 doesn't have (heart, faces, sweat, ...), drawn and animated by
 * B2's own balloon effect (OVL_36 fldeff_gyoe, field effect 4).
 *
 * B2's balloon task draws the G3D actor at *(handle + 0x24 + type * 4); nothing else reads the
 * handle. So each HGSS balloon is a field-effect task with B2's vtable entries for init and draw
 * (pop of 7 ticks, 30-tick hold, same height and depth bias as `!`), a handle of our own inside
 * the task's work holding the icon's two frames (a/0/7/4 members EMOTE_FIRST_MEMBER + 2 * icon
 * + 0/1, built by tools/follower_emotes.py), and an update that flips `type` between them as
 * HGSS's balloon animation does (frame 1 for 4 ticks, 0 for 8, 1 for the rest), then runs B2's
 * self-deleting update.
 *
 * Resources live exactly as long as the task: loaded in emote_hgss_start, freed by the task's exit
 * callback, which B2 calls both when the balloon deletes itself and when the field tears its
 * effect tasks down (zone change, battle, menu) before freeing its own effects. No state outlives
 * a field, nothing is cached across uses. Each balloon reads two 768-byte members; the textures
 * (2 x 128 bytes + 16-byte palettes) are transferred to VRAM by a VBlank TCB, as the field's own
 * G3D objects are, since GX_BeginLoadTex mid-frame unmaps texture VRAM from the 3D engine. */
#include "follow.h"
#include "talk.h"

/* emote_syms.ld */
void *FieldEffects_TCBCreate(void *fx, const void *vtable, void *pos, u32 user, void *params, u32 pri);
void *FieldEffects_GetField(void *fx);
void *FieldEffects_GetArc(void *fx);
void FLDEFF_GYOE_Init(void *tcb, void *work);
void FLDEFF_GYOE_UpdateAuto(void *tcb, void *work);
void FLDEFF_GYOE_Draw(void *tcb, void *work);
void FldAct_GetSnapshot(void *actor, u16 *out);
void *G3DRes_ReadArcTool(void *arc, u32 member);
int G3DRes_AllocTex(void *res);
int G3DRes_TransTex(void *res);
int G3DRes_FreeTex(void *res);
void G3DRes_Free(void *res);
void *G3DMdl_Create(void *res, u32 idx, void *texres);
void G3DMdl_Free(void *mdl);
void *G3DActor_Create(void *mdl, void *anm, u32 count);
void G3DActor_Free(void *act);
void NNS_G3dMdlSetFlagAll(void *resmdl, u32 flag);
void *GFL_VBlankTCBAdd(void (*fn)(void *tcb, void *data), void *data, u32 pri);
void GFL_TCBRemove(void *tcb);
int GFL_IsCardIrqEnabled(void);

#define ICON_COUNT      14
#define VBLANK_PRI      10

/* B2's balloon handle layout (0x38 bytes); only act[] and depth are read by its draw */
typedef struct {
    void *vtcb;         /* +0x00 (B2: field effects) pending texture transfer */
    void *res[2];       /* +0x04 (B2: res[4]) */
    volatile u32 sent;  /* +0x0C: 1 once the VBlank transfer ran */
    u32 pad0;
    void *mdl[2];       /* +0x14 */
    u32 pad1[2];
    void *act[2];       /* +0x24: the draw's actor = act[type] */
    u32 pad2[2];
    u16 depth;          /* +0x34: B2 sets 4 (camera-space depth bias of the draw) */
    u16 pad3;
} Handle;

/* FLDEFF_GYOE task work: 0x1C bytes copied from the params, then the pop / hold state */
typedef struct {
    u32 type;           /* frame 0 / 1 */
    u32 play_se;
    Handle *h;
    void *actor;
    u16 snap[4];        /* the actor's identity; the task ends when it changes */
    void *field;
    u32 phase;          /* +0x1C: 0 pop, 1 hold, 2 done */
    u32 count;          /* +0x20: hold ticks, done at 30 */
    u32 done;           /* +0x24: FLDEFF_GYOE_CheckEnd */
    s32 y, vy;
    Handle hd;          /* +0x30: ours */
} Work;

_Static_assert(__builtin_offsetof(Handle, act) == 0x24 && __builtin_offsetof(Handle, depth) == 0x34
               && sizeof(Handle) == 0x38, "B2 balloon handle layout");
_Static_assert(__builtin_offsetof(Work, phase) == 0x1C && __builtin_offsetof(Work, done) == 0x24
               && __builtin_offsetof(Work, hd) == 0x30 && sizeof(Work) <= 0xA0, "B2 balloon work layout");

#ifdef EMOTE_FIRST_MEMBER

static void send(Handle *h)
{
    G3DRes_TransTex(h->res[0]);
    G3DRes_TransTex(h->res[1]);
    h->sent = 1;
}

static void vblank(void *tcb, void *data)
{
    (void)tcb;
    Handle *h = data;
    if (!h->sent && !GFL_IsCardIrqEnabled())    /* else retry next VBlank, as the field's VRAM TCBs do */
        send(h);
}

static void emote_exit(void *tcb, Work *w)
{
    (void)tcb;
    Handle *h = &w->hd;
    if (h->vtcb) {
        GFL_TCBRemove(h->vtcb);
        if (!h->sent)
            send(h);    /* torn down within a frame of the start: FreeTex frees transferred keys only */
    }
    for (u32 f = 0; f < 2; f++) {
        G3DActor_Free(h->act[f]);
        G3DMdl_Free(h->mdl[f]);
        if (h->res[f]) {
            G3DRes_FreeTex(h->res[f]);
            G3DRes_Free(h->res[f]);
        }
    }
}

static void emote_update(void *tcb, Work *w)
{
    Handle *h = &w->hd;
    if (h->vtcb && h->sent) {
        GFL_TCBRemove(h->vtcb);
        h->vtcb = 0;
    }
    u32 n = w->count + 1;   /* the hold tick this update reaches */
    w->type = w->phase && (n <= 4 || n > 12);
    FLDEFF_GYOE_UpdateAuto(tcb, w);     /* may delete the task (-> emote_exit): last */
}

static const void *const emote_vtable[5] = {    /* B2's manual/auto vtables _021D1014 / _021D1028 */
    (void *)sizeof(Work), FLDEFF_GYOE_Init, emote_exit, emote_update, FLDEFF_GYOE_Draw,
};

void *emote_hgss_start(void *field, void *fa, u32 icon)
{
    /* B2 draws ! ? note ... itself (talk.c) */
    if (icon >= ICON_COUNT || icon == 6 || icon == 7 || icon == 8 || icon == 12)
        return 0;
    void *fx = Field_GetFieldEffects(field);
    struct {
        u32 type, play_se;
        void *h, *actor;
        u16 snap[4];
        void *field;
    } p;    /* FLDEFF_GYOE params (0x1C bytes, copied by its init) */
    p.type = p.play_se = 0;     /* frame 0; no SE (talk.c plays it) */
    p.h = 0;                    /* set below, before the first draw */
    p.actor = fa;
    p.field = FieldEffects_GetField(fx);
    FldAct_GetSnapshot(fa, p.snap);
    u8 *tcb = FieldEffects_TCBCreate(fx, emote_vtable, 0, 0, &p, 0);
    if (!tcb)
        return 0;
    Work *w = (Work *)(tcb + 0x18);     /* FUN_021A3AFC; the slot was zeroed by TCBCreate */
    Handle *h = w->h = &w->hd;
    h->depth = 4;
    void *arc = FieldEffects_GetArc(fx);
    for (u32 f = 0; f < 2; f++) {
        void *res = h->res[f] = G3DRes_ReadArcTool(arc, EMOTE_FIRST_MEMBER + 2 * icon + f);
        G3DRes_AllocTex(res);
        void *mdl = h->mdl[f] = G3DMdl_Create(res, 0, res);
        NNS_G3dMdlSetFlagAll(*(void **)(*(u8 **)((u8 *)mdl + 4) + 4), 0);   /* as B2's loader (0x021B3E72) */
        h->act[f] = G3DActor_Create(mdl, 0, 0);
    }
    h->vtcb = GFL_VBlankTCBAdd(vblank, h, VBLANK_PRI);
    return tcb;
}

#else   /* built without the balloon models (tools/follower_emotes.py) */

void *emote_hgss_start(void *field, void *fa, u32 icon)
{
    (void)field;
    (void)fa;
    (void)icon;
    return 0;
}

#endif
