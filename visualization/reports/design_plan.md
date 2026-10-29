# Phase 1: audit and figure design (before final plotting)

All observations below were obtained from the existing logs and current repository source. They do not establish which exact binary/configuration was used when the experiments ran.

## Completed audit

Seven ASCII-compatible UTF-8 `.log` files, CRLF newlines, one `mode=online key=value` telemetry line followed by `---`. 1,690 total lines comprise 845 telemetry records and 845 separators. No missing/illegal core values, duplicate frames, unrecognized lines, zero raw denominators or hits greater than raw. All 838 within-experiment frame intervals equal 10. No pairs of experiments have identical telemetry, including when latency is excluded.

| Experiment | Records | Frame range | Design |
| --- | ---: | --- | --- |
| 01_static | 64 | 10–640 | Static, no outer cage |
| 02_static_A | 63 | 10–630 | Static, cage A |
| 03_arc_A | 177 | 10–1770 | Arc, cage A |
| 04_loop_A | 174 | 10–1740 | Loop, cage A; reported relative displacement |
| 05_static_B | 71 | 10–710 | Static, cage B |
| 06_arc_B | 177 | 10–1770 | Arc, cage B |
| 07_loop_B | 119 | 10–1190 | Loop, cage B |

Static records show candidate accumulation, orientation bins 1–2 and zero active Mask/hits. Four dynamic runs show positive Masks, first recorded at frames 170, 140, 170 and 50 respectively. All dynamic runs reach the source's 60-bin capacity. The static/dynamic durations differ; A/B are cage conditions, not independent replicates of one condition. Do not pool samples for significance tests.

03_arc_A contains a 9.304 ms recorded callback; retain it in full-range plots and tables. Tukey outlier counts are diagnostic only and often flag startup/zero phases; no outliers are removed. Mask/candidate counts can decrease, consistent with candidate expiry/snapshot updates. Count plateaus do not establish voxel identity stability or algorithm convergence.

## Confirmed semantics and uncertainties

Read-only evidence: `src/gasf_filter/src/gasf_filter_node.cpp` (on_lidar, lines 160–240; learning_loop, 243–260), `src/gasf_filter/include/gasf_filter/core.hpp` (OnlineLearner, 63–127), `src/gasf_filter/config/online.yaml`, and root `README.md`, experiment section.

- frame: received LiDAR callback counter; not timestamps or log-line indices.
- raw: `msg->points.size()`, all incoming points including nonfinite/non-near-field points.
- candidate_hits: finite near-field points hitting the Mask snapshot loaded at callback start; counts points, not voxels.
- mask_voxels: size of that immutable Mask snapshot.
- callback_ms: steady-clock elapsed milliseconds from callback entry through processing/publication/enqueue, measured **before** statistics formatting/publishing/logging and final header assignment. Background learning is asynchronous; this does not measure end-to-end latency or the entire callback return time.
- learning_frames: learner's processed observation-batch count, asynchronously published.
- orientation_bins: number of stored relative IMU orientation prototypes; current source caps it at 60, default angular separation 6 degrees. Global coverage is not the per-voxel orientation bit count used for admission.
- candidate_voxels: current size of learner's candidate map, including unconfirmed candidates; not cumulative unique voxels ever seen, nor disjoint from active Mask.
- dropped_learning_batches: cumulative learner queue discards or failed queue-lock submissions; not LiDAR/ROS transport loss. Zero reports cannot establish complete sensor delivery.

Defaults require per-voxel hits >=8, per-voxel orientation-bin count >=3 and recency <=250 learner batches. Candidate cleanup runs every 25 learner updates and Mask snapshots every 5 by default. Model state and atomics are sampled at different instants. No historical run manifests, subscriber loads, exact build hashes, voxel identities, full callback traces or ground truth are available in these logs.

## Skill application and chosen components

Read the compatibility entry, plot/SKILL.md and Resonance, Rendition and Appraisal stages in full. Used the explicit no-confirmation instruction as the Skill's quick path. Read gallery index and opened three reference images and cards. All three cards have empty code fields, so there was no reference implementation to reuse.

1. `oa-tech-pone-0258309-f04`: observation points + box summaries, restrained whitespace, thin borders. Primary distribution grammar. Whiskers are 1.5 IQR, not confidence intervals.
2. `oa-geo-hess-30-629-2026-f12`: paired panels and ECDF. Alternative density appearance is shown in style_references.png; density smoothing is unsuitable for the zero-heavy current ratios and is not used.
3. `oa-geo-esd-15-527-2024-f04`: paired response plots with consistent category encoding. Borrow arrangement for orientation relationships, not its domain-specific data or unsupported causal interpretation.

Chosen palette is Okabe-Ito + neutral grey, adapted from the references' categorical separation to satisfy the user's color-vision requirement; shapes also encode experiments. All numeric axes start at zero. Formal figures preserve individual observations. No gallery files, taste records or installed skill files are modified; no new packages are installed.

Six real-data exploratory views in `exploratory_overview.png` precede final plotting: mask/candidate trajectories, ratio boxes, latency ECDF, raw counts and bins-versus-mask scatter. They guide selection away from density estimation and pooled group bars, toward per-run facets, observation points and a full-range latency view.

## Formal figure plan

| Figure | Design and evidence supported | Not supported |
| --- | --- | --- |
| 1 Online Mask Convergence | Seven equal-scale facets; observed Mask and candidate counts vs original Frame; first-positive sample markers | Proven convergence, exact activation instant, fixed voxel membership |
| 2 Mask Hit Ratio Comparison | Per-run horizontal boxes + all samples; sample-mean markers; secondary Frame trajectories; n shown | Precision/Recall/Accuracy, inference that larger ratios are better |
| 3 Runtime Latency Distribution | Full-range ECDF + per-run sample distributions; annotated maximum; mean/P50/P95/P99/max in CSV and summary | Full-frame quantiles, timing deadlines or real-time guarantees |
| 4 Static vs Dynamic Learning | Five metric rows, static/dynamic columns with matching row scales; individual experiments retained; no pooled bars | Causal motion effects, significance, endpoint comparison independent of duration |
| 5 Orientation Diversity vs Mask Activation | 2x2 scatter panels: cage A/B columns, Mask/candidate rows; no-cage static baseline shown in both for context; 60-bin cap marked | Universal activation threshold, causal effect, independent-sample p-values |

All five have English titles, axes, legends and captions; PNG 300 DPI, SVG and PDF share the same figure objects. Spearman results are descriptive only, with valid pair counts; constant-series coefficients are NA. Unequal duration, no-cage baseline and disturbed loop are prominently documented.
