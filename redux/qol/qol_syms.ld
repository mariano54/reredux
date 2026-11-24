/* Black 2 (IREO) symbols for the qol modules, shared by all of them (followers/syms.ld,
   ballfx_syms.ld and emote_syms.ld are included too). Thumb functions have bit 0 set. Names follow
   swan's White 2 symbols ported to B2 (W2 -> B2 delta: ARM9 0 / -0x2C, OVL_12 / OVL_36 -0x40);
   module-specific symbols can also go in the module's SYMS. Verify each in pokeblack2/asm. */

/* ARM9 main loop (TwlMain 0x02005124: bl 0x02005654 at 0x0200516A, bl 0x02005668 at 0x02005172) */
GFLAppUpdate = 0x02005655;
nullsub_4 = 0x02005669;                 /* empty (bx lr), called once per main-loop frame */
