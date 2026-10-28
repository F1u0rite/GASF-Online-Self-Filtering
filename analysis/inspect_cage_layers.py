#!/usr/bin/env python3
"""Diagnostics for Day-1 GASF results; not a self-filter / not a ground truth.

Requires only precomputed analyze_cage_bags.py results (NPZ + JSON).
Does not read or modify ROS bags, and never infers the physical origin of a return.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

BINS = np.array([0., .12, .20, .30, .45, .60, .90, 1.20])


def band_counts(xyz):
    if len(xyz) == 0:
        return [0] * (len(BINS) - 1)
    return np.histogram(np.linalg.norm(xyz, axis=1), bins=BINS)[0].astype(int).tolist()


def read_points(p):
    with np.load(p) as n:
        return n['xyz'].astype(np.float32)


def main():
    a = argparse.ArgumentParser()
    a.add_argument('--results', type=Path, required=True, help='Previous day1 results directory')
    a.add_argument('--out', type=Path, help='Default: same as --results')
    args = a.parse_args()
    root = args.results.expanduser().resolve()
    out = args.out.expanduser().resolve() if args.out else root
    out.mkdir(parents=True, exist_ok=True)

    base = read_points(root / 'no_cage_samples.npz')
    candidates = {}
    for key in 'AB':
        with np.load(root / f'candidate_{key}.npz') as n:
            candidates[key] = n['xyz'].astype(np.float32)

    stats = {'note': 'Candidate points are voxel centers; categories describe range, not object identity.',
             'range_band_edges_m': BINS.tolist(),
             'no_cage_display_samples': {'points': int(len(base)), 'range_counts': band_counts(base)},
             'candidates': {}}
    for name, pts in candidates.items():
        stats['candidates'][name] = {
            'voxel_centers': int(len(pts)), 'range_counts': band_counts(pts),
            'z_min_m': float(pts[:, 2].min()) if len(pts) else None,
            'z_max_m': float(pts[:, 2].max()) if len(pts) else None,
            'range_min_m': float(np.linalg.norm(pts, axis=1).min()) if len(pts) else None,
            'range_max_m': float(np.linalg.norm(pts, axis=1).max()) if len(pts) else None,
        }
    (out/'candidate_layer_stats.json').write_text(json.dumps(stats, indent=2, ensure_ascii=False))

    fig, axes = plt.subplots(2, 2, figsize=(12, 10), constrained_layout=True)
    for j, name in enumerate('AB'):
        pts = candidates[name]
        for i, (u, v, text) in enumerate([(0, 1, 'XY'), (0, 2, 'XZ')]):
            ax = axes[i,j]
            if len(base):
                ax.scatter(base[:,u], base[:,v], s=1, alpha=.10, color='gray', label='No outer cage (sampled)')
            if len(pts):
                ax.scatter(pts[:,u], pts[:,v], s=20, alpha=.85, label=f'Cage {name} candidates ({len(pts)})')
            ax.set_xlim(-.85,.85); ax.set_ylim(-.85,.85)
            ax.set_xlabel('X (m)'); ax.set_ylabel(('Y' if i == 0 else 'Z')+' (m)')
            ax.set_title(f'{name}: {text} | compare visually ONLY (not registered)')
            ax.set_aspect('equal'); ax.grid(alpha=.18); ax.legend(fontsize=8)
    fig.savefig(out/'04_candidate_vs_baseline.png', dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 4.6), constrained_layout=True)
    x = np.arange(len(BINS)-1)
    labels = [f'{lo:.2f}-{hi:.2f}' for lo,hi in zip(BINS[:-1], BINS[1:])]
    for i, name in enumerate('AB'):
        counts = stats['candidates'][name]['range_counts']
        ax.bar(x + (i-.5)*.35, counts, width=.34, label=f'Cage {name}')
    ax.set_xticks(x, labels); ax.set_ylabel('Candidate voxels'); ax.set_xlabel('Range from LiDAR origin (m)')
    ax.set_title('Candidate voxel radial distribution (not validated self points)')
    ax.grid(axis='y', alpha=.2); ax.legend()
    fig.savefig(out/'05_candidate_range_bands.png', dpi=180)
    plt.close(fig)
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    print(f'\nSaved: {out}/04_candidate_vs_baseline.png')
    print(f'Saved: {out}/05_candidate_range_bands.png')
    print(f'Saved: {out}/candidate_layer_stats.json')

if __name__ == '__main__':
    main()
