/* HGSS follower Poké Ball effect (HGSS ov01_0220329C modes 0-3 and the 20-frame recall task
 * ov01_02205DB4), drawn with Black 2's FieldG3DObjSystem like the field's smoke puff.
 *
 * Models (HGSS a/1/0/3 0x81 monsterball, 0x68 mb_out + 0xA4 its SRT anim) are appended to the
 * field-effect archive a/0/7/4 by tools/follower_ballfx.py, which also writes ballfx_ids.h. Both
 * resource groups are loaded per effect with deferred textures (uploaded by the field's VBlank TCB,
 * like every field effect), and freed when it ends.
 *
 * Shrink: the actor's BlAct ScaleX / ScaleY (+0x12 / +0x14), which BlActScene_Draw loads into
 * MTX_SCALE per actor and nothing rewrites after creation. Flash: the actor's 16-colour texture
 * palette (BlActMaterial.PltAddr) is saved and overwritten with white from a one-shot GFL VBlank
 * TCB through GX_BeginLoadTexPltt's LCDC mapping (CPU copy: our buffer is in ITCM, which DMA can't
 * read), and restored the same way at the end. */
#include "ballfx.h"
#include "ballfx_ids.h"     /* generated: BALLFX_DAT_BALL, BALLFX_DAT_BURST, BALLFX_DAT_BURST_ANM */

#define FX_ONE          0x1000
#define AF_HIDDEN       0x4
#define TCB_PRI         10
#define MAX_TICKS       90      /* safety stop */

/* FieldG3DObjSystem (swan field_g3dobj.h) */
#define SYS_GRP_COUNT(s)    (*(u16 *)((u8 *)(s) + 0x04))
#define SYS_OBJ_COUNT(s)    (*(u16 *)((u8 *)(s) + 0x06))
#define SYS_GRPS(s)         (*(u8 **)((u8 *)(s) + 0x08))   /* 0x2C each, +0 MdlRes */
#define SYS_OBJS(s)         (*(u8 **)((u8 *)(s) + 0x0C))   /* 0x68 each, +0 flags (bits 0-1 state), +4 group, +0x44 actor */
#define GRP_SIZE        0x2C
#define OBJ_SIZE        0x68

/* field actor */
#define ACTOR_FLAGS(a)  (*(u32 *)((u8 *)(a) + 0x00))
#define ACTOR_UID(a)    (*(u16 *)((u8 *)(a) + 0x08))
#define ACTOR_WPOS(a)   ((s32 *)((u8 *)(a) + 0x44))

enum { M_BALL, M_BURST };
#define LIVE_GRP(n)     (1 << (n))
#define LIVE_OBJ(n)     (4 << (n))

static struct {
    void *field, *sys, *actor;
    void *res[2];       /* MdlRes of our groups: recognises our slots in a rebuilt field */
    void *tcb;
    u32 plt;            /* palette offset in texture palette VRAM */
    s32 pos[3];
    u16 uid, grp[2], obj[2];
    s16 scale[2];       /* the actor's BlAct scale before the shrink */
    s8 ofs[2];
    u8 active, mode, t, n, large, dir, anim, live, op, saved;
    u16 pal[16];
} B;

static u8 *grp_at(u32 i) { return SYS_GRPS(B.sys) + GRP_SIZE * i; }
static u8 *obj_at(u32 i) { return SYS_OBJS(B.sys) + OBJ_SIZE * i; }
static u32 obj_state(u32 n) { return *(u32 *)obj_at(B.obj[n]) & 3; }

static int handles_ok(void)
{
    for (u32 n = 0; n < 2; n++) {
        if ((B.live & LIVE_GRP(n)) && *(void **)grp_at(B.grp[n]) != B.res[n])
            return 0;
        if ((B.live & LIVE_OBJ(n)) && (!obj_state(n) || *(u16 *)(obj_at(B.obj[n]) + 4) != B.grp[n]))
            return 0;
    }
    return 1;
}

static int actor_ok(void)
{
    return (ACTOR_FLAGS(B.actor) & 1) && ACTOR_UID(B.actor) == B.uid;
}

/* the actor's BlAct (struct BlAct, 0x1C bytes) and its scene */
static u8 *blact(u8 **scene)
{
    void *fb = FldAct_GetFieldBlAct(B.actor);
    void *bs = fb ? FieldBlAct_GetBlActSys(fb) : 0;
    u32 i = FldAct_GetBlActIdx(B.actor);
    if (!bs || i == 0xFFFF)
        return 0;
    *scene = BlActSys_GetScene(bs);
    return *(u8 **)(*scene + 0x08) + 0x1C * i;
}

static void grp_add(u32 n, void *arc)
{
    u32 i, cnt = SYS_GRP_COUNT(B.sys);
    for (i = 0; i < cnt && *(void **)grp_at(i); i++)
        ;
    if (i == cnt)
        return;     /* no free slot (AddResGroup would return 0 = someone else's group) */
    u32 req[9];
    FieldG3DObjResRequest_Clear(req);
    FieldG3DObjResRequest_SetModel(req, arc, n == M_BALL ? BALLFX_DAT_BALL : BALLFX_DAT_BURST);
    if (n == M_BURST) {
        FieldG3DObjResRequest_SetAnmArc(req, arc);
        FieldG3DObjResRequest_AddAnm(req, BALLFX_DAT_BURST_ANM);
    }
    B.grp[n] = FieldG3DObjSystem_AddResGroup(B.sys, req, 0);
    B.res[n] = *(void **)grp_at(B.grp[n]);
    B.live |= LIVE_GRP(n);
}

static void obj_add(u32 n)
{
    u32 i, cnt = SYS_OBJ_COUNT(B.sys);
    if (!(B.live & LIVE_GRP(n)))
        return;
    for (i = 0; i < cnt && ((*(u32 *)obj_at(i) & 3) || *(void **)(obj_at(i) + 0x44)); i++)
        ;
    if (i == cnt)
        return;
    B.obj[n] = FieldG3DObjSystem_AddObj(B.sys, B.grp[n], 0, B.pos);
    B.live |= LIVE_OBJ(n);
}

static void obj_free(u32 n)
{
    if (!(B.live & LIVE_OBJ(n)))
        return;
    if (obj_state(n) == 2)
        *(u32 *)obj_at(B.obj[n]) &= ~3;    /* still pending: FreeObj ignores it, the VBlank setup wouldn't */
    else
        FieldG3DObjSystem_FreeObj(B.sys, B.obj[n]);
    B.live &= ~LIVE_OBJ(n);
}

static void vblank(void *tcb, void *data)
{
    (void)data;
    if (GFL_IsCardIrqEnabled())
        return;     /* retry next VBlank, as the field's own VRAM TCBs do */
    GX_BeginLoadTexPltt();
    volatile u16 *p = (volatile u16 *)(GX_TexPlttLcdcAddr + B.plt);
    for (u32 i = 0; i < 16; i++) {
        if (B.op == 1) {
            B.pal[i] = p[i];
            p[i] = 0x7FFF;
        } else {
            p[i] = B.pal[i];
        }
    }
    GX_EndLoadTexPltt();
    B.saved = B.op == 1;
    GFL_TCBRemove(tcb);
    B.tcb = 0;
}

/* op 1: white (plt = palette offset), op 2: restore */
static void pal_request(u32 op, u32 plt)
{
    if (op == 1 && B.saved) {
        /* still white from the last effect: keep the saved colours, cancel its restore */
        if (B.tcb && plt == B.plt) {
            GFL_TCBRemove(B.tcb);
            B.tcb = 0;
        }
        return;
    }
    if (B.tcb) {
        if (op == 2 && B.op == 1) {     /* the white never reached VRAM */
            GFL_TCBRemove(B.tcb);
            B.tcb = 0;
        }
        return;
    }
    if (op == 2 && !B.saved)
        return;
    if (op == 1)
        B.plt = plt;
    B.op = op;
    B.tcb = GFL_VBlankTCBAdd(vblank, 0, TCB_PRI);
}

static void set_scale(u32 n)
{
    static const u16 inv[4] = {FX_ONE, FX_ONE / 2, FX_ONE / 3, FX_ONE / 4};   /* HGSS: FX32_ONE / n */
    u8 *scene, *ba = blact(&scene);
    if (ba) {
        *(s16 *)(ba + 0x12) = B.scale[0] * inv[n - 1] >> 12;
        *(s16 *)(ba + 0x14) = B.scale[1] * inv[n - 1] >> 12;
    }
}

/* forget a torn-down field's handles without touching its memory */
static void drop(void)
{
    if (B.tcb)
        GFL_TCBRemove(B.tcb);
    B.tcb = 0;
    B.saved = 0;
    B.live = 0;
    B.active = 0;
    B.ofs[0] = B.ofs[1] = 0;
}

/* end the effect on a live field */
static void stop(void)
{
    for (u32 n = 0; n < 2; n++) {
        obj_free(n);
        if (B.live & LIVE_GRP(n))
            FieldG3DObjSystem_FreeResGroup(B.sys, B.grp[n]);
    }
    B.live = 0;
    if (B.mode & 1 && actor_ok())
        set_scale(1);
    pal_request(2, 0);
    B.ofs[0] = B.ofs[1] = 0;
    B.active = 0;
}

static int valid(void *field)
{
    return field == B.field && Field_GetG3DObjSys(field) == B.sys && handles_ok();
}

void ballfx_reset(void)
{
    if (!B.active)
        return;
    if (valid(B.field))
        stop();
    else
        drop();
}

int ballfx_busy(void)
{
    return B.active || B.tcb;
}

void ballfx_offset(s32 *dx, s32 *dz)
{
    *dx = B.ofs[0];
    *dz = B.ofs[1];
}

void ballfx_start(void *field, void *actor, u32 mode, u32 large)
{
    if (B.active) {
        if (valid(field))
            stop();
        else
            drop();
    }
    void *sys = Field_GetG3DObjSys(field), *fx = Field_GetFieldEffects(field);
    if (!sys || !fx || !actor)
        return;
    if ((mode & 1) && (ACTOR_FLAGS(actor) & AF_HIDDEN))
        return;     /* HGSS: already hidden -> no effect */
    B.field = field;
    B.sys = sys;
    B.actor = actor;
    B.uid = ACTOR_UID(actor);
    B.mode = mode;
    B.large = large;
    B.dir = GetActorFaceDir(actor);
    B.t = B.n = B.anim = 0;
    s32 *w = ACTOR_WPOS(actor);
    B.pos[0] = w[0];
    B.pos[1] = w[1];
    B.pos[2] = w[2] + (6 << 12);       /* toward the camera, as HGSS and B2's smoke puff */
    void *arc = FieldEffects_GetArc(fx);
    if (mode != BALLFX_BURST)
        grp_add(M_BALL, arc);
    if (mode == BALLFX_RELEASE || mode == BALLFX_BURST)
        grp_add(M_BURST, arc);
    if (mode == BALLFX_RELEASE) {
        SetActorHidden(actor, 1);
        obj_add(M_BALL);
    } else if (mode == BALLFX_BURST) {
        obj_add(M_BURST);
    } else {
        u8 *scene, *ba = blact(&scene);
        B.scale[0] = B.scale[1] = FX_ONE;
        if (ba) {
            B.scale[0] = *(s16 *)(ba + 0x12);
            B.scale[1] = *(s16 *)(ba + 0x14);
            u32 m = *(u16 *)ba & 0x3FFF;
            u8 *mat = *(u8 **)(scene + 0x04) + 0x28 * m;
            if (mode == BALLFX_RECALL && m != 0x3FFF && *(u32 *)(mat + 0x14) == 3)  /* GX_TEXFMT_PLTT16 */
                pal_request(1, *(u32 *)(mat + 0x10));
        }
    }
    B.active = 1;
}

/* burst: from frame 0 once the object exists, until the last frame. -> 1 when finished */
static int burst_step(void)
{
    if (!(B.live & LIVE_OBJ(M_BURST)))
        return 1;
    if (obj_state(M_BURST) == 2)
        return 0;   /* textures not uploaded yet */
    if (!B.anim) {
        FieldG3DObjSystem_SetAnmFrame(B.sys, B.obj[M_BURST], 8, 0);
        B.anim = 1;
    }
    return !FieldG3DObjSystem_StepObjAnm(B.sys, B.obj[M_BURST], FX_ONE);
}

void ballfx_tick(void *field)
{
    if (!B.active)
        return;
    if (!valid(field)) {
        drop();
        return;
    }
    if (!actor_ok() || ++B.n > MAX_TICKS) {
        stop();
        return;
    }
    int done = 0;
    if (B.mode == BALLFX_RELEASE && B.t < 2) {
        /* the closed ball for 2 ticks from when it is drawn, then the burst */
        if ((B.live & LIVE_OBJ(M_BALL)) && obj_state(M_BALL) == 2)
            return;
        if (++B.t < 2)
            return;
        obj_free(M_BALL);
        obj_add(M_BURST);
        SetActorHidden(B.actor, 0);
    }
    if (B.mode == BALLFX_RELEASE || B.mode == BALLFX_BURST) {
        done = burst_step();
    } else {
        u32 t = ++B.t;
        if (t <= 4) {
            set_scale(t);
            if (B.large) {
                /* HGSS: 64x64 followers slide delta * t / 4 along their facing (1 unit N/S, 10 W/E) */
                static const s8 delta[4] = {-1, 1, -10, 10};
                s32 d = delta[B.dir & 3] * (s32)t / 4;
                B.ofs[0] = B.dir >= 2 ? d : 0;
                B.ofs[1] = B.dir < 2 ? d : 0;
            }
        }
        if (t == 4) {
            obj_add(M_BALL);
            SetActorHidden(B.actor, 1);
        }
        if (t == (B.mode == BALLFX_RECALL ? 8 : 20))
            obj_free(M_BALL);
        done = t >= 20;
    }
    if (done)
        stop();
}
