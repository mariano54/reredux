"""texts_check.py : the rules / menu texts: every Japanese character has a glyph (occurs in the Japanese
Black 2's own text), Japanese lines <= 18 characters, English lines <= 37 (list labels <= 30), every
English character occurs in the US Black 2's text. Prints the problems and a count."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import sys
sys.path.insert(0, f'{RR_RX}/tools')
sys.path.insert(0, f'{RR_RX}/qol')
import ndsfs, gen5text
import rules, menu
B = f'{RR_B}'


def seen_chars(path):
    rom = ndsfs.Rom(path)
    seen = set()
    for p in ('a/0/0/2', 'a/0/0/3'):
        fid = next(f for f, q in rom.paths.items() if q == p)
        for b in ndsfs.narc(rom.file(fid)):
            try:
                secs = gen5text.decode(b)
            except Exception:
                continue
            for sec in secs:
                for t, _ in sec:
                    seen.update(gen5text.text_to_chars(t))
    return seen


seen = {'en': seen_chars(B + '/vanilla_rom/black2.nds'), 'ja': seen_chars(B + '/jp_rom/jp_orig.nds')}
bad = 0
for t in rules.TEXTS + menu.TEXTS:
    k = t['key']
    label = any(k.startswith(p) for p in ('MENU_ROW_', 'MENU_VAL_', 'MENU_PRESET', 'MENU_DONE', 'MENU_BACK')) \
        and not k.startswith('MENU_PRESET_ASK')
    for lang, lim in (('en', 30 if label else 37), ('ja', 18)):
        s = t[lang]
        plain = s
        while '{' in plain:
            a = plain.index('{')
            plain = plain[:a] + plain[plain.index('}', a) + 1:]
        lines = plain.split('\n')
        chars = [c for c in gen5text.text_to_chars(s.replace('\n', '\\n')) if c < 0xF000 or c >= 0xFF00]
        miss = sorted({chr(c) for c in chars if c not in seen[lang] and c not in (0xFFFE, 0xFFFF, 0x20, 0x3000)})
        w = max(len(l) for l in lines)
        if miss or w > lim:
            bad += 1
            print(lang, k, repr(s), 'MISSING' if miss else '', miss, 'width', w, '>', lim if w > lim else '')
print('checked', len(rules.TEXTS + menu.TEXTS), 'texts;', bad, 'problems')
