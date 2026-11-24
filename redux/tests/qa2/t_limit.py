"""t_limit.py LANG : the species limit rule on the QA2 ROM, from qa2_LANG_nuz_bedroom (t_menu.py LANG nuz: Classic
Nuzlocke + graveyard + species limit "same species"). Dupes / first catch / nickname are switched off for the
scenarios that don't test them (rules_tst flag commands). Scenarios (bed menu kit + script wild battles):
  A same species, none owned: wild Patrat not blocked, caught (party)
  B a Patrat in the party: wild Patrat -> balls refused ("species limit" line), limit_blocks + 1
  C evolution line: wild Watchog (Patrat's line) refused (line message); D Off: Watchog not blocked
  E first catch only + statics count: a blocked encounter doesn't use the area; the next allowed one does
  F only in the PC: party full, Pidove caught to the PC; wild Pidove refused
  G graveyard box ignored: the party's Patrat fainted -> graveyard; wild Patrat allowed again
Shots build/qa2/limit_LANG/, sheet build/qa2/limit_LANG_sheet.png."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qa2 import Q2, FLAGS, V_LIMIT

lang = sys.argv[1]
q = Q2(f'limit_{lang}', lang)
q.load('nuz_bedroom')
q.step(10)
for f in ('dupes', 'first', 'nick', 'statics', 'noitems'):
    q.setflag(FLAGS[f], 0)
q.check('limit = same species (menu)', q.var(V_LIMIT), 1)
q.bed('KIT')
q.step(200)
q.wait_free(2000, tap='B')
party = lambda: [p[0] for p in q.tst()['party']]
q.check('kit', party(), [149, 149])


def blocked(sp, want, msg=None, tag=''):
    q.w16((q.sym['rules_dbg'] & ~1) + 10, 0xFF)          # rules_dbg.last_block: 0xFF = no rule evaluated
    q.check(f'{tag}: battle', q.wild(sp), True)
    d = q.dbg()
    got = d['last_block'] if d['last_block'] != 0xFF else 0  # all catch rules off: nothing evaluated = no block
    q.check(f'{tag}: species {sp} block', got, want)
    if msg:
        q.bag_use('balls', 0, tag + '_refused')
        q.check(f'{tag}: ball refused, message', q.dbg()['last_refuse_msg'], q.txt(msg))
        q.bag_close()
    q.check(f'{tag}: ran', q.run_away(), True)


def catch(sp, tag):
    q.check(f'{tag}: battle', q.wild(sp), True)
    q.check(f'{tag}: not blocked', q.dbg()['last_block'], 0)
    q.bag_use('balls', 0, tag + '_throw')
    if q.until({'yesno'}, 3000) == 'yesno':
        q.touch(128, 115)                    # nickname? NO
    q.wait_free(4000, tap='B')


catch(504, 'A')
q.check('A: Patrat in the party', party(), [149, 149, 504])
b0 = q.dbg2()['limit_blocks']
blocked(504, 3, 'RULES_CATCH_LIMIT', 'B')
q.check('B: limit_blocks + 1', q.dbg2()['limit_blocks'] - b0, 1)
q.setvar(V_LIMIT, 2)
blocked(505, 4, 'RULES_CATCH_LINE', 'C')
q.setvar(V_LIMIT, 0)
blocked(505, 0, None, 'D')
q.setvar(V_LIMIT, 1)
q.setflag(FLAGS['first'], 1)
q.setflag(FLAGS['statics'], 1)
a0 = q.areas()
blocked(504, 3, None, 'E1')
q.check('E1: area not used by the blocked encounter', q.areas(), a0)
blocked(506, 0, None, 'E2')
q.check('E2: the allowed encounter used the area', sorted(set(q.areas()) - set(a0)), [117])
q.setflag(FLAGS['first'], 0)
q.setflag(FLAGS['statics'], 0)
q.script(['    PokePartyAdd 0x8020, 506, 0, 5', '    PokePartyAdd 0x8020, 506, 0, 5', '    PokePartyAdd 0x8020, 506, 0, 5'])
q.check('F: party full', len(party()), 6)
catch(519, 'F')
q.check('F: Pidove not in the party (PC)', 519 in party(), False)
blocked(519, 3, 'RULES_CATCH_LIMIT', 'F2')
q.test_cmd(1, 2, 0)                          # the Patrat (slot 2): HP 0
g0 = q.tst()['grave']
blocked(506, 3, None, 'G0')                  # any battle: afterwards the fainted Patrat goes to the graveyard
q.check('G: Patrat moved to the graveyard', (504 in party(), q.tst()['grave'] - g0), (False, 1))
blocked(504, 0, None, 'G')
q.say('rules_dbg', q.dbg(), q.dbg2())
q.result()
q.sheet(both=True)
