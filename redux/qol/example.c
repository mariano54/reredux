/* Example qol module (example.py): two counters, readable at the addresses build/qol/LANG/
 * qol_map.json lists (symbols example_frames, example_field_frames):
 *   example_frames        +1 per main-loop frame (a FRAME function, called by core.c)
 *   example_field_frames  +1 per field frame: overlay 36 FieldRoutine_Run's call of
 *                         sub_203D5E4 is redirected here (a BL patch), and we call it on. */
#include "qol.h"

void sub_203D5E4(void);          /* example.py SYMS */

u32 example_frames;
u32 example_field_frames;

void example_frame(void)
{
    example_frames++;
}

void example_field_hook(void)
{
    example_field_frames++;
    sub_203D5E4();
}
