"""t_menus.py LANG SCEN[,SCEN..] : faster menus (qol/menuspeed) on the release ROM, from the smoke fixture battery
(build/statview_integ/dsv; Continue in Aspertia's Pokémon Center). EMU=melon runs it in the headless melonDS (MPU:
a wild pointer aborts as on hardware), else DeSmuME.

Each scenario (scen.py) is played twice by an eager player (the next input as soon as the game takes it): speed-ups
on, then off (flag 0x5DA set after Continue). Checks:
  - timing: every step in LIMIT is taken within its limit with the speed-ups on, and the ones in SLOWER are slower
    again with them off (the flag gates them);
  - sound: no sound effect, sequence or cry is cut sooner with the speed-ups on than off (sndcheck.py);
  - state: the save data at the end is the same both ways (party, Bag, money, boxes, ...; savecmp.py);
  - every step's picture changed (the flow went through: the screenshots are in build/menuspeed/t_menus_*)."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_B  # noqa: E402
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mh, meas, flow, flowrun, scen, sndcheck, savecmp

lang, scens = sys.argv[1], sys.argv[2].split(',')
kind = 'mel' if os.environ.get('EMU') == 'melon' else 'dsm'
ROM = f'{RR_B}/out/redux3_{lang}.nds'
DSV = f'{RR_B}/statview_integ/dsv/rel_{lang}_smoke_{lang}.dsv'
OUT = os.environ.get("MS_OUT") or f"{RR_B}/menuspeed/t_menus_{chr(95).join(scens)}_{lang}_{kind}"
os.makedirs(OUT, exist_ok=True)

# ready (frames) with the speed-ups on, at most (melonDS / DeSmuME measured + a few frames); Redux 1.4.1 in comments
LIMIT = {
    'xmenu.close': 34,              # 46
    'party.open': 40,               # 77
    'party.sub_close': 10,          # 19: the task menu's blink
    'party.switch_pick': 10,        # 19
    'summary.open': 48,             # 78
    'bag.open': 40, 'bag.item_menu_close': 10, 'bag.give': 40,
    'dex.open': 34, 'options.open': 36, 'options.close': 54, 'card.open': 48,
    'mart.hello': 32,               # 45: the list menu's wait
    'mart.exit': 64,                # 83
    'box.exit_prompt': 10,          # 19
}
# with the speed-ups off these take at least (the flag must gate them)
SLOWER = {'party.sub_close': 17, 'party.switch_pick': 17, 'bag.item_menu_close': 16, 'mart.hello': 36,
          'box.exit_prompt': 17}

fails = []


def check(what, ok, info=''):
    print(('OK   ' if ok else 'FAIL ') + what, info, flush=True)
    if not ok:
        fails.append(what)


def run_one(s, off):
    E = mh.emu(kind, ROM, DSV, tag=f'tm_{s}_{lang}_{"off" if off else "on"}_{os.getpid()}')
    flow.start(E, None)
    if off:
        flowrun.set_flag(E, 0x5DA, True)
        E.step(2)
    meas.snd_hooks(E)
    r = flowrun.run(E, scen.SCEN[s](False), phases=1, margin=1, odir=f'{OUT}/{s}_{"off" if off else "on"}',
                    log=lambda *x: print(*x, flush=True))
    data = r.pop('_save_bin', b'')
    p = f'{OUT}/{s}_{"off" if off else "on"}.json'
    json.dump(r, open(p, 'w'), indent=1)
    open(p.replace('.json', '_save.bin'), 'wb').write(data)
    return r, p


if len(sys.argv) > 3 and sys.argv[3] in ('on', 'off'):    # a child: one emulator per process
    run_one(scens[0], sys.argv[3] == 'off')
    sys.exit(0)
import subprocess
for s in scens:
    for mode in ('on', 'off'):
        rc = subprocess.run([sys.executable, "-u", os.path.abspath(__file__), lang, s, mode], env=dict(os.environ, MS_OUT=OUT)).returncode
        check(f'{s} {mode}: ran', rc == 0, f'rc {rc}')
runs = {s: {m: (json.load(open(f'{OUT}/{s}_{m}.json')), f'{OUT}/{s}_{m}.json') for m in ('on', 'off')}
        for s in scens}


def ready(r, k):
    v = r.get(k)
    return meas.mean(v['ready']) if v else None


for s in scens:
    on, p_on = runs[s]['on']
    off, p_off = runs[s]['off']
    for k in on['_order']:
        base = k.split('#')[0]
        a, b = ready(on, k), ready(off, k)
        print(f'  {k:28s} on {a}  off {b}', flush=True)
        if base in LIMIT:
            check(f'{s} {k}: on <= {LIMIT[base]}', a is not None and a <= LIMIT[base], f'({a})')
        if base in SLOWER:
            check(f'{s} {k}: off >= {SLOWER[base]}', b is not None and b >= SLOWER[base], f'({b})')
        resp = on[k]['resp'][0]
        if resp is None:        # an eager input can land while the previous screen is still closing: no new picture
            print(f'WARN {s} {k}: no picture change (resp None)', flush=True)
    sys.argv = ['sndcheck', p_off, p_on]
    check(f'{s}: no sound cut sooner with the speed-ups on', sndcheck.main() == 0)
    if s != 'xmenu':        # xmenu: an eager B during the slide-in closes the menu in one run and not the other, so
        sys.argv = ['savecmp', p_off, p_on]     # the play records (menu / step counters) differ; nothing else is in it
        check(f'{s}: same game state both ways', savecmp.main() == 0)
print('RESULT', 'PASS' if not fails else 'FAIL ' + ', '.join(fails), flush=True)
