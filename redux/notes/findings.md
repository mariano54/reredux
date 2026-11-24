# Blaze Black 2 Redux v1.4.1 — reverse-engineering findings

Base: Pokémon Black 2 (USA/Europe) `IREO`, the same build as `pokeblack2`. Redux has no source;
it was made by hex editing plus Tinke/PPNFR/SAK/CTRMap (see its credits). Everything here is derived
from the official `.xdelta` decoded against synthetic sources (no ROM needed) and diffed against
pokeblack2 assembled with GNU as. Generated detail: [arm9-changes.md](arm9-changes.md).

## Patch overview

- 512 MiB ROM, only ~1.0 MiB of literal new bytes. Tinke rebuilt the filesystem, so almost every
  file moved, but 33 of 318 data files and ~7 of 344 overlays carry real changes.
- Header: arm9 size 0x9AC0C (same as vanilla decompressed); FAT at 0x38B000 (662 entries).
- Overlay table: only overlay 167's entry was rewritten (see below).

## arm9 (static + ITCM): 6 functions, 1 code cave, 1 table

Coverage: 573,453 of 617,212 bytes verified (93%); the rest are short copies from elsewhere in the
vanilla ROM that cannot be checked without one (assumed unchanged). ITCM: no changes.

| Address | Function | Change | Feature |
|---|---|---|---|
| 0201CDF0 | `PML_UtilPIDIsRare` | `cmp r0, #8` → `cmp r0, #128` | Shiny rate 1/8192 → 1/512 |
| 0201D7A4 | `PML_GenPID` | `eors r4, r0` → `nop` | PID generation tweak (likely the shiny-lock removal by Aspharon) |
| 02026B18 | `PML_MoveIsHM` | body zeroed, now `movs r0,#0; bx lr` | HM moves can be forgotten |
| 02035312 | `canPlayerExchangePhotos` | `movs r0,#0` → `movs r0,r0` | no-op in practice (r0 is already 0 on that path) |
| 02032E88 | `ISSSwitch_IsOffCore` | case 2 `pop {r3,pc}` → `beq` | unexplained; branches past the function |
| 02031B96 | `FUN_02031B94` | alignment padding `0000` → `0203` | harmless leftover |

**Code cave at 0x02093BF0** (vanilla: zero padding inside rodata `_02093390`): Redux placed two
small Thumb routines and a pointer table there:
- `0x02093BF0`: range check on r2 against 0x9E94/0xA0DC/0xA268/0xA2AC/0xA430, remapping r1 —
  looks like an ID/offset remap (e.g. extra entries for the 18th type).
- `0x02093C20`: second routine plus Thumb pointers into the battle overlays
  (0x021B6BA9, 0x021B6BB9, 0x021BA811, 0x021B8E31, 0x021B8E43) — Fairy-type glue.

**Tables**
- `_02092394` (236 × {u16, u16}): high byte of the first field rewritten in almost every entry.
  Purpose not yet identified.
- `_0209054C`, `_02090C84`, `_02090D50`: scattered nibble-packed (0x00/0x11/0x22) bytes changed —
  probably small 4bpp graphics (icons/glyphs). To identify.

## Overlays

Recovered without a ROM (`recover_overlays.py`, detail in [overlay-changes.md](overlay-changes.md)).
How: `blz.c` now reproduces Nintendo's BLZ compressor exactly (242/242 untouched overlays match
the vanilla file size; tokens chosen top-down, raw head = first point where savings reach the
total), 251/260 vanilla overlay images match pokeblack2's SHA-1s (mwld pads image ends to up to
128 bytes), and the compressed vanilla arm9 is rebuilt at its exact size (0x736A4,
`arm9model.py`). Copies inside Redux's files are filled from that vanilla model; output bytes
that depend on the few remaining holes (copies from DSProt overlays 12/35/165 and ~6 others) are
tracked as unverifiable and excluded.

| Overlay | Role | Changed (verified) | Unverifiable | What changed |
|---|---|---|---|---|
| 167 | battle core | 41 B in 9 functions + 384 B new | 202 B | **Fairy type**: new 18×18 type chart at 0x02199740 (the overlay's RAM start moved down 0x180 to make room); every "type < 17" check became "< 18" (`GetTypeEffectiveness`, `splitTypeCore`, `DoesMonHaveType`, `ServerEvent_CalcDamage`, `GetTypeWeaknesses`, Color Change, Conversion 2). Triple Kick power handler 10 → 20 (Triple Axel). |
| 168 | battle handlers | 2 B (data) | 20 B | one table halfword 0 → 0x023C |
| 36 | field / overworld | 45 B in 5 functions | holes inferred (see note) | Hidden Grottos (`hollowSet`, `generateHollow`: respawn every visit), dust clouds (`EffectEncount_GenDustCloudItem`: no Gems; `UpdatePhenomenon`), `EventBattleCall_DecideEnvTrainer` rewritten (37 B; probably the forced weather/terrain for special trainers) |
| 255 | UI (type-aware screens) | 12 B in 6 functions | 0 | type limits 17 → 18 and 49 → 50; one call redirected to the arm9 code cave `0x02093BF0` |
| 265 | UI | 20 B | 0 | type-icon order list extended by one entry (Fairy) |
| 166 | — | 6 B (data) | 0 | small table edit |

The 18×18 chart was checked against Gen 6 matchups (Fairy vs Dragon/Dark/Fighting 2×, Dragon vs
Fairy 0×, Steel/Poison vs Fairy 2×, Ghost/Dark vs Steel neutral as in Gen 6): all correct.

Note on ov36: its 49 hole bytes were filled by `blzsolve.py`, which picks values that reproduce
vanilla, so a Redux change hiding exactly behind those bytes would be missed. Overlays 205–207
are not recovered yet (their FAT entries were copied from vanilla, so the file split is unknown).

## Data files (33 changed)

Text (`a/0/0/2`, `a/0/0/3`, ~470 KB new), Pokémon icons `a/0/0/7` (Gen VI box sprites, 383 KB),
learnsets `a/0/1/8`, trainer Pokémon `a/0/9/2`, wild encounters `a/1/2/7`, event scripts
`a/0/5/6` (32 KB), maps `a/0/0/8`, personal `a/0/1/6`, items/moves/evolutions, and a few others.
Data diffs need the vanilla files, which need a ROM.

Checked Oct 16 with `tools/narcs.py`: NARC section headers are copied from vanilla, so the layout
can only be solved where the last offset entry changed (6 of 33 archives, e.g. scripts `a/0/5/6`,
trainers `a/0/9/1`/`a/0/9/2`, map models `a/0/0/8`). Even then Redux's changed subfiles are mostly
copies of vanilla bytes: trainer Pokémon 89% known, trainer headers 27%, event scripts 7%. Unlike
code (rebuilt from pokeblack2), there is no source for vanilla data, so **the data side needs a
legally dumped Black 2 ROM**; with one, every file diffs exactly in minutes.
