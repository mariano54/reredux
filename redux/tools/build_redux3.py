#!/usr/bin/env python3
"""ReRedux: both final ROMs (English and Japanese) from the three input ROMs, in one command.

  build_redux3.py [--lang en|jp|both] [--test] [--with MOD,..] [--only MOD,..]

Run from anywhere with a Python that has Pillow (sprite conversion, icon). Inputs (redux/build/):
  vanilla_rom/black2.nds   US Black 2            jp_rom/jp_orig.nds   Japanese Black 2
  vanilla_rom/redux.nds    Blaze Black 2 Redux
Japanese translations (optional, not vendored): set $REDUX_JP_WORK to a directory with tr/*.json.
  boxart/us.png, jp.png    optional user-supplied box art for custom icons
External assets (paths in redux/build/redux3.json, keys "essentials" and "hgss", or the
REDUX_ESSENTIALS / REDUX_HGSS environment variables, or --essentials / --hgss): the Pokémon
Essentials follower sheets and pokeheartgold's files/data/mmodel/mmodel.

Steps (intermediate ROMs in build/redux3/):
  EN: Redux -> followers (build_followers.build) -> qol modules (qol_build.build) -> optional icon
  JP: Redux -> jp_port (Japanese text/graphics) -> followers (Japanese talk lines from
      $REDUX_JP_WORK/tr/f_00.json, English species names for the Essentials sheets) -> qol -> optional icon
Outputs: build/out/redux3_en.nds, redux3_jp.nds.

--test builds on the follower test base instead of Redux: build/out/followtest_base.nds, rebuilt
first from the named tree build/named/followtest (build_rom.py; --no-base-rebuild to skip), with
the example module and -DQOL_TEST, no icon -> build/out/redux3_test_en.nds / redux3_test_jp.nds.
--with adds disabled modules (e.g. example); --only builds core + the listed modules.
Each language's qol layout/symbols/patches: build/qol/LANG[_test]/qol_map.json.

Modules: redux/qol/NAME.py (+ NAME.c); see tools/qol_build.py and the README's ReRedux section.
"""
import argparse, hashlib, json, os, shutil, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_followers, jp_port, qol_build

B = os.path.normpath(os.path.join(HERE, '..', 'build'))
US, JP, REDUX = (os.path.join(B, p) for p in ('vanilla_rom/black2.nds', 'jp_rom/jp_orig.nds', 'vanilla_rom/redux.nds'))
JP_WORK = os.environ.get('REDUX_JP_WORK') or os.path.normpath(os.path.join(HERE, '..', 'translations', 'jp'))
TEST_TREE = os.path.join(B, 'named', 'followtest')
TEST_BASE = os.path.join(B, 'out', 'followtest_base.nds')
TMP = os.path.join(B, 'redux3')
ICONS = {'en': ('boxart/us.png', (180, 0, 512, 332)), 'jp': ('boxart/jp.png', (120, 60, 512, 452))}
TITLES = {'en': 'Pokémon\nBlaze Black 2 ReRedux\nFan modification',      # banner title, every language slot
          'jp': 'ポケットモンスター\nブレイズブラック２ リリダックス\nファンメイド改造版'}


def config(a):
    cfg = {}
    p = os.path.join(B, 'redux3.json')
    if os.path.exists(p):
        cfg = json.load(open(p))
    ess = a.essentials or os.environ.get('REDUX_ESSENTIALS') or cfg.get('essentials')
    hgss = a.hgss or os.environ.get('REDUX_HGSS') or cfg.get('hgss')
    for name, v in (('essentials', ess), ('hgss', hgss)):
        if not v or not os.path.isdir(v):
            sys.exit(f'{name}: set --{name}, REDUX_{name.upper()} or "{name}" in {p} (got {v!r})')
    return ess, hgss


def step(msg):
    print(f'\n== {msg}', flush=True)
    return time.time()


def build_lang(lang, base, a, ess, hgss):
    sfx = '_test' if a.test else ''
    t0 = step(f'{lang.upper()}: base {os.path.relpath(base, B)}')
    if lang == 'jp':
        src = os.path.join(TMP, f'jp{sfx}_base.nds')
        jp_port.cmd_build(US, JP, base, JP_WORK, src)
    else:
        src = base
    step(f'{lang.upper()}: followers')
    fol = os.path.join(TMP, f'{lang}{sfx}_followers.nds')
    kw = dict(names_rom=US, talk_lines=os.path.join(JP_WORK, 'tr', 'f_00.json')) if lang == 'jp' else {}
    info = build_followers.build(src, fol, essentials=ess, hgss=hgss, **kw)
    elf = os.path.join(TMP, f'{lang}{sfx}_follow.elf')        # build/followers is shared by both languages
    shutil.copy(info['elf'], elf)
    step(f'{lang.upper()}: qol modules')
    out = os.path.join(B, 'out', f'redux3{sfx}_{lang}.nds')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with_ = list(a.with_) + (['example'] if a.test else [])
    qol_build.build(fol, out, lang, with_, a.only, a.test, follower_elf=elf)
    if not a.test and not a.no_icon:
        from PIL import Image
        import set_icon
        img, crop = ICONS[lang]
        set_icon.set_icon(out, Image.open(os.path.join(B, img)).crop(crop),
                          os.path.join(B, 'boxart', f'icon_{"us" if lang == "en" else "jp"}.png'), TITLES[lang])
        print('icon and title replaced')
    sha = hashlib.sha1(open(out, 'rb').read()).hexdigest()
    print(f'{lang.upper()}: wrote {out} ({os.path.getsize(out)} bytes, sha1 {sha}) in {time.time() - t0:.0f} s')
    return out


def main():
    ap = argparse.ArgumentParser(description='ReRedux ROMs (see the module docstring)')
    ap.add_argument('--lang', default='en', choices=('en', 'jp', 'both'))
    ap.add_argument('--test', action='store_true', help='build on the followtest base (+ example module, -DQOL_TEST)')
    ap.add_argument('--no-base-rebuild', action='store_true', help='--test: use followtest_base.nds as it is')
    ap.add_argument('--with', dest='with_', default='', help='also build these disabled qol modules (comma list)')
    ap.add_argument('--only', help='build only core and these qol modules (comma list; empty = core only)')
    ap.add_argument('--essentials', help='Essentials follower sheets (DIR/normal, DIR/shiny)')
    ap.add_argument('--hgss', help='pokeheartgold files/data/mmodel/mmodel')
    ap.add_argument('--no-icon', action='store_true')
    a = ap.parse_args()
    a.with_ = [n for n in a.with_.split(',') if n]
    a.only = [n for n in a.only.split(',') if n] if a.only is not None else None
    ess, hgss = config(a)
    for p in (US, REDUX) + ((JP,) if a.lang != 'en' else ()):
        if not os.path.exists(p):
            sys.exit(f'missing input ROM {p}')
    if a.lang != 'en' and not os.path.isdir(os.path.join(JP_WORK, 'tr')):
        sys.exit(f'missing Japanese translation directory {os.path.join(JP_WORK, "tr")} (set REDUX_JP_WORK)')
    os.makedirs(TMP, exist_ok=True)
    base = REDUX
    if a.test:
        base = TEST_BASE
        if not a.no_base_rebuild:
            step('test base: build_rom.py --src named/followtest')
            subprocess.run([sys.executable, 'build_rom.py', '--src', TEST_TREE, '--out', TEST_BASE], cwd=HERE, check=True)
    outs = []
    try:
        for lang in (('en', 'jp') if a.lang == 'both' else (a.lang,)):
            outs.append(build_lang(lang, base, a, ess, hgss))
    except qol_build.QolError as e:
        sys.exit(f'qol: {e}')
    print('\n' + '\n'.join(outs))


if __name__ == '__main__':
    main()
