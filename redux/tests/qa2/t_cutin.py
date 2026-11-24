"""t_cutin.py LANG TURBO [PART..] : 3D cut-ins with speed-ups on, turbo off (TURBO 0) or on (1) (QA2 ROM, from
qa2_LANG_def_bedroom + the kit's 2 Dragonite Lv60 + all 8 badges by script). qol2_dbg.ci_extra counts the
cut-in's extra (2x) callback calls: they must happen with turbo off and not with turbo on (no 4x).
  gym   Aspertia Gym (zone 489): var 0x40A9 = 3 (both trainers beaten), talk to Cheren: his intro, the gym-leader
        VS cut-in, the battle (Dragon Claw), the post-battle scene (Basic Badge, TM83; flag 2414). MEAS frames
        from the battle start (wild/trainer encounter effect) to the first battle menu.
  surf  Aspertia pond (as t_extra): the second Dragonite knows Surf (the lead / follower doesn't): A at the water
        -> yes -> the Surf HM cut-in -> on the water. MEAS frames from YES to standing on the water.
  fly   Floccesy Town: a Tranquill Lv30 with Fly; X -> Pokémon -> Tranquill -> Fly -> Aspertia on the town map ->
        the Fly cut-in -> Aspertia. MEAS frames from the map choice to the arrival.
Shots build/qa2/cutin_LANG_TURBO/, sheet build/qa2/cutin_LANG_TURBO_sheet.png; frame recordings rec_*/."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qa2 import Q2

lang, turbo = sys.argv[1], int(sys.argv[2])
parts = sys.argv[3:] or ['gym', 'surf', 'fly']
q = Q2(f'cutin_{lang}_{turbo}' + ''.join('_' + p for p in sys.argv[3:]), lang)   # parts given: own run dir (rr.py splits)
BADGES = [f'    TrainerCardAddBadge {i}' for i in range(8)]
meas = {}


def setup(extra, badges=True):
    q.load('def_bedroom')
    q.step(10)
    q.bed('KIT')
    q.step(200)
    q.wait_free(2000, tap='B')
    q.script((BADGES if badges else []) + ['    PlayerEnableRunningShoes'] + extra)
    q.step(40)


def ci():
    return q.q2dbg().get('ci_extra', 0)


def rec(tag):
    d = os.path.join(q.dir, 'rec_' + tag)
    os.makedirs(d, exist_ok=True)
    for f in os.listdir(d):
        os.remove(os.path.join(d, f))
    q.rec_frames(d)
    q.every = 3


if 'gym' in parts:
    setup(['    WorkSetConst 0x40A9, 3', '    MapChangeWarp 489, 15, 5, 0'], badges=False)   # no Basic Badge yet
    q.say('gym zone', q.zone(), q.pos())
    q.check('gym (zone 489)', q.zone(), 489)
    q.check('gym: next to Cheren (on his stage, from the stairs)', q.nav(14, 2), True)
    q.face('RIGHT')
    if turbo:
        q.check('turbo on', q.turbo_set(1), True)
    c0 = ci()
    q.tap('A')
    field = lambda: q.r32(q.r32(0x021410F4) + 0x20) if q.gsys() else 0
    t_battle = None
    rec('gym')
    for i in range(3000):                     # Cheren's lines (A) until the field closes for the battle
        if not field():
            t_battle = q.frame
            break
        if i % 30 == 0:
            q.hold('A', 4)
        else:
            q.step(1)
    t_menu = None
    for i in range(3000):                     # encounter effect, VS cut-in, intro -> the battle menu
        q.step(1)
        if i % 5 == 0 and q.ui() == 'menu':
            t_menu = q.frame
            break
    q.rec = None
    meas['gym_intro_frames'] = (t_menu - t_battle) if t_menu and t_battle else None
    meas['gym_ci_extra'] = ci() - c0
    q.say('MEAS gym: field closed -> battle menu', meas['gym_intro_frames'], 'ci_extra', ci() - c0, 'turbo', q.turbo())
    q.check('gym: battle menu', t_menu is not None, True)
    q.snap('gym_battle_menu')
    for k in range(40):                       # Dragon Claw until the battle is over (the field is back)
        if field():
            break
        if q.ui() == 'menu':
            q.fight(0)
        for i in range(60):
            q.step(10)
            if field() or q.ui() == 'menu':
                break
            if i % 4 == 3:
                q.tap('A', idle=6)
    shots = 0
    for i in range(400):                      # the post-battle scene
        if q.field_ready():
            break
        if i % 8 == 0 and shots < 12:
            q.snap(f'gym_after_{shots:02d}')
            shots += 1
        q.tap('A', idle=10)
    q.check('gym: post-battle scene over, field free', q.wait_free(3000, tap='A'), True)
    q.check('gym: Basic Badge scene ran (flag 2414)', q.flag(2414), 1)
    q.snap('gym_end')

if 'surf' in parts:
    setup(['    PokePartyLearnMove 1, 0, 57', '    MapChangeWarp 427, 48, 764, 0'])
    q.wait_free(1500, tap='B')
    q.goto(50, 764)
    q.face('RIGHT')
    if turbo:
        q.check('turbo on', q.turbo_set(1), True)
    c0 = ci()
    q.tap('A')
    q.step(150)                               # "The water is a deep blue... Would you like to surf on it?" YES/NO
    q.snap('surf_question')
    q.check('surf: the question is up (event running)', q.event_running(), True)
    rec('surf')
    q.tap('A')                                # YES
    q.step(40)
    t0 = q.frame
    q.tap('A')                                # "Dragonite used Surf!" -> the cut-in
    t1 = None
    for i in range(600):
        q.step(1)
        w = q.wpos()
        if w and w[0] >= 51 and not q.event_running():
            t1 = q.frame
            break
    q.rec = None
    meas['surf_frames'] = (t1 - t0) if t1 else None
    meas['surf_ci_extra'] = ci() - c0
    q.say('MEAS surf: "used Surf!" closed -> on the water', meas['surf_frames'], 'ci_extra', ci() - c0)
    q.check('surf: on the water', t1 is not None, True)
    q.snap('surfing')

if 'fly' in parts:
    setup(['    FlagSet 2401', '    PokePartyAdd 0x8020, 520, 0, 30', '    PokePartyLearnMove 2, 0, 19',
           '    MapChangeWarp 439, 30, 30, 0'])
    q.wait_free(1500, tap='B')
    q.say('fly from zone', q.zone(), q.pos())
    q.snap('fly_start')
    if turbo:
        q.check('turbo on', q.turbo_set(1), True)
    c0 = ci()
    q.tap('X')
    q.step(40)
    q.touch(64, 48)                           # POKEMON
    q.step(120)
    q.snap('fly_party')
    q.touch(65, 80)                           # third slot: Tranquill
    q.step(60)
    q.snap('fly_mon_menu')
    q.touch(200, 109)                         # Fly
    q.step(150)
    q.snap('fly_map')
    for k in ('LEFT', 'DOWN'):                # Floccesy -> Route 19 -> Aspertia City
        q.tap(k)
        q.step(60)
        q.snap(f'fly_map_{k}')
    rec('fly')
    t0 = q.frame
    q.tap('A')
    t1 = None
    for i in range(1500):
        q.step(1)
        if q.zone() == 427 and q.field_ready():
            t1 = q.frame
            break
    q.rec = None
    meas['fly_frames'] = (t1 - t0) if t1 else None
    meas['fly_ci_extra'] = ci() - c0
    q.say('MEAS fly: map A -> Aspertia field free', meas['fly_frames'], 'ci_extra', ci() - c0)
    q.check('fly: arrived in Aspertia', t1 is not None, True)
    q.snap('fly_arrived')
q.say('MEASUREMENTS', meas)
q.result(dict(meas=meas))
q.sheet(both=True)
