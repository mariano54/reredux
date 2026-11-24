#!/usr/bin/env python3
"""Measure a device recording separately from the ROM's swap-request counter.

Requires ffmpeg, ffprobe and numpy (the emulator test venv has numpy). Example for
an Odin recording made with `screenrecord --size 1280x720`, using the user's
1196x897 top-screen layout at (0, 91) on a 1920x1080 display:

  presentation.py capture.mp4 --crop 0,61,796,596 --ignore-top 25 --ignore-bottom 12

The picture-change threshold is a heuristic, not an FPS counter. Pauses, walking
into a wall, sprite animation and recording overhead affect it. Local animation
can continue while the whole-picture mean remains below the threshold. Use
gap_audit.py to index candidate events, then inspect their source frames. More
trials do not turn this proxy into a validated measure of perceived stutter.
Compare the same
save state and input script; keep the original timestamps (never transcode to a
fixed frame rate first). Screen recording measures captured output, not panel
scanout or button-to-photon latency.
"""
import argparse
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np


def analyze(path, crop=None, ignore_top=0, ignore_bottom=0, threshold=2.0, start=0.0, end=None):
    for tool in ('ffmpeg', 'ffprobe'):
        if not shutil.which(tool):
            raise RuntimeError(f'{tool} is required')
    probe = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_frames',
        '-show_entries', 'frame=best_effort_timestamp_time', '-of', 'json', str(path),
    ]))
    times = np.array([float(f['best_effort_timestamp_time']) for f in probe['frames']])
    if len(times) < 2 or np.any(np.diff(times) <= 0):
        raise ValueError('Need at least two video frames with strictly increasing timestamps')
    times -= times[0]
    included = (times >= start) & (times <= (end if end is not None else times[-1]))
    if included.sum() < 2:
        raise ValueError('Analysis window must include at least two frames')
    filters = []
    if crop:
        x, y, width, height = crop
        filters.append(f'crop={width}:{height}:{x}:{y}')
    filters += ['scale=256:192', 'format=gray']
    cmd = [
        'ffmpeg', '-v', 'fatal', '-i', str(path), '-vf', ','.join(filters),
        '-fps_mode', 'passthrough', '-f', 'rawvideo', '-',
    ]
    # Stream the decoded frames; a long recording should not need a full copy in RAM.
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    changes, previous, decoded = [], None, 0
    try:
        while True:
            data = bytearray()
            while len(data) < 256 * 192:
                chunk = proc.stdout.read(256 * 192 - len(data))
                if not chunk:
                    break
                data.extend(chunk)
            if not data:
                break
            if len(data) != 256 * 192:
                raise ValueError('Incomplete decoded frame')
            if decoded < len(times) and included[decoded]:
                frame = np.frombuffer(data, np.uint8).reshape(192, 256).astype(np.int16)
                frame = frame[ignore_top:192 - ignore_bottom]
                if previous is not None:
                    changes.append(float(np.abs(frame - previous).mean()))
                previous = frame
            decoded += 1
        error = proc.stderr.read().decode(errors='replace')
        if proc.wait():
            raise RuntimeError(error)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        proc.stdout.close()
        proc.stderr.close()
    if decoded != len(times):
        raise ValueError(f'Decoder/probe frame mismatch: {decoded} vs {len(times)}')
    times = times[included]

    def distribution(values):
        if not len(values):
            return None
        return {k: round(float(v), 3) for k, v in zip(
            ('min', 'p10', 'median', 'p90', 'p95', 'p99', 'max'),
            np.percentile(values, (0, 10, 50, 90, 95, 99, 100)),
        )}

    change_times = times[np.flatnonzero(np.array(changes) > threshold) + 1]
    intervals = np.diff(change_times) * 1000
    return dict(
        video=str(path), crop=crop, ignore_top=ignore_top, ignore_bottom=ignore_bottom,
        threshold=threshold, frames=len(times), decoded_frames=decoded,
        analysis_window=[start, end], seconds=round(float(times[-1] - times[0]), 3),
        captured_frames_per_second=round((len(times) - 1) / (times[-1] - times[0]), 3),
        captured_intervals_ms=distribution(np.diff(times) * 1000),
        picture_changes=len(change_times), picture_change_intervals_ms=distribution(intervals),
        content_changes_per_wall_second=float(len(change_times) / (times[-1] - times[0])),
        content_interval_over_25ms_percent=float(100 * (intervals > 25).mean()) if len(intervals) else None,
        picture_change_intervals_by_ms={
            'under_12': int((intervals < 12).sum()),
            '12_to_22': int(((intervals >= 12) & (intervals <= 22)).sum()),
            'over_22_to_50': int(((intervals > 22) & (intervals <= 50)).sum()),
            'over_50': int((intervals > 50).sum()),
        },
        # Retain every interval. Long gaps may be intentional stops OR real stalls;
        # excluding them silently would make a stuttering run appear smooth.
        picture_change_times_seconds=[round(float(t - times[0]), 6) for t in change_times],
        frame_times_seconds=[round(float(t), 6) for t in times],
        mean_grayscale_deltas=changes,
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('video', type=Path)
    ap.add_argument('--crop', help='content rectangle in the recorded video: x,y,width,height')
    ap.add_argument('--ignore-top', type=int, default=0, help='rows to ignore after scaling to 256x192')
    ap.add_argument('--ignore-bottom', type=int, default=0)
    ap.add_argument('--threshold', type=float, default=2.0, help='mean grayscale difference for a picture change')
    ap.add_argument('--start', type=float, default=0, help='start of analysis window, seconds from first video frame')
    ap.add_argument('--end', type=float, help='end of analysis window')
    ap.add_argument('--out', type=Path, help='write JSON including individual picture-change times')
    args = ap.parse_args()
    crop = tuple(map(int, args.crop.split(','))) if args.crop else None
    if crop and (len(crop) != 4 or min(crop[:2]) < 0 or min(crop[2:]) <= 0):
        ap.error('--crop must be x,y,width,height with positive width and height')
    if min(args.ignore_top, args.ignore_bottom) < 0 or args.ignore_top + args.ignore_bottom >= 192:
        ap.error('ignored rows must leave part of the picture visible')
    if args.threshold <= 0:
        ap.error('--threshold must be positive')
    if args.start < 0 or (args.end is not None and args.end <= args.start):
        ap.error('analysis window must have 0 <= start < end')
    result = analyze(args.video, crop, args.ignore_top, args.ignore_bottom, args.threshold, args.start, args.end)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2) + '\n')
    arrays = ('picture_change_times_seconds', 'frame_times_seconds', 'mean_grayscale_deltas')
    print(json.dumps({k: v for k, v in result.items() if k not in arrays}, indent=2))


if __name__ == '__main__':
    main()
