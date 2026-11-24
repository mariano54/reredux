/* ReRedux test module (fieldpark.py, built only with --with fieldpark; never in the release ROMs): parks the
 * ARM9 at the end of every main-loop frame whose field routine finished an update (field parity back to the
 * Run half), with interrupts off, until the test harness clears fieldpark_dbg.parked. A melonDS harness then
 * reads main RAM at the same point of every field update, whatever the frame timing (the 60 fps draws, the
 * low-latency updates): build/w/rampark.py compares two runs update by update. */
#include "qol.h"
#include "speed.h"

#define IME     (*(volatile u32 *)0x04000208)

typedef struct {
    u8 on;              /* set by the harness */
    u8 parked;          /* 1 while parked; the harness clears it */
    u8 pad[2];
    u32 count;          /* parks so far */
    u32 field_frame;    /* qol frame of the last field routine call (kept by fieldpark_field) */
} FieldPark;

FieldPark fieldpark_dbg;
extern struct { u8 on, live, overrun, pad0; u32 field_frame; } turbo_dbg __attribute__((weak));

void fieldpark_frame(void)
{
    FieldPark *p = &fieldpark_dbg;
    void *gsys = QOL_GSYS;
    u8 *f;
    u32 ime;
    if (!p->on || !gsys || !(f = *(u8 **)((u8 *)gsys + 0x20)))
        return;
    if (!&turbo_dbg || turbo_dbg.field_frame + 1 != qol_header.frames || f[0xD9] != 0)
        return;
    ime = IME;
    IME = 0;
    p->parked = 1;
    p->count++;
    while (*(volatile u8 *)&p->parked)
        ;
    IME = ime;
}
