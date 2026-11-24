/* Black 2 (IREO) addresses used by ballfx.c. Every one was read in pokeblack2/asm (body checked, not
   only the W2 -> B2 map); Thumb functions have bit 0 set. */

/* OVL_36 field */
Field_GetFieldEffects = 0x0218050D;                 /* field + 0x9C */
Field_GetG3DObjSys = 0x02180515;                    /* field + 0x140 */
FieldEffects_GetArc = 0x021A3731;                   /* fx + 0x0C: ArcTool of a/0/7/4 */
FieldBlAct_GetBlActSys = 0x02193BCD;                /* + 0x04 */
FieldG3DObjResRequest_Clear = 0x021C059D;           /* 0x24-byte request */
FieldG3DObjResRequest_SetModel = 0x021C05AD;
FieldG3DObjResRequest_SetAnmArc = 0x021C05B5;
FieldG3DObjResRequest_AddAnm = 0x021C05B9;
FieldG3DObjSystem_AddResGroup = 0x021C0051;         /* -> first slot with MdlRes == 0 (0 also when full) */
FieldG3DObjSystem_FreeResGroup = 0x021C005D;
FieldG3DObjSystem_AddObj = 0x021C006D;              /* pending (state 2) while its group's textures wait for VBlank */
FieldG3DObjSystem_FreeObj = 0x021C0105;             /* frees state-1 objects only */
FieldG3DObjSystem_StepObjAnm = 0x021C0171;          /* 1 while playing, 0 at the last frame */
FieldG3DObjSystem_SetAnmFrame = 0x021C0221;

/* OVL_12 actors */
FldAct_GetFieldBlAct = 0x0216737D;                  /* actor system + 0x28 */
FldAct_GetBlActIdx = 0x02167201;                    /* renderer vtable +0x14 = u16 at actor + 0xC4 */

/* ARM9 */
BlActSys_GetScene = 0x0204F225;                     /* + 0x04 */
GFL_VBlankTCBAdd = 0x020056FD;                      /* (fn(tcb, data), data, pri) -> tcb */
GFL_TCBRemove = 0x0203A6A9;
GFL_IsCardIrqEnabled = 0x02005CF1;                  /* IE & 0x80000 */
GX_BeginLoadTexPltt = 0x020762B5;                   /* NitroSDK; maps the palette bank to LCDC */
GX_EndLoadTexPltt = 0x02076335;
GX_TexPlttLcdcAddr = 0x0214C074;                    /* sTexPltt.lcdc (struct at 0x0214C06C + 8) */
