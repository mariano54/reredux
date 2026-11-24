# Follower movement and field cut-in drawing, 2026-10-23

The reported symptoms were a follower lurching during a straight run and horizontal lines
on the main screen during Bianca's first Pokédex handover in WatermelonDS. The follower
symptom was reproduced. A separate cut-in particle-timing bug was reproduced during the
investigation. The exact horizontal-line symptom has not been established by these replays.

## Follower drawing offset

Medium followers have an extra half-tile drawing offset to maintain visual spacing.
`update_offset` formerly derived this offset from actor grid positions. The two actors
advance their grid positions at different moments, so their apparent grid separation
alternates between one and two tiles even when their world-space separation is steady.
The two-tile case cleared the target offset for one logic tick, producing a visible lurch.

The correction derives alignment and direction from the continuous world positions.
It retains the existing easing, size rules, talk motions, and restriction against moving
the sprite further away from the camera when following north.

Measured with a medium Charizard follower on a straight Floccesy street:

| Movement | Physical separation | Earlier drawn separation | Corrected drawn separation |
| --- | --- | --- | --- |
| Walking right | 20 units | 24–26 units, repeating at tile boundaries | 26 units |
| Running right | 21 units | 25–27 units, repeating at tile boundaries | 27 units |

These are world-coordinate drawing units, not screen pixels. Measurements include actor
world position, world-position offset, and signed model offset. Only measuring world
position misses the bug. Small Oshawott and large Steelix controls also maintain a steady
drawn separation. The fix does not assert that every species and route has been tested.

`tests/perf/follower_motion.py` cold boots the supplied ROM using a copied QA battery save,
changes the in-memory lead, and records both physical and drawn gaps. Example:

```sh
python redux/tests/perf/follower_motion.py --rom redux/build/out/redux3_en.nds \
  --lib /path/to/libperf.dylib --save /path/to/disposable-qa.sav \
  --out redux/build/follower-run.json --run
```

Omit `--run` for walking. `--species 501` and `--species 208` exercise the small/large
controls. A pre-fix ROM fails on the periodic drawn-gap change while keeping a steady
physical gap. The input save must have a living party; the harness never overwrites it.

## Field cut-in timing

The ordinary field particle call was already split into draw-only and calculate-and-draw
paths for 60 fps interpolation. Field cut-ins use a different render callback that still
calls the native calculate-and-draw entry point. Drawing that path twice advances the
particles twice; in the handover, the stars finish before the Pokédex stops rotating.

The engine selects its render callback using `Field + 0x13C`: 0 is the ordinary field,
1 a field cut-in, and 2 an encounter effect. In overlay 36, `FieldG3D_RenderPhase2`
at `0x021808F8` dispatches through the callback table at `0x021C9ED0`. The cut-in callback
at `0x02181238` calls particle processing at `0x021BB674` before `Fld3DCi_Draw` at
`0x021BB7D4`. These addresses apply to the English-engine Redux/ReRedux builds, including
the Japanese text port.

The interpolation hook now uses the native split drawing path for modes 1 and 2 and
invalidates its interpolation history on mode changes. Mode 0 resumes ordinary 60 fps
field drawing. This preserves special-effect timing without attempting to convert their
stateful draw routines to 60 fps.

Both language opening replays observe the Pokédex cut-in and assert native drawing mode.
Story and gameplay checks cover the rival battle, return to the field, menus, saving,
and continuing. Software-rendered local replays and Odin3 WatermelonDS 0.8.0.rc3 Vulkan
recordings show the particle-timing correction. The Odin comparison used separate ROM
names and a separate QA battery save, with the existing player saves backed up.

The original handover was also replayed at Vulkan 1× and 6×. The recorded frames do not
identify a definite horizontal-line artifact, so there is no established causal claim
linking the reported lines to the corrected timing bug or to resolution scaling.
