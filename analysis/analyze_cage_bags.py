#!/usr/bin/env python3
"""Day-1 cage LiDAR exploratory analysis: ROS 2 Livox CustomMsg bags.

Outputs preliminary near-field, body-frame occupancy *candidates*, not validated self masks.
Only reads bags; does not edit source data or require FAST-LIVO2.
"""
import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

DATASETS = {
    'no_cage': ['01_static', '01_static_no_cage'],
    'static_A': ['02_static_A'],
    'arc_A': ['03_arc_A'],
    'static_B': ['05_static_B'],
    'arc_B': ['06_arc_B'],
}


def find_dataset(root, options):
    for name in options:
        if (root / name / 'metadata.yaml').exists():
            return root / name
    return None


def storage_id_from_metadata(path):
    # Standard rosbag2 metadata; avoid requiring additional YAML packages.
    for line in (path / 'metadata.yaml').read_text().splitlines():
        s = line.strip()
        if s.startswith('storage_identifier:'):
            return s.split(':', 1)[1].strip().strip('\"\'')
    return 'sqlite3'


def unpack_near_points(msg, min_range, max_range):
    """Bounded-memory, sensor-frame near-field extraction."""
    lo2, hi2 = min_range ** 2, max_range ** 2
    xyz = []
    intensity = []
    for p in msg.points:
        x, y, z = p.x, p.y, p.z
        d2 = x*x + y*y + z*z
        if lo2 <= d2 <= hi2 and math.isfinite(d2):
            xyz.append((x, y, z))
            intensity.append(p.reflectivity)
    if not xyz:
        return np.empty((0, 3), dtype=np.float32), np.empty(0, dtype=np.uint8)
    return np.asarray(xyz, np.float32), np.asarray(intensity, np.uint8)


def analyze_one(path, args):
    try:
        import rosbag2_py
        from rclpy.serialization import deserialize_message
        from livox_ros_driver2.msg import CustomMsg
    except ImportError as e:
        raise RuntimeError('请先 source ROS2 Humble 和 livox_ros2_ws，并确认 rosbag2_py 可用：' + str(e)) from e

    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(uri=str(path), storage_id=storage_id_from_metadata(path)),
        rosbag2_py.ConverterOptions(input_serialization_format='cdr', output_serialization_format='cdr')
    )

    hits = defaultdict(int)
    point_hits = defaultdict(int)
    frames, raw_points, near_points = 0, 0, 0
    first_timebase = last_timebase = None
    samples, sample_intensity = [], []
    seen_lidar = 0
    seen_any = False
    while reader.has_next():
        topic, data, bag_timestamp = reader.read_next()
        if topic != '/livox/lidar':
            continue
        seen_any = True
        seen_lidar += 1
        if (seen_lidar - 1) % args.stride:
            continue
        msg = deserialize_message(data, CustomMsg)
        raw_points += len(msg.points)
        if first_timebase is None:
            first_timebase = int(msg.timebase)
        last_timebase = int(msg.timebase)
        xyz, intensity = unpack_near_points(msg, args.r_min, args.r_max)
        frames += 1
        near_points += len(xyz)
        if len(xyz):
            ijk = np.floor(xyz / args.voxel).astype(np.int32)
            voxels, counts = np.unique(ijk, axis=0, return_counts=True)
            for v, n in zip(voxels, counts):
                key = tuple(int(t) for t in v)
                hits[key] += 1
                point_hits[key] += int(n)
            # Small display sample per processed scan (not used in scoring)
            max_per_frame = max(1, args.plot_limit // max(1, args.max_frames))
            if len(xyz) > max_per_frame:
                ix = np.linspace(0, len(xyz)-1, max_per_frame, dtype=int)
                xyz, intensity = xyz[ix], intensity[ix]
            samples.append(xyz)
            sample_intensity.append(intensity)
        if frames >= args.max_frames:
            break

    if not seen_any:
        raise RuntimeError(f'{path} 中没有 /livox/lidar；先运行 ros2 bag info 检查。')
    if not frames:
        raise RuntimeError(f'{path} 未处理到任何 LiDAR 帧。')
    pts = np.concatenate(samples, axis=0) if samples else np.empty((0, 3), np.float32)
    refl = np.concatenate(sample_intensity) if sample_intensity else np.empty(0, np.uint8)
    return dict(name=path.name, path=str(path), frames=frames, scanned_lidar_messages=seen_lidar,
                raw_points=raw_points, near_points=near_points, near_frac=near_points/max(1,raw_points),
                hits=dict(hits), total_hits=dict(point_hits), points=pts, reflectivity=refl,
                timebase_start=first_timebase, timebase_end=last_timebase)


def occupancy_rate(ds, idx):
    if ds is None:
        return 0.0
    return ds['hits'].get(idx, 0) / max(ds['frames'], 1)


def choose_candidates(static, arc, base, args):
    candidates = []
    rows = []
    for index in static['hits']:
        s = occupancy_rate(static, index)
        a = occupancy_rate(arc, index)
        b = occupancy_rate(base, index)
        center = (np.asarray(index, dtype=np.float64) + .5) * args.voxel
        radius = float(np.linalg.norm(center))
        if radius > args.candidate_radius:
            continue
        if s >= args.static_threshold and a >= args.arc_threshold and (s - b) >= args.baseline_delta:
            candidates.append(index)
            rows.append([*index, round(s,4), round(a,4), round(b,4), round(radius,4)])
    return np.asarray(candidates, dtype=np.int32).reshape(-1,3), rows


def plot_overview(data, out, args):
    fig, axes = plt.subplots(2, 5, figsize=(19, 8), constrained_layout=True)
    for j, key in enumerate(DATASETS):
        ds = data.get(key)
        title = key + (f' ({ds["frames"]} frames)' if ds else ' (missing)')
        for i, (u,v,lab) in enumerate(((0,1,'XY'),(0,2,'XZ'))):
            ax = axes[i,j]
            if ds is not None and len(ds['points']):
                p = ds['points']
                ax.scatter(p[:,u], p[:,v], s=.17, alpha=.14, rasterized=True)
            ax.set_title(title + '  ' + lab)
            ax.set_xlabel(('X','Y','Z')[u] + ' (m)')
            ax.set_ylabel(('X','Y','Z')[v] + ' (m)')
            ax.set_xlim(-args.r_max, args.r_max)
            ax.set_ylim(-args.r_max, args.r_max)
            ax.set_aspect('equal')
            ax.grid(alpha=.15)
    fig.suptitle('Raw near-field point samples in the LiDAR frame | not registered across bags',fontsize=13)
    fig.savefig(out/'01_near_field_overview.png',dpi=160)
    plt.close(fig)


def plot_range_reflectivity(data, out, args):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.7), constrained_layout=True)
    for key, ds in data.items():
        xyz, refl = ds['points'], ds['reflectivity']
        if len(xyz):
            ranges = np.linalg.norm(xyz, axis=1)
            axes[0].hist(ranges, bins=40, range=(args.r_min, args.r_max),
                         histtype='step', density=True, label=key, linewidth=1.3)
            axes[1].hist(refl.astype(float), bins=32, range=(0, 256),
                         histtype='step', density=True, label=key, linewidth=1.3)
    axes[0].set(xlabel='Distance from LiDAR (m)', ylabel='Sample density', title='Near-field range')
    axes[1].set(xlabel='Reflectivity (0-255)', ylabel='Sample density', title='Near-field reflectivity')
    for ax in axes:
        ax.grid(alpha=.2)
        ax.legend(fontsize=8)
    fig.savefig(out/'03_range_reflectivity.png',dpi=170)
    plt.close(fig)


def plot_candidate_models(candidates, data, out, args):
    fig, axes = plt.subplots(2,2,figsize=(12,11),constrained_layout=True)
    for j, cage in enumerate('AB'):
        model = candidates[cage]
        pts = (model.astype(np.float32) + .5) * args.voxel
        for i, (u,v,lab) in enumerate(((0,1,'XY'),(0,2,'XZ'))):
            ax=axes[i,j]
            if len(pts):
                ax.scatter(pts[:,u],pts[:,v],s=2,alpha=.65,rasterized=True)
            ax.set_xlim(-args.candidate_radius,args.candidate_radius)
            ax.set_ylim(-args.candidate_radius,args.candidate_radius)
            ax.set_xlabel(('X','Y','Z')[u]+' (m)')
            ax.set_ylabel(('X','Y','Z')[v]+' (m)')
            ax.set_aspect('equal')
            ax.grid(alpha=.15)
            ax.set_title(f'Cage {cage} CANDIDATES, {lab} ({len(pts)} voxels)')
    fig.suptitle('PRELIMINARY fixed-structure candidates (not a verified cage mask)',fontsize=12)
    fig.savefig(out/'02_candidate_models.png',dpi=180)
    plt.close(fig)


def main():
    p=argparse.ArgumentParser(description='Mid360 ROS2 CustomMsg bag candidate cage analysis')
    p.add_argument('--bags-root',type=Path,default=Path('~/cage_bags').expanduser())
    p.add_argument('--out',type=Path,default=Path('~/cage_analysis').expanduser())
    p.add_argument('--voxel',type=float,default=.06,help='Voxel size in meters')
    p.add_argument('--r-min',type=float,default=.12)
    p.add_argument('--r-max',type=float,default=1.20)
    p.add_argument('--candidate-radius',type=float,default=.90)
    p.add_argument('--stride',type=int,default=10,help='Analyze 1 of every N LiDAR messages')
    p.add_argument('--max-frames',type=int,default=120,help='Max sampled frames for each bag')
    p.add_argument('--plot-limit',type=int,default=15000)
    p.add_argument('--static-threshold',type=float,default=.12)
    p.add_argument('--arc-threshold',type=float,default=.04)
    p.add_argument('--baseline-delta',type=float,default=.08)
    args=p.parse_args()
    if args.voxel<=0 or args.stride<1 or args.max_frames<1 or args.r_min<0 or args.r_max<=args.r_min:
        p.error('invalid voxel/stride/frame/range arguments')
    args.bags_root=args.bags_root.expanduser()
    args.out=args.out.expanduser()
    args.out.mkdir(parents=True,exist_ok=True)
    data={}
    print(f'INPUT: {args.bags_root}\nOUTPUT: {args.out}',flush=True)
    for key, names in DATASETS.items():
        location=find_dataset(args.bags_root,names)
        if not location:
            print(f'[SKIP] {key}: not found among {names}',flush=True)
            continue
        print(f'[READ] {key}: {location.name}',flush=True)
        data[key]=analyze_one(location,args)
        d=data[key]
        print(f'       frames={d["frames"]}, raw_points={d["raw_points"]:,}, near={d["near_points"]:,} ({d["near_frac"]:.1%}), voxels={len(d["hits"]):,}',flush=True)
        np.savez_compressed(args.out/f'{key}_samples.npz',xyz=d['points'],reflectivity=d['reflectivity'])

    summary={'configuration':vars(args).copy(),'datasets':{}}
    summary['configuration']['bags_root']=str(args.bags_root)
    summary['configuration']['out']=str(args.out)
    for key, d in data.items():
        summary['datasets'][key]={k:v for k,v in d.items() if k in (
            'name','path','frames','scanned_lidar_messages','raw_points','near_points',
            'near_frac','timebase_start','timebase_end')}
        summary['datasets'][key]['occupied_voxels']=len(d['hits'])
        summary['datasets'][key]['sample_reflectivity_median'] = (float(np.median(d['reflectivity'])) if len(d['reflectivity']) else None)

    if data:
        plot_overview(data,args.out,args)
        print('[OK] 01_near_field_overview.png',flush=True)
        plot_range_reflectivity(data,args.out,args)
        print('[OK] 03_range_reflectivity.png',flush=True)
    candidates={}
    for cage in 'AB':
        sta=data.get('static_'+cage)
        arc=data.get('arc_'+cage)
        if sta is None or arc is None:
            continue
        vox, rows=choose_candidates(sta,arc,data.get('no_cage'),args)
        candidates[cage]=vox
        centers=(vox.astype(np.float32)+.5)*args.voxel
        np.savez_compressed(args.out/f'candidate_{cage}.npz',voxel_indices=vox,xyz=centers,voxel_size=np.float32(args.voxel))
        with (args.out/f'candidate_{cage}.csv').open('w',newline='') as f:
            writer=csv.writer(f)
            writer.writerow(['ix','iy','iz','static_hit_rate','arc_hit_rate','nocage_hit_rate','range_m'])
            writer.writerows(rows)
        print(f'[CANDIDATES] cage_{cage}: {len(vox)} voxels',flush=True)
    if len(candidates)==2:
        plot_candidate_models(candidates,data,args.out,args)
        print('[OK] 02_candidate_models.png',flush=True)
    summary['candidate_voxels']={k:len(v) for k,v in candidates.items()}
    with (args.out/'summary.json').open('w') as f:
        json.dump(summary,f,indent=2,ensure_ascii=False)
    print('\n[DONE] Files saved in',args.out)
    print('IMPORTANT: candidates can contain nearby static environment / floor; do NOT use as final removal mask.')

if __name__=='__main__':
    main()
