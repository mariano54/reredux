"""t_texts.py : static checks of the settings-menu texts against what the modules do (no emulator).
- Turbo button hint: R toggles 2x speed (turbo.c: "press R ... to switch 2x game speed on / off"), so the hint must
  name R and must not say "hold" (regression: it read "A button that runs the whole game faster while you hold it",
  JP 押している　あいだ).
- Every hint/label: EN at most 2 lines of <= 40 characters (proportional font; the real check is the newgame screenshots); JP checked by rules/jp_chars.py (glyphs, width).
Exit 1 on a failure."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, subprocess, sys
Q = f'{RR_RX}/qol'
sys.path.insert(0, Q)
sys.path.insert(0, f'{RR_RX}/tools')
import menu
fails = []


def check(what, ok):
    print('OK  ' if ok else 'FAIL', what)
    if not ok:
        fails.append(what)


h = menu.SETTINGS['TURBO']['hint']
check('turbo hint (EN) names R, no "hold": ' + repr(h['en']), 'R' in h['en'] and 'hold' not in h['en'].lower())
check('turbo hint (JP) names Ｒ, no 押している: ' + repr(h['ja']), 'Ｒ' in h['ja'] and '押している' not in h['ja'])
for t in menu.TEXTS:                    # every message page ({BE01} breaks): <= 2 lines of <= 40 characters
    for page in t['en'].split('{BE01}'):
        lines = page.strip('\n').split('\n')
        if len(lines) > 2 or max(len(l) for l in lines) > 40:
            check(f"{t['key']} EN fits (2 lines x 40)", False)
r = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'qa2', 'texts_check.py')],
                   capture_output=True, text=True)
print(r.stdout.strip().splitlines()[-1])
check('EN/JP glyphs and widths (qa2/texts_check.py)', r.stdout.strip().endswith('0 problems'))
print('RESULT', 'PASS' if not fails else 'FAIL ' + ', '.join(fails))
sys.exit(1 if fails else 0)
