"""t_extra.py LANG [PART..] : checks that need the QA test ROM (kind qa = release modules + rules_test + qol2_test; states
from the qol2 suite: build/qol2/states/qa_LANG_def_kg / def_r19):
  fairy  lead species -> Clefairy (Redux: pure Fairy): party -> summary; shots show the type label (JP: フェアリー)
  large  Patrat fainted, a Dragonite leads (tried species until the follower is a large 64x64 one: tail box set);
         Route 19 -> the Aspertia gate (indoors: large ones can't follow): ballfx (recall) before the warp, no
         follower inside; back out: ballfx (release), follower out again
  surf   the follower's own Surf (Patrat with Surf, Aspertia pond): follower ops run (follow_dbg[5]) increase, frames
Shots build/qa/extra_LANG/, sheet build/qa/extra_LANG_sheet.png."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import qa as QAM
sys.path.insert(0, QAM.S + '/qol2')
from qt import QR

lang = sys.argv[1]
parts = sys.argv[2:] or ['fairy', 'large', 'surf']
XNAME = f'extra_{lang}' + ''.join('_' + p for p in sys.argv[2:])   # parts given: own run dir (rr.py splits)
q = QR(XNAME, lang, 'qa')
type(q).path = QAM.QA.path
type(q).nav = QAM.QA.nav
q.dir = os.path.join(QAM.QA_DIR, XNAME)
os.makedirs(q.dir, exist_ok=True)
import rt as RTM
# the follower code's ballfx_start (ITCM; its address moves with follow.c changes, so from the QA test ROM's ELF)
BALLFX = RTM.nm(f'{QAM.QA_DIR}/roms/qa_test_{lang}.elf', 'ballfx_start')


def follower():
    v = q.r32(q.fdbg + 12)
    return q.r32(q.fdbg + 4), (v & 0xFFF, v >> 16 & 0xFFF), q.r32(q.fdbg + 16)


if 'fairy' in parts:
    q.load('def_kg')
    q.step(5)
    q.set_pparam(0, 5, 35)
    q.check('lead is Clefairy', q.pparam(0, 5), 35)
    q.step(20)
    q.tap('X')
    q.step(40)
    q.touch(64, 48)
    q.step(90)
    q.snap('fairy_party')
    q.tap('A')                               # opened by touch: the first A only selects the slot
    q.step(90)
    q.tap('A')                               # its menu
    q.step(90)
    q.snap('fairy_party_menu')
    q.tap('A')                               # Summary (info page: Type)
    q.step(150)
    q.snap('fairy_summary')
    for k in range(2):
        q.tap('RIGHT')
        q.step(40)
        q.snap(f'fairy_summary{k + 2}')
    for _ in range(4):
        q.tap('B')
        q.step(40)
    q.check('field after the summary', q.wait_free(1500, tap='B'), True)

if 'large' in parts:
    q.load('def_r19')
    q.step(5)
    q.test_cmd(1, 0, 0)                       # Patrat (slot 0) fainted -> slot 1 leads
    large = None
    for sp in (149, 95, 208, 130, 321, 248, 384, 646):
        q.set_pparam(1, 5, sp)
        for d in ('LEFT', 'LEFT', 'RIGHT', 'RIGHT'):     # the tail box is placed once the follower walks
            q.hold(d, 10)
            q.step(30)
        obj, fpos, tail = follower()
        q.say('species', sp, 'follower obj', hex(obj), 'tail box', hex(tail))
        if tail:
            large = sp
            break
    q.check('a large follower (tail box)', large is not None, True)
    q.snap('large_route19')
    ev = []
    q.emu.memory.register_exec(BALLFX, lambda a, s: ev.append(q.frame), 2)
    q.rec = q.dir + '/rec_large'
    os.makedirs(q.rec, exist_ok=True)
    q.nav(52, 702)
    q.snap('large_at_gate')
    n0, z0 = len(ev), q.zone()
    q.hold('DOWN', 12)
    q.wait_free(1500)
    q.step(30)
    q.snap('large_inside_gate')
    obj, fpos, tail = follower()
    q.say('inside: zone', q.zone(), 'ballfx calls', ev[n0:], 'follower', hex(obj), fpos)
    q.check('recall: ballfx before the warp, inside the gate', (len(ev) > n0, q.zone()), (True, 438))
    n1 = len(ev)
    q.hold('UP', 12)
    q.wait_free(1500)
    for _ in range(3):
        q.hold('UP', 10)
        q.step(20)
    q.step(60)
    q.rec = None
    obj, fpos, tail = follower()
    q.snap('large_back_out')
    q.say('outside: zone', q.zone(), 'ballfx calls', ev[n1:], 'follower', hex(obj), fpos, 'tail', hex(tail))
    q.check('release: ballfx again on Route 19, large follower out', (len(ev) > n1, q.zone(), tail != 0),
            (True, 437, True))

if 'surf' in parts:
    q.load('def_kg')
    q.step(5)
    q.set_pparam(0, 0x39, 57)
    q.set_flag(2406, 0)
    q.bed_warp(427, 48, 764, 0)
    q.wait_free(1500, tap='B')
    q.step(30)
    q.goto(50, 764)
    q.hold('RIGHT', 3)
    q.step(20)
    ops0 = q.r32(q.fdbg + 20)
    q.rec = q.dir + '/rec_surf'
    os.makedirs(q.rec, exist_ok=True)
    on = None
    for i in range(60):
        q.hold('A', 4)
        q.step(16)
        if q.pos() == (51, 764):
            on = q.frame
            break
    q.step(60)
    q.rec = None
    ops1 = q.r32(q.fdbg + 20)
    q.say('follower ops run', ops0, '->', ops1, 'last op', hex(q.r32(q.fdbg + 24)))
    q.snap('surfing')
    q.check('follower Surf: ops ran, player on the water', (ops1 > ops0, on is not None), (True, True))
q.result()
QAM.QA.sheet(q, both=True)
