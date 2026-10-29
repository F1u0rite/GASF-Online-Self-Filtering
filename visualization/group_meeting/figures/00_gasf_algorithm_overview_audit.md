# Local source audit and design record

Scope: current local checkout, online mode. No remote access. Working directory and Git root both resolve to `C:/Users/Sunxiaosun/Desktop/GASF-Online-Self-Filtering`; initial `git status --short` was empty.

## Pre-render implementation checklist

- `gasf_filter_node.cpp`, `on_lidar`: atomic-load one immutable Mask at callback entry. The same point loop checks finite coordinates and inclusive radial range, forms voxel keys and matches the snapshot; independently collects unique voxel keys for learning. The diagram separates these logical paths, not two independent LiDAR callback threads. Queue submission actually follows point-cloud publication.
- `core.hpp`, `make_voxel`: floor each LiDAR-frame coordinate / voxel size. No world transform or CAD registration.
- `on_imu` / `on_lidar`: gyro integration with finite-rate checks, 0 < dt < 0.1 s and 0.015 rad/s deadband; nearest past attitude within 100 ms is attached to each observation. No eligible attitude means hits still accumulate but no orientation bit is added.
- `core.hpp`, `OnlineLearner::update`: per-voxel hits, latest processed learning frame, orientation bit set. Cleanup every 25 processed batches removes age > 250. These are not raw incoming frame IDs.
- `get_orientation_bin`: nearest quaternion reference; create new bin if nearest distance >= 6 degrees and fewer than 60 bins. At cap, reuse nearest bin. Admission counts each voxel's observed bin bits, not global bin count.
- `confirmed`: hits >= 8 AND per-voxel bin count >= 3 AND age <= 250. Failed candidates remain available until pruning. Confirmation does not produce semantic labels.
- Queue: capacity 5; full queue evicts oldest before pushing new batch; failed try-lock drops incoming batch. Background `learning_loop` updates candidates and atomically replaces the Mask every 5 processed batches. Initial Mask empty. No wait for learning completion, but not a claim of a universally lock-free callback (orientation mutex still exists).
- Filtering: valid near-field Mask membership -> removed; all other points -> retained, including invalid coordinates and out-of-range points. No independent correctness labels.
- Outputs: retained/removed PointCloud2 on demand; Mask voxel centers published by 1 s timer on demand; statistics every 10 received frames. Optional filtered CustomMsg disabled in online.yaml. Raw output exists but is omitted from overview for clarity.
- README and online.yaml agree with these mechanisms. Numeric cap 60 and prune interval 25 are hard-coded rather than online.yaml entries. Previous group-meeting speaker notes describe the earlier full-range latency figure; this unrelated historical document is preserved.
- Missing: full body/world motion consistency, semantic cage identity, independent self/environment labels, completed FAST-LIVO2 integration or demonstrated SLAM improvement.

## Design and Skill application

Read installed compatibility entry and plot/SKILL.md, Resonance, Rendition and Appraisal. Inspected gallery index and `plos-cc0-trajectories` card/image: borrow direct labels, arrows and a restrained emphasis box, not its trajectory plot or omissions. No suitable software pipeline template found in filtered gallery index; gallery-local index absent. Custom Matplotlib vector swimlanes follow the user's specified design. Existing six-page overview supplies typography, white background and blue/green palette. Here colors indicate architecture roles, not experiment groups. No new dependencies, gallery writes or uploads.

Parts: upper lane = learning preparation + bounded queue + worker; lower lane = callback filtering; central amber snapshot = atomic update/read handoff; output labels include ROS topics; bottom three limitations remain visible. Detailed timing and publication caveats stay here rather than filling nodes.

The companion script exports one figure object to PNG/SVG/PDF, keeps SVG text editable, checks text bounds and PNG DPI, and hashes existing source/config/log/visualization files before and after. Re-run from repository root: `python visualization/group_meeting/figures/00_gasf_algorithm_overview.py`.
