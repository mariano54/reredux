/* blz.c - Nintendo DS "bottom LZ" (BLZ) codec for arm9/overlay modules.
 *
 *   blz -d in out     decompress
 *   blz -e in out [start]   compress; bytes before start (e.g. 0x4000 for arm9) stay raw
 *
 * Format: the file is [raw head][LZ stream][pad 0xFF to 4][u32 enc_len | hdr_len<<24][u32 inc_len].
 * The stream is read backwards from the end; each flag byte (MSB first) selects literal or a
 * (len-3, disp-3) pair stored big-endian as 4-bit len | 12-bit disp.
 *
 * Encoder: greedy, scanning from the end of the data; longest match with displacement 3..0x1002
 * and length 3..18, no overlap (len <= disp). The raw head is chosen afterwards from the running
 * savings. Environment knobs (for experiments; defaults are the Nintendo-matching choice):
 *   BLZ_TIE=near|far     equal-length matches: nearest (default) or farthest displacement
 *   BLZ_HEAD=first|max   raw-head rule: first token whose running savings exceed the final total
 *                        (default, as AetiasHax/ds-rom), or the earliest maximum (CUE's blz -en)
 *   BLZ_N=0x1002         maximum displacement
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAXLEN 18
#define MINLEN 3

static uint8_t *readall(const char *p, size_t *n) {
    FILE *f = fopen(p, "rb");
    if (!f) { perror(p); exit(1); }
    fseek(f, 0, SEEK_END); *n = ftell(f); fseek(f, 0, SEEK_SET);
    uint8_t *b = malloc(*n + 16);
    if (fread(b, 1, *n, f) != *n) { perror("read"); exit(1); }
    fclose(f);
    return b;
}

static void writeall(const char *p, const uint8_t *b, size_t n) {
    FILE *f = fopen(p, "wb");
    if (!f || fwrite(b, 1, n, f) != n) { perror(p); exit(1); }
    fclose(f);
}

static int decode(const uint8_t *in, size_t n, uint8_t **out, size_t *on) {
    if (n < 8) return -1;
    uint32_t bt = in[n-8] | in[n-7] << 8 | in[n-6] << 16 | (uint32_t)in[n-5] << 24;
    uint32_t inc = in[n-4] | in[n-3] << 8 | in[n-2] << 16 | (uint32_t)in[n-1] << 24;
    uint32_t enc = bt & 0xFFFFFF, hdr = bt >> 24;
    if (enc > n || hdr > enc) return -1;
    *on = n + inc;
    uint8_t *o = malloc(*on);
    memcpy(o, in, n);
    long src = (long)n - hdr, dst = (long)*on, lim = (long)n - enc;
    while (src > lim) {
        uint8_t flags = in[--src];
        for (int b = 0; b < 8 && src > lim; b++, flags <<= 1) {
            if (flags & 0x80) {
                if (src - 2 < lim) return -2;
                src -= 2;
                int v = in[src] | in[src + 1] << 8;
                int disp = (v & 0xFFF) + 3, len = (v >> 12) + 3;
                if (dst - len < lim || dst + disp - 1 >= (long)*on) return -3;
                while (len--) { dst--; o[dst] = o[dst + disp]; }
            } else {
                if (dst - 1 < 0) return -4;
                o[--dst] = in[--src];
            }
        }
    }
    *out = o;
    return 0;
}

typedef struct { uint16_t len, disp; } Tok;   /* len 0 = literal */

static uint8_t *encode(const uint8_t *in, size_t n, size_t *pn, long start) {
    const char *e;
    int far = (e = getenv("BLZ_TIE")) && !strcmp(e, "far");
    int headmax = (e = getenv("BLZ_HEAD")) && !strcmp(e, "max");
    long maxd = (e = getenv("BLZ_N")) ? strtol(e, 0, 0) : 0x1002;

    Tok *tok = malloc(sizeof(Tok) * (n + 1));
    long *pos = malloc(sizeof(long) * (n + 1));   /* data index just past each token (its top) */
    size_t nt = 0;
    long r = (long)n;                              /* bytes [r, n) are encoded */
    while (r > start) {
        long p = r - 1, best = 0, bestd = 0;
        for (long d = MINLEN; d <= maxd && p + d < (long)n; d++) {
            if (in[p] != in[p + d]) continue;
            long l = 0;
            while (l < MAXLEN && l < d && p - l >= start && in[p - l] == in[p + d - l]) l++;
            if (l > best || (far && l == best && l >= MINLEN)) { best = l; bestd = d; }
        }
        pos[nt] = r;
        if (best >= MINLEN) { tok[nt].len = best; tok[nt].disp = bestd; r -= best; }
        else { tok[nt].len = 0; tok[nt].disp = 0; r -= 1; }
        nt++;
    }
    /* running savings: a flag byte costs 1 per 8 tokens, a pair saves len - 2 */
    long *sav = malloc(sizeof(long) * (nt + 1));
    long s = 0;
    for (size_t i = 0; i < nt; i++) {
        if (i % 8 == 0) s--;
        if (tok[i].len) s += tok[i].len - 2;
        sav[i] = s;
    }
    long total = s;
    size_t keep = nt;   /* tokens [0, keep) go in the stream */
    if (headmax) {
        long bs = 0; keep = 0;
        for (size_t i = 0; i < nt; i++) if (sav[i] > bs) { bs = sav[i]; keep = i + 1; }
    } else {
        for (size_t i = 0; i < nt; i++) if (sav[i] > total) { keep = i + 1; break; }
    }
    long saved = keep ? sav[keep - 1] : 0;
    if (keep == 0 || saved <= 0) {     /* nothing to gain: store as is */
        uint8_t *out = malloc(n); memcpy(out, in, n); *pn = n; free(tok); free(pos); free(sav); return out;
    }
    size_t raw = pos[keep - 1] - (tok[keep - 1].len ? tok[keep - 1].len : 1);
    /* stream bytes in decode order (backwards from the top), then reversed into the file */
    uint8_t *st = malloc(n + nt / 8 + 16);
    size_t q = 0;
    for (size_t g = 0; g < keep; g += 8) {
        uint8_t fl = 0;
        for (size_t k = 0; k < 8; k++) {
            fl <<= 1;
            if (g + k < nt && tok[g + k].len) fl |= 1;
        }
        st[q++] = fl;
        for (size_t k = 0; k < 8 && g + k < keep; k++) {
            Tok t = tok[g + k];
            if (t.len) {
                uint16_t v = (uint16_t)((t.len - 3) << 12 | (t.disp - 3));
                st[q++] = v >> 8; st[q++] = v & 0xFF;
            } else {
                st[q++] = in[pos[g + k] - 1];
            }
        }
    }
    size_t pad = (4 - ((raw + q) & 3)) & 3;
    size_t out_len = raw + q + pad + 8;
    if (out_len >= n) {                /* compression would not shrink it: store as is */
        uint8_t *out = malloc(n); memcpy(out, in, n); *pn = n;
        free(tok); free(pos); free(sav); free(st); return out;
    }
    uint8_t *out = malloc(out_len);
    memcpy(out, in, raw);
    for (size_t i = 0; i < q; i++) out[raw + q - 1 - i] = st[i];
    memset(out + raw + q, 0xFF, pad);
    uint32_t hdr = pad + 8, enc_len = q + hdr, inc = n - out_len;
    uint32_t bt = enc_len | hdr << 24;
    uint8_t *ft = out + out_len - 8;
    for (int i = 0; i < 4; i++) { ft[i] = bt >> (8 * i); ft[4 + i] = inc >> (8 * i); }
    *pn = out_len;
    free(tok); free(pos); free(sav); free(st);
    return out;
}

int main(int argc, char **argv) {
    if (argc != 4 && !(argc == 5 && !strcmp(argv[1], "-e"))) { fprintf(stderr, "usage: blz -d|-e in out [start]\n"); return 2; }
    size_t n, on;
    uint8_t *in = readall(argv[2], &n), *out;
    if (!strcmp(argv[1], "-d")) {
        int e = decode(in, n, &out, &on);
        if (e) { fprintf(stderr, "decode error %d\n", e); return 1; }
    } else {
        out = encode(in, n, &on, argc == 5 ? strtol(argv[4], 0, 0) : 0);
    }
    writeall(argv[3], out, on);
    return 0;
}
