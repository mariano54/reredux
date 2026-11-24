"""ReRedux loadspeed (loadspeed.c): shorter loading on warps (doors, stairs, gates, ...) and after battles.
Needs speed.c (speed_dbg; its DoorEnterSeq / DoorExitSeq wrappers call ls_door_enter / ls_door_exit*).

Measured in melonDS (headless, interpreter, cycle profile + card log; build/scripts/warpspeed/, README
"ReRedux: loading"). A map change reads 0.9-1.7 MB from the card (the 344 KB field overlay 36, map models
and textures, field effects, NPC sprites, the next BGM, ...). With Black 2's header card timing (1TROM:
gap1 0x657 = 1623 card clocks before every 512-byte page) the reads took 33-59 frames of a 60-120 frame
load, the CPU polling the card meanwhile. DeSmuME doesn't time card reads.

Always on (no visible or audible change, same data):
  - card timing: the header's ROM control words (0x60 normal reads, 0x64 KEY1, 0x6E secure delay) are
    the SDK's MROM values (0x00586000 / 0x001808F8 / 0x051E) instead of 1TROM (0x00416657 / 0x081808F8 /
    0x0D7E): 10720 -> 2740 bus cycles per page. MROM is one of the SDK's two retail settings (mask-ROM
    carts); emulators and flashcarts run MROM games. The game copies 0x60 into every read command.
  - Pokémon and trainer-record crypto / checksum loops in ARM, a word at a time (same results): entering
    a Pokémon Center the medal checks decrypt every box slot and the records (15 -> 6 frames);
  - the route gates' electronic sign: its bitmap re-layout without 4 library divisions per byte (same
    bitmap; 15 frames per gate entry).
Under the speed-ups flag 0x5DA (set = OFF):
  - the BGM change of a warp ("prepare": fade out, then load the next BGM) fades out in 30 sound frames,
    not 60; entering a door makes that request as the door starts to open, not after the walk-in. The
    sound driver counts main-loop frames, which nearly stop while a map loads, so vanilla's fade ended
    ~35 frames after the map was ready. The music still fades out completely before the next BGM;
  - one 30 Hz event update per state: the steps of EventMapChangeCore, EventFieldOpen, EventFieldSndWait,
    the building fade-in's last steps and DoorExitSeq's black part run in the same update (return 2);
  - DoorExitSeq (black screen) stops the camera trace at once instead of replaying its queue (12 f)."""

FRAME = ['ls_frame']
SYMS = {
    'ls_SendRequest': 0x0202EC7D,       # ARM9 FieldSnd_SendRequest(fs, cmd, bgm, fadeOut, [sp] fadeIn)
    'ls_BGMPrepare': 0x0202FFC9,        # ARM9 FUN_0202FFC8(fs, gd, zone, season): request 6, fade-out 60
    'ls_XfadeCallback': 0x021B8E11,     # OVL_36 building fade-in event (crossfade + LCD / touch screen steps)
    'ls_SndWaitCallback': 0x0202FEBD,   # ARM9 EventFieldSndWait (waits for FieldSnd idle)
    'ls_FieldOpenCallback': 0x0201944D, # ARM9 EventFieldOpen_Callback
    'ls_MapCoreCallback': 0x0217CFF1,   # OVL_35 EventMapChangeCore_Callback
    'ls_BmpRelayout': 0x0216A005,       # OVL_12 FUN_0216A004(src bitmap, dst bitmap): gate sign re-layout
}

# ROM header card timing: SDK 1TROM -> MROM (tools/qol_build.py HEADER)
HEADER = {
    0x60: (bytes.fromhex('57664100'), bytes.fromhex('00605800')),   # normal ROMCTRL 0x00416657 -> 0x00586000
    0x64: (bytes.fromhex('f8081808'), bytes.fromhex('f8081800')),   # KEY1 ROMCTRL 0x081808F8 -> 0x001808F8
    0x6E: (bytes.fromhex('7e0d'), bytes.fromhex('1e05')),           # secure area delay 0x0D7E -> 0x051E
}

B = bytes.fromhex
PATCHES = [
    # Pokémon / record crypto and checksums: ARM loops, same results (loadspeed.c; always on)
    dict(where='arm9', addr=0x0201ECDC, kind='jump', expect=B('0fb4f8b5051c00244e080ad0'), target='ls_crypt',
         note='PML crypt (Pokemon data) -> ARM loop'),
    dict(where='arm9', addr=0x0204411C, kind='jump', expect=B('0fb4f8b5051c00244e080ad0'), target='ls_crypt',
         note='records crypt -> ARM loop'),
    dict(where='arm9', addr=0x0201ED28, kind='jump', expect=B('18b4002200234c0807d05900'), target='ls_sum16',
         note='PML checksum -> ARM loop'),
    dict(where='arm9', addr=0x02044100, kind='jump', expect=B('18b400230024002904d9025d'), target='ls_sum8',
         note='records checksum -> ARM loop'),
    dict(where='ov12', addr=0x0216A114, kind='bl', orig=0x0216A005, target='ls_bmp_relayout',
         note='gate sign bitmap re-layout without divisions'),
    dict(where='arm9', addr=0x0202FFFA, kind='bl', orig=0x0202EC7D, target='ls_prepare_req',
         note='warp BGM prepare: fade-out 60 -> 30'),
    dict(where='ov36', addr=0x0219F74A, kind='bl', orig=0x0202FFC9, target='ls_door_prep_hook',
         note='DoorEnterSeq state 6: BGM prepare (skipped when made at the door start)'),
    dict(where='ov36', addr=0x021B8A38, kind='ptr', orig=0x021B8E11, target='ls_xfade',
         note='building fade-in event: steps 2-6 in one update'),
    # one event update per state: chained (loadspeed.c chain())
    dict(where='arm9', addr=0x0202FF14, kind='ptr', orig=0x0202FEBD, target='ls_sndwait',
         note='EventFieldSndWait: done in the same update'),
    dict(where='arm9', addr=0x020194C0, kind='ptr', orig=0x0201944D, target='ls_fieldopen',
         note='EventFieldOpen (headless): ready -> done in the same update'),
    dict(where='arm9', addr=0x020194EC, kind='ptr', orig=0x0201944D, target='ls_fieldopen',
         note='EventFieldOpen: ready -> done in the same update'),
    dict(where='ov35', addr=0x0217D2D4, kind='ptr', orig=0x0217CFF1, target='ls_mapcore',
         note='EventMapChangeCore: states 1-4 chained'),
]
