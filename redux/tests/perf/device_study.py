#!/usr/bin/env python3
"""Run a predeclared crossover study on the connected Odin, using ClusterTune's UI.

This is an active device benchmark, not a headless test. It changes clock profiles
and renderer settings, injects movement, and reloads an EXISTING state. Use only
with an idle device and backed-up saves. Protocol JSON is written before runs;
the caller supplies conditions, balanced block order, timings and expected caps.
UI coordinates for the emulator's pause/state panels match the tested 1920x1080
WatermelonDS 0.8.0.rc3 layout. Refuses a different display size. It never writes a
ROM, battery save, save state, or ClusterTune profile. A failed run stops the batch.

  device_study.py PROTOCOL.json OUTPUT_DIR [--pilot CONDITION] [--resume]

Raw video, input times, frequency/thermal telemetry, logs, screenshots and metadata
are retained. Run presentation.py separately; trials, not frames, are the units
for statistical inference. Injected commands are timed by the host, not emulated
frames. The same starting state and command schedule do NOT ensure an identical
path: inspect the loaded/end screenshots and the motion around candidate gaps.
Warmup/capture/input/logcat clocks are not synchronized to an individual frame.
On interruption only inputs are released; the last
selected renderer and clock profile stay in place, so restore them deliberately.
"""
import argparse
import hashlib
import json
import re
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

PKG = 'me.magnum.melondualds'
COMPONENT = PKG + '/me.magnum.melonds.ui.emulator.EmulatorActivity'
URI = ('content://com.android.externalstorage.documents/tree/primary%3AROMs%2Fnds/'
       'document/primary%3AROMs%2Fnds%2FPokemon%20Blaze%20Black%202%20ReRedux%20%28JP%29.nds')


def adb(*args, capture=False):
    return subprocess.run(['adb', *args], check=True, stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
                          stderr=subprocess.PIPE, timeout=30).stdout


def shell(command):
    return adb('shell', command, capture=True).decode(errors='replace').strip()


def tap(x, y):
    adb('shell', 'input', 'tap', str(x), str(y))
    time.sleep(.3)


def nodes():
    shell('uiautomator dump /sdcard/odin-study-ui.xml')
    return list(ET.fromstring(adb('shell', 'cat', '/sdcard/odin-study-ui.xml', capture=True)).iter('node'))


def tap_text(label, scroll=False):
    for attempt in range(3 if scroll else 1):
        found = [n for n in nodes() if n.get('text') == label or n.get('content-desc') == label]
        if found:
            x1, y1, x2, y2 = map(int, re.findall(r'\d+', found[0].get('bounds')))
            tap((x1 + x2) // 2, (y1 + y2) // 2)
            return
        if scroll:
            adb('shell', 'input', 'swipe', '1100', '940', '1100', '450', '300')
            time.sleep(.2)
    raise RuntimeError(f'UI label not found: {label}')


def caps():
    return [int(v) for v in shell('cat /sys/devices/system/cpu/cpufreq/policy0/scaling_max_freq '
                                 '/sys/devices/system/cpu/cpufreq/policy6/scaling_max_freq').split()]


def set_clock(condition):
    adb('shell', 'am', 'start', '-W', '-n', 'com.aure.clustertune/.MainActivity')
    time.sleep(.4)
    tap_text(condition['clock'], scroll=True)
    tap_text('Apply ' + condition['clock'], scroll=True)
    time.sleep(.5)
    actual = caps()
    if actual != condition['caps_khz']:
        raise RuntimeError(f'ClusterTune caps did not apply: {actual} != {condition["caps_khz"]}')


def set_renderer(renderer):
    adb('shell', 'am', 'start', '-W', '-n', PKG + '/.DefaultIcon')
    time.sleep(.7)
    tap_text('Settings')
    tap_text('Video')
    tap_text('Renderer')
    tap_text({'opengl': 'OpenGL', 'vulkan': 'Vulkan'}[renderer])


def load_scene():
    adb('shell', 'am', 'start', '-W', '-n', COMPONENT, '-a', PKG + '.LAUNCH_ROM', '-d', URI)
    time.sleep(2)
    adb('shell', 'input', 'keyevent', '4')
    time.sleep(.35)
    tap(960, 330)       # Load state
    tap(1590, 690)      # existing slot 7
    time.sleep(.8)


def screenshot(path):
    path.write_bytes(adb('exec-out', 'screencap', '-p', capture=True))


def direction(value):
    adb('shell', 'input', 'joystick', 'motionevent', 'MOVE', str(value), '0')


TELEMETRY = r'''
printf 'uptime,c0_cur,c6_cur,c0_max,c6_max,gpu_cur,cpu0_temp,cpu6_temp,gpu_temp,battery_temp,current_ua,voltage_uv,status\n'
for i in $(seq 1 36); do
  printf '%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n' \
    "$(cut -d ' ' -f 1 /proc/uptime)" \
    "$(cat /sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq)" \
    "$(cat /sys/devices/system/cpu/cpufreq/policy6/scaling_cur_freq)" \
    "$(cat /sys/devices/system/cpu/cpufreq/policy0/scaling_max_freq)" \
    "$(cat /sys/devices/system/cpu/cpufreq/policy6/scaling_max_freq)" \
    "$(cat /sys/class/kgsl/kgsl-3d0/devfreq/cur_freq)" \
    "$(cat /sys/class/thermal/thermal_zone1/temp)" \
    "$(cat /sys/class/thermal/thermal_zone25/temp)" \
    "$(cat /sys/class/thermal/thermal_zone32/temp)" \
    "$(cat /sys/class/power_supply/battery/temp)" \
    "$(cat /sys/class/power_supply/battery/current_now)" \
    "$(cat /sys/class/power_supply/battery/voltage_now)" \
    "$(cat /sys/class/power_supply/battery/status)"
  sleep 1
done
'''


def trial(protocol, condition_id, out, block, position):
    condition = protocol['conditions'][condition_id]
    out.mkdir(parents=True, exist_ok=False)
    meta = dict(condition_id=condition_id, condition=condition, block=block, position=position,
                protocol_sha256=hashlib.sha256(json.dumps(protocol, sort_keys=True).encode()).hexdigest(),
                started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
    (out / 'metadata.json').write_text(json.dumps(meta, indent=2))
    print(f'SETUP {out.name} {condition_id}', flush=True)
    adb('shell', 'am', 'force-stop', PKG)
    set_clock(condition)
    set_renderer(condition['renderer'])
    load_scene()
    screenshot(out / 'loaded.png')
    # Verify that saved state loaded in the field, using the existing ROM counter's
    # white glyphs at the top-left (screenshots retained for visual auditing too).
    from PIL import Image
    im = Image.open(out / 'loaded.png').convert('RGB')
    white = sum(1 for r, g, b in im.crop((0, 92, 230, 160)).getdata() if min(r, g, b) > 230)
    if white < 100:
        raise RuntimeError('Expected overworld counter was not found after loading slot 7')
    time.sleep(protocol['warmup_seconds'])
    if caps() != condition['caps_khz']:
        raise RuntimeError('Clock caps changed while launching the emulator')
    meta['start_battery'] = shell('dumpsys battery')
    meta['system_settings'] = shell('settings get system performance_mode; settings get system fan_mode; '
                                    'settings get system peak_refresh_rate; settings get system min_refresh_rate')
    log_start = shell('date +%s') + '.000'
    telemetry_file = (out / 'telemetry.csv').open('wb')
    monitor = subprocess.Popen(['adb', 'shell', TELEMETRY], stdout=telemetry_file, stderr=subprocess.DEVNULL)
    rec = subprocess.Popen(['adb', 'shell', 'screenrecord', '--size', '1280x720', '--bit-rate', '8000000',
                            '--time-limit', str(protocol['record_seconds']), '/sdcard/odin-study.mp4'],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    t0 = time.monotonic()
    inputs = []
    print(f'RECORD {out.name} {condition_id}', flush=True)
    try:
        time.sleep(2)
        next_event = time.monotonic()
        value = 1
        while time.monotonic() - t0 < protocol['record_seconds'] - 1.5:
            before = time.monotonic() - t0
            direction(value)
            inputs.append(dict(value=value, before=before, after=time.monotonic() - t0))
            value = -value
            next_event += protocol['input_direction_hold_seconds']
            time.sleep(max(0, next_event - time.monotonic()))
        direction(0)
        stdout, stderr = rec.communicate(timeout=12)
        (out / 'recorder.txt').write_bytes(stdout + stderr)
        if rec.returncode:
            raise RuntimeError('screenrecord failed: ' + stderr.decode(errors='replace'))
    finally:
        direction(0)
        if rec.poll() is None:
            rec.terminate()
            rec.communicate(timeout=10)
    monitor.wait(timeout=12)
    telemetry_file.close()
    meta['input_events'] = inputs
    meta['end_caps_khz'] = caps()
    meta['end_battery'] = shell('dumpsys battery')
    (out / 'metadata.json').write_text(json.dumps(meta, indent=2))
    log = shell('logcat -d -v threadtime -T ' + log_start)
    (out / 'device.log').write_text('\n'.join(l for l in log.splitlines() if 'VulkanPerf' in l))
    adb('pull', '/sdcard/odin-study.mp4', str(out / 'capture.mp4'))
    screenshot(out / 'end.png')
    import csv
    rows = list(csv.DictReader((out / 'telemetry.csv').open()))
    if not rows or any([int(r['c0_max']), int(r['c6_max'])] != condition['caps_khz'] for r in rows):
        raise RuntimeError('Clock cap drift found in telemetry; trial is invalid')
    (out / 'complete.json').write_text(json.dumps(dict(valid=True, samples=len(rows))) + '\n')
    print(f'DONE {out.name} {condition_id}', flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('protocol', type=Path)
    ap.add_argument('output', type=Path)
    ap.add_argument('--pilot', help='one excluded pilot condition')
    ap.add_argument('--resume', action='store_true')
    args = ap.parse_args()
    protocol = json.loads(args.protocol.read_text())
    if '1920x1080' not in shell('wm size') and '1080x1920' not in shell('wm size'):
        raise RuntimeError('This benchmark UI is calibrated only for 1920x1080')
    args.output.mkdir(parents=True, exist_ok=True)
    if args.pilot:
        trial(protocol, args.pilot, args.output / ('pilot-' + args.pilot), -1, -1)
        return
    for block, order in enumerate(protocol['blocks']):
        for position, cid in enumerate(order):
            out = args.output / f'b{block + 1:02d}-p{position + 1}-{cid}'
            if args.resume and (out / 'complete.json').exists():
                continue
            trial(protocol, cid, out, block, position)
    print('STUDY COMPLETE', flush=True)


if __name__ == '__main__':
    try:
        main()
    finally:
        direction(0)
