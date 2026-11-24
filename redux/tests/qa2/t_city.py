"""t_city.py LANG STATE : the City setting in the world. From STATE (qa2 bedroom: def = Black City, custom = White
Forest): script warp into the Route 15 gate (zone 379) next to its east exit (warp 1 -> Black City, zone 0), walk
east through it; log the zone that loads and its place name, shots. Black City (0) for city 0; for city 1 B2's
map-change code loads White Forest instead (KeyInfo +0x2C, ov35 FUN_0217ED20)."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qa2 import Q2, V_CITY

lang, state = sys.argv[1], sys.argv[2]
q = Q2(f'city_{lang}_{state}', lang)
q.load(state)
q.step(10)
city = q.var(V_CITY)
q.say('city var', city, 'KeyInfo', q.keyinfo())
q.script(['    MapChangeWarp 379, 14, 5, 0'])
q.step(60)
q.say('gate zone', q.zone(), 'pos', q.pos())
q.check('in the Route 15 gate', q.zone(), 379)
q.snap('gate')
p = q.path(15, 5)
q.say('path to the exit', p)
q.nav(14, 5)
for _ in range(3):
    q.hold('RIGHT', 20)
    q.wait_free(3000, tap='B')
q.step(60)
z = q.zone()
q.say('zone after the exit', z, 'pos', q.pos())
q.snap('after_exit')
q.hold('LEFT', 8)
q.step(60)
q.snap('after_exit2')
from PIL import ImageStat
im = q.emu.screenshot().convert('RGB').crop((0, 0, 256, 192))
r_, g_, b_ = ImageStat.Stat(im).mean
look = 'forest' if g_ - r_ > 15 else 'city'          # White Forest is green, Black City grey
q.say('top screen mean RGB', round(r_), round(g_), round(b_), '->', look)
q.check('zone 0 loads (Black City / White Forest share it; the map variant differs)', z, 0)
q.check('the map shown', look, 'forest' if city else 'city')
q.result({'zone': z, 'city': city})
q.sheet(both=False)
