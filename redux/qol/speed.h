/* ReRedux speed / turbo modules (speed.c, turbo.c): shared definitions. */
#ifndef QOL_SPEED_H
#define QOL_SPEED_H
#include "qol.h"

#define QOL_GSYS        (*(void **)0x021410F4)  /* the GameSystem (stored by GameSystem_Init, 0x020166D4) */

typedef struct {
    u8 override;        /* 0: flag 0x5DA decides; 1: force off; 2: force on (emulator tests) */
    u8 on;              /* speed-ups on this frame */
    u8 groups;          /* runtime patch groups: bit g toggles whenever group g is switched */
    u8 pad;
    u32 writes;         /* runtime patch entries written so far */
    u32 door_frame;     /* qol frame of the last door-sequence step */
} SpeedDbg;
extern SpeedDbg speed_dbg;

/* Runtime byte patches (speed_rtp.h, qol2_rtp.h): one entry = vanilla and fast bytes at addr, in a
 * group (all entries of one overlay); see speed.c. */
typedef struct {
    u32 addr;
    u16 len;
    u8 group, pad;
    const u8 *van, *fast;
} Rtp;
#define RTP(a, g, v, f) {a, sizeof(v) - 1, g, 0, (const u8 *)(v), (const u8 *)(f)},

/* Write group g of tab[0..n) to its fast (want = 1) or vanilla bytes when every byte of the group is
 * one or the other (its overlay is loaded); -> 1 if anything was written. */
int qol_rtp_apply(const Rtp *tab, u32 n, u32 g, u32 want);

#endif
