"""t_turbo.py LANG : R turbo with the bike, in Castelia (heavy maps), auto-run on rails (QA2 ROM, from
qa2_LANG_def_bedroom: speed-ups, turbo and auto-run on). Setup by script: a Patrat Lv10 (the follower), Running Shoes,
then a warp to Castelia's waterfront (zone 30, grid).
  grid  (zone 30): run / walk (B) / bike, each with turbo off and on: frames per tile from the player's world
        position, frames where the turbo's overrun guard dropped the extra tick, extra field ticks. Bike on: the
        follower goes into its ball (follow_dbg obj 0); bike off: it comes back out on the first step.
        Frames recorded (every 2nd) while biking with turbo -> ballfx_sheet contact sheets (map streaming).
  rail  (zone 28, Castelia's streets, a rail map; in through the Castelia gate 252): auto-run without B,
        walk with B, turbo on/off, bike + turbo; follower hidden (obj 0) on rails.
Results in the log (MEAS lines) and build/qa2/results.jsonl; shots build/qa2/turbo_LANG/."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qa2 import Q2

lang = sys.argv[1]
parts = sys.argv[2:] or ['aspertia', 'grid', 'rail']
q = Q2(f'turbo_{lang}' + ''.join('_' + p for p in sys.argv[2:]), lang)   # parts given: own run dir (rr.py splits)
S = os.path.dirname(os.path.abspath(__file__))
meas = {}


def follower_obj():
    return q.follower()[0]


def m(tag, d, frames, keys=(), rec=None):
    r = q.move_measure(d, frames, keys, rec)
    meas[tag] = r
    q.say('MEAS', tag, r, 'follower obj', follower_obj(), 'zone', q.zone())
    return r


def sheet(rec, tag, n=40):
    fs = sorted(f for f in os.listdir(rec) if f.endswith('.png'))
    if not fs:
        return
    a, b = int(fs[0][:6]), int(fs[-1][:6])
    step = max(2, ((b - a) // n) // 2 * 2)
    out = os.path.join(os.path.dirname(q.dir), f'turbo_{lang}_{tag}_sheet.png')
    subprocess.run([sys.executable, os.path.join(S, '..', 'ballfx_sheet.py'), rec, str(a), str(b), str(step), out,
                    '0', '0', '256', '192', '1'])
    q.say('sheet', out)


def fresh_rec(tag):
    d = os.path.join(q.dir, 'rec_' + tag)
    os.makedirs(d, exist_ok=True)
    for f in os.listdir(d):
        os.remove(os.path.join(d, f))
    return d


q.load('def_bedroom')
q.step(10)
q.script(['    PokePartyAdd 0x8020, 504, 0, 10', '    PlayerEnableRunningShoes'])
q.check('Patrat in the party', q.party_n(), 1)

if 'aspertia' in parts:                      # a light map for comparison: the Aspertia plaza (row 752)
    q.script(['    MapChangeWarp 427, 36, 752, 0'])
    q.step(30)
    q.check('Aspertia plaza', q.zone(), 427)
    q.turbo_set(0)
    m('aspertia_run', 'RIGHT', 50)
    q.turbo_set(1)
    m('aspertia_run_turbo', 'LEFT', 50)
    q.load('def_bedroom')
    q.step(10)
    q.script(['    PokePartyAdd 0x8020, 504, 0, 10', '    PlayerEnableRunningShoes'])

if 'grid' in parts:
    q.script(['    MapChangeWarp 30, 12, 7, 0'])
    q.step(30)
    q.say('zone', q.zone(), 'pos', q.pos(), 'wpos', q.wpos())
    q.check('Castelia waterfront (zone 30)', q.zone(), 30)
    q.hold('DOWN', 8)
    q.step(30)
    q.snap('castelia_grid')
    q.check('follower out on the grid map', follower_obj() != 0, True)
    q.check('turbo off', q.turbo_set(0), True)
    q.nav(5, 7)                               # the open row 7 runs x 5..21
    m('grid_run', 'RIGHT', 70)
    m('grid_walk_B', 'LEFT', 70, ('B',))
    q.check('turbo on', q.turbo_set(1), True)
    q.snap('turbo_on')
    q.nav(5, 7)
    m('grid_run_turbo', 'RIGHT', 70)
    m('grid_walk_B_turbo', 'LEFT', 70, ('B',))
    q.nav(5, 7)
    obj0 = follower_obj()
    q.check('follower still out after turbo running', obj0 != 0, True)
    # bike (Field_ToggleCycling, as the Bicycle does)
    q.bike()
    q.step(10)
    q.snap('bike_on_recall')
    q.step(50)
    q.check('bike: follower recalled (obj 0)', follower_obj(), 0)
    q.snap('bike_on')
    q.turbo_set(0)
    m('grid_bike', 'RIGHT', 40)
    q.turbo_set(1)
    rec = fresh_rec('bike_grid')
    m('grid_bike_turbo', 'LEFT', 40, rec=rec)
    m('grid_bike_turbo_down', 'DOWN', 40, rec=rec)
    m('grid_bike_turbo_up', 'UP', 40, rec=rec)
    m('grid_bike_turbo_right', 'RIGHT', 40, rec=rec)
    sheet(rec, 'bike_grid')
    q.bike()
    q.step(30)
    q.snap('bike_off')
    q.check('bike off: still no follower before a step', follower_obj() != 0 and q.follower()[1] is not None
            and q.r32(q.fdbg + 12) >> 28 == 0, False)
    rec2 = fresh_rec('release_grid')
    q.rec_frames(rec2)
    q.hold('RIGHT', 10)
    q.step(60)
    q.rec = None
    q.snap('bike_off_step')
    q.check('first step after the bike: follower out of its ball', follower_obj() != 0, True)
    sheet(rec2, 'release_grid', 30)
    q.save('turbo_grid_end')

if 'rail' in parts:
    q.script(['    MapChangeWarp 252, 4, 4, 0']) if 'grid' not in parts else None
    if 'grid' in parts:
        q.load('def_bedroom')
        q.step(10)
        q.script(['    PokePartyAdd 0x8020, 504, 0, 10', '    PlayerEnableRunningShoes'])
        q.script(['    MapChangeWarp 252, 4, 4, 0'])
    q.step(30)
    q.check('Castelia gate (zone 252)', q.zone(), 252)
    q.nav(2, 4)
    for _ in range(3):
        q.hold('LEFT', 20)
        q.wait_free(3000, tap='B')
        if q.zone() == 28:
            break
    q.step(60)
    q.say('zone', q.zone(), 'wpos', q.wpos())
    q.check('Castelia streets (zone 28, rail)', q.zone(), 28)
    q.snap('castelia_rail')
    q.hold('RIGHT', 10)
    q.step(30)
    q.check('rail map: follower hidden (obj 0)', follower_obj(), 0)
    q.turbo_set(0)
    rec = fresh_rec('rail')
    q.hold('LEFT', 24)                        # into the street, away from the gate
    q.step(20)
    seq = [('rail_run', 'LEFT', 40, ()), ('rail_walk_B', 'RIGHT', 40, ('B',)), ('T', 1, 0, 0),
           ('rail_run_turbo', 'LEFT', 40, ()), ('rail_walk_B_turbo', 'RIGHT', 40, ('B',)), ('BIKE', 0, 0, 0),
           ('rail_bike_turbo', 'LEFT', 30, ()), ('rail_bike_turbo_back', 'RIGHT', 30, ()), ('T', 0, 0, 0),
           ('rail_bike', 'LEFT', 30, ()), ('rail_bike_back', 'RIGHT', 30, ()), ('BIKE', 0, 0, 0)]
    for tag, d, n, keys in seq:
        if tag == 'T':
            q.turbo_set(d)
        elif tag == 'BIKE':
            q.bike()
            q.step(40)
            q.snap('rail_bike_toggle')
        else:
            m(tag, d, n, keys, rec=rec)
            q.check(f'{tag}: still in the streets (zone 28), follower hidden', (q.zone(), follower_obj()), (28, 0))
    sheet(rec, 'rail')
    q.snap('rail_end')
    run, walk = meas.get('rail_run', {}), meas.get('rail_walk_B', {})
    q.check('auto-run on rails: run without B faster than walking with B',
            bool(run.get('fpt') and walk.get('fpt') and run['fpt'] < walk['fpt']), True)
q.say('MEASUREMENTS', json.dumps(meas))
q.result(dict(meas=meas))
q.sheet(both=False)
