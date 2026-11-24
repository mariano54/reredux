"""diag_decode.py N [shift]: fill overlay N from the vanilla model, decode, and report the first
stream position where output desyncs from vanilla (>= 32 consecutive mismatches) plus provenance."""
import sys, struct
import redux_rom as R, overlays as O
n = int(sys.argv[1]); shift = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0
rom = R.ReduxRom(); fat = rom.fat(); M = O.VanillaModel(rom, fat)
name, s, e = fat[n]; van = R.Vanilla(f'overlay_{n}')
data = rom.read(s, e - s); m = rom.mask(s, e - s)
unknown = [p for p in range(len(data)) if not m[p]]
srcs = {p: S for p in unknown if (S := rom.source_offset(s + p)) is not None}
buf, f, u = O.fill_model(data, unknown, srcs, M)
exp = bytes(shift) + van.data
L = len(buf); bt, inc = struct.unpack('<II', buf[-8:]); enc, hl = bt & 0xFFFFFF, bt >> 24
out = bytearray(buf + bytes(inc)); src, dst, lim = L - hl, len(out), L - enc
streak = 0; tokpos = []
while src > lim:
    src -= 1; fl = buf[src]; fpos = src
    for _ in range(8):
        if src <= lim: break
        if fl & 0x80:
            src -= 2; v = buf[src] | buf[src + 1] << 8; disp, ln = (v & 0xFFF) + 3, (v >> 12) + 3
            for _ in range(ln):
                if dst <= 0: break
                dst -= 1; out[dst] = out[dst + disp] if dst + disp < len(out) else 0
        else:
            src -= 1; dst -= 1; out[dst] = buf[src]
        tokpos.append((src, fpos, dst))
        streak = streak + 1 if dst < len(exp) and out[dst] != exp[dst] else 0
        if streak >= 32: break
        fl = (fl << 1) & 0xFF
    if streak >= 32: break
p = tokpos[-32][0]
print(f'desync near stream {p} (dst {tokpos[-32][2]:#x}); filled={f} unfilled={u}')
piece = lambda S: next((hex(a) for a, d in reversed(M.pieces) if a <= S < a + len(d)), None)
for q in range(p - 24, p + 8):
    S = srcs.get(q)
    print(q, 'known' if m[q] else 'copy', hex(buf[q]), '' if S is None else f'src {S:#x} piece {piece(S)}')
