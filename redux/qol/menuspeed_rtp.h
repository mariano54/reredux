/* menuspeed's runtime byte patches (menuspeed.c writes them with its own copy of speed.c's apply, menuspeed.py claims
 * them); same format as speed_rtp.h / qol2_rtp.h. Each group is one overlay, at least 8 bytes in all. */
#ifdef MS_GROUPS
enum { M_OV36, M_OV207, M_OV140, M_OV255, M_COUNT };
#else
/* X menu (field subscreen FUN_0219FC60) state 4: B / X closes the menu without waiting for the close button's
 * press animation (16 frames) */
RTP(0x0219FD2C, M_OV36, "\xAC\xF6\x18\xFC\x00\x28\x00\xD0",
                        "\xAC\xF6\x18\xFC\xC0\x46\x00\xE0")
/* X menu slide-in: 0x60 per update instead of 0x40 (3 updates instead of 4 before it takes input) */
RTP(0x0219FCDE, M_OV36, "\x40\x2A", "\x60\x2A")
RTP(0x0219FCF4, M_OV36, "\x40\x3A", "\x60\x3A")
/* X menu slide-out: 0x60 per update */
RTP(0x0219FE14, M_OV36, "\x40\x31", "\x60\x31")
RTP(0x0219FE28, M_OV36, "\x40\x32", "\x60\x32")
/* summary (ov207): B / the return button closes it without waiting for the button's press animation (16 frames),
 * unless a cry plays (menuspeed.c ms_frame: the group is off while a voice is playing) */
RTP(0x021B3282, M_OV207, "\x99\xF6\x6D\xF9\x00\x28\x03\xD0",
                         "\x99\xF6\x6D\xF9\x00\x28\x03\xE0")
/* Options (ov140): fade-out / fade-in GFL_FadeSet(3, .., .., 0) (8 frames) -> wait ~3 = -4 (`mvns r3, r0`, r0 = 3):
 * 2 frames */
RTP(0x0219EA64, M_OV140, "\x00\x22\x00\x23", "\x00\x22\xC3\x43")
RTP(0x0219EAA4, M_OV140, "\x10\x22\x00\x23", "\x10\x22\xC3\x43")
/* Box (ov255): its generic "wait for the button's press animation" step goes on at once (B -> "Continue Box
 * operations?" 16 frames sooner, ...) */
RTP(0x021BBECC, M_OV255, "\x13\xF0\xAC\xFB\x00\x28\x27\xD1",
                         "\x13\xF0\xAC\xFB\x00\x28\xC0\x46")
#endif
/* where: M_OV36=ov36 M_OV207=ov207 M_OV140=ov140 M_OV255=ov255 */
