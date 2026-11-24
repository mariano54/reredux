"""ReRedux menuspeed (menuspeed.c): faster menus, under the speed-ups flag 0x5DA. Measured frame-exact in a headless
melonDS and DeSmuME against Redux 1.4.1 (redux/tests/menuspeed: sweep.py, timeline.py; README "ReRedux: menus").

  - task menus (arm9 APP_TASKMENU: party / Bag / Box item menus, many yes/no's): one short blink, 4 frames, not 16;
  - X menu: no wait for the close button's animation; slides in / out in 3 updates, not 4; a chosen item starts
    its app in the same update (with qol2's blink skip);
  - EventFieldMenu / EventFieldAppCall (ov12): a state that only moved on runs the next one in the same update;
    the field's fade-out / fade-in around an app: 2 frames, not 4;
  - summary: B closes it without waiting for the return button's animation (not while a cry plays).
Needs speed.c (Rtp, speed_dbg) and qol2.c (its overlay-load hook calls menuspeed_ovl_loaded)."""
import os, re

FRAME = ['ms_frame']
SYMS = {
    'ms_EvMenu': 0x0215A875,            # OVL_12 EventFieldMenu callback
    'ms_EvAppCall': 0x0215B50D,         # OVL_12 EventFieldAppCall callback
    'ms_VoicePlayingAny': 0x020066C1,   # ARM9 PokeVoice_IsPlayingAny
    'ms_SndActiveAny': 0x020062A9,      # ARM9 GFL_SndPlayerIsActiveAny (the SE players)
    'ms_SeqPlayerIndex': 0x020061B9,    # ARM9 GFL_SndSeqGetPlayerIndex (SDAT player - 1)
    'ms_PlayerActive': 0x02006295,      # ARM9 GFL_SndPlayerIsActive(index)
    'ms_SEPlayCore': 0x02006215,        # ARM9 GFL_SndSEPlayCore(se, volume)
    'ms_SEPlayOnPlayer': 0x020061DD,    # ARM9 FUN_020061DC(se, index): play on that player
    'ms_SEPlayerVolume': 0x0200632D,    # ARM9 GFL_SndPlayerSetVolume(index, volume)
    'GFL_FadeSet': 0x0204E061,
}

HERE = os.path.dirname(os.path.abspath(__file__))
RTP_RE = re.compile(r'RTP\((0x[0-9A-Fa-f]+),\s*(M_\w+),\s*"((?:\\x[0-9A-Fa-f]{2})+)",\s*"((?:\\x[0-9A-Fa-f]{2})+)"\)')
WHERE_RE = re.compile(r'(M_\w+)=(\w+)')


def _hex(s):
    return bytes(int(x, 16) for x in re.findall(r'\\x([0-9A-Fa-f]{2})', s))


def rtp_claims():
    """menuspeed_rtp.h's ranges as no-op patches (vanilla bytes checked, nobody else may touch them)"""
    txt = open(os.path.join(HERE, 'menuspeed_rtp.h')).read()
    where = dict(WHERE_RE.findall(txt.split('/* where:')[1]))
    out, groups = [], {}
    for m in RTP_RE.finditer(txt):
        addr, g, van, fast = int(m.group(1), 16), m.group(2), _hex(m.group(3)), _hex(m.group(4))
        assert len(van) == len(fast) and van != fast, hex(addr)
        groups[g] = groups.get(g, 0) + len(van)
        out.append(dict(where=where[g], addr=addr, kind='bytes', expect=van, target=van,
                        note=f'runtime patch site ({g})'))
    for g, n in groups.items():
        assert n >= 8, f'{g}: {n} bytes is too little to tell its overlay is loaded'
    return out


def PATCHES(ctx):
    return rtp_claims() + [
        # task menus: blink period and length (arm9 APP_TASKMENU update / IsFinish: `blx div` -> thunks)
        dict(where='arm9', addr=0x0202DB96, kind='bl', orig=0x0208D868, target='ms_tm_period',
             note='task menu: blink period 4 -> 2'),
        dict(where='arm9', addr=0x0202DBEC, kind='bl', orig=0x0208D868, target='ms_tm_total',
             note='task menu: chosen after 4 frames, not 16'),
        # task-menu buttons (APP_TASKMENU_WIN: Options' buttons, ...): same blink (update / IsFinish, `blx sdiv`)
        dict(where='arm9', addr=0x0202E3C2, kind='bl', orig=0x0208D65C, target='ms_tm_period',
             note='task-menu button: blink period 4 -> 2'),
        dict(where='arm9', addr=0x0202E440, kind='bl', orig=0x0208D65C, target='ms_tm_total',
             note='task-menu button: done after 4 frames, not 16'),
        # list menus (BmpMenuList): the cursor and input after at most 4 frames, not the header's wait (20 in the field)
        dict(where='arm9', addr=0x02025756, kind='bl', expect=bytes.fromhex('216b0029'), target='ms_mlwait',
             note='list menu: input after 4 frames at most'),
        # SEs: one for SE player 1 while it still plays goes to an idle SE player (no SE is cut by a quicker menu)
        dict(where='arm9', addr=0x0200625C, kind='ptr', orig=0x02006215, target='ms_se_play',
             note='GFL_SndSEPlay: no SE stops another (idle player)'),
        dict(where='arm9', addr=0x02006264, kind='ptr', orig=0x02006215, target='ms_se_play',
             note='GFL_SndSEPlayEx: no SE stops another (idle player)'),
        # the X menu's field events: chained states
        dict(where='ov12', addr=0x0215A838, kind='ptr', orig=0x0215A875, target='ms_ev_menu',
             note='EventFieldMenu: chained states'),
        dict(where='ov12', addr=0x0215B508, kind='ptr', orig=0x0215B50D, target='ms_ev_appcall',
             note='EventFieldAppCall: chained states'),
        # the field fade-out / fade-in events (ov36): 2 frames when they belong to an app call
        dict(where='ov36', addr=0x021B8CF2, kind='bl', orig=0x0204E061, target='ms_fieldfade',
             note='field fade-out: 2 frames around an app'),
        dict(where='ov36', addr=0x021B8D50, kind='bl', orig=0x0204E061, target='ms_fieldfade',
             note='field fade-in: 2 frames around an app'),
    ]
