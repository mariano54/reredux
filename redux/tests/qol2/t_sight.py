"""t_sight.py LANG KIND MODE : trainer sight on Route 20 (state KIND_LANG_MODE_r20: player at (158, 650), trainer 3392
at (152, 651) facing right, sight 6): step DOWN into its line -> "!" -> it walks up -> battle.
MEAS sight = step done (player on (158, 651)) -> battle call (OVL_12 EventBattleCall first run); tiles walked
by the trainer from the "!" are logged (acmd log of FldAct_SetAcmd)."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, sys
from qt import QR

lang, kind, mode = sys.argv[1:4]
q = QR(f'sight_{kind}_{lang}_{mode}', lang, kind)
q.load(f'{mode}_r20')
q.hook(0x02168BAC, 'battlecall')
acm = []


def ah(a, s):
    r = q.emu.memory.register_arm9
    acm.append((q.frame, r.r1, r.lr))


q.emu.memory.register_exec(0x02166E88, ah, 2)
q.rec = q.dir + '/rec'
os.makedirs(q.rec, exist_ok=True)
q.step(5)
q.emu.input.keypad_add_key(__import__('desmume.controls', fromlist=['keymask']).keymask(
    __import__('desmume.controls', fromlist=['Keys']).Keys.KEY_DOWN))
t_arrive = None
for i in range(60):
    q.step(1)
    if q.pos() == (158, 651):
        break
q.emu.input.keypad_rm_key(__import__('desmume.controls', fromlist=['keymask']).keymask(
    __import__('desmume.controls', fromlist=['Keys']).Keys.KEY_DOWN))
q.check('stepped into the line', q.pos(), (158, 651))
t_arrive = q.frame
for i in range(900):
    walked = [f for f, c, l in acm if f >= t_arrive and c == 2]
    if walked and (q.frame - walked[0]) % 20 == 0:
        q.hold('A', 4)
    else:
        q.step(1)
    if q.first('battlecall'):
        break
w = [f for f, c, l in acm if f >= t_arrive]
q.say('MEAS bang2walk', (w[1] - t_arrive) if len(w) > 1 else None, 'MEAS walk_end', (w[-1] - t_arrive) if w else None)
tb = q.first('battlecall')
q.rec = None
q.say('acmds', [(f, hex(c)) for f, c, l in acm if f >= t_arrive][:40])
q.say('MEAS sight', (tb - t_arrive) if tb else None)
q.check('battle started', tb is not None, True)
bc_state = []


def bc(a, s):
    st = q.r32(q.emu.memory.register_arm9.r1)
    if not bc_state or bc_state[-1][1] != st:
        bc_state.append((q.frame, st))


q.emu.memory.register_exec(0x02168BAC, bc, 2)
q.check('battle menu', q.until({'menu'}, 3000, tap='B'), 'menu')
s1 = next((f for f, s in bc_state if s == 1), None)
s2 = next((f for f, s in bc_state if s == 2), None)
q.say('battle call states', bc_state[:12], 'MEAS tr_enc', (s2 - s1) if s1 and s2 else None, 'qol2_dbg', q.q2dbg())
q.result(dict(sight=(tb - t_arrive) if tb else None))
