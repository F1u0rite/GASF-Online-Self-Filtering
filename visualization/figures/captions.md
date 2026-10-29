## 01_online_mask_convergence

Online Mask Convergence (observed trajectories). Points are logged observations; connecting lines are visual guides, not interpolated data. Solid lines show the active snapshot count and dashed lines show the candidate-map count. All facets share scales and retain actual Frame numbers. The first positive Mask sample is annotated, not an exact activation instant. Equal counts do not prove convergence or equal voxel membership. Candidate and Mask states are asynchronous. *04_loop_A: reported LiDAR/cage relative displacement.

## 02_mask_hit_ratio_comparison

Mask Hit Ratio Comparison. Mask Hit Ratio = candidate_hits / raw, plotted as a percentage of all incoming points at logged frames. Boxes show Q1, median and Q3; whiskers extend to the furthest observations within 1.5 IQR. Every valid logged observation is shown, with deterministic vertical jitter only. Hollow diamonds show the arithmetic mean of per-record ratios. The lower panel retains the original temporal trajectories. Sample counts are not independent trial counts. This metric is not Precision, Recall, Accuracy or F1. *04_loop_A: reported LiDAR/cage relative displacement.

## 03_runtime_latency_distribution

Runtime Latency Distribution. Logged callback_ms observations, recorded every 10 frames in the supplied logs. Boxes show Q1/P50/Q3, with 1.5-IQR whiskers and all samples; diamonds indicate means. The empirical CDF uses all valid recorded observations without smoothing. The complete observed range, including the maximum, is retained. P95/P99 in the associated table describe these sampled log points, not all frames, and provide no real-time guarantee. The timer excludes statistics emission and asynchronous worker completion. *04_loop_A: reported LiDAR/cage relative displacement.

## 04_static_vs_dynamic_learning

Static vs Dynamic Learning. Each experiment remains separate; columns distinguish motion labels verified against the repository README. Rows share scales between static and dynamic panels and show actual logged Frame values. No-cage static 01_static is a distinct baseline. A/B denote cage conditions, not replicates. Unequal durations and uncontrolled runtime settings prevent causal or pooled significance claims. Global orientation bins have a source cap of 60. The learner counters and Mask snapshot are asynchronously observed. *04_loop_A: reported LiDAR/cage relative displacement.

## 05_orientation_diversity_vs_mask_activation

Orientation Diversity vs Mask Activation. Each point is an actual logged observation, with no positional jitter, fitted trend or interpolation; coincident points overlap. Cage A/B are separate columns; the same no-cage static reference is repeated in both and not counted as an additional experiment. Dashed lines mark the current source cap of 60 global orientation bins, not a universal Mask activation threshold. Spearman associations in the associated table are descriptive, with tied ranks and pair counts; no p-values are reported because observations are temporally dependent and cap-limited. Constant-series correlations are undefined. Global bins differ from per-voxel admission bins, and logged model states are asynchronous. *04_loop_A: reported LiDAR/cage relative displacement.
