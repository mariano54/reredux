#!/bin/bash
# Download the official Blaze Black 2 Redux v1.4.1 release (Drayano's Drive) and
# extract only the .xdelta patches into build/patch/. The .exe patchers are skipped.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/patch
ZIP=build/patch/v1.4.1_BlazeBlack2Redux.zip
ZIP_SHA=ed87c03a3e828ff2223b33badaaee1c1349fc086c0775ff9b6472322834c5a22
PATCH_SHA=071ddf7e2edd94185c557414ca622e495d5caac99086c859e6b791d4cf35a2b6

if [ ! -f "$ZIP" ]; then
  curl -sSL -o "$ZIP" "https://drive.usercontent.google.com/download?id=1AhsdffDiz872gwIB-kiGKutDAsM-GWvS&export=download&confirm=t"
fi
echo "$ZIP_SHA  $ZIP" | shasum -a 256 -c -

unzip -ojq "$ZIP" '*.xdelta' -d build/patch
mv -f "build/patch/Pokemon Blaze Black 2 Redux Complete v1.4.1.xdelta" build/patch/complete.xdelta
echo "$PATCH_SHA  build/patch/complete.xdelta" | shasum -a 256 -c -
