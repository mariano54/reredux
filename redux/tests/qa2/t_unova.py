"""t_unova.py LANG [STEP..] : Unova Link's Key System on the release ROM with t_smoke.py's battery save
(rel_LANG_smoke_LANG.dsv: Challenge Mode, Black City, no keys). Title -> main menu -> UNOVA LINK -> Key System ->
Key System Settings -> Set Difficulty: Easy (key message), Normal (nothing), back; Change City: White Forest (key
message), back. SetGameDifficulty / KeyInfo_SetCity must never run (exec hooks) and the KeyInfo read by Unova
Link must stay Challenge / Black City. STEP args: replay keys / "x,y" touches instead (exploration).
Shots build/qa2/unova_LANG/, sheet build/qa2/unova_LANG_sheet.png."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qa2
from qa import QA

lang = sys.argv[1]
steps = sys.argv[2:]
q = QA(f'unova_{lang}', lang, 'rel', run=f'smoke_{lang}', keep_save=True)
for f in os.listdir(q.dir):
    if f.endswith('.png'):
        os.remove(os.path.join(q.dir, f))
q.check('battery save present', os.path.exists(QA.dsv('rel', lang, f'smoke_{lang}')), True)
calls = {'set_diff': 0, 'set_city': 0}
kis = []
r = q.emu.memory.register_arm9
q.emu.memory.register_exec(0x02010514, lambda a, s: (calls.__setitem__('set_diff', calls['set_diff'] + 1), calls.setdefault('where', []).append((q.frame, hex(r.lr), hex(r.r1)))), 2)
q.emu.memory.register_exec(0x02010550, lambda a, s: calls.__setitem__('set_city', calls['set_city'] + 1), 2)
q.emu.memory.register_exec(0x02010528, lambda a, s: kis.append(r.r0), 2)     # GetGameDifficulty(ki)
for i in range(3000):                   # title: A until the main menu's Key System panel reads the KeyInfo
    q.step(1)
    if kis:
        break
    if q.frame >= 200 and q.frame % 30 == 0:
        q.hold('A', 4)
q.check('main menu (Key System panel read the KeyInfo)', bool(kis), True)
q.step(90)
q.say('boot-time calls (save block init: rules_keyinfo_init -> Challenge)', calls)
calls.update(set_diff=0, set_city=0, where=[])
W = int(os.environ.get('UWAIT', '300'))


def go(k, tag=None):
    if ',' in k:
        x, y = map(int, k.split(','))
        q.touch(x, y)
    else:
        q.tap(k)
    q.step(W)
    q.snap(tag or k.replace(',', '_'))


if steps:
    for s in steps:
        go(s)
else:
    for k in ('DOWN', 'DOWN', 'DOWN'):
        go(k)
    go('A', 'unova_link')
    go('A', 'key_system')
    go('DOWN')
    go('A', 'key_settings')
    n_ki = len(kis)
    go('A', 'difficulty_list')          # cursor on Easy Mode
    q.check('in the Set Difficulty list (Unova Link read the difficulty)', len(kis) > n_ki, True)
    go('A', 'easy_refused')             # "You cannot select this item until it's been unlocked with the Easy Key."
    go('A', 'easy_msg_closed')
    go('DOWN', 'normal_hl')
    go('A', 'normal_nothing')
    go('B', 'difficulty_back')
    go('DOWN', 'city_row')
    go('A', 'city_list')
    go('DOWN', 'white_forest_hl')
    go('A', 'white_forest_refused')
    go('A', 'city_msg_closed')
    go('B', 'city_back')
    go('B', 'settings_back')
    ki = kis[-1] if kis else 0
    key = q.r32(ki + 0x34)
    diff = {0x31239: 0, 0x15657: 1, 0x49589: 2}.get(q.r32(ki + 0x28) ^ key, 1)
    city_t = [q.r32(0x0208F9F8 + 4 * i) for i in range(2)]
    city = city_t.index(q.r32(ki + 0x2C) ^ key) if (q.r32(ki + 0x2C) ^ key) in city_t else 0
    q.say('calls', calls, 'ki', hex(ki), 'difficulty', diff, 'city', city)
    q.check('no SetGameDifficulty / SetCity calls', (calls['set_diff'], calls['set_city']), (0, 0))
    q.check('KeyInfo still Challenge / Black City', (diff, city), (2, 0))
q.result()
q.sheet(both=True)
