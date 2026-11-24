"""Gen 5 (B/W, B2/W2) message bank codec, lossless (decode -> text -> encode is byte-exact).

Bank layout: u16 sections, u16 entries, u32 section size, u32 0, u32 section offsets[sections];
each section: u32 size, per entry (u32 offset from section start, u16 length in chars, u16 flags),
then string data. String e is u16 chars XOR-encrypted: key = 0x7C89 + e * 0x2983 for the first
char, rotated left 3 bits per char. Strings end with 0xFFFF.

Text format, one entry per line:
  \\n           0xFFFE line break
  {BE01}       control code 0xF000 with type BE01 and no args;  {0101:3,0}  with args
  {U+XXXX}     any other raw u16 the game uses (and characters that are not printable)
  {{  \\\\       literal '{' and backslash
A line `@flags=N` before an entry sets its u16 flags; `--- section N` separates sections.
"""
import re, struct

KEY0, KEYSTEP = 0x7C89, 0x2983
rotl = lambda k: ((k << 3) | (k >> 13)) & 0xFFFF
rotr = lambda k: ((k >> 3) | (k << 13)) & 0xFFFF


def _crypt(chars, e):
    key = (KEY0 + e * KEYSTEP) & 0xFFFF
    out = []
    for c in chars:
        out.append(c ^ key)
        key = rotl(key)
    return out


def chars_to_text(chars):
    s, i = [], 0
    n = len(chars)
    if n and chars[-1] == 0xFFFF:
        n -= 1
    else:
        s.append('{NOEND}')   # keep the rare unterminated string lossless
    while i < n:
        c = chars[i]
        if c == 0xFFFE:
            s.append('\\n')
        elif c == 0xF000 and i + 2 < n and i + 3 + chars[i + 2] <= n:
            typ, argc = chars[i + 1], chars[i + 2]
            args = chars[i + 3:i + 3 + argc]
            s.append('{' + f'{typ:04X}' + (':' + ','.join(map(str, args)) if argc else '') + '}')
            i += 3 + argc
            continue
        elif c == ord('{'):
            s.append('{{')
        elif c == ord('\\'):
            s.append('\\\\')
        elif c < 0x20 or 0xD800 <= c < 0xE000 or c >= 0xE000:
            s.append(f'{{U+{c:04X}}}')
        else:
            s.append(chr(c))
        i += 1
    return ''.join(s)


TOKEN = re.compile(r'\{\{|\\\\|\\n|\{NOEND\}|\{U\+([0-9A-F]{4})\}|\{([0-9A-F]{4})(?::([0-9,]*))?\}|.', re.S)


def text_to_chars(text):
    out, end = [], True
    for m in TOKEN.finditer(text):
        t = m.group(0)
        if t == '{{':
            out.append(ord('{'))
        elif t == '\\\\':
            out.append(ord('\\'))
        elif t == '\\n':
            out.append(0xFFFE)
        elif t == '{NOEND}':
            end = False
        elif m.group(1):
            out.append(int(m.group(1), 16))
        elif m.group(2):
            args = [int(a) for a in m.group(3).split(',')] if m.group(3) else []
            out += [0xF000, int(m.group(2), 16), len(args)] + args
        else:
            out.append(ord(t))
    return out + ([0xFFFF] if end else [])


def padding(data):
    """The (non-zero, game-specific) bytes padding the last section to 4 bytes."""
    sections, entries = struct.unpack('<HH', data[:4])
    so = struct.unpack('<I', data[12 + 4 * (sections - 1):16 + 4 * (sections - 1)])[0]
    if not entries:
        return None
    off, ln, _ = struct.unpack('<IHH', data[so + 4 + 8 * (entries - 1):so + 12 + 8 * (entries - 1)])
    end = so + off + 2 * ln
    size = struct.unpack('<I', data[so:so + 4])[0]
    if (end - so) % 4 == 0:
        return None            # no padding needed
    return bytes(data[end:so + size])   # b'' when the section was left unaligned


def decode(data):
    """-> list of sections, each a list of (text, flags)."""
    sections, entries, _, _ = struct.unpack('<HHII', data[:12])
    offs = struct.unpack(f'<{sections}I', data[12:12 + 4 * sections])
    out = []
    for so in offs:
        sec = []
        for e in range(entries):
            off, ln, flags = struct.unpack('<IHH', data[so + 4 + 8 * e:so + 12 + 8 * e])
            enc = list(struct.unpack(f'<{ln}H', data[so + off:so + off + 2 * ln]))
            sec.append((chars_to_text(_crypt(enc, e)), flags))
        out.append(sec)
    return out


def encode(sections, unk=0, pad=None):
    """pad: bytes padding the section end to 4 (None = zeros; b'' = leave unaligned)."""
    entries = len(sections[0]) if sections else 0
    blobs = []
    for sec in sections:
        table, body = b'', b''
        base = 4 + 8 * entries
        for e, (text, flags) in enumerate(sec):
            chars = _crypt(text_to_chars(text), e)
            table += struct.pack('<IHH', base + len(body), len(chars), flags)
            body += struct.pack(f'<{len(chars)}H', *chars)
        if len(body) % 4:                     # sections are padded to 4 bytes at the end
            need = 4 - len(body) % 4
            body += b'\x00' * need if pad is None else pad[:need]
        size = 4 + len(table) + len(body)
        blobs.append(struct.pack('<I', size) + table + body)
    head = 12 + 4 * len(sections)
    offs, p = [], head
    for b in blobs:
        offs.append(p)
        p += len(b)
    hdr = struct.pack('<HHII', len(sections), entries, sum(len(b) for b in blobs), unk)
    return hdr + struct.pack(f'<{len(sections)}I', *offs) + b''.join(blobs)


def to_file(sections, pad=None):
    """pad: None or zeros -> default; otherwise recorded as @pad=hex (empty = unaligned)."""
    lines = [] if pad is None or (pad and not pad.strip(b'\x00')) else [f'@pad={pad.hex()}']
    for si, sec in enumerate(sections):
        if len(sections) > 1:
            lines.append(f'--- section {si}')
        for text, flags in sec:
            if flags:
                lines.append(f'@flags={flags}')
            lines.append(text)
    return '\n'.join(lines) + '\n' if lines else ''


def from_file(s):
    """-> (sections, pad)"""
    sections, cur, flags, pad = [], [], 0, None
    for line in s.split('\n')[:-1]:
        if line.startswith('@pad=') and not cur and not sections:
            pad = bytes.fromhex(line[5:])
            continue
        if line.startswith('--- section '):
            if cur or sections:
                sections.append(cur)
            cur = []
            continue
        if line.startswith('@flags='):
            flags = int(line[7:])
            continue
        cur.append((line, flags))
        flags = 0
    sections.append(cur)
    return sections, pad
