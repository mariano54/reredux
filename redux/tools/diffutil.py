"""Byte diffing between a GAS-built vanilla image and Redux bytes, ignoring GAS encoding artifacts."""
import os, re, struct, subprocess, tempfile


PLACEHOLDER = 0x02004000   # address build_vanilla.py gives unresolved externs


def thumb_t1_form(x):
    """GAS `adds/subs rd,#imm8` (T2) with imm < 8 -> the `adds/subs rd,rd,#imm3` (T1) encoding mwasm used."""
    op = x >> 11
    if op in (0b00110, 0b00111):
        d, imm = (x >> 8) & 7, x & 0xFF
        if imm < 8:
            opc = 0b0001110 if op == 0b00110 else 0b0001111
            return (opc << 9) | (imm << 6) | (d << 3) | d
    return None


def thumb_add_equiv(a, b):
    """GAS picks `adds rd,#imm8` (T2) where mwasm/mwcc emitted `adds rd,rd,#imm3` (T1); subs too."""
    for x, y in ((a, b), (b, a)):
        op = x >> 11
        if op in (0b00110, 0b00111):
            d, imm = (x >> 8) & 7, x & 0xFF
            if imm < 8:
                opc = 0b0001110 if op == 0b00110 else 0b0001111
                if y == (opc << 9) | (imm << 6) | (d << 3) | d:
                    return True
    return False


def real_diffs(vanilla, redux, known, base):
    """Addresses where Redux differs from vanilla, skipping unknown bytes and encoding artifacts:
    words differing only in the thumb bit (pointers to externs GAS cannot type) and T1/T2 adds."""
    out, i, n = [], 0, min(len(vanilla), len(redux))
    while i < n:
        if not known[i] or vanilla[i] == redux[i]:
            i += 1
            continue
        w = i & ~3
        if w + 4 <= n:
            V = struct.unpack('<I', vanilla[w:w + 4])[0]
            # unknown Redux bytes are assumed unchanged
            rb = bytes(redux[w + k] if known[w + k] else vanilla[w + k] for k in range(4))
            Rw = struct.unpack('<I', rb)[0]
            if V == PLACEHOLDER:   # pointer to an extern build_vanilla could not resolve (DSProt)
                i = w + 4
                continue
            # pointer words off by one: thumb bit, or `.word FUN_x - 1`, which mwasm and GAS evaluate
            # differently. Only for code/data addresses so constant edits (e.g. 17 -> 18) still show.
            if abs(V - Rw) == 1 or V ^ Rw == 1:
                if 0x01FF8000 <= min(V, Rw) < 0x02400000:
                    i = w + 4
                    continue
        h = i & ~1
        if h + 2 <= n:
            V = struct.unpack('<H', vanilla[h:h + 2])[0]
            alt = thumb_t1_form(V)
            if alt is not None:
                ab = struct.pack('<H', alt)
                # every known Redux byte matches the mwasm (T1) encoding of the same instruction
                if all(not known[h + k] or redux[h + k] == ab[k] for k in range(2)):
                    i = h + 2
                    continue
        out.append(base + i)
        i += 1
    return out


def runs(addrs, gap=8):
    out = []
    for a in addrs:
        if out and a - out[-1][1] <= gap:
            out[-1][1] = a
        else:
            out.append([a, a])
    return out


def disasm(data, addr, mode):
    with tempfile.NamedTemporaryFile(suffix='.bin', delete=False) as f:
        f.write(data)
        path = f.name
    try:
        cmd = ['arm-none-eabi-objdump', '-D', '-z', '-b', 'binary', '-marm', f'--adjust-vma={addr:#x}', path]
        if mode == 'thumb':
            cmd[5:5] = ['-Mforce-thumb']
        txt = subprocess.run(cmd, capture_output=True, text=True).stdout
    finally:
        os.unlink(path)
    lines = []
    for l in txt.splitlines():
        m = re.match(r'\s*([0-9a-f]+):\s+((?:[0-9a-f]{2,8} ?)+)\s+(.*)$', l)
        if m:
            lines.append((int(m.group(1), 16), m.group(2).strip(), re.sub(r'\s+', ' ', m.group(3)).split(';')[0].strip()))
    return lines
