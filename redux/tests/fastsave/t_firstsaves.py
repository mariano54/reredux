"""t_firstsaves.py STAGE LANG : the first saves of a new game on the merged release ROM (fastsave x menu/story).
STAGE save: from the qa new-game bedroom state (build/qa/states/rel_LANG_def_bedroom.dst, copied to
  build/fastsave_integ/states/), no battery (own ROM link rel_LANG_fsfirst_LANG -> own .dsv): the story's
  bedroom -> Mom (first save, B2's whole-save write) -> outside -> Hugh -> the key bearer (gifts + save), driven like
  build/scripts/qa/t_story.py. After each save the exported battery must hold the RAM save buffer (snapshot when the
  save engine reaches state 11) in BOTH copies with valid CRCs / CRC table / header / commit. MEAS frames per save
  (engine state 0 -> 11) and fs_dbg.
STAGE boot: cold boot that battery (copied to fs_fsfirst_boot_LANG) -> Continue: the field, the zone, every block
  as after the key bearer's save. (Then run t_integ.py with SRC_DSV_LANG = that battery for a later menu save.)"""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import json, os, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'qa'))
import sav
from fs import FS

stage, lang = sys.argv[1], sys.argv[2]
BLK = sav.load_blocks()
DBG = 'skipped changed compared verified promoted dropped guard resets saves steps updates max_ticks seeded stale pg_written pg_skipped segs'.split()
B = os.path.dirname(FS)
OUTD = os.path.join(FS, 'out', f'firstsaves_{lang}')
os.makedirs(OUTD, exist_ok=True)
STATE_SRC = f'{B}/qa/states/rel_{lang}_def_bedroom.dst'
STATE = os.path.join(FS, 'states', f'rel_{lang}_def_bedroom.dst')
RUN = f'fsfirst_{lang}'
DSV = os.path.expanduser(f'{RR_DSV}/rel_{lang}_{RUN}.dsv')
JS = os.path.join(OUTD, 'firstsaves.json')
V = 0x40A1


def sdinfo(f):
    sc = f.r32(0x02140F60)
    sd = f.r32(sc + 0x10) if sc else 0
    return (sd, f.r32(sd + 0x34), f.r32(sd + 0x30)) if sd else (0, 0, 0)


def dbg(f):
    a = f.sym.get('fs_dbg')
    return {k: f.r32((a & ~1) + 12 + 4 * i) for i, k in enumerate(DBG)} if a else {}


if stage == 'save':
    import qa
    qa.QA_DIR, qa.ROMS, qa.STATES = FS + '/qa', FS + '/qa/roms', FS + '/states'
    from qa import QA
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    shutil.copy(STATE_SRC, STATE)
    q = QA(f'fs_firstsaves_{lang}', lang, 'rel', run=RUN)
    q.emu.savestate.load_file(STATE)
    q.say('state loaded', STATE)
    q.step(10)
    reg = q.emu.memory.register_arm9
    saves = []                          # per completed save: dict(start, done, snapshot)
    cur = {}
    writes = [0]

    def eng(a, s):
        # as t_integ.py: inside the engine step, state 10 pass 2 (the commit poll) = what both copies now hold
        sd = reg.r0
        v = q.r8(sd + 0x18)
        cur.setdefault('calls', 0)
        cur['calls'] += 1
        if 'start' not in cur:
            cur['start'] = q.frame
        if v == 10 and q.r8(sd + 0x19) == 1:
            buf, size = q.r32(sd + 0x34), q.r32(sd + 0x30)
            if True:
                cur['snap'] = bytes(q.m[buf: buf + size])
                cur['snapf'] = q.frame
        cur['last'] = v

    def collect():
        """the save since the last collect(): its first engine call, last commit poll, RAM then"""
        if cur.get('snap') is not None:
            saves.append(dict(start=cur.get('start'), done=cur['snapf'], ram=cur['snap'], calls=cur.get('calls')))
        cur.clear()
    q.emu.memory.register_exec(0x0203B9BC, eng, 2)
    q.emu.memory.register_exec(0x0203C07C, lambda a, s: writes.__setitem__(0, writes[0] + 1), 2)

    def free(n=8000):
        ok = q.wait_field(n, tap='A', settle=40)
        q.say('  free', ok, 'zone', q.zone(), 'pos', q.pos(), 'var40A1', q.var(V), 'frame', q.frame)
        return ok

    def check_battery(tag, k0):
        collect()
        new = saves[k0:]
        q.check(f'{tag}: a save completed', len(new) >= 1, True)
        if not new:
            return None
        s = new[-1]
        exp = os.path.join(OUTD, f'battery_{tag}.sav')
        if os.path.exists(exp):
            os.remove(exp)
        q.emu.backup.export_file(exp)
        c = sav.check(exp, s['ram'])
        q.say(f'{tag} battery', json.dumps(c))
        for cp in 'AB':
            q.check(f'{tag}: copy {cp}: every block == RAM', c[cp]['diff'], [])
            q.check(f'{tag}: copy {cp}: CRCs valid', c[cp]['bad'], [])
            q.check(f'{tag}: copy {cp}: CRC table/header/commit == RAM', c[cp]['foot_eq_ram'], True)
        q.check(f'{tag}: both copies same counter', c['A']['counter'] == c['B']['counter'], True)
        open(os.path.join(OUTD, f'ram_{tag}.bin'), 'wb').write(s['ram'])
        q.say(f'MEAS {tag}: saves {len(new)} frames', [(x['start'], x['done'],
              x['done'] - x['start'] if x['start'] else None) for x in new], 'card writes so far', writes[0],
              'fs_dbg', dbg(q))
        return c

    # Mom's scene (first save) -> outside the house
    k = len(saves)
    cur.clear()
    q.goto(10, 8)
    free()
    q.goto(4, 9)
    q.hold('DOWN', 20)
    free()
    q.check('outside the house (zone 427)', (q.zone(), q.pos()), (427, (47, 762)))
    q.snap('outside')
    c_mom = check_battery('mom', k)
    q.nav(43, 762)
    q.hold('UP', 10)
    free()
    q.check('Hugh met (var 0x40A1 = 1)', q.var(V), 1)
    # the key bearer (gifts + save)
    k = len(saves)
    cur.clear()
    q.nav(46, 726)
    q.face('UP')
    q.tap('A')
    free(9000)
    q.snap('keys')
    q.check("key bearer's gifts (flags 2965, 1603)", (q.flag(2965), q.flag(1603)), (1, 1))
    c_keys = check_battery('keys', k)
    expect = dict(zone=q.zone(), pos=list(q.pos()))
    q.step(30)
    q.emu.memory.register_exec(0x0203B9BC, None)
    q.emu.memory.register_exec(0x0203C07C, None)
    fails = list(q.fails)
    q.say('fails', fails)
    q.emu.close()                       # flush the battery to DSV
    json.dump(dict(expect=expect, fails=fails, dsv=DSV,
                   saves=[(x['start'], x['done']) for x in saves]), open(JS, 'w'))
    print('RESULT', 'PASS' if not fails else 'FAIL', '(save stage)')
else:
    from fs import F
    st = json.load(open(JS))
    ram = open(os.path.join(OUTD, 'ram_keys.bin'), 'rb').read()
    rom = f'{B}/out/redux3_{lang}.nds'
    g = F(rom, f'fs_fsfirst_boot_{lang}', f'firstsaves_{lang}_boot', dsv=st['dsv'],
          qmap=f'{B}/qol/{lang}/qol_map.json')
    ok = g.boot_continue()
    g.check('Continue reaches the field', ok is not None, True)
    g.step(10)
    sd, buf, size = sdinfo(g)
    cur = bytes(g.m[buf: buf + size])
    diff = [i for i, (o, s) in enumerate(BLK) if cur[o:o + s] != ram[o:o + s]]
    g.say('blocks differing after Continue (the game rewrites some on Continue):', diff, 'zone', g.zone())
    g.check('zone as saved', g.zone(), st['expect']['zone'])
    for i in list(range(1, 27)):
        if i in diff:
            g.check(f'block {i} (boxes / bag / party) as saved', False, True)
    g.shot('continue')
    g.close()
    fails = st['fails'] + g.fails
    print('FAILS', fails)
    print('RESULT', 'PASS' if not fails else 'FAIL')
