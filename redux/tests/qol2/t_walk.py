"""t_walk.py LANG KIND STATE DIR FRAMES [b] [noshoes] [autorun_off] [turbo] : hold DIR (+B with b) for FRAMES from
state KIND_LANG_STATE (Running Shoes flag 0x963 set unless noshoes; autorun_off: set flag 0x5DC first).
MEAS tile = median frames per tile after the first one; acmd codes set for the player; follower distance
(tiles, Chebyshev) after each player step."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import sys
from qt import Q
from desmume.controls import Keys, keymask

lang, kind, state, d, n = sys.argv[1:6]
opts = sys.argv[6:]
tag = '_'.join([d] + opts)
q = Q(f'walk_{kind}_{lang}_{state}_{tag}', lang, kind)
q.load(state)
q.step(3)
q.set_flag(0x963, 'noshoes' not in opts)
if 'autorun_off' in opts:
    q.set_flag(0x5DC, 1)
q.step(20)
if 'turbo' in opts:
    q.tap('R')
    q.step(10)
acm = []


def ah(a, s):
    r = q.emu.memory.register_arm9
    acm.append((q.frame, r.r1))


q.emu.memory.register_exec(0x02166E88, ah, 2)
keys = [d] + (['B'] if 'b' in opts else [])
for k in keys:
    q.emu.input.keypad_add_key(keymask(getattr(Keys, 'KEY_' + k)))
pos, changes, fdist = q.pos(), [], []
t0 = q.frame
for i in range(int(n)):
    q.step(1)
    p = q.pos()
    if p != pos:
        changes.append(q.frame)
        pos = p
for k in keys:
    q.emu.input.keypad_rm_key(keymask(getattr(Keys, 'KEY_' + k)))
q.step(30)
f3 = q.r32(q.fdbg + 12)
fx, fz = f3 & 0xFFF, (f3 >> 16) & 0xFFF
px, pz = q.pos()
iv = [b - a for a, b in zip(changes, changes[1:])]
med = sorted(iv)[len(iv) // 2] if iv else None
codes = sorted(set(c for f, c in acm))
q.say('tiles', len(changes), 'intervals', iv, 'MEAS tile', med, 'codes', [hex(c) for c in codes])
q.say('player', (px, pz), 'follower', (fx, fz), 'dist', max(abs(px - fx), abs(pz - fz)), 'qol2_dbg autorun', q.q2dbg().get('autorun'))
q.check('moved', len(changes) >= 3, True)
q.result(dict(tile=med, tiles=len(changes)))
