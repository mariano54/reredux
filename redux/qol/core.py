"""qol core (always built first): block header at QOL_BASE + the per-frame FRAME dispatcher."""

PATCHES = [
    # TwlMain loop: bl nullsub_4 (an empty function) -> qol_main_frame, once per main-loop frame
    dict(where='arm9', addr=0x02005172, kind='bl', orig=0x02005669, target='qol_main_frame',
         note='main loop frame hook'),
]
