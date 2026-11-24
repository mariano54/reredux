/* Follower code is appended to the game's ITCM autoload block (vanilla ITCM ends at 0x01FF93A0;
   ITCM is 32 KiB, 0x01FF8000-0x02000000). build_followers.py checks the base address. */
ENTRY(follow_hook_field_frame)
INCLUDE syms.ld
INCLUDE ballfx_syms.ld
INCLUDE emote_syms.ld

SECTIONS
{
    . = 0x01FF93A0;
    .itcm : {
        KEEP(*(.text.follow_hook_field_frame))
        KEEP(*(.text.follow_script_cmd))
        KEEP(*(.text.follow_ev_warp))
        KEEP(*(.text.follow_ev_warp_pad))
        KEEP(*(.text.follow_ev_fly_create))
        KEEP(*(.text.follow_ev_fly))
        KEEP(*(.text.follow_ev_sweet_scent))
        KEEP(*(.text.follow_wofs_hook))
        KEEP(*(.text.follow_shadow_init))
        KEEP(*(.text.follow_shadow_delete))
        *(.text*)
        *(.rodata*)
        *(.data*)
        . = ALIGN(4);
        *(.bss*)
        *(COMMON)
        . = ALIGN(32);
    }
    /DISCARD/ : { *(.comment) *(.ARM.*) *(.note*) }
}
