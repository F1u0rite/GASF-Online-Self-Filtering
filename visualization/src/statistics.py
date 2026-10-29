"""Descriptive sampled-log statistics, never accuracy or full-frame guarantees."""
import numpy as np
import pandas as pd
from .log_parser import GROUPS, META

LATENCY_LIMIT = ('Logged callback samples only (observed cadence: every 10 frames in supplied logs); '
                 'P95/P99 are not full-frame quantiles or real-time guarantees.')
RATIO_LIMIT = 'candidate_hits / raw over logged samples; not Precision, Recall, Accuracy or F1.'
LEARNING_METRICS = ('learning_frames', 'orientation_bins', 'mask_voxels', 'candidate_voxels', 'dropped_learning_batches')


def with_derived(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['mask_hit_ratio'] = pd.Series(pd.NA, index=df.index, dtype='Float64')
    ok = df.raw.notna() & df.candidate_hits.notna() & (df.raw > 0) & (df.candidate_hits >= 0)
    df.loc[ok, 'mask_hit_ratio'] = df.loc[ok, 'candidate_hits'] / df.loc[ok, 'raw']
    df['learning_lag_frames'] = df.frame - df.learning_frames
    for col, pos in [('motion',0), ('cage',1), ('trajectory',2), ('experiment_note',3)]:
        df[col] = df.group.map(lambda g:META[g][pos])
    return df


def describe(series: pd.Series) -> dict:
    x = series.dropna().to_numpy(dtype=float)
    out = dict(n_valid=len(x), mean=np.nan, std=np.nan, minimum=np.nan, p25=np.nan,
               p50=np.nan, p75=np.nan, p95=np.nan, p99=np.nan, maximum=np.nan)
    if len(x):
        out.update(mean=float(np.mean(x)), std=float(np.std(x, ddof=1)) if len(x)>1 else np.nan,
                   minimum=float(x.min()), maximum=float(x.max()))
        out.update(zip(('p25','p50','p75','p95','p99'), np.quantile(x,[.25,.5,.75,.95,.99],method='linear')))
    return out


def compute_statistics(df: pd.DataFrame) -> dict[str,pd.DataFrame]:
    ratios, latency, learning, activation, orientation = [], [], [], [], []
    for group in GROUPS:
        sub = df[(df.group == group) & df.analysis_eligible].sort_values('frame')
        ratios.append(dict(group=group, n_records=len(sub), n_undefined=int(sub.mask_hit_ratio.isna().sum()),
                           **describe(sub.mask_hit_ratio),
                           pooled_logged_points_ratio=(sub.loc[sub.mask_hit_ratio.notna(),'candidate_hits'].sum() /
                               sub.loc[sub.mask_hit_ratio.notna(),'raw'].sum()) if sub.mask_hit_ratio.notna().any() else np.nan,
                           n_positive=int((sub.mask_hit_ratio > 0).sum()), scope=RATIO_LIMIT))
        latency.append(dict(group=group, n_records=len(sub), **describe(sub.callback_ms),
                            quantile_method='linear', unit='ms', scope=LATENCY_LIMIT))
        for metric in LEARNING_METRICS:
            valid = sub[sub[metric].notna()]
            learning.append(dict(group=group, motion=META[group][0], cage=META[group][1],
                                 trajectory=META[group][2], metric=metric, **describe(sub[metric]),
                                 first=valid[metric].iloc[0] if len(valid) else np.nan,
                                 final=valid[metric].iloc[-1] if len(valid) else np.nan,
                                 final_metric_frame=valid.frame.iloc[-1] if len(valid) else np.nan,
                                 experiment_note=META[group][3],
                                 scope='Per experiment; unequal lengths; no pooled static/dynamic inference'))
        active = sub[sub.mask_voxels > 0]
        first = active.iloc[0] if len(active) else None
        preceding = sub[(sub.frame < first.frame) & sub.mask_voxels.notna()] if first is not None else sub.iloc[:0]
        previous = preceding.iloc[-1] if len(preceding) else None
        valid_mask = sub[sub.mask_voxels.notna()]
        tail_n = 0
        if len(valid_mask):
            final_mask = valid_mask.mask_voxels.iloc[-1]
            for value in reversed(valid_mask.mask_voxels.tolist()):
                if value != final_mask:
                    break
                tail_n += 1
        activation.append(dict(group=group, n_mask_valid=len(valid_mask), n_positive_mask=len(active),
                               last_zero_before_first_positive_frame=previous.frame if previous is not None and previous.mask_voxels==0 else np.nan,
                               first_positive_sample_frame=first.frame if first is not None else np.nan,
                               bins_at_first_positive_sample=first.orientation_bins if first is not None else np.nan,
                               first_positive_hit_frame=sub.loc[sub.candidate_hits>0,'frame'].min(),
                               final_mask=valid_mask.mask_voxels.iloc[-1] if len(valid_mask) else np.nan,
                               final_candidate=sub.candidate_voxels.iloc[-1] if len(sub) else np.nan,
                               final_bins=sub.orientation_bins.iloc[-1] if len(sub) else np.nan,
                               first_bin_cap_sample_frame=sub.loc[sub.orientation_bins==60,'frame'].min(),
                               trailing_equal_mask_samples=tail_n,
                               trailing_equal_mask_frame_span=(valid_mask.frame.iloc[-1]-valid_mask.frame.iloc[-tail_n]) if tail_n else np.nan,
                               scope='First positive LOGGED sample; equality of voxel counts is not convergence or mask identity'))
        for target in ('mask_voxels','candidate_voxels'):
            pairs = sub[['orientation_bins',target]].dropna().astype(float)
            constant = len(pairs)<2 or pairs.nunique().min()<2
            rho = np.nan if constant else pairs.orientation_bins.rank(method='average').corr(pairs[target].rank(method='average'))
            orientation.append(dict(group=group, target=target, n_pairs=len(pairs),
                                    unique_orientation_bins=pairs.orientation_bins.nunique(),
                                    spearman_rho=rho, status='undefined_constant_or_insufficient' if constant else 'descriptive_only',
                                    n_at_source_cap=int((pairs.orientation_bins==60).sum()),
                                    method='Spearman: Pearson correlation of average tied ranks; no p-values',
                                    scope='Autocorrelated time series; cap=60; asynchronous snapshots; no causal inference'))
    return {'mask_hit_ratio_summary':pd.DataFrame(ratios), 'callback_latency_summary':pd.DataFrame(latency),
            'static_dynamic_summary':pd.DataFrame(learning), 'mask_activation_summary':pd.DataFrame(activation),
            'orientation_association':pd.DataFrame(orientation)}
