"""Human-readable report generated from the same numeric tables as the figures."""
from pathlib import Path
from .data_audit import markdown_table
from .statistics import LATENCY_LIMIT, RATIO_LIMIT


def write_report(df,tables,output: Path):
    quality=tables['data_quality']
    latency=tables['callback_latency_summary']
    ratios=tables['mask_hit_ratio_summary']
    active=tables['mask_activation_summary']
    eligible=df[df.analysis_eligible]
    maximum=eligible.loc[eligible.callback_ms.idxmax()] if eligible.callback_ms.notna().any() else None
    sections=['# GASF online-controls audit and descriptive results',
      'Generated from read-only logs. CSV tables and figures share the same parsed observations. '
      'No smoothing, imputation, interpolation, record synthesis or outlier deletion is performed. '
      'Unknown values are NA. No ground-truth accuracy metric is calculated.',
      '## Inventory and quality',
      f'{len(tables["file_inventory"])} input files inventoried; {len(df)} telemetry records; '
      f'{len(eligible)} analysis-eligible records; {len(tables["parse_diagnostics"])} diagnostic events. '
      'A diagnostic count is not a count of distinct bad records: one record can have several events.',
      markdown_table(quality[['group','records','complete_records','frame_min','frame_max','non_10_intervals','missing_or_invalid_values','diagnostics']]),
      'Each supplied file is ASCII-compatible UTF-8, with CRLF and alternating key=value telemetry / `---` separators. '
      'See file_inventory.csv for the actual encoding, byte count and SHA-256 of each input. '
      'See field_ranges.csv for every core field, valid n, missing n, quartiles, extrema, decreases and Tukey outlier counts. '
      'Outlier flags are descriptive and are never used as exclusion rules. '
      'parse_diagnostics.csv retains every warning/error with source line; an empty file with headers means no diagnostics.',
      '## Mask Hit Ratio',RATIO_LIMIT,
      'All ratio columns are fractions in CSV (multiply by 100 for the figure percentages). '
      'The mean is the arithmetic mean of per-record ratios, including zero/startup observations. '
      'pooled_logged_points_ratio is sum(hits)/sum(raw) across valid ratio rows; it is a different weighting. '
      'Neither is a whole-run point fraction because unlogged frames are unavailable. '
      'raw <= 0 or invalid/missing counts produce NA, not zero. Ratios above 1 are retained and flagged as errors, never clipped.',
      markdown_table(ratios[['group','n_valid','mean','p50','p95','maximum','pooled_logged_points_ratio']]),
      '## Logged callback latency (ms)',LATENCY_LIMIT,
      'P50/P95/P99 use numpy.quantile(method="linear"). These are statistical quantile interpolations between '
      'ordered observed values, not interpolation of missing frames. Standard deviations use ddof=1. '
      'All valid samples are included, including startup and maxima. '
      'The source timer ends before statistics formatting/publishing/logging and before the final header assignment; '
      'it includes conditional point-cloud publication but does not wait for the learner. Subscriber configuration, '
      'hardware load and transport loss are not recorded, so between-run speed differences are descriptive only.',
      markdown_table(latency[['group','n_valid','mean','p50','p95','p99','maximum']]),
      (f'The maximum retained observation is {maximum.callback_ms:.3f} ms in {maximum.group}, Frame {maximum.frame}. '
       'There is no evidence in these logs to classify it as corruption.' if maximum is not None else 'No valid latency samples.'),
      '## Learning and first observed Mask activation',
      markdown_table(active[['group','n_mask_valid','first_positive_sample_frame','bins_at_first_positive_sample','final_mask','final_candidate','final_bins','first_bin_cap_sample_frame']]),
      'First-positive columns describe logged samples. A zero sample followed by a positive sample only brackets '
      'the observed transition, not the first-ever activation: unlogged intervening changes are unknown. '
      'Static zero masks indicate no positive Mask in the recorded snapshots. '
      'trailing_equal_mask_samples and its Frame span describe equal cardinality only; voxel membership is unavailable. '
      'No numerical or algorithmic convergence claim is made.',
      '## Static/dynamic comparability',
      'Root README verifies 01_static as no-outer-cage static; A and B denote distinct cage conditions. '
      '02_static_A and 05_static_B are static; arc/loop runs are dynamic. '
      '04_loop_A has reported LiDAR/cage relative displacement and is explicitly marked in figures. '
      'The experiment duration varies, observations are temporally correlated, and there are no documented repeated trials '
      'under matched conditions. static_dynamic_summary.csv retains each run separately for all five learning metrics, '
      'including per-metric valid sample counts and the Frame of the final nonmissing value. No pooled group test is conducted.',
      'The supplied logs report dropped_learning_batches = 0 throughout. This is the cumulative count of '
      'learning-queue overflows/lock submission failures, not a count of dropped sensor or ROS transport frames. '
      'Frame minus learning_frames is an asynchronous snapshot lag, not elapsed time or evidence of a dropped batch.',
      '## Orientation associations',
      markdown_table(tables['orientation_association'][['group','target','n_pairs','unique_orientation_bins','spearman_rho','status','n_at_source_cap']]),
      'Spearman rho is Pearson correlation of average tied ranks. Constant vectors or insufficient pairs yield NA. '
      'No significance test or confidence interval is computed. Global orientation_bins grows with time and is capped '
      'at 60 in the current source; all dynamic runs reach that cap. Its plateau does not prove complete orientation '
      'coverage. Mask admission depends on per-voxel hits, per-voxel orientation bits and recency, none of which '
      'can be reconstructed from these aggregate logs. Associations can reflect common time trends, cap saturation and '
      'asynchronous snapshots; they do not establish causation or a universal activation threshold.',
      '## Definitions, design and provenance',
      'See [design_plan.md](design_plan.md) for the source-backed field dictionary, experiment-specific limitations, '
      'Skill reference selection and pre-implementation plan. Current source/configuration confirms intended semantics, '
      'but no run manifest ties these logs to a historical binary or exact parameter set. '
      'See [figure captions](../figures/captions.md) for publication-ready interpretation constraints. '
      'run_integrity.json records input/source hashes before and after the run; environment.json records runtime versions.',
      '## Follow-up experiments',
      'Collect repeated cold-start trials with matched duration, sensor playback, subscriber configuration and hardware load; '
      'record build/configuration hashes and mounting condition. Log every callback and end-to-end timing for latency guarantees. '
      'Save Mask voxel identities/snapshots to test membership stability with an explicit convergence criterion. '
      'Collect IMU/pose traces and per-voxel orientation evidence to distinguish bin-cap effects from coverage. '
      'Obtain independently annotated self/environment point labels and appropriate held-out trials before reporting '
      'Precision/Recall or environment false-removal rates.']
    output.mkdir(parents=True,exist_ok=True)
    (output/'audit_report.md').write_text('\n\n'.join(sections)+'\n',encoding='utf-8')
    table_notes=['# Table definitions and limitations',
                 'All CSVs use UTF-8, comma delimiters, decimal points and NA for missing/undefined values. '
                 'Counts are logged-sample counts unless a column explicitly describes points, voxels, frames or bins. '
                 'summary quantiles use linear interpolation; standard deviation uses ddof=1.',
                 RATIO_LIMIT,LATENCY_LIMIT,
                 'parsed_records.csv preserves original Frame, source file/line, complete raw line, per-field NA and analysis eligibility. '
                 'Invalid/duplicate fields are NA with diagnostics. All duplicate Frame copies are retained but excluded. '
                 'A Frame reversal excludes that entire group pending session separation. Non-10 gaps are reported; '
                 'plots break connecting lines across gaps. Non-telemetry text is reported, not silently discarded.',
                 'data_quality / file_inventory / frame_intervals / field_ranges / cross_group_identity / parse_diagnostics: '
                 'inventory, completeness, interval frequencies, raw-data distributions and diagnostics.',
                 'mask_hit_ratio_summary: full logged-run per-record ratios including startup zeros; pooled_logged_points_ratio '
                 'is a separately labelled point-weighted statistic over logged observations only.',
                 'callback_latency_summary: valid recorded callbacks only, in milliseconds; n_valid, mean, standard deviation, '
                 'minimum, P25/P50/P75/P95/P99 and maximum. No full-frame or real-time guarantee.',
                 'static_dynamic_summary: each run and each of five metrics retained separately; endpoints have different durations. '
                 'Orientation association uses descriptive tied-rank Spearman with effective pair counts and no p-values; '
                 'n_pairs is observed pair count, not an autocorrelation-adjusted effective sample size.',
                 'mask_activation_summary: first positive logged sample, not exact physical activation; '
                 'trailing equal counts are not proof of convergence. See reports/audit_report.md for interpretation.']
    (output.parent/'tables/README.md').write_text('\n\n'.join(table_notes)+'\n',encoding='utf-8')
