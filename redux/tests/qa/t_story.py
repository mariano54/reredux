"""t_story.py LANG [FROM] : the real opening on the release ROM, from the t_newgame.py bedroom state (rel_LANG_def_bedroom)
to Route 19: Mom (first save) -> outside -> Hugh -> Redux's key bearer on the lookout stairs (keys + save) -> Bianca ->
Hugh's push-back -> starter (choice, nickname yes/no + name entry, Pokédex) -> follower out -> Hugh's Pokédex scene
-> rival battle (VS cut-in, A taps) -> Pokémon Center tour (heal, PC, Mart, Poké Balls) -> Mom (Running Shoes)
-> Aspertia gate -> Route 19. Navigation: qa.QA.nav (BFS on the map permission grid, perm.py).
States build/qa/states/rel_LANG_s_<stage>.dst (FROM resumes at a stage). Shots build/qa/story_LANG/ (+ rec/ every
90 frames), sheet build/qa/story_LANG_sheet.png."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
from rrenv import skip_frames, no_skip, RENDER_TAIL  # noqa: E402,F401  (RR_SKIP_RENDER: draw only what is looked at)
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qa import QA

lang = sys.argv[1]
start = sys.argv[2] if len(sys.argv) > 2 else None
q = QA(f'story_{lang}', lang, 'rel')
rec = os.path.join(q.dir, 'rec')
os.makedirs(rec, exist_ok=True)
_step = q.step
cutin_modes = []
watch_cutin = False


def step(n=1):
    for k in range(n):
        if (-(q.frame + 1)) % 90 < RENDER_TAIL:      # the rec/ frame and the ones before it are drawn
            no_skip(q.emu)
        elif k < n - RENDER_TAIL:
            skip_frames(q.emu, 1)
        _step(1)
        if watch_cutin:
            field = q.r32(q.gsys() + 0x20) if q.gsys() else 0
            if 0x02000000 <= field < 0x02400000 and q.r32(field + 0x13C) == 1:
                cutin_modes.append(q.r8(q.sym['fps60_dbg'] + 1))
        if q.frame % 90 == 0:
            q.emu.screenshot().save(os.path.join(rec, f'{q.frame:06d}.png'))


q.step = step
STAGES = ['bedroom', 'outside', 'hugh', 'keys', 'lookout', 'bianca1', 'pushback', 'starter', 'hughdex', 'battle',
          'center', 'mom', 'r19']
V = 0x40A1


def free(n=8000):
    ok = q.wait_field(n, tap='A', settle=40)
    q.say('  free', ok, 'zone', q.zone(), 'pos', q.pos(), 'var40A1', q.var(V), 'frame', q.frame)
    return ok


def follower():
    """follow_dbg[1] = follower object code (0 = none), [3] = its tile"""
    return q.r32(q.fdbg + 4), q.r32(q.fdbg + 12)


def stage(name):
    q.save('s_' + name)
    q.snap(name)


def run(name):
    return start is None or STAGES.index(name) >= STAGES.index(start)


if start:
    q.load('s_' + STAGES[STAGES.index(start) - 1] if STAGES.index(start) else 'def_bedroom')
else:
    q.load('def_bedroom')
q.step(10)

if run('outside'):
    q.goto(10, 8)
    free()
    q.goto(4, 9)
    q.hold('DOWN', 20)
    free()
    q.check('outside the house (zone 427)', (q.zone(), q.pos()), (427, (47, 762)))
    stage('outside')
if run('hugh'):
    q.nav(43, 762)
    q.hold('UP', 10)
    free()
    q.check('Hugh met (var 0x40A1 = 1)', q.var(V), 1)
    stage('hugh')
if run('keys'):
    q.nav(46, 726)
    q.face('UP')
    q.tap('A')
    free(9000)
    stage('keys')
    ki = q.keyinfo()
    q.say('KeyInfo after the key bearer', ki)
    q.check('key bearer: no keys, difficulty / city unchanged', ki and (ki['obtained'], ki['unlocked'],
            ki['difficulty'], ki['city']), ([0] * 5, [0] * 5, 2, 0))
    q.check('key bearer: his other gifts (National Pokédex flag 2965, 1603)', (q.flag(2965), q.flag(1603)), (1, 1))
    q.check('key bearer gone (stairs free)', q.nav(37, 722), True)
if run('lookout'):
    for _ in range(3):
        q.hold('UP', 30)
        free()
    q.check('lookout: var 2', q.var(V), 2)
    stage('lookout')
if run('bianca1'):
    q.nav(36, 710)
    q.face('UP')
    q.tap('A')
    free(9000)
    q.check('Bianca met: var 3', q.var(V), 3)
    stage('bianca1')
if run('pushback'):
    q.nav(37, 719)
    q.hold('DOWN', 16)
    free()
    stage('pushback')
if run('starter'):
    q.check('no follower before the starter', follower()[0], 0)
    q.nav(36, 710)
    q.face('UP')
    watch_cutin = True
    q.tap('A')
    free(15000)
    watch_cutin = False
    q.check('Pokédex cut-in observed', bool(cutin_modes), True)
    q.check('Pokédex cut-in keeps native draw cadence', set(cutin_modes), {0})
    q.step(30)
    f = follower()
    q.say('follower obj', hex(f[0]), 'tile', (f[1] & 0xFFF, f[1] >> 16 & 0xFFF))
    q.check('starter: var 4, follower out', (q.var(V), f[0] != 0), (4, True))
    stage('starter')
if run('hughdex'):
    for _ in range(4):
        if q.var(V) >= 5:
            break
        q.hold('DOWN', 24)
        free()
    q.check("Hugh's Pokédex scene: var 5", q.var(V), 5)
    stage('hughdex')
if run('battle'):
    q.hold('DOWN', 24)
    free(40000)
    q.check('rival battle + Pokémon Center tour: zone 435, var 6', (q.zone(), q.var(V)), (435, 6))
    stage('battle')
if run('center'):
    stage('center')
if run('mom'):
    q.goto(6, 18)
    q.hold('DOWN', 20)
    free(20000)
    q.check('Mom (Running Shoes): var 7', (q.zone(), q.var(V), q.flag(0x963)), (427, 7, 1))
    stage('mom')
if run('r19'):
    q.nav(52, 711)
    q.hold('UP', 20)
    free()
    q.hold('UP', 20)
    free()
    q.goto(4, 2)
    q.hold('UP', 20)
    free()
    q.hold('UP', 20)
    free()
    q.check('Route 19', q.zone(), 437)
    f = follower()
    q.check('follower on Route 19', f[0] != 0, True)
    stage('r19')
q.result()
q.sheet(both=True)
q.sheet(rec, os.path.join(os.path.dirname(q.dir), f'story_{lang}_rec_sheet.png'))
