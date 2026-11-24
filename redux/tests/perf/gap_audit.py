#!/usr/bin/env python3
"""Index candidate picture gaps without calling them stutters or assigning a cause.

Reads presentation.py JSON, retaining source-video timestamps. Separates gaps
with sparse capture timestamps from gaps containing regularly sampled, low-change
pictures. A low mean grayscale difference can hide local sprite motion; neither
category proves that the game or the physical display stalled. Inspect the source
frames, including moving foreground objects, before labeling an event.

  gap_audit.py build/odin/study/b*/presentation.json --out build/odin/study/results/audit
"""
import argparse
import collections
import csv
import json
import math
from pathlib import Path


def events(path, gap_ms=25.0):
    data = json.loads(path.read_text())
    times = data['frame_times_seconds']
    deltas = data['mean_grayscale_deltas']
    threshold = data['threshold']
    if len(times) < 2 or len(deltas) != len(times) - 1:
        raise ValueError(f'Frame/delta count mismatch: {path}')
    if not all(math.isfinite(t) for t in times + deltas):
        raise ValueError(f'Nonfinite measurements: {path}')
    if any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError(f'Non-increasing timestamps: {path}')
    changed = [i + 1 for i, delta in enumerate(deltas) if delta > threshold]
    rows = []
    for a, b in zip(changed, changed[1:]):
        duration = 1000 * (times[b] - times[a])
        if duration <= gap_ms:
            continue
        intervals = [1000 * (times[i + 1] - times[i]) for i in range(a, b)]
        sparse = sum(t > gap_ms for t in intervals)
        low_change = b - a - 1
        kind = ('sparse_capture_timestamps' if not low_change else
                'regular_samples_low_change' if not sparse else 'mixed')
        rows.append(dict(
            trial=path.parent.name, video=data['video'],
            start_seconds=times[a], end_seconds=times[b], gap_ms=duration,
            analysis_frame_start=a, analysis_frame_end=b,
            low_change_samples=low_change,
            max_capture_interval_ms=max(intervals), sparse_capture_intervals=sparse,
            kind=kind, grayscale_threshold=threshold,
        ))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('measurements', nargs='+', type=Path)
    ap.add_argument('--gap-ms', type=float, default=25)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    if not math.isfinite(args.gap_ms) or args.gap_ms <= 0:
        ap.error('--gap-ms must be finite and positive')
    rows = [row for path in sorted(args.measurements) for row in events(path, args.gap_ms)]
    summary = dict(
        event_count=len(rows), gap_threshold_ms=args.gap_ms,
        kinds=dict(collections.Counter(row['kind'] for row in rows)),
        over_50ms_kinds=dict(collections.Counter(row['kind'] for row in rows if row['gap_ms'] > 50)),
        interpretation=[
            'These are candidate gaps in a whole-picture change proxy, not confirmed stutters.',
            'Source timestamps are relative to the first captured frame, not synchronized with host input commands or logcat.',
            'Sparse capture timestamps cannot distinguish missing recording samples from an upstream stall.',
            'Regular low-change samples can contain local animation, intentional stops, or a repeated output picture.',
            'No game/emulator/display cause or physical scanout behavior is assigned automatically.',
        ], events=rows)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'gap_events.json').write_text(json.dumps(summary, indent=2) + '\n')
    with (args.out / 'gap_events.csv').open('w', newline='') as f:
        columns = ('trial', 'video', 'start_seconds', 'end_seconds', 'gap_ms',
                   'analysis_frame_start', 'analysis_frame_end', 'low_change_samples',
                   'max_capture_interval_ms', 'sparse_capture_intervals', 'kind', 'grayscale_threshold')
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({k: v for k, v in summary.items() if k != 'events'}, indent=2))


if __name__ == '__main__':
    main()
