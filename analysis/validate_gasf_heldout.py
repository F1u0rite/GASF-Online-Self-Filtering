#!/usr/bin/env python3
"""Offline held-out candidate-mask check on Livox CustomMsg ROS 2 bags.

Uses PREVIOUSLY computed candidate_A/B.npz; never retrains the models.
No bag data are modified. Results are diagnostic, NOT detection accuracy.
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def storage_from_metadata(bag):
    metadata = (bag / 'metadata.yaml')
    if not metadata.is_file():
        raise FileNotFoundError(f'Missing metadata.yaml in {bag}')
    for line in metadata.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line.startswith('storage_identifier:'):
            return line.split(':', 1)[1].strip().strip('"\'')
    return 'sqlite3'


def load_model(path):
    if not path.is_file():
        raise FileNotFoundError(f'Missing candidate model: {path}')
    with np.load(path) as f:
        indices = np.asarray(f['voxel_indices'], dtype=np.int32)
        voxel = float(f['voxel_size'])
    if voxel <= 0 or indices.ndim != 2 or indices.shape[1] != 3:
        raise ValueError(f'Invalid model file: {path}')
    return {tuple(v) for v in indices.tolist()}, voxel


def extract_near_field(msg, min_range, max_range):
    low2, high2 = min_range*min_range, max_range*max_range
    points = []
    for p in msg.points:
        x,y,z = float(p.x),float(p.y),float(p.z)
        r2=x*x+y*y+z*z
        if math.isfinite(r2) and low2 <= r2 <= high2:
            points.append((x,y,z))
    return np.asarray(points,dtype=np.float32).reshape(-1,3)


def analyze_heldout(bag, model, voxel, args):
    try:
        import rosbag2_py
        from rclpy.serialization import deserialize_message
        from livox_ros_driver2.msg import CustomMsg
    except ImportError as exc:
        raise RuntimeError('Please source ROS 2 Humble and livox_ros2_ws first') from exc

    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(uri=str(bag), storage_id=storage_from_metadata(bag)),
        rosbag2_py.ConverterOptions(input_serialization_format='cdr', output_serialization_format='cdr'))

    all_original=[]
    all_removed=[]
    all_retained=[]
    n_frames=0
    seen_lidar=0
    near_count=0
    dropped_count=0
    per_frame=[]
    for topic, record, stamp in iter(lambda: reader.read_next() if reader.has_next() else None, None):
        if topic != '/livox/lidar':
            continue
        seen_lidar += 1
        if (seen_lidar-1) % args.stride:
            continue
        msg=deserialize_message(record,CustomMsg)
        points=extract_near_field(msg,args.r_min,args.r_max)
        n_frames+=1
        if len(points):
            keys=np.floor(points/voxel).astype(np.int32)
            flags=np.fromiter((tuple(k) in model for k in keys),dtype=bool,count=len(points))
            removed=points[flags]
            retained=points[~flags]
            near_count += len(points)
            dropped_count += len(removed)
            per_frame.append({'sample_frame':n_frames,'near_points':len(points),'candidate_hits':len(removed),
                              'hit_fraction':float(flags.mean())})
            # Evenly sample per-frame for plotting only. Statistics use ALL near-field points.
            limit=max(1,args.plot_points//max(args.max_frames,1))
            if len(points)>limit:
                step=np.linspace(0,len(points)-1,limit,dtype=int)
                points=points[step]
                flags=flags[step]
            all_original.append(points)
            all_removed.append(points[flags])
            all_retained.append(points[~flags])
        if n_frames >= args.max_frames:
            break
    if not n_frames:
        raise ValueError(f'No LiDAR data in {bag}')
    def merge(xs):
        return np.concatenate(xs,axis=0) if xs else np.empty((0,3),np.float32)
    return merge(all_original),merge(all_retained),merge(all_removed),{
        'bag':str(bag),'processed_frames':n_frames,'lidar_messages_traversed':seen_lidar,
        'near_field_points_processed':near_count,'candidate_hits':dropped_count,
        'candidate_hit_fraction':dropped_count/max(1,near_count),
        'voxel_size_m':voxel, 'candidate_voxels':len(model),
        'per_frame_hit_fraction':per_frame,
        'warning':'Candidate-mask hit fraction, not self-filter precision/recall; no ground-truth labels.'}


def plot_preview(cage, original, kept, dropped, report, output):
    fig, axes=plt.subplots(2,3,figsize=(14,8.5),constrained_layout=True)
    groups=[(original,'Original','#4b82b8'),(kept,'Retained','#128b70'),(dropped,'Candidate hits','#c44a48')]
    for row,(i,j) in enumerate(((0,1),(0,2))):
        for col,(pts,label,color) in enumerate(groups):
            ax=axes[row,col]
            if len(pts):
                ax.scatter(pts[:,i],pts[:,j],s=1.8,alpha=.35,color=color,rasterized=True)
            ax.set(xlim=(-1.2,1.2),ylim=(-1.2,1.2),
                   xlabel=['X','Y','Z'][i]+' (m)',ylabel=['X','Y','Z'][j]+' (m)')
            ax.set_aspect('equal')
            ax.grid(alpha=.15)
            ax.set_title(f'{cage}: {label} ({len(pts):,} display points)')
    fig.suptitle(f'HELD-OUT BAG, FROZEN candidate mask | {Path(report["bag"]).name} | '
                 f'full near-field hit fraction {report["candidate_hit_fraction"]:.1%}\n'
                 'UNVERIFIED self candidates; visualization sampled, statistics use all processed points',fontsize=11)
    fig.savefig(output,dpi=160)
    plt.close(fig)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--bags-root',type=Path,default=Path('~/cage_bags'))
    p.add_argument('--results',type=Path,default=Path('~/cage_filter_ws/analysis/results/day1'))
    p.add_argument('--stride',type=int,default=20)
    p.add_argument('--max-frames',type=int,default=60)
    p.add_argument('--plot-points',type=int,default=15000)
    p.add_argument('--r-min',type=float,default=0.12)
    p.add_argument('--r-max',type=float,default=1.2)
    p.add_argument('--cage',choices=['A','B','both'],default='both')
    args=p.parse_args()
    args.bags_root=args.bags_root.expanduser()
    args.results=args.results.expanduser()
    if args.stride<1 or args.max_frames<1 or args.plot_points<1 or args.r_min<0 or args.r_max<=args.r_min:
        p.error('Invalid stride / max-frames / plot-points / range settings')
    report={}
    for cage,bagname in [('A','04_loop_A'),('B','07_loop_B')]:
        if args.cage not in ('both',cage):
            continue
        bag=args.bags_root/bagname
        if not bag.is_dir():
            raise FileNotFoundError(f'Missing bag: {bag}')
        model,voxel=load_model(args.results/f'candidate_{cage}.npz')
        print(f'[READ] {bagname} | {cage}: {len(model)} frozen candidate voxels',flush=True)
        original,kept,dropped,stat=analyze_heldout(bag,model,voxel,args)
        if cage=='A':
            stat['mechanical_note']='LiDAR moved a few mm relative to the cage during 04_loop_A; treat as disturbed case.'
        out=args.results/f'07_heldout_{cage}.png'
        plot_preview(cage,original,kept,dropped,stat,out)
        report[cage]=stat
        print(f'[DONE] {out} | {stat["candidate_hits"]:,}/{stat["near_field_points_processed"]:,} near-field points = {stat["candidate_hit_fraction"]:.2%}',flush=True)
    out=args.results/'07_heldout_stats.json'
    out.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(f'[DONE] {out}',flush=True)

if __name__=='__main__':
    main()
