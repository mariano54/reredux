#!/bin/bash
# Decode the Redux xdelta without a Black 2 ROM by applying it to synthetic sources:
#   zero.bin (all 0x00) -> build/rom/known0.nds
#   ff.bin   (all 0xFF) -> build/rom/known1.nds
#     bytes equal in both are Redux's own bytes (ADD/RUN); the rest were copied from vanilla.
#   xdelta3 printdelta -> build/rom/delta.txt
#     every copy instruction with its vanilla source offset (parsed by tools/copymap.py).
set -euo pipefail
cd "$(dirname "$0")/.."
command -v xdelta3 >/dev/null || { echo "need xdelta3 (brew install xdelta)"; exit 1; }
P=build/patch/complete.xdelta
[ -f "$P" ] || tools/fetch_patch.sh
mkdir -p build/rom build/tmp
N=536870912
if [ ! -f build/rom/known0.nds ]; then
  truncate -s $N build/tmp/zero.bin
  xdelta3 -d -f -n -s build/tmp/zero.bin "$P" build/rom/known0.nds
fi
if [ ! -f build/rom/known1.nds ]; then
  LC_ALL=C tr '\0' '\377' < build/tmp/zero.bin > build/tmp/ff.bin
  xdelta3 -d -f -n -s build/tmp/ff.bin "$P" build/rom/known1.nds
fi
if [ ! -f build/rom/delta.txt ]; then
  xdelta3 printdelta "$P" > build/rom/delta.txt   # exact copy instructions (tools/copymap.py)
fi
rm -rf build/tmp
ls -la build/rom
