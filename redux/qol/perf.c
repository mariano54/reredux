/* ReRedux engine-wide speed-ups (perf.py, in the release ROMs).
 *
 * HBlank interrupt gating. GFL keeps the HBlank interrupt on all the time: 263 interrupts per frame, each one
 * entering the OS dispatcher (ITCM), saving / restoring the divider + sqrt context (CP_SaveContext /
 * CP_RestoreContext) and running the HBlank task manager (GFL_TCBMgrUpdate) -- whose list is empty nearly
 * everywhere (the field, menus). ~85k ARM9 cycles per frame (8% of the frame, melonDS interpreter) spent on
 * nothing. While the HBlank task list is empty the HBlank interrupt is masked (IE bit 1, checked once per
 * main-loop frame); adding an HBlank task (GFUser HBlank add, 0x02005680, the only way one is added) unmasks
 * it at once, before the task can miss an HBlank, so a task runs on exactly the HBlanks it ran on before.
 * Display-list DMA. fps60 already opts into the SDK's FIFO-triggered DMA in the
 * field. Enable that standard transfer mode for other scenes too, including
 * battles. It sends the same list on GX's chosen channel, with fewer FIFO
 * interrupts. No extra animation ticks or different command/geometry data.
 * Tests: perf_dbg.slow_dma restores the stock mode outside the field.
 * Counters: perf_dbg. */
#include "qol.h"

u32 OS_EnableIrqMask(u32 mask);
u32 OS_DisableIrqMask(u32 mask);
u32 OS_ResetRequestIrqMask(u32 mask);
void *GFL_TCB_AddTask(void *mgr, void *fn, void *work, u32 pri);

#define GFL_SYS         (*(u8 **)(0x0209DA58 + 0x14))   /* GFL system work: +0x18 the HBlank task manager */
#define REG_IE          (*(volatile u32 *)0x04000210)
#define IRQ_HBLANK      2u
#define RAM_OK(p)       ((u32)(p) - 0x02000000u < 0x400000u)
#define NNS_FAST_DMA    (*(volatile u32 *)0x0214697C)

typedef struct {
    u8 off;             /* tests: 1 = no gating */
    u8 gated;           /* we masked the HBlank interrupt (the task list was empty) */
    u8 slow_dma;        /* tests: keep the stock display-list transfer outside the field */
    u8 pad;
    u32 gates, ungates; /* maskings / unmaskings */
    u32 gated_frames;   /* main-loop frames that ended with the interrupt masked by us */
} PerfDbg;

PerfDbg perf_dbg;

static void ungate(void)
{
    perf_dbg.gated = 0;
    OS_ResetRequestIrqMask(IRQ_HBLANK);     /* an HBlank seen while masked is stale */
    OS_EnableIrqMask(IRQ_HBLANK);
    perf_dbg.ungates++;
}

/* FRAME: mask the HBlank interrupt while no HBlank task exists */
void perf_frame(void)
{
    PerfDbg *d = &perf_dbg;
    u8 *sys = GFL_SYS, *mgr = RAM_OK(sys) ? *(u8 **)(sys + 0x18) : 0;
    /* The SDK's FIFO-triggered DMA sends the identical display list with fewer
     * interrupts. fps60 already uses it for the field; enable it for other
     * scenes too. GX still chooses its DMA channel and manages completion. */
    NNS_FAST_DMA = !d->slow_dma;
    if (d->off || !RAM_OK(mgr)) {
        if (d->gated)
            ungate();
        return;
    }
    if (*(u8 **)(mgr + 0x10) != mgr + 8) {     /* a task in the list (head != the sentinel) */
        if (d->gated)
            ungate();
        return;
    }
    if (REG_IE & IRQ_HBLANK) {
        OS_DisableIrqMask(IRQ_HBLANK);
        d->gated = 1;
        d->gates++;
    }
    if (d->gated)
        d->gated_frames++;
}

/* ARM9 0x02005680 (GFUser HBlank task add: GFL_TCB_AddTask(the HBlank manager, fn, work, pri)) -> here */
void *perf_hblank_add(void *fn, void *work, u32 pri)
{
    void *t = GFL_TCB_AddTask(*(void **)(GFL_SYS + 0x18), fn, work, pri);
    if (perf_dbg.gated)
        ungate();
    return t;
}
