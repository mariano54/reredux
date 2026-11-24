"""t_dex.py LANG : Pokédex foreign-language entries (QA2 ROM, from qa2_LANG_def_bedroom). Script: menu flags for the
Pokémon / Pokédex entries (2401, 2402), National Pokédex, a Patrat and a Zubat (#41: only species 1-493 have foreign
entries in Black 2's dex data, FUN_0200CEA4). q2tst command 3 (PokeParty_SetParam(PF_Region) + addPkmToDex, the
game's own registration) records the Zubat in the native language, then French and German (EN ROM) / English and
French (JP ROM). X -> Pokédex -> scroll to Zubat (Unova #061) -> INFO: the language buttons; L / R switch the top
screen entry. Shots build/qa2/dex_LANG/ (both screens), sheet build/qa2/dex_LANG_sheet.png."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qa2 import Q2

lang = sys.argv[1]
q = Q2(f'dex_{lang}', lang)
q.load('def_bedroom')
q.step(10)
q.script(['    FlagSet 2401', '    FlagSet 2402', '    PokeDexGiveNational', '    PokePartyAdd 0x8020, 504, 0, 5',
          '    PokePartyAdd 0x8020, 41, 0, 5'])
langs = (2, 3, 5) if lang == 'en' else (1, 2, 3)     # native first, the last one stays the Zubat's
for l in langs:
    q.check(f'Zubat language {l} via SetParam + addPkmToDex', q.set_lang(1, l), l)
q.tap('X')
q.step(40)
q.touch(190, 48)
q.step(300)
q.snap('list')
for _ in range(3):
    q.hold('DOWN', 200)
    q.step(90)


def zubat_shown():
    """the list's preview (top screen, left) shows the Zubat (purple) instead of "Undiscovered" """
    im = q.emu.screenshot().convert('RGB').crop((0, 200, 120, 280))
    return any(r > 90 and b > 150 and g < 110 for r, g, b in im.getdata())


for _ in range(8):
    if zubat_shown():
        break
    q.tap('DOWN')
    q.step(60)
q.check('cursor on Zubat (#061)', zubat_shown(), True)
q.snap('zubat_row')
q.tap('A')
q.step(120)
q.snap('info')
top = lambda: q.emu.screenshot().convert('RGB').crop((0, 0, 256, 192)).tobytes()
t0 = top()
q.tap('L')
q.step(120)
q.snap('L')
t1 = top()
q.tap('R')
q.step(120)
q.snap('R')
t2 = top()
q.check('L: a foreign entry on the top screen', t1 != t0, True)
q.check('R: the other language', t2 != t1, True)
for _ in range(4):
    q.tap('B')
    q.step(60)
q.check('back to the field', q.wait_free(1500, tap='B'), True)
q.result()
q.sheet(both=True)
