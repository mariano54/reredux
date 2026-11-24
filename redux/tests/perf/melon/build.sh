#!/bin/sh
# Builds the perf benchmark's headless melonDS (JIT compiled in, ML_JIT=1 turns it on) into OUT/libperf.dylib:
#   sh redux/tests/perf/melon/build.sh [OUT]          (default OUT: redux/build/perf-melon)
# Source: $REDUX_MELON_SRC (default: build/ext/melonheadless, melonDS 1.0 + the PC profiler), copied to
# OUT/src and patched (patch_core.py); cmake build in OUT/build (a few minutes the first time, then incremental).
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=${1:-$HERE/../../../build/perf-melon}
SRC=${REDUX_MELON_SRC:-$HERE/../../../build/ext/melonheadless}
PY=${PYTHON:-python3}
if [ ! -d "$SRC" ]; then
  echo "Set REDUX_MELON_SRC to the headless melonDS source with the ARM9 PC profiler." >&2
  exit 1
fi
mkdir -p "$OUT"
OUT=$(cd "$OUT" && pwd)
if [ ! -d "$OUT/src" ]; then
  cp -R "$SRC" "$OUT/src"
fi
$PY "$HERE/patch_core.py" "$OUT"
cmake -S "$OUT/src" -B "$OUT/build" -DCMAKE_BUILD_TYPE=Release -DBUILD_QT_SDL=OFF -DENABLE_JIT=ON \
  -DENABLE_OGLRENDERER=OFF -DENABLE_GDBSTUB=OFF -DENABLE_LTO_RELEASE=OFF > "$OUT/cmake.log" 2>&1
cmake --build "$OUT/build" --target core teakra -j 10 > "$OUT/make.log" 2>&1
CORE=$(find "$OUT/build" -name libcore.a | head -1)
TEAKRA=$(find "$OUT/build" -name libteakra.a | head -1)
c++ -std=c++17 -O2 -fwrapv -shared -fPIC -DJIT_ENABLED -I"$OUT/src/src" -I"$(dirname "$CORE")" -I"$HERE" \
  "$HERE/libmelon.cpp" "$CORE" "$TEAKRA" -o "$OUT/libperf.dylib"
echo "built $OUT/libperf.dylib"
