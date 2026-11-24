#!/usr/bin/env python3
"""Add following Pokémon (redux/followers/) to a Black 2 USA/EU ROM (vanilla or Redux-based).

  build_followers.py IN.nds OUT.nds [--essentials DIR]

Run with a python that has Pillow when --essentials is given (sprite conversion).

1. Compiles followers/follow.c (arm-none-eabi-gcc, Thumb) linked at the end of the game's ITCM block,
   with the species -> overworld sprite table from the ROM's own a/2/0/8 embedded.
2. Grows arm9's ITCM autoload block by the code size (ITCM is 32 KiB, the game uses 0x13A0 bytes),
   shifts the autoload list after it, and moves the SDK's ITCM arena start past the new code.
3. Patches overlay 36's FieldRoutine_Run to call the follower hook once per field frame, and points
   the warp / Fly / Sweet Scent GameEvents of overlays 12, 33 and 35 at the follower's wrappers
   (EVENT_HOOKS), storing those overlays uncompressed.
4. With --essentials DIR (a folder of Pokémon Essentials follower sheets, DIR/normal/NAME.png),
   converts sheets for every species #1-649 the game has no field sprite for (103 Gen 5 species
   plus their forms/female variants) into new a/0/4/8 textures and a/0/4/7 registry entries with
   obj codes from 0x126C, and moves the two arm9 constants that map obj codes to registry indices.
5. Rebuilds the ROM with romtool (FAT/header re-layout).

As a library: build(src, dst, essentials=, hgss=, talk_lines=, names_rom=) does the same as the CLI
(tools/build_redux3.py uses it); follower_patch_ranges() lists the bytes it changes.
"""
import argparse, json, os, re, struct, subprocess, sys
import gen5text, ndsfs, romtool
import follower_ballfx, follower_emotes, follower_talk

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', 'followers')
BUILD = os.path.join(HERE, '..', 'build', 'followers')
BLZ = os.path.join(HERE, '..', 'build', 'bin', 'blz')

ITCM_BASE = 0x01FF8000
ITCM_END_VANILLA = 0x01FF93A0
ITCM_LIMIT = 0x02000000
ITCM_RESERVE = 0x6000              # fixed size, so code changes never move the ROM layout
ARENA_LO_LITERAL = 0x0207B400      # OS_GetInitArenaLo: `.word 0x01FF93A0` (ITCM arena start)
HOOK_SITE = 0x0217FFAC             # OVL_36 FieldRoutine_Run: bl 0x02180B00
HOOK_ORIG = 0x02180B00
OV36_RAM = 0x0217F600
OV12_RAM = 0x021503C0
OV33_RAM = 0x02176B00
OV35_RAM = 0x0217C940
# GameEvent callbacks / creators that wait for the follower (follow.c follow_ev_*): literal-pool
# words (or table entries) holding the vanilla function -> our wrapper
EVENT_HOOKS = [
    (35, [0x0217DB98, 0x0217DBF8, 0x0217E174], 0x0217D2D9, 'follow_ev_warp'),  # EventMapChangeWarp_Create*
    (35, [0x0217DEBC], 0x0217D931, 'follow_ev_warp_pad'),                   # EventMapChangeWarpPad_Create
    (33, [0x02178960], 0x02178965, 'follow_ev_fly'),                        # FUN_02178908 (EventFly)
    (33, [0x02178610], 0x02178615, 'follow_ev_sweet_scent'),                # EventSweetScent_Create
    (12, [0x0216CAA8, 0x0216CB00], 0x0215966D, 'follow_ev_fly_create'),     # field-move tables, Fly
]
WOFS_HOOK = 0x02196DE4             # OVL_36 billboard update: bl FldAct_SetWPosOffset -> follow_wofs_hook
WOFS_ORIG = 0x0216732C
# OVL_36 field-effect task descriptor of the per-actor ground shadow (OV36_FUN_021A3BF0): work size,
# init, delete, update, draw. Copied into each task when it is created; init / delete -> follow.c
# follow_shadow_init / _delete (they scale the follower's shadow)
SHADOW_TASK_DESC = 0x021D0530
SHADOW_TASK_HOOKS = [(SHADOW_TASK_DESC + 4, 0x021A3C21, 'follow_shadow_init'),
                     (SHADOW_TASK_DESC + 8, 0x021A3CB5, 'follow_shadow_delete')]
SCRIPT_CMD_TABLE = 0x0216B538      # OVL_12: 0x2F3 handlers; NULL entries are unused ids
FOLLOW_SCRIPT_CMD = 0x89           # first free id: talk.s calls the follower code through it
SCRIPT_CMD_PERMS = 0x0216B1F0      # OVL_12: u8 per command, bit n = allowed in script context n

# FUN_0200FE34 (obj code -> a/0/4/7 index): 0x1000 <= obj < 0x126C -> obj - 0xE87;
# 0x2000 <= obj < 0x200B -> obj - 0x1C1B. New Pokémon entries are inserted after 0x126B.
LIT_POKE_END = 0x0200FE74
LIT_3D_OFFSET = 0x0200FE7C
POKE_OBJ_END = 0x126C
POKE_INDEX_OFFSET = 0xE87
TEMPLATE_32 = 0x1000    # Bulbasaur: ctrl 14, 8 x 32x32
TEMPLATE_64 = 0x10EF    # Steelix: ctrl 13, 6 x 64x64 (right = mirrored left)
SPECIES_BANK = 90       # a/0/0/2 species names
ESS_SPECIAL = {29: 'NIDORANfE', 32: 'NIDORANmA'}

SOURCES = ['follow.c', 'talk.c', 'talk_select.c', 'emote.c', 'ballfx.c']
CFLAGS = ['-mthumb', '-march=armv5te', '-mlong-calls', '-Os', '-ffreestanding', '-nostdlib',
          '-fno-builtin', '-ffunction-sections', '-fdata-sections', '-fno-common', '-Wall', '-Werror']


def thumb_bl(src, dst):
    off = dst - (src + 4)
    assert -(1 << 22) <= off < (1 << 22) and not off & 1, hex(off)
    off = (off >> 1) & 0x3FFFFF
    return struct.pack('<HH', 0xF000 | (off >> 11), 0xF800 | (off & 0x7FF))


def decode_bl(code, at):
    hi, lo = struct.unpack_from('<HH', code, at)
    assert hi & 0xF800 == 0xF000 and lo & 0xF800 == 0xF800, 'not a Thumb BL'
    off = ((hi & 0x7FF) << 11) | (lo & 0x7FF)
    if off & 0x200000:
        off -= 0x400000
    return off * 2


def fid_of(rom, path):
    return next(f for f, p in rom.paths.items() if p == path)


def tpoke_rows(rom):
    tab = ndsfs.narc(rom.file(fid_of(rom, 'a/2/0/8')))[0]
    return [struct.unpack_from('<4H', tab, 8 * i) for i in range(len(tab) // 8)]


def tpoke_header(rows):
    n = len(rows)
    rows = [r if len(r) == 5 else r + (r[3],) for r in rows]
    body = ',\n'.join('    %d, %d, %d, 0x%04X, 0x%04X' % r for r in rows)
    return (f'/* generated by build_followers.py from a/2/0/8 (+ added sprites): species, gender (2 = any) | size class << 8\n'
            f'   | hover << 10 | shadow shrink << 11, form, obj code, shiny obj code */\n'
            f'#define TPOKE_COUNT {n}\nstatic const unsigned short tpoke_table[TPOKE_COUNT * 5] = {{\n{body}\n}};\n')


def zone_modes_header():
    """followers/zone_modes.json -> 2 bits per zone (0 PREVENT, 1 HEIGHT_RESTRICT, 2 ALLOW)."""
    import json
    modes = json.load(open(os.path.join(SRC, 'zone_modes.json')))['modes']
    code = {'PREVENT': 0, 'HEIGHT_RESTRICT': 1, 'ALLOW': 2}
    n = max(int(k) for k in modes) + 1
    packed = bytearray((n + 3) // 4)
    for k, v in modes.items():
        z = int(k)
        packed[z // 4] |= code[v] << (2 * (z % 4))
    body = ', '.join(f'0x{b:02X}' for b in packed)
    return (f'/* generated by build_followers.py from followers/zone_modes.json: 2 bits per zone,\n'
            f'   0 PREVENT, 1 HEIGHT_RESTRICT, 2 ALLOW (zones past the end: ALLOW) */\n'
            f'#define ZONE_MODE_COUNT {n}\nstatic const unsigned char zone_mode_bits[] = {{{body}}};\n')


def libgcc():
    """switch tables and division helpers"""
    return subprocess.run(['arm-none-eabi-gcc', '-mthumb', '-march=armv5te', '-print-libgcc-file-name'],
                          capture_output=True, text=True, check=True).stdout.strip()


def compile_code(rows, talk_script, defines=()):
    os.makedirs(BUILD, exist_ok=True)
    open(os.path.join(BUILD, 'tpoke_table.h'), 'w').write(tpoke_header(rows))
    open(os.path.join(BUILD, 'zone_modes.h'), 'w').write(zone_modes_header())
    elf, binf = (os.path.join(BUILD, n) for n in ('follow.elf', 'follow.bin'))
    extra = [f"-DTALK_SCRIPT={talk_script}", *defines]
    for k in ('FOLLOW_DEBUG_SPECIES', 'FOLLOW_DEBUG_FORCE'):   # test builds only
        if os.environ.get(k):
            extra += [f'-D{k}=' + os.environ[k], '-DFOLLOW_DEBUG_SHINY=' + os.environ.get('FOLLOW_DEBUG_SHINY', '0')]
    open(os.path.join(BUILD, 'defines.txt'), 'w').write(' '.join(extra) + '\n')   # for test scripts
    objs = []
    for src in SOURCES:
        objs.append(os.path.join(BUILD, src.replace('.c', '.o')))
        subprocess.run(['arm-none-eabi-gcc', *CFLAGS, *extra, '-I', SRC, '-I', BUILD, '-c',
                        os.path.join(SRC, src), '-o', objs[-1]], check=True)
    subprocess.run(['arm-none-eabi-ld', '-T', os.path.join(SRC, 'itcm.ld'), '-L', SRC, '--gc-sections', '--no-warn-rwx-segments',
                    '-o', elf, *objs, libgcc()], check=True, cwd=SRC)
    subprocess.run(['arm-none-eabi-objcopy', '-O', 'binary', '-j', '.itcm', elf, binf], check=True)
    syms = {}
    for line in subprocess.run(['arm-none-eabi-nm', elf], capture_output=True, text=True, check=True).stdout.splitlines():
        a, t, n = line.split()
        syms[n] = int(a, 16)
    blob = open(binf, 'rb').read()
    assert len(blob) <= ITCM_RESERVE, f'follower code {len(blob):#x} exceeds the ITCM reserve'
    return blob + bytes(ITCM_RESERVE - len(blob)), syms


def patch_arm9(arm9, ram, blob):
    i = arm9.find(struct.pack('<II', 0xDEC00621, 0x2106C0DE))
    p = i - 0x1C
    al, ale, ast = struct.unpack_from('<3I', arm9, p)
    addr, size = struct.unpack_from('<II', arm9, al - ram)
    assert addr == ITCM_BASE and ITCM_BASE + size == ITCM_END_VANILLA, 'unexpected ITCM layout'
    assert len(blob) % 32 == 0 and ITCM_END_VANILLA + len(blob) <= ITCM_LIMIT
    ins = ast - ram + size              # end of the ITCM block's source data
    out = bytearray(arm9[:ins] + blob + arm9[ins:])
    struct.pack_into('<II', out, p, al + len(blob), ale + len(blob))
    struct.pack_into('<I', out, al + len(blob) - ram + 4, size + len(blob))
    lit = ARENA_LO_LITERAL - ram
    assert struct.unpack_from('<I', out, lit)[0] == ITCM_END_VANILLA
    struct.pack_into('<I', out, lit, ITCM_END_VANILLA + len(blob))
    return bytes(out)


def species_names(rom):
    bank = ndsfs.narc(rom.file(fid_of(rom, 'a/0/0/2')))[SPECIES_BANK]
    return [t for t, _ in gen5text.decode(bank)[0]]


def ess_name(species, name):
    return ESS_SPECIAL.get(species) or re.sub(r'[^A-Za-z0-9]', '', name).upper()


class Sprites:
    """a/0/4/7 registry + a/0/4/8 textures, with new Pokémon obj codes allocated from 0x126C."""

    def __init__(self, rom):
        self.rom = rom
        self.regf, self.resf = fid_of(rom, 'a/0/4/7'), fid_of(rom, 'a/0/4/8')
        self.reg_raw, self.res_raw = rom.file(self.regf), rom.file(self.resf)
        self.reg = ndsfs.narc(self.reg_raw)[0]
        self.res = ndsfs.narc(self.res_raw)
        self.new_entries = []
        for obj in (TEMPLATE_32, TEMPLATE_64, POKE_OBJ_END - 1):
            assert struct.unpack_from('<H', self.entry(obj), 0)[0] == obj

    def entry(self, obj):
        if obj >= POKE_OBJ_END:
            return self.new_entries[obj - POKE_OBJ_END]
        i = obj - POKE_INDEX_OFFSET
        return bytes(self.reg[4 + 28 * i:4 + 28 * (i + 1)])

    def texture(self, obj):
        return self.res[struct.unpack_from('<H', self.entry(obj), 16)[0]]

    def add(self, like_obj, data, scene_node=None):
        """New obj code drawn like `like_obj` (same registry settings) with texture file `data`;
        scene_node 10 = walking Pokémon, 11 = flying/floating."""
        obj = POKE_OBJ_END + len(self.new_entries)
        self.res.append(data)
        e = bytearray(self.entry(like_obj))
        struct.pack_into('<H', e, 0, obj)
        struct.pack_into('<H', e, 16, len(self.res) - 1)
        if scene_node is not None:
            e[3] = scene_node
        self.new_entries.append(bytes(e))
        return obj

    def files(self):
        reg = bytearray(self.reg)
        at = 4 + 28 * (POKE_OBJ_END - POKE_INDEX_OFFSET)
        reg[at:at] = b''.join(self.new_entries)
        struct.pack_into('<I', reg, 0, struct.unpack_from('<I', reg, 0)[0] + len(self.new_entries))
        return {self.regf: ndsfs.pack_narc([bytes(reg)], ndsfs.narc_layout(self.reg_raw)),
                self.resf: ndsfs.pack_narc(self.res, ndsfs.narc_layout(self.res_raw))}


def ess_variants(ess_dir, base):
    """(form, gender, sheet name) for a species' Essentials sheets; gender-specific first."""
    out = [(0, 1, base + '_female'), (0, 2, base)]
    k = 1
    while os.path.exists(os.path.join(ess_dir, 'normal', f'{base}_{k}.png')):
        out.append((k, 2, f'{base}_{k}'))
        k += 1
    return [v for v in out if os.path.exists(os.path.join(ess_dir, 'normal', v[2] + '.png'))]


def flier_check(rom):
    """-> flies(species): Flying type or Levitate (a/0/1/6 personal data)."""
    personal = ndsfs.narc(rom.file(fid_of(rom, 'a/0/1/6')))

    def flies(sp):
        d = personal[sp]
        return 2 in (d[6], d[7]) or 26 in (d[24], d[25], d[26])
    return flies


def add_gen5(S, rows, ess_dir, names):
    """Sprites for species the game has none for. -> (new rows, {obj: (index frames, pal, sheet)})"""
    import follower_sprites as F
    have = {r[0] for r in rows}
    new_rows, info = [], {}
    flies = flier_check(S.rom)
    for sp in range(1, 650):
        if sp in have:
            continue
        base = ess_name(sp, names[sp])
        variants = ess_variants(ess_dir, base)
        if not any(g == 2 and f == 0 for f, g, _ in variants):
            print('no sheet for', sp, base)
        for form, gender, fname in variants:
            fr = F.sheet_frames(os.path.join(ess_dir, 'normal', fname + '.png'), cols=(0, 2))
            big = fr['down'][0].width > 32 or fr['down'][0].height > 32
            size = 64 if big else 32
            idx, pal = F.quantize(F.ds_frames(fr, size, mirrored=big))
            tmpl = TEMPLATE_64 if big else TEMPLATE_32
            # Flying type or Levitate: drawn like the game's own floating Pokémon (scene node 11)
            obj = S.add(tmpl, F.btx_encode(S.texture(tmpl), idx, pal), scene_node=11 if flies(sp) else 10)
            info[obj] = (idx, pal, fname, size, big)
            new_rows.append((sp, gender, form, obj))
    return new_rows, info


def hgss_shiny_index(hgss_dir):
    """HGSS follower textures keyed by their up/down texels -> shiny palette bytes (palette 2)."""
    import glob
    import follower_sprites as F
    out = {}
    for p in sorted(glob.glob(os.path.join(hgss_dir, 'mmodel_*.NSBTX'))):
        d = open(p, 'rb').read()
        try:
            texs, pals = F.btx_layout(d)
        except AssertionError:
            continue
        if len(pals) >= 2:
            frames, _ = F.btx_decode(d)
            out.setdefault(F.texel_key(frames), F.palette_bytes(d, 1))
    return out


def add_shiny(S, rows, ess_dir, hgss_dir, names, gen5_info):
    """A shiny twin for every follower obj code. -> rows with a fifth column (shiny obj code)."""
    import follower_sprites as F
    hg = hgss_shiny_index(hgss_dir) if hgss_dir else {}
    shiny_of, stats = {}, {'hgss': 0, 'essentials': 0, 'none': 0}
    for sp, gender, form, obj in rows:
        if obj in shiny_of:
            continue
        data = S.texture(obj)
        frames, pal = F.btx_decode(data)
        new = None
        if obj in gen5_info:
            idx, npal, fname, size, big = gen5_info[obj]
            sh = os.path.join(ess_dir, 'shiny', fname + '.png')
            if os.path.exists(sh):
                sfr = F.sheet_frames(sh, cols=(0, 2))
                new = F.btx_set_palette(data, F.shiny_palette(idx, F.ds_frames(sfr, size, mirrored=big), npal))
                stats['essentials'] += 1
        elif F.texel_key(frames) in hg:
            new = F.btx_set_palette(data, hg[F.texel_key(frames)])
            stats['hgss'] += 1
        elif ess_dir:
            base = ess_name(sp, names[sp])
            fname = base if form == 0 else f'{base}_{form}'
            n, s = (os.path.join(ess_dir, d, fname + '.png') for d in ('normal', 'shiny'))
            cmap = F.colour_map(n, s) if os.path.exists(n) and os.path.exists(s) else None
            if cmap:
                new = F.btx_set_palette(data, F.map_palette(pal, cmap))
                stats['essentials'] += 1
        if new is None:
            stats['none'] += 1
            shiny_of[obj] = obj
        else:
            shiny_of[obj] = S.add(obj, new)
    print('shiny sprites:', stats)
    return [r + (shiny_of[r[3]],) for r in rows]


TALK_SCRIPT_FILE = 1230     # a/0/5/6 common script for ids 2000-2099 (text: story bank 208)
TALK_SCRIPT_BASE = 2000
TALK_TEXT_BANK = 208        # a/0/0/3
TALK_ARC = 208              # a/2/0/8 (the TPoke table): the talk data is appended to it


class RomView:
    """The ROM with the files changed so far (several steps append to the same NARCs)."""
    def __init__(self, rom, files):
        self.rom, self.files, self.paths = rom, files, rom.paths

    def file(self, fid):
        return self.files[fid] if fid in self.files else self.rom.file(fid)


def add_talk(rom, talk):
    """Append followers/talk.s to common script 1230 and the talk lines (follower_talk.TalkData) to
    story bank 208. -> ({file id: NARC bytes}, script id, text id of the first line)"""
    import gen5script
    import redux_rom as R
    scrf, txtf = fid_of(rom, 'a/0/5/6'), fid_of(rom, 'a/0/0/3')
    scr_raw, txt_raw = rom.file(scrf), rom.file(txtf)
    scripts, texts = ndsfs.narc(scr_raw), ndsfs.narc(txt_raw)

    bank = texts[TALK_TEXT_BANK]
    secs = gen5text.decode(bank)
    first = len(secs[0])
    lines = talk.texts()
    for s in secs:
        s += [(line, 0) for line in lines]
    texts[TALK_TEXT_BANK] = gen5text.encode(secs, struct.unpack_from('<I', bank, 8)[0], gen5text.padding(bank))

    listing, _ = gen5script.decompile_best(scripts[TALK_SCRIPT_FILE], R.BUILD)
    assert gen5script.assemble_any(listing, R.BUILD) == scripts[TALK_SCRIPT_FILE]
    listing_lines = listing.split('\n')
    last = max(i for i, l in enumerate(listing_lines) if l.startswith('.script '))
    index = sum(1 for l in listing_lines if l.startswith('.script '))
    listing_lines.insert(last + 1, '.script scr_follow')
    talk_s = open(os.path.join(SRC, 'talk.s')).read()
    for name, i in talk.extra_ids().items():
        talk_s = talk_s.replace(name, str(first + i))
    scripts[TALK_SCRIPT_FILE] = gen5script.assemble_any('\n'.join(listing_lines) + '\n' + talk_s, R.BUILD)
    return ({scrf: ndsfs.pack_narc(scripts, ndsfs.narc_layout(scr_raw)),
             txtf: ndsfs.pack_narc(texts, ndsfs.narc_layout(txt_raw))}, TALK_SCRIPT_BASE + index, first)


FIELD_MOVE_FILE = 1243      # a/0/5/6 common script: Strength, Surf, Cut, Waterfall, Dive, Flash, Teleport, Dig
# HGSS's follower reaction to a field move it used (talk.c TALK_OP_CUT / _STRENGTH): after Cut's
# effect, and once Strength is on. (cut-in slot variable, op)
FIELD_MOVE_SITES = [
    (r'(    PlayHMCutInEffect (\d+)\n    VMCall @\w+\n    HMCallCut\n(?:    .*\n){4}    VMSleep 3\n)', 11),
    (r'(    PlayHMCutInEffect (\d+)\n    VMCall @\w+\n)(?=    MsgSystem 11, 2\n)', 12),   # "Strength made it possible..."
]
# Moves the follower uses itself, with no cut-in (talk.h TALK_OP_SURF.. _FLASH): the HM pose + cut-in
# block becomes `if (op(slot) != 1) { pose; cut-in; [recall] }`. Surf (scr_2 A button, scr_3 menu)
# and the menu moves Flash / Teleport / Dig (scr_8 / scr_9 / scr_10, messages 27-29; scr_13 is
# Flash's other variant). (pattern, op, recall after the cut-in: HGSS's recall task)
CUT_IN = r'    VMCall @pre_L2\n    PlayHMCutInEffect (?P<slot>\d+)\n(?P<end>    (?:VMCall @pre_L3|PlayerSetSpecialSequence 1)\n)'
FIELD_MOVE_SKIP_SITES = [
    (CUT_IN + r'(?=    HMCallSurf\n)', 13, True),
    (r'(?<=    MsgSystem 29, 2\n    MsgSystemClose\n)' + CUT_IN, 14, True),
    (r'(?<=    MsgSystem 28, 2\n    MsgSystemClose\n)' + CUT_IN, 15, True),
    (r'(?<=    MsgSystem 27, 2\n    MsgSystemClose\n)' + CUT_IN, 16, False),
]
TALK_OP_RECALL = 17


def add_field_moves(rom):
    """Hook the follower's field-move reaction into common script 1243. -> {file id: NARC}"""
    import gen5script
    import redux_rom as R
    scrf = fid_of(rom, 'a/0/5/6')
    raw = rom.file(scrf)
    scripts = ndsfs.narc(raw)
    listing, _ = gen5script.decompile_best(scripts[FIELD_MOVE_FILE], R.BUILD)
    count = 0
    for pattern, op in FIELD_MOVE_SITES:
        listing, n = re.subn(pattern, lambda m: m.group(1) + f'    .hword 0x0089, {op}, 0x8030, {m.group(2)}\n',
                             listing)
        count += n
    assert count >= 3, f'field move hooks: {count} sites'
    skips = 0

    def skip_block(m, op, recall):
        nonlocal skips
        skips += 1
        slot, label = m.group('slot'), f'fm_follower_{skips}'
        return (f'    .hword 0x0089, {op}, 0x8030, {slot}\n'
                f'    StackPush 0x8030\n    StackPushConst 1\n    StackCmp 5\n    VMJumpIf 255, @{label}\n'
                + m.group(0)
                + (f'    .hword 0x0089, {TALK_OP_RECALL}, 0x8030, 0\n' if recall else '')
                + f'{label}:\n')
    for pattern, op, recall in FIELD_MOVE_SKIP_SITES:
        listing, n = re.subn(pattern, lambda m: skip_block(m, op, recall), listing)
        assert n, f'field move op {op}: no site'
    count += skips
    scripts[FIELD_MOVE_FILE] = gen5script.assemble_any(listing, R.BUILD)
    print(f'field move reactions hooked at {count} sites of common script {FIELD_MOVE_FILE}')
    return {scrf: ndsfs.pack_narc(scripts, ndsfs.narc_layout(raw))}


def add_talk_data(rom, talk, text_base, nzones):
    """Append the talk data member to a/2/0/8. -> ({file id: NARC}, member)"""
    fid = fid_of(rom, 'a/2/0/8')
    raw = rom.file(fid)
    members = ndsfs.narc(raw)
    members.append(talk.blob(text_base, nzones))
    return {fid: ndsfs.pack_narc(members, ndsfs.narc_layout(raw))}, len(members) - 1


MEDIUM_AREA = 370       # opaque bounding box (all frames) of a 32x32 sprite; Pikachu 18x20 = 360 is small
# Follower shadow: 1/32 steps smaller than the player's (follow.c shadow_apply), per size class (small
# 22/32 = 69%, medium 27/32 = 84%, large 100%), 2 more for a hovering sprite (one that floats above it).
# (21/32 and less: a small Pokémon's shadow hides behind its feet in the low phase of the bob.)
SHADOW_SHRINK = (10, 5, 0)
SHADOW_SHRINK_HOVER = 2


def add_size_classes(S, rows):
    """Follower size class in the gender column's high byte: 0 small (1 tile behind), 1 medium
    (1.5: one tile, drawn half a tile further back), 2 large 64x64 sprite (2 tiles); and bit 10,
    hover: the sprite floats above its shadow (follow.c WOFS_HOVER) instead of standing in it. That is
    the game's floating scene node 11 (B2's own flying/floating sprites, and ours for Flying types and
    Levitate), except for large sprites of Pokémon that neither fly nor levitate (Steelix, Kyogre...).
    Bits 11-15: how much smaller its shadow is (SHADOW_SHRINK)."""
    import follower_sprites as F
    flies = flier_check(S.rom)
    cls_of, out, count, hover = {}, [], [0, 0, 0], set()
    for r in rows:
        obj = r[3]
        if obj not in cls_of:
            if S.entry(obj)[7] == 2:
                cls_of[obj] = 2
            else:
                frames, _ = F.btx_decode(S.texture(obj))
                ys = [y for f in frames for y, row in enumerate(f) if any(row)]
                xs = [x for f in frames for row in f for x, v in enumerate(row) if v]
                area = (max(ys) - min(ys) + 1) * (max(xs) - min(xs) + 1) if ys else 0
                cls_of[obj] = 1 if area >= MEDIUM_AREA else 0
            count[cls_of[obj]] += 1
        e = S.entry(obj)
        hv = e[3] == 11 and (cls_of[obj] != 2 or flies(r[0]))
        if hv:
            hover.add(obj)
        shrink = SHADOW_SHRINK[cls_of[obj]] + (SHADOW_SHRINK_HOVER if hv else 0)
        out.append((r[0], r[1] | cls_of[obj] << 8 | hv << 10 | shrink << 11) + tuple(r[2:]))
    print(f'follower sizes: {count[0]} small, {count[1]} medium, {count[2]} large; {len(hover)} hovering sprites')
    return out


def patch_obj_index(arm9, ram, count):
    lit = lambda a: a - ram
    assert struct.unpack_from('<I', arm9, lit(LIT_POKE_END))[0] == POKE_OBJ_END
    assert struct.unpack_from('<I', arm9, lit(LIT_3D_OFFSET))[0] == 0x1C1B
    out = bytearray(arm9)
    struct.pack_into('<I', out, lit(LIT_POKE_END), POKE_OBJ_END + count)
    struct.pack_into('<I', out, lit(LIT_3D_OFFSET), 0x1C1B - count)
    return bytes(out)


def patch_event_hooks(code, ov_id, ram, syms):
    for ov, sites, orig, name in EVENT_HOOKS:
        if ov != ov_id:
            continue
        for at in sites:
            assert struct.unpack_from('<I', code, at - ram)[0] == orig, f'{at:#x}: not {orig:#x}'
            struct.pack_into('<I', code, at - ram, syms[name] | 1)


blz_decode = romtool.blz_decode


def follower_patch_ranges(added=0):
    """[(where, address, size, what)] of the code / data bytes build() changes outside the follower
    code itself, so later steps (tools/qol_build.py) can refuse patches that collide with them."""
    out = [('arm9', ARENA_LO_LITERAL, 4, 'followers: ITCM arena start literal'),
           ('itcm', ITCM_END_VANILLA, ITCM_RESERVE, 'followers: follower code block'),
           ('ov36', HOOK_SITE, 4, 'followers: FieldRoutine_Run hook'),
           ('ov36', WOFS_HOOK, 4, 'followers: billboard sprite offset hook'),
           ('ov36', SHADOW_TASK_DESC + 4, 8, 'followers: shadow task init / delete'),
           ('ov12', SCRIPT_CMD_TABLE + 4 * FOLLOW_SCRIPT_CMD, 4, 'followers: script command 0x89'),
           ('ov12', SCRIPT_CMD_PERMS + FOLLOW_SCRIPT_CMD, 1, 'followers: script command 0x89 permissions')]
    for ov, sites, _, name in EVENT_HOOKS:
        out += [(f'ov{ov}', at, 4, f'followers: {name}') for at in sites]
    if added:
        out += [('arm9', LIT_POKE_END, 4, 'followers: obj code range literal'),
                ('arm9', LIT_3D_OFFSET, 4, 'followers: obj code 3D offset literal')]
    return out


def build(src, dst, essentials=None, hgss=None, hgss_root=None, talk_lines=None, names_rom=None):
    """Add the followers to ROM `src`, write `dst`. -> {'syms': {name: address}, 'elf': path of the
    linked follower code (build/followers/follow.elf), 'added': new obj codes, 'patches':
    follower_patch_ranges()}. Used by main() (the CLI) and tools/build_redux3.py."""
    # --hgss is POKEHEARTGOLD/files/data/mmodel/mmodel
    hgss_root = hgss_root or (hgss and os.path.normpath(os.path.join(hgss, '..', '..', '..', '..')))
    rom = ndsfs.Rom(src)
    rows = tpoke_rows(rom)
    files, added = {}, 0
    if essentials or hgss:
        S = Sprites(rom)
        names = species_names(ndsfs.Rom(names_rom) if names_rom else rom)   # English (Essentials file names)
        info = {}
        if essentials:
            new_rows, info = add_gen5(S, rows, essentials, names)
            rows = new_rows + rows    # gender-specific rows first; ours never collide with vanilla's
            print(f'added {len(new_rows)} field sprites ({len({r[0] for r in new_rows})} species)')
        rows = add_shiny(S, rows, essentials, hgss, names, info)
        files, added = S.files(), len(S.new_entries)
        print(f'{added} new obj codes {POKE_OBJ_END:#x}-{POKE_OBJ_END + added - 1:#x}')
    else:
        S = Sprites(rom)
    rows = add_size_classes(S, rows)
    if not hgss_root:
        sys.exit('--hgss or --hgss-root (a pokeheartgold checkout) is needed for the talk data')
    lines = json.load(open(talk_lines)) if talk_lines else None    # e.g. Japanese (jp_port.py)
    talk = follower_talk.TalkData(hgss_root, follower_talk.TILE_GROUPS, translations=lines)
    talk_files, talk_script, text_base = add_talk(RomView(rom, files), talk)
    files.update(talk_files)
    nzones = max(int(z) for z in talk.map['zones']) + 1
    talk_files, talk_dat = add_talk_data(RomView(rom, files), talk, text_base, nzones)
    files.update(talk_files)
    print(f'talk script id {talk_script}, {len(talk.texts())} lines from text id {text_base}, '
          f'data a/2/0/8 member {talk_dat}; {talk.stats["disabled"]} HGSS entries unused in Unova')
    files.update(add_field_moves(RomView(rom, files)))
    files.update(follower_ballfx.ball_assets(RomView(rom, files), hgss_root, BUILD))
    emote_files, emote_first = follower_emotes.emote_assets(RomView(rom, files), hgss_root)
    files.update(emote_files)
    print(f'emote balloons: a/0/7/4 members {emote_first}-{emote_first + 27}')
    blob, syms = compile_code(rows, talk_script, [f'-DTALK_ARC={TALK_ARC}', f'-DTALK_DAT={talk_dat}',
                                                  f'-DEMOTE_FIRST_MEMBER={emote_first}'])
    hook = syms['follow_hook_field_frame']
    print(f'follower code: {os.path.getsize(os.path.join(BUILD, "follow.bin"))} of {len(blob)} bytes at {ITCM_END_VANILLA:#010x}, hook {hook:#010x}')
    assert hook == ITCM_END_VANILLA, 'hook must be first'

    arm9 = patch_arm9(bytes(rom.m[rom.arm9[0]:rom.arm9[0] + rom.arm9[1]]), rom.arm9_ram, blob)
    if added:
        arm9 = patch_obj_index(arm9, rom.arm9_ram, added)

    ovs = romtool.OverlayTable(rom, files)

    code = ovs.load(36, OV36_RAM)
    at = HOOK_SITE - OV36_RAM
    assert HOOK_SITE + 4 + decode_bl(code, at) == HOOK_ORIG, 'hook site does not call 0x02180B00'
    code[at:at + 4] = thumb_bl(HOOK_SITE, hook)
    # Pokémon billboard update (port of HGSS ov01_021F8D80): its sprite offset store goes through
    # follow_wofs_hook, which gives the follower HGSS's bob, standing in its shadow (follow.c WOFS_REST)
    at = WOFS_HOOK - OV36_RAM
    assert WOFS_HOOK + 4 + decode_bl(code, at) == WOFS_ORIG, 'unexpected billboard update code'
    code[at:at + 4] = thumb_bl(WOFS_HOOK, syms['follow_wofs_hook'])
    # the follower's shadow is drawn to its size (follow.c shadow_apply)
    for at, orig, name in SHADOW_TASK_HOOKS:
        assert struct.unpack_from('<I', code, at - OV36_RAM)[0] == orig, f'{at:#x}: not {orig:#x}'
        struct.pack_into('<I', code, at - OV36_RAM, syms[name] | 1)
    ovs.store(36, code)

    # script command FOLLOW_SCRIPT_CMD (an empty slot of the OVL_12 command table) -> our handler
    code = ovs.load(12, OV12_RAM)
    patch_event_hooks(code, 12, OV12_RAM, syms)
    at = SCRIPT_CMD_TABLE - OV12_RAM + 4 * FOLLOW_SCRIPT_CMD
    assert struct.unpack_from('<I', code, at)[0] == 0, 'script command slot is not free'
    struct.pack_into('<I', code, at, syms['follow_script_cmd'] | 1)
    # FUN_02153D38 (VM pre-command hook) stops the script unless the command's permission byte
    # allows the current script context (bits 0-2); free slots have 0.
    code[SCRIPT_CMD_PERMS - OV12_RAM + FOLLOW_SCRIPT_CMD] = 7
    ovs.store(12, code)

    for ov_id, ram in ((33, OV33_RAM), (35, OV35_RAM)):
        code = ovs.load(ov_id, ram)
        patch_event_hooks(code, ov_id, ram, syms)
        ovs.store(ov_id, code)

    out = romtool.build(src, files=files, arm9=arm9, ovt9=ovs.bytes())
    open(dst, 'wb').write(out)
    print('wrote', dst)
    return {'syms': syms, 'elf': os.path.join(BUILD, 'follow.elf'), 'added': added,
            'patches': follower_patch_ranges(added)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('dst')
    ap.add_argument('--essentials', help='Essentials follower sheets: DIR/normal/*.png, DIR/shiny/*.png')
    ap.add_argument('--hgss', help='pokeheartgold files/data/mmodel/mmodel (shiny palettes for #1-493)')
    ap.add_argument('--hgss-root', help='pokeheartgold checkout (talk data, Poké Ball effect); default: from --hgss')
    ap.add_argument('--talk-lines', help='JSON {"f:N": text}: the talk lines in another language')
    ap.add_argument('--names-rom', help='an English ROM to take species names from (Essentials sheets are named in English)')
    a = ap.parse_args()
    build(a.src, a.dst, essentials=a.essentials, hgss=a.hgss, hgss_root=a.hgss_root,
          talk_lines=a.talk_lines, names_rom=a.names_rom)


if __name__ == '__main__':
    main()
