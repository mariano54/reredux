/* ReRedux qol block: shared declarations for the modules in redux/qol/ (see tools/qol_build.py).
 * Code is Thumb (followers' flags), linked at QOL_BASE (0x021FD080) in main RAM; B2 functions come
 * from followers/syms.ld + qol/syms.ld + the module's SYMS (Thumb, bit 0 set). */
#ifndef QOL_H
#define QOL_H

typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;
typedef signed char s8;
typedef signed short s16;
typedef signed int s32;
typedef void (*qol_fn)(void);

/* At QOL_BASE (core.c): a fixed header test scripts and other code can find. */
#define QOL_MAGIC   0x33584452u     /* "RDX3" */
#define QOL_VERSION 1u
typedef struct {
    u32 magic;
    u32 version;
    u32 frames;         /* main-loop frames since boot (core's hook) */
    u32 end;            /* end of the used part of the block */
    const qol_fn *frame_hooks;
    const char *modules; /* "core,example,..." */
    u32 reserved[2];
} QolHeader;
extern QolHeader qol_header;

/* generated (qol_gen.c): the modules' FRAME functions, NULL-terminated */
extern const qol_fn qol_frame_hooks[];
extern const char qol_modules[];

#define REG16(a) (*(volatile u16 *)(a))
#define REG32(a) (*(volatile u32 *)(a))

#endif
