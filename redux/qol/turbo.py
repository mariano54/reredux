"""ReRedux turbo (turbo.c): R toggles 2x game speed in the field and in standalone battles, sound
at normal speed. Off while event flag 0x5DB is set. The battle hook also carries the speed module's
extra tick every 10th frame. Research: build/research_speed.md section 3."""

FRAME = ['turbo_frame']
SYMS = {
    'FieldRoutine_RunAltFrame': 0x0218011D,     # OVL_36
    'GFL_PTC_ActiveCount': 0x0204FFFD,          # ARM9: live particle managers
    'GFL_PTC_CalcAll': 0x02050045,              # ARM9: SPL calc of every manager (no draw)
    'GameData_Is30FPSSkipFrame': 0x02017459,    # ARM9: gd+0x1CE counter (0 = events run this frame)
}
PATCHES = [
    dict(where='ov36', addr=0x021803C2, kind='bl', expect=b'\x90\x47\x06\x1c', target='turbo_call',
         note='Field_CallRoutines: Run + RunAltFrame in one frame'),
    dict(where='arm9', addr=0x020169C2, kind='bl', orig=0x02017459, target='turbo_skip_hook',
         note='GSYS_Update: events this frame? (low-latency re-phase on a new press)'),
    dict(where='ov167', addr=0x02199C18, kind='bl', expect=b'\x28\x1c\x88\x47', target='turbo_battle_hook',
         note='battle proc main: extra main-loop tick'),
    dict(where='ov168', addr=0x021DF284, kind='bl', orig=0x02049A99, target='turbo_draw_gate',
         note='BTLV_EFFECT_Main: no draw in the extra tick'),
]
