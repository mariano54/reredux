#!/usr/bin/env python3
"""Analyze a completed device_study crossover; trials, not frames, are samples.

Requires numpy and scipy; --plot also requires matplotlib. Reads a frozen protocol.json and
all predeclared trials, validates their protocol hashes/caps, and refuses incomplete
blocks. Uses paired block-bootstrap confidence intervals and an exact two-sided
sign-flip test (exchangeable paired differences under the null), with Holm correction
across the four predeclared comparisons times two primary metrics. P values are
secondary to effect sizes and the predeclared practical-equivalence margins.

  study_stats.py PROTOCOL.json STUDY_DIR --out OUTPUT_DIR [--plot]

Inference is limited to this device, workload and capture method. Bootstrap intervals
describe observed run variation; zero observed rare stalls do not prove their future
probability is zero. Net battery drain while tethered is not total device power and
must not be extrapolated into unplugged battery life.
"""
import argparse
import csv
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np
from scipy.stats import t as student_t

PRIMARY = ('content_changes_per_wall_second', 'content_interval_over_25ms_percent')


def bootstrap_ci(values, seed=20261022, count=100000):
    values = np.asarray(values, dtype=float)
    samples = np.random.default_rng(seed).choice(values, (count, len(values)), replace=True).mean(axis=1)
    return [float(x) for x in np.percentile(samples, (2.5, 97.5))]


def student_ci(values):
    """Secondary small-sample sensitivity check; does not replace the protocol's bootstrap CI."""
    a = np.asarray(values, dtype=float)
    half = float(student_t.ppf(.975, len(a) - 1) * a.std(ddof=1) / np.sqrt(len(a)))
    return [float(a.mean() - half), float(a.mean() + half)]


def sign_flip_p(differences):
    d = np.asarray(differences, dtype=float)
    observed = abs(d.mean())
    permutations = np.asarray(list(itertools.product((-1, 1), repeat=len(d))))
    return float((np.abs((permutations * d).mean(axis=1)) >= observed - 1e-12).mean())


def holm(pvalues):
    order = np.argsort(pvalues)
    adjusted = np.empty(len(pvalues))
    previous = 0.0
    for rank, index in enumerate(order):
        previous = max(previous, min(1.0, pvalues[index] * (len(pvalues) - rank)))
        adjusted[index] = previous
    return adjusted.tolist()


def telemetry_metrics(path):
    data = list(csv.DictReader(path.open()))
    t0 = float(data[0]['uptime'])
    rows = [r for r in data if 3 <= float(r['uptime']) - t0 <= 37]
    if not rows:
        raise ValueError('No telemetry in analysis window')
    mean = lambda key, scale=1: float(np.mean([float(r[key]) / scale for r in rows]))
    return dict(
        sampled_cpu_temperature_c=float(np.mean([max(float(r['cpu0_temp']), float(r['cpu6_temp'])) / 1000 for r in rows])),
        gpu_temperature_c=mean('gpu_temp', 1000), battery_temperature_c=mean('battery_temp', 10),
        c0_mean_ghz=mean('c0_cur', 1e6), c6_mean_ghz=mean('c6_cur', 1e6),
        net_battery_drain_w=float(np.mean([-float(r['current_ua']) * float(r['voltage_uv']) / 1e12 for r in rows])),
        battery_statuses=sorted({r['status'] for r in rows}),
    )


def study(protocol, root):
    protocol_hash = hashlib.sha256(json.dumps(protocol, sort_keys=True).encode()).hexdigest()
    rows = []
    for block, order in enumerate(protocol['blocks']):
        for position, cid in enumerate(order):
            p = root / f'b{block + 1:02d}-p{position + 1}-{cid}'
            if not (p / 'complete.json').exists() or not (p / 'presentation.json').exists():
                raise ValueError(f'Incomplete predeclared trial: {p}')
            meta = json.loads((p / 'metadata.json').read_text())
            if meta['protocol_sha256'] != protocol_hash:
                raise ValueError(f'Protocol changed: {p}')
            if meta['condition_id'] != cid or meta['end_caps_khz'] != protocol['conditions'][cid]['caps_khz']:
                raise ValueError(f'Condition or caps mismatch: {p}')
            if meta['system_settings'].splitlines()[-2:] != ['60.0', '60.0']:
                raise ValueError(f'Display configuration mismatch: {p}')
            expected = protocol['conditions'][cid]['caps_khz']
            for r in csv.DictReader((p / 'telemetry.csv').open()):
                if [int(r['c0_max']), int(r['c6_max'])] != expected:
                    raise ValueError(f'Clock cap drift: {p}')
                if int(r['c0_cur']) > expected[0] or int(r['c6_cur']) > expected[1]:
                    raise ValueError(f'Measured clock exceeded selected cap: {p}')
            native_vulkan_lines = len((p / 'device.log').read_text().splitlines())
            if bool(native_vulkan_lines) != (protocol['conditions'][cid]['renderer'] == 'vulkan'):
                raise ValueError(f'Renderer/native-log mismatch: {p}')
            metrics = json.loads((p / 'presentation.json').read_text())
            if metrics['analysis_window'] != protocol['analysis_window_seconds']:
                raise ValueError(f'Analysis window mismatch: {p}')
            row = dict(trial=p.name, block=block + 1, position=position + 1, condition=cid,
                       renderer=protocol['conditions'][cid]['renderer'],
                       clock=protocol['conditions'][cid]['clock'],
                       c0_cap_khz=expected[0], c6_cap_khz=expected[1],
                       native_vulkan_log_lines=native_vulkan_lines,
                       **{k: metrics[k] for k in PRIMARY},
                       captured_frames_per_second=metrics['captured_frames_per_second'],
                       captured_p99_ms=metrics['captured_intervals_ms']['p99'],
                       content_p99_ms=metrics['picture_change_intervals_ms']['p99'],
                       content_max_ms=metrics['picture_change_intervals_ms']['max'],
                       content_gaps_over_50ms=metrics['picture_change_intervals_by_ms']['over_50'],
                       **telemetry_metrics(p / 'telemetry.csv'))
            rows.append(row)

    secondary = ('captured_p99_ms', 'content_p99_ms', 'sampled_cpu_temperature_c', 'net_battery_drain_w')
    groups = {}
    for cid in protocol['conditions']:
        group = [r for r in rows if r['condition'] == cid]
        groups[cid] = dict(n=len(group))
        for key in PRIMARY + secondary:
            values = [r[key] for r in group]
            groups[cid][key] = dict(mean=float(np.mean(values)), sd=float(np.std(values, ddof=1)),
                                    ci95=bootstrap_ci(values), min=min(values), max=max(values))

    comparisons = []
    pvalues = []
    for candidate, baseline in protocol['planned_comparisons']:
        paired = {cid: sorted((r for r in rows if r['condition'] == cid), key=lambda r: r['block'])
                  for cid in (candidate, baseline)}
        c = dict(candidate=candidate, baseline=baseline, n_pairs=len(protocol['blocks']), metrics={})
        for key in PRIMARY + secondary:
            differences = [a[key] - b[key] for a, b in zip(paired[candidate], paired[baseline])]
            s = dict(mean_difference=float(np.mean(differences)), ci95=bootstrap_ci(differences),
                     ci95_student_sensitivity=student_ci(differences), paired_differences=differences)
            if key in PRIMARY:
                s['p_sign_flip_two_sided'] = sign_flip_p(differences)
                pvalues.append(s['p_sign_flip_two_sided'])
            c['metrics'][key] = s
        if baseline in ('GS', 'VS') and candidate in ('GL', 'VL'):
            fps = c['metrics'][PRIMARY[0]]['ci95']
            stalls = c['metrics'][PRIMARY[1]]['ci95']
            margins = protocol['noninferiority_margins']
            c['underclock_within_practical_margins'] = (
                fps[0] > -margins['content_changes_per_second_loss']
                and stalls[1] < margins['over_25ms_percent_increase'])
            c['underclock_student_sensitivity_pass'] = (
                c['metrics'][PRIMARY[0]]['ci95_student_sensitivity'][0] > -margins['content_changes_per_second_loss']
                and c['metrics'][PRIMARY[1]]['ci95_student_sensitivity'][1] < margins['over_25ms_percent_increase'])
        comparisons.append(c)
    adjusted = iter(holm(pvalues))
    for c in comparisons:
        for key in PRIMARY:
            c['metrics'][key]['p_holm_8_tests'] = next(adjusted)
    return dict(protocol=protocol, protocol_sha256=protocol_hash, trials=rows, conditions=groups,
                comparisons=comparisons,
                measurement_interpretation={
                    'primary_metrics': 'Captured whole-picture change proxies, not validated stutter or physical FPS measurements.',
                    'noninferiority': 'The numerical margins apply only to these proxies; they do not establish equivalent perceived smoothness.',
                    'device_path_validation': 'This tool does not validate matching game positions. Inspect loaded/end screenshots and trajectories before treating traversals as identical.',
                    'gap_validation': 'Inspect source frames: local animation can continue within a whole-picture low-change gap. Do not label every detected gap a stall.',
                },
                limitations=[
                    'One physical device and one starting scene; no claim about all maps, battles or loading transitions.',
                    'Wall-time inputs are not a deterministic game-frame replay; any differing paths and transitions confound smoothness and thermal comparisons.',
                    'Whole-picture low-change gaps include local motion and natural stops; capture timestamps also have gaps. No individual event is causally attributed automatically.',
                    'Input command, video and native log clocks lack frame-level synchronization; aggregate logs cannot establish the cause of a specific visible hitch.',
                    'Screen recording adds load and observes captured output, not physical scanout or input latency.',
                    'Clock and fan/performance modes were fixed/verified; thermal carryover is mitigated by balanced order, not eliminated.',
                    'Small run-level sample; confidence intervals describe observed variation and do not prove absence of rare future stalls.',
                    'Battery readings are net drain in a tethered setup, not a battery-life measurement.',
                ])


def plot(result, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    labels = {'GS': 'OpenGL\nStock', 'GL': 'OpenGL\nLarge underclock',
              'VS': 'Vulkan\nStock', 'VL': 'Vulkan\nLarge underclock'}
    order = ('GS', 'GL', 'VS', 'VL')
    colors = ['#4776b4', '#80a3cf', '#218571', '#7ab8aa']
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.5), layout='constrained')
    for ax, key, title, ylabel in zip(axes, PRIMARY,
             ('Captured picture-change proxy', 'Candidate picture-change gaps'),
             ('Pictures per second', 'Gaps over 25 ms (%)')):
        for x, cid in enumerate(order):
            summary = result['conditions'][cid][key]
            values = [r[key] for r in result['trials'] if r['condition'] == cid]
            jitter = np.linspace(-.1, .1, len(values))
            ax.scatter(x + jitter, values, color=colors[x], alpha=.6, s=30)
            lo, hi = summary['ci95']
            ax.errorbar(x, summary['mean'], yerr=[[summary['mean'] - lo], [hi - summary['mean']]],
                        fmt='D', capsize=6, color='#182c3a', markersize=6, linewidth=2)
        ax.set_xticks(range(4), [labels[c] for c in order])
        ax.set_title(title, loc='left', fontsize=12, weight='bold')
        ax.set_ylabel(ylabel)
        if key == PRIMARY[0]:
            ax.set_ylim(58.5, 60.1)
            ax.axhline(60, color='#8996a3', linestyle='--', linewidth=1)
            ax.set_ylabel(ylabel + ' (zoomed axis)')
        ax.grid(axis='y', alpha=.2)
        ax.spines[['top', 'right']].set_visible(False)
    fig.suptitle('Odin 3 · ReRedux Route 20 · 6× native · 60 Hz\n8 trials per configuration; diamonds and bars = mean and 95% run-level CI',
                 fontsize=14, weight='bold')
    fig.savefig(out / 'comparison.png', dpi=180)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('protocol', type=Path)
    ap.add_argument('study', type=Path)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--plot', action='store_true')
    args = ap.parse_args()
    result = study(json.loads(args.protocol.read_text()), args.study)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'statistics.json').write_text(json.dumps(result, indent=2) + '\n')
    rows = result['trials']
    with (args.out / 'trials.csv').open('w') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    if args.plot:
        plot(result, args.out)
    print(json.dumps({k: result[k] for k in ('conditions', 'comparisons')}, indent=2))


if __name__ == '__main__':
    main()
