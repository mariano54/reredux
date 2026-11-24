"""ReRedux 60 fps field (fps60.c): field logic stays 30 Hz, every frame draws a whole 3D picture, the frame
after each update's logic a midpoint one (camera, billboard actors, 3D objects, model animations halfway
between the last real picture and the current state). A midpoint picture is drawn only when it fits in the frame
(per-frame time budget); vanilla 30 fps drawing while R turbo runs and while real pictures don't fit (a slow
emulator), back as soon as they do. NNS display lists go out as one GX-FIFO DMA each during the field's draws.
Tests: `fps60_dbg.want = 0` draws as vanilla, `fps60_dbg.nofast = 1` (+159) keeps B2's chunked display-list DMA."""

FRAME = ['fps60_frame']
SYMS = {
    'GFL_G3DSysResetGeometryCounter': 0x02049D15,   # ARM9
    'GCTX_HIDGetHeldKeys': 0x0203DF21,              # ARM9
    'BlActSys_Draw': 0x0204F659,                    # ARM9
    'NNS_G3dGlbSetBaseTrans': 0x020658A5,           # ARM9
    'NNS_G3dDraw': 0x02066301,                      # ARM9
    'F60_PTC_ActiveCount': 0x0204FFFD,              # ARM9: live particle managers
    'F60_PTC_DrawAll': 0x0205001D,                  # ARM9: SPL draw of every manager (no calc)
    'F60_FieldPtcMain': 0x021BB675,                 # OVL_36: veneer to GFL_PTC_Main (draw + calc)
    'Field_RenderStart': 0x021800D5,                # OVL_36
    'FieldG3D_RenderPhase1': 0x021808D1,            # OVL_36
    'FieldG3D_RenderPhase2': 0x021808F9,            # OVL_36
    'FieldCamera_CalcTransform': 0x0218578D,        # OVL_36
    'Field_CalcDepthOfs': 0x0218132D,               # OVL_36 (stored at field +0x110 by Field_RenderStart)
}
PATCHES = [
    dict(where='ov36', addr=0x0217FF9A, kind='bl', orig=0x021800D5, target='fps60_run_render',
         note='FieldRoutine_Run (paused path): Field_RenderStart -> whole midpoint picture'),
    dict(where='ov36', addr=0x021800C4, kind='bl', orig=0x021800D5, target='fps60_run_render',
         note='FieldRoutine_Run: Field_RenderStart -> whole midpoint picture'),
    dict(where='ov36', addr=0x02180182, kind='bl', orig=0x021808F9, target='fps60_alt_render',
         note='FieldRoutine_RunAltFrame: phase 2 -> whole real picture'),
    dict(where='ov36', addr=0x0218115A, kind='bl', orig=0x0204F659, target='fps60_blact_draw',
         note='FieldRenderPhase2_Fieldmap: BlActSys_Draw (field +0xC0)'),
    dict(where='ov36', addr=0x02181170, kind='bl', orig=0x0204F659, target='fps60_blact_draw',
         note='FieldRenderPhase2_Fieldmap: BlActSys_Draw (field +0xC8)'),
    dict(where='ov36', addr=0x021811EE, kind='bl', orig=0x0204F659, target='fps60_blact_draw',
         note='FieldRenderPhase2_Fieldmap: BlActSys_Draw (field +0xC4)'),
    dict(where='ov36', addr=0x0218121E, kind='bl', orig=0x021BB675, target='fps60_ptc',
         note='FieldRenderPhase2_Fieldmap: GFL_PTC_Main (the midpoint picture only draws the particles)'),
    dict(where='arm9', addr=0x02049B6C, kind='bl', orig=0x020658A5, target='fps60_basetrans',
         note='GFL_G3DSysDrawObj: NNS_G3dGlbSetBaseTrans'),
    dict(where='arm9', addr=0x02049BBE, kind='bl', orig=0x020658A5, target='fps60_basetrans',
         note='GFL_G3DSysDrawObjBBoxCull: NNS_G3dGlbSetBaseTrans'),
    dict(where='arm9', addr=0x02049D08, kind='bl', orig=0x02066301, target='fps60_nns_draw',
         note="GFL's render-object draw: NNS_G3dDraw (animation frames at the midpoint)"),
]
