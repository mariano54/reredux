#!/usr/bin/env python3
"""Assemble vanilla Black 2 (IREO) modules from the pokeblack2 disassembly with GNU as.

pokeblack2 targets mwasmarm; a few mechanical rewrites make it GAS-compatible while keeping
every label at its original address (verified: zero drift on main and all touched overlays):
  * strip `;` comments (mwasm comment char; in GAS `;` separates statements)
  * `.public` -> `.global`, bare `.rodata` -> `.section .rodata`, drop mwasm `.section` flags
  * drop trailing commas on `.byte` lines (GAS emits an extra 0 byte for them)

Outputs build/vanilla/<module>.bin (flat image from the lowest section address) and
build/vanilla/<module>.json (section bases/sizes). Remaining byte differences against the real
ROM are encoding choices only (see diffutil.py), not layout.

usage: build_vanilla.py [main itcm overlay_167 ...]   (default: main itcm + all overlays)
"""
import hashlib, json, os, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PB2 = os.environ.get('POKEBLACK2', os.path.join(ROOT, 'build', 'ext', 'pokeblack2'))
ASM = os.path.join(PB2, 'asm')
OUT = os.path.join(ROOT, 'build', 'vanilla')
WORK = os.path.join(OUT, 'work')
ADDR_RE = re.compile(r'([0-9A-F]{8})$')
LABEL_RE = re.compile(r'^(?:_|FUN_)([0-9A-F]{8})$')
DEF_RE = re.compile(r'^([A-Za-z_][\w]*):\s*;\s*0x([0-9A-Fa-f]{8})', re.M)
def _manifest():
    out = {}
    path = os.path.join(PB2, 'black2.en', 'overlays.sha1')
    if os.path.exists(path):
        for line in open(path):
            h, p = line.split()
            m = re.search(r'OVY_(\d+)\.', p)
            if m:
                out[f'overlay_{m.group(1)}'] = h
    return out


MANIFEST = _manifest()
FUNC_RE = re.compile(r'^\s*(thumb|arm|non_word_aligned_thumb)_func_start\s+(\w+)', re.M)
SKIP_SECTIONS = {'.ARM.attributes', '.comment'}


def strip_comment(line):
    quoted = False
    for i, c in enumerate(line):
        if c == '"' and (i == 0 or line[i - 1] != '\\'):
            quoted = not quoted
        elif c == ';' and not quoted:
            return line[:i].rstrip()
    return line


T1_RE = re.compile(r'^(\s*)(add|sub)\s+r([0-7]),\s*r([0-7]),\s*#(0x[0-9a-fA-F]+|\d+)\s*$')
MODE_RE = re.compile(r'^\s*(?:(thumb|non_word_aligned_thumb)_func_start|(arm)_func_start|\.(thumb|arm)\b)')


def gas_source(text, symtab=None):
    out = []
    thumb = False
    for line in text.splitlines():
        line = strip_comment(line)
        m = MODE_RE.match(line)
        if m:
            thumb = bool(m.group(1)) or m.group(3) == 'thumb'
        m = T1_RE.match(line) if thumb else None
        if m and int(m.group(5), 0) < 8:
            # mwasm encodes 3-operand `add/sub rd, rn, #imm3` as T1 even when rd == rn; GAS picks T2.
            op = 0x1C00 if m.group(2) == 'add' else 0x1E00
            d, n, imm = int(m.group(3)), int(m.group(4)), int(m.group(5), 0)
            line = f'{m.group(1)}.hword {op | imm << 6 | n << 3 | d:#06x}'
        line = re.sub(r'^(\s*)\.public\s', r'\1.global ', line)
        line = re.sub(r'^(\s*)\.rodata\s*$', r'\1.section .rodata', line)
        m = re.match(r'^(\s*)\.section\s+(\.[\w.]+)', line)
        if m and m.group(2) not in ('.text', '.data', '.bss', '.rodata'):
            line = f'{m.group(1)}.section {m.group(2)},"ax"'   # mwasm flags; keep it allocated
        elif m:
            line = f'{m.group(1)}.section {m.group(2)}'
        # `.word NAME - 1` always stands for NAME's own address (mwasm valued NAME at +1);
        # GAS would emit address - 1.
        if '- 1' in line or '-1' in line:
            def fix(m):
                name = m.group(1)
                a = (symtab or {}).get(name)
                if a is None:
                    mm = LABEL_RE.match(name)
                    a = int(mm.group(1), 16) if mm else None
                return f'{a:#010x}' if a is not None else m.group(0)
            line = re.sub(r'\b([A-Za-z_]\w*)\s*-\s*1\b', fix, line)
        if re.match(r'^\s*\.byte\b', line):
            line = re.sub(r'[,\\\s]+$', '', line)
        out.append(line)
    return '\n'.join(out) + '\n'


def global_symbols():
    """name -> address for every `name: ; 0xADDR` definition in the disassembly."""
    table, modes = {}, {}
    paths = [os.path.join(d, fn) for d, _, fns in os.walk(PB2) if '/.git' not in d
             for fn in fns if fn.endswith('.s')]   # asm/ plus lib/ (syscalls, crt0)
    for path in paths:
        if True:
            with open(path, errors='replace') as f:
                text = f.read()
            for name, addr in DEF_RE.findall(text):
                table.setdefault(name, int(addr, 16))
            for mode, name in FUNC_RE.findall(text):
                modes.setdefault(name, 'arm' if mode == 'arm' else 'thumb')
    # linker-defined symbols the disassembly references but never defines
    table.setdefault('dtcm_bss', 0x02FE00A0)   # DTCM base + 0xA0 bytes of DTCM data (autoload table)
    return table, modes


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def build(module, gsyms):
    src = os.path.join(ASM, module + '.s')
    w = os.path.join(WORK, module)
    os.makedirs(w, exist_ok=True)
    macros = os.path.join(w, 'asm', 'macros')
    os.makedirs(macros, exist_ok=True)
    for fn in os.listdir(os.path.join(ASM, 'macros')):
        with open(os.path.join(ASM, 'macros', fn), errors='replace') as f:
            src_macros = gas_source(f.read())
            # mwasm gives thumb function symbols odd values (so `.word FUN_x - 1` is the even address);
            # GAS only does that for labels marked .thumb_func.
            src_macros = re.sub(r'(\.macro (?:non_word_aligned_)?thumb_func_start name\n(?:.*\n)*?\s*\.thumb)\n',
                                r'\1\n\t.thumb_func\n', src_macros)
            with open(os.path.join(macros, fn), 'w') as g:
                g.write(src_macros)
    with open(src, errors='replace') as f:
        text = f.read()
    with open(os.path.join(w, 'm.s'), 'w') as f:
        f.write(gas_source(text, gsyms[0]))
    r = run(['arm-none-eabi-as', '-mcpu=arm946e-s', '-o', 'm.o', 'm.s'], cwd=w)
    if r.returncode:
        errs = [l for l in r.stderr.splitlines() if 'Error' in l]
        return module, {'error': errs[:5]}
    # section sizes
    hdr = run(['arm-none-eabi-objdump', '-h', 'm.o'], cwd=w).stdout
    sizes = {m.group(1): int(m.group(2), 16)
             for m in re.finditer(r'^\s+\d+\s+(\S+)\s+([0-9a-f]+)', hdr, re.M)}
    # section bases from address-named / comment-defined symbols
    syms = run(['arm-none-eabi-objdump', '-t', 'm.o'], cwd=w).stdout
    bases, drift = {}, 0
    local_defs = dict((n, int(a, 16)) for n, a in DEF_RE.findall(text))
    for line in syms.splitlines():
        p = line.split()
        if len(p) < 5 or not re.fullmatch(r'[0-9a-f]{8}', p[0]):
            continue
        val, sec, name = int(p[0], 16), p[-3], p[-1]
        if sec in ('*UND*', '*ABS*') or sec.startswith('.ARM'):
            continue
        m = LABEL_RE.match(name) or (None if 'thunk' in name else ADDR_RE.search(name))
        want = int(m.group(1), 16) if m else local_defs.get(name)
        if want is None:
            continue
        if sec not in bases:
            bases[sec] = want - val
        elif bases[sec] + val != want:
            drift += 1
    und = [l.split()[-1] for l in run(['arm-none-eabi-nm', '-u', 'm.o'], cwd=w).stdout.splitlines()]
    # Externs become typed absolute symbols so ld emits direct bl/blx instead of interworking
    # veneers (which would otherwise show up as fake diffs).
    table, modes = gsyms
    # Placeholder names collide across overlays, so the global mode table can be wrong. The call
    # sites say which mode the target is in: from thumb, `bl` = thumb target, `blx` = ARM target.
    local_modes = {}
    thumb = False
    for line in text.splitlines():
        mm = MODE_RE.match(strip_comment(line))
        if mm:
            thumb = bool(mm.group(1)) or mm.group(3) == 'thumb'
        cm = re.match(r'^\s*(blx?)\s+([A-Za-z_]\w*)\s*$', strip_comment(line))
        if cm:
            is_blx = cm.group(1) == 'blx'
            local_modes.setdefault(cm.group(2), 'arm' if is_blx == thumb else 'thumb')
    stubs, unresolved = [], []
    for u in und:
        m = ADDR_RE.search(u)
        addr = table.get(u, int(m.group(1), 16) if m else None)
        if addr is None:
            unresolved.append(u)
            addr = 0x02004000
        stubs.append(f'\t.global {u}')
        mode = local_modes.get(u, modes.get(u))
        if mode == 'thumb':
            stubs.append(f'\t.type {u}, %function\n\t.thumb_set {u}, {addr:#010x}')
        elif mode == 'arm':
            stubs.append(f'\t.type {u}, %function\n\t.set {u}, {addr:#010x}')
        else:
            stubs.append(f'\t.set {u}, {addr:#010x}')
    with open(os.path.join(w, 'stubs.s'), 'w') as f:
        f.write('\n'.join(stubs) + '\n')
    r = run(['arm-none-eabi-as', '-mcpu=arm946e-s', '-o', 'stubs.o', 'stubs.s'], cwd=w)
    if r.returncode:
        return module, {'error': r.stderr.splitlines()[:5]}
    lines = ['SECTIONS {']
    loadable = []
    for sec, size in sizes.items():
        if sec in SKIP_SECTIONS or size == 0 or sec not in bases:
            continue
        noload = ' (NOLOAD)' if sec == '.bss' else ''
        lines.append(f'  {sec} {bases[sec]:#x}{noload} : {{ m.o({sec}) }}')
        if sec != '.bss':
            loadable.append((bases[sec], sec, size))
    lines.append('  /DISCARD/ : { *(.ARM.attributes) *(.comment) }')
    lines.append('}')
    with open(os.path.join(w, 'link.ld'), 'w') as f:
        f.write('\n'.join(lines) + '\n')
    r = run(['arm-none-eabi-ld', '--use-blx', '--no-warn-rwx-segments', '--no-check-sections', '-T', 'link.ld', '-o', 'm.elf', 'm.o', 'stubs.o'], cwd=w)
    if r.returncode:
        return module, {'error': r.stderr.splitlines()[:5]}
    loadable.sort()
    base = loadable[0][0]
    img = bytearray()
    for b, sec, size in loadable:
        run(['arm-none-eabi-objcopy', '-O', 'binary', '-j', sec, 'm.elf', 'sec.bin'], cwd=w)
        with open(os.path.join(w, 'sec.bin'), 'rb') as f:
            data = f.read()[:size]  # drop linker veneers appended past the original section
        off = b - base
        if len(img) < off:
            img += bytes(off - len(img))
        img[off:off + len(data)] = data
    # pokeblack2 records the SHA-1 of every linked overlay; mwld pads the image end to a section
    # alignment we don't model, so find the padding that reproduces the hash.
    verified = None
    want = MANIFEST.get(module)
    if want:
        verified = False
        for al in (1, 4, 8, 16, 32, 64, 128, 256, 512):
            padded = bytes(img) + bytes(-len(img) % al)
            if hashlib.sha1(padded).hexdigest() == want:
                img, verified = bytearray(padded), True
                break
    with open(os.path.join(OUT, module + '.bin'), 'wb') as f:
        f.write(img)
    meta = {'base': base, 'size': len(img), 'drift': drift, 'unresolved': unresolved, 'verified': verified,
            'sections': [{'name': s, 'base': b, 'size': z} for b, s, z in loadable],
            'bss': {'base': bases.get('.bss'), 'size': sizes.get('.bss', 0)}}
    with open(os.path.join(OUT, module + '.json'), 'w') as f:
        json.dump(meta, f, indent=1)
    return module, meta


def main():
    os.makedirs(WORK, exist_ok=True)
    mods = sys.argv[1:] or (['main', 'itcm'] + sorted(
        (f[:-2] for f in os.listdir(ASM) if f.startswith('overlay_') and f.endswith('.s')),
        key=lambda s: int(s.split('_')[1])))
    gsyms = global_symbols()
    bad = 0
    with ThreadPoolExecutor(os.cpu_count()) as ex:
        for mod, meta in ex.map(lambda m: build(m, gsyms), mods):
            if 'error' in meta or meta['drift']:
                bad += 1
                print(f'{mod}: FAILED {meta.get("error") or "drift=%d" % meta["drift"]}')
    print(f'built {len(mods) - bad}/{len(mods)} modules into {OUT}')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
