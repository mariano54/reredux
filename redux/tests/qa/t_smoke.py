"""t_smoke.py LANG [PART..] : gameplay smoke test on the release ROM from the t_story.py state after Mom's scene
(rel_LANG_s_mom: Aspertia, outside the Pokémon Center, Running Shoes, starter following).
Parts (default all, in order; each saves rel_LANG_m_<part>):
  run     Aspertia plaza (row 752): auto-run tile time (no B: 6 f/tile with speed-ups), B held: walking (8 f/tile with speed-ups);
          follower trails (distance <= 2)
  turbo   R in the field: turbo_dbg.on 1 + SE 0x54D, extra field ticks while walking; R again: off + SE 0x551
  talk    face the follower, A: its talk script runs (balloon / cry / text), close with A/B
  wild    through the gate (its first-visit scenes) to Route 19, walk in the grass until a wild battle; R in battle (turbo on, extra battle ticks), R off; Poké Ball;
          registration (new species) -> nickname yes/no seen -> NO -> field; the foe in the party (2 Pokémon)
  heal    back to Aspertia, Pokémon Center: Nurse (7, 10) heals
  mart    Poké Mart clerk (11, 16), from (9, 16) across the counter: Buy -> first item x1 -> yes -> leave
  menu    X menu: Pokémon (party -> first -> summary), Pokédex, Bag, Trainer Card (shots), each closed with B
  save    X -> Save -> yes -> saved; battery save left in <battery dir>/rel_LANG_smoke_LANG.dsv (t_continue.py)
SE ids played are logged (GFL_SndSEPlay hook). Shots build/qa/smoke_LANG/, sheet build/qa/smoke_LANG_sheet.png."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qa import QAR

lang = sys.argv[1]
parts = sys.argv[2:] or ['run', 'turbo', 'talk', 'wild', 'heal', 'mart', 'menu', 'save']
ALL = ['run', 'turbo', 'talk', 'wild', 'heal', 'mart', 'menu', 'save']
q = QAR(f'smoke_{lang}', lang, 'rel')
prev = ALL.index(parts[0]) - 1
q.load('s_mom' if prev < 0 else f'm_{ALL[prev]}')
q.step(10)
T = q.sym['turbo_dbg'] & ~1
R = q.sym['rules_dbg'] & ~1
se = []


def on_se(a, s):
    se.append((q.frame, q.emu.memory.register_arm9.r0))


q.emu.memory.register_exec(0x02006254, on_se, 2)


def tdbg():
    return dict(on=q.r8(T), live=q.r8(T + 1), field=q.r32(T + 16), battle=q.r32(T + 20))


def ses(since):
    return [hex(s) for f, s in se if f >= since]


def follower():
    v = q.r32(q.fdbg + 12)
    return q.r32(q.fdbg + 4), (v & 0xFFF, v >> 16 & 0xFFF)


def walk_measure(d, n, keys=()):
    """hold d (+keys) for n frames -> frames per tile (median of the steps after the first), follower distances"""
    for k in keys:
        q.emu.input.keypad_add_key(q.km(k))
    q.emu.input.keypad_add_key(q.km(d))
    ch, pos, dist = [], q.pos(), []
    for i in range(n):
        q.step(1)
        if q.pos() != pos:
            ch.append(q.frame)
            pos = q.pos()
            fo = follower()[1]
            dist.append(max(abs(fo[0] - pos[0]), abs(fo[1] - pos[1])))
    for k in (d,) + tuple(keys):
        q.emu.input.keypad_rm_key(q.km(k))
    q.step(20)
    iv = sorted(b - a for a, b in zip(ch, ch[1:]))
    return (iv[len(iv) // 2] if iv else None), dist


from desmume.controls import Keys, keymask
q.km = lambda k: keymask(getattr(Keys, 'KEY_' + k))
done = lambda p: q.save('m_' + p)

if 'run' in parts:
    q.nav(37, 752)
    q.face('RIGHT')
    t, dist = walk_measure('RIGHT', 60)
    q.say('auto-run: frames/tile', t, 'follower distance', dist)
    q.check('auto-run without B (6 f/tile with speed-ups, 8 without)', t is not None and t in (6, 8), True)
    q.check('follower trails (distance 1..2)', bool(dist) and all(1 <= x <= 2 for x in dist[1:]), True)
    q.snap('autorun')
    q.face('LEFT')
    t, dist = walk_measure('LEFT', 80, ('B',))
    q.say('B held: frames/tile', t, 'follower distance', dist)
    q.check('B held = walk (8 f/tile with speed-ups, 16 without)', t is not None and (7 <= t <= 9 or t >= 15), True)
    done('run')

if 'turbo' in parts:
    f0 = q.frame
    d0 = tdbg()
    q.tap('R')
    q.step(10)
    d1 = tdbg()
    q.check('R: turbo on + SE 0x54d', (d1['on'], '0x54d' in ses(f0)), (1, True))
    q.face('RIGHT')
    t, dist = walk_measure('RIGHT', 40)
    d2 = tdbg()
    q.say('turbo walk frames/tile', t, 'extra field ticks', d2['field'] - d1['field'])
    q.check('turbo: extra field ticks, faster tiles', (d2['field'] > d1['field'], t is not None and t <= 6), (True, True))
    q.snap('turbo_on')
    f1 = q.frame
    q.tap('R')
    q.step(10)
    q.check('R: turbo off + SE 0x551', (tdbg()['on'], '0x551' in ses(f1)), (0, True))
    done('turbo')

if 'talk' in parts:
    q.step(30)
    obj, (fx, fz) = follower()
    px, pz = q.pos()
    d = 'DOWN' if fz > pz else 'UP' if fz < pz else 'LEFT' if fx < px else 'RIGHT'
    q.face(d)
    f0 = q.frame
    q.tap('A')
    q.step(25)
    ev = q.event_running()
    q.snap('talk1')
    q.step(35)
    q.snap('talk2')
    q.step(40)
    q.snap('talk3')
    q.check('follower talk script runs', ev, True)
    q.say('talk SEs', ses(f0))
    q.check('field free after the talk', q.wait_field(2500, tap='A', settle=40), True)
    done('talk')


def to_route19():
    q.nav(52, 711)
    for _ in range(2):
        q.hold('UP', 20)
        q.wait_field(3000, tap='A', settle=40)
    q.nav(4, 2)
    for _ in range(2):
        q.hold('UP', 20)
        q.wait_field(3000, tap='A', settle=40)
    q.say('route 19?', q.zone(), q.pos())


def grass_battle():
    w0 = q.dbg()['wild_starts']
    to_route19()
    q.nav(60, 695)
    for i in range(400):
        # field-feel: one tile per move (hold until the tile changes), so the 6-frame run stays in the grass
        d = 'RIGHT' if (i // 2) % 2 else 'LEFT'
        p = q.pos()
        q.emu.input.keypad_add_key(keymask(getattr(Keys, 'KEY_' + d)))
        for _ in range(20):
            q.step(1)
            if q.pos() != p:
                break
        q.emu.input.keypad_rm_key(keymask(getattr(Keys, 'KEY_' + d)))
        q.step(4)
        if q.dbg()['wild_starts'] > w0:
            return True
    return False


if 'wild' in parts:
    q.check('wild battle started in the grass', grass_battle(), True)
    d = q.dbg()
    q.say('wild species', d['last_species'], 'area', d['last_area'])
    q.check('battle menu', q.until({'menu'}, 3000, tap='A'), 'menu')
    q.snap('wild_menu')
    f0, d0 = q.frame, tdbg()
    q.tap('R')
    q.step(60)
    d1 = tdbg()
    q.check('R in battle: turbo on, extra battle ticks, SE 0x54d',
            (d1['on'], d1['battle'] > d0['battle'], '0x54d' in ses(f0)), (1, True, True))
    q.tap('R')
    q.step(10)
    q.check('R in battle: off', tdbg()['on'], 0)
    caught = False
    for attempt in range(4):
        if q.ui() != 'menu':
            q.until({'menu'}, 2000, tap='B')
        q.bag_use('balls', 0, f'ball{attempt}')
        s = q.until({'yesno', 'menu'}, 4000, tap='B')
        q.say('after ball', attempt, '->', s)
        if s == 'yesno':
            q.snap('nickname_question')
            q.touch(128, 115)                   # NO
            caught = True
            break
        if s is None:
            break
    q.check('caught; registration -> nickname yes/no', caught, True)
    q.check('field after the catch', q.wait_field(3000, tap='B', settle=40), True)
    q.snap('after_catch')
    done('wild')

if 'heal' in parts:
    q.nav(52, 702)
    q.hold('DOWN', 20)
    q.wait_field(2000, tap=None)
    q.nav(4, 13)
    q.hold('DOWN', 20)
    q.wait_field(2000, tap=None)
    q.say('zone', q.zone(), 'pos', q.pos())
    q.nav(48, 740)
    q.hold('UP', 20)
    q.wait_field(2000, tap=None)
    q.check('in the Pokémon Center', q.zone(), 435)
    q.nav(7, 12)
    q.face('UP')
    q.tap('A')
    shots = 0
    for i in range(60):
        q.step(20)
        if i % 4 == 0 and shots < 10:
            q.snap(f'heal{shots}')
            shots += 1
        if q.field_ready():
            break
        q.tap('A')
    q.check('heal done, field free', q.wait_field(2000, tap='A', settle=40), True)
    done('heal')

if 'mart' in parts:
    q.nav(9, 16)
    q.face('RIGHT')
    seq = ['A', 'A', 'A', 'A', 'A', 'A', 'A']
    for k, key in enumerate(seq):
        q.tap(key)
        q.step(40)
        q.snap(f'mart{k}')
    for k in range(4):
        q.tap('B')
        q.step(40)
        q.snap(f'mart_b{k}')
    q.check('Mart: field free', q.wait_field(2000, tap='B', settle=40), True)
    done('mart')

if 'menu' in parts:
    q.tap('X')
    q.step(40)
    q.snap('xmenu')
    for name, pos in (('party', (64, 48)), ('dex', (190, 48)), ('bag', (64, 92)), ('card', (190, 92))):
        q.touch(*pos)
        q.step(90)
        q.snap(name)
        if name == 'party':
            q.tap('A')                       # opened by touch: the first A only selects the slot
            q.step(90)
            q.tap('A')                       # its menu
            q.step(90)
            q.snap('party_menu')
            q.tap('A')                       # Summary
            q.step(150)
            q.snap('summary')
            q.tap('RIGHT')
            q.step(40)
            q.snap('summary2')
            q.tap('B')
            q.step(60)
        for _ in range(3):
            q.tap('B')
            q.step(40)
        q.step(40)
        q.snap(name + '_closed')
        if q.field_ready():
            q.tap('X')
            q.step(40)
    q.check('menus closed, field free', q.wait_field(2000, tap='B', settle=40), True)
    done('menu')

if 'save' in parts:
    q.tap('X')
    q.step(40)
    q.touch(64, 136)
    q.step(60)
    q.snap('save_question')
    q.tap('A')
    for i in range(150):
        q.step(20)
        if q.field_ready():
            break
        if i % 10 == 9:
            q.tap('A')
    q.snap('saved')
    q.check('saved, field free', q.wait_field(2000, tap='A', settle=40), True)
    q.say('zone', q.zone(), 'pos', q.pos())
    done('save')
q.say('SEs', sorted({hex(s) for f, s in se})[:60])
q.result()
q.sheet(both=True)
