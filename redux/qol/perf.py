"""ReRedux engine-wide speed-ups (perf.c): mask empty HBlank task interrupts and
use the SDK's FIFO-triggered display-list DMA throughout the game (already used
by fps60 in the field). Command data/order and animation updates are unchanged.
Tests: perf_dbg.off disables HBlank gating; perf_dbg.slow_dma keeps stock DMA
outside the field. The controls are independent."""

FRAME = ['perf_frame']
SYMS = {
    'OS_EnableIrqMask': 0x02079E71,         # ARM9: IE |= mask (IME off around), returns the old IE
    'OS_DisableIrqMask': 0x02079E95,        # ARM9: IE &= ~mask
    'OS_ResetRequestIrqMask': 0x02079EB9,   # ARM9: IF = mask (acknowledge)
    'GFL_TCB_AddTask': 0x0203A615,          # ARM9: (mgr, fn, work, pri) -> task
}
PATCHES = [
    dict(where='arm9', addr=0x02067CF0, kind='u32', orig=0x02146974, target=0x02146974,
         note='NNS geometry globals: buffer, DMA-busy, fast-DMA flag at +8'),
    dict(where='arm9', addr=0x02005680, kind='jump', expect=bytes.fromhex('38b5051c04480c1c4069131c'),
         target='perf_hblank_add', note='GFUser HBlank task add: unmask the HBlank interrupt'),
]
