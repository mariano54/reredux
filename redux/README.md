# Pokémon Blaze Black 2 ReRedux (Blaze Black 2 Redux reverse engineering)

## Credits

- **Pokémon Black 2 / White 2**: © Nintendo, Creatures Inc., GAME FREAK inc. Pokémon and all related
  names are trademarks of Nintendo, Creatures and GAME FREAK, and The Pokémon Company.
- **Blaze Black 2**: by **Drayano**.
- **Blaze Black 2 Redux**: by **AphexCubed** (with Drayano), whose v1.4.1 is the base of everything here.
- **pokeblack2** and the Gen 5 decompilation / research community, whose disassembly, symbols and
  documentation made this possible; **pokeheartgold** for the HeartGold/SoulSilver following-Pokémon
  reference; the PokeScriptSDK5 command definitions (fetched at build time, not included).

## Disclaimer

- This is an unofficial fan project. It is not affiliated with, endorsed by or supported by Nintendo,
  The Pokémon Company, GAME FREAK, Creatures, Drayano or AphexCubed.
- This repository contains **only code**: tools, patch sources and notes. It contains **no ROM, no
  game, and no game assets**. It is not the game, and it cannot be played on its own.
- To use it you must **own Pokémon Black 2** and dump your own cartridge. The build steps read your
  ROM and the publicly released Redux patch, and produce the patched ROM on your own machine. Do not
  ask for, share or distribute ROMs.
- Provided as-is, with no warranty. Keep backups of your saves.

## What this is

- **A decompilation of Blaze Black 2 Redux**: what Blaze Black 2 and Redux v1.4.1 change in Pokémon
  Black 2, recovered as editable source on top of `pokeblack2` (code, scripts, text, data tables,
  maps), with tools that rebuild the ROM byte-exact from that source.
- **The source code of ReRedux**: Redux plus HeartGold/SoulSilver-style following Pokémon, a rules
  and settings menu at the start (Challenge Mode, Nuzlocke options, species limit, no items), speed-ups
  that never cut a sound, faster loading and saving, smoother and snappier movement, IV/EV columns,
  evolution and level-up move pages, a Japanese version, and more (see "ReRedux: player guide").
- **Not fully tested.** It has been played and tested in emulators (melonDS, DeSmuME) with automated
  checks, not on every route, every battle facility or real hardware. Expect bugs.
- **Meant for experimenting.** The goal is to let others make their own patches and try ideas on the
  game: edit the extracted source, add a module, rebuild.
- **AI-coded.** Almost all of it was written by Claude (Anthropic's AI) working with one person. You
  can do the same: ask Claude for a feature in plain words, and it can read the code here, implement
  it, build the ROM and test it in an emulator.

## ReRedux features

Everything Blaze Black 2 Redux has (Fairy type, all 649 Pokémon obtainable, updated types, stats,
abilities and movesets, harder trainers), plus:

**Following Pokémon (HeartGold/SoulSilver style)**
- Your lead Pokémon walks behind you, sized to the Pokémon (large ones take two tiles, flying ones hover,
  shadows scale with the Pokémon).
- Talk to it: HGSS's own lines, motions, cries and emote balloons. It returns to its Poké Ball for the
  bike, Surf and doors it can't fit through, and joins you on Surf.

**Your rules, chosen before the adventure starts**
- A settings menu right after the intro: Difficulty (Challenge by default), Black City or White Forest
  (no Key System), Nuzlocke rules one by one (release or graveyard on faint, game over, first catch per
  area, dupes and shiny clauses, always nickname), species limit (one per species or per evolution line),
  no items in battle (you and/or trainers), and speed options. A recap asks you to confirm.
- SELECT in the field shows every rule you chose, and how many Pokémon the rules have taken.

**Faster, never cut short**
- Snappier controls: running reacts in about 2 frames instead of 9.5 (no turning on the spot first),
  so it feels like a GBA game. Smooth running at 6 frames per tile, walking at 8, with the follower in step.
- 60 fps overworld: the field logic keeps its 30 Hz pace, every frame shows a picture (camera, people,
  objects and water halfway in between), steady everywhere measured incl. Route 20's bridges, Virbank and
  Castelia; a lighter engine (a third less CPU per field frame than before) leaves room to spare.
- Loading about 40% faster on doors, stairs and gates, and after battles.
- Saving about 2.5× faster (only what changed is written; both save copies stay intact).
- Faster Pokémon Center heals, shops, text, cutscenes and menus; auto-run (hold B to walk).
- R toggles 2× turbo in the field and in battle; music and sound effects keep their normal speed.
- No sound is ever cut off: jingles, cries, evolution and hatching play in full, and the capture
  animation matches Black 2.

**More information on screen**
- Pokémon summary: IVs and EVs in columns next to the stats; SELECT shows the totals and Hidden Power.
- A new EVO/MOVES page in the summary and the Pokédex: how the Pokémon evolves (every method, branching
  families) and every move it learns by level, with type and power.
- Base stats, abilities and hidden ability on every Pokédex entry.

**Also**
- A Japanese version (English + 日本語), built from the Japanese release's text and fonts.
- Starting a New Game over an old save asks before overwriting it instead of refusing every save.

Findings: [notes/findings.md](notes/findings.md) · exact diff: [notes/rom-diff.md](notes/rom-diff.md) ·
[scripts](notes/script-changes.md) ·
[arm9](notes/arm9-changes.md) · [overlays](notes/overlay-changes.md)

## Editable sources → ROM (needs your Black 2 ROM)

Put a clean Black 2 (USA/Europe) ROM, SHA-1 `e51e6dfb8678a3d19dcd2a10691b96a569ca0abb`, at
`build/vanilla_rom/black2.nds`, then:

```sh
tools/fetch_patch.sh                                   # official v1.4.1 patch (sha256-pinned)
mkdir -p build/bin && cc -O2 -o build/bin/blz tools/blz.c
xdelta3 -d -s build/vanilla_rom/black2.nds build/patch/complete.xdelta build/vanilla_rom/redux.nds
cd tools
python3 fetch_script_defs.py      # PokeScriptSDK5 command definitions -> build/ext (not vendored)
python3 rom_diff.py               # exact per-file diff -> notes/rom-diff.md, build/files/
python3 export_text.py            # message banks  -> build/src/{redux,vanilla}/text/{system,story}/NNNN.txt
python3 export_scripts.py         # event scripts  -> build/src/{redux,vanilla}/scripts/NNNN.s
python3 export_data.py            # tables         -> build/src/{redux,vanilla}/data/*.json
python3 build_rom.py --check      # sources -> build/out/redux_built.nds, identical to redux.nds
python3 test_edit_build.py        # edit text/trainer/encounter, rebuild, verify
```

Edit anything under `build/src/redux/` and run `build_rom.py` to get a playable ROM. Every format is
lossless (decode → encode is byte-exact for all files of both ROMs):

| Source | Archive | Format |
|---|---|---|
| `text/system`, `text/story` | a/0/0/2, a/0/0/3 | one entry per line; `\n` line break, `{BE01}` control codes, `{U+XXXX}` raw chars |
| `scripts/NNNN.s` | a/0/5/6 | assembler listing: `.script` entries, labels, `CommandName args`, `.move`, raw `.hword` |
| `data/trainers.json` | a/0/9/1 + a/0/9/2 | trainers with parties (species/moves/items by name or `#id`) |
| `data/encounters.json` | a/1/2/7 | per zone, per season: rates + slots `[species, min, max(, form)]` |
| `data/personal.json` | a/0/1/6 | base stats, types, abilities, egg groups, TM/tutor bit fields (hex) |
| `data/learnsets.json`, `evolutions.json` | a/0/1/8, a/0/1/9 | `[level, move]`; `[method, param, target, slot]` |
| `data/moves.json`, `items.json` | a/0/2/1, a/0/2/4 | common fields decoded, the rest kept as hex |

`romtool.py` re-lays out the filesystem when a file changes size (0x200 alignment, FAT, header CRC;
never overwriting a DSi-enhanced ROM's TWL area).

### Named tree (recommended for editing)

```sh
python3 export_named.py ../build/vanilla_rom/redux.nds ../build/named/redux
python3 build_rom.py --src ../build/named/redux --check          # byte-identical to redux.nds
```

```
named/redux/
  manifest.json                     file -> archive slot (the builder only needs this)
  constants/*.txt                   SPECIES_/ITEM_/MOVE_/TRAINER_/ZONE_* (frozen at export)
  zones/400_accumula_town/zone.json   zone header: script, init_script, text, encounter, location
                         events.s     event script, e.g.  ItemCheckCount ITEM_SACRED_ASH, 1, 0x8020
                         init.s       MsgActor 1024, 35, 0, 0  ; "Jasmine: Er... Do you know about…"
                         text.txt     the zone's dialogue, one entry per line
                         entities.json  NPCs, warps (with destination zone names), triggers, furniture
                         matrix.json    map grid: map model id per cell (maps/models/NNNN.bin)
  maps/models/NNNN.bin              map models (binary; drop in files made with CTRMap & co.)
  scripts/common/NNNN.s             shared scripts no zone points at
  text/system/0090_species.txt ...  labeled system banks (species, moves, items, locations, …)
  data/*.json                       trainers, encounters, personal, learnsets, evolutions, moves, items
```

### Adding a town

```sh
python3 new_zone.py ../build/named/redux --from 400 --name "Pokegen Town"   # clones Accumula Town's layout
# -> zones/617_pokegen_town/{zone.json, events.s, text.txt, entities.json, matrix.json}
# add a warp to it from an existing zone's entities.json ("dest_zone": 617), then:
python3 build_rom.py --src ../build/named/redux --out ../build/out/mine.nds
python3 test_new_zone.py   # end-to-end check (7/7)
```

The new zone gets its own script, text bank, entity file and map matrix slots and a location name;
its init script is shared with the template (as Redux's Faraway Island does). Point matrix cells at
new map models to give it a new map.

### Following Pokémon (HGSS-style)

```sh
# Pillow needed (sprite conversion); arm-none-eabi-gcc for the code; a pokeheartgold checkout
# for the HGSS data (talk lines and conditions, Poké Ball and balloon graphics, shiny palettes)
python3 build_followers.py ../build/vanilla_rom/redux.nds ../build/out/redux_followers.nds \
    --essentials ESSENTIALS_DIR --hgss POKEHEARTGOLD/files/data/mmodel/mmodel
```

Your party's first non-fainted, non-egg Pokémon walks behind you, as in HeartGold/SoulSilver:
- **Movement:** it walks along your path 1.5 tiles behind for most Pokémon (one tile on the grid,
  drawn half a tile further back), one tile for small ones (Pikachu-sized: sprites filling under
  370 px of their 32x32 frame), and two tiles for large 64x64 sprites, which also occupy the tile
  behind them (NPCs walk around it, and you can talk to it there). It runs HGSS's idle cycle and
  bob (B2's Pokémon billboards are a port of HGSS's), and flying/floating Pokémon keep flapping.
  Build with `-DIDLE_MODE=0` to freeze walkers. Walk into it and you swap places; down a ledge it
  follows to the edge and hops. The code (`followers/*.c`) is compiled into a 24 KiB block
  appended to the ITCM and called once per field frame from a hook in overlay 36.
- **Sprites:** B2 ships field sprites for 546 species. The 103 missing Gen 5 species (124 sprites with
  forms) are converted from the Pokémon Essentials follower sheets (`ESSENTIALS_DIR/normal`,
  `/shiny`). Every sprite gets a **shiny** twin: HGSS's own palettes for #1–493, Essentials colours
  for Gen 5. Credits: `followers/CREDITS.md`.
- **Talking to it** runs HGSS's own interaction (`talk.c`, `talk_select.c`, driven by `talk.s`
  through script command 0x89): its 759 lines, chosen by HGSS's rules (status, HP, held item, type,
  friendship, mood, nature, weather, time of day, the tile it stands on, nearby people, hidden
  items, the place), each with HGSS's motions (hops, shakes, spins…), cries (also HGSS's low cry)
  and emote balloons (all 14: B2's own `!` `?` note `…` plus HGSS's heart, faces, sweat, poison,
  zZ…, `emote.c`), yes/no questions with follow-ups, friendship and mood changes, and gifts
  (HGSS's Fashion Case accessories become Musical props). The HGSS data is read from the decomp
  at build time (`tools/follower_talk.py`) and translated to Unova by `followers/talk_mapping.json`:
  every zone uses the lines of a matching HGSS place (gyms by type, Pokémon Centers, towns,
  routes, caves…), HGSS story flags become badge / Prop Case checks, and lines about Johto-only
  people and places are left out.
- **Mood** (HGSS's hidden per-Pokémon value, kept in an unused byte of B2's Pokémon data): changed
  by talking and by field moves, reset when a Pokémon becomes the lead. After Cut or Strength used
  by the follower it reacts like HGSS: Cut lifts its mood, a move of its own type makes it hop twice.
- **Where it can follow** (`followers/zone_modes.json`, HGSS's map rules): not in communication
  rooms, battle facilities, the Hall of Fame and similar; large (64x64) Pokémon not indoors.
- **Poké Ball** (`ballfx.c`, HGSS's own models): it goes back into its ball (white flash, shrink)
  when you get on the bike, before a warp into a place it can't follow (the warp waits for it), on
  warp panels, and when another Pokémon surfs or flies; it comes back out after the bike, such a
  place or a warp panel.
- **Field moves it uses itself** (hooks in common script 1243 and the Fly / Sweet Scent events):
  Surf without a cut-in (it hops, cries, steps onto your tile and jumps into the water), and a hop
  and cry for Fly, Dig, Teleport, Flash and Sweet Scent, twice when the move is of its type.
- **Visibility:** after a battle or menu it is back where it was, after Continue it stands behind
  you, after a warp it appears on your first step. Hidden while a script hides the player, on rail
  maps and while a story partner (Hugh, Cheren…) walks with you.

Tested in DeSmuME (`emu_drive.py`): indoors and outdoors, door warps and warp panels, after a wild
battle, ledges, normal and shiny Gen 1 and Gen 5 sprites, large followers (tail tile, recall and
release), talking (motions, cries, every balloon icon, texts with names and items), Surf, Cut, Fly,
Dig, Teleport, Flash, Sweet Scent, scripted player hiding, Continue. Demo video:
`build/scripts/make_video_hgss.py`.

### ReRedux: player guide

ReRedux is Blaze Black 2 Redux plus following Pokémon (above), a rules menu (Challenge Mode by
default, optional Nuzlocke rules) and many speed-ups. It comes in English and Japanese:
`Pokemon Blaze Black 2 ReRedux (EN).nds` and `(JP).nds`, built from your own ROMs.

**The settings menu** appears once in a new game, right after the flight over Unova. It comes
before Mom's scene. The main page lists every setting as "Name: Value" (Difficulty, City) or a
category with a summary ("Nuzlocke: Off / Classic / Custom", "Catch rules: Off / 3 on", "Items:
Normal", "Speed: Default / Custom"). A on a setting opens a small list of all its values: the
current one is marked ● and under the cursor, the hint at the bottom describes the highlighted
value, A picks it and B leaves it unchanged. A category opens its page of "Name: Value" rows (same
lists; B or *Back* returns). *Use Classic Nuzlocke preset...* lists what it turns on and asks first.
*Start the adventure!* shows every setting again, then asks "Start the adventure with these rules?".
After that nothing can be changed: there is no Key System any more (see below). Press **SELECT** in
the field at any time to see all your settings (and the rules' death count).

| Page | Setting | Default | What it does |
|---|---|---|---|
| main | Difficulty: Easy / Normal / **Challenge** | Challenge | B2's own modes: Challenge Mode makes trainers' Pokémon stronger. |
| main | City: **Black City** / White Forest | Black City | The postgame area: Black City and Black Tower (Black 2's own), or White Forest and White Treehollow (as in White 2). Set as the Key System's City Key does. |
| Nuzlocke | Use Classic Nuzlocke preset... | – | Turns on Fainted: Released, Game over, Always nickname, First catch only, Dupes clause and Shiny clause (after a yes/no). |
| | Fainted: Kept / Released / Graveyard | Kept | After every battle, Pokémon that fainted in it are released, or moved to the last PC Box (Graveyard). A Pokémon revived in the same battle still counts (unless that would leave no Pokémon that never fainted). Its held item goes to the Bag first. |
| | Game over | off | If all your Pokémon faint, "The adventure is over" and the game goes back to the title screen. Anything since your last save is lost. |
| | Always nickname | off | Every Pokémon you catch, receive or hatch goes to name entry. |
| Catch rules | First catch only | off | Only the first wild Pokémon you meet in each area (place name) can be caught. Other Poké Balls are refused with a message. Encounters only count once you carry a Poké Ball. All Hidden Grottos together are one area. |
| | Dupes clause | off | Species you've already caught can't be caught, and they don't use up the area. |
| | Species limit: Off / Same species / Same evolution line | Off | A wild Pokémon can't be caught (balls refused with a message) if your party or PC (not the graveyard box) already has that species, or in line mode any member of its evolution family (pre-evolutions, babies, branches, Shedinja). Doesn't use up the area. Applies to every wild battle, static ones too; the shiny clause wins. Gifts, eggs and trades aren't limited. |
| | Shiny clause | off | Shiny Pokémon can always be caught and never use up the area. |
| | Statics count | off | Legendary, scripted and Hidden Grotto battles count as the area's encounter. When off, they are free catches. |
| Items | No battle items | off | You can't use items from the Bag in battle. Poké Balls still work. |
| | No trainer items | off | Trainers you battle never use items. |
| Speed | Speed-ups | **on** | Every speed-up listed below. |
| | Turbo button | **on** | Allows the R turbo. |
| | Auto-run | **on** | Once you have the Running Shoes, you run without holding B. Hold B to walk. Like B-running in vanilla, running off in a new direction starts at once (no turn on the spot first); a short tap toward your follower still only turns you to face it, and B + a tap turns on the spot anywhere. |
| | Quick save | off | *Save* in the menu writes at once: no question, no yes/no. |
| | Quick Surf | off | Press A facing water to Surf at once, without "Would you like to Surf?". |

**Controls**
- **R** (field or battle): 2× turbo on/off. A confirm sound plays when it turns on, a cancel sound
  when it turns off. Music, cries and sound effects keep their normal speed. In battle the 2× runs only
  while no sound effect, cry or jingle plays (text, menus, gauges), so no sound is cut off. Turbo doesn't
  work in link or Wi-Fi battles, while a wireless connection is open, or while the game saves.
- **B** held: walk (with Auto-run on); B + a short tap of a direction turns on the spot (a tap toward the follower turns you to face it without B).
- **A** facing your follower: talk to it (HGSS's lines, emote balloons, cries; Japanese in the JP ROM).
- **SELECT** (in the field, when you could open the menu): shows every setting you chose, and how
  many Pokémon the rules took so far when Fainted isn't Kept.
- The summary's stats page (party or PC) shows each stat's **IV and EV** in two columns right of the
  stat ("IV" / "EV" above them; JP 個体値 / 努力値), HP as "current/max". **SELECT** there switches
  the Ability box between the ability and the totals: the IV total, Hidden Power's type, and the EV
  total with what's left of 510. The choice stays while you flip through Pokémon and pages and is back
  to the ability the next time you open a summary. Eggs and the battle summary are unchanged
  (`qol/statview.*`). The stat rows' text windows are 23 tiles wide (to x 248): with 24 the page's 13 windows
  needed 774 of the 768 tiles of the top text layer (frame 4, 0x6000 bytes), the last one (the move description)
  was never created, and leaving the page (LEFT, or RIGHT to EVO/MOVES) freed that NULL window: a data abort, i.e.
  a hang, on hardware and in melonDS (DeSmuME has no MPU and read on). Now 762 tiles (`statview.py` checks the sum).
- **EVO/MOVES** (summary and Pokédex): how a species evolves and the moves it learns by level, from
  Redux's own data (see "ReRedux: EVO/MOVES pages").
  - Summary (party or PC): RIGHT from the STATS page (or from RIBBONS when the Pokémon has ribbons) opens a
    page « EVO/MOVES » (JP ／しんか・わざ). Top screen: the whole evolution family, pre-evolutions first,
    the shown Pokémon in blue, every evolution with its method ("Lv. 16", "Fire Stone", "Knows Ancient
    Power", "Level up in Chargestone Cave", ...). Bottom screen: the level-up moves of its form, "Lv. N"
    and the move; moves it knows are blue, the next one it learns is red, and the list starts at that move.
    **A** (or a tap on a move) puts a cursor in the list: UP / DOWN move it and the top screen shows that
    move's type, category, PP, power, accuracy and description; A or B leaves the list. The white box
    shows the list position; its arrows and L / R scroll the list by a page. UP / DOWN outside the list go to the next Pokémon (eggs
    are skipped, as on every page but STATUS), LEFT goes back to STATS.
  - Pokédex entry: a fifth page EVO/MOVES after FORMS (its own capsule on the bottom bar, the green
    theme; LEFT on INFO / RIGHT on FORMS reach it too). Top: the evolution family as above; bottom: the
    level-up moves with each move's type and power, scrolled with the arrows, a tap on the list's upper /
    lower half, or L / R. UP / DOWN show the next / previous species. For species only seen it shows "???",
    as INFO does.
- **Base stats** (Pokédex): every entry's INFO page shows the species' base stats on its (otherwise empty) top
  screen, in the EVO page's box style: HP, Attack, Defense, Sp. Atk, Sp. Def and Speed as numbers with bars coloured
  by value (red under 50, orange, yellow, lime, green, teal from 130; a bar is full at 180), the total, the two
  abilities and the hidden ability (JP 種族値, ＨＰ / こうげき / ぼうぎょ / とくこう / とくぼう / すばやさ, 合計, とくせい,
  夢特性). The values are Redux's (its personal data) for the form the entry shows (the FORMS page's choice: Deoxys
  Speed, Rotom Wash, Giratina Origin, ...). Species only seen show "???". Choosing a foreign-language entry shows it
  there as in Black 2; the next species brings the stats back.

**No Key System.** Everything the keys used to choose is asked in the settings menu. Redux's key
bearer in Aspertia still gives his other gifts (National Pokédex, the save) but no keys, and
Unova Link's Key System refuses difficulty and City Key changes ("key not unlocked"). The
Iron / Iceberg chamber keys from the Underground Ruins still work there (they pick which Regi
chamber its door opens).

**Speed-ups** (with Speed-ups on):
- Walking takes 8 frames per tile instead of 16. Running takes 6 instead of 8. B2 draws the field at
  30 fps and its 3D has no sub-pixel precision, so the camera moves by whole units per 30 Hz update:
  walking is 4 units every update; running is 16 units in 3 updates, which no whole number divides, so it
  steps 5, 5, 6 (the least uneven split: never more than a third of a unit off an even motion, about a
  pixel every third picture, like vanilla's own 4 / 5 px running on maps with a closer camera). The
  follower moves by exactly as much as you in every update, so it never wobbles against you. Cutscene
  walks and trainers walking up keep their 12 / 6 frames.
- The field shows its picture a frame sooner (input to screen: 2-3 frames instead of B2's 3-4): each
  30 Hz update runs whole in its first frame and the second frame is idle. Before the update where the
  camera crosses the middle of a map block (the map then streams in new blocks), or after an update
  that ended late in its frame, the game goes back to B2's own split for a while; both switches keep
  every picture on screen for exactly 2 frames ("ReRedux: field timing" below).
- New games start at text speed Fast. Options still offers all three.
- Battles (no sound may be cut off; see "Battle sounds" below):
  - Battle messages auto-advance after 0.75× the wait ("X used the Poké Ball!" keeps its wait: the
    capture runs exactly as in vanilla).
  - The level-up stat box shows sooner (after the jingle).
  - Wild encounters get one flash, a 2× swirl and a short white fade. Trainer encounters get one flash.
  - 3D cut-ins run at 2×: Fly, the HM cut-ins and the trainer "VS" screen.
  - The battle fades out and back in from white sooner. The music still fades out over its normal
    half second.
  - Animations, sound effects, cries and jingles (capture, level-up, move learned), the evolution and
    the egg hatch keep vanilla timing.
- Cutscenes:
  - Script pauses take 0.625× as long and camera pans 0.69× as long.
  - Scripted walks, script fades and emote balloons are shorter.
  - Doors open and close faster.
- Trainers' "!" pause is shorter and they walk up to you faster.
- Facilities:
  - The Pokémon Center heal and the Poké Mart zoom are faster.
  - The PC drops the "booted up the PC" and "Storage System was accessed" lines. Its boot and
    shutdown sounds and the Box animations play at normal speed (speeding them up cut the sounds off).
- Menus: start-menu apps open and close without waiting for the button animations, and screen wipes take half as long.
- Save: about 2.5× faster (see "Fast save" below). The game no longer reads the whole save back to
  find what changed, and it writes only the parts that changed (still to both copies). The texts print
  at once and the progress dots don't hold it up. "X saved the game." stays for 0.5 s; A or B closes it
  sooner.
- Loading (doors, stairs, gates, warps, after battles; see "ReRedux: loading"):
  - The music of the old place fades out in half the time, and for a door it starts fading as the door
    opens, so the game no longer waits on a finished map for the fade to end. It still fades out completely.
  - The steps of a map change no longer wait a 30 Hz update each, and coming out of a door the black
    screen doesn't wait for the camera.
- Also faster:
  - Pokédex registration and the nickname screen fade in faster.
  - Fish bite sooner.
  - "Keep old moves" skips "Give up on learning?".
  - The season banner is shorter.

**Battle sounds.** Every battle-side speed-up was checked against vanilla Redux 1.4.1 (a headless
melonDS harness with hooks on the NNS sequence start / force-stop / free, the wave-out stop and the BGM
volume moves; the same save, trainer battle with level-ups, move learning and an evolution, wild catch with
Pokédex registration, run away, egg hatch). A sound counts as cut when it is force-stopped before its
natural end earlier than in vanilla. Removed because they cut sounds: the A/B jingle skip (level-up
jingle stopped after 18-25 of 48 frames, capture jingle after 39 of 226), the evolution and egg A-skips
(the transformation and egg-crack sounds never played, the scene music was cut short), the extra battle
tick every 10th frame (SEs stopped 3-5 frames sooner), the VM resume in battle (SEs stopped up to 7
frames sooner), the 10-frame battle music fade-out (vanilla 30), and
the ungated battle turbo (jingles, the capture fanfare and many SEs stopped at about half their length).
The Poké Ball capture (throw, opening, Pokémon drawn in, drop, three wobbles, click) now runs on vanilla
Black 2's / Redux's timeline (same wild Azurill, Master and Poké Ball: every capture sound within the few
frames by which Black 2 and Redux differ from each other); before, the extra tick ran it about 10% fast
(third wobble 41 frames early) and the shorter wait of "X used the Poké Ball!" threw the ball 18-30
frames early.
Kept (no cut measured): message waits ×0.75, the level-up stat box, the encounter flash / swirl / fade,
the battle fade-in, "Keep old moves", the Pokédex registration fades and the turbo gated on sound.
The 80 → 60 page wait of 0xFF-wait battle messages used to write 0 into the battle view's PokeCon pointer
(BTLV_SCU_StartMsg reuses r1 as an offset): the next Pokémon sent out (e.g. after a level-up message)
read a garbage BattlePokeParam and the ARM9 data-aborted. That was the Janitor Orville freeze; the patch
now also moves the offset base (`speed_rtp.h`).

**Always on:**
- Booting is faster: the copyright screen is shorter, the black gaps are shorter, and the title doesn't wait for Kyurem's cry.
- Loading from the card is faster: the ROM header asks for the SDK's mask-ROM card timing instead of Black 2's
  slower one (about 4x faster card reads in melonDS and on hardware). Entering a Pokémon Center (the medal
  checks) and a route gate (its electronic sign) need less CPU time. Nothing looks or sounds different.
- *Continue* doesn't ask "Turn on the C-Gear?". The C-Gear stays off; you can turn it on from its screen.
- The X menu opens with the cursor shown on **POKÉMON**, so X then A opens the party (Black 2 opened it with the
  cursor hidden, and the first A only showed it). It comes back on POKÉMON after closing any app too (Black 2: on
  that app). Before your first Pokémon (no POKÉMON icon) it is Black 2's. Touch works as before (`qol/xmenu.*`:
  the menu's create in overlay 36 and EventFieldMenu's return callback in overlay 12; tests `tests/xmenu/`,
  DeSmuME and melonDS).
- "1, 2, and... Ta-da!" plays without its pauses.
- The title screen's logo badge under "BLAZE BLACK 2" reads REREDUX (Redux's own letters, the badge
  widened to the right; `qol/logo.py`). "Developed by AphexCubed" stays.

**Known limitations**
- **Fast save: only tested in DeSmuME.** B2's write order, both save copies, the CRCs and the card
  library's write verify are unchanged, so real flash should behave as in vanilla. Still, test it on a
  flashcart or a DS before you rely on it.
- Testing: DeSmuME 0.9.12; loading times also in a headless melonDS (interpreter). Real hardware and DSi mode
  are untested. The mask-ROM card timing is what most retail carts use, so flashcarts should handle it, but it
  wasn't tried on one.
- The settings (difficulty and city too) can't be changed after *Start the adventure!*.
- Species limit: the Battle Box isn't searched; gifts, eggs and in-game trades aren't limited.
  In-game trades keep their original nickname (B2 doesn't let you rename another trainer's Pokémon),
  so Always nickname doesn't apply to them.
- Turbo doesn't speed up sound waits or VBlank fades, and doesn't work in link or Wi-Fi battles.
  It is limited by the CPU: a turbo frame does two field ticks, and where one tick already fills most
  of a frame the turbo frame takes two VBlanks, i.e. normal speed. Measured in DeSmuME (before the
  8 / 6-frame steps): indoors 2× (running 2.9 instead of 5.6 frames per tile), Aspertia 1.0–1.8×
  depending on the scene, Castelia (streets and waterfront) 1.0× (every turbo frame took two VBlanks);
  cut-ins still gain, and battles gain in their silent stretches (about 11% of a whole battle in
  melonDS). In melonDS turbo frames rarely overrun in the field (0–4 in 300 frames in Aspertia,
  Floccesy, Virbank: each one holds a picture for 2 frames); running with turbo is 3 frames per tile.
- The Japanese ROM's Pokédex shows foreign entries with the right labels, but a Japanese-language
  Pokémon's language button is drawn with the Japanese release's "E" graphic (its button order
  differs from the US one the code uses). Only species #1–493 have foreign entries (as in Black 2).
- Right after *New Game*, B2 writes the whole save to both copies (about 40 s in DeSmuME, while the
  professor's introduction runs), and nothing can be skipped there. The saves after that only write
  what changed (fast save): Mom's scene and the key bearer save in about 3 and 2 s (DeSmuME).
- *New Game* over an existing save: B2 then writes nothing at the start and refuses every save ("There is
  already a saved game file."), Mom's mandatory first save included. ReRedux's first save (Mom's, or a menu
  save) asks to overwrite the old save instead: YES writes the whole new save, NO keeps the old one. See
  "ReRedux: fast save".
- Redux's key bearer stands on the lookout stairs in Aspertia. Talk to him once (gifts and a save)
  before you can go up to Bianca.
- The ROM header's internal name and game code are Black 2's (`POKEMON B2`, `IREO`), so saves and
  cheats made for Black 2 apply. The banner (the launcher's icon and title) is ReRedux's: "Pokémon /
  Blaze Black 2 ReRedux / Fan modification" (JP: "ポケットモンスター / ブレイズブラック２ リリダックス /
  ファンメイド改造版"), with the US or Japanese box art as the icon.

QA (both languages, fresh new games through the real intro): `build/qa/` contact sheets, scripts in
`build/scripts/qa/` (see "Final QA" below).

### ReRedux: both release ROMs and the qol modules

```sh
# Pillow needed; inputs: build/vanilla_rom/{black2,redux}.nds, build/jp_rom/jp_orig.nds,
# optional: $REDUX_JP_WORK/tr/*.json for JP builds; asset paths in build/redux3.json
# {"essentials": DIR, "hgss": POKEHEARTGOLD/files/data/mmodel/mmodel} (or REDUX_ESSENTIALS / REDUX_HGSS)
python3 build_redux3.py                  # -> build/out/redux3_en.nds, redux3_jp.nds
python3 build_redux3.py --lang en --test # followtest base + example module -> build/out/redux3_test_en.nds
```

EN is Redux → followers → qol modules → icon; JP is Redux → `jp_port.py` → followers (Japanese
talk lines) → qol modules → icon. `--with NAME` adds a disabled module, `--only A,B` builds just
those (plus `core`).

**Memory.** The qol code lives in a 96 KiB ARM9 autoload segment at `0x021FD080` (the end of the
highest main-RAM overlay, B2's vanilla main-arena start); the main-arena start
(`OS_GetInitArenaLo`'s literal at `0x0207B3F0`) moves to `0x02215080`. B2 carves the main arena only
at boot (two GFL root heaps of fixed size), and measured in DeSmuME it leaves 221 KiB unused for the
whole game (title, field, battle, menus, save): with the block, 125 KiB stay unused and no heap
changes. The follower code stays in the ITCM (19.9 of 24 KiB). At `0x021FD080` a header reads
`RDX3`, version, a main-loop frame counter (`+8`) and the used end.

**Adding a module** (`qol/NAME.c` + `qol/NAME.py`, built in name order after `core`; the C code is
Thumb with the followers' flags, `#include "qol.h"`, B2 functions from `followers/syms.ld`,
`qol/qol_syms.ld` or the module's `SYMS`; follower globals are visible too):

```python
# qol/example.py (qol/example.c defines example_frame, example_field_hook)
ENABLED = False                                   # only with --with example (and in --test builds)
FRAME = ['example_frame']                         # called once per main-loop frame by core.c
SYMS = {'sub_203D5E4': 0x0203D5B9}                # B2 functions the C code calls (Thumb: bit 0 set)
PATCHES = [                                       # FieldRoutine_Run's `bl sub_203D5E4` -> our hook
    dict(where='ov36', addr=0x0217FFA6, kind='bl', orig=0x0203D5B9, target='example_field_hook'),
]
# other shapes: dict(where='arm9', addr=LITERAL, kind='ptr', orig=OLD_FUNC, target='my_func')
#               dict(where='ov12', addr=A, kind='bytes', expect=b'\x06\x20', target=b'\x08\x20')
```

`where` is `arm9` (static image), `itcm` or `ovN` (overlay N; its RAM base comes from the overlay
table, the patched overlay is stored uncompressed). Kinds: `bl`/`blx` (Thumb call → Thumb/ARM),
`arm_bl`/`arm_blx`, `jump`/`arm_jump` (replace a function: its entry jumps to `target`, no register
clobbered), `bytes`, `u8`/`u16`/`u32`, `ptr` (symbol address, +1 for Thumb functions). Every patch
must say what it overwrites (`expect=` bytes, or `orig=` the current call target / value); a patch
overlapping another module's or the followers' patched bytes stops the build. `PATCHES` may also be a
function of a context (`ctx.lang`, `ctx.test`, `ctx.rom`), and `files(ctx)` may replace data files
(`tools/gfx5.py`: LZ10, NCGR / NSCR / NCLR and Gen 5 font helpers; used by `qol/statview.py`, `qol/logo.py`).
`ENABLED = False` keeps a module out unless named with `--with`. `HEADERS(ctx)` may return
`{'name.h': text}`: headers generated from the ROM before compiling (e.g. `rules_family.h`, the
species → evolution family table). New message lines:
`TEXTS = [dict(bank=('system', 1), key='MY_LINE', en='...', ja='...')]` appends a line to that
bank in the build's language (after `jp_port` in JP builds; `id=N` asserts the id); the ids reach C
as `TXT_MY_LINE` (`#include "qol_texts.h"`) and Python as `ctx.text_id('MY_LINE')`. Redux's script
files hold raw bytes that don't relocate: patch scripts append-only (see `qol/menu.py`). Each build writes
`build/qol/LANG[_test]/qol_map.json` (symbols, patches) and `qol.map`. `qol/example.*` is a working
example: a FRAME counter and a field-frame counter fed by a redirected call in overlay 36. The tool
alone: `python3 qol_build.py IN.nds OUT.nds [--lang jp] [--with example]` on a ROM with followers.

### ReRedux: EVO/MOVES pages

`qol/evomoves.{py,c}` (summary, overlay 207) and `qol/dexmoves.c` (Pokédex, overlay 298), one module.

**Data.** The evolution graph is baked into the qol block at build time from the ROM's a/0/1/9 (`HEADERS`:
`evomoves_data.h`, 650 species, ~1.9 KB; method 0 slots, e.g. Redux's dead Feebas entry, are dropped). The family
is the root (walking pre-evolutions up) and then depth first; a second method to the same species (Mantyke,
Karrablast, Feebas) is a continuation row. Every Gen 5 method 1-27 has a line (friendship / day / night, level,
trade (+ item / for a species), item (+ gender), Atk vs Def, Wurmple's random split, Shedinja, Beauty, held item +
day / night, known move, party member, gender + level, the three places: Chargestone Cave, Pinwheel Forest, Twist
Mountain from bank 109); item, move, species and place names come from the ROM's banks through word sets. The
learnset is read when the page is drawn with the game's own `PML_LearnsetLvUpLoad` (a/0/1/8, the form's entry
through the personal table), move data with its move-data cache (type, category, power, accuracy, PP), move
descriptions from bank 402. The lines live in summary bank 179 (EN and JP); the build checks that every character
is in the font and that the widest move / type / species names fit their columns (`check_texts`).

**Summary.** Overlay 207 keeps its page in app+0x58 (0 STATUS, 1 STATS, 2 RIBBONS, 3 STATS' move selection) and
runs five per-page steps through jump tables (hide and create in PageRedraw 0x021B49D0, finish-old / finish-new in
the page change 0x021B4AFC, the per-frame update in the main step). Those five tables call `em_hide` /
`em_create` / `em_finold` / `em_finnew` / `em_update` instead, which run the original case for pages 0-3 and
EVO/MOVES as page 4: its windows are created and printed like the other pages' (print queue, then char
transfer), its finish loads the STATUS page's lined memo panel (top), its own label (a/0/7/7 member 181:
NSCR 67 with « EVO/MOVES » drawn in the labels' pixel font into free NCGR 11 tiles; JP in the small font) and its
learnset panel (member 182: NSCR 65 recomposed into eight uniform rows, 9 new NCGR 10 tiles). `em_input` runs
before the app's input step (RIGHT onto the page, LEFT back, A / taps / list keys); everything else is the app's.
App init and exit reset and free the page.

**Pokédex.** The entry screen runs one page module at a time (a table of init / main / exit / input functions
created from the page number by FUN_021A061C); the framework keeps the bottom bar (overlay 298's button manager)
and the top header. EVO/MOVES is page 5: its module (`dexmoves.c`) sets up its layers like the CRY page (the
INFO grid on BG0 of both screens with a green theme from palettes appended to a/1/5/7, our boxes and text on BG2
from bitmaps printed with its own font and print queue), fades in / out with the framework's fade objects,
slides the header in with its own label, and handles the bar's actions as INFO does (pages, leave, next /
previous species, the Y checkbox). LEFT on INFO / RIGHT on FORMS (on CRY without FORMS) and a tap on the EVO
capsule ask for page 5: the next action read becomes another page's (the running module ends itself) and the
module switch takes page 5. The capsule is drawn on the bar's BG (the vanilla capsule, active / inactive,
`evomoves_capsule.h`, palette rows 9-11, tiles 480-503 of the bar's free chars): the entry bar's buttons are moved
so that five page capsules keep the vanilla spacing (UP x 0, DOWN 20, INFO 40, AREA 72, CRY 104, FORMS 136, EVO
168, checkbox 202, X 217, back 235; with three page capsules they take the four-capsule spots and EVO follows).

**Base stats** (`qol/dexstats.c`, same module). The INFO page module's table (overlay 298 `0x021AC3D4`: init, main,
exit, input) gets our main and exit around the vanilla ones. Vanilla INFO keeps its top screen empty unless a
foreign-language entry is chosen: overlay 296's second info panel then shows it there (sub BG 2 and 3 on, BG 0
scrolled to the card); while hidden, BG 2 is off. After INFO's own setup we allocate 601 tiles from frame 6's
(sub BG 2) GFL char allocator, print the box into a 30 x 20 tile bitmap with INFO's font and our print queue
(bank 179 lines, ability names from bank 374), load the stats palette (a/1/5/7, appended) into palette row 14 and,
while no foreign entry is shown, write our map straight into BG 2's screen in VRAM and turn BG 2 on. GFL's screen
buffer of frame 6 keeps the card's map: a foreign entry (or the page's exit) gets it back with GFL_BGSysLoadScr, so the
foreign card is untouched. Values: `PML_PersonalGetParamSingle(species, form, param)` (params 0-5 stats, 26-28
abilities) for the form the entry shows (`0x0200D3C8`, as INFO's own `FUN_021A3004` asks). INFO's fade-in waits for
our first print (at most 30 frames; in practice 0). Never more than the entry's heap can spare (the setup is skipped
with less than 31 KB allocatable; measured 89 KB free, 65 KB after).

Tests (`build/scripts/evomoves/`, py-desmume, `build_test.py` builds em_LANG test ROMs with `qol2_test`):
`t_first.py`, `t_views.py` (20 showcase species, family and learnset checked against the ROM data),
`t_egg_pc.py` (eggs skipped / never shown, the PC Box summary), `t_sweep.py` (every species 1-649 and form on the
summary page, 731 pages), `t_dex.py` (Pokédex navigation: keys, capsule, touch, species change, other pages after
ours), `t_dexsweep.py` (every species on the Pokédex page), `t_dexstats.py` (base stats: showcase species incl.
HP 255 / Def 230, eight forms, seen-only, a foreign entry and back, the other pages, the FORMS page's choice, the list),
`t_dsweep.py` (every species' base stats on INFO). `EMU=melon` runs any of them in the headless melonDS (`melemu.py`:
the same driver API on bfix's libbf, which emulates the MPU, so a NULL / wild pointer data-aborts as on hardware;
`par.sh` lists any abort): t_first, t_views, t_egg_pc, t_dex, t_dexstats and sweeps pass in both emulators.

### Final QA (ReRedux)

The scripts below now live in `redux/tests/` (same directory names) and are normally run through the
regression runner (see **Testing**); they still run one at a time from their directory, as listed here
(emulator venv: py-desmume; results in `build/qa/`, contact sheets `*_sheet.png`):

```sh
sh rebuild_twice.sh                 # both ROMs twice: SHA-1 equal (deterministic) + QA test ROMs (build_test.py)
python t_newgame.py en def          # real intro + settings menu defaults (rel ROM); jp too; `nuz test` for the rules
python t_story.py en                # bedroom -> key bearer -> starter (follower) -> rival -> Pokémon Center -> Route 19
python t_smoke.py en                # auto-run, R turbo (field/battle), follower talk, catch, heal, Mart, menus, save
python t_continue.py en [unova]     # Continue (no C-Gear prompt) / Unova Link (Challenge Mode)
python t_rules.py en                # the rules agent's battle scenarios on the QA test ROM
python t_extra.py en                # JP/EN Fairy label, large follower recall/release at a gate, follower Surf
python t_texts.py                   # settings-menu texts vs. behaviour (turbo hint), JP glyphs
```

`qa.py` drives DeSmuME. It gives every run its own battery save (an old `.dsv` is moved aside),
and its `nav()` walks a BFS path over the maps' permission grids (`perm.py`). The qol2 agent's suite
(`build/scripts/qol2/t_*.py`) runs on the QA test ROM as kind `qa` (symlinks `build/qol2/qa_LANG.*`,
`build/qol/qa_LANG`).

Extended pass, `build/scripts/qa2/` (results `build/qa2/`): `build_qa2.py` (QA2 ROMs: release modules +
`rules_test` with a CUSTOM bed-menu row that runs any script commands the test writes into it, +
`qol2_test` mailbox: params, language + Pokédex, bike, Bag counts), `regen.sh` (ROMs + bedroom states),
`par2.sh` (parallel runs), `t_menu.py LANG def|custom|nuz` (the settings menu: pickers, B, preset,
recap, flags/vars/KeyInfo), `t_view.py` (SELECT settings view), `t_limit.py` (species limit),
`t_nuz.py LANG revive|egg` (revived-in-battle release, held item to the Bag, egg nickname),
`texts_check.py` (widths and glyphs of every rules/menu text).

### ReRedux: loading

`qol/loadspeed.{c,py}`. Measured frame-exact in a headless melonDS (interpreter, the core Watermelon DS uses)
and in DeSmuME 0.9.12, from the input (battles: the last lit battle frame) until the field is lit and free
(`build/scripts/warpspeed/`: `ws_measure.py`, `table.py`; saves in front of Aspertia's Pokémon Center, house
429's stairs, the Aspertia gate, Route 19 / 20 for battles). EN and JP give the same numbers (±6 f, gate).

| melonDS (DeSmuME) | Redux 1.4.1 | before | after | change |
|---|---|---|---|---|
| Pokémon Center door, in | 221 (230) | 197 (207) | 111 (117) | −44% (−43%) |
| Pokémon Center door, out | 224 (227) | 202 (209) | 117 (120) | −42% (−43%) |
| stairs, up / down | 132 / 130 (135 / 133) | 119 / 117 (124 / 121) | 87 / 86 (91 / 90) | −27% (−27%) |
| gate, in / out | 183 / 181 (193 / 185) | 179 / 172 (189 / 179) | 101 / 98 (114 / 103) | −44% / −43% (−40% / −42%) |
| wild win / run → field | 158 (159) | 114 (114) | 70 (72) | −39% (−37%) |
| trainer win → field | 159 (162) | 115 (117) | 72 (75) | −37% (−36%) |

Speed-ups off: door 175 / 177, battle 113 (the always-on parts below).

**Where the time went** (melonDS cycle profile of the load, EventFieldClose → EventFieldOpen done; door in, before
→ after): 86 → 47 frames.
- Card reads 1.0–1.7 MB per map change (the 344 KB field overlay 36, map models and textures, the 170 KB field
  effects archive a/0/7/4, NPC sprites, the next BGM). Black 2's header asks for the SDK's slow "1TROM" card
  timing (1623 card clocks before each 512-byte page) and the CPU polls the card meanwhile: 41.6 → 15.8 frames.
  DeSmuME doesn't time card reads, so it gains nothing here.
- Entering a Pokémon Center the medal checks read every box slot and ~105 trainer records, each read decrypting
  and re-encrypting a Pokémon or the whole record block: 15 → 6.4 frames.
- Idle frames (one 30 Hz event update per state): 9.5 → 7.
- After the load the game waited for the old music's fade-out: its 60 sound frames are counted in main-loop
  frames, which nearly stop while a map loads, so ~35 frames of black or frozen picture were left (door in and
  out, gates). Now 0.
- Gates: the electronic sign's bitmap re-layout did 4 library divisions per byte: 15 frames → 1.

**What changed.** Always on (nothing looks or sounds different):
- ROM header card timing: the SDK's "MROM" values (0x60 0x00586000, 0x64 0x001808F8, 0x6E 0x051E; were 0x00416657 /
  0x081808F8 / 0x0D7E). 10720 → 2740 bus cycles per page. MROM is one of the SDK's two retail settings (mask-ROM
  carts), so flashcarts and emulators handle it (`qol_build.py` modules can declare `HEADER` patches).
- Pokémon / record crypto and checksum loops (0x0201ECDC, 0x0204411C, 0x0201ED28, 0x02044100) in ARM, a word at a
  time; same results (`crypt_check.py`, the fast-save integrity tests).
- The gate sign re-layout (ov12 0x0216A004) with counters instead of divisions; same bitmap (screens compared).
Under the speed-ups flag:
- The music change of a warp fades out in 30 sound frames, not 60, and for a door it starts as the door opens
  (DoorEnterSeq state 0 instead of 6). It still fades out completely before the next BGM; recordings of every
  transition show no abrupt cut (`wavcheck.py`).
- EventMapChangeCore, EventFieldOpen, EventFieldSndWait, the building fade-in's last steps (touch-screen
  palettes, tiles and map now in one frame) and DoorExitSeq's black part run their steps in one update.
- Coming out of a door the camera trace is stopped at once instead of replaying its queue (12 frames of black;
  the player stands still, so the camera ends where the replay would).
- Not changed: door / walk / zoom animations, sound effects, the battle side (`battleexit`).

### ReRedux: fast save

`qol/fastsave.{c,py}` (under the speed-ups flag; quick save is flag 0x5DD).

**How vanilla B2 saves.** The GFL backup engine is at arm9 `0x0203B9BC`, and EventSave state 9 runs one step of it per
30 Hz update.
1. It reads the whole save copy at flash `[sd+0]` back from the card, 2 KB per step (73 blocks, 150 KB, about 50–80
   frames in DeSmuME). It compares that with RAM to find the blocks that changed.
2. For each copy in turn, it writes every changed block whole: the data, a u16 counter and a CRC16. Then it writes
   the CRC table, the header (with the save counter) and the commit byte. The SDK verifies each 256-byte page it
   writes, and a page takes 1–2 frames.

There is no fixed per-frame wait. All of that time is card I/O.

**What fastsave changes.** B2's write order, both copies, the CRCs, the counters, the commit byte and the verify all
stay as they are.
- **Known contents.** Fastsave keeps two 32-bit hashes per block and per 256-byte page of both copies.
  - A block or page becomes known when the loader reads it whole at Continue (copy A into the save buffer, copy B
    into scratch).
  - It also becomes known when the card compares it equal, or when a save that completes both copies writes it and
    RAM still hashes the same afterwards.
  - Fastsave forgets a block or page when any other card write touches it (`fs_guard` at the card-write entry
    `0x0203C07C`), or when a save fails or is cancelled.
  - It forgets everything when copy A's CRC table, header or commit byte differs from what the last save wrote. It
    reads these back at every save start, which catches an emulator savestate loaded without its save file.
- **Compare.** A known block whose hash matches is "unchanged", and a known block that doesn't match is "changed",
  both without a card read. Unknown blocks are compared on the card as before.
- **Writes.** For a changed block, fastsave writes only the pages that the target copy doesn't already hold, one card
  write per run of pages in ascending order. The last page, which holds the counter and CRC, is always written.
  Flash ends up byte-identical to a whole-block write.
- **Fixed waits.**
  - The save step runs for about 0.5 frame per update, or about 2 frames while it compares on the card.
  - The texts print at once, and the yes/no's choice doesn't blink.
  - The progress dots fill as soon as the write ends.
  - There's no wait for the save jingle; it keeps playing.
  - "X saved the game." stays for 15 updates instead of 45.
  - Quick save also skips the question.
- **Moved here.** qol2's save-steps and quick-save thunks, and speed's "saved box" runtime patch, now live in
  fastsave.

**New Game over another save** (not gated; `fs_ow_check`, ov12 `0x02163C44`). Vanilla B2 keeps two flags in
SaveControl (`*0x02140F60`): +0 "new game" (set by the title's New Game `FUN_0200749C`, cleared when a save
completes) and +1 "a save was loaded from the card at boot" (`FUN_02007324`). EventSave state 4 (after YES) calls
`FUN_0200746C` = +0 && +1, and refuses with bank 208 msg 8 "There is already a saved game file. It is impossible to
save." (state 0x0E). No ID is compared with the card: it is RAM state only, so the game can never be saved (and an
emulator savestate keeps refusing whatever save file is next to it) until the card is erased at the title
(Up + SELECT + B).
- The scripted saves (common script 1230 scr_3: Mom's mandatory first save, the key bearer, ...) make the same
  decision in script: `SaveDataGetStatus` (cmd 0x138) copies +1/+0 into 0x8026/0x8027 *before* "Would you like to
  save?", and YES with both set prints msg 9, the refusal. Mom then asks again, forever, so such a game can't even
  leave the house.
- ReRedux asks "There is already a saved game file. Overwrite it with this new adventure?" (`TXT_FS_OVERWRITE`,
  story 208) with a yes/no instead, in both places: the menu save (`fs_ow_check`, also with quick save on) and
  the scripted save (1230 scr_3's `MsgSystem 9` → a stub appended to the file; YES goes on to `SaveDataWrite`).
- YES (menu save) clears +1, so the save runs exactly as the first save of a new game on an empty card: New Game marked every
  block changed, both copies, the CRCs, the footer and the commit are written. Fastsave's table follows the card as
  for any save (it was seeded from the old save at boot; a card that changed underneath is caught by the footer
  check).
- NO closes the menu (or, at Mom, takes the vanilla refusal path, and she asks again); nothing is written and the
  next save asks again.
- A Continue'd game (+0 = 0) and a new game on an empty card (+1 = 0) never see the question.
- Other refusals of the same check (ov140, ov199 link/feature saves) stay vanilla until the first menu save.
- Tests (`build/scripts/fastsave/ow.sh`):
  - `t_overwrite.py`: prep (old save → New Game → bedroom), then save yes / no / quick / vanilla, then boot
    (Continue = the new game, then a normal save, then a 2nd cold boot), and cont (Continue the old save: no
    question).
  - `t_owmom.py`: Mom's scripted save, yes and no-then-yes.
- Rescuing a melonDS savestate from such a game: emulator savestates (melonDS `NDCS`, DeSmuME too) carry the
  card's contents, so loading one rewrites the old save. Clear +1 in the state's main RAM (`NDSG` section, RAM
  at file offset 0x24). The script has already cached the status, so at Mom answer NO once, then YES; the
  whole new save is then written.

**Measured** (DeSmuME, frames from touching SAVE until the player can move again). The save is the first one after
Continue from a battery save in the player's room, after walking two steps. The phases are: menu → panel switch →
question → yes/no → prep + "Saving…" → write → SE + "saved" text → box → close.

| ROM | phases | total |
|---|---|---|
| EN before | 21 · 22 · 18 · 24 · 25 · **186** · 47 · 92 · 13 | **448** |
| EN after | 21 · 22 · 6 · 10 · 25 · **45** · 12 · 32 · 13 | **186** |
| EN quick save, before → after | yes/no 2 → 2, write 208 → 49 | 448 → **180** |
| JP before → after | the same phases | 446 → **186** |
| JP quick save, before → after | | 444 → **180** |
| EN, nothing changed | write 112 → 33 | 390 → 174 |
| EN, 1 Pokémon put in a box | write 239 → 57 | 501 → 198 |
| EN, 75 Pokémon in 3 boxes + item + flag | write 403 → 202 | 665 → 343 |

What's left:
- The menu, panel and close phases are the start menu and the sub-screen loading its panel.
- The prep phase is the player's save pose.
- The box phase is the 0.5 s the confirmation stays up.

**Integrity tests** (`build/fastsave/`, py-desmume):
- `integ.sh SNAP LANG NAME MODE [quick|speedoff|stale]` changes something, saves, and checks that both copies in
  the exported battery equal the RAM save buffer block by block, with valid block CRCs, CRC table, header and commit
  byte. It then cold-boots the battery, checks Continue, position, flag, bag, boxes and that every block equals the
  saved one, and saves and checks once more.
- `stale` simulates a savestate loaded without its save file. The boxes come back while fastsave's table is rolled
  back. `stalenocheck` shows that the footer check is what catches it.
- `t_newgame.py` covers the whole-save write after *New Game*.
- `matrix.sh` and `matrix2.sh` produce the numbers above.

### ReRedux: field timing (smooth steps, input latency)

Measured with `build/feel/` (melonDS core headless with a 3D swap counter, `feel/melon/`; DeSmuME 0.9.12),
the user's save teleported to Aspertia, Floccesy, Virbank and Route 19 (`teleport.py`: GameData's
location is rewritten before the field is built).

**Steps.** B2's field logic and 3D both run at 30 Hz (one update per two frames). The camera follows the
player, so the world scrolls by the player's step per update, and the DS rasterizer has no sub-pixel
precision.
| | walk: units per update | run: units per update | follower gap while running |
|---|---|---|---|
| vanilla / Redux 1.4.1 | 2 (16 f/tile) | 4 (8 f/tile) | – |
| ReRedux 1st | 2.3125, 6 × 2.28125 (14 f) | 5, 6, 5 (6 f) | 21 / 22 units, alternating (1-unit wobble at 10 Hz) |
| ReRedux 2nd | 4 (8 f) | 8 (4 f) | 24 units, constant |
| ReRedux now | 4 (8 f) | 5, 5, 6 (6 f) | 21 units, constant (walking 20) |

A 6-frame run can't be even: 16 units in 3 updates. 5, 5, 6 is an even 5⅓ units per update rounded to
whole units (at most ⅓ unit off). Fractional camera positions would not help: every vertex would then be
rounded to a pixel on its own, so the scene would shimmer instead of shifting. 7 frames per tile would be
worse (tiles of 4 and 3 updates: 4 and 5⅓ units per update). The follower used to wobble because it starts
each tile one update after the player and walked the same 5, 6, 5 table; now the player's run has its own
5, 5, 6 table (the four run start functions rewritten in place, `speed_rtp.h`) and the follower walks
acmd 0x50 (5, 6, 5) one update later: both move by the same amount in every update (gap 21 units in every
picture in Aspertia, Floccesy, Virbank and Route 19, also with turbo).
Screen steps per picture at the player's feet (block match): Floccesy (≈ 1 px per unit) Redux running
4 px (89%), ReRedux 5 and 6 px (44 : 29, two 5s and a 6 per tile); Virbank (≈ 1.25 px per unit) Redux 5 px
(92%), ReRedux 6 and 7 px (95 : 45); Route 19 Redux 5 px (89%), ReRedux 6 and 7 px (33 : 20). Walking: 4 px
(Floccesy 76%), 5 px (Virbank 85%).
No lag frames (main-loop frame taking 2 VBlanks) in Aspertia, Floccesy and Virbank; on Route 19 one
picture is held 3 frames at a block crossing (the map streams in the next blocks), as in Redux. The 4-frame
run (ReRedux 2nd) held 3–5 pictures per 20 tiles there. No follower or actor drop-outs (polygons per swap
180–480 of 2048). The follower is drawn every frame; it bobs (B2's / HGSS's time-based 10-update cycle,
independent of steps).

**Emulator load** (a headless melonDS runner, per frame: ARM9 busy / halted cycles with a PC profile in the
interpreter, host time with the JIT, 3D polygons, VRAM texture writes, card bytes, audio samples; same save
and places, standing and 20 tiles of running, Redux 1.4.1 vs ReRedux):
- The game reaches its VBlank halt in every frame except the map-streaming frame on Route 19 (Redux
  too). Audio: 547–549 samples in every frame; nothing touches the sound side (ARM7). The mask-ROM card
  timing only shortens the ARM9's card polling (a map block streams in 2.4x the bytes per update).
- ReRedux had added 35k ARM9 cycles per frame standing (+3.2% of a frame, every frame; Aspertia: Redux
  44.3% busy, ReRedux 47.5%): the follower's party lookups (~27k: each PokeParty_GetParam decrypts the
  whole Pokémon, ~12 calls per tick; now cached on a hash of the party's bytes, talk.c) and the runtime
  patch checks (15k; now the first entry of each group, speed.c). Now +9k (45.1%), mostly the follower
  actor itself. Running: Redux 45–52% busy per frame, ReRedux 47–53%; the low-latency updates (turbo.c)
  do the same work as 45 / 66% in alternate frames instead of ~55 / 55.
- Host time per frame (JIT, one Apple core, software 3D): Redux 2.5–3.4 ms, ReRedux 2.1–3.2 ms (noise
  level); 3D polygons +2–5 (the follower); texture writes the same.

**Latency** (frames from the key going down at a frame start to the first changed picture, averaged over
the 8 phases of the 30 Hz update; melonDS / DeSmuME):
| | vanilla B2 | Redux 1.4.1 | ReRedux before | ReRedux 2nd | ReRedux now (re-phase) |
|---|---|---|---|---|---|
| start moving, facing that way | 3.5 / 3.5 | 3.5 / 3.5 | 3.5 / 3.5 | **2.5** / 2.5 | **2.0** / 2.0 |
| start running in a new direction (vanilla: B held) | 3.5 / 3.5 | 3.5 / 3.5 | **10.0** / 10.0 (turned first) | **2.5** / 2.5 | **2.0** / 2.0 |
| start walking in a new direction (turns first; first step on screen) | 9.5 / 9.5 | 9.5 / 9.5 | 3.5 / 3.5 (B held: no turn) | 9.0 / 9.0 | 8.5 / 8.5 |
| X → menu | 2.5 / 2.5 | 2.5 / 2.5 | 2.5 / 2.5 | 2.5 / 2.5 | **2.0** / 2.0 |
| A closes a text box | 1.5 / 1.5 | 1.5 / 1.5 | 1.5 / 1.5 | 1.5 / 1.5 | **1.0** / 1.0 |
| R turbo on: start moving | | | 2.0 | 2.0 | 2.0 |

(ReRedux 2nd and now: Floccesy away from the block-middle lines, EN and JP alike; next to such a line the
update before a crossing hands over to split updates and the latency is vanilla's there. Where a combined
update doesn't fit, as in DeSmuME in busy towns, too.)
- **Re-phase on a new press** (`turbo.c` turbo_skip_hook, with the low-latency updates): the 0–1 frame
  wait for the 30 Hz key latch is gone when the player stands. A new press (any key but R) in the idle
  frame of a combined update runs that update at once: GSYS_Update's `GameData_Is30FPSSkipFrame` call
  (`0x020169C2`, before the events) latches the keys as `GFL_HIDUpdateKeypad` does, the events run, and
  the field routine call runs the combined update. Events → Run → Alt stay once per update in vanilla
  order; the 30 Hz cadence moves a frame earlier (the picture before is shown 1 frame). That frame is paid
  back (one idle frame more: a picture held 3 frames) once the player stands with no key held and no event
  runs, so the game is never more than a frame ahead. Checked in melonDS with `build/w/replay.py`: the
  same savestate, a random 2,400–3,600-frame key script (taps, holds, X / B menus, A) recorded with
  re-phase and replayed per update without it: every actor's position and facing equal in every update
  (5 scripts, ~1,800 updates each, 4–12 re-phases), each update at most 1 frame earlier, update rate equal
  (29.6–29.8 per 60 frames both ways; menus pause the field).
- Auto-run used vanilla's walking rule (turn on the spot first, 8 frames) for running: fixed
  (`qol2.c` qol2_turn_hook in FUN_0219BBA8: B held = walk turns first, running doesn't, except a tap
  toward the follower, which is pass-through, so that you can still face it to talk).
- The rest is B2's pipeline: the key is latched by the 30 fps HID latch at the start of a Run frame
  (0–1 frame wait), Run moves the player and draws the first half of the 3D, the Alt frame draws the
  second half and requests the swap, the next frame shows it. `turbo.c` (speed-ups on, turbo off)
  runs Run + Alt in one frame and idles the next, which saves the Alt frame. A combined update costs
  turbo's frame (both halves); where it doesn't fit the game uses the split (in DeSmuME, whose ARM9
  is slower, almost always: latency as vanilla there). The hand-overs: see turbo.c. Measured in melonDS
  while running: 70–90% combined updates in Aspertia / Floccesy streets, 15–30% in Virbank; all swaps 2
  frames apart (0 held pictures in 1,600 frames).
- Menus (X) and text boxes are 2D, drawn by the event VM / sub-screen: unchanged and as fast as vanilla.

### ReRedux: 60 fps field

Module `qol/fps60.c` (in both release ROMs, always on). The field logic stays at 30 Hz; every frame draws a whole
3D picture instead of half of one.
- **What B2 does.** One 30 Hz update = two frames. Run frame: input, actors, effects, camera, then
  `Field_RenderStart` (camera transform, `FieldG3D_RenderPhase1`: fog, light, camera flush, map chunks).
  Alt frame: map loaders, sub-screen, then `FieldG3D_RenderPhase2` (BlAct billboards in three scenes
  (+0xC0/+0xC4/+0xC8), field effects, G3D objects, weather, particles, 3D cut-ins) and the swap request.
  Polygon RAM holds one complete picture; the rasterizer keeps showing it until the next swap.
- **60 fps.** Run frame: camera transform (once per update, as vanilla), then phase 1 + phase 2 + swap of a
  midpoint picture: G3D camera look-at position / target, every BlAct position, every translation passed to
  `NNS_G3dGlbSetBaseTrans` by `GFL_G3DSysDrawObj` / `DrawObjBBoxCull` and the frame of every NNS animation of
  the drawn models (`NNS_G3dDraw` in GFL's render-object draw: water scrolling, doors) put halfway between
  the last real picture and now, then restored. Alt frame: phase 1 + phase 2 + swap of the real picture
  (recorded). Sprite (billboard) animation frames stay as they are; particles, weather and 2D are drawn as
  they are (30 Hz). A value that moved more than 12 units (actors, objects; the bike moves 8 per update),
  32 (camera) or 4 animation frames per update is a cut / a reused slot: drawn where it is now.
- **No side effects.** The midpoint picture's `GFL_PTC_Main` (SPL draw + calc of every particle manager,
  called by phase 2) only draws, so particles still advance once per update. Checked with the test module
  `qol/fieldpark` (`--with fieldpark`: the ARM9 parks after every field update until the harness reads RAM;
  `build/w/rampark.py`): main RAM after every update equal with the 60 fps draws (+ re-phase) on and off,
  EN and JP (Floccesy + X menu, Aspertia + X menu, Virbank, Route 19, Route 20 grass, a sign's text boxes;
  165–234 updates each; fps60's own data aside), except in 4–6 updates per run, the same ones whatever the
  keys, where an OS tick value and a few timing scratch words differ and are equal again the next update.
- **Cost.** A whole picture took 90–170 of the 263 scanlines (melonDS; more under its JIT), so with the
  Run frame's logic (25–100 lines) the frames ran at 75–99 % busy (JIT) on Route 20 and in Virbank. Two
  changes made every picture cheaper: during the field's draws NNS sends each display list with one
  GX-FIFO-mode DMA (`NNS_G3dGeUseFastDma`, flag 0x0214697C, set around the draws; B2 otherwise feeds them in
  472-byte DMA chunks with a GXFIFO interrupt each, ~75 lists per picture; the GX DMA is channel 3, the lowest
  priority, so it holds no other DMA back): a quarter of a draw saved, every picture pixel-identical; and the
  engine-wide HBlank gating (`qol/perf.c`, below). fps60's own bookkeeping only looks at the billboard slots /
  3D objects / animations the last real picture used (lists instead of whole-table scans).
- **Time budget** (per frame, no cool-downs). The midpoint picture is drawn only when the scanlines left
  before the VBlank cover the longest of the last 4 whole draws + 10 lines (the rest of the main loop takes
  ~5); otherwise only that one frame keeps the last picture, and the next update's midpoint is drawn again as
  soon as it fits. The real picture is always drawn. Overruns of the game's own (a map block read from the
  card: ~330 lines of logic in one Run frame, vanilla lags there too; a script) are counted and cost nothing
  else. Before, two such overruns within 2 s switched to 30 fps drawing for 1 s, doubling up to 30 s and only
  reset in a new map -- on the long overworld (Route 20 ↔ Floccesy ↔ Virbank is one field) a few block
  crossings left it at 30 fps for half a minute: the drop seen at the Route 20 bridge. Now only real pictures
  that don't fit in their own Alt frame twice within 1 s (a slow emulator) switch to vanilla split drawing
  (phase 1 in Run, phase 2 in Alt, both timed), and it switches back as soon as a whole picture fits in the
  Alt frame for 3 updates in a row (at the latest after 10 s); R turbo draws as vanilla too. Vanilla drawing
  still records the real pictures, so switching back is seamless. No midpoint picture when nothing moved
  (camera, billboards, objects, animations; no particles or weather) or in the update that starts an event
  (the X menu loads its graphics then).
- **Re-phase** (with `turbo.c`): a new press in the Alt frame runs that update's Alt half in
  `turbo_skip_hook` without its picture, then the next update's events and Run with its midpoint picture
  in the same frame (vanilla order Alt N → events N + 1 → Run N + 1; paid back like the low-latency one).
- **Measured** (melonDS, user's save; Castelia reached through a side street's warp: `build/w/teleport2.py`
  rewrites every RAM copy of the saved location, so zones outside the overworld matrix load): 60 swaps/s and
  60 distinct pictures/s while moving; screen steps 2–4 px per picture instead of 5–7; 0 lag frames, 0
  overruns, nothing left out. ARM9 busy % mean / max per frame moving (vanilla drawing): Aspertia 62 / 82
  (47 / 65), Floccesy 58 / 76 (46 / 60), Virbank 70 / 86 (52 / 67), Route 19 55 / 68 (43 / 53), Route 20
  54 / 66 (44 / 52), Castelia main street walking 61 / 81 (49 / 70), Castelia side street 51 / 62
  (41 / 50); standing 46–77 (37–53). Latency (key down → first changed picture, 8 phases): start moving /
  running / turning then running / X menu 2.0 frames, A on a text box 1.0–1.5 (the 30 fps build before:
  2.5 / 2.5 / 2.5 / 1.5; melonDS and DeSmuME, EN and JP). DeSmuME 0.9.12
  (slower ARM9): game speed 100%, mostly real pictures only (≈ 30 fps), occasional vanilla fallback.
  Logic: replays of random key scripts (same savestate) with and without re-phase / with the 30 fps
  low-latency drawing: every actor equal in every update. Audio: the same sounds in the same updates; a
  sound command reaches the ARM7 up to ~10 ms later in a frame (the sound flush comes after the field's
  draw, as the frame's load already varies it in vanilla).
- **Measured again with the benchmark** (`rr.py --perf`, Testing → performance; ARM9 busy % per frame mean /
  p90 / max, melonDS JIT; interpreter mean in brackets; before → after the cost / budget / gating changes):
  Route 20 bridge 75 / 85 / 91 → 47 / 58 / 70 (66 → 41), its other bridge 63 → 33, the bridge in autumn
  (falling leaves) 75 / 89 / 98 → 50 / 75 / 90 (67 → 43; midpoints left out 12 → 0), its grass 68 → 42,
  Virbank 81 / 97 / 100 → 64 / 81 / 93 (74 → 50; left out 13 → 0), Aspertia 75 / 88 / 96 → 45 / 58 / 70,
  Floccesy 72 → 44, Route 19 69 → 40, a Castelia street (645 polygons, 2311 vertices) 67 / 76 / 85 →
  39 / 50 / 63. 690 frames over Route 20 in autumn: 30 updates (1 s) of 30 fps fallback → none, 3 midpoints
  left out (the frames after the two card-read lag frames, which vanilla has too). Polygons ≤ 645 and
  vertices ≤ 2311 everywhere measured (limits 2048 / 6144): never the limit.
- **Logic identity** of the changes (`perf/desync.py`, fieldpark ROM, interpreter and JIT, Virbank / Route 20
  autumn bridge / Route 20 grass (a wild battle starts in the same update in both runs) / Aspertia, 97–150
  updates each): field actors, GSYS, the field and GFL's RNG equal in every update with the HBlank gating, the
  GX-FIFO DMA and the 60 fps draws each on / off and all three together; the only other GameData-window
  difference is the play-time seconds counter (real-time clock) ticking one update apart.

### ReRedux: engine speed-ups

Module `qol/perf.c` (both release ROMs). **HBlank interrupt gating**: GFL keeps the HBlank interrupt on all the
time -- 263 interrupts per frame, each entering the OS dispatcher (ITCM), saving and restoring the divider / sqrt
context (`CP_SaveContext` / `CP_RestoreContext`), running GFL's HBlank task manager and rescheduling threads on
the way out -- while that task list is empty nearly everywhere (the field, menus). Measured: ~150k of the
~1.1M ARM9 cycles per frame (13 %) outside the draws. While the list is empty the interrupt is masked (IE bit 1,
checked once per main-loop frame); the GFUser HBlank task add (0x02005680, the only way a task is added) unmasks
it immediately (stale request cleared), so every task runs on the same HBlanks as before. `perf_dbg.off = 1`
turns it off (tests). Everywhere in the benchmark: ARM9 busy −14 to −18 points on its own (interpreter; JIT
−9 (Virbank) to −23).

**Fast display-list DMA outside the field.** The SDK's FIFO-triggered transfer mode is now enabled
throughout the game, including battles. It sends the same geometry commands in the same order with
fewer FIFO interrupts; it does not add animation updates, shorten scripts, or change sprite poses.
The 60 fps field renderer already selected this mode around its draws. `perf_dbg.slow_dma = 1`
(byte +2) restores stock transfers outside those field draws for paired tests.

In matched local wild/trainer battle replays, ARM9 busy cycles fell by 9.3–9.8% with melonDS JIT and
5.1–5.2% with its interpreter. The JIT battle state and update counts matched on every sampled frame.
The trainer replay matched both screens throughout; the wild replay differed only in the blinking
clock colon on the lower screen. Ten field scenes in both modes retained identical pictures and
missed-frame counts. These are emulated CPU measurements, not a measured Android FPS or battery
improvement; existing loading/presentation stalls still need device validation. Reproduction tools:
`tests/perf/battle_perf.py` (copied QA battery save, fixed RTC and inputs) and
`tests/perf/dma_check.py` (same-ROM field states, old/new transfer mode). See
`notes/fast-dma.md` for the retained evidence and limits.

### ReRedux: on-screen FPS counter (debug builds only)

`build_redux3.py --lang jp --with fpscounter` (module `qol/fpscounter.c`, `ENABLED = False`: never in the
release ROMs) draws `P U flags` in the top-left corner of the top screen, refreshed every 60 VBlanks: P = 3D
pictures per second (swap requests the main loop issued: 60 = fps60 draws every frame, 30 = vanilla rhythm),
U = field logic updates per second (30; 60 under R turbo), flags F fps60 fallback on, T turbo on, L in-between
pictures left out for time this second, S left out because nothing moved. 16x16 OBJs in OAM 118..127
(palette 15, glyphs at the top of bank E), rewritten after every VBlank wait; shown while bank E is the main
OBJ VRAM in 1D mapping (field, menus). P counts submitted pictures: standing still they may look alike.

**Counter limits:** P counts the game's swap requests over 60 **emulated** VBlanks. It cannot see the host
emulator skipping a render, repeating a picture, or delivering pictures unevenly; it is not a wall-clock FPS
or latency measurement. `60 30` is the intended field rendering/logic ratio, but does not by itself prove
smooth output. Check host presentation separately before changing the ROM's frame budget.

**Odin 3 / WatermelonDS 0.8.0.rc3 check (2026-10-22):** the connected device used Vulkan at 6x native,
automatic frame skipping, and a display forced to 120 Hz. Native logs reported skipped renders despite the
ROM reading `60 30`; five 2-second log windows recorded 27 render skips, average work 10.43 ms, average
window p95 24.11 ms, and a worst frame of 28.44 ms. Turning frameskip off stopped those deliberate skips.
Lowering resolution to 3x alone still left long native work timings. An exploratory recording comparison
from the same Route 20 bridge save state, replaying six right/left pairs, measured the following capture
and picture-change intervals (these alone do not establish the cause of perceived sluggishness):

| Renderer / resolution / display | Captured interval p10 / median / p90 | Picture-change gaps under 12 / 12–22 / 22–50 / over 50 ms |
|---|---|---|
| Vulkan / 3x / 120 Hz, frameskip Off | 8.96 / 16.57 / 22.80 ms | 56 / 462 / 61 / 12 |
| OpenGL / 3x / 120 Hz | 7.61 / 8.21 / 8.90 ms | 132 / 220 / 146 / 11 |
| OpenGL / 3x / 60 Hz | 16.10 / 16.70 / 17.37 ms | 0 / 496 / 0 / 11 |
| OpenGL / 6x / 60 Hz | 16.40 / 16.69 / 17.15 ms | 0 / 548 / 0 / 13 |

The input script deliberately stops between directions; long picture-change gaps include those stops.
The picture-change test is a mean grayscale difference heuristic, with the counter excluded. Screenrecord
observes captured output, adds some load, and does not measure physical scanout or button-to-photon latency.
These are short device runs, not a guarantee for every map, loading transition, menu or battle. The final
device settings were **OpenGL, 6x, frameskip Off, 60 Hz**, retaining JIT and threaded rendering. Original
battery saves were checked byte-for-byte; a spare state preserved the test's starting position.

To inspect a device recording without converting it to a fixed frame rate (requires ffmpeg, ffprobe and
the emulator Python's numpy):

```sh
# Record while moving through the affected area. Start from the same state for each comparison.
adb shell screenrecord --size 1280x720 --bit-rate 8000000 --time-limit 18 /sdcard/perf.mp4
adb pull /sdcard/perf.mp4 redux/build/odin/perf.mp4
# This crop matches the tested custom Odin layout. Adjust it for other layouts; exclude the FPS counter.
python3 redux/tests/perf/presentation.py redux/build/odin/perf.mp4 \
  --crop 0,61,796,596 --ignore-top 25 --ignore-bottom 12 --out redux/build/odin/presentation.json
```

The report separates recording intervals from picture changes, retains long gaps, and exports the individual
change times for inspection against the input script. Input-command, video and native-log clocks are not
synchronized to individual frames. The headless `--perf` benchmark measures emulated work; it cannot
measure Android presentation or establish the cause of the user's perceived sluggishness.

**Repeated renderer/underclock study (2026-10-22):** the short clips above were exploratory. The follow-up
held refresh rate at 60 Hz, resolution at 6x, frameskip Off, JIT/threaded rendering on, and the same fan and
Odin performance modes. WatermelonDS 0.8.0.rc3 and ClusterTune 0.3.1; the JP ROM was `3ed14622…`. There
were 32 trials: eight complete, balanced crossover blocks of OpenGL/Vulkan × Stock/Large Underclock.
Each trial reloaded the same Route 20 bridge state, warmed up for 8 seconds, then recorded 40 seconds with
alternating horizontal input every 0.45 seconds and no programmed rests. The middle 34 seconds were
analyzed (18.1 minutes total). Trials, not the thousands of frames, were the statistical samples. The
protocol and the 1 fps / 1 percentage-point non-inferiority margins were saved before measured runs.

| Renderer | CPU profile | Changing pictures/s, mean [95% run-bootstrap CI] | Picture-change gaps >25 ms, mean [95% CI] |
|---|---|---|---|
| OpenGL | Stock | 59.372 [59.242, 59.494] | 0.521% [0.353, 0.697] |
| OpenGL | Large | 59.565 [59.433, 59.706] | 0.310% [0.130, 0.477] |
| Vulkan | Stock | 59.610 [59.526, 59.678] | 0.303% [0.204, 0.415] |
| Vulkan | Large | 59.705 [59.663, 59.748] | 0.167% [0.093, 0.234] |

Large caps were verified throughout: C0 1,785,600 / C6 1,958,400 kHz versus Stock 3,532,800 / 4,320,000 kHz.
No sampled current frequency exceeded its selected cap. Native logs independently confirmed each renderer.
Both underclocked configurations passed the predeclared margins **for the captured picture-change
proxies** using paired block-bootstrap intervals; a secondary Student-t small-sample check passed too.
This does not establish equivalent perceived smoothness. Vulkan Large minus Stock: +0.095 pictures/s, paired
Student 95% CI [-0.046, +0.235]; long-gap rate -0.136 percentage points, CI [-0.347, +0.075]. There was no
statistically established superiority after Holm correction across the eight secondary sign-flip tests.
Vulkan Large had the best observed means, but these data do not establish a universal renderer winner.

The sampled CPU sensors were cooler under Large: about 1.67 °C for Vulkan and 4.04 °C for OpenGL in the
paired runs. Net battery-drain readings were taken while tethered: Vulkan's estimated change (-0.043 W)
had a paired 95% bootstrap CI crossing zero [-0.119, +0.023 W]. This is not a demonstrated battery-life
improvement. Candidate picture-change gaps remained: the worst measured gap was 52.6 ms; Vulkan Large
had one gap over 50 ms in its eight analyzed runs. These are not counts of confirmed stalls (see the
frame audit below). Detection-threshold sensitivity was checked at 0.5/1/2/4 grayscale levels. This is
one device and one starting scene, with capture/telemetry overhead; it does not measure input latency, physical
scanout, all maps, or 120 Hz performance. Both original battery saves and the starting state remained
byte-identical. The device was left at **Vulkan, Large Underclock, 6x, 60 Hz, frameskip Off**, paused at the
starting bridge position.

Reproduction tools (active-device benchmark; requires the matching existing slot 7 and an idle Odin):

```sh
# Python environment: numpy, pillow, scipy, matplotlib; host tools: adb, ffmpeg, ffprobe.
# This changes clock profiles/renderers and moves the player; back up saves first.
python3 redux/tests/perf/device_study.py redux/tests/perf/odin_crossover.json redux/build/odin/study
# For each completed trial, inspect the 3–37 s window; repeat for the other trial directories.
python3 redux/tests/perf/presentation.py redux/build/odin/study/b01-p1-VS/capture.mp4 \
  --crop 0,61,796,596 --ignore-top 25 --ignore-bottom 12 --start 3 --end 37 \
  --out redux/build/odin/study/b01-p1-VS/presentation.json
python3 redux/tests/perf/study_stats.py redux/tests/perf/odin_crossover.json redux/build/odin/study \
  --out redux/build/odin/study/results --plot
```

Raw videos, input-event times, caps/current frequencies, temperatures, battery samples, native logs and
loaded/end screenshots live under `build/odin/study/`. `results/trials.csv` and `results/statistics.json`
retain all 32 trials; `results/comparison.png` shows individual runs and mean confidence intervals.

**Frame audit and reproduction limits (2026-10-22):** all 32 loaded screenshots show the same bridge,
but the end screenshots show different positions, including different map transitions. Host-timed
alternating inputs did not produce identical game-frame trajectories. The frozen protocol's assertion
that turning affects conditions equally was an assumption, not a verified fact; it is retained unchanged
for provenance. Differing paths confound the interpretation of smoothness and temperature differences.
More repetitions or narrower confidence intervals cannot validate an unsuitable outcome measure.

`gap_audit.py` indexed 210 candidate gaps over 25 ms: 56 with sparse capture timestamps, 137 with regular
timestamps and low whole-picture differences, and 17 mixed. All 33 gaps over 50 ms contain low-change
samples; four also contain sparse capture timestamps. None is assigned a cause automatically. Source
frames from Vulkan Large `b06-p2-VL` at 9.651–9.701 s show the camera holding while the player/follower
continue changing pose. The whole-picture threshold misses that local motion. Vulkan Stock `b05-p2-VS`
shows the same sequence at 9.688–9.738 s. These do not demonstrate a 50 ms whole-game stall.

There is a stronger recorded candidate: OpenGL Large runs `b02-p4-GL`, `b03-p4-GL` and `b05-p1-GL` hold
the whole scene for 51.5, 51.9 and 51.6 ms, respectively, at the same position beside the house, around
21.69 s. The ROM counter displays `L` in those windows. The foreground also holds (unlike the Vulkan
examples). This is a recurring captured-output event worth tracing; its cause and its relevance to the
user's perceived hitch still need frame-level attribution and a check without screenrecord.

The separate deterministic benchmark was rerun twice at all ten spots in both JIT and interpreter,
using the **exact device ROM** (`3ed14622…`), matching QOL symbols and a copy of the original JP battery
save. Every one of the 20 pairs had identical per-frame rows and counters. `r20_long_aut/J` repeatedly
reports emulated-budget misses at zero-based frames 301 and 586, plus three omitted midpoints; its
interpreter run has no such budget misses and two omitted midpoints. This is a concrete game/core timing
repro, not proof of the cause of a physical Odin hitch. The grass and Route 19 routes also enter events;
their lag counters must be interpreted with the retained screenshots, not treated as steady field FPS.
Raw rows, candidate-event timestamps, inspected frames, screenshots and repeatability checks are retained
under `build/odin/study/results/audit/`.

```sh
python3 redux/tests/perf/gap_audit.py redux/build/odin/study/b*/presentation.json \
  --out redux/build/odin/study/results/audit
```

A game change can reduce work in shared rendering/loading paths and benefit many situations using those
paths. It cannot guarantee every scene, device setting, driver, OS scheduling delay or display cadence.
The current patch interpolates field positions/camera/models; sprite animation, particles, weather and
2D still have their existing update rates, and battles require separate work. Keep the budget guards:
forcing an extra draw to make the counter read 60 can spend time needed by real updates. A performance
fix needs a specific failing trace, an explanation of the missed budget, a before/after replay, and
regressions across dense maps, streaming boundaries, effects/weather, menus, encounters and battles.
Physical output pacing and controller latency require device measurements as well as ROM counters.

### Boot test in an emulator

```sh
python3 -m venv ../build/emu && ../build/emu/bin/pip install py-desmume pillow   # DeSmuME 0.9.12
../build/emu/bin/python boot_test.py ../build/out/mine.nds ../build/boot/mine --every 50
```

Runs the ROM headless, taps Start/A through the title into the intro and saves screenshots (exit 1
if the screen never changes). vanilla + `redux_patch.py apply` and the new-zone test ROM give
screenshots pixel-identical to official Redux; an edited intro line shows up in game.

### Redux on top of a modified Black 2

```sh
python3 redux_patch.py make ../build/vanilla_rom/black2.nds ../build/vanilla_rom/redux.nds ../build/patch_redux
python3 redux_patch.py apply ../build/patch_redux MY_HACK.nds MY_HACK+redux.nds --report report.md
python3 test_patch.py      # vanilla+patch == Redux; modified base keeps its edits; conflicts reported
```

The patch is a list of semantic units (each message line, zone record, NARC subfile, file, code
module) with vanilla and Redux values. Applying is a three-way merge per unit: where the base still
has the vanilla value Redux's is taken, where both changed the base wins and the unit is listed in
the report; code modules fall back to merging Redux's byte ranges that don't collide. The base must
be a Black 2 USA/EU derivative (same archive numbering).
Not covered yet: maps/zone headers, graphics, arm9/overlay code edits (see `notes/` for what changed).

## Testing

The regression suite is `redux/tests/` (tracked: every worktree has it). `rr.py` runs it as a job graph,
many emulators at once, on the ROMs of *this* worktree's `redux/build/` (`out/redux3_LANG.nds`, `redux3/`,
`qol/`; build them first with `tools/build_redux3.py`, or pass `--build`):

```sh
python3 redux/tests/rr.py --quick              # quick tier: new games, settings menu, views, statview, evomoves
python3 redux/tests/rr.py --full               # everything: ~180 jobs, EN + JP, DeSmuME + melonDS, perf numbers
python3 redux/tests/rr.py --changed [REF]      # only the areas the files changed since REF (default HEAD) touch
python3 redux/tests/rr.py --m3 --lang en       # the old quick_m3 chain: new game -> story -> smoke -> continue
python3 redux/tests/rr.py --only 'qol2\.' -j 8 # a regex over job ids (+ the jobs they start from); --list shows them
```

- **Jobs** (`suite.py`): one test script each (`t_newgame.py en def`, `t_story.py en`, ...); a job's
  dependencies are the jobs whose savestates / battery saves it starts from (new game -> story -> smoke ->
  continue / Unova Link; QA test ROM build -> new game -> qol2 `t_prep` -> the qol2 tests; ...). Ready jobs
  start longest-chain-first (durations of earlier runs, `build/testruns/durations.json`); a failure skips its
  dependents and is printed at once with its FAIL lines and log; `--fail-fast` stops starting new jobs.
- **Isolation**: each run is `build/testruns/<id>/` (`latest` links the newest): `b/` is a shadow of
  `redux/build` (test output directories are fresh, everything else links to the real build tree), so a
  run never loads an earlier run's savestates; every job gets its own DeSmuME battery directory
  (`cfg/<job>/desmume`, via `XDG_CONFIG_HOME`; `~/.config/desmume` is never used), logs in `logs/<job>.log`,
  and `summary.txt` / `results.json` at the end. Emulators run headless (SDL dummy drivers: no Dock icons).
- **Checkpoint cache** (`--reuse`, on by default except with `--full`): a passed job is remembered under a key
  made of its command, the SHA-1 of the ROM it ran on, the harness files it uses and its dependencies' keys,
  with the savestates / battery saves it produced (`build/testcache/`, hard links). A rerun on the same ROMs
  restores them (CACHED) instead of replaying the game; any rebuild changes the ROM's SHA-1, so a stale state
  is never reused.
- **Tiers**: `--quick` (boot-to-bedroom new games, the settings menu + SELECT view, the rules new game, the
  statview, EVO/MOVES and X-menu suites from their fixture save (X menu also in melonDS and on the bedroom
  state), static text checks), `--full` (every test with a RESULT, the melonDS (MPU) runs of the EVO/MOVES tests, the fast-save matrix incl. the stale-save negative
  control that must FAIL, plus the battle-exit / fix-float measurements), `--changed` (module / follower /
  test files -> areas, `suite.AREAS_BY_PATH`; tools or core changes select everything).
- Paths come from the repo (`rrenv.py`); the machine-specific bits are environment variables:
  `REDUX_EMU_PY` (Python with py-desmume 0.0.9 + Pillow + numpy; default `build/emu-venv` or the original job
  venv), `REDUX_MELON_SCRIPTS` (bfix's `mel.py` + `../lib/libbf.dylib`, the headless melonDS with MPU), `REDUX_BUILD`.
  Fixtures read from the build tree: `build/statview_integ/dsv/` and `build/ff_integ/sav/` (battery saves).
- `-j` defaults to cores − 2; `--build` rebuilds the release ROMs first, `--determinism` once more at the
  end (SHA-1s must match).
- **Speed-ups inside a job**: DeSmuME skips *drawing* (2D + 3D; the emulation is unchanged) every frame no
  test can look at: `step(n)` and `wait_field()` mark all but the last 3 frames before any possible screenshot,
  never while display capture is on or frames are being recorded (`rrenv.py`, `--render-all` turns it off).
  From one savestate the 3-frame tail gives pixel-identical screenshots, and a screenshot taken too early
  prints `RR-RENDER-STALE`, which fails the job. Long tests made of independent parts (`t_scenes`, `t_cutin`,
  `t_turbo`, `t_extra`) run one job per part (each part loads its own start state anyway). Jobs off the
  critical path run at a lower priority (`--no-nice`).
- **Times** (M5 Max, 18 cores, shared with other work; 2026-10-22): `--full -j 16` 10.8–11.2 min (+1 min
  with `--build`; 218 jobs, ~175 job-minutes), `--quick` 2.6 min (0.2 min when the ROMs are unchanged:
  cached), `--m3 --lang en` 3.4 min (the chain is sequential). The old way (build/scripts phases with
  `integ/runq.py`, 6 at a time, scripted back to back without the double release build) took 24 min; by hand
  ~1 h. Per job, emulation is everything: py-desmume runs ~270 fps alone (~220 with 6, ~85–110 each with 16
  in parallel), Python overhead per frame is < 1 %, screenshots 0.06 ms + 1.1 ms per PNG.
- **Known flaky checks** (also in the old harness): DeSmuME's clock is the host's, so random encounters,
  catches and bites differ from run to run: `bx.mksave.r19` (an encounter on the way into the grass),
  `qa.rules` (Route 19 encounters), `qa.smoke` (the catch), `qol2.fish`, `qa.extra.surf`. Rerun them with
  `--only`; pinning the emulated clock would make them deterministic.

### Testing → performance

`redux/tests/perf/perf.py` (or `rr.py --perf ...`) is the field-performance benchmark: ~10–20 s for all spots, and
exact (emulated cycle counts, no wall clock: the same ROM, state and keys give the same numbers every run), so
A/B comparisons need no repetitions. Start any performance work from it:

```sh
python3 redux/tests/rr.py --perf --save-baseline before     # EN release ROM of this worktree
# ... change something, tools/build_redux3.py --lang en ...
python3 redux/tests/rr.py --perf --baseline before          # table + difference per spot + top functions
python3 redux/tests/perf/perf.py --spots virbank,r20_bridge_aut --rom X.nds --map X_qol_map.json --top 40
```

- **Spots** (`perf.py` SPOTS): Route 20's wooden bridges (summer, autumn: falling leaves), its grass, Virbank,
  Aspertia, Floccesy, Route 19, a Castelia street (645 polygons), each a short key script (180 frames: standing,
  running, walking), plus `r20_long_aut` (690 frames over Route 20 in autumn, across map-block boundaries). The
  savestates are made once per ROM SHA-1 (`build/perfstates/<sha1>/`, ~10 s: the battery save `$REDUX_PERF_SAV`
  is continued and warped there before the field is built, season set in GameData) with a screenshot each.
- **Two runs per spot**, in parallel: `J` = melonDS with its JIT (what Watermelon DS / melonDS Android run; it
  counts cycles per block, ~6–15 % more busy than the interpreter), `I` = the interpreter plus a cycle profile
  per function (B2 function starts, swan names, our qol symbols) split into *inside the 3D draws* (phase 1 /
  phase 2 → the render call's return) and *outside*. Columns: ARM9 busy % per frame (halted / idle-loop cycles vs
  all) mean / p90 / max, busy kilocycles per frame, `lag` (frames over budget: a main-loop iteration of 2+
  VBlanks), new pictures/s while moving, fps60's midpoint pictures drawn / left out, fallback updates, frames in
  vanilla drawing, polygons / vertices of the swapped lists (the hardware limits are 2048 / 6144).
- Results: `build/perf/results/<sha1>.json`; `--save-baseline NAME` / `--baseline NAME` keep and compare
  `build/perf/baseline_NAME.json`. The emulator is `build/perf-melon/libperf.dylib`, built on first use by
  `perf/melon/build.sh` from `$REDUX_MELON_SRC` (the headless melonDS 1.0 core with the PC profiler) +
  `perf/melon/patch_core.py` (halted cycles under the JIT, PC watchpoints that switch the profile table, swapped
  polygon / vertex counts) + `perf/melon/libmelon.cpp` (the C API, `ML_JIT=1` turns the JIT on).
- Logic identity after a performance change: `perf/desync.py` on a ROM built `--with fieldpark` (the test module
  parks the ARM9 after every field update): two runs with a switch on / off, compared update by update (main
  RAM; differences in the game's logic state -- field actors, GameData, GSYS, the field, GFL's RNG -- listed
  first), e.g. `desync.py ROM MAP build/perfstates/<sha1>/virbank.mlst 'RIGHT:40,:5,UP:15' '' 'perf_dbg+0=1'`.

## ROM-free analysis

Earlier work recovered Redux's code changes from the patch alone (no ROM): `decode_patch.sh`,
`copymap.py`, `build_vanilla.py` (pokeblack2 assembled with GNU as, 251/260 overlays SHA-1 exact),
`blz.c` (Nintendo-exact BLZ), `recover_overlays.py`, `arm9_changes.py`, `overlay_changes.py`. The
real ROM later confirmed those results byte for byte.
