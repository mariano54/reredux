"""ds.py : the base-stats helpers for the tests (dexstats.c DsDbg, the expected values from the named tree's personal.json,
opening a Pokédex entry with every species registered)."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from em import R

STATS = ('hp', 'atk', 'def', 'spa', 'spd', 'spe')
_P = None


def personal():
    global _P
    if _P is None:
        _P = json.load(open(R + '/build/named/redux/data/personal.json'))
    return _P


def expect(sp, form=0):
    """(stats in the summary order, total, abilities) of species sp's form (form_stats: the first alternate entry)"""
    p = personal()
    e = p[sp]
    if form and e['form_stats'] and form < e['form_count']:
        e = p[e['form_stats'] + form - 1]
    st = [e[k] for k in STATS]
    return st, sum(st), [e['ability1'], e['ability2'], e['ability_hidden']]


def ds(q):
    D = q.sym_addr('ds_dbg')
    r8, r16 = q.r8, q.r16
    d = dict(magic=q.r32(D))
    for i, n in enumerate('on ready shown pending caught foreign holds fail'.split()):
        d[n] = r8(D + 4 + i)
    d['species'], d['form'] = r16(D + 12), r16(D + 14)
    d['stats'] = [r16(D + 16 + 2 * i) for i in range(6)]
    d['abil'] = [r16(D + 28 + 2 * i) for i in range(3)]
    d['total'] = r16(D + 34)
    for i, n in enumerate('setups exits redraws flushes shows hides'.split()):
        d[n] = r16(D + 36 + 2 * i)
    t = r16(D + 48)
    d['tile'] = t - 0x10000 if t & 0x8000 else t
    d['maps'], d['restores'] = r16(D + 50), r16(D + 52)
    d['heap_free'], d['heap_after'] = q.r32(D + 56), q.r32(D + 60)
    d['bgcnt'] = r16(0x0400100C)
    d['bg2_on'] = (q.r32(0x04001000) >> 10) & 1
    return d


def register(q, a, b):
    """species a..b caught (q2tst cmd 7: party slot 1 set to each, then restored), national Pokédex on"""
    T = q.T
    q.w32(T + 8, a); q.w32(T + 12, b); q.w32(T + 4, 7)
    for _ in range(600):
        q.step(1)
        if not q.r32(T + 4):
            break
    return q.r32(T + 20)


def register_form(q, sp, form, lang=2):
    """species sp in form `form` registered as caught (slot 1 set to it; q2tst cmd 3 with its language)"""
    q.q2(2, 1, 0x05, sp)
    q.q2(2, 1, 0x6F, form)
    q.q2(3, 1, lang)


def open_dex(q):
    """the Pokédex (national list) opened on the list's entry -> INFO"""
    q.tap('X'); q.step(40); q.touch(192, 48); q.step(400)
    q.touch(28, 137); q.step(90)
    for _ in range(3):
        q.tap('UP', 1, 4)
    q.step(30)
    q.tap('A'); q.step(200)


def open_entry(q, last=649):
    """every species 1..last caught, the Pokédex opened on an entry (INFO)"""
    register(q, 1, last)
    open_dex(q)


def species_list(q):
    """the Pokédex context's species list (array, count, index pointer); dexstats' ctx is dexmoves' too: read it from
    the INFO page's own frame: the page module context is the 5th argument, kept by dexmoves only on its page, so the
    sweep goes to EVO/MOVES once (LEFT) and back (RIGHT)"""
    DX = q.sym_addr('dx_dbg')
    q.tap('LEFT'); q.step(150)
    ctx = q.r32(DX + 40)
    q.tap('RIGHT'); q.step(150)
    return q.r32(ctx + 0x18), q.r16(ctx + 0x1C), q.r32(ctx + 0x20)


def show(q, lst, count, idxp, sp, wait=80):
    """the next list entry = sp, DOWN: the entry shows it (wait until our redraw is flushed)"""
    D = q.sym_addr('ds_dbg')
    q.w16(lst + 2 * ((q.r16(idxp) + 1) % count), sp)
    r0 = q.r16(D + 40 + 2)
    q.tap('DOWN', 1, 2)
    for _ in range(wait):
        q.step(2)
        d = ds(q)
        if d['species'] == sp and d['flushes'] != r0 and not d['pending']:
            break
    q.step(24)                  # the entry takes the next key only after its own species change settled
    return ds(q)
