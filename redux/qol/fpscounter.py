"""ReRedux debug FPS counter (fpscounter.c): a few 8x8 sprites in the top-left corner of the top screen showing
`P U flags` once per second (counted over the last 60 VBlanks):
  P  pictures per second: 3D buffer swaps the main loop issued (GFL_G3DSysCheckSwapBuffers with a swap requested),
     i.e. distinct 3D pictures shown. 60 = fps60 drawing every frame, 30 = vanilla rhythm.
  U  field logic updates per second (FieldRoutine_Run calls seen by fps60; 30 = normal, more under R turbo).
  flags  F fps60 fallback to vanilla drawing active (real pictures didn't fit), T R turbo on,
         L in-between pictures left out for lack of time this second, S left out because nothing moved.
Debug tool, not in the release ROMs: only with `build_redux3.py --with fpscounter`."""

ENABLED = False
FRAME = ['fpsc_frame']
SYMS = {
    'GFL_G3DSysCheckSwapBuffers': 0x02049AB9,   # ARM9: SWAP_BUFFERS write when the G3D system requested one
    'FPSC_MainVBlank': 0x02005259,              # ARM9: TwlMain's after-VBlank-wait call (GFL VBlank work)
}
PATCHES = [
    dict(where='arm9', addr=0x02005176, kind='bl', orig=0x02049AB9, target='fpsc_swap',
         note='TwlMain loop: GFL_G3DSysCheckSwapBuffers -> count the 3D swaps'),
    dict(where='arm9', addr=0x020051A4, kind='bl', orig=0x02005259, target='fpsc_vblank',
         note='TwlMain loop: after the VBlank wait -> count VBlanks, draw the counter sprites'),
]
