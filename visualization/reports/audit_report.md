# GASF online-controls audit and descriptive results

Generated from read-only logs. CSV tables and figures share the same parsed observations. No smoothing, imputation, interpolation, record synthesis or outlier deletion is performed. Unknown values are NA. No ground-truth accuracy metric is calculated.

## Inventory and quality

7 input files inventoried; 845 telemetry records; 845 analysis-eligible records; 0 diagnostic events. A diagnostic count is not a count of distinct bad records: one record can have several events.

| group | records | complete_records | frame_min | frame_max | non_10_intervals | missing_or_invalid_values | diagnostics |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 01_static | 64 | 64 | 10 | 640 | 0 | 0 | 0 |
| 02_static_A | 63 | 63 | 10 | 630 | 0 | 0 | 0 |
| 03_arc_A | 177 | 177 | 10 | 1770 | 0 | 0 | 0 |
| 04_loop_A | 174 | 174 | 10 | 1740 | 0 | 0 | 0 |
| 05_static_B | 71 | 71 | 10 | 710 | 0 | 0 | 0 |
| 06_arc_B | 177 | 177 | 10 | 1770 | 0 | 0 | 0 |
| 07_loop_B | 119 | 119 | 10 | 1190 | 0 | 0 | 0 |

Each supplied file is ASCII-compatible UTF-8, with CRLF and alternating key=value telemetry / `---` separators. See file_inventory.csv for the actual encoding, byte count and SHA-256 of each input. See field_ranges.csv for every core field, valid n, missing n, quartiles, extrema, decreases and Tukey outlier counts. Outlier flags are descriptive and are never used as exclusion rules. parse_diagnostics.csv retains every warning/error with source line; an empty file with headers means no diagnostics.

## Mask Hit Ratio

candidate_hits / raw over logged samples; not Precision, Recall, Accuracy or F1.

All ratio columns are fractions in CSV (multiply by 100 for the figure percentages). The mean is the arithmetic mean of per-record ratios, including zero/startup observations. pooled_logged_points_ratio is sum(hits)/sum(raw) across valid ratio rows; it is a different weighting. Neither is a whole-run point fraction because unlogged frames are unavailable. raw <= 0 or invalid/missing counts produce NA, not zero. Ratios above 1 are retained and flagged as errors, never clipped.

| group | n_valid | mean | p50 | p95 | maximum | pooled_logged_points_ratio |
| --- | --- | --- | --- | --- | --- | --- |
| 01_static | 64 | 0 | 0 | 0 | 0 | 0 |
| 02_static_A | 63 | 0 | 0 | 0 | 0 | 0 |
| 03_arc_A | 177 | 0.0164123 | 0.017195 | 0.0217015 | 0.0222787 | 0.0164179 |
| 04_loop_A | 174 | 0.017059 | 0.0178035 | 0.0220793 | 0.0230869 | 0.0170599 |
| 05_static_B | 71 | 0 | 0 | 0 | 0 | 0 |
| 06_arc_B | 177 | 0.031832 | 0.0341906 | 0.0385965 | 0.0394238 | 0.0318338 |
| 07_loop_B | 119 | 0.0348959 | 0.0357356 | 0.0401807 | 0.0416667 | 0.0348985 |

## Logged callback latency (ms)

Logged callback samples only (observed cadence: every 10 frames in supplied logs); P95/P99 are not full-frame quantiles or real-time guarantees.

P50/P95/P99 use numpy.quantile(method="linear"). These are statistical quantile interpolations between ordered observed values, not interpolation of missing frames. Standard deviations use ddof=1. All valid samples are included, including startup and maxima. The source timer ends before statistics formatting/publishing/logging and before the final header assignment; it includes conditional point-cloud publication but does not wait for the learner. Subscriber configuration, hardware load and transport loss are not recorded, so between-run speed differences are descriptive only.

| group | n_valid | mean | p50 | p95 | p99 | maximum |
| --- | --- | --- | --- | --- | --- | --- |
| 01_static | 64 | 1.85784 | 2.0305 | 2.4709 | 3.0645 | 3.096 |
| 02_static_A | 63 | 1.91744 | 2.17 | 2.3726 | 2.60112 | 2.678 |
| 03_arc_A | 177 | 1.31563 | 1.103 | 2.2572 | 2.90344 | 9.304 |
| 04_loop_A | 174 | 1.43467 | 1.4515 | 1.8316 | 1.97847 | 2.244 |
| 05_static_B | 71 | 1.73134 | 1.73 | 2.3875 | 3.0766 | 3.148 |
| 06_arc_B | 177 | 1.49769 | 1.512 | 2.1064 | 2.52424 | 2.711 |
| 07_loop_B | 119 | 0.690462 | 0.571 | 1.5341 | 1.9205 | 2.195 |

The maximum retained observation is 9.304 ms in 03_arc_A, Frame 1500. There is no evidence in these logs to classify it as corruption.

## Learning and first observed Mask activation

| group | n_mask_valid | first_positive_sample_frame | bins_at_first_positive_sample | final_mask | final_candidate | final_bins | first_bin_cap_sample_frame |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 01_static | 64 | NA | NA | 0 | 77 | 2 | NA |
| 02_static_A | 63 | NA | NA | 0 | 185 | 2 | NA |
| 03_arc_A | 177 | 170 | 5 | 191 | 228 | 60 | 1730 |
| 04_loop_A | 174 | 140 | 4 | 235 | 267 | 60 | 690 |
| 05_static_B | 71 | NA | NA | 0 | 229 | 2 | NA |
| 06_arc_B | 177 | 170 | 3 | 241 | 286 | 60 | 1550 |
| 07_loop_B | 119 | 50 | 4 | 281 | 354 | 60 | 490 |

First-positive columns describe logged samples. A zero sample followed by a positive sample only brackets the observed transition, not the first-ever activation: unlogged intervening changes are unknown. Static zero masks indicate no positive Mask in the recorded snapshots. trailing_equal_mask_samples and its Frame span describe equal cardinality only; voxel membership is unavailable. No numerical or algorithmic convergence claim is made.

## Static/dynamic comparability

Root README verifies 01_static as no-outer-cage static; A and B denote distinct cage conditions. 02_static_A and 05_static_B are static; arc/loop runs are dynamic. 04_loop_A has reported LiDAR/cage relative displacement and is explicitly marked in figures. The experiment duration varies, observations are temporally correlated, and there are no documented repeated trials under matched conditions. static_dynamic_summary.csv retains each run separately for all five learning metrics, including per-metric valid sample counts and the Frame of the final nonmissing value. No pooled group test is conducted.

The supplied logs report dropped_learning_batches = 0 throughout. This is the cumulative count of learning-queue overflows/lock submission failures, not a count of dropped sensor or ROS transport frames. Frame minus learning_frames is an asynchronous snapshot lag, not elapsed time or evidence of a dropped batch.

## Orientation associations

| group | target | n_pairs | unique_orientation_bins | spearman_rho | status | n_at_source_cap |
| --- | --- | --- | --- | --- | --- | --- |
| 01_static | mask_voxels | 64 | 2 | NA | undefined_constant_or_insufficient | 0 |
| 01_static | candidate_voxels | 64 | 2 | 0.75431 | descriptive_only | 0 |
| 02_static_A | mask_voxels | 63 | 2 | NA | undefined_constant_or_insufficient | 0 |
| 02_static_A | candidate_voxels | 63 | 2 | 0.44961 | descriptive_only | 0 |
| 03_arc_A | mask_voxels | 177 | 48 | 0.40496 | descriptive_only | 5 |
| 03_arc_A | candidate_voxels | 177 | 48 | 0.283264 | descriptive_only | 5 |
| 04_loop_A | mask_voxels | 174 | 50 | 0.816305 | descriptive_only | 106 |
| 04_loop_A | candidate_voxels | 174 | 50 | 0.651618 | descriptive_only | 106 |
| 05_static_B | mask_voxels | 71 | 2 | NA | undefined_constant_or_insufficient | 0 |
| 05_static_B | candidate_voxels | 71 | 2 | 0.0743235 | descriptive_only | 0 |
| 06_arc_B | mask_voxels | 177 | 52 | 0.963516 | descriptive_only | 23 |
| 06_arc_B | candidate_voxels | 177 | 52 | 0.905271 | descriptive_only | 23 |
| 07_loop_B | mask_voxels | 119 | 34 | 0.888188 | descriptive_only | 71 |
| 07_loop_B | candidate_voxels | 119 | 34 | 0.578654 | descriptive_only | 71 |

Spearman rho is Pearson correlation of average tied ranks. Constant vectors or insufficient pairs yield NA. No significance test or confidence interval is computed. Global orientation_bins grows with time and is capped at 60 in the current source; all dynamic runs reach that cap. Its plateau does not prove complete orientation coverage. Mask admission depends on per-voxel hits, per-voxel orientation bits and recency, none of which can be reconstructed from these aggregate logs. Associations can reflect common time trends, cap saturation and asynchronous snapshots; they do not establish causation or a universal activation threshold.

## Definitions, design and provenance

See [design_plan.md](design_plan.md) for the source-backed field dictionary, experiment-specific limitations, Skill reference selection and pre-implementation plan. Current source/configuration confirms intended semantics, but no run manifest ties these logs to a historical binary or exact parameter set. See [figure captions](../figures/captions.md) for publication-ready interpretation constraints. run_integrity.json records input/source hashes before and after the run; environment.json records runtime versions.

## Follow-up experiments

Collect repeated cold-start trials with matched duration, sensor playback, subscriber configuration and hardware load; record build/configuration hashes and mounting condition. Log every callback and end-to-end timing for latency guarantees. Save Mask voxel identities/snapshots to test membership stability with an explicit convergence criterion. Collect IMU/pose traces and per-voxel orientation evidence to distinguish bin-cap effects from coverage. Obtain independently annotated self/environment point labels and appropriate held-out trials before reporting Precision/Recall or environment false-removal rates.
