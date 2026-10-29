"""Data quality summaries and integrity verification."""
import hashlib
import json
from pathlib import Path

import pandas as pd

from .log_parser import FIELDS, GROUPS, ParseResult


def audit(result: ParseResult) -> dict[str, pd.DataFrame]:
    quality, ranges, intervals, similarity = [], [], [], []
    df = result.records
    for group in GROUPS:
        sub = df[df.group == group]
        frames = sub.frame.dropna()
        diff = frames.diff().dropna()
        valid = sub[sub.analysis_eligible]
        counts = diff.value_counts().sort_index()
        for gap, n in counts.items():
            intervals.append(dict(group=group, frame_interval=int(gap), count=int(n)))
        quality.append(dict(group=group, files=int((result.inventory.group == group).sum()),
                            records=len(sub), complete_records=int(sub[list(FIELDS)].notna().all(axis=1).sum()),
                            eligible_records=len(valid), frame_min=frames.min(), frame_max=frames.max(),
                            interval_counts=json.dumps({str(int(k)):int(v) for k,v in counts.items()}),
                            non_10_intervals=int((diff != 10).sum()),
                            duplicate_frame_records=int((frames.duplicated(keep=False)).sum()),
                            missing_or_invalid_values=int(sub[list(FIELDS)].isna().sum().sum()),
                            zero_raw=int((sub.raw == 0).sum()),
                            hits_exceed_raw=int((sub.candidate_hits > sub.raw).sum()),
                            diagnostics=int((result.diagnostics.group == group).sum()),
                            scope='Recorded telemetry only; no independent trial replication'))
        for field in FIELDS:
            x = sub[field].dropna().astype(float)
            q1, q3 = (x.quantile(.25), x.quantile(.75)) if len(x) else (float('nan'), float('nan'))
            ranges.append(dict(group=group, field=field, n_valid=len(x), n_missing=len(sub)-len(x),
                               minimum=x.min(), q25=q1, median=x.median(), q75=q3, maximum=x.max(),
                               unique_values=x.nunique(), decreases=int((x.diff() < 0).sum()),
                               tukey_outliers=int(((x < q1-1.5*(q3-q1)) | (x > q3+1.5*(q3-q1))).sum()),
                               scope='Outlier flags are descriptive; no values removed'))
    for i, ga in enumerate(GROUPS):
        for gb in GROUPS[i+1:]:
            a = df[df.group == ga][list(FIELDS)].reset_index(drop=True)
            b = df[df.group == gb][list(FIELDS)].reset_index(drop=True)
            similarity.append(dict(group_a=ga, group_b=gb, same_record_count=len(a)==len(b),
                                   all_fields_identical=a.equals(b),
                                   counts_identical_excluding_latency=a.drop(columns='callback_ms').equals(b.drop(columns='callback_ms'))))
    return {'data_quality':pd.DataFrame(quality), 'field_ranges':pd.DataFrame(ranges),
            'frame_intervals':pd.DataFrame(intervals), 'cross_group_identity':pd.DataFrame(similarity),
            'file_inventory':result.inventory, 'parse_diagnostics':result.diagnostics}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(paths, root: Path) -> dict:
    return {p.relative_to(root).as_posix():sha256(p) for p in sorted(paths) if p.is_file()}


def markdown_table(df: pd.DataFrame) -> str:
    """No optional tabulate dependency."""
    def fmt(v):
        if pd.isna(v):
            return 'NA'
        if isinstance(v, float):
            return f'{v:.6g}'
        return str(v).replace('|', '\\|').replace('\n', ' ')
    return '\n'.join(['| ' + ' | '.join(df.columns) + ' |',
                      '| ' + ' | '.join(['---']*len(df.columns)) + ' |'] +
                     ['| ' + ' | '.join(fmt(v) for v in row) + ' |' for row in df.itertuples(index=False, name=None)])
