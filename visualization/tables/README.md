# Table definitions and limitations

All CSVs use UTF-8, comma delimiters, decimal points and NA for missing/undefined values. Counts are logged-sample counts unless a column explicitly describes points, voxels, frames or bins. summary quantiles use linear interpolation; standard deviation uses ddof=1.

candidate_hits / raw over logged samples; not Precision, Recall, Accuracy or F1.

Logged callback samples only (observed cadence: every 10 frames in supplied logs); P95/P99 are not full-frame quantiles or real-time guarantees.

parsed_records.csv preserves original Frame, source file/line, complete raw line, per-field NA and analysis eligibility. Invalid/duplicate fields are NA with diagnostics. All duplicate Frame copies are retained but excluded. A Frame reversal excludes that entire group pending session separation. Non-10 gaps are reported; plots break connecting lines across gaps. Non-telemetry text is reported, not silently discarded.

data_quality / file_inventory / frame_intervals / field_ranges / cross_group_identity / parse_diagnostics: inventory, completeness, interval frequencies, raw-data distributions and diagnostics.

mask_hit_ratio_summary: full logged-run per-record ratios including startup zeros; pooled_logged_points_ratio is a separately labelled point-weighted statistic over logged observations only.

callback_latency_summary: valid recorded callbacks only, in milliseconds; n_valid, mean, standard deviation, minimum, P25/P50/P75/P95/P99 and maximum. No full-frame or real-time guarantee.

static_dynamic_summary: each run and each of five metrics retained separately; endpoints have different durations. Orientation association uses descriptive tied-rank Spearman with effective pair counts and no p-values; n_pairs is observed pair count, not an autocorrelation-adjusted effective sample size.

mask_activation_summary: first positive logged sample, not exact physical activation; trailing equal counts are not proof of convergence. See reports/audit_report.md for interpretation.
