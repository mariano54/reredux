"""mksave.py LANG [r19|r20] : portable battery saves for the battle-exit timings (Continue works on every B2-format ROM).
From the QA test ROM's Nuzlocke bedroom (test_LANG_nuz_bedroom), rules flags cleared (no Nuzlocke), bed KIT (2 Dragonite
Lv60, Master/Poke Balls, Potions), then
  r20 : bed warp to Route 20 (158, 650), one step above trainer 3392's sight line -> in-game save
  r19 : bed ROUTE (Route 19 grass) -> in-game save
-> build/battleexit/saves/{r19,r20}_LANG.dsv"""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, shutil, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'qa'))
import qa
from qa import QAR

lang = sys.argv[1]
WHERE = sys.argv[2:] or ['r20', 'r19']
SAVES = qa.B + '/battleexit/saves'
os.makedirs(SAVES, exist_ok=True)


def ingame_save(q):
    q.tap('X')
    q.step(40)
    q.touch(190, 92)
    q.step(60)
    q.snap('save_question')
    q.tap('A')
    for i in range(150):
        q.step(20)
        if q.field_ready():
            break
        if i % 10 == 9:
            q.tap('A')
    q.snap('saved')
    return q.wait_field(2000, tap='A', settle=40)


for where in WHERE:
    run = f'mksave_{where}'
    q = QAR(f'bx_mksave_{lang}_{where}', lang, 'test', run=run)
    q.load('nuz_bedroom')
    q.step(10)
    for f in range(0x5D0, 0x5DA):
        q.set_flag(f, False)
    q.step(10)
    q.bed('KIT')
    q.check('kit: field free', q.wait_free(1500, tap='B'), True)
    if where == 'r20':
        q.check('warp script', q.bed_warp(446, 158, 650, 0), True)
    else:
        q.bed('ROUTE')
    q.check('warped: field free', q.wait_free(1500, tap='B'), True)
    if where == 'r19':
        q.step(30)
        q.check('in the grass', q.nav(60, 695), True)
    q.step(60)
    q.say('zone', q.zone(), 'pos', q.pos())
    q.snap('there')
    q.check('saved', ingame_save(q), True)
    q.say('zone', q.zone(), 'pos', q.pos())
    q.step(120)
    q.emu.destroy()
    src = qa.QA.dsv('test', lang, run)
    dst = f'{SAVES}/{where}_{lang}.dsv'
    shutil.copy(src, dst)
    q.say('battery save', src, '->', dst, os.path.getsize(dst))
    q.result()
