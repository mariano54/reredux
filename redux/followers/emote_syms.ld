/* Black 2 (IREO) addresses used by emote.c. Every one was read in pokeblack2/asm (body checked);
   Thumb functions have bit 0 set. Some repeat ballfx_syms.ld with the same value (allowed). */

/* OVL_36: field effect 4 (fldeff_gyoe, the ! ? note ... balloons) */
FieldEffects_TCBCreate = 0x021A38B9;        /* (fx, vtable, pos, user, params, pri) -> task (0xD4-byte slot, work at +0x18, <= 0xA0 bytes); calls init, which calls update once */
FieldEffects_GetField = 0x021A3721;         /* fx + 0x08 */
FieldEffects_GetArc = 0x021A3731;           /* fx + 0x0C: ArcTool of a/0/7/4 */
FLDEFF_GYOE_Init = 0x021B3FC9;              /* vtable +4: copies the 0x1C-byte params, vy = 6.0, runs update */
FLDEFF_GYOE_UpdateAuto = 0x021B4035;        /* _021D1028 +0xC: pop, 30-tick hold, then deletes the task */
FLDEFF_GYOE_Draw = 0x021B4079;              /* draws *(handle + 0x24 + type * 4), depth bias from u16 handle + 0x34 */

/* OVL_12 */
FldAct_GetSnapshot = 0x02167D89;            /* (actor, u16[3] out): what FLDEFF_GYOE's update compares */

/* ARM9 GFL G3D */
G3DRes_ReadArcTool = 0x02049385;            /* (arctool, member) -> res */
G3DRes_AllocTex = 0x020495A1;               /* texture + palette VRAM keys, no transfer */
G3DRes_TransTex = 0x020495F1;               /* transfer to the keys (GX_BeginLoadTex: VBlank only); sets the loaded flags */
G3DRes_FreeTex = 0x02049535;                /* releases the keys whose loaded flag is set */
G3DRes_Free = 0x02049405;
G3DMdl_Create = 0x0204972D;                 /* (res, model index, texture res) */
G3DMdl_Free = 0x020497D5;
G3DActor_Create = 0x020498B9;               /* (mdl, anm list, anm count) */
G3DActor_Free = 0x02049935;
NNS_G3dMdlSetFlagAll = 0x02068435;          /* (NNSG3dResMdl, flag): per-material flag, B2's balloon loader clears it (HGSS: fog off) */

/* ARM9 */
GFL_VBlankTCBAdd = 0x020056FD;              /* (fn(tcb, data), data, pri) -> tcb */
GFL_TCBRemove = 0x0203A6A9;
GFL_IsCardIrqEnabled = 0x02005CF1;          /* the field's VRAM TCBs skip VBlanks with a card transfer running */
