"""t_pc.py LANG KIND MODE : Pokémon Center PC (zone 435) from KIND_LANG_MODE_pc: stand below the PC, A every 20 frames
(boot, "Which PC?" -> Someone's PC, storage list -> first item) until the Box app is lit; then R (next box)
x3; then B every 20 frames until the field is free (exit prompt answered by B/A as needed).
MEAS open = A -> Box app lit; switch = frames of each box switch (screen changing); close = first B -> field."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, sys
from qt import QR
from PIL import ImageChops, ImageStat

lang, kind, mode = sys.argv[1:4]
q = QR(f'pc_{kind}_{lang}_{mode}', lang, kind)
q.load(f'{mode}_pc')
q.step(5)
q.check('at 435', q.zone(), 435)
q.goto(4, 12)
q.face('UP')
q.step(20)
q.rec = q.dir + '/rec'
os.makedirs(q.rec, exist_ok=True)
t0 = q.frame
box = None
dark = False
LM = q.r32(0x0216B538 + 4 * 0xB2) & ~1     # script command ListMenuInitTR handler (OVL_12)
q.say('ListMenuInitTR handler', hex(LM))
q.hook(LM, 'listmenu')


def storage_list():
    """the second list menu of the PC script (the storage list) is up"""
    lm = [e[0] for e in q.events if e[1] == 'listmenu']
    return len(lm) >= 2 and q.frame - lm[1] > 30


chosen = os.environ.get('PCMODE', 'move') != 'move'
for i in range(80):
    if not chosen and storage_list():
        q.step(10)
        q.tap('DOWN')
        q.tap('DOWN')                     # Deposit, Withdraw, Move Pokémon
        q.snap('storage_list')
        chosen = True
    q.hold('A', 4)
    for k in range(16):
        q.step(1)
        if not q.normal():
            dark = True
    if dark and q.zone() is not None and q.until_lit(200, 15):
        box = q.frame
        break
q.say('MEAS open', (box - t0) if box else None)
q.snap('box')
q.step(30)


def img():
    return q.emu.screenshot().convert('L').resize((128, 192))


sw = []
for k in range(3):
    ref = img()
    q.hold('R', 4)
    t = q.frame - 4
    last = t
    prev = ref
    for i in range(80):
        q.step(1)
        cur = img()
        if ImageStat.Stat(ImageChops.difference(cur, prev)).mean[0] > 0.3:
            last = q.frame
        prev = cur
    sw.append(last - t)
q.say('MEAS switch', sw, 'qol2_dbg', q.q2dbg())
q.snap('box3')
tc = q.frame
ok = False
for i in range(80):
    q.tap('B', idle=14)
    if q.field_ready() and q.normal():
        ok = True
        break
q.rec = None
ok = ok and q.wait_free(300)
q.say('MEAS close', q.frame - tc)
q.check('box opened', box is not None, True)
q.check('field after', ok, True)
q.snap('end')
q.result(dict(open=(box - t0) if box else None, switch=sw, close=q.frame - tc))
