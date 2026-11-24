"""measure.py ROMKIND LANG CASE [TAG] : battle-exit timing from a portable battery save (mksave.py), frame-exact.

ROMKIND: b2 (vanilla Black 2: EN black2.nds, JP jp_orig.nds), redux (EN redux.nds; JP = Redux + jp_port,
build/redux3/jp_base.nds), r3 (Redux 3.0 release build/out/redux3_LANG.nds), or a path to a .nds (TAG names the run).
CASE: win | run | catch | trainer  (win/run/catch from r19_LANG.dsv: walk in the Route 19 grass; trainer from
r20_LANG.dsv: one step DOWN into trainer 3392's line).
Boot -> Continue -> case -> battle -> (catch: Pokédex page, nickname question answered NO) -> field.
Per frame (from the last battle input on): master brightness, mean luma of both screens, and (US-code ROMs)
GameEvent callbacks, fades, overlay loads, BGM calls, CPU scanlines (bxlib).
MEAS (frames): t0 = last frame of the battle at full brightness before its fade-out; t1 = first frame the field is
at full brightness, lit and controllable (no event running; probe: a held direction moves the player).
exit = t1 - t0; dark = frames in [t0, t1) whose top screen is dark (mean luma < 24).
For catch: exit counts from the battle fade-out to the dex page (in1) plus from the NO answer to the field (out).
Output build/battleexit/<run>/ : trace.json, timeline.txt, rec/ (every frame of the window), MEAS lines in log."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bxlib
from bxlib import Bx, bright

B = bxlib.B
kind, lang, case = sys.argv[1], sys.argv[2], sys.argv[3]
ROMS = {('b2', 'en'): B + '/vanilla_rom/black2.nds', ('b2', 'jp'): B + '/jp_rom/jp_orig.nds',
        ('redux', 'en'): B + '/vanilla_rom/redux.nds', ('redux', 'jp'): B + '/redux3/jp_base.nds',
        ('r3', 'en'): B + '/base/redux3_en.nds', ('r3', 'jp'): B + '/base/redux3_jp.nds',
        ('new', 'en'): B + '/out/redux3_en.nds', ('new', 'jp'): B + '/out/redux3_jp.nds'}
if kind.endswith('.nds'):
    rom, kind = kind, (sys.argv[4] if len(sys.argv) > 4 else 'x')
else:
    rom = ROMS[(kind, lang)]
us = not (kind == 'b2' and lang == 'jp')
name = f'bx_{kind}_{lang}_{case}' + ('_off' if os.environ.get('SPEEDOFF') else '')
save = f'{B}/battleexit/saves/{"r20" if case == "trainer" else "r19"}_{lang}.dsv'
q = Bx(rom, name, us=us, save=save, qol_map=f'{B}/qol/{lang}/qol_map.json' if kind == 'new' else None)
q.say('rom', rom, 'us', us, 'save', save)
HOOKS = {0x0217F600: 'ProcInit', 0x0217F73C: 'FieldCreate', 0x0217F85C: 'R0open', 0x0217F96C: 'R1mapload',
         0x0217FDF0: 'R2spawnfin', 0x0217FF64: 'R3run', 0x0218011C: 'R3alt', 0x0204A7B4: 'arcread',
         0x0204B4E4: 'arcreadLZ', 0x0204AB1C: 'tool_read', 0x0204ABA4: 'tool_read2', 0x020712B0: 'ovl',
         0x02199CD4: 'btl_end'}
if os.environ.get('PROFILE') and us:
    for a, t in HOOKS.items():
        q.hook(a, t)
    q.hook(0x02070E40, 'rd', lambda q: q.emu.memory.register_arm9.r2)
REC = os.path.join(q.dir, 'rec')


def luma(im, top=True):
    box = (0, 0, 256, 192) if top else (0, 192, 256, 384)
    g = im.convert('L').crop(box).resize((64, 48))
    d = list(g.getdata())
    return sum(d) / len(d)


def ui():
    p = q.emu.screenshot().convert('RGB').getpixel
    if p((215, 357)) == (112, 216, 48):
        return 'menu'
    if p((240, 212)) == (128, 8, 8) and p((128, 212)) == (32, 32, 32) and p((128, 270)) == (32, 32, 32):
        return 'yesno'
    if p((128, 242))[0] > 200 and p((240, 212))[0] > 100 and p((240, 212))[1] < 40:
        return 'yesno'
    return None


def field_free():
    return q.zone() is not None and not q.event_running() and q.normal()


# --- boot -> Continue ----------------------------------------------------------------------------------
q.step(500)
ok = 0
for i in range(400):
    q.tap('A', idle=10)
    if us and q.gsys() and q.zone():
        break
    if not us and i > 60:
        break
for i in range(600):
    q.step(1)
    ok = ok + 1 if (not us or (q.zone() and not q.event_running())) else 0
    if ok >= 60:
        break
if os.environ.get('SPEEDOFF') and us:
    q.set_flag(0x5DA)          # speed-ups OFF (vanilla timings on the same ROM)
    q.say('speed-ups off (flag 0x5DA set)')
q.shot('continued')
q.say('continued at', q.frame, 'zone', q.zone() if us else '?')

# --- into a battle -----------------------------------------------------------------------------------
lumas = []          # (frame, top luma, bottom luma, brightness top, brightness bottom)


def stepl(n=1):
    for _ in range(n):
        q.step(1)
        im = q.emu.screenshot()
        lumas.append((q.frame, round(luma(im), 1), round(luma(im, False), 1),
                      bright(q.m.read_short(0x0400006C)), bright(q.m.read_short(0x0400106C))))
        if q.rec:
            im.save(os.path.join(q.rec, f'{q.frame:06d}.png'), compress_level=1)


def battle_started():
    if us:
        return any(cb == 0x02168BAD for cb, st in q.cur['ev']) or q.r32(q.gsys() + 0x18) and \
            q.r32(q.r32(q.gsys() + 0x18) + 4) == 0x02168BAD
    return False


if case == 'trainer':
    q.hold('DOWN', 10)
    q.step(4)
else:
    for i in range(600):
        q.hold('RIGHT' if (i // 2) % 2 else 'LEFT', 10)
        q.step(4)
        if (us and q.battles) or (not us and ui() is not None):
            break
q.say('encounter at', q.frame)
st = None
for i in range(400):
    q.tap('B' if case != 'trainer' else 'A', idle=14)
    st = ui()
    if st == 'menu':
        break
q.say('battle menu', st, 'at', q.frame)
q.shot('menu')

# --- the last input --------------------------------------------------------------------------------
if case in ('win', 'trainer'):
    pass
elif case == 'run':
    q.touch(128, 170, idle=0)
elif case == 'catch':
    q.touch(40, 165, idle=60)        # BAG
    q.touch(190, 40, idle=60)        # Poké Balls pocket
    q.touch(65, 30, idle=60)         # first ball (Master Ball)
    q.touch(128, 175, idle=0)        # USE

q.trace(True, REC)
t_input = q.frame


def hold(k, n):
    q.press(k)
    stepl(n)
    q.release(k)


def touch(x, y, idle):
    q.emu.input.touch_set_pos(x, y)
    stepl(6)
    q.emu.input.touch_release()
    stepl(idle)


def bc_state():
    if not q.rows:
        return None
    b = [st for cb, st in q.rows[-1]['ev'] if cb == 0x02168BAD]
    return b[-1] if b else None


phase = 'battle'
t_no = None
dark_run = 0
seen_dark = 0
lit_run = 0
t_lit = None
PROBE_STATE = os.path.join(q.dir, 'probe.dst')


def nonus_back():
    """address-free: after a dark run (>= 10 frames), the first frame of a lit run (>= 40 frames); a state is
    saved at that frame for the controllability probe -> True when done"""
    global seen_dark, lit_run, t_lit
    lit = lumas[-1][1] >= 24 and lumas[-1][3] == 0 and lumas[-1][4] == 0
    if not lit:
        seen_dark += 1
        lit_run = 0
        return False
    if seen_dark < 10:
        return False
    lit_run += 1
    if lit_run == 1:
        t_lit = q.frame
        q.save_state(PROBE_STATE)
    return lit_run >= 40


for i in range(8000):
    if phase == 'battle':
        if case in ('win', 'trainer') and i % 4 == 0 and ui() == 'menu':
            touch(128, 95, 40)        # FIGHT
            touch(65, 50, 0)          # move 1 (Dragon Claw)
            continue
        if i % 20 == 0:
            hold('B', 4)
        else:
            stepl()
        if us:
            s = bc_state()
            if s is not None and s >= 4:
                phase = 'post'
        else:
            dark_run = dark_run + 1 if lumas[-1][1] < 24 else 0
            if dark_run >= 10:
                phase = 'post'
                seen_dark = dark_run
    elif phase == 'post':
        if case == 'catch':
            if i % 4 == 0 and ui() == 'yesno':
                t_no = q.frame
                touch(128, 115, 0)    # NO
                phase = 'back'
                seen_dark = lit_run = 0
                continue
            if i % 20 == 0 and lumas[-1][1] >= 24:
                hold('A', 4)
                continue
        stepl()
        if us and os.environ.get('PROBE') and case != 'catch':
            nonus_back()
        if case != 'catch' and us and field_free():
            phase = 'done'
        elif case != 'catch' and not us and nonus_back():
            phase = 'done'
    elif phase == 'back':
        stepl()
        if us and os.environ.get('PROBE'):
            nonus_back()
        if us and field_free():
            phase = 'done'
        elif not us and nonus_back():
            phase = 'done'
    if phase == 'done':
        break
q.trace(False)
t_end = q.frame
q.say('window', t_input, '->', t_end, 'phase', phase)
json.dump(lumas, open(os.path.join(q.dir, 'lumas.json'), 'w'))
json.dump(dict(t_input=t_input, t_no=t_no, t_end=t_end, case=case), open(os.path.join(q.dir, 'meta.json'), 'w'))
q.dump()
bxlib.summarize(q.rows, os.path.join(q.dir, 'timeline.txt'))


def probe(t_from, maxk=90, hold_n=14):
    """first k such that a 2-frame UP press at frame t_from + k changes the picture (the player turns / walks)
    compared with no input -> t_from + k (the field takes input from then on)"""
    q.trace(False)
    q.load_state(PROBE_STATE)
    base = []
    for j in range(maxk + hold_n + 2):
        q.emu.cycle(with_joystick=False)
        base.append(q.emu.screenshot().tobytes())
    for k in range(0, maxk):
        q.load_state(PROBE_STATE)
        for j in range(k):
            q.emu.cycle(with_joystick=False)
        q.press('UP')
        for j in range(2):
            q.emu.cycle(with_joystick=False)
        q.release('UP')
        for j in range(hold_n - 2):
            q.emu.cycle(with_joystick=False)
        if q.emu.screenshot().tobytes() != base[k + hold_n - 1]:
            return t_from + k
    return None


if (not us or os.environ.get('PROBE')) and t_lit is not None:
    t1p = probe(t_lit)
    q.say('probe: lit at', t_lit, 'controllable at', t1p)
    json.dump(dict(t_lit=t_lit, t1=t1p), open(os.path.join(q.dir, 'probe.json'), 'w'))
q.say('done', name)
