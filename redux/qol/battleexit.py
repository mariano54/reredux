"""ReRedux battleexit (battleexit.c): a shorter black screen after a battle, under the speed-ups flag
0x5DA (set = OFF). Needs speed.c (speed_dbg.override).

Battle -> field, measured in DeSmuME (wild win, Route 19; EventBattleCall OVL_12 0x02168BAC states):
  t0 last lit battle frame -> battle fade-out 16 f (ov167 0x02199CD4 state 1, 1 step/frame)
  -> 19 f black: the battle waits for its BGM fade-out (GFL_SndBGMFadeOut(30), state 2) -> teardown
  -> 7 f post-battle proc (ov166, state 4) -> 4 f states 5-8 -> 69 f EventFieldOpen (ov36 and map data
  read from the card, CPU-bound) -> 28 f EventBGMFadeWait (state 9: the field BGM pop first fades out the
  battle BGM that is already stopped, 30 sound frames stretched by the load's lag frames, then reloads the
  field BGM, 10 f) -> 12 f field fade-in (state 10, CallFieldMapEntranceInTransition) = 155 f
  (vanilla Black 2 160, Blaze Black 2 Redux 159).
With the speed-ups on:
  - battle fade-out 2 steps per frame (8 f; ov167 0x02199D66 -> bx_btl_fade_step). The battle BGM still
    fades out over vanilla's 30 sound frames before the battle tears down (10 cut the music off);
  - the field BGM pop (ov12 0x02168D86, EventBGMFadePop_Create) drops its fade-out when no BGM is playing
    any more (nothing to hear): the pop runs during the field load, and the fade-in starts as soon as the
    field is ready. A BGM that still plays (after a catch the victory music goes on through the Pokédex
    screens) keeps vanilla's 30-frame fade-out. Defeat (whiteout, EventBGMFadeStop) is unchanged.
  - EventBattleCall states 9 -> 10 -> 11 and EventBGMFadeWait run their steps in one event tick (a result
    of 2 re-runs the current event at once) instead of one 30 Hz tick each.
Field -> battle: the battle intro's fade-in from white (ov167 0x021D12F8, GFL_FadeSet wait 2) runs at
wait 0. The encounter effect itself is qol2's.
Evidence and the harness: build/battleexit/, build/scripts/battleexit/ (measure.py, analyze.py)."""

FRAME = ['bx_frame']
SYMS = {
    'bx_SndBGMIsPlaying': 0x02005FA9,           # ARM9 GFL_SndBGMIsPlaying
    'bx_EventBGMFadePop_Create': 0x0202FE85,    # ARM9 (fade-in +0xC = 60, fade-out +0xE = 30 in its data)
    'bx_GameEvent_GetData': 0x02016EDD,         # ARM9
    'bx_FadeSet': 0x0204E061,                   # ARM9 GFL_FadeSet(mode, from, to, wait)
    'bx_EventBattleCall_Callback': 0x02168BAD,  # OVL_12
    'bx_EventBGMFadeWait_Callback': 0x0202FF19, # ARM9
}

# the 7 GameEvent_Create(..., EventBattleCall_Callback, 0x2C) literals in OVL_12 (wild, trainer, ... battles)
BATTLECALL_LITERALS = (0x02168640, 0x02168818, 0x0216885C, 0x021688A4, 0x0216891C, 0x02168960, 0x02168ABC)

PATCHES = [
    *[dict(where='ov12', addr=a, kind='ptr', orig=0x02168BAD, target='bx_battlecall',
           note='EventBattleCall: chain states 9 -> 10 -> 11 in one tick') for a in BATTLECALL_LITERALS],
    dict(where='arm9', addr=0x0202FF70, kind='ptr', orig=0x0202FF19, target='bx_fadewait',
         note='EventBGMFadeWait: done -> parent in the same tick'),
    # battle proc exit (ov167 0x02199CD4): state 0 BGM fade-out, state 1 brightness steps
    # (battle end: the BGM fade-out stays vanilla's 30 frames; 10 cut the music off)
    dict(where='ov167', addr=0x02199D66, kind='bl', expect=bytes.fromhex('501ea051'), target='bx_btl_fade_step',
         note='battle end: fade-out 2 steps per frame'),
    # EventBattleCall state 7: EventBGMFadePop_Create(gsys)
    dict(where='ov12', addr=0x02168D86, kind='bl', orig=0x0202FE85, target='bx_bgm_pop',
         note='after battle: field BGM pop, no fade-out of silence'),
    # battle intro fade-in from white/black (FUN_021D12F8's two GFL_FadeSet calls)
    dict(where='ov167', addr=0x021D130E, kind='bl', orig=0x0204E061, target='bx_intro_fade',
         note='battle intro fade-in wait 2 -> 0'),
    dict(where='ov167', addr=0x021D131C, kind='bl', orig=0x0204E061, target='bx_intro_fade',
         note='battle intro fade-in wait 2 -> 0'),
]
