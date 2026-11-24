"""Gen 5 (B2/W2) event script decompiler/assembler (lossless).

File layout: u32 relative entry offsets (each relative to the end of its own field), terminated by
u16 0xFD13; then bytecode. An instruction is u16 command id + parameters (sizes from the
PokeScriptSDK5 definitions: ushort/ref ushort/const ushort/fx16 = 2, byte/bool = 1, int/fx32 = 4).
Branch parameters (`int` on Jump/Call/CallActionSeq commands) are s32 offsets relative to the end
of the parameter. Movement data (targets of ActorCmdExec) is u16 code, u16 count pairs ending with
code 0x00FE.

Listing format (one item per line):
  .script NAME            header entry (in order)
  NAME:                   label
  CmdName a, b, @label    instruction (branch args are labels)
  .move CODE, COUNT       movement step
  .hword 0x1234 / .byte 0x12   raw data the decoder could not attribute (several: .hword 1, 2, 3)
"""
import os, re, struct

SIZES = {'ushort': 2, 'ref ushort': 2, 'const ushort': 2, 'fx16': 2, 'byte': 1, 'bool': 1,
         'int': 4, 'fx32': 4}
FLOW_END = {'End', 'Return'}
HEADER_END = 0xFD13


def load_defs(paths):
    """{id: (name, [(type, size, is_branch)], ctype, [param names])} from PokeScriptSDK5 YAML files."""
    defs = {}
    for path in paths:
        cur = None
        for line in open(path, encoding='utf-8'):
            m = re.match(r'^(0x[0-9a-fA-F]+):\s*$', line)
            if m:
                cur = int(m.group(1), 16)
                defs.setdefault(cur, {'name': f'CMD_{cur:X}', 'params': [], 'pnames': [], 'ctype': None})
                defs[cur]['params'] = []
                defs[cur]['pnames'] = []
                continue
            if cur is None:
                continue
            m = re.match(r'^  Name:\s*(\S+)', line)
            if m:
                defs[cur]['name'] = m.group(1)
            m = re.match(r'^    - Name:\s*(\S+)', line)
            if m:
                defs[cur]['pnames'].append(m.group(1))
            m = re.match(r'^      Type:\s*(.+?)\s*$', line)
            if m:
                defs[cur]['params'].append(m.group(1))
                if len(defs[cur]['pnames']) < len(defs[cur]['params']):
                    defs[cur]['pnames'].append('')
            m = re.match(r'^  CommandType:\s*(\S+)', line)
            if m:
                defs[cur]['ctype'] = m.group(1)
    out = {}
    for i, d in defs.items():
        branchy = d['ctype'] in ('Jump', 'Call', 'CallActionSeq')
        ps = []
        for t in d['params']:
            if t not in SIZES:
                raise ValueError(f'unknown param type {t!r} in command {i:#x}')
            ps.append((t, SIZES[t], branchy and t == 'int'))
        out[i] = (d['name'], ps, d['ctype'], d['pnames'])
    # unique names for the assembler
    seen = {}
    for i in sorted(out):
        n = out[i][0]
        if n in seen:
            out[i] = (f'{n}_{i:X}',) + out[i][1:]
        seen[out[i][0]] = i
    return out


def default_defs(build_dir):
    """Base commands merged with *all* overlay files (later overlays win on id clashes)."""
    return defsets(build_dir)[None]


_DEFSETS = {}


def defsets(build_dir):
    """{None: base only, N: base + Overlay N} - overlay commands (0x3E8+) differ per overlay."""
    if build_dir in _DEFSETS:
        return _DEFSETS[build_dir]
    base = os.path.join(build_dir, 'ext', 'PokeScriptSDK5', 'yml', 'B2W2')
    out = {None: load_defs([os.path.join(base, 'Base.yml')])}
    for f in sorted(os.listdir(base)):
        m = re.match(r'Overlay (\d+)\.yml$', f)
        if m:
            out[int(m.group(1))] = load_defs([os.path.join(base, 'Base.yml'), os.path.join(base, f)])
    _DEFSETS[build_dir] = out
    return out


def decompile_best(data, build_dir, sym=None):
    """Try every overlay command set; keep the one decoding the most bytes as code."""
    best = None
    for ov, defs in defsets(build_dir).items():
        txt, st = decompile(data, defs)
        key = (st['code'] + st['move'], ov is None)
        if best is None or key > best[0]:
            best = (key, ov, txt, st)
    _, ov, txt, st = best
    if sym is not None:
        txt, _ = decompile(data, defsets(build_dir)[ov], sym)
    if ov is not None:
        txt = f'.overlay {ov}\n' + txt
    st['overlay'] = ov
    return txt, st


def assemble_any(text, build_dir, sym=None):
    first = text.split('\n', 1)[0]
    ov = int(first.split()[1]) if first.startswith('.overlay ') else None
    return assemble(text if ov is None else text.split('\n', 1)[1], defsets(build_dir)[ov], sym)


def decompile(data, defs, sym=None):
    """-> (listing text, stats). Never fails: unknown regions become raw data."""
    n = len(data)
    entries, p = [], 0
    while p + 2 <= n and struct.unpack_from('<H', data, p)[0] != HEADER_END:
        if p + 4 > n:
            break
        off = struct.unpack_from('<i', data, p)[0]
        entries.append(p + 4 + off)
        p += 4
    has_term = p + 2 <= n and struct.unpack_from('<H', data, p)[0] == HEADER_END
    hdr_end = p + 2 if has_term else p
    insns = {}      # addr -> (cmd, [values], size)
    moves = {}      # addr -> (code, count)
    labels = {}
    owner = bytearray(n)   # 1 = covered
    code_q = [(e, 'code') for e in entries]
    for e in entries:
        labels.setdefault(e, f'scr_{len(labels)}')

    def take(a, ln):
        if a < hdr_end or a + ln > n or any(owner[a:a + ln]):
            return False
        for k in range(a, a + ln):
            owner[k] = 1
        return True

    while code_q:
        a, kind = code_q.pop()
        if not (hdr_end <= a < n):
            continue          # out-of-file header entry: kept as .script_raw
        if kind == 'move':
            while a + 4 <= n and a not in moves:
                code, cnt = struct.unpack_from('<HH', data, a)
                if not take(a, 4):
                    break
                moves[a] = (code, cnt)
                a += 4
                if code == 0x00FE:
                    break
            continue
        while a + 2 <= n and a not in insns:
            cmd = struct.unpack_from('<H', data, a)[0]
            if cmd not in defs:
                break
            name, ps, ctype = defs[cmd][:3]
            size = 2 + sum(s for _, s, _ in ps)
            if a + size > n or any(owner[a:a + size]) or a < hdr_end:
                break
            vals, q, ok = [], a + 2, True
            for t, s, br in ps:
                v = int.from_bytes(data[q:q + s], 'little', signed=(t in ('int', 'fx32', 'fx16')))
                q += s
                if br:
                    tgt = q + v
                    if not (hdr_end <= tgt < n):
                        ok = False
                    vals.append(('@', tgt))
                else:
                    vals.append(v)
            if not ok:
                break
            take(a, size)
            insns[a] = (cmd, vals, size)
            for v in vals:
                if isinstance(v, tuple):
                    tgt = v[1]
                    labels.setdefault(tgt, f'{"mv" if ctype == "CallActionSeq" else "L"}_{tgt:04X}')
                    code_q.append((tgt, 'move' if ctype == 'CallActionSeq' else 'code'))
            a += size
            if ctype in FLOW_END or (ctype == 'Jump' and cmd == 0x1E):
                break
    # lay out items, then emit; a label is only emitted where an item starts (or at the end of the
    # file), everything else is referenced by its raw relative offset so nothing is lost
    items, a = [], hdr_end
    while a < n:
        if a in insns:
            items.append((a, 'insn'))
            a += insns[a][2]
        elif a in moves:
            items.append((a, 'move'))
            a += 4
        else:
            b = a + 1
            while b < n and b not in insns and b not in moves and b not in labels:
                b += 1
            items.append((a, ('raw', b)))
            a = b
    starts = {x[0] for x in items} | {n}
    emitted = {k for k in labels if k in starts}
    # stable names: entry labels stay scr_N; others are numbered within the script they follow,
    # so an edit only renames labels inside that script
    entry_set = set(entries)
    cur, counts = 'pre', {}
    for a in sorted(emitted):
        if a in entry_set:
            cur = labels[a]
            continue
        kind_ = 'mv' if labels[a].startswith('mv_') else 'L'
        counts[(cur, kind_)] = counts.get((cur, kind_), 0) + 1
        labels[a] = f'{cur}_{kind_}{counts[(cur, kind_)]}'
    ref = lambda tgt, rel: f'@{labels[tgt]}' if tgt in emitted else f'={rel}'
    hdr_lines = []
    for i, e in enumerate(entries):
        hdr_lines.append(f'.script {labels[e]}' if e in emitted else f'.script_raw {e - (4 * i + 4)}')
    out = hdr_lines + (['.header_end'] if has_term else ['.no_header_end'])
    for a, kind in items:
        if a in emitted:
            out.append(f'{labels[a]}:')
        if kind == 'insn':
            cmd, vals, size = insns[a]
            args, q = [], a + 2
            pn = defs[cmd][3]
            for k, ((t, s, br), v) in enumerate(zip(defs[cmd][1], vals)):
                q += s
                if isinstance(v, tuple):
                    args.append(ref(v[1], v[1] - q))
                else:
                    args.append(sym.fmt(pn[k] if k < len(pn) else '', t, v) if sym else str(v))
            line = f'    {defs[cmd][0]}' + (' ' + ', '.join(args) if args else '')
            note = sym.comment(pn, vals) if sym else None
            out.append(line + (f'  ; {note}' if note else ''))
        elif kind == 'move':
            code, cnt = moves[a]
            out.append(f'    .move 0x{code:X}, {cnt}')
        else:
            chunk = data[a:kind[1]]
            if len(chunk) % 2 == 0:
                out += [f'    .hword 0x{struct.unpack_from("<H", chunk, k)[0]:04X}' for k in range(0, len(chunk), 2)]
            else:
                out += [f'    .byte 0x{x:02X}' for x in chunk]
    if n in emitted:
        out.append(f'{labels[n]}:')
    stats = dict(size=n, entries=len(entries), code=sum(v[2] for v in insns.values()),
                 move=4 * len(moves), raw=n - hdr_end - sum(v[2] for v in insns.values()) - 4 * len(moves))
    return '\n'.join(out) + '\n', stats


def assemble(text, defs, sym=None):
    by_name = {v[0]: (k, v[1], v[2]) for k, v in defs.items()}
    lines = [l.split(';', 1)[0].strip() for l in text.split('\n')]
    lines = [l for l in lines if l]
    scripts = [(l.split()[0], l.split()[1]) for l in lines if l.startswith('.script')]
    term = '.header_end' in lines
    body = [l for l in lines if not l.startswith('.script') and l not in ('.header_end', '.no_header_end')]
    hdr = 4 * len(scripts) + (2 if term else 0)
    # pass 1: addresses
    addr, labels = hdr, {}
    sizes = []
    for l in body:
        if l.endswith(':'):
            labels[l[:-1]] = addr
            sizes.append(0)
            continue
        op = l.split(None, 1)[0]
        if op == '.hword':
            s = 2 * (l.count(',') + 1)
        elif op == '.byte':
            s = l.count(',') + 1
        elif op == '.move':
            s = 4
        else:
            s = 2 + sum(sz for _, sz, _ in by_name[op][1])
        sizes.append(s)
        addr += s
    out = bytearray()
    for i, (kind, sname) in enumerate(scripts):
        out += struct.pack('<i', int(sname) if kind == '.script_raw' else labels[sname] - (4 * i + 4))
    if term:
        out += struct.pack('<H', HEADER_END)
    for l, s in zip(body, sizes):
        if l.endswith(':'):
            continue
        parts = l.split(None, 1)
        op, rest = parts[0], (parts[1] if len(parts) > 1 else '')
        args = [x.strip() for x in rest.split(',')] if rest else []
        if op == '.hword':
            out += b''.join(struct.pack('<H', int(a, 0)) for a in args)
        elif op == '.byte':
            out += bytes(int(a, 0) for a in args)
        elif op == '.move':
            out += struct.pack('<HH', int(args[0], 0), int(args[1], 0))
        else:
            cmd, ps, _ = by_name[op]
            out += struct.pack('<H', cmd)
            for (t, sz, br), v in zip(ps, args):
                if v.startswith('@'):
                    end = len(out) + sz
                    out += struct.pack('<i', labels[v[1:]] - end)
                elif v.startswith('='):
                    out += struct.pack('<i', int(v[1:]))
                else:
                    iv = sym.parse(v) if sym else None
                    iv = int(v, 0) if iv is None else iv
                    out += iv.to_bytes(sz, 'little', signed=t in ('int', 'fx32', 'fx16') and iv < 0)
    return bytes(out)
