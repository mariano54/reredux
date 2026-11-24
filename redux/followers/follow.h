/* Black 2 (IREO) functions used by the follower code. Addresses are in syms.ld (Thumb, bit 0 set);
 * names follow swan's White 2 symbols, ported to Black 2. */
#ifndef FOLLOW_H
#define FOLLOW_H

typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;
typedef signed short s16;
typedef signed int s32;
typedef signed char s8;

typedef struct { u16 x; s16 y; u16 z; } GPos;

/* PokeParty_GetParam / SetParam field ids */
#define PF_PID          0x00
#define PF_SPECIES      0x05
#define PF_ITEM         0x06
#define PF_FRIENDSHIP   0x09
#define PF_IS_EGG       0x4C
#define PF_SEX          0x6E    /* 0 male, 1 female, 2 genderless */
#define PF_FORME        0x6F
#define PF_NATURE       0x70
#define PF_MOOD         0x9C    /* s8, HGSS MON_DATA_MOOD (box offset 0x86, unused by B2) */
#define PF_STATUS       0x9D    /* 0 none, 1 paralysis, 2 sleep, 3 freeze, 4 burn, 5 poison */
#define PF_LEVEL        0x9E
#define PF_NOW_HP       0xA0
#define PF_MAX_HP       0xA1
#define PF_TYPE1        0xAE
#define PF_TYPE2        0xAF

/* ARM9 */
void *GSYS_GetGameData(void *gsys);
int GSYS_GetEventRunningFlag(void *gsys);
void *GameData_GetParty(void *gd);
void *GameData_GetEventWork(void *gd);
int EventWork_FlagGet(void *ew, u32 flag);
u32 PokeParty_GetPkmCount(void *party);
void *PokeParty_GetPkm(void *party, u32 idx);
u32 PokeParty_GetParam(void *pkm, u32 field, u32 data);
void PokeParty_SetParam(void *pkm, u32 field, u32 value);
int PokeParty_IsRare(void *pkm);
void *GameData_GetBag(void *gd);
void *GameData_GetBadges(void *gd);
u32 GameData_GetSeason(void *gd);
int isBadgeObtained(void *badges, u32 n);
u32 BagSave_GetItemCountByID(void *bag, u32 item, u32 heap);
u32 GetItemParam(u32 item, u32 param, u32 heap);
u32 GFL_RandomLC(u32 max);
u32 DayPeriod_Now(u32 season);
void GFL_ArcSysReadRange(void *dest, u32 arc, u32 dat, u32 offset, u32 length);
void GFL_SndSEPlay(u32 se);
int Snd_IsLoading(void);    /* PokeVoice_Play busy-waits while this is set */
u16 PokeVoice_Play(u16 species, u16 form, u8 pan, int chorus, s32 chorusVol, s32 chorusSpeed, int reverse, void *chatter);
void PokeVoice_AdjustSpeed(u16 h, s32 delta);
s32 PokeVoice_GetSpeed(u16 h);
int PokeVoice_IsPlaying(u16 h);
void VM_SetNativeCallback(void *vm, int (*cb)(void *vm, void *env));

/* OVL_12 (actor system) */
void *CreateNewActorByParam(void *sys, s16 x, s16 z, u16 dir, u16 uid, u16 obj, u16 mv, u16 zone);
void DeleteActor(void *actor);
void *FindFieldActor(void *sys, u16 uid);
void *FindPlayerFieldActor(void *sys);
void SetActorFlag(void *actor, u32 flag);
void ClearActorFlag(void *actor, u32 flag);
int CheckActorFlag(void *actor, u32 flag);
void SetActorMovementFlag(void *actor, u32 flag);
int CheckActorMovementFlag(void *actor, u32 flag);
u16 GetActorFaceDir(void *actor);
void SetActorFaceDir(void *actor, u16 dir);
u32 GetCachedTileUnderActor(void *actor);   /* low 16 bits class, high 16 bits flags */
u16 FldAct_GetObjCode(void *actor);
u16 FldAct_GetAcmd(void *actor);
int FldAct_CanSetAcmd(void *actor);
void FldAct_SetAcmd(void *actor, u16 code);
u16 GetActorMoveCode(void *actor);
void GetActorInitGPos(void *actor, GPos *out);
void FldAct_GetGPos(void *actor, GPos *out);
void SetActorGPos(void *actor, s16 x, s16 y, s16 z, u16 dir);
u32 ActorRouteCollCheck(void *actor, s16 x, s16 y, s16 z, u16 dir);   /* 0 = the actor can step there */
void SetActorHidden(void *actor, int hidden);
void SetActorSCRID(void *actor, u16 scrid);
void FldAct_UpdateBlInfoForNewObjCode(void *actor, u16 obj);
void FldAct_SetWPosOffset(void *actor, const s32 *vec);  /* fx32 x, y, z */
void follow_wofs_hook(void *actor, s32 *vec);            /* build_followers.py WOFS_HOOK */

/* OVL_36 (field) */
void Field_UpdateActors(void *field);
u32 FieldPlayer_GetExState(void *player);
void Field_ToggleCycling(void *field);      /* what using the Bicycle does (test builds) */
void *Field_GetFieldEffects(void *field);
void *FLDEFF_GYOE_SetMMdlAuto(void *effects, void *actor, u32 type, int play_se);
int FLDEFF_GYOE_CheckEnd(void *tcb);
/* Every actor's ground shadow is a field-effect task (OV36_FUN_021A3BF0) drawing one billboard of the
 * shadow resource; its work: +0x04 the shadow effect's data (+0x14 its BlActScene), +0x08 the actor,
 * +0x14 the billboard's index in that scene (0xFFFF: none). build_followers.py points the task
 * descriptor's init / delete at follow_shadow_init / follow_shadow_delete. */
void FieldEffect_ShadowInit(void *task, void *work);
void FieldEffect_ShadowDelete(void *task, void *work);
void BlActScene_SetObjectSize(void *scene, u16 idx, const s16 *sx, const s16 *sy);   /* ARM9, fx16 */
void follow_shadow_init(void *task, void *work);
void follow_shadow_delete(void *task, void *work);

/* GameEvent callbacks: (event, &state, work) -> 1 when finished. build_followers.py points the
 * events below at our wrappers (follow.c), which call these. */
int EventMapChangeWarp_Callback(void *ev, int *state, void *work);     /* OVL_35: doors, stairs, warp tiles */
int EventMapChangeWarpPad_Callback(void *ev, int *state, void *work);  /* OVL_35 */
void *EventFly_Create(void *use, void *params);                        /* OVL_12 field-move table */
int EventFly_Callback(void *ev, int *state, void *work);               /* OVL_33 */
int EventSweetScent_Callback(void *ev, int *state, void *work);        /* OVL_33 */


/* script VM */
void *GSYS_GetField(void *gsys);
void *FieldScriptEnv_GetGameSystem(void *env);
u16 VM_ReadU16(void *vm);
u16 *ScriptReadVar(void *vm, void *env);
u16 ScriptReadAny(void *vm, void *env);

#endif
