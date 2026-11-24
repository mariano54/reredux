# Fast geometry transfers outside the overworld

The selected optimization enables NitroSystem's existing FIFO-triggered display-list DMA
throughout the game. The field renderer already enabled it around its own draws. This extends
that lower-interrupt transfer path to battles and other NNS-rendered scenes.

`qol/perf.c` sets the existing `NNS_G3dFlagUseFastDma` at `0x0214697C` once per main-loop frame.
The SDK still owns the transfer, selected DMA channel, command buffer, and completion callback.
The existing field wrappers continue to work. The original geometry-command data and order,
sprite poses, animation/script clocks, sound code, and battle logic are retained.

`perf_dbg.slow_dma` uses byte +2 of the existing debug struct's padding (struct size and the
other fields' offsets are preserved). Set it to 1 to restore stock DMA outside the field;
the field's existing fast-DMA selection is independent. The patch declaration verifies the
ARM9 geometry-global literal at `0x02067CF0` before using that layout.

The code paths were checked against the local B2 assembly (`pokeblack2/asm/main.s`),
the NNS geometry command-buffer implementation (`gecom.c`), and the SDK DMA routines.

## Measurements

Raw evidence is retained under `redux/build/further-perf/` (ignored by Git).
The final candidates and maps are `selected-jp.nds`, `selected-en.nds`, and `qol-selected/`.
All tests used copied QA saves; the player's save was never opened for writing.

Each battle comparison restored one state into the same ROM, set the transfer mode, warmed
the framebuffers, and ran 1,800 frames with identical inputs. The RTC was fixed. Each frame
records actual 3D swaps, ARM9 busy cycles, both screen hashes, and a hash of the standalone
battle module, server (including battle RNG), and full BattleMon records (HP, conditions,
stages, moves and PP).

| Scene/core | Mean busy cycles: stock | Mean busy cycles: fast | Reduction | Missing 3D swaps: stock/fast |
| --- | ---: | ---: | ---: | ---: |
| Wild battle, JIT | 453,681 | 409,142 | 9.82% | 9 / 9 |
| Wild battle, interpreter | 389,773 | 369,534 | 5.19% | 8 / 7 |
| Trainer + Dragon Claw, JIT | 463,278 | 420,040 | 9.33% | 12 / 12 |
| Trainer + Dragon Claw, interpreter | 403,507 | 383,025 | 5.08% | 10 / 9 |

The JIT comparisons matched battle-state hashes, main-loop counts, and hardware swap counts
on every sampled frame. The trainer replay's screens also matched every frame. In the wild
replay, eleven lower-screen frames differed only in two pixels of the clock's blinking colon;
the upper-screen battle matched throughout. Captures in `captured-battle/` verify that location.

In the interpreter, reduced transfer work changed frame phase around loads and avoided one
missing swap per sampled scene. The battle-state hashes differed transiently on 7/16 frames,
respectively, then matched at the end. Therefore universal frame-by-frame timing identity
across cores is not claimed. No extra animation/battle ticks are introduced.

`selected-field/summary.json` compares ten field scenarios in JIT and interpreter modes:
20 matched comparisons, with identical pictures, midpoint counts, and lag counts. The field
already had fast DMA, so little additional field benefit is expected. The observed JIT CPU
change ranged from zero to about 1.1%; interpreter cycles were effectively unchanged.

These deterministic samples measure emulated work. They are not independent randomized
samples of all battles, physical display cadence, Android scheduling, temperatures, or battery
use. They do not establish that every move, battle format, or device will sustain 60 FPS.
The existing loading/transition gaps remain; the Odin was disconnected during this work.

## Reproduce

Use the emulator Python selected by `tests/rrenv.py`. Build the usual language ROMs with the
current sources; no opt-in module is required. `battle_perf.py --help` and `dma_check.py --help`
list arguments. Supply the exact ROM/map pair and Route 19/20 QA save fixtures, never a player's
current save. Each tool writes only to its output directory and the benchmark's own state cache.

The geometry CPU-send loop was also investigated. That candidate was rejected after a corrected
Virbank JIT comparison regressed. It is not in the active source or selected ROMs. Earlier runs
in `all-spots/` include an invalid instruction-restoration baseline and are not evidence for a
gain. The rejected source and diagnostic results remain in `rejected-cpu-send/`. The selected
optimization does not modify `MIi_CpuSend32` or patch executable instructions in the benchmarks.

## Regression and release artifacts

All 48 unique quick-regression checks passed across English and Japanese, including new-game
setup, settings, party/PC/egg summaries, battle entry, Pokédex/evolution views, and X menus.
The initial isolated test tree had stale output links for some summary test ROMs; those groups
were rerun after correcting the links. The raw initial failures and corrected runs are retained,
and `regression-combined.json` records the final status of every unique check.

The Japanese release was updated only after those checks. Its SHA-1 is
`90b5b6f3d3cfbc8f8c24d42964c353c4f9218acd`, with canonical outputs
`build/out/redux3_jp.nds` and `build/out/Pokemon Blaze Black 2 ReRedux (JP).nds`.
It includes neither the FPS-counter module nor the aborted battle interpolation experiment.
`build/further-perf/release.json` records the previous ROM hash and backup location.
The English candidate was built and tested; the English release was not replaced.
No ROM was installed on the disconnected Odin.
