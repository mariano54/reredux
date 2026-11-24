"""ReRedux fast save (fastsave.c): the start-menu save in less time. Under the speed-ups flag 0x5DA
(set = OFF); quick save under flag 0x5DD (opt-in, menu.py row).

  - B2 reads the whole 150 KB save copy back to find the blocks that changed, then writes each changed
    block whole to both copies. Here blocks and 256-byte pages whose flash contents are known (read at
    load, or written by a complete save this session; checked against the copy's footer at every
    save) aren't read back, and only the pages that differ are written. Both copies, the write order,
    CRCs, counters, the commit byte and the SDK's verify are B2's own;
  - the save step runs ~0.5 frame per update (was one step; qol2 had 4);
  - the save texts print at once, the yes/no doesn't blink, the progress dots fill when the write ends,
    no wait for the save jingle, "X saved the game." stays 15 updates (0.5 s; vanilla 150, speed had 45);
  - quick save (0x5DD): no question, no yes/no (was qol2's yes/no skip);
  - not gated: a New Game started over another game's save could never be saved (B2 refuses: "There is
    already a saved game file. It is impossible to save."); its first save now asks to overwrite the old
    save (YES: the whole new save is written as on an empty card; NO: nothing is written).
Measurements and the integrity tests: README "ReRedux: fast save"; scripts in build/fastsave/."""
import os, sys

FRAME = ['fs_frame']
SYMS = {
    'fs_CardRead': 0x0203BFF9,          # ARM9 GFL backup: synchronous card read (0 = failed)
    'fs_CardWrite': 0x0203C07D,         # ARM9: start an async card write (with verify) -> lock id
    'fs_CardWriteDone': 0x0203C11D,     # ARM9: async card write done? (lock, &ok, cb) -> 1 when done
    'fs_CompareBlock': 0x0203B81D,      # ARM9 GFL backup: compare block idx with the card (1 diff, 2 same, 0 later)
    'fs_WriteBlock': 0x0203B92D,        # ARM9: CRC + start the card write of block idx (copy by status)
    'fs_EngineStep': 0x0203B9BD,        # ARM9: async save state machine step (0/1 busy, 2 done, 3 error)
    'fs_SaveAsyncMain': 0x02017851,     # ARM9: GameData async save step (EventSave state 9)
    'fs_GetMsgSpeed': 0x02017BCD,       # ARM9: message speed from the config (<0: chars per frame)
    'fs_SEIsPlaying': 0x020062C5,       # ARM9: SE still playing?
    'fs_PanelDone': 0x02198B29,         # OVL_36: save panel's progress dots all lit?
    'fs_GaugeAllDots': 0x021EB401,      # OVL_87 (save panel): light all 10 dots
    'fs_PrintMsg': 0x02163F39,          # OVL_12 EventSave: print message N
    'fs_MsgWait': 0x0216404D,           # OVL_12 EventSave: message still printing?
    'fs_SaveYesNoCreate': 0x021641E1,   # OVL_12 EventSave: create the yes/no
    'fs_SaveYesNoPoll': 0x0216421D,     # OVL_12 EventSave: poll it (0 YES, 1 NO, else busy)
    'fs_SaveIsOverwrite': 0x0200746D,   # ARM9 SaveControl: new game (+0) && a save was loaded at boot (+1)
}

TEXTS = [dict(bank=('story', 208), key='FS_OVERWRITE',      # EventSave's bank (state 1 opens story 0xD0)
              en='There is already a saved game file.\nOverwrite it with this new adventure?',
              ja='すでに　別の　レポートが　あります\n新しい　冒険で　上書きしますか？',
              note='New Game over another save: the first save asks (fs_ow_check)')]

SAVE_SCRIPT = 1230                      # common script 1230 scr_3 (global 2003): the scripted save (Mom, ...)
REFUSE = ['    MsgSystem 9, 2', '    MsgSystemClose', '    WorkSetConst 32805, 0', 'scr_3_L3:']


def files(ctx):
    """The scripted saves (common script 1230 scr_3: Mom's first save, the key bearer, ...) read the status
    (SaveDataGetStatus -> 0x8026 a save was loaded at boot, 0x8027 new game), ask "Would you like to save the
    game?" and, when YES && both, print msg 9 (the refusal; the caller then asks again forever). Here msg 9
    becomes the overwrite question: YES -> the save goes ahead (SaveDataWrite: the whole new save, as on an
    empty card); NO -> the vanilla refusal path (no save). In place: `MsgSystem 9, 2` (6 bytes) -> `VMJump`
    to a stub appended to the file (Redux's script code must not move, see menu.py)."""
    import ndsfs
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import menu as M
    gen5script, build_dir = M._scripts()
    fid = ctx.fid('a/0/5/6')
    raw = ctx.rom.file(fid)
    scripts = ndsfs.narc(raw)
    data = scripts[SAVE_SCRIPT]
    listing, _ = gen5script.decompile_best(data, build_dir)
    if gen5script.assemble_any(listing, build_dir) != data:
        raise ValueError(f'script {SAVE_SCRIPT} does not round-trip')
    sc = M.Script(listing, gen5script, build_dir)
    L = sc.lines
    hits = [i for i in range(len(L)) if L[i:i + 4] == REFUSE]
    if len(hits) != 1 or 'SaveDataGetStatus 32806, 32807, 32808' not in listing:
        raise ValueError(f'script {SAVE_SCRIPT}: the save refusal (msg 9) found {len(hits)} times')
    i = hits[0]
    L[i:i + 4] = ['    VMJump @rx_ow', '    MsgSystemClose', 'rx_ow_no:', '    WorkSetConst 32805, 0', 'scr_3_L3:']
    sc.sites += 1
    sc.tail += ['rx_ow:',
                f'    MsgSystem {ctx.text_id("FS_OVERWRITE")}, 2',
                '    YesNoWin 32809',
                '    MsgSystemClose',
                '    StackPush 32809',
                '    StackPushConst 0',
                '    StackCmp 1',
                '    VMJumpIf 255, @rx_ow_no',        # not YES: the refusal path (no save)
                '    VMJump @scr_3_L3']               # YES: save (0x8025 is still 1)
    new = gen5script.assemble_any(sc.text(), build_dir)
    M.check_in_place(data, new, sc.sites)
    scripts[SAVE_SCRIPT] = new
    print('fastsave: script 1230 scr_3 (scripted save): overwrite question instead of the refusal')
    return {fid: ndsfs.pack_narc(scripts, ndsfs.narc_layout(raw))}


PATCHES = [
    # the GFL backup engine (arm9)
    dict(where='arm9', addr=0x0203B1AE, kind='bl', orig=0x0203BFF9, target='fs_load_tramp',
         note='save load: copy [sd+0] read whole into RAM, every block known'),
    dict(where='arm9', addr=0x0203BA4A, kind='bl', orig=0x0203B81D, target='fs_cmp',
         note='save engine state 1: skip the card compare of known blocks'),
    dict(where='arm9', addr=0x0203BAC2, kind='bl', orig=0x0203B92D, target='fs_wblock',
         note='save engine state 3: note the blocks written'),
    dict(where='arm9', addr=0x0203B1CA, kind='bl', orig=0x0203BFF9, target='fs_load_tramp',
         note='save load: copy [sd+4] read into a scratch buffer, its pages known'),
    dict(where='arm9', addr=0x0203B97E, kind='bl', orig=0x0203C07D, target='fs_seg_write',
         note='block write: only the pages that changed in that copy'),
    dict(where='arm9', addr=0x0203BB08, kind='bl', orig=0x0203C11D, target='fs_seg_poll',
         note='block write done: chain the next run of pages'),
    dict(where='arm9', addr=0x0203AEE0, kind='bl', orig=0x0203B9BD, target='fs_engine',
         note='SaveControl async step: track the menu save, learn the written blocks when complete'),
    dict(where='arm9', addr=0x0203C07C, kind='jump', expect=bytes.fromhex('f0b587b0051c0e1c171c0593'),
         target='fs_write_tramp', note='card backup write: other writes drop the known blocks they touch'),
    # EventSave_Update (ov12)
    dict(where='ov12', addr=0x02163D06, kind='bl', orig=0x02017851, target='fs_savestep',
         note='EventSave state 9: save steps for ~1.1 frames per update'),
    dict(where='ov12', addr=0x02163F7E, kind='bl', orig=0x02017BCD, target='fs_msg_speed',
         note='EventSave messages print at once'),
    dict(where='ov12', addr=0x02163D56, kind='bl', orig=0x02198B29, target='fs_gauge',
         note='EventSave state 10: light the progress dots when the write is done'),
    dict(where='ov12', addr=0x02163DE6, kind='bl', orig=0x020062C5, target='fs_se_wait',
         note="EventSave state 12: don't wait for the save jingle"),
    dict(where='ov12', addr=0x02163E32, kind='bl', expect=bytes.fromhex('c86c9628'), target='fs_hold_cmp',
         note='EventSave state 16: "saved" box 15 updates (was speed_rtp.h: 45)'),
    dict(where='ov12', addr=0x02163C1A, kind='bl', orig=0x02163F39, target='fs_question',
         note='quick save: no question'),
    dict(where='ov12', addr=0x02163C22, kind='bl', orig=0x0216404D, target='fs_question_wait',
         note='quick save: no question to wait for'),
    dict(where='ov12', addr=0x02163C2C, kind='bl', orig=0x021641E1, target='fs_qs_create',
         note='quick save: no yes/no'),
    dict(where='ov12', addr=0x02163C34, kind='bl', orig=0x0216421D, target='fs_qs_poll',
         note='quick save: answer YES'),
    dict(where='ov12', addr=0x02163C44, kind='bl', orig=0x0200746D, target='fs_ow_tramp',
         note='New Game over another save: ask to overwrite it instead of refusing (msg 8)'),
]
