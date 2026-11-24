#!/usr/bin/env python3
"""Download the B2W2 script command definitions from ds-pokemon-hacking/PokeScriptSDK5 into
build/ext/PokeScriptSDK5/ (not committed: the upstream repo has no license file)."""
import os, subprocess, urllib.parse
import redux_rom as R

REPO = 'ds-pokemon-hacking/PokeScriptSDK5'
FILES = ['yml/B2W2/Base.yml'] + [f'yml/B2W2/Overlay {n}.yml' for n in
                                  (50, 51, 52, 53, 54, 55, 58, 61, 62, 63, 64, 65, 66, 67, 68)]


def main():
    out = os.path.join(R.BUILD, 'ext', 'PokeScriptSDK5')
    for f in FILES:
        dst = os.path.join(out, f)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        r = subprocess.run(['gh', 'api', f'repos/{REPO}/contents/{urllib.parse.quote(f)}',
                            '-H', 'Accept: application/vnd.github.raw'], capture_output=True, check=True)
        open(dst, 'wb').write(r.stdout)
        print(f, len(r.stdout))


if __name__ == '__main__':
    main()
