"""ReRedux title logo: the "REDUX" badge under "BLAZE BLACK 2" on the title screen reads "REREDUX" (EN and JP: both
ROMs use Redux's English logo).

The logo is the title screen's top BG (a/0/2/6: NCGR 0, 8 bpp, LZ10; tile map NSCR 1; palette NCLR 2). The badge (map
pixels x 181-239, y 137-149: dark outline, grey / white frame, a blue plate with a left-to-right gradient and five
white letters) is widened by WIDEN pixels to the right (there is free space below the "2"'s lightning; the "K" of
BLACK is right of its left edge): its right end moves, the plate and frame rows between are stretched (gradient
kept), and Redux's own letter glyphs R, E, D, U, X are set again as R E R E D U X, evenly spaced. The changed 8x8
cells get new tiles (free slots of the NCGR) or are overwritten when used only there. No code."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))

TITLE_ARC, LOGO_NCGR, LOGO_NSCR, LOGO_NCLR = 'a/0/2/6', 0, 1, 2
X0, X1, Y0, Y1 = 181, 239, 137, 149     # the badge (inclusive), map pixels
PLATE_X0, PLATE_X1 = 184, 236           # the blue plate's columns
LETTER_Y0, LETTER_Y1 = 140, 146         # rows that hold the letters (the plate rows)
WIDEN = 14
WORD = 'REREDUX'


def _lum(c):
    return (c[0] + c[1] + c[2]) / 3


def badge(ctx, report=None):
    import ndsfs, gfx5
    fid = ctx.fid(TITLE_ARC)
    raw = ctx.rom.file(fid)
    narc = ndsfs.narc(raw)
    gd, glz = gfx5.unpack(narc[LOGO_NCGR])
    sd, slz = gfx5.unpack(narc[LOGO_NSCR])
    g, s = gfx5.NCGR(gd), gfx5.NSCR(sd)
    pal = gfx5.nclr(narc[LOGO_NCLR])
    assert g.bpp == 8 and s.w == 256, 'logo: unexpected title graphics'
    # the logo as pixels (palette indices), tile cols 16-31, rows 15-20
    TX0, TX1, TY0, TY1 = 16, 32, 15, 21
    W, H = (TX1 - TX0) * 8, (TY1 - TY0) * 8
    img = [[0] * W for _ in range(H)]
    for ty in range(TY0, TY1):
        for tx in range(TX0, TX1):
            px = gfx5.tile_px(g, s.at(tx, ty))
            for y in range(8):
                for x in range(8):
                    img[(ty - TY0) * 8 + y][(tx - TX0) * 8 + x] = px[y][x]

    def P(x, y):
        return img[y - TY0 * 8][x - TX0 * 8]

    # sanity: dark outline at the badge's left / right columns, transparent right of it (room to widen)
    dark = lambda x, y: P(x, y) and _lum(pal[P(x, y)]) < 125
    assert all(dark(X0 + 1, y) for y in range(Y0 + 1, Y1)) and all(dark(X1, y) for y in range(Y0 + 1, Y1)), \
        'logo: badge not where expected'
    assert all(P(x, y) == 0 for x in range(X1 + 2, X1 + WIDEN + 2) for y in range(Y0 + 1, Y1 + 1)), \
        'logo: no room right of the badge'
    # plate background colours (the letter-free rows), and the letters as column runs
    bg = {P(x, y) for x in range(PLATE_X0, PLATE_X1 + 1) for y in (LETTER_Y0, LETTER_Y1)}
    cols = [x for x in range(PLATE_X0, PLATE_X1 + 1)
            if any(P(x, y) not in bg for y in range(LETTER_Y0, LETTER_Y1 + 1))]
    runs = []
    for x in cols:
        if runs and x == runs[-1][1] + 1:
            runs[-1][1] = x
        else:
            runs.append([x, x])
    assert len(runs) == 5, f'logo: expected the 5 letters of REDUX, found column runs {runs}'
    glyph = {}
    for ch, (a, b) in zip('REDUX', runs):
        glyph[ch] = [[P(x, y) if P(x, y) not in bg else None for x in range(a, b + 1)]
                     for y in range(LETTER_Y0, LETTER_Y1 + 1)]
    # new badge: rows Y0..Y1, columns X0..X1+WIDEN
    nx1 = X1 + WIDEN
    nplate1 = PLATE_X1 + WIDEN
    new = {}
    for y in range(Y0, Y1 + 1):
        for x in range(X0, nx1 + 2):
            if x < PLATE_X0:
                v = P(x, y)                                   # left frame as it was
            elif x <= nplate1:                                # plate / frame rows: stretched
                ox = PLATE_X0 + round((x - PLATE_X0) * (PLATE_X1 - PLATE_X0) / (nplate1 - PLATE_X0))
                v = P(ox, y)
                if LETTER_Y0 <= y <= LETTER_Y1 and v not in bg:   # no old letter pixels: nearest plate pixel
                    near = min((c for c in range(PLATE_X0, PLATE_X1 + 1) if P(c, y) in bg), key=lambda c: abs(c - ox))
                    v = P(near, y)
            else:
                v = P(x - WIDEN, y)                           # right frame and outline, moved
            new[x, y] = v
    # the stretch must not leave the "2" (rows above the plate, left part) changed: keep those rows' original
    # pixels where the logo's "2" overlaps the badge's top outline (row Y0), only extend its dark run
    for x in range(X0, nx1 + 2):
        if x <= X1:
            new[x, Y0] = P(x, Y0)
        else:
            new[x, Y0] = P(X1, Y0) if x <= nx1 else P(X1 + 1, Y0)
    # letters: R E R E D U X, same left margin as REDUX, evenly spaced up to the same right margin
    # spacing by each glyph's solid (bright) columns, so the faint anti-aliased edges don't skew it
    def solid(c):
        cs = [xx for xx in range(len(glyph[c][0]))
              if any(row[xx] is not None and _lum(pal[row[xx]]) >= 170 for row in glyph[c])]
        return cs[0], cs[-1]
    sol = {c: solid(c) for c in 'REDUX'}
    old_gaps = [(runs[k + 1][0] + sol['REDUX'[k + 1]][0]) - (runs[k][0] + sol['REDUX'[k]][1]) - 1 for k in range(4)]
    left = runs[0][0] + sol['R'][0]                      # first solid column, as in REDUX
    right = runs[-1][0] + sol['X'][1] + WIDEN            # last solid column, moved with the frame
    swidths = [sol[c][1] - sol[c][0] + 1 for c in WORD]
    space = right - left + 1 - sum(swidths)
    n = len(WORD) - 1
    r = space % n                                        # the extra pixels spread evenly, not all at the front
    extra = {int((j + 0.5) * n / r) for j in range(r)} if r else set()
    gaps = [space // n + (1 if k in extra else 0) for k in range(n)]
    x = left
    placed = []
    for k, c in enumerate(WORD):
        x0 = x - sol[c][0]
        for yy, row in enumerate(glyph[c]):
            for xx, v in enumerate(row):
                if v is not None:
                    new[x0 + xx, LETTER_Y0 + yy] = v
        placed.append((c, x, x + swidths[k] - 1))
        x += swidths[k] + (gaps[k] if k < n else 0)
    if report is not None:
        report.update(old_gaps=old_gaps, gaps=gaps)
    for (x, y), v in new.items():
        img[y - TY0 * 8][x - TX0 * 8] = v
    # retile the changed cells
    refs = {}
    for i, m in enumerate(narc):
        d, _ = gfx5.unpack(m)
        if d[:4] == b'RCSN':
            for k, e in enumerate(gfx5.NSCR(d).m):
                refs.setdefault(e & 0x3FF, []).append((i, k))
    free = [t for t in range(1, g.ntiles()) if t not in refs and not any(g.data[t * 64:t * 64 + 64])]
    changed, fresh = 0, 0
    for ty in range(Y0 // 8, Y1 // 8 + 1):
        for tx in range(X0 // 8, (nx1 + 1) // 8 + 1):
            e = s.at(tx, ty)
            cell = [img[(ty - TY0) * 8 + y][(tx - TX0) * 8:(tx - TX0) * 8 + 8] for y in range(8)]
            if cell == gfx5.tile_px(g, e):
                continue
            t = e & 0x3FF
            if t == 0 or len(refs.get(t, ())) > 1:
                if not free:
                    raise ValueError('logo: no free tiles left in the title NCGR')
                t = free.pop(0)
                fresh += 1
            g.set_tile(t, cell)
            s.put(tx, ty, (e & 0xF000) | t)
            changed += 1
    narc[LOGO_NCGR] = gfx5.pack(g.encode(), glz)
    narc[LOGO_NSCR] = gfx5.pack(s.encode(), slz)
    print(f'logo: badge {X0}-{nx1} x {Y0}-{Y1} reads {WORD} ({", ".join(f"{c} {a}-{b}" for c, a, b in placed)}); '
          f'{changed} cells retiled, {fresh} new tiles ({len(free)} free left)')
    if report is not None:
        report.update(img=img, origin=(TX0 * 8, TY0 * 8), pal=pal)
    return {fid: ndsfs.pack_narc(narc, ndsfs.narc_layout(raw))}


def files(ctx):
    return badge(ctx)
