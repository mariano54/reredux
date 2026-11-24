# ReRedux

Source code and build/research tools for extending Pokémon Blaze Black 2 Redux v1.4.1 with following Pokémon, configurable challenge/Nuzlocke rules, 60 fps overworld rendering, faster saves/loads/menus, and summary/Pokédex stat screens.

> **Code-only repository:** This repository contains **only original source code, build scripts, and technical research notes**. It includes **no game ROMs, no pre-built binary patches (`.xdelta`), no sprites, no game scripts, no dialogue dumps, no screenshots, and no third-party assets**. To build a patched ROM locally, you must supply your own legitimately dumped Pokémon Black 2 ROM and external assets.

## Features built from source

ReRedux adds the following modifications on top of Blaze Black 2 Redux v1.4.1 (by Drayano and AphexCubed):

- Following Pokémon (all 649 species + shinies), built locally from external follower sprite sheets and a `pokeheartgold` reference checkout.
- Configurable enforced Nuzlocke rules, Challenge Mode, species limits, and battle item restrictions.
- Lower-latency movement and turning with a 60 fps interpolated overworld.
- Faster saving, loading, cutscenes, doors, battles, menus, and optional 2× turbo without cutting audio.
- IV/EV columns, full level-up movesets, and evolution info in summary screens and the Pokédex.
- Tooling to build an optional Japanese localization when you supply your own Japanese Black 2 ROM and translation mappings.

This project is experimental and not bug-free; it is published as source code to demonstrate these patching and optimization techniques.

## Contents

| Path | Contents |
| --- | --- |
| [redux/tools/](redux/tools/) | Extraction, semantic patching, ROM rebuilding, Japanese porting, and ReRedux build scripts |
| [redux/followers/](redux/followers/) | Following Pokémon C/ASM code, linker symbols, and behavior mappings |
| [redux/qol/](redux/qol/) | Quality-of-life features, rule enforcement, and performance patch modules |
| [redux/tests/](redux/tests/) | Regression test harnesses, emulator instrumentation, and performance benchmarks |
| [redux/device/auto_refresh/](redux/device/auto_refresh/) | Optional Android automatic refresh-rate helper |
| [redux/notes/](redux/notes/) | Technical binary-diff and DMA/performance notes |

## Build from your own ROM

### Prerequisites

- Python 3, Pillow (`requirements-build.txt`), a host C compiler (`cc`), `xdelta3`, and the `arm-none-eabi` GCC/binutils toolchain.
- Authenticated GitHub CLI (`gh`) for fetching external script command definitions (`PokeScriptSDK5`).
- Your own clean USA/Europe Pokémon Black 2 cartridge dump (SHA-1: `e51e6dfb8678a3d19dcd2a10691b96a569ca0abb`).
- External follower sprite sheets (Pokémon Essentials Gen 8 follower sheets) and a local `pret/pokeheartgold` checkout (`files/data/mmodel/mmodel`). See [redux/followers/CREDITS.md](redux/followers/CREDITS.md).

### Steps (English build)

Run these commands from the repository root:

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements-build.txt
mkdir -p redux/build/bin redux/build/vanilla_rom redux/build/jp_rom
cc -O2 -o redux/build/bin/blz redux/tools/blz.c
```

1. Place your clean USA/Europe Black 2 ROM at `redux/build/vanilla_rom/black2.nds`.
2. Download the official Blaze Black 2 Redux v1.4.1 patch and produce the base Redux ROM locally:

```sh
./redux/tools/fetch_patch.sh
xdelta3 -d -s redux/build/vanilla_rom/black2.nds redux/build/patch/complete.xdelta redux/build/vanilla_rom/redux.nds
python3 redux/tools/fetch_script_defs.py
```

3. Point the builder at your external follower sheets and `pokeheartgold` checkout, then build:

```sh
export REDUX_ESSENTIALS=/path/to/essentials-followers
export REDUX_HGSS=/path/to/pokeheartgold/files/data/mmodel/mmodel
python3 redux/tools/build_redux3.py --lang en --no-icon
```

The output ROM is written to `redux/build/out/redux3_en.nds`.

### Optional Japanese build

No Japanese game dialogue or translation JSONs are vendored in this repository. If you also own a clean Japanese Pokémon Black 2 ROM (SHA-1: `751b6dc1a792aadd4cfba86a07199652aa06119b`), place it at `redux/build/jp_rom/jp_orig.nds`, extract translatable delta items with `python3 redux/tools/jp_port.py extract ...`, populate your own `tr/*.json` directory, set `REDUX_JP_WORK=/path/to/your/jp_work`, and run:

```sh
python3 redux/tools/build_redux3.py --lang jp --no-icon
```

## Research and tests

Read [redux/README.md](redux/README.md) for the editable extraction formats, module internals, and test commands. Optional disassembly tools accept external checkouts via `POKEBLACK2` and `REDUX_SWAN` (not required for normal builds).

For DeSmuME regression tests, install [requirements-test.txt](requirements-test.txt), point `REDUX_EMU_PY` to that environment's Python, and list the quick suite with `python3 redux/tests/rr.py --quick --list`. See [redux/notes/fast-dma.md](redux/notes/fast-dma.md) for DMA optimization notes.

## Credits and disclaimer

Pokémon Black 2 / White 2 © Nintendo, Creatures Inc., and GAME FREAK inc.
Blaze Black 2 is by Drayano; Blaze Black 2 Redux is by AphexCubed with Drayano.
See [redux/README.md](redux/README.md#credits) and [redux/followers/CREDITS.md](redux/followers/CREDITS.md) for full research and asset credits.

This is an unofficial, non-commercial fan project with no affiliation with or endorsement from Nintendo, The Pokémon Company, GAME FREAK, Creatures, Drayano, or AphexCubed. No ROMs, binary patches, or copyrighted game assets are distributed here.
