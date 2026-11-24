"""t_xmenu.py LANG [game|bedroom] : the X menu opens with the cursor shown on POKÉMON (qol/xmenu), on the release ROM.

game (the smoke battery save, build/statview_integ/dsv; also in melonDS with EMU=melon):
  X -> cursor on POKÉMON and lit -> A opens the party (one press) -> B: the menu is back on POKÉMON -> A opens it again;
  DOWN to BAG, A (bag opens) -> B: the menu is back on POKÉMON (vanilla: BAG) -> B, X -> POKÉMON, A -> party;
  SAVE, then NO -> X -> POKÉMON; touch POKÉDEX / BAG still open them (touch unchanged) and the menu comes back on
  POKÉMON; with the "has Pokémon" flag 0x961 cleared (no POKÉMON icon) the remembered item is used (vanilla);
  Y (registered item) doesn't go through the menu. Each menu picture: only POKÉMON's button lit (no stale highlight).
bedroom (DeSmuME: the new game's bedroom state of qa.ng.rel_def, no Pokémon yet): X keeps vanilla (no POKÉMON icon,
  the cursor hidden as in vanilla)."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, sys
sys.path.insert(0, f'{RR_T}/statview')
MELON = os.environ.get('EMU') == 'melon'
if MELON:
    sys.path.insert(0, f'{RR_T}/evomoves')
    import melemu
    melemu.install()
from sv import SV, B

lang = sys.argv[1]
mode = sys.argv[2] if len(sys.argv) > 2 else 'game'
POKEMON, POKEDEX, BAG, SAVE = 1, 2, 3, 5
CENTER = [(0x40, 0x2C), (0xC0, 0x2C), (0x40, 0x5C), (0xC0, 0x5C), (0x40, 0x8C), (0xC0, 0x8C)]   # slot -> touch point
LIT = ((16, 56, 80), (32, 88, 120))         # the lit button's fill (bottom screen; melonDS +-1)
PARTY = (0x0219A052, 'b2f685fa0028')        # overlay 165 (party) loaded
BAGOV = (0x0219CAA0, 'aff65efd0028')        # overlay 142 (bag) loaded

name = f'xmenu_{mode}_{lang}' + ('_melon' if MELON else '')
dsv = f'{B}/statview_integ/dsv/rel_{lang}_smoke_{lang}.dsv' if mode == 'game' else None
q = SV(name, f'{B}/out/redux3_{lang}.nds', lang, dsv)
D = q.sym_addr('xmenu_dbg')


def dbg():
    m = q.r32(D + 8)
    d = dict(calls=q.r32(D), saved=q.r8(D + 4), used=q.r8(D + 5), slot=q.r8(D + 6), way=q.r8(D + 7), menu=m)
    if 0x02000000 <= m < 0x02400000:
        d.update(col=q.r8(m + 0x1E), row=q.r8(m + 0x1F), shown=q.r32(m + 0x2C),
                 ids=[q.r32(m + 0x3C + i * 0x1C) if q.r32(m + 0x34 + i * 0x1C) == 1 else None for i in range(6)])
    return d


def loaded(ov):
    a, h = ov
    return bytes(q.m[a + i] for i in range(6)).hex() == h


def lit():
    """lit-fill pixels per button (slots 0-5) on the bottom screen"""
    im = q.emu.screenshot().convert('RGB')
    out = []
    for cx, cy in CENTER:
        n = 0
        for y in range(cy - 18, cy + 18):
            for x in range(cx - 60, cx + 60):
                r, g, b = im.getpixel((x, 192 + y))
                n += any(abs(r - L[0]) <= 6 and abs(g - L[1]) <= 6 and abs(b - L[2]) <= 6 for L in LIT)
        out.append(n)
    return out


def ready(frames=400):
    """until the menu takes input (FUN_0219FC60 state 3: slid in), then 10 frames"""
    for _ in range(frames):
        m = q.r32(D + 8)
        if 0x02000000 <= m < 0x02400000 and q.r32(m + 0xC) == 3:
            break
        q.step(1)
    q.step(10)


def open_menu(tag, slide=False):
    c = q.r32(D)
    q.hold('X', 6)
    if slide:                               # the slide-in: the cursor moves with the buttons
        for i in range(4):
            q.step(3)
            q.snap(f'{tag}_slide{i}')
    ready()
    q.check(f'{tag}: menu created', q.r32(D) == c + 1, True)
    d = menu_ok(tag)
    q.check(f'{tag}: opened by X', d['way'], 1)
    return d


def menu_ok(tag, want_slot=0):
    d = dbg()
    q.snap(tag)
    lt = lit()
    q.say(tag, d, 'lit', lt)
    q.check(f'{tag}: cursor on POKEMON (used id, slot, col/row, shown)',
            (d['used'], d['slot'], d.get('col'), d.get('row'), d.get('shown')), (POKEMON, want_slot, 0, 0, 1))
    q.check(f'{tag}: only POKEMON lit', [n > 1000 for n in lt], [i == want_slot for i in range(6)])
    return d


def wait_menu_back(tag, c0, frames=600):
    """after closing an app: until the menu was created again"""
    for _ in range(frames):
        if q.r32(D) > c0:
            break
        q.step(1)
    ready()
    q.check(f'{tag}: menu back', q.r32(D) > c0, True)
    return menu_ok(tag)


def until(ov, frames=400):
    for _ in range(frames):
        if loaded(ov):
            q.step(30)
            return True
        q.step(1)
    return False


def close_menu():
    q.tap('B')
    q.check('field free after closing', q.wait_field(600, tap='B', settle=30), True)


if mode == 'bedroom':
    q.emu.savestate.load_file(f'{B}/qa/states/rel_{lang}_def_bedroom.dst')
    q.step(30)
    q.check('bedroom: field free', q.wait_field(600, settle=20), True)
    q.say('flags 961/962', q.flag(0x961), q.flag(0x962))
    c = q.r32(D)
    q.hold('X', 6)
    ready()
    d = dbg()
    q.snap('bedroom_x')
    q.say('bedroom', d, 'lit', lit())
    q.check('bedroom: menu created', d['calls'], c + 1)
    q.check('bedroom: no POKEMON icon', POKEMON in d.get('ids', []), False)
    q.check('bedroom: vanilla (cursor hidden until a key)', (d['way'], d['slot'], d['used'], d.get('shown')),
            (1, 0xFF, 0xFF, 0))
    close_menu()
    q.result()
    q.sheet()
    sys.exit(0)

q.check('continue', q.boot_continue(), True)
q.say('flags 961/962', q.flag(0x961), q.flag(0x962))

# 1. fresh: X -> A opens the party at once
d = open_menu('x_fresh', slide=True)
q.check('layout: POKEMON is slot 0', d.get('ids', [None])[0], POKEMON)
q.tap('A')
q.check('A: party opened', until(PARTY), True)
q.snap('party')
c = q.r32(D)
q.tap('B')
wait_menu_back('after party', c)
q.tap('A')
q.check('A again: party opened', until(PARTY), True)
c = q.r32(D)
q.tap('B')
wait_menu_back('after party 2', c)

# 2. BAG by keys: the menu comes back on POKEMON, not on BAG
q.tap('DOWN')
q.step(10)
d = dbg()
q.check('DOWN: cursor on BAG', (d['col'], d['row']), (0, 1))
q.check('DOWN: only BAG lit', [n > 1000 for n in lit()], [i == 2 for i in range(6)])
q.tap('A')
q.check('A: bag opened', until(BAGOV), True)
q.snap('bag')
c = q.r32(D)
q.tap('B')
d = wait_menu_back('after bag', c)
q.check('after bag: the remembered item is BAG', (d['way'], d['saved']), (2, BAG))
close_menu()
open_menu('x_after_bag')
q.tap('A')
q.check('A: party opened (after BAG)', until(PARTY), True)
c = q.r32(D)
q.tap('B')
wait_menu_back('after party 3', c)
close_menu()

# 3. SAVE, then NO
open_menu('x_before_save')
q.tap('DOWN')
q.tap('DOWN')
q.tap('A')
q.step(120)
q.snap('save_question')
c = q.r32(D)
q.tap('B')
q.step(120)
q.snap('save_no')
if q.r32(D) > c:                            # the menu came back
    d = menu_ok('after save')
    q.check('after save: the remembered item is SAVE', d['saved'], SAVE)
    close_menu()
q.check('save: NO -> field', q.wait_field(900, tap='B', settle=30), True)
open_menu('x_after_save')
close_menu()

# 4. touch: POKEDEX, BAG open as before and the menu comes back on POKEMON
open_menu('x_touch')
c = q.r32(D)
q.touch(*CENTER[1])
q.step(200)
q.snap('dex')
for _ in range(3):                          # B until the Pokédex closes (never once the menu is back)
    q.tap('B')
    for _ in range(300):
        if q.r32(D) > c:
            break
        q.step(1)
    if q.r32(D) > c:
        break
d = wait_menu_back('after dex', c, 900)
q.check('after dex: the remembered item is POKEDEX', (d['way'], d['saved']), (2, POKEDEX))
c = q.r32(D)
q.touch(*CENTER[2])
q.check('touch BAG: bag opened', until(BAGOV), True)
q.tap('B')
wait_menu_back('after touch bag', c)
close_menu()

# 5. no POKEMON icon (flag 0x961 cleared): vanilla
q.set_flag(0x961, False)
c = q.r32(D)
q.hold('X', 6)
ready()
d = dbg()
q.snap('x_no_pokemon')
q.say('no POKEMON', d, 'lit', lit())
q.check('no POKEMON: menu created', d['calls'], c + 1)
q.check('no POKEMON: no icon', POKEMON in d.get('ids', []), False)
q.check('no POKEMON: vanilla (cursor hidden until a key)', (d['way'], d['slot'], d['used'], d.get('shown')),
        (1, 0xFF, 0xFF, 0))
close_menu()
q.set_flag(0x961, True)

# 6. Y (registered item): not the menu
c = q.r32(D)
q.tap('Y')
q.step(60)
q.snap('y')
q.check('Y: no menu', q.r32(D), c)
q.check('Y: field free after B', q.wait_field(600, tap='B', settle=30), True)
open_menu('x_last')
close_menu()
q.result()
q.sheet()
