"""t_egg.py LANG KIND MODE TAP : forced egg hatch (research_qol2 D.2 pokes: lead Patrat counts as a ready egg) from
KIND_LANG_MODE_kg, one step in the bedroom -> "Oh?" -> hatch proc (ov307). TAP (A or none) every 20 frames
while the proc is in states <= 5 (wobble), then B (nickname: NO).
MEAS hatch = hatch proc first -> last frame (ov307 main 0x021DDC6A); wobble = state 5 frames."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, sys
from qt import QR

lang, kind, mode, tapk = sys.argv[1:5]
q = QR(f'egg_{kind}_{lang}_{mode}_{tapk}', lang, kind)
q.load(f'{mode}_kg')
POKES = [(0x02182328, 'f8b50090', '01207047'), (0x021AF6C8, '12d0', 'c046'), (0x021AF6D0, '0ed1', 'c046'),
         (0x0216E6A0, '06d0', 'c046')]
for a, o, n in POKES:
    q.cpoke(a, o, n)
st = []


def eh(a, s):
    w = q.emu.memory.register_arm9.r4
    v = q.r32(w + 0x10)
    if not st or st[-1][1] != v:
        st.append((q.frame, v))
    st_last[0] = q.frame


st_last = [0]
q.emu.memory.register_exec(0x021DDC6E, eh, 2)     # after `bl keys` (r4 = work)
q.step(5)
for k in range(8):
    p = q.pos()
    q.hold('RIGHT' if k % 2 == 0 else 'LEFT', 20)
    for i in range(30):
        if q.event_running():
            q.tap('B', idle=14)               # "Oh?"
        else:
            q.step(10)
        if st:
            break
    q.say('step', k, p, '->', q.pos(), 'event', q.event_running())
    if st:
        break
q.cpokes = []                                       # one hatch only
q.check('hatch proc started', bool(st), True)
q.rec = q.dir + '/rec'
os.makedirs(q.rec, exist_ok=True)
for i in range(200):
    cur = st[-1][1] if st else 0
    if q.frame - st_last[0] > 30 and st_last[0]:
        break
    if cur <= 5 and tapk != 'none':
        q.tap(tapk, idle=14)
    elif cur > 5:
        q.tap('B', idle=14)
    else:
        q.step(20)
q.rec = None
s5 = [f for f, v in st if v == 5]
s6 = [f for f, v in st if v == 6]
q.say('states', st)
q.say('MEAS hatch', st_last[0] - st[0][0], 'MEAS wobble', (s6[0] - s5[0]) if s5 and s6 else None)
ok = q.wait_free(1500, tap='B')
q.check('field after', ok, True)
q.say('species', q.pparam(0, 5), 'egg', q.pparam(0, 0x4C), 'qol2_dbg', q.q2dbg())
q.check('lead not an egg', q.pparam(0, 0x4C), 0)
q.snap('end')
q.result(dict(hatch=st_last[0] - st[0][0]))
