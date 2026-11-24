"""Example qol module: counters proving the block and the hooks work (see example.c).
Disabled by default; built by `build_redux3.py --with example` and in --test builds."""

ENABLED = False
FRAME = ['example_frame']
SYMS = {'sub_203D5E4': 0x0203D5B9}       # ARM9, called by FieldRoutine_Run every field frame
PATCHES = [
    # OVL_36 FieldRoutine_Run (0x0217FF64): `bl sub_203D5E4` right before the follower hook
    dict(where='ov36', addr=0x0217FFA6, kind='bl', orig=0x0203D5B9, target='example_field_hook',
         note='field frame counter'),
]
