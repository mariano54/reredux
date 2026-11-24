"""ReRedux rules: test-only module (disabled; build/scripts/rules/build.py --extra rules_test).

- rules_test.c: rules_tst mailbox / state snapshot for the emulator tests (FRAME function).
- zone 428 (the player's bedroom, a/0/5/6 script 856): the bed's script entry is redirected to an
  appended test menu (append-only, like menu.py): a kit (2x Dragonite Lv60 with Dragon Claw +
  Growl, Master/Poke Balls, Potions), script wild battles (Patrat, shiny Patrat, Lillipup: statics),
  a trainer with a Hyper Potion (Robert, #630), a gift with the usual nickname question (patched by
  menu.patch_nicknames like the real gifts), a warp to Route 19 (grass), a full heal and a custom-script
  row (CUSTOM, for build/scripts/qa2/): its body is `VMJump @rt_end`, the marker "QA2SCRPT" and a
  CUSTOM_BYTES zero buffer; the harness writes an assembled script fragment over it (from the VMJump on)
  in the loaded script before picking the row, so a test can run any script commands (warps, gifts,
  badges, flags, trades, egg hatches...)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ENABLED = False
SOURCES = ['rules_test.c']
FRAME = ['rules_test_frame']
SYMS = {'BoxSaveAccessor_GetBox': 0x02007E15, 'PokePasoParam_GetParam': 0x0201CD89,
        'PokeParty_SetParam': 0x0201CD1D}
BED_SCRIPT, BED_TEXT = 856, 173

ROWS = [('KIT', 'Kit: 2 Dragonite, balls'), ('PATRAT', 'Wild Patrat'), ('SHINY', 'Shiny Patrat'),
        ('LILLIPUP', 'Wild Lillipup'), ('TRAINER', 'Trainer Robert'), ('GIFT', 'Gift Patrat'),
        ('ROUTE', 'Warp: Route 19'), ('HEAL', 'Heal the party'), ('CUSTOM', 'Custom script (QA)')]
CUSTOM_MARK = b'QA2SCRPT'
CUSTOM_BYTES = 2048
TEXTS = [dict(bank=('story', BED_TEXT), key='RT_' + k, en=t, ja=t) for k, t in
         ROWS + [('PROMPT', 'Rules test'), ('GIFT_GOT', 'You received a Pokémon!'),
                 ('GIFT_NICK', 'Give a nickname to the\nPokémon you received?')]]


def wild(species, flags):
    return [f'    CallWildBattle {species}, 3, {flags}', '    WildBattleIsVictory 0x8010',
            '    StackPush 0x8010', '    StackPushConst 1', '    StackCmp 1', f'    VMJumpIf 255, @rt_lose_{species}_{flags}',
            '    CallWildBattleEnd', '    VMJump @rt_end', f'rt_lose_{species}_{flags}:', '    CallWildLose',
            '    VMJump @rt_end']


def test_menu(ctx):
    t = lambda k: ctx.text_id('RT_' + k)
    L = ['rt_menu:', '    ActorPauseAll', f'    MsgSystem {t("PROMPT")}, 0',
         '    ListMenuInitTR 31, 1, 0, 1, 0x8024']
    L += [f'    ListMenuAdd {t(k)}, 65535, {i}' for i, (k, _) in enumerate(ROWS)]
    L += ['    ListMenuShow', '    MsgSystemClose', '    MsgWinCloseAll']
    body = {
        'KIT': ['    PokePartyAdd 0x8020, 149, 0, 60', '    PokePartyLearnMove 0, 0, 337', '    PokePartyLearnMove 0, 1, 45',
                '    PokePartyAdd 0x8020, 149, 0, 60', '    PokePartyLearnMove 1, 0, 337', '    PokePartyLearnMove 1, 1, 45',
                '    ItemAdd 1, 10, 0x8020', '    ItemAdd 4, 30, 0x8020', '    ItemAdd 17, 5, 0x8020',
                '    FlagSet 2401'],
        'PATRAT': wild(504, 0), 'SHINY': wild(504, 2), 'LILLIPUP': wild(506, 0),
        'TRAINER': ['    CallTrainerBattle 630, 0, 0', '    TrainerBattleIsVictory 0x8010', '    StackPush 0x8010',
                    '    StackPushConst 1', '    StackCmp 1', '    VMJumpIf 255, @rt_tlose', '    CallTrainerBattleEnd',
                    '    VMJump @rt_end', 'rt_tlose:', '    CallTrainerLose', '    VMJump @rt_end'],
        'GIFT': ['    PokePartyAdd 0x8010, 504, 0, 10', '    PokePartyGetCount 0x8021, 0', '    WorkSub 0x8021, 1',
                 f'    MsgSystem {t("GIFT_GOT")}, 0', '    MsgWaitAdvance', '    MsgSystemClose',
                 f'    MsgSystem {t("GIFT_NICK")}, 0', '    WorkSetConst 0x8022, 0', '    YesNoWin 0x8022',
                 '    MsgSystemClose', '    StackPush 0x8022', '    StackPushConst 0', '    StackCmp 1',
                 '    VMJumpIf 255, @rt_gift_end', '    WorkSetConst 0x8023, 0', '    CallPokeNameInput 0x8023, 0x8021, 1',
                 'rt_gift_end:', '    VMJump @rt_end'],
        'ROUTE': ['    MapChangeWarpPad 437, 52, 700, 0', '    VMJump @rt_end'],
        'HEAL': ['    PokePartyRecoverAll', '    VMJump @rt_end'],
        'CUSTOM': ['    VMJump @rt_end',
                   '    .hword ' + ', '.join(f'0x{CUSTOM_MARK[i] | CUSTOM_MARK[i + 1] << 8:04X}' for i in range(0, 8, 2))] +
                  ['    .hword ' + ', '.join(['0'] * 32)] * (CUSTOM_BYTES // 64),
    }
    for i, (k, _) in enumerate(ROWS):
        L += ['    StackPush 0x8024', f'    StackPushConst {i}', '    StackCmp 1', f'    VMJumpIf 255, @rt_n{i}']
        L += body[k]
        if not body[k][-1].startswith('    VMJump'):
            L += ['    VMJump @rt_end']
        L += [f'rt_n{i}:']
    L += ['rt_end:', '    WorkSetConst 0x8024, 0', '    RTFinishSubEvents', '    ActorUnlockAll', '    VMHalt']
    return L


def files(ctx):
    import ndsfs
    import menu as M
    gen5script, build_dir = M._scripts()
    fid = ctx.fid('a/0/5/6')
    raw = ctx.rom.file(fid)
    scripts = ndsfs.narc(raw)
    data = scripts[BED_SCRIPT]
    listing, _ = gen5script.decompile_best(data, build_dir)
    assert gen5script.assemble_any(listing, build_dir) == data
    sc = M.Script(listing, gen5script, build_dir)
    L = sc.lines
    at = next(i for i, l in enumerate(L) if l.startswith(f'    MsgInfo {40}, 2'))   # "It's a brand-new bed!"
    label = next(L[i][:-1] for i in range(at, 0, -1) if L[i].endswith(':') and not L[i].startswith(' '))
    L[L.index(f'.script {label}')] = '.script rt_menu'
    L[len(L):] = [l for l in test_menu(ctx)]    # appended after the original code
    n = M.patch_nicknames(sc, 'rt')
    assert n == 1, n
    sc.sites += 1
    new = gen5script.assemble_any(sc.text(), build_dir)
    M.check_in_place(data, new, sc.sites)
    scripts[BED_SCRIPT] = new
    print(f'rules_test: bed ({label}) -> test menu in script {BED_SCRIPT}')
    return {fid: ndsfs.pack_narc(scripts, ndsfs.narc_layout(raw))}
