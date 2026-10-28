#!/usr/bin/env python3
"""Export exploratory NPZ candidate voxels to a simple text index list for frozen diagnostics.
NEVER claims the voxels are verified self points.
"""
import argparse
from pathlib import Path
import numpy as np

ap=argparse.ArgumentParser()
ap.add_argument('--npz',type=Path,required=True)
ap.add_argument('--out',type=Path,required=True)
a=ap.parse_args()
with np.load(a.npz) as f:
    idx=np.asarray(f['voxel_indices'],dtype=np.int32)
    vox=float(f['voxel_size'])
with a.out.open('w') as h:
    h.write(f'# UNVERIFIED diagnostic mask, voxel_size={vox:.8f} m\n')
    for x,y,z in idx:
        h.write(f'{x} {y} {z}\n')
print(f'exported {len(idx)} voxels to {a.out}; voxel size={vox:.5f} m')
