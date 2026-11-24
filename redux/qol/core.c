/* ReRedux qol core: the block header (first bytes of the block, at QOL_BASE) and the per-frame
 * dispatcher. TwlMain's loop calls an empty function (nullsub_4) once per frame; core.py points
 * that call at qol_main_frame, which runs every module's FRAME functions in module order. */
#include "qol.h"

extern char __qol_end[];

__attribute__((section(".qol_header"), used))
QolHeader qol_header = {
    QOL_MAGIC, QOL_VERSION, 0, (u32)__qol_end, qol_frame_hooks, qol_modules, {0, 0},
};

void qol_main_frame(void)
{
    const qol_fn *f;
    qol_header.frames++;
    for (f = qol_frame_hooks; *f; f++)
        (*f)();
}
