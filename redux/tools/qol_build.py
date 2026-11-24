#!/usr/bin/env python3
"""ReRedux "qol block": C modules in redux/qol/ linked into main RAM, hooked in by declared patches.

  qol_build.py IN.nds OUT.nds [--lang en|jp] [--with NAME,..] [--only NAME,..] [--test]

Memory: a new ARM9 autoload segment of QOL_SIZE (96 KiB) at QOL_BASE = 0x021FD080, the end of the
highest main-RAM overlay (ov290) and B2's main-arena start; the NTR main-arena lo literal
(OS_GetInitArenaLo, 0x0207B3F0) is raised by QOL_SIZE. The arena is only carved up at boot (the
GFL root heaps, 0x6000 + 0x1A3E00 bytes, from OS_AllocFromArenaLo); measured in DeSmuME the arena
keeps 0x37540 bytes (221 KiB) unused for the whole game, so the block leaves 0x1F540 (125 KiB) of
it free and no heap changes size. crt0 copies the segment before main(), flushes the data cache
and invalidates the instruction cache for it; .bss is part of the image (zero at boot). In DSi
(TWL) mode the game's main arena starts at 0x0276DDE0 instead, above the block (not tested).

Modules: every redux/qol/NAME.py (not starting with '_') is a module; `core` is always built
first. A module may define
  SOURCES  = ['NAME.c', ...]   C files in redux/qol/ (default: NAME.c if it exists)
  PATCHES  = [dict(...), ...]  or def PATCHES(ctx): -> list   (see Patch below)
  FRAME    = ['func', ...]     void func(void) called once per main-loop frame (core's hook)
  SYMS     = {'Name': 0x...}   extra B2 symbols (Thumb functions with bit 0 set) for the linker
  DEFINES  = ['-DFOO=1']       extra compiler flags for this build
  ENABLED  = False             only built when named with --with (default True)
  LANGS    = ('en',)           only for these languages (default both)
  def files(ctx): -> {'a/0/1/6' or file id: bytes}   data file replacements (ctx.rom has the
                                                    files changed so far, ctx.fid(path))
  HEADER   = {offset: (old_bytes, new_bytes)}   ROM header fields (offset < 0x15E) to change; the old bytes
             are checked, the header CRC16 is recomputed (e.g. the card timing, loadspeed.py)
  TEXTS    = [dict(bank=('system', 1), key='CATCH_USED', en='...', ja='...'), ...]  or TEXTS(ctx)
             new message lines appended to a text bank ('system' a/0/0/2 or 'story' a/0/0/3) in the
             build's language ('en' strings for --lang en, 'ja' for --lang jp; JP falls back to 'en'
             with a warning). Text format as in gen5text (control codes {BE01}, {0100:1}, ...), a real
             newline is a line break. Optional id=N: the line must get exactly that id (e.g. a line
             the game picks by number). Lines are appended in module order after the bank's last
             line (in every section), after jp_port in JP builds. The ids: C gets qol_texts.h
             (#define TXT_KEY id, TXT_KEY_BANK bank), Python ctx.text_id('KEY') / ctx.texts in
             PATCHES(ctx) and files(ctx). Keys are global (unique across modules).
Patch dict: where='arm9' | 'itcm' | 'ovN' (overlay id N, RAM base read from the overlay table,
stored uncompressed), addr=RAM address, kind, target, and a check:
  expect=bytes     the bytes currently at addr (any kind)
  orig=value       current branch destination (bl/blx/arm_bl/arm_blx) or value (u8/u16/u32/ptr)
  expect=None or unchecked=True   no check (discouraged; marked in qol_map.json)
kinds: 'bl' Thumb BL -> Thumb target · 'blx' Thumb BLX -> ARM · 'arm_bl' ARM BL -> ARM ·
  'arm_blx' ARM BLX -> Thumb · 'jump' Thumb function entry -> target (bx pc; ldr pc, =target:
  12 bytes, 14 if addr is not 4-aligned; no register clobbered) · 'arm_jump' ARM entry (8 bytes) ·
  'bytes' target=bytes · 'u8'/'u16'/'u32' target=int or symbol · 'ptr' u32 = symbol address
  (+1 for Thumb functions; literal pools, function tables).
target strings are symbols of the qol code, the module SYMS / redux/qol/qol_syms.ld / followers/*.ld,
or the follower code (follow.elf). Patches are checked against each other and against the bytes
the followers step and this step change (refused when they overlap) and applied in module order.

The C code: Thumb, the followers' compiler flags, linked by redux/qol/qol.ld at QOL_BASE with the
B2 symbols (followers/syms.ld, ballfx_syms.ld, emote_syms.ld, qol/qol_syms.ld, module SYMS) and the
follower code's global symbols (PROVIDE, when the ROM has followers). -DREDUX_LANG_EN or
-DREDUX_LANG_JP, -DQOL_TEST for test builds. Build files and qol_map.json (layout, symbols,
patches) go to build/qol/LANG[_test]/.
"""
import argparse, importlib.util, json, os, re, struct, subprocess, sys
import gen5text, ndsfs, romtool
import build_followers as BF

HERE = os.path.dirname(os.path.abspath(__file__))
QOL = os.path.normpath(os.path.join(HERE, '..', 'qol'))
FOLLOWERS = os.path.normpath(os.path.join(HERE, '..', 'followers'))
BUILD_ROOT = os.path.normpath(os.path.join(HERE, '..', 'build', 'qol'))

QOL_BASE = 0x021FD080           # end of overlay 290 (highest main-RAM overlay) = vanilla arena lo
QOL_SIZE = 0x18000              # fixed, so code changes never move the ROM layout
MAIN_ARENA_LO_LITERAL = 0x0207B3F0   # OS_GetInitArenaLo case OS_ARENA_MAIN (NTR): .word 0x021FD080
MAIN_ARENA_HI = 0x023E0000
ITCM_BASE = 0x01FF8000
SYM_FILES = [os.path.join(FOLLOWERS, f) for f in ('syms.ld', 'ballfx_syms.ld', 'emote_syms.ld')] + \
            [os.path.join(QOL, 'qol_syms.ld')]
KINDS = {'bl': 4, 'blx': 4, 'arm_bl': 4, 'arm_blx': 4, 'arm_jump': 8, 'bytes': None,
         'u8': 1, 'u16': 2, 'u32': 4, 'ptr': 4, 'jump': None}


class QolError(Exception):
    pass


# --- instruction encoding ---------------------------------------------------------------------

def _range(off, bits, what):
    if not -(1 << bits) <= off < (1 << bits):
        raise QolError(f'{what}: branch offset {off:#x} out of range')


def enc_bl(src, dst):
    assert dst & 1, 'bl: target must be Thumb (bit 0 set)'
    dst &= ~1
    _range(dst - (src + 4), 22, 'bl')
    return BF.thumb_bl(src, dst)


def enc_blx(src, dst):
    if dst & 3:
        raise QolError(f'blx: ARM target {dst:#x} not 4-aligned')
    off = dst - ((src + 4) & ~3)
    _range(off, 22, 'blx')
    off = (off >> 1) & 0x3FFFFF
    return struct.pack('<HH', 0xF000 | (off >> 11), 0xE800 | (off & 0x7FE))


def enc_arm_bl(src, dst):
    if dst & 3 or src & 3:
        raise QolError('arm_bl: source and target must be ARM (4-aligned)')
    off = dst - (src + 8)
    _range(off, 25, 'arm_bl')
    return struct.pack('<I', 0xEB000000 | (off >> 2) & 0xFFFFFF)


def enc_arm_blx(src, dst):
    if not dst & 1 or src & 3:
        raise QolError('arm_blx: ARM source, Thumb target (bit 0 set)')
    off = (dst & ~1) - (src + 8)
    _range(off, 25, 'arm_blx')
    return struct.pack('<I', 0xFA000000 | (off >> 1 & 1) << 24 | (off >> 2) & 0xFFFFFF)


def enc_jump(src, dst):
    """Thumb entry: [nop] bx pc; nop; (ARM) ldr pc, [pc, #-4]; .word dst  (interworking load)"""
    pre = b'\xc0\x46' if src & 2 else b''
    return pre + struct.pack('<HHII', 0x4778, 0x46C0, 0xE51FF004, dst)


def enc_arm_jump(src, dst):
    if src & 3:
        raise QolError('arm_jump: source not 4-aligned')
    return struct.pack('<II', 0xE51FF004, dst)


def dec_branch(code, at, src):
    """Destination of the Thumb BL/BLX or ARM BL/BLX at `at` (Thumb destinations with bit 0 set)."""
    hi, lo = struct.unpack_from('<HH', code, at)
    if hi & 0xF800 == 0xF000 and lo & 0xE800 == 0xE800:
        off = ((hi & 0x7FF) << 12) | ((lo & 0x7FF) << 1)
        if off & 0x400000:
            off -= 0x800000
        if lo & 0x1000:
            return (src + 4 + off) | 1
        return ((src + 4) & ~3) + off
    w = struct.unpack_from('<I', code, at)[0]
    if w >> 24 in (0xEB, 0xFA, 0xFB):
        off = (w & 0xFFFFFF) << 2
        if off & 0x2000000:
            off -= 0x4000000
        if w >> 25 == 0x7D:      # BLX imm
            return (src + 8 + off + ((w >> 24 & 1) << 1)) | 1
        return src + 8 + off
    return None


# --- symbols ----------------------------------------------------------------------------------

def ld_syms(paths):
    out = {}
    for p in paths:
        if os.path.exists(p):
            for m in re.finditer(r'^\s*(\w+)\s*=\s*(0x[0-9A-Fa-f]+)\s*;', open(p).read(), re.M):
                out[m.group(1)] = int(m.group(2), 16)
    return out


def elf_syms(elf, globals_only=False):
    """{name: address} of the symbols defined in `elf` (not the linker-script ones) from readelf;
    Thumb functions with bit 0 set. Global symbols win over local (static) ones of the same name."""
    loc, glob = {}, {}
    txt = subprocess.run(['arm-none-eabi-readelf', '-sW', elf], capture_output=True, text=True, check=True).stdout
    for line in txt.splitlines():
        f = line.split()
        if len(f) < 8 or not f[0].endswith(':') or f[3] not in ('FUNC', 'OBJECT', 'NOTYPE'):
            continue
        if f[6] in ('UND', 'ABS') or f[7].startswith('$') or (globals_only and f[4] != 'GLOBAL'):
            continue
        (glob if f[4] == 'GLOBAL' else loc)[f[7]] = int(f[1], 16)
    return {**loc, **glob}


# --- modules ----------------------------------------------------------------------------------

class Module:
    def __init__(self, name):
        self.name = name
        path = os.path.join(QOL, name + '.py')
        spec = importlib.util.spec_from_file_location('qol_' + name, path)
        self.py = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.py)
        g = lambda k, d: getattr(self.py, k, d)
        default_src = [name + '.c'] if os.path.exists(os.path.join(QOL, name + '.c')) else []
        self.sources = list(g('SOURCES', default_src))
        self.frame = list(g('FRAME', []))
        self.syms = dict(g('SYMS', {}))
        self.defines = list(g('DEFINES', []))
        self.enabled = bool(g('ENABLED', True))
        self.langs = tuple(g('LANGS', ('en', 'jp')))
        self.patches_decl = g('PATCHES', [])
        self.files_fn = g('files', None)
        self.texts_decl = g('TEXTS', [])
        self.header_decl = g('HEADER', {})

    def patches(self, ctx):
        p = self.patches_decl(ctx) if callable(self.patches_decl) else self.patches_decl
        return [dict(d, module=self.name) for d in p]

    def texts(self, ctx):
        t = self.texts_decl(ctx) if callable(self.texts_decl) else self.texts_decl
        return [dict(d, module=self.name) for d in t]


def discover():
    names = sorted(f[:-3] for f in os.listdir(QOL) if f.endswith('.py') and not f.startswith('_'))
    names.remove('core')
    return ['core'] + names


class Ctx:
    """What module hooks (PATCHES(ctx), files(ctx)) see."""

    def __init__(self, rom, files, lang, test):
        self.rom = BF.RomView(rom, files)
        self.files, self.lang, self.test = files, lang, test
        self.syms = {}
        self.texts = {}          # KEY -> (archive 'system'/'story', bank, id)

    def fid(self, path):
        return BF.fid_of(self.rom, path)

    def text_id(self, key):
        if key not in self.texts:
            raise QolError(f'unknown text key {key!r}')
        return self.texts[key][2]


# --- texts ------------------------------------------------------------------------------------

TEXT_ARCS = {'system': 'a/0/0/2', 'story': 'a/0/0/3'}
TEXT_LANG = {'en': 'en', 'jp': 'ja'}


def add_texts(mods, ctx):
    """Append the modules' TEXTS to their banks (ctx.files gets the rebuilt NARCs); fills ctx.texts."""
    want = [t for m in mods for t in m.texts(ctx)]
    if not want:
        return
    lk = TEXT_LANG[ctx.lang]
    by_arc = {}
    for t in want:
        unknown = set(t) - {'bank', 'key', 'en', 'ja', 'id', 'module', 'note'}
        if unknown:
            raise QolError(f'{t["module"]}: text {t.get("key")}: unknown keys {sorted(unknown)}')
        arc, bank = t['bank']
        if arc not in TEXT_ARCS or not re.fullmatch(r'[A-Z][A-Z0-9_]*', t.get('key', '')):
            raise QolError(f'{t["module"]}: bad text {t}')
        if t['key'] in ctx.texts:
            raise QolError(f'{t["module"]}: text key {t["key"]} defined twice')
        ctx.texts[t['key']] = None
        by_arc.setdefault(arc, []).append(t)
    for arc, ts in by_arc.items():
        fid = ctx.fid(TEXT_ARCS[arc])
        raw = ctx.rom.file(fid)
        narc = ndsfs.narc(raw)
        new_banks = {}
        for t in ts:
            bank = t['bank'][1]
            if bank not in new_banks:
                data = narc[bank]
                new_banks[bank] = (gen5text.decode(data), struct.unpack_from('<I', data, 8)[0],
                                   gen5text.padding(data))
            secs = new_banks[bank][0]
            text = t.get(lk)
            if text is None:
                print(f'qol: warning: text {t["key"]} has no {lk!r} string, using en')
                text = t['en']
            text = text.replace('\n', '\\n')
            gen5text.text_to_chars(text)        # syntax check
            tid = len(secs[0])
            if t.get('id') is not None and t['id'] != tid:
                raise QolError(f'{t["module"]}: text {t["key"]} must be {arc} bank {bank} line {t["id"]}, '
                               f'but the bank has {tid} lines')
            for s in secs:
                s.append((text, 0))
            ctx.texts[t['key']] = (arc, bank, tid)
        for bank, (secs, unk, pad) in new_banks.items():
            narc[bank] = gen5text.encode(secs, unk, pad)
        ctx.files[fid] = ndsfs.pack_narc(narc, ndsfs.narc_layout(raw))
    print(f'qol: {len(want)} text lines: ' + ', '.join(
        f'{arc} {bank}: {min(i for a, b, i in ctx.texts.values() if (a, b) == (arc, bank))}-'
        f'{max(i for a, b, i in ctx.texts.values() if (a, b) == (arc, bank))}'
        for arc, bank in sorted({v[:2] for v in ctx.texts.values()})))


def texts_header(texts):
    lines = ['/* generated by tools/qol_build.py: ids of the qol modules\' TEXTS */',
             '#ifndef QOL_TEXTS_H', '#define QOL_TEXTS_H']
    for k, (arc, bank, tid) in texts.items():
        lines += [f'#define TXT_{k} {tid}', f'#define TXT_{k}_BANK {bank}    /* {arc} */']
    return '\n'.join(lines + ['#endif', ''])


# --- patch registry ---------------------------------------------------------------------------

class Space:
    """A patchable address space: arm9 static image, the ITCM block, or one overlay."""

    def __init__(self, name, data, base, limit):
        self.name, self.data, self.base, self.limit = name, data, base, limit

    def off(self, addr, n):
        if not (self.base <= addr and addr + n <= self.limit):
            raise QolError(f'{self.name}: {addr:#x}+{n} outside {self.base:#x}-{self.limit:#x}')
        return addr - self.base


class Registry:
    def __init__(self, arm9, ram, ovs):
        self.arm9, self.ram, self.ovs = bytearray(arm9), ram, ovs
        self.spaces, self.claims, self.log = {}, [], []
        al = romtool.autoloads(self.arm9, ram)
        self.static_end = al[0][4] + ram          # autoload data start = end of the static code/data
        self.itcm = next(a for a in al if a[0] == ITCM_BASE)

    def space(self, where):
        if where in self.spaces:
            return self.spaces[where]
        if where == 'arm9':
            s = Space('arm9', self.arm9, self.ram, self.static_end)
        elif where == 'itcm':
            a, size, _, _, foff = self.itcm
            s = Space('itcm', None, ITCM_BASE, ITCM_BASE + size)
            s.foff = foff
        elif re.fullmatch(r'ov\d+', where):
            ov = int(where[2:])
            s = Space(where, self.ovs.load(ov), self.ovs.ram(ov), self.ovs.ram(ov) + self.ovs.size(ov))
            s.ov = ov
        else:
            raise QolError(f'unknown where {where!r}')
        self.spaces[where] = s
        return s

    def read(self, where, addr, n):
        s = self.space(where)
        o = s.off(addr, n)
        if where == 'itcm':
            return bytes(self.arm9[s.foff + o:s.foff + o + n])
        return bytes(s.data[o:o + n])

    def write(self, where, addr, data):
        s = self.space(where)
        o = s.off(addr, len(data))
        if where == 'itcm':
            self.arm9[s.foff + o:s.foff + o + len(data)] = data
        else:
            s.data[o:o + len(data)] = data

    def claim(self, where, addr, n, what, record=True):
        for w, a, m, other in self.claims:
            if w == where and a < addr + n and addr < a + m:
                raise QolError(f'{what} ({where} {addr:#x}+{n}) overlaps {other} ({w} {a:#x}+{m})')
        if record:
            self.claims.append((where, addr, n, what))

    def finish(self):
        for where, s in self.spaces.items():
            if where.startswith('ov'):
                self.ovs.store(s.ov, s.data)
        return bytes(self.arm9)


def resolve(target, syms):
    if isinstance(target, int):
        return target
    if target not in syms:
        raise QolError(f'unknown symbol {target!r}')
    return syms[target]


def apply_patch(reg, p, syms):
    where, addr, kind = p.get('where'), p.get('addr'), p.get('kind')
    what = f"{p['module']}: {p.get('note') or kind} @{where}:{addr:#x}" if isinstance(addr, int) else p['module']
    if kind not in KINDS or not isinstance(addr, int) or not where:
        raise QolError(f'{what}: bad patch {p}')
    unknown = set(p) - {'where', 'addr', 'kind', 'target', 'expect', 'orig', 'unchecked', 'note', 'module'}
    if unknown:
        raise QolError(f'{what}: unknown keys {sorted(unknown)}')
    if 'expect' not in p and 'orig' not in p and not p.get('unchecked'):
        raise QolError(f'{what}: give expect= (current bytes) or orig= (current target/value), or unchecked=True')
    t = p.get('target')
    try:
        if kind == 'bytes':
            new = bytes(t)
        elif kind in ('u8', 'u16', 'u32', 'ptr'):
            new = resolve(t, syms).to_bytes(KINDS[kind], 'little')
        else:
            dst = resolve(t, syms)
            if kind == 'bl' and not dst & 1:
                raise QolError('bl to an ARM target, use blx')
            new = {'bl': enc_bl, 'blx': enc_blx, 'arm_bl': enc_arm_bl, 'arm_blx': enc_arm_blx,
                   'jump': enc_jump, 'arm_jump': enc_arm_jump}[kind](addr, dst)
        reg.claim(where, addr, len(new), what, record=False)
        cur = reg.read(where, addr, len(new))
    except (QolError, OverflowError, TypeError) as e:
        raise QolError(f'{what}: {e}' if not str(e).startswith(what) else str(e))
    if p.get('expect') is not None and cur != bytes(p['expect']):
        raise QolError(f'{what}: expected {bytes(p["expect"]).hex()}, found {cur.hex()}')
    if 'orig' in p:
        if kind in ('bl', 'blx', 'arm_bl', 'arm_blx'):
            d = dec_branch(cur, 0, addr)
            if d is None or (d | 1) != (p['orig'] | 1):
                raise QolError(f'{what}: expected a call to {p["orig"]:#x}, found {cur.hex()}'
                               + (f' (-> {d:#x})' if d is not None else ''))
        elif kind in ('u8', 'u16', 'u32', 'ptr'):
            if int.from_bytes(cur, 'little') != p['orig']:
                raise QolError(f'{what}: expected {p["orig"]:#x}, found {int.from_bytes(cur, "little"):#x}')
        else:
            raise QolError(f'{what}: orig= is not supported for {kind}, use expect=')
    reg.claim(where, addr, len(new), what)
    reg.write(where, addr, new)
    reg.log.append(dict(module=p['module'], where=where, addr=addr, kind=kind, size=len(new),
                        target=t if isinstance(t, (str, int)) else bytes(t).hex(), old=cur.hex(), new=new.hex(),
                        note=p.get('note', ''), checked=p.get('expect') is not None or 'orig' in p))


# --- compile ----------------------------------------------------------------------------------

CFLAGS = BF.CFLAGS


def compile_link(mods, out_dir, lang, test, follower_elf, texts_h=None):
    os.makedirs(out_dir, exist_ok=True)
    open(os.path.join(out_dir, 'qol_texts.h'), 'w').write(texts_h or texts_header({}))
    frame = [f for m in mods for f in m.frame]
    gen_c = os.path.join(out_dir, 'qol_gen.c')
    with open(gen_c, 'w') as f:
        f.write('/* generated by tools/qol_build.py: FRAME functions of the enabled modules */\n')
        f.write('#include "qol.h"\n')
        f.write(''.join(f'void {n}(void);\n' for n in frame))
        f.write('const qol_fn qol_frame_hooks[] = {' + ''.join(f'{n}, ' for n in frame) + '0};\n')
        f.write('const char qol_modules[] = "' + ','.join(m.name for m in mods) + '";\n')
    lines = ['/* generated by tools/qol_build.py */']
    for m in mods:
        lines += [f'{k} = {v:#010x};    /* {m.name}.py */' for k, v in m.syms.items()]
    if follower_elf:
        lines += [f'PROVIDE({k} = {v:#010x});' for k, v in sorted(elf_syms(follower_elf, True).items())]
    open(os.path.join(out_dir, 'gen_syms.ld'), 'w').write('\n'.join(lines) + '\n')
    defines = ['-DREDUX_LANG_' + lang.upper(), f'-DQOL_BASE={QOL_BASE:#x}', f'-DQOL_SIZE={QOL_SIZE:#x}']
    defines += ['-DQOL_TEST'] if test else []
    defines += ['-DQOL_FOLLOWERS'] if follower_elf else []
    defines += [d for m in mods for d in m.defines]
    objs = []
    for src in [os.path.join(QOL, s) for m in mods for s in m.sources] + [gen_c]:
        obj = os.path.join(out_dir, os.path.basename(src)[:-2] + '.o')
        if obj in objs:
            raise QolError(f'two sources named {os.path.basename(src)}')
        subprocess.run(['arm-none-eabi-gcc', *CFLAGS, *defines, '-I', QOL, '-I', out_dir, '-I', FOLLOWERS,
                        '-c', src, '-o', obj], check=True)
        objs.append(obj)
    elf, binf = os.path.join(out_dir, 'qol.elf'), os.path.join(out_dir, 'qol.bin')
    keep = sorted({p['target'] for m in mods for p in m.patches_static if isinstance(p.get('target'), str)})
    subprocess.run(['arm-none-eabi-ld', '-L', QOL, '-L', FOLLOWERS, '-L', out_dir, '-T', os.path.join(QOL, 'qol.ld'),
                    '--gc-sections', '--no-warn-rwx-segments', *[f'--undefined={k}' for k in keep],
                    '-Map', os.path.join(out_dir, 'qol.map'), '-o', elf, *objs, BF.libgcc()], check=True)
    subprocess.run(['arm-none-eabi-objcopy', '-O', 'binary', '-j', '.qol', elf, binf], check=True)
    blob = open(binf, 'rb').read()
    syms = elf_syms(elf)
    if syms.get('qol_header') != QOL_BASE:
        raise QolError('qol_header must be first in the block')
    if len(blob) > QOL_SIZE:
        raise QolError(f'qol code {len(blob):#x} exceeds the block ({QOL_SIZE:#x})')
    return blob, syms, frame


# --- the step ---------------------------------------------------------------------------------

def has_followers(arm9, ram):
    itcm = next(a for a in romtool.autoloads(arm9, ram) if a[0] == ITCM_BASE)
    return itcm[1] != BF.ITCM_END_VANILLA - ITCM_BASE


def build(src, dst, lang='en', with_=(), only=None, test=False, follower_elf=None, tag=None):
    """Compile the enabled qol modules and patch them into ROM `src`; write `dst`. follower_elf:
    the follower code linked into `src` (default: build/followers/follow.elf when the ROM has
    followers; pass it explicitly when several builds share that directory). -> qol_map dict"""
    rom = ndsfs.Rom(src)
    ram = rom.arm9_ram
    arm9 = bytes(rom.m[rom.arm9[0]:rom.arm9[0] + rom.arm9[1]])
    if any(a[0] == QOL_BASE for a in romtool.autoloads(arm9, ram)):
        raise QolError(f'{src} already has a qol block')
    fol = has_followers(arm9, ram)
    if fol and follower_elf is None:
        follower_elf = os.path.join(BF.BUILD, 'follow.elf')
    if not fol:
        follower_elf = None
    names = discover()
    mods = []
    for n in names:
        m = Module(n)
        want = (n == 'core' or (only is None and (m.enabled or n in with_)) or
                (only is not None and n in only))
        if want and lang in m.langs:
            mods.append(m)
    files = {}
    ctx = Ctx(rom, files, lang, test)
    add_texts(mods, ctx)
    for m in mods:
        m.patches_static = m.patches(ctx)
    out_dir = os.path.join(BUILD_ROOT, tag or (lang + ('_test' if test else '')))
    os.makedirs(out_dir, exist_ok=True)
    for m in mods:                      # generated headers (e.g. tables from the ROM's data): HEADERS(ctx)
        hdr = getattr(m.py, 'HEADERS', None)
        for name, text in (hdr(ctx) if callable(hdr) else {}).items():
            open(os.path.join(out_dir, name), 'w').write(text)
    blob, qsyms, frame = compile_link(mods, out_dir, lang, test, follower_elf, texts_header(ctx.texts))
    syms = ld_syms(SYM_FILES)
    for m in mods:
        syms.update(m.syms)
    if follower_elf:
        syms.update(elf_syms(follower_elf, True))
    syms.update(qsyms)
    ctx.syms = syms

    ovs = romtool.OverlayTable(rom, files)
    reg = Registry(arm9, ram, ovs)
    reg.claim('arm9', MAIN_ARENA_LO_LITERAL, 4, 'qol: main arena lo literal')
    if fol:
        added = struct.unpack_from('<I', arm9, BF.LIT_POKE_END - ram)[0] != BF.POKE_OBJ_END
        for where, a, n, what in BF.follower_patch_ranges(added):
            reg.claim(where, a, n, what)
    for m in mods:
        for p in m.patches_static:
            apply_patch(reg, p, syms)
    arm9 = reg.finish()
    lit = MAIN_ARENA_LO_LITERAL - ram
    if struct.unpack_from('<I', arm9, lit)[0] != QOL_BASE:
        raise QolError('main arena lo literal is not 0x021FD080')
    end = max(o['ram'] + o['ram_size'] + o['bss'] for o in rom.overlays() if o['ram'] < 0x02400000)
    if end > QOL_BASE:
        raise QolError(f'an overlay ends at {end:#x}, inside the qol block')
    arm9 = bytearray(romtool.add_autoload(arm9, ram, QOL_BASE, blob + bytes(QOL_SIZE - len(blob))))
    struct.pack_into('<I', arm9, lit, QOL_BASE + QOL_SIZE)
    for m in mods:
        if m.files_fn:
            for k, v in m.files_fn(ctx).items():
                files[ctx.fid(k) if isinstance(k, str) else k] = v
    out = romtool.build(src, files=files, arm9=bytes(arm9), ovt9=ovs.bytes())
    hdr_log = []
    for m in mods:
        for off, (old, new) in sorted(m.header_decl.items()):
            if not 0 <= off < 0x15E or off + len(old) > 0x15E or len(old) != len(new):
                raise QolError(f'{m.name}: bad header patch at {off:#x}')
            if out[off:off + len(old)] != old:
                raise QolError(f'{m.name}: header {off:#x} is {out[off:off + len(old)].hex()}, expected {old.hex()}')
            hdr_log.append(dict(module=m.name, offset=off, old=old.hex(), new=new.hex()))
    if hdr_log:
        out = bytearray(out)
        for h in hdr_log:
            new = bytes.fromhex(h['new'])
            out[h['offset']:h['offset'] + len(new)] = new
        struct.pack_into('<H', out, 0x15E, romtool.crc16(bytes(out[:0x15E])))
        out = bytes(out)
    open(dst, 'wb').write(out)
    info = dict(rom=dst, lang=lang, test=test, base=QOL_BASE, size=QOL_SIZE, used=len(blob),
                arena_lo=QOL_BASE + QOL_SIZE, modules=[m.name for m in mods], frame=frame,
                symbols={k: v for k, v in sorted(qsyms.items())}, patches=reg.log, header=hdr_log,
                texts={k: list(v) for k, v in ctx.texts.items()})
    json.dump(info, open(os.path.join(out_dir, 'qol_map.json'), 'w'), indent=1)
    print(f'qol: {len(mods)} modules ({", ".join(info["modules"])}), {len(blob)} of {QOL_SIZE} bytes at '
          f'{QOL_BASE:#010x}, {len(reg.log)} patches, arena lo {QOL_BASE + QOL_SIZE:#010x}; wrote {dst}')
    return info


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('src')
    ap.add_argument('dst')
    ap.add_argument('--lang', default='en', choices=('en', 'jp'))
    ap.add_argument('--with', dest='with_', default='', help='also build these disabled modules (comma list)')
    ap.add_argument('--only', help='build only core and these modules (comma list)')
    ap.add_argument('--test', action='store_true', help='-DQOL_TEST')
    ap.add_argument('--follower-elf', help='follower code ELF of SRC (default build/followers/follow.elf)')
    a = ap.parse_args()
    try:
        build(a.src, a.dst, a.lang, [n for n in a.with_.split(',') if n],
              a.only.split(',') if a.only is not None else None, a.test, a.follower_elf)
    except QolError as e:
        sys.exit(f'qol_build: {e}')


if __name__ == '__main__':
    main()
