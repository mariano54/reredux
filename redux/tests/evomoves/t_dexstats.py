"""t_dexstats.py LANG : the base stats on the Pokédex INFO page's top screen (dexstats.c).
Registered: every species but the form ones below and Oshawott (#501, only seen in the save); forms: Deoxys Attack and
Speed, Wormadam Trash, Rotom Wash, Giratina Origin, Shaymin Sky, Tornadus Therian, Kyurem White; Pikachu with its foreign
entries (6 languages). Checks: the entry opens on INFO with our box; showcase species (stats, total, abilities against
the named tree's personal.json, the form the entry shows); the seen-only one shows ??? (no values); a foreign entry hides
our box (the card back, BG2 on), changing species brings it back; the other pages (AREA, CRY, FORMS, EVO) and back to
INFO; the FORMS page's form choice; the list and back; the field (no crash). Sheet -> build/evomoves/dexstats_LANG.png"""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, sys, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from em import EM, B
from ds import ds, expect, register, register_form, open_dex, species_list, show

lang = sys.argv[1]
q = EM(f'em_dexstats_{lang}', lang)
shots = []
FORMS = [(386, 1), (386, 3), (413, 1), (479, 2), (487, 1), (492, 1), (641, 1), (646, 2)]
SKIP = sorted({sp for sp, _ in FORMS} | {501, 25})


def snap(tag, label):
    shots.append((q.snap(tag), label))


def gold(x=128, y=27):
    """our box's gold border on the top screen (the foreign card has none there)"""
    r, g, b = q.emu.screenshot().convert('RGB').getpixel((x, y))
    return r > 200 and g > 170 and b < 90


def check_species(sp, form, d, label):
    st, tot, ab = expect(sp, form)
    if d['caught']:
        got = (d['species'], d['form'], d['shown'], d['stats'], d['total'], d['abil'])
        want = (sp, form, 1, st, tot, ab)
    else:
        got = (d['species'], d['shown'], d['stats'], d['total'])
        want = (sp, 1, [0] * 6, 0)
    q.check(f'{label}: #{sp} form {form}', got, want)
    q.check(f'{label}: our box on the top screen', gold(), True)


q.boot_continue()
lo = 1
for s in SKIP:
    if s > lo:
        register(q, lo, s - 1)
    lo = s + 1
register(q, lo, 649)
for sp, f in FORMS:
    register_form(q, sp, f)
for lg in (1, 3, 4, 5, 7, 8):
    register_form(q, 25, 0, lg)
open_dex(q)
d = ds(q)
q.say('entry', d)
q.check('the entry opens on INFO with our box', (d['on'], d['shown'], d['ready'], d['fail']), (1, 1, 1, 0))
q.check('the box drawn before the fade-in', d['holds'] < 30, True)
snap('entry', f'entry #{d["species"]}')
lst, count, idxp = species_list(q)
for sp, form, label in ((1, 0, 'Bulbasaur'), (6, 0, 'Charizard'), (113, 0, 'Chansey (HP 250)'),
                        (242, 0, 'Blissey (HP 255)'), (213, 0, 'Shuckle (Def 230)'), (386, 1, 'Deoxys Attack form'),
                        (413, 1, 'Wormadam Trash'), (479, 2, 'Rotom Wash'), (487, 1, 'Giratina Origin'),
                        (492, 1, 'Shaymin Sky'), (641, 1, 'Tornadus Therian'), (646, 2, 'Kyurem White'),
                        (649, 0, 'Genesect'), (501, 0, 'seen only'), (25, 0, 'Pikachu')):
    d = show(q, lst, count, idxp, sp)
    q.step(6)
    check_species(sp, form, d, label)
    snap(f'sp{sp}', f'{label}')
# a foreign entry (Pikachu's first language button)
q.touch(10, 98); q.step(60)
d = ds(q)
q.check('foreign entry: our box hidden, the card shown', (d['foreign'], d['shown'], d['bg2_on'], gold()), (1, 0, 1, False))
snap('foreign', 'Pikachu: a foreign entry (vanilla card)')
d = show(q, lst, count, idxp, 26)
q.step(6)
q.check('next species: the foreign entry gone, our box back', (d['foreign'], d['shown'], d['species']), (0, 1, 26))
check_species(26, 0, d, 'after the foreign entry')
d = show(q, lst, count, idxp, 386)
q.step(6)
# the other pages and back: RIGHT x 5 (AREA, CRY, FORMS, EVO, INFO)
s0, e0 = d['setups'], d['exits']
for k, page in enumerate(('AREA', 'CRY', 'FORMS', 'EVO')):
    q.tap('RIGHT'); q.step(150)
    d = ds(q)
    q.check(f'{page}: our box gone', (d['on'], d['shown']), (0, 0))
    if page in ('AREA', 'FORMS'):
        snap(f'page_{page}', f'Deoxys: {page} page')
    if page == 'FORMS':                     # the FORMS page: the next form shown
        q.tap('R'); q.step(60)
        snap('forms_next', 'FORMS: R (the next form shown)')
q.tap('RIGHT'); q.step(150)
d = ds(q)
q.say('back on INFO', d)
q.check('back on INFO: our box again', (d['on'], d['shown'], d['setups'], d['exits']), (1, 1, s0 + 1, e0 + 1))
q.check('FORMS: R chose the Speed form, INFO and our stats follow', d['form'], 3)
check_species(386, 3, d, 'Deoxys after FORMS')
snap('info_again', f'Deoxys back on INFO (form {d["form"]})')
# the list and back
q.tap('B'); q.step(150)
d = ds(q)
q.check('list: our box gone', (d['on'], d['shown']), (0, 0))
q.tap('A'); q.step(200)
d = ds(q)
q.check('the entry again: our box', (d['on'], d['shown']), (1, 1))
q.tap('B'); q.step(150)
q.tap('B'); q.step(150)
q.check('field after the Pokédex', q.wait_field(3000, tap='B', settle=30), True)
q.result()
out = f'{B}/evomoves/dexstats_{lang}{"_melon" if os.environ.get("EMU") == "melon" else ""}.png'
subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'labelsheet.py'), out] +
               [a for p, l in shots for a in (p, l)])
q.say('sheet', out)
