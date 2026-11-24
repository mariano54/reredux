/* Black 2 (IREO) addresses; Thumb functions have bit 0 set. Verified against the B2 disassembly via
   the swan White 2 symbol map (W2 -> B2 deltas: ARM9 0 / -0x2C, OVL_12 -0x40, OVL_36 -0x40). */

/* ARM9 */
GSYS_GetEventRunningFlag = 0x02016ABD;
GSYS_GetGameData = 0x02016AD9;
GameData_GetParty = 0x0201735D;
GameData_GetEventWork = 0x02017395;
EventWork_FlagGet = 0x020191AD;
PokeParty_GetParam = 0x0201CCF9;
PokeParty_IsRare = 0x0201CDAD;
PokeParty_SetParam = 0x0201CD1D;       /* fixes the checksum */
GameData_GetBag = 0x02017355;
GameData_GetBadges = 0x02017975;       /* the save block isBadgeObtained reads (s00D5_TrainerCardHasBadge) */
GameData_GetSeason = 0x020173AD;
isBadgeObtained = 0x0200C97D;
BagSave_GetItemCountByID = 0x02008539;
GetItemParam = 0x020267F1;
GFL_RandomLC = 0x02005749;             /* [0, max) */
DayPeriod_Now = 0x02015A91;            /* 0 morning, 1 day, 2 evening, 3 night, 4 late night */
GFL_ArcSysReadRange = 0x0204A941;
BlActScene_SetObjectSize = 0x0204EA5D; /* GFL BBD SetObjectSiz: object +0x12 / +0x14 = *sx, *sy (fx16) */
GFL_SndSEPlay = 0x02006255;
Snd_IsLoading = 0x02005CBD;
PokeVoice_Play = 0x020069F5;
PokeVoice_AdjustSpeed = 0x02006B5D;
PokeVoice_GetSpeed = 0x02006BAD;
PokeVoice_IsPlaying = 0x02006C41;
VM_SetNativeCallback = 0x02015A89;
PokeParty_GetPkmCount = 0x0201FDF9;
PokeParty_GetPkm = 0x0201FF09;

/* OVL_12 */
CreateNewActorByParam = 0x02166881;
DeleteActor = 0x02166941;
SetActorFlag = 0x02166FC9;
ClearActorFlag = 0x02166FD1;
CheckActorFlag = 0x02166FDD;
SetActorMovementFlag = 0x02166FE9;
CheckActorMovementFlag = 0x02166FFD;
FldAct_GetObjCode = 0x02167019;
FldAct_GetAcmd = 0x0216721D;
FldAct_CanSetAcmd = 0x02166E45;
FldAct_SetAcmd = 0x02166E89;
GetActorMoveCode = 0x02167021;
GetActorFaceDir = 0x02167079;
SetActorFaceDir = 0x02167059;
GetCachedTileUnderActor = 0x02167235;
GetActorInitGPos = 0x0216725D;
FldAct_GetGPos = 0x02167295;
SetActorHidden = 0x02167535;
SetActorSCRID = 0x02167035;
FindFieldActor = 0x02167A15;
FindPlayerFieldActor = 0x02167A61;
SetActorGPos = 0x02167C3D;
ActorRouteCollCheck = 0x0215E485;
EventFly_Create = 0x0215966D;          /* field-move table entry 8 (_0216CA88 / _0216CAE0) */
FldAct_UpdateBlInfoForNewObjCode = 0x02167DE9;
FldAct_SetWPosOffset = 0x0216732D;     /* actor +0x50 = *vec (the billboard sprite offset) */

/* OVL_36 */
Field_UpdateActors = 0x02180B01;
FieldPlayer_GetExState = 0x0219A6C5;
Field_ToggleCycling = 0x02180435;
Field_GetFieldEffects = 0x0218050D;
FLDEFF_GYOE_SetMMdlAuto = 0x021B3F65;   /* (effects, actor, type 0 ! 1 ? 2 note 3 ..., play SE) -> task */
FLDEFF_GYOE_CheckEnd = 0x021B3FB5;
FieldEffect_ShadowInit = 0x021A3C21;    /* per-actor shadow task (descriptor _021D0530): init, delete */
FieldEffect_ShadowDelete = 0x021A3CB5;

/* script VM (ARM9 / OVL_12) */
VM_ReadU16 = 0x020159E9;
GSYS_GetField = 0x02016AF1;
FieldScriptEnv_GetGameSystem = 0x0215516D;
ScriptReadVar = 0x021548E9;
ScriptReadAny = 0x02154911;

/* OVL_35 (map change events) */
EventMapChangeWarp_Callback = 0x0217D2D9;
EventMapChangeWarpPad_Callback = 0x0217D931;

/* OVL_33 */
EventFly_Callback = 0x02178965;
EventSweetScent_Callback = 0x02178615;
