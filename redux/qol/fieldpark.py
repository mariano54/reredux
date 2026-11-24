"""ReRedux test module (fieldpark.c): parks the ARM9 after every completed field update so that an emulator
harness can compare main RAM update by update (e.g. 60 fps draws on / off). Built only with --with fieldpark."""

ENABLED = False
FRAME = ['fieldpark_frame']
