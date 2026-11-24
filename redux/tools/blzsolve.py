"""Decode a BLZ stream that has holes (stream bytes we could not recover), filling each hole with the
value that best reproduces an expected output (vanilla, aligned to the Redux layout).

Holes are bytes Redux copied from parts of the vanilla ROM we cannot rebuild. They are usually short
(4-8 bytes), so a local search per hole is enough:
  literal byte   -> the expected output byte
  token bytes    -> the (len, disp) whose copy matches the expected output longest (respecting any
                    known half of the token)
  flag byte      -> the value whose next 8 tokens (holes inside resolved the same way) match best
Every inferred byte is reported, so changes that depend on a guess can be flagged.
"""
import struct


class Solver:
    def __init__(self, buf, known, expected, exp_ok):
        self.buf = bytearray(buf)
        self.known = bytearray(known)       # 1 = byte is real Redux data or an exact fill
        self.exp = expected                 # expected decompressed bytes (same length as output)
        self.exp_ok = exp_ok                # 1 where expected is meaningful
        n = len(buf)
        bt, inc = struct.unpack('<II', bytes(self.buf[-8:]))
        self.enc, self.hl, self.inc = bt & 0xFFFFFF, bt >> 24, inc
        self.lim = n - self.enc
        self.inferred = []

    # -- helpers ---------------------------------------------------------------------------------
    def _score_copy(self, out, dst, disp, ln):
        s = 0
        for k in range(1, ln + 1):
            d = dst - k
            if d < 0:
                break
            v = out[d + disp] if d + disp < len(out) else None
            if v is None:
                return -1
            if self.exp_ok[d]:
                if v != self.exp[d]:
                    return s
                s += 1
        return s

    def _best_token(self, out, dst, hi_known, lo_known, hi, lo):
        best = None
        for ln in range(18, 2, -1):
            if hi_known and (hi >> 4) != ln - 3:
                continue
            for disp in range(3, 0x1003):
                v = ((ln - 3) << 12) | (disp - 3)
                if hi_known and (v >> 8) != hi:
                    continue
                if lo_known and (v & 0xFF) != lo:
                    continue
                if dst + disp - 1 >= len(out):
                    break
                sc = self._score_copy(out, dst, disp, ln)
                if sc == ln or (best is None or sc > best[0]):
                    if best is None or sc > best[0]:
                        best = (sc, ln, disp)
                    if sc == ln:
                        return ln, disp
        return (best[1], best[2]) if best else (3, 3)

    def _token(self, out, src, dst, commit):
        """Decode one token at stream position src (pointing past it). Returns (src, dst, score)."""
        flagbit = self._cur_bit
        if flagbit:
            src -= 2
            lo_k, hi_k = self.known[src], self.known[src + 1]
            if not (lo_k and hi_k):
                ln, disp = self._best_token(out, dst, hi_k, lo_k, self.buf[src + 1], self.buf[src])
                v = ((ln - 3) << 12) | (disp - 3)
                if commit:
                    for q, b in ((src, v & 0xFF), (src + 1, v >> 8)):
                        if not self.known[q]:
                            self.buf[q] = b
                            self.known[q] = 1
                            self.inferred.append(q)
            v = self.buf[src] | self.buf[src + 1] << 8 if (lo_k and hi_k) or commit else v
            disp, ln = (v & 0xFFF) + 3, (v >> 12) + 3
            sc = 0
            for _ in range(ln):
                if dst <= 0:
                    break
                dst -= 1
                b = out[dst + disp] if dst + disp < len(out) else 0
                out[dst] = b
                if self.exp_ok[dst]:
                    sc += 1 if b == self.exp[dst] else -1
            return src, dst, sc
        src -= 1
        if dst <= 0:
            return src, dst, 0
        dst -= 1
        if not self.known[src]:
            b = self.exp[dst] if self.exp_ok[dst] else 0
            if commit:
                self.buf[src] = b
                self.known[src] = 1
                self.inferred.append(src)
        else:
            b = self.buf[src]
        out[dst] = b
        return src, dst, (1 if self.exp_ok[dst] and b == self.exp[dst] else 0)

    def _group(self, out, src, dst, flags, commit):
        total = 0
        for _ in range(8):
            if src <= self.lim:
                break
            self._cur_bit = flags & 0x80
            src, dst, sc = self._token(out, src, dst, commit)
            total += sc
            flags = (flags << 1) & 0xFF
        return src, dst, total

    def decode(self):
        n = len(self.buf)
        out = bytearray(self.buf + bytes(self.inc))
        src, dst = n - self.hl, len(out)
        while src > self.lim:
            src -= 1
            if not self.known[src]:
                best = None
                for f in range(256):
                    trial = bytearray(out)
                    saved = (bytearray(self.buf), bytearray(self.known), len(self.inferred))
                    _, _, sc = self._group(trial, src, dst, f, commit=False)
                    self.buf, self.known = saved[0], saved[1]
                    del self.inferred[saved[2]:]
                    if best is None or sc > best[0]:
                        best = (sc, f)
                self.buf[src] = best[1]
                self.known[src] = 1
                self.inferred.append(src)
            src, dst, _ = self._group(out, src, dst, self.buf[src], commit=True)
        return bytes(out), self.inferred
