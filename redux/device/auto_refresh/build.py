#!/usr/bin/env python3
"""Build a tiny, standalone Android helper with the local Android SDK (no Gradle)."""
import os
from pathlib import Path
import shutil
import subprocess

SOURCE = Path(__file__).resolve().parent
OUT = SOURCE.parents[1] / 'build' / 'odin' / 'auto-refresh'
SDK = Path(os.environ.get('ANDROID_SDK_ROOT', str(Path.home() / 'Library/Android/sdk')))
TOOLS = SDK / 'build-tools' / '35.0.0'
ANDROID = SDK / 'platforms' / 'android-35' / 'android.jar'


def run(*args):
    subprocess.run(list(map(str, args)), check=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name in ('classes', 'dex'):
        shutil.rmtree(OUT / name, ignore_errors=True)
        (OUT / name).mkdir()
    run(TOOLS / 'aapt2', 'compile', '--dir', SOURCE / 'res', '-o', OUT / 'resources.zip')
    run(TOOLS / 'aapt2', 'link', '-I', ANDROID, '--manifest', SOURCE / 'AndroidManifest.xml',
        '-o', OUT / 'unsigned.apk', OUT / 'resources.zip')
    run('javac', '--release', '8', '-classpath', ANDROID, '-d', OUT / 'classes',
        *sorted((SOURCE / 'src').rglob('*.java')))
    run('jar', 'cf', OUT / 'classes.jar', '-C', OUT / 'classes', '.')
    run(TOOLS / 'd8', '--min-api', '26', '--lib', ANDROID, '--output', OUT / 'dex', OUT / 'classes.jar')
    shutil.copyfile(OUT / 'unsigned.apk', OUT / 'with-dex.apk')
    run('zip', '-j', OUT / 'with-dex.apk', OUT / 'dex' / 'classes.dex')
    run(TOOLS / 'zipalign', '-f', '4', OUT / 'with-dex.apk', OUT / 'aligned.apk')
    key = OUT / 'local-helper.jks'
    if not key.exists():
        run('keytool', '-genkeypair', '-keystore', key, '-storepass', 'android', '-keypass', 'android',
            '-alias', 'helper', '-keyalg', 'RSA', '-keysize', '2048', '-validity', '10000',
            '-dname', 'CN=Local Odin Helper')
    apk = OUT / 'OdinAutoRefresh.apk'
    run(TOOLS / 'apksigner', 'sign', '--ks', key, '--ks-pass', 'pass:android',
        '--out', apk, OUT / 'aligned.apk')
    run(TOOLS / 'apksigner', 'verify', apk)
    print(apk)


if __name__ == '__main__':
    main()
