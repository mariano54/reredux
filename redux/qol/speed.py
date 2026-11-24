"""ReRedux speed-ups (speed.c): faster walk/run, cutscenes, doors, heal, shop, battle message waits; new
games default to text speed Fast. Off while event flag 0x5DA is set. Battle animations keep vanilla timing
(the extra tick every 10th frame and the VM resume cut sounds off there).
Addresses, old bytes and measurements: build/research_speed.md (sections 1, 4, 5)."""
import os, re

FRAME = ['speed_frame']
SYMS = {
    'FieldScriptEnv_SetWaitCounter': 0x02155215,   # OVL_12
    'FldCam_MoveTo': 0x02186F89,                   # OVL_36 (EVCameraMoveTo / MoveToCommon)
    'FldCam_Return': 0x02186FB9,
    'FldCam_MoveToDefault': 0x02187035,
    'GFL_FadeSet': 0x0204E061,
    'DoorEnterSeq': 0x0219F5DD,                    # OVL_36 GameEvent callbacks
    'DoorExitSeq': 0x0219F381,
}

HERE = os.path.dirname(os.path.abspath(__file__))
RTP_RE = re.compile(r'RTP\((0x[0-9A-Fa-f]+),\s*(G_\w+),\s*"((?:\\x[0-9A-Fa-f]{2})+)",\s*"((?:\\x[0-9A-Fa-f]{2})+)"\)')
WHERE = {'G_ARM9': 'arm9', 'G_OV36': 'ov36', 'G_OV36_DOOR': 'ov36', 'G_OV12': 'ov12', 'G_OV33': 'ov33',
         'G_OV167': 'ov167'}


def _hex(s):
    return bytes(int(x, 16) for x in re.findall(r'\\x([0-9A-Fa-f]{2})', s))


def rtp_claims():
    """speed_rtp.h's ranges as no-op patches: the build checks their vanilla bytes and that no other
    patch touches them (speed.c rewrites them at run time)."""
    out = []
    groups = {}
    for m in RTP_RE.finditer(open(os.path.join(HERE, 'speed_rtp.h')).read()):
        addr, g, van, fast = int(m.group(1), 16), m.group(2), _hex(m.group(3)), _hex(m.group(4))
        assert len(van) == len(fast) and van != fast, hex(addr)
        groups[g] = groups.get(g, 0) + len(van)
        out.append(dict(where=WHERE[g], addr=addr, kind='bytes', expect=van, target=van,
                        note=f'runtime patch site ({g})'))
    for g, n in groups.items():
        assert n >= 8, f'{g}: {n} bytes is too little to tell its overlay is loaded'
    return out


def PATCHES(ctx):
    return rtp_claims() + [
        # checks: the cache helpers and the GameSystem pointer speed.c / turbo.c use
        dict(where='arm9', addr=0x0207B0AC, kind='bytes', expect=bytes.fromhex('00c0a0e3001081e01f00c0e3'),
             target=bytes.fromhex('00c0a0e3001081e01f00c0e3'), note='DC_FlushRange (ARM) is here'),
        dict(where='arm9', addr=0x0207B0E8, kind='bytes', expect=bytes.fromhex('001081e01f00c0e3'),
             target=bytes.fromhex('001081e01f00c0e3'), note='IC_InvalidateRange (ARM) is here'),
        dict(where='arm9', addr=0x0201686C, kind='u32', orig=0x021410F4, target=0x021410F4,
             note='GameSystem pointer literal'),
        # new games: text speed Fast (initConfig 0x020089C0 `movs r0, #1`); Options still offers all 3
        dict(where='arm9', addr=0x020089D2, kind='bytes', expect=b'\x01\x20', target=b'\x02\x20',
             note='default text speed Fast'),
        # VMSleep: SetWaitCounter(env, n) -> x0.625 unless right after a sound command
        dict(where='ov12', addr=0x021541AE, kind='bl', orig=0x02155215, target='vmsleep_hook',
             note='VMSleep x0.625'),
        # script camera moves x0.69
        dict(where='ov36', addr=0x021AE850, kind='bl', orig=0x02186F89, target='speed_cam_move_to',
             note='EVCameraMoveTo'),
        dict(where='ov36', addr=0x021AE8BE, kind='bl', orig=0x02186F89, target='speed_cam_move_to',
             note='EVCameraMoveToCommon'),
        dict(where='ov36', addr=0x021AE8F8, kind='bl', orig=0x02186FB9, target='speed_cam_return',
             note='EVCameraReturn'),
        dict(where='ov36', addr=0x021AE922, kind='bl', orig=0x02187035, target='speed_cam_default',
             note='EVCameraMoveToDefault'),
        # scripted walks (FieldAcmdTCB_CommitAcmd) 0x0C -> 0x4C, 0x10 -> 0x50
        dict(where='ov36', addr=0x0218EF46, kind='bl', orig=0x02166E89, target='speed_acmd_commit',
             note='scripted walk remap'),
        # FadeEx (script cmd 0xB3): GFL_FadeSet wait / 2
        dict(where='ov36', addr=0x021AB240, kind='bl', orig=0x0204E061, target='speed_fadeex',
             note='FadeEx wait / 2'),
        # door sequences (GameEvent callbacks): mark them active for the door prop speed-up
        dict(where='ov36', addr=0x0219F554, kind='ptr', orig=0x0219F5DD, target='speed_door_enter',
             note='DoorEnterSeq callback'),
        dict(where='ov36', addr=0x0219F1F4, kind='ptr', orig=0x0219F381, target='speed_door_exit',
             note='DoorExitSeq callback'),
        # battle messages: auto-advance wait x0.75 (measured: no sound is cut; README "Battle sounds")
        dict(where='ov167', addr=0x021D2EA4, kind='bl', expect=b'\x20\x1c\x14\x30', target='speed_msgwait_hook',
             note='battle message wait x0.75'),
    ]
