"""suite.py : the ReRedux regression job graph for rr.py. Each Job runs one test script (or a short command list) of
redux/tests/<grp>/ with the emulator Python; deps are the jobs whose savestates / battery saves it starts from.

Tiers: quick (a few minutes: boot + new game, settings menu, views, static checks, fixture-based statview / evomoves),
full (everything that reports a RESULT, both emulators, + perf), perf (frame-count measurements without pass/fail:
battle exit, fix-float). Areas: what a job exercises, for --changed (AREAS_BY_PATH).

Checkpoint cache (rr.py --reuse): a job's key = its command + the SHA-1 of the ROM it runs on (rom kind) + extra input
files + the harness files it uses (LIBS) + its dependencies' keys. A PASS is remembered under that key with the job's
`outputs` (savestates / battery saves other jobs start from), so a rerun on the same ROMs restores them instead of
replaying the game; a new build changes the key, so a stale state is never reused."""


class Job:
    def __init__(self, id, grp, cmds, deps=(), tiers=('full',), areas=(), result='RESULT', est=60, env=None, pre=(),
                 lang=None, timeout=None, rom=None, outputs=(), inputs=()):
        self.id, self.grp, self.cmds, self.deps = id, grp, cmds, list(deps)
        self.tiers, self.areas, self.result, self.est = set(tiers), set(areas), result, est
        self.env, self.pre, self.lang, self.timeout = dict(env or {}), list(pre), lang, timeout
        self.rom, self.outputs, self.inputs = rom, list(outputs), list(inputs)

    def __repr__(self):
        return f'Job({self.id})'


# ROM a job runs on, by kind ({B} = the run's build tree)
ROMS = {'rel': '{B}/out/redux3_{L}.nds', 'qa': '{B}/qa/roms/qa_test_{L}.nds', 'qa2': '{B}/qa2/roms/qa2_{L}.nds',
        'sv': '{B}/out/sv_{L}.nds', 'em': '{B}/out/em_{L}.nds'}
# harness files a group's scripts import (redux/tests/<dir>); rrenv.py and the root helpers always count
LIBS = {'qa': ('qa', 'qol2', 'rules'), 'qa2': ('qa2', 'qa', 'qol2', 'rules'), 'qol2': ('qol2', 'rules', 'qa'),
        'integ': ('integ', 'qol2', 'rules'), 'statview': ('statview',), 'evomoves': ('evomoves', 'statview'),
        'fastsave': ('fastsave', 'qa', 'qol2', 'rules'), 'battleexit': ('battleexit', 'qa', 'qol2', 'rules'),
        'ff': ('ff',), 'xmenu': ('xmenu', 'statview', 'evomoves'), 'menuspeed': ('menuspeed', 'qa', 'fastsave')}

# changed path (prefix, relative to the repo root) -> areas; first match wins; 'all' = every job
_STORY = {'story', 'qa'}
AREAS_BY_PATH = [
    ('redux/qol/statview', {'statview', 'evomoves'}), ('redux/qol/evomoves', {'evomoves', 'statview'}),
    ('redux/qol/dexmoves', {'evomoves'}), ('redux/qol/dexstats', {'evomoves'}),
    ('redux/qol/fastsave', {'fastsave', 'boot', 'qol2'} | _STORY),
    ('redux/qol/battleexit', {'battleexit', 'rules', 'qa2'} | _STORY),
    ('redux/qol/rules_test', {'rules', 'qa2', 'qol2', 'menu', 'fastsave', 'battleexit'}),
    ('redux/qol/qol2_test', {'qol2', 'qa2', 'statview', 'evomoves', 'menu'}),
    ('redux/qol/rules', {'rules', 'menu', 'qa2', 'fastsave'}), ('redux/qol/menu', {'menu', 'texts', 'rules', 'qa2'}),
    ('redux/qol/speed', {'speed', 'turbo', 'feel', 'qa2'} | _STORY), ('redux/qol/turbo', {'turbo', 'speed', 'feel', 'qa2'} | _STORY),
    ('redux/qol/loadspeed', {'speed', 'fastsave', 'feel', 'qol2'} | _STORY), ('redux/qol/qol2', {'qol2', 'qa2'} | _STORY),
    ('redux/qol/logo', {'boot', 'menu'}), ('redux/qol/example', set()),
    ('redux/qol/xmenu', {'xmenu', 'qol2', 'statview', 'evomoves'} | _STORY),
    ('redux/qol/menuspeed', {'all'}),         # task menus, list menus, SE players, the X menu's events: everywhere
    ('redux/qol/', {'all'}),
    ('redux/followers/', {'followers', 'feel', 'qol2'} | _STORY),
    ('redux/tools/', {'all'}), ('pokeblack2/', {'all'}),
    ('redux/tests/qa/', {'qa', 'story', 'menu', 'rules', 'fastsave', 'battleexit', 'qa2', 'qol2'}),
    ('redux/tests/qa2/', {'qa2', 'texts'}), ('redux/tests/rules/', {'rules', 'qol2', 'qa2', 'qa'}),
    ('redux/tests/qol2/', {'qol2', 'qa', 'qa2'}), ('redux/tests/statview/', {'statview', 'evomoves'}),
    ('redux/tests/evomoves/', {'evomoves'}), ('redux/tests/fastsave/', {'fastsave'}),
    ('redux/tests/battleexit/', {'battleexit'}), ('redux/tests/ff/', {'feel'}), ('redux/tests/integ/', {'qol2'}),
    ('redux/tests/xmenu/', {'xmenu'}),
    ('redux/tests/perf/', set()),                  # the benchmark (rr.py --perf), no regression job
    ('redux/tests/menuspeed/', {'menus'}),
    ('redux/tests/', {'all'}),
]
IGNORED_PATHS = ('redux/README.md', 'redux/docs/', 'redux/notes/', 'README', 'redux/tests/rr.py', 'redux/tests/suite.py',
                 'redux/.gitignore')


def areas_for(paths):
    out = set()
    for p in paths:
        if any(p.startswith(i) for i in IGNORED_PATHS):
            continue
        for pre, a in AREAS_BY_PATH:
            if p.startswith(pre):
                out |= a
                break
        else:
            out.add('all')
    return out


def build(langs):
    """the job graph for these languages (the release ROMs are rr.py's --build, before any job)"""
    J = []

    def job(*a, **kw):
        j = Job(*a, **kw)
        J.append(j)
        return j

    Q = ('quick', 'full')
    job('qa.texts', 'qa', [['t_texts.py']], tiers=Q, areas={'menu', 'texts'}, est=5, inputs=['{RX}/qol/menu.py'])
    job('qa2.texts_check', 'qa2', [['texts_check.py']], tiers=Q, areas={'menu', 'texts'}, result='rc', est=5,
        inputs=['{RX}/qol/menu.py'] + [ROMS['rel'].replace('{L}', L) for L in langs])
    for L in langs:
        jp = L == 'jp'
        st = lambda kind, *names: [f'{{B}}/{kind}/states/{n}.dst' for n in names]
        # --- test ROMs (seconds each; never cached) ---
        for k, grp, script in (('qa', 'qa', 'build_test.py'), ('qa2', 'qa2', 'build_qa2.py'),
                               ('sv', 'statview', 'build_test.py'), ('em', 'evomoves', 'build_test.py')):
            job(f'build.{k}.{L}', grp, [[script, L]], tiers=('quick', 'full', 'perf'), areas={'all'}, result='rc', est=5,
                lang=L)
        # --- qa: the real opening on the release ROM ---
        job(f'qa.ng.rel_def.{L}', 'qa', [['t_newgame.py', L, 'def']], tiers=Q, areas={'menu', 'story', 'boot', 'qa'},
            est=50, lang=L, rom='rel', outputs=st('qa', f'rel_{L}_def_bedroom'))
        job(f'qa.ng.test_def.{L}', 'qa', [['t_newgame.py', L, 'def', 'test']], deps=[f'build.qa.{L}'],
            areas={'menu', 'qol2', 'qa'}, est=50, lang=L, rom='qa', outputs=st('qa', f'test_{L}_def_bedroom'))
        job(f'qa.ng.test_nuz.{L}', 'qa', [['t_newgame.py', L, 'nuz', 'test']], deps=[f'build.qa.{L}'], tiers=Q,
            areas={'menu', 'rules', 'qa'}, est=50, lang=L, rom='qa', outputs=st('qa', f'test_{L}_nuz_bedroom'))
        job(f'qa.story.{L}', 'qa', [['t_story.py', L]], deps=[f'qa.ng.rel_def.{L}'],
            areas={'story', 'followers', 'speed', 'qa'}, est=90, lang=L, rom='rel', outputs=st('qa', f'rel_{L}_s_*'))
        job(f'qa.smoke.{L}', 'qa', [['t_smoke.py', L]], deps=[f'qa.story.{L}'],
            areas={'story', 'followers', 'turbo', 'speed', 'fastsave', 'qa'}, est=90, lang=L, rom='rel',
            outputs=st('qa', f'rel_{L}_m_*') + [f'{{CFG}}/rel_{L}_smoke_{L}.dsv'])
        smoke_dsv = [('dsv', f'qa.smoke.{L}', f'rel_{L}_smoke_{L}.dsv')]
        job(f'qa.continue.{L}', 'qa', [['t_continue.py', L]], deps=[f'qa.smoke.{L}'], pre=smoke_dsv,
            areas={'story', 'fastsave', 'boot', 'qa'}, est=20, lang=L, rom='rel')
        job(f'qa.continue_unova.{L}', 'qa', [['t_continue.py', L, 'unova']], deps=[f'qa.smoke.{L}'], pre=smoke_dsv,
            areas={'story', 'menu', 'qa'}, est=20, lang=L, rom='rel')
        job(f'qa2.unova.{L}', 'qa2', [['t_unova.py', L]], deps=[f'qa.smoke.{L}'], pre=smoke_dsv,
            areas={'menu', 'qa2'}, est=30, lang=L, rom='rel')
        job(f'qa.rules.{L}', 'qa', [['t_rules.py', L] + (['t_battles_jp.py'] if jp else [])],
            deps=[f'qa.ng.test_nuz.{L}'], areas={'rules'}, est=120, lang=L, rom='qa')
        for p in ('fairy', 'large', 'surf'):
            job(f'qa.extra.{p}.{L}', 'qa', [['t_extra.py', L, p]], deps=[f'qol2.prep.{L}'], areas={'followers', 'qa'},
                est=40, lang=L, rom='qa')
        # --- qa2: settings menu and its features on the QA2 ROM ---
        for m in ('def', 'custom', 'nuz'):
            job(f'qa2.menu.{m}.{L}', 'qa2', [['t_menu.py', L, m]], deps=[f'build.qa2.{L}'],
                tiers=Q if m == 'custom' else ('full',), areas={'menu', 'qa2'}, est=60, lang=L, rom='qa2',
                outputs=st('qa2', f'qa2_{L}_{m}_bedroom'))
        job(f'qa2.view.{L}', 'qa2', [['t_view.py', L]], deps=[f'qa2.menu.custom.{L}'], tiers=Q, areas={'menu', 'qa2'},
            est=25, lang=L, rom='qa2')
        job(f'qa2.city.def.{L}', 'qa2', [['t_city.py', L, 'def_bedroom']], deps=[f'qa2.menu.def.{L}'],
            areas={'menu', 'qa2'}, est=30, lang=L, rom='qa2')
        job(f'qa2.city.custom.{L}', 'qa2', [['t_city.py', L, 'custom_bedroom']], deps=[f'qa2.menu.custom.{L}'],
            areas={'menu', 'qa2'}, est=30, lang=L, rom='qa2')
        job(f'qa2.limit.{L}', 'qa2', [['t_limit.py', L]], deps=[f'qa2.menu.nuz.{L}'], areas={'rules', 'qa2'}, est=60,
            lang=L, rom='qa2')
        for m in ('revive', 'egg'):
            job(f'qa2.nuz.{m}.{L}', 'qa2', [['t_nuz.py', L, m]], deps=[f'qa2.menu.nuz.{L}'], areas={'rules', 'qa2'},
                est=60, lang=L, rom='qa2')
        # the long ones run as one job per part: every part starts from its own load of the bedroom state, so a part
        # alone checks exactly what it checks inside the whole run (own run dir: NAME_PART)
        on_def = [('dex', [], {'qa2'}), ('candy.A', ['A'], {'qol2', 'qa2'}), ('candy.B', ['B'], {'qol2', 'qa2'}),
                  ('turbo.aspertia', ['aspertia'], {'turbo', 'speed', 'qa2'}),
                  ('turbo.grid_rail', ['grid', 'rail'], {'turbo', 'speed', 'qa2'})]
        on_def += [(f'cutin.{t}.{p}', [t, p], {'speed', 'turbo', 'qa2'}) for t in '01' for p in ('gym', 'surf', 'fly')]
        on_def += [(f'scenes.{s}.{n}', [s, n], {'speed', 'qa2'}) for s in ('on', 'off')
                   for n in ('sewers', 'frigate', 'chasm', 'virbank', 'driftveil', 'opelucid')]
        for name, args, ar in on_def:
            script = 't_' + name.split('.')[0] + '.py'
            job(f'qa2.{name}.{L}', 'qa2', [[script, L] + args], deps=[f'qa2.menu.def.{L}'], areas=ar, est=60, lang=L,
                rom='qa2')
        # --- qol2 suite on the QA test ROM (kind qa) ---
        job(f'qol2.bedroom.{L}', None, [], deps=[f'qa.ng.test_def.{L}'], result='internal', est=1, lang=L, areas={'qol2'},
            pre=[('copy', f'{{B}}/qa/states/test_{L}_def_bedroom.dst', f'{{B}}/qol2/states/qa_{L}_def_bedroom.dst')])
        job(f'qol2.prep.{L}', 'qol2', [['t_prep.py', L, 'def', 'qa']], deps=[f'qol2.bedroom.{L}'], areas={'qol2'},
            est=40, lang=L, rom='qa', outputs=st('qol2', f'qa_{L}_def_kg', f'qa_{L}_def_r19'))
        job(f'qol2.config.{L}', 'qol2', [['t_config.py', L, 'qa', 'def_bedroom']], deps=[f'qol2.bedroom.{L}'],
            areas={'qol2', 'menu'}, est=20, lang=L, rom='qa')
        job(f'qol2.mkopt.{L}', 'integ', [['mk_opt.py', L]], deps=[f'qol2.prep.{L}'], areas={'qol2'}, est=5, lang=L,
            rom='qa', outputs=st('qol2', f'qa_{L}_opt_bedroom', f'qa_{L}_opt_kg'))
        for w, args in (('pc', ['435', '9', '12', '0', 'def_pc']), ('r20', ['446', '158', '650', '0', 'def_r20'])):
            job(f'qol2.warp.{w}.{L}', 'qol2', [['t_warp.py', L, 'def_kg'] + args + ['qa']], deps=[f'qol2.prep.{L}'],
                areas={'qol2'}, est=20, lang=L, rom='qa', outputs=st('qol2', f'qa_{L}_{args[-1]}'))
        on_prep = [('apps', ['t_apps.py', L, 'qa', 'def']), ('catch', ['t_catch.py', L, 'qa', 'def']),
                   ('egg', ['t_egg.py', L, 'qa', 'def', 'A']), ('evo', ['t_evo.py', L, 'qa', 'def', 'A']),
                   ('fish', ['t_fish.py', L, 'qa', 'def']), ('level', ['t_level.py', L, 'qa', 'def', 'B', 'forget']),
                   ('surf.def', ['t_surf.py', L, 'qa', 'def']), ('save.def', ['t_save.py', L, 'qa', 'def']),
                   ('regress', ['t_regress.py', L, 'qa', 'def']),
                   ('walk', ['t_walk.py', L, 'qa', 'def_r19', 'UP', '90', 'b'] if jp else
                    ['t_walk.py', L, 'qa', 'def_r19', 'UP', '60']),
                   ('ci.turbo', ['t_ci.py', L, 'qa', 'def', 'turbo'])]
        if not jp:
            on_prep.append(('ci.def', ['t_ci.py', L, 'qa', 'def']))
        for name, argv in on_prep:
            job(f'qol2.{name}.{L}', 'qol2', [argv], deps=[f'qol2.prep.{L}'], areas={'qol2'}, est=40, lang=L, rom='qa',
                outputs=[f'{{CFG}}/qa_{L}_save_def.dsv'] if name == 'save.def' else [])
        job(f'qol2.pc.{L}', 'qol2', [['t_pc.py', L, 'qa', 'def']], deps=[f'qol2.warp.pc.{L}'], areas={'qol2'}, est=40,
            lang=L, rom='qa')
        job(f'qol2.sight.{L}', 'qol2', [['t_sight.py', L, 'qa', 'def']], deps=[f'qol2.warp.r20.{L}'], areas={'qol2'},
            est=40, lang=L, rom='qa')
        for name, argv in (('save.opt', ['t_save.py', L, 'qa', 'opt']), ('surf.opt', ['t_surf.py', L, 'qa', 'opt'])):
            job(f'qol2.{name}.{L}', 'qol2', [argv], deps=[f'qol2.mkopt.{L}'], areas={'qol2'}, est=40, lang=L, rom='qa',
                outputs=[f'{{CFG}}/qa_{L}_save_opt.dsv'] if name == 'save.opt' else [])
        for m in ('def',) + (() if jp else ('opt',)):
            job(f'qol2.boot.{m}.{L}', 'qol2', [['t_boot.py', L, 'qa', f'save_{m}']], deps=[f'qol2.save.{m}.{L}'],
                pre=[('dsv', f'qol2.save.{m}.{L}', f'qa_{L}_save_{m}.dsv')], areas={'qol2', 'boot', 'fastsave'},
                est=20, lang=L, rom='qa')
        # --- statview / evomoves (fixture battery: build/statview_integ/dsv) ---
        fix = [f'{{B}}/statview_integ/dsv/rel_{L}_smoke_{L}.dsv']
        for t in ('release', 'party', 'pc', 'egg', 'battle', 'select'):
            job(f'sv.{t}.{L}', 'statview', [[f't_{t}.py', L]], deps=[f'build.sv.{L}'], tiers=Q, areas={'statview'},
                est=40, lang=L, rom='sv', inputs=fix)
        for t in ('first', 'views', 'egg_pc', 'dex', 'dexstats'):
            job(f'em.{t}.{L}', 'evomoves', [[f't_{t}.py', L]], deps=[f'build.em.{L}'], tiers=Q, areas={'evomoves'},
                est=60, lang=L, rom='em', inputs=fix)
            job(f'em.mel.{t}.{L}', 'evomoves', [[f't_{t}.py', L]], deps=[f'build.em.{L}'], env={'EMU': 'melon'},
                areas={'evomoves'}, est=60, lang=L, rom='em', inputs=fix)
        # --- X menu: cursor on POKEMON (smoke fixture battery; the new game's bedroom state: no Pokemon yet) ---
        job(f'xmenu.game.{L}', 'xmenu', [['t_xmenu.py', L]], tiers=Q, areas={'xmenu', 'qol2'}, est=60, lang=L, rom='rel',
            inputs=fix)
        job(f'xmenu.mel.game.{L}', 'xmenu', [['t_xmenu.py', L]], env={'EMU': 'melon'}, tiers=Q, areas={'xmenu', 'qol2'},
            est=90, lang=L, rom='rel', inputs=fix)
        job(f'xmenu.bedroom.{L}', 'xmenu', [['t_xmenu.py', L, 'bedroom']], deps=[f'qa.ng.rel_def.{L}'], tiers=Q,
            areas={'xmenu'}, est=20, lang=L, rom='rel')
        # --- faster menus (qol/menuspeed): eager player, speed-ups on vs off: timing limits, no sound cut sooner,
        #     the same game state (smoke fixture battery; both emulators) ---
        for grp_name, sc in (('xparty', 'xmenu,party'), ('apps', 'apps,bag'), ('dex', 'dex'), ('pc', 'pc'),
                             ('shop', 'mart,nurse'), ('battle', 'battle')):
            job(f'menus.{grp_name}.{L}', 'menuspeed', [['t_menus.py', L, sc]], areas={'menus', 'qol2'},
                est=600, lang=L, rom='rel', inputs=fix, timeout=3600)
            job(f'menus.mel.{grp_name}.{L}', 'menuspeed', [['t_menus.py', L, sc]], env={'EMU': 'melon'},
                tiers=Q if grp_name == 'xparty' else ('full',), areas={'menus', 'qol2'}, est=500, lang=L, rom='rel',
                inputs=fix, timeout=3600)
        # --- fast save (on links to the release ROMs: fastsave_integ/rr) ---
        snap = '{B}/fastsave_integ/rr'
        rom, qmap = f'{snap}/redux3_{L}.nds', f'{snap}/qol_{L}/qol_map.json'
        src = {f'SRC_DSV_{L.upper()}': f'{{CFG:qol2.save.def.{L}}}/qa_{L}_save_def.dsv', 'FS_ELF': f'{snap}/follow_{L}.elf'}
        job(f'fs.gameover.{L}', 'fastsave', [['t_gameover.py', L]], deps=[f'qa.ng.test_nuz.{L}'], areas={'fastsave', 'rules'},
            est=60, lang=L, rom='qa')
        job(f'fs.firstsaves.{L}', 'fastsave', [['t_firstsaves.py', 'save', L], ['t_firstsaves.py', 'boot', L]],
            deps=[f'qa.ng.rel_def.{L}'], areas={'fastsave'}, est=60, lang=L, rom='rel')
        modes = [('mx.normal', f'mx_rr_{L}_tiny_normal', ['tiny', 'nosession2']),
                 ('mx.quick', f'mx_rr_{L}_tiny_quick', ['tiny', 'quick', 'nosession2']),
                 ('su.big', f'su_rr_{L}_big', ['big'])]
        if not jp:
            modes += [('su.none', f'su_rr_{L}_none', ['none']), ('su.pc1', f'su_rr_{L}_pc1', ['pc1']),
                      ('su.bigq', f'su_rr_{L}_bigq', ['big', 'quick']), ('su.off', f'su_rr_{L}_off', ['tiny', 'speedoff']),
                      ('su.stale', f'su_rr_{L}_stale', ['tiny', 'stale']),
                      ('su.stalenc', f'su_rr_{L}_stalenc', ['tiny', 'stalenocheck', 'nosession2'])]
        for name, tag, opts in modes:
            job(f'fs.{name}.{L}', 'fastsave',
                [['t_integ.py', s, rom, qmap, L, tag] + opts for s in ('save', 'boot')],
                deps=[f'qol2.save.def.{L}', 'fs.snap'], env=src, areas={'fastsave'}, est=60, lang=L, rom='rel',
                result='expect_fail' if name == 'su.stalenc' else 'RESULT')
        if not jp:
            job(f'fs.twice.{L}', 'fastsave', [['t_twice.py', rom, qmap, L, f'su_rr_{L}_3x', '3']],
                deps=[f'qol2.save.def.{L}', 'fs.snap'], env=src, areas={'fastsave'}, est=60, lang=L, result='rc', rom='rel')
        job(f'fs.no.{L}', 'fastsave', [['t_no.py', rom, qmap, L, f'su_rr_{L}_no']], deps=[f'qol2.save.def.{L}', 'fs.snap'],
            env=src, areas={'fastsave'}, est=40, lang=L, rom='rel')
        job(f'fs.newgame.{L}', 'fastsave', [['t_newgame.py', s, rom, qmap, L, f'su_rr_{L}_ng'] for s in ('save', 'boot')],
            deps=['fs.snap'], areas={'fastsave', 'menu'}, est=90, lang=L, rom='rel')
        # --- battle exit / fix-float measurements (no pass/fail) ---
        for w in ('r19', 'r20'):                 # one emulator per process: one save each (as jobs2 + jobs2b did)
            job(f'bx.mksave.{w}.{L}', 'battleexit', [['mksave.py', L, w]], deps=[f'qa.ng.test_nuz.{L}'],
                tiers=('full', 'perf'), areas={'battleexit'}, est=60, lang=L, rom='qa',
                outputs=[f'{{B}}/battleexit/saves/{w}_{L}.dsv'])
        for case in ('win', 'run', 'catch', 'trainer'):
            job(f'bx.measure.{case}.{L}', 'battleexit', [['measure.py', 'new', L, case]],
                deps=[f'bx.mksave.{"r20" if case == "trainer" else "r19"}.{L}'],
                tiers=('full', 'perf'), areas={'battleexit', 'speed'}, result='meas', est=40, lang=L, rom='rel')
        ffenv = {'SAV': f'rel_{L}_smoke_{L}.dsv'}
        ffix = [f'{{B}}/ff_integ/sav/rel_{L}_smoke_{L}.dsv']
        rel, elf = f'{{B}}/out/redux3_{L}.nds', f'{{B}}/redux3/{L}_follow.elf'
        catchenv = dict(ffenv, QOLMAP=f'{{B}}/qol/{L}/qol_map.json', EFFDBG='auto', THROWS='4')
        for name, extra in (('catch', {}), ('post', {'POST': 'field'}), ('turbo', {'POST': 'field', 'TURBO': '1'})):
            tag = f'm_{name}_{L}'
            job(f'ff.{name}.{L}', 'ff', [['catch.py', rel, tag], ['ballgap.py', f'{{B}}/ff_integ/out/{tag}/rec*']],
                env=dict(catchenv, **extra), tiers=('full', 'perf'), areas={'feel', 'followers', 'turbo'}, result='meas',
                est=60, lang=L, rom='rel', inputs=ffix)
        job(f'ff.meas.{L}', 'ff', [['meas2.py', rel, elf, f'm_meas_{L}']], env=ffenv, tiers=('full', 'perf'),
            areas={'feel', 'followers'}, result='meas', est=60, lang=L, rom='rel', inputs=ffix)
    job('fs.snap', None, [], result='internal', est=1, areas={'fastsave'}, pre=[('fs_snap', langs)])
    return J
