"""t_integ.py ROM QMAP LANG NAME MODE [quick] [speedoff] [stale] [nosession2]
Save integrity: Continue from the source battery, change things (MODE), menu save, then
  1. right after the save: the battery (exported) must hold the RAM save buffer exactly, block by block, in BOTH
     copies, with valid CRCs (block footers + CRC table) and the commit byte;
  2. cold boot the battery -> Continue: zone / position / the changed bag item / flag / moved boxes as saved, and
     every save block in RAM equal to the one saved (blocks the game rewrites on Continue are listed);
  3. (session 2) change again, save again, check the battery again.
MODE: none | tiny (walk 2 steps) | pc1 (walk + 1 Pokemon into a box) | big (walk + 75 Pokemon into 3 boxes, Poke
Ball count -1, flag 0x5EF). stale: save, take a savestate, change + save again, load the savestate (the battery stays newer in
DeSmuME), save -> fastsave must notice (fs_dbg.stale) and the battery must still equal RAM."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import sys, os, json, struct, subprocess, tempfile
from fs import F, phases, B, FS
import sav

stage = sys.argv[1]                     # save | boot (DeSmuME can't be opened twice in one process)
rom, qmap, lang, name, mode = sys.argv[2:7]
opts = sys.argv[7:]
SRC = {'en': os.environ.get('SRC_DSV_EN') or os.path.expanduser(f'{RR_DSV}/q2t_en_save_def.dsv'),
       'jp': os.environ.get('SRC_DSV_JP') or os.path.expanduser(f'{RR_DSV}/q2t_jp_save_def.dsv')}
BLK = sav.load_blocks()
ELF = os.environ.get('FS_ELF') or f'{B}/redux3/{lang}_follow.elf'
FDBG = int(subprocess.run(['arm-none-eabi-nm', ELF], capture_output=True, text=True).stdout.split('follow_dbg')[0]
           .strip().split('\n')[-1].split()[0], 16)
DBG = 'skipped changed compared verified promoted dropped guard resets saves steps updates max_ticks seeded stale pg_written pg_skipped segs'.split()
tag = f'fs_{name}'
results = {}
LAST = {}
FOOTLEN_OFF = 108                       # FsDbg.foot_len (checked: 0xA4 after a save)


def sdinfo(f):
    sc = f.r32(0x02140F60)
    sd = f.r32(sc + 0x10)
    return sd, f.r32(sd + 0x34), f.r32(sd + 0x30)


def pos(f):
    v = f.r32(FDBG + 8)
    return v & 0xFFFF, v >> 16


def dbg(f):
    a = f.sym.get('fs_dbg')
    if a is None:
        return {}
    a &= ~1
    return {k: f.r32(a + 12 + 4 * i) for i, k in enumerate(DBG)}


def change(f, how, k):
    sd, buf, size = sdinfo(f)
    did = {}
    if how in ('tiny', 'big', 'pc1'):
        p0 = pos(f)
        f.hold('DOWN' if k % 2 == 0 else 'UP', 10)
        f.step(20)
        f.hold('RIGHT' if k % 2 == 0 else 'LEFT', 10)
        f.step(30)
        did['walk'] = (p0, pos(f))
    if how in ('big', 'pc1'):
        # deposit copies of the lead Pokemon (party block 26: data from +8, 220 bytes; box slot = first 136)
        party = bytes(f.m[buf + BLK[26][0] + 8: buf + BLK[26][0] + 8 + 136])
        if how == 'big':
            slots = [(1 + k, s) for s in range(30)] + [(2 + k, s) for s in range(30)] + [(3 + k, s) for s in range(15)]
        else:
            slots = [(4 + k, 7)]
        for bi, sl in slots:
            a = buf + BLK[bi][0] + 136 * sl
            for j in range(0, 136, 4):
                f.emu.memory.write_long(a + j, struct.unpack_from('<I', party, j)[0])
        did['deposited'] = len(slots)
    if how == 'big':
        bag = buf + BLK[25][0]
        q = f.r16(bag + 6)
        f.w16(bag + 6, q - 1)
        did['pokeball'] = (q, q - 1)
        f.set_flag(0x5EF, k % 2 == 0)
        did['flag5EF'] = int(k % 2 == 0)
    f.step(10)
    return did


def save_and_check(f, k, quick):
    sd, buf, size = sdinfo(f)
    snap = {}

    def eng(a, s_):
        # inside the engine's step: the save buffer at rest (no Pokemon decrypted in place, as can be
        # seen at a frame boundary); pass 2's commit poll = what both copies now hold
        r0 = f.r.r0
        if r0 == sd and f.r8(sd + 0x18) == 10 and f.r8(sd + 0x19) == 1:
            snap['ram'] = bytes(f.m[buf: buf + size])
            snap['frame'] = f.frame
    f.hook(0x0203B9BC, eng)

    def tr(h):
        if 'tab' not in snap and h.r8(sd + 0x18) == 11 and h.save_state is not None and h.save_state >= 10:
            if h.sym.get('fs_dbg'):
                fa = h.sym['fs_dbg'] & ~1
                fz = min(v for v in h.sym.values() if v > h.sym['fs_dbg']) - fa
                snap['tab'] = bytes(h.m[fa: fa + fz])
    res = f.menu_save(trace=tr)
    f.emu.memory.register_exec(0x0203B9BC, None)
    ph, tot = phases(res)
    f.say(f'[{k}] PHASES', ' '.join(f'{n}={v}' for n, v in ph), 'TOTAL', tot)
    f.say(f'[{k}] fs_dbg', dbg(f))
    f.step(20)
    exp = os.path.join(f.dir, f'battery_{k}.sav')
    if os.path.exists(exp):
        os.remove(exp)
    f.emu.backup.export_file(exp)
    if 'ram' not in snap:
        snap['ram'] = bytes(f.m[buf: buf + size])
        f.say('note: RAM snapshot after the save (state 11 not seen)')
    open(os.path.join(f.dir, f'ram_{k}.bin'), 'wb').write(snap['ram'])
    c = sav.check(exp, snap['ram'])
    f.say(f'[{k}] battery', json.dumps(c))
    f.check(f'[{k}] save completed (EventSave reached the saved box)', 16 in res['first'], True)
    for cp in 'AB':
        f.check(f'[{k}] copy {cp}: every block == RAM', c[cp]['diff'], [])
        f.check(f'[{k}] copy {cp}: CRCs valid', c[cp]['bad'], [])
        f.check(f'[{k}] copy {cp}: CRC table/header/commit == RAM', c[cp]['foot_eq_ram'], True)
    f.check(f'[{k}] both copies same counter', c['A']['counter'] == c['B']['counter'], True)
    results[f'save{k}'] = dict(phases=ph, total=tot, dbg=dbg(f), counter=c['A']['counter'])
    LAST.update(snap)
    return snap['ram']


STATE = os.path.join(FS, 'out', name, 'integ_state.json')
if stage == 'save':
  # --- session 1 -------------------------------------------------------------------------------------------
  f = F(rom, tag, name, dsv=SRC[lang], qmap=qmap)
  f.boot_continue()
  if 'quick' in opts:
      f.set_flag(0x5DD, True)
  if 'speedoff' in opts:
      f.set_flag(0x5DA, True)
  f.step(30)
  did = change(f, mode, 0)
  f.say('changes', did)
  expect = dict(zone=f.zone(), pos=pos(f), flag5EF=f.flag(0x5EF))
  ram = save_and_check(f, 0, 'quick' in opts)
  if 'stale' in opts or 'stalenocheck' in opts:
      # an emulator savestate loaded without its battery: fastsave's table goes back to the end of save 0
      # while flash holds save 1. Save 1 deposits 75 Pokemon into boxes 1-3; then they leave again (the box
      # blocks get their save-0 contents back, which the stale table knows) and save 2 must still write
      # them (fastsave notices the battery changed: fs_dbg.stale). stalenocheck: the same with the check
      # defeated (foot_len = 0) -> the boxes stay full in flash: the test catches it.
      fsa = f.sym['fs_dbg'] & ~1
      sd, buf, size = sdinfo(f)
      tab0, buf0 = LAST['tab'], LAST['ram']           # both as at the end of save 0 (RAM == flash then)
      did2 = change(f, 'big', 0)
      save_and_check(f, 1, 'quick' in opts)
      f.step(10)
      for bi in (1, 2, 3):
          o = BLK[bi][0]
          for j in range(0, 0xFF0, 4):
              f.emu.memory.write_long(buf + o + j, struct.unpack_from('<I', buf0, o + j)[0])
      for j in range(0, len(tab0) & ~3, 4):
          f.emu.memory.write_long(fsa + j, struct.unpack_from('<I', tab0, j)[0])
      f.check('FsDbg.foot_len offset', f.r32(fsa + FOOTLEN_OFF), 0xA4)
      if 'stalenocheck' in opts:
          f.say('foot check defeated: foot_len', hex(fsa + FOOTLEN_OFF))
          f.w32(fsa + FOOTLEN_OFF, 0)
      f.say('boxes 1-3 back to their save-0 contents, fs_dbg back to the end of save 0 (flash: save 1)')
      ram = save_and_check(f, 2, 'quick' in opts)
      f.check('stale battery noticed (fs_dbg.stale)', dbg(f).get('stale', 0) >= 1, True)
      expect = dict(zone=f.zone(), pos=pos(f), flag5EF=f.flag(0x5EF))
  f.step(30)
  f.close()
  open(os.path.join(f.dir, 'ram_final.bin'), 'wb').write(ram)
  json.dump(dict(expect=expect, results=results, fails=f.fails), open(STATE, 'w'))
  print('RESULT', 'PASS' if not f.fails else 'FAIL', '(save stage)')
  sys.exit(0)


# --- cold boot ---------------------------------------------------------------------------------------------
st = json.load(open(STATE))
expect, results = st['expect'], st['results']
expect['pos'] = tuple(expect['pos'])
ram = open(os.path.join(FS, 'out', name, 'ram_final.bin'), 'rb').read()
g = F(rom, tag, name + '_boot', keep=True, qmap=qmap)
ok = g.boot_continue()
g.check('Continue reaches the field', ok is not None, True)
g.step(10)
sd, buf, size = sdinfo(g)
cur = bytes(g.m[buf: buf + size])
same = [i for i, (o, s) in enumerate(BLK) if cur[o:o + s] == ram[o:o + s]]
diff = [i for i in range(len(BLK)) if i not in same]
g.say('blocks equal after Continue:', len(same), 'of', len(BLK), 'differing:', diff)
g.check('zone', g.zone(), expect['zone'])
g.check('position', pos(g), expect['pos'])
g.check('flag 0x5EF', g.flag(0x5EF), expect['flag5EF'])
for i in range(1, 25):
    o, s = BLK[i]
    if cur[o:o + s] != ram[o:o + s]:
        g.check(f'box block {i} as saved', False, True)
o = BLK[25][0]
g.check('bag (block 25) as saved', cur[o:o + BLK[25][1]] == ram[o:o + BLK[25][1]], True)
o = BLK[26][0]
g.check('party (block 26) as saved', cur[o:o + BLK[26][1]] == ram[o:o + BLK[26][1]], True)
results['continue_diff_blocks'] = diff
g.shot('continue')
if 'nosession2' not in opts:
    if 'quick' in opts:
        g.set_flag(0x5DD, True)
    did = change(g, mode if mode != 'none' else 'tiny', 1)
    g.say('session 2 changes', did)
    save_and_check(g, 10, 'quick' in opts)
g.step(30)
g.close()
fails = st['fails'] + g.fails
print('FAILS', fails)
json.dump(dict(results=results, fails=fails), open(os.path.join(FS, 'out', name, 'integ.json'), 'w'))
print('RESULT', 'PASS' if not fails else 'FAIL')
