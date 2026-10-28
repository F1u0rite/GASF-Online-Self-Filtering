#!/usr/bin/env python3
"""Preview existing Day-1 candidate voxels on sampled near-field points.

DIAGNOSTIC ONLY: candidate voxels are not a verified self-object mask. This
script does not modify source bags or train an adaptive model.
"""
import argparse
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def read_model(path):
    with np.load(path) as f:
        indices = np.asarray(f['voxel_indices'], dtype=np.int32)
        size = float(f['voxel_size'])
    return {tuple(row) for row in indices}, size


def preview(results_dir, cage, out_dir):
    sample_path = results_dir / f'arc_{cage}_samples.npz'
    model_path = results_dir / f'candidate_{cage}.npz'
    if not sample_path.exists() or not model_path.exists():
        raise FileNotFoundError(f'Missing {sample_path.name} or {model_path.name}; run analyze_cage_bags.py first')
    with np.load(sample_path) as f:
        points = np.asarray(f['xyz'], dtype=np.float32)
    model, vox = read_model(model_path)
    indices = np.floor(points / vox).astype(np.int32)
    removed = np.fromiter((tuple(v) in model for v in indices), dtype=bool, count=len(points))
    near_keep, near_drop = points[~removed], points[removed]

    fig, axes = plt.subplots(2, 3, figsize=(15, 9), constrained_layout=True)
    for row, dims in enumerate(((0, 1), (0, 2))):
        x, y = dims
        names = ('X', 'Y') if row == 0 else ('X', 'Z')
        for col, (pts, title, color) in enumerate(((points, 'Input near-field sample', '#4b82b8'),
                                                   (near_keep, 'Retained', '#148e70'),
                                                   (near_drop, 'Candidate-mask removed', '#c44a48'))):
            ax = axes[row, col]
            if len(pts):
                ax.scatter(pts[:, x], pts[:, y], s=2, alpha=.34, color=color, rasterized=True)
            ax.set(xlim=(-1.2, 1.2), ylim=(-1.2, 1.2), xlabel=f'{names[0]} (m)', ylabel=f'{names[1]} (m)')
            ax.set_aspect('equal')
            ax.grid(alpha=.15)
            ax.set_title(f'{cage} {title} ({len(pts):,} sampled points)')
    fig.suptitle('OFFLINE DIAGNOSTIC ONLY | Voxels are UNVERIFIED self candidates; sampled points only', fontsize=13)
    out_path = out_dir / f'06_candidate_filter_preview_{cage}.png'
    fig.savefig(out_path, dpi=180)
    plt.close(fig)
    return {
        'cage': cage,
        'input_near_field_sample_points': int(len(points)),
        'candidate_voxels': len(model),
        'matched_candidate_points': int(removed.sum()),
        'retained_points': int((~removed).sum()),
        'matched_fraction_of_near_field_sample': float(removed.mean()) if len(removed) else 0,
        'voxel_size_m': vox,
        'note': 'Diagnostic only; not true-positive removal rate; no evaluation of environment false positives'
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--results', type=Path, required=True)
    ap.add_argument('--out', type=Path, default=None)
    args = ap.parse_args()
    root = args.results.expanduser()
    out = args.out.expanduser() if args.out else root
    out.mkdir(parents=True, exist_ok=True)
    report = {}
    for cage in ('A', 'B'):
        report[cage] = preview(root, cage, out)
        print(f"Cage {cage}: {report[cage]['matched_candidate_points']:,} / {report[cage]['input_near_field_sample_points']:,} near-field sampled points match preliminary candidates")
    report_path = out / '06_candidate_filter_preview_stats.json'
    report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f'[DONE] {out}')

if __name__ == '__main__':
    main()
