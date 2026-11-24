"""ReRedux qol2 (qol2.c): more "slow game" fixes. Spec, sites and measurements:
build/research_qol2.md; test evidence: build/qol2/.

Under the speed-ups flag 0x5DA (set = OFF; runtime byte patches in qol2_rtp.h, or thunks):
  level-up: stat box after 16 ticks, not 80 · wild encounter: one flash, 2x swirl, short white fade;
  trainer encounter: one flash · trainer sight: shorter "!" pause and pre-turn wait, walk-up 12 f per
  tile · start menu: no wait for the button blink; party / bag / trainer card close without waiting for
  the return button; every GFL_WipeSet wipe at half the frames · 3D cut-ins (Fly, HM cut-ins, trainer
  VS) at 2x, not while the R turbo is on · save: no pre-scan for the progress dots (the rest of the save:
  fastsave.py) · Pokédex registration -> nickname: faster fades and blends · PC: no "booted up the PC" /
  "Storage System was accessed" lines (script 1244; its boot / shutdown sounds and Box animations play
  at normal speed) · fishing: bite after 20-58 frames · "Keep old moves" skips "Give up on learning?" ·
  season banner shorter.
No sound may be cut off, so these stay vanilla: the battle jingles (capture, level-up, move learned:
the A/B skip cut them), the evolution and egg-hatch scenes (the A-skip left out their sound effects and
cut their music short).
Auto-run (flag 0x5DC, set = OFF): run without B, hold B to walk (also on rails); running off in a new
direction does not turn on the spot first (qol2_turn_hook; walking with B does, as in vanilla).
Opt-in: quick Surf (flag 0x5DE: A at water surfs without the yes/no; common script 1243, after the
followers' edit). Quick save (flag 0x5DD) is in fastsave.py.
Static: boot (copyright hold 91 -> 31 f, black gaps 31 -> 5 f, the title doesn't wait for Kyurem's
cry), Continue never asks "C-Gear on?" (C-Gear stays off), new games default to Battle Style "Set",
the "1, 2, and... Ta-da!" lines lose their four pauses.
Settings-menu rows (Speed options page): menu.py. Needs speed.c (qol_rtp_apply, speed_dbg)."""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))

FRAME = ['qol2_frame']
SYMS = {
    'q2_FS_LoadOverlay': 0x020712B1,        # ARM9 sys_load_overlay (called by GFL_OvlLoad)
    'q2_FieldEffectCallback': 0x021BBA15,   # OVL_36 EventFieldEffect_Callback
}
FLAGS = dict(autorun_off=0x5DC, quicksave=0x5DD, quicksurf=0x5DE)

RTP_RE = re.compile(r'RTP\((0x[0-9A-Fa-f]+),\s*(Q_\w+),\s*"((?:\\x[0-9A-Fa-f]{2})+)",\s*"((?:\\x[0-9A-Fa-f]{2})+)"\)')
WHERE_RE = re.compile(r'(Q_\w+)=(\w+)')


def _hex(s):
    return bytes(int(x, 16) for x in re.findall(r'\\x([0-9A-Fa-f]{2})', s))


def rtp_claims():
    """qol2_rtp.h's ranges as no-op patches (vanilla bytes checked, nobody else may touch them)"""
    txt = open(os.path.join(HERE, 'qol2_rtp.h')).read()
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


def B(h):
    return bytes.fromhex(h)


def PATCHES(ctx):
    return rtp_claims() + [
        # every overlay load: apply the runtime patches before the overlay's code first runs
        dict(where='arm9', addr=0x0203CE82, kind='bl', orig=0x020712B1, target='qol2_ovl_load',
             note='GFL_OvlLoad: runtime patches right after the load'),
        # (evolution / egg hatch: no A-skip; it left the scenes' sound effects out and cut their music short)
        # (battle jingles: the capture / level-up / move-learned jingles play to their end, as in vanilla; the
        #  earlier A/B skip cut them off)
        # auto-run: start running in a new direction without turning on the spot first (FUN_0219BBA8,
        # standing with Running Shoes: `ldr r1, [r4, #4]; movs r0, #2` -> bl; then `tst r0, r1; bne move`)
        dict(where='ov36', addr=0x0219BBDC, kind='bl', expect=B('61680220'), target='qol2_turn_hook',
             note='auto-run: no turn on the spot before running (except toward the follower)'),
        # 3D cut-ins 2x
        dict(where='ov36', addr=0x021BB8A4, kind='ptr', orig=0x021BBA15, target='qol2_ci2x',
             note='EventFieldEffect callback: 3D cut-ins 2x'),
        # wipes / 2
        dict(where='arm9', addr=0x020279B8, kind='bl', expect=B('0f9d041c'), target='qol2_wipe_hook',
             note='GFL_WipeSet: div / 2'),
        # (save steps per update and quick save: fastsave.py)
        # (PC: boot / shutdown SE waits and Box animations stay vanilla — the sounds were cut off)
        # static: new games use Battle Style "Set" (initConfig: bics -> orrs of bit 0x40)
        dict(where='arm9', addr=0x020089E6, kind='bytes', expect=B('8a43'), target=B('0a43'),
             note='default Battle Style Set'),
        # static: boot / title / Continue (ov162; no save loaded yet, so no flag)
        dict(where='ov162', addr=0x021A0CBA, kind='bytes', expect=B('5a28'), target=B('1e28'),
             note='boot: copyright hold 91 -> 31 f'),
        dict(where='ov162', addr=0x021A0BF8, kind='bytes', expect=B('1e28'), target=B('0428'),
             note='boot: black gap after the first screen 31 -> 5 f'),
        dict(where='ov162', addr=0x021A0CE4, kind='bytes', expect=B('1e28'), target=B('0428'),
             note='boot: black gap after the copyright 31 -> 5 f'),
        dict(where='ov162', addr=0x0219D0F8, kind='bytes', expect=B('01d1'), target=B('c046'),
             note="title: don't wait for Kyurem's cry"),
        dict(where='ov162', addr=0x0219DFB0, kind='bytes', expect=B('07d1'), target=B('c046'),
             note='Continue: no "C-Gear on?" prompt (C-Gear off)'),
    ]


# --- data: scripts (append-only, as menu.py) and texts ---------------------------------------------

PC_SCRIPT, FIELD_MOVES_SCRIPT = 1244, 1243
TADA = [('system', 401, 5), ('system', 401, 16), ('system', 178, 41), ('story', 511, 25),
        ('story', 611, 19), ('story', 615, 15)]     # "1, {BE02:20}2, and{BE02:20}... Ta-da!" (move forget)


def _flag_skip(flag, skip):
    """jump to skip unless flag is set"""
    return [f'    StackPushFlag {flag:#x}', '    StackPushConst 1', '    StackCmp 1', f'    VMJumpIf 255, @{skip}']


def patch_pc(sc):
    """1244: "X booted up the PC." and "The Pokémon Storage System was accessed." only with speed-ups off"""
    L = sc.lines
    n = 0
    for k, want in enumerate(('    MsgSystem 0, 2', '    MsgSystem 14, 2')):
        idx = [i for i, l in enumerate(L) if l == want]
        if len(idx) != 1:
            raise ValueError(f'script 1244: {want.strip()!r} found {len(idx)} times')
        skip = f'rq_pc{k}_skip'
        sc.redirect(idx[0], lambda moved, skip=skip: _flag_skip(0x5DA, skip) + moved[:1] + [f'{skip}:'] + moved[1:],
                    f'pc{k}')
        n += 1
    return n


def patch_surf(sc):
    """1243 scr_2: with flag 0x5DE set, no "Would you like to Surf?" yes/no (answer YES)"""
    L = sc.lines
    i = L.index('scr_2_L2:')
    want = ['    MsgSystem 13, 2', '    YesNoWin 32784', '    MsgSystemClose', '    StackPush 32784',
            '    StackPushConst 0', '    StackCmp 1', '    VMJumpIf 255, @scr_2_L3', '    VMCall @scr_2_L5']
    if L[i + 1:i + 1 + len(want)] != want:
        raise ValueError(f'script 1243 scr_2_L2 is not the Surf question: {L[i + 1:i + 9]}')
    L.insert(i + 4, 'rq_surf_yes:')
    sc.redirect(i + 1, lambda moved: _flag_skip(0x5DE, 'rq_surf_ask') +
                ['    WorkSetConst 32784, 0', '    VMJump @rq_surf_yes', 'rq_surf_ask:'] + moved, 'surf')


def _scripts(ctx):
    sys.path.insert(0, HERE)
    import menu as M
    gen5script, build_dir = M._scripts()
    import ndsfs
    fid = ctx.fid('a/0/5/6')
    raw = ctx.rom.file(fid)
    scripts = ndsfs.narc(raw)
    for sid, fn in ((PC_SCRIPT, patch_pc), (FIELD_MOVES_SCRIPT, patch_surf)):
        data = scripts[sid]
        listing, _ = gen5script.decompile_best(data, build_dir)
        if gen5script.assemble_any(listing, build_dir) != data:
            raise ValueError(f'script {sid} does not round-trip')
        sc = M.Script(listing, gen5script, build_dir)
        fn(sc)
        new = gen5script.assemble_any(sc.text(), build_dir)
        M.check_in_place(data, new, sc.sites)
        scripts[sid] = new
    return fid, ndsfs.pack_narc(scripts, ndsfs.narc_layout(raw))


def _texts(ctx):
    import ndsfs, gen5text, struct
    out = {}
    for arc, path in (('system', 'a/0/0/2'), ('story', 'a/0/0/3')):
        fid = ctx.fid(path)
        raw = ctx.rom.file(fid)
        narc = ndsfs.narc(raw)
        for a, bank, line in TADA:
            if a != arc:
                continue
            data = narc[bank]
            secs = gen5text.decode(data)
            unk, pad = struct.unpack_from('<I', data, 8)[0], gen5text.padding(data)
            if gen5text.encode(secs, unk, pad) != data:
                raise ValueError(f'{arc} bank {bank} does not round-trip')
            for s in secs:
                t, f = s[line]
                if t.count('{BE02:20}') != 4:
                    raise ValueError(f'{arc} {bank}:{line} is not the "Ta-da!" line: {t[:60]!r}')
                s[line] = (t.replace('{BE02:20}', ''), f)
            narc[bank] = gen5text.encode(secs, unk, pad)
        out[fid] = ndsfs.pack_narc(narc, ndsfs.narc_layout(raw))
    return out


def files(ctx):
    fid, scr = _scripts(ctx)
    out = {fid: scr}
    out.update(_texts(ctx))
    print('qol2: scripts 1244 (PC lines), 1243 (quick Surf); "Ta-da!" pauses in', len(TADA), 'lines')
    return out
