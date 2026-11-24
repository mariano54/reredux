/* ReRedux qol block: a main-RAM autoload segment at 0x021FD080 (the end of the highest main-RAM
   overlay and B2's vanilla main-arena start; the arena now starts after the block). Linked by
   tools/qol_build.py, which checks the base, size (QOL_SIZE) and that qol_header comes first. */
ENTRY(qol_header)
INCLUDE syms.ld
INCLUDE ballfx_syms.ld
INCLUDE emote_syms.ld
INCLUDE qol_syms.ld
INCLUDE gen_syms.ld

SECTIONS
{
    . = 0x021FD080;
    .qol : {
        KEEP(*(.qol_header))
        *(.text*)
        *(.rodata*)
        *(.data*)
        . = ALIGN(4);
        *(.bss*)
        *(COMMON)
        . = ALIGN(4);
        __qol_end = .;
        . = ALIGN(32);
    }
    /DISCARD/ : { *(.comment) *(.ARM.*) *(.note*) }
}
