"""Parse key=value telemetry without altering inputs or inventing observations."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
from pathlib import Path
import re

import pandas as pd

FIELDS = ('frame', 'raw', 'candidate_hits', 'mask_voxels', 'callback_ms',
          'learning_frames', 'orientation_bins', 'candidate_voxels',
          'dropped_learning_batches')
GROUPS = ('01_static', '02_static_A', '03_arc_A', '04_loop_A',
          '05_static_B', '06_arc_B', '07_loop_B')
META = {
    '01_static': ('Static', 'None', 'Static', 'No outer cage'),
    '02_static_A': ('Static', 'A', 'Static', ''),
    '03_arc_A': ('Dynamic', 'A', 'Arc', ''),
    '04_loop_A': ('Dynamic', 'A', 'Loop', 'Reported LiDAR/cage relative displacement'),
    '05_static_B': ('Static', 'B', 'Static', ''),
    '06_arc_B': ('Dynamic', 'B', 'Arc', ''),
    '07_loop_B': ('Dynamic', 'B', 'Loop', ''),
}
KEY_VALUE = re.compile(r'\b([A-Za-z_][A-Za-z_0-9]*)\s*=\s*([^\s,;\"\'\}\]]*)')
FIELD_HINT = re.compile(r'\b(?:' + '|'.join(FIELDS) + r')\b\s*[:=]')
ISSUE_COLUMNS = ['group', 'source_file', 'source_line', 'severity', 'code', 'field', 'value', 'detail']


@dataclass
class ParseResult:
    records: pd.DataFrame
    diagnostics: pd.DataFrame
    inventory: pd.DataFrame


def identify_group(path: Path, root: Path) -> str | None:
    for group in GROUPS:
        if path.stem == group or group in path.relative_to(root).parts[:-1]:
            return group
    return None


def parse_logs(root: Path | str, encoding: str = 'auto') -> ParseResult:
    """Retain incomplete rows; invalid field values become NA with diagnostics.

    Only recognized delimiters/blank lines are ignored silently. Other lines are
    reported. Duplicate frames are retained but ALL copies excluded from analysis.
    Frame reversals exclude the group's timeline, requiring explicit session split.
    """
    root = Path(root).resolve()
    if not root.is_dir():
        raise FileNotFoundError(root)
    rows, issues, files = [], [], []

    def issue(group, file, line, code, field='', value='', detail='', severity='warning'):
        issues.append(dict(zip(ISSUE_COLUMNS, (group, file, line, severity, code, field, value, detail))))

    for path in sorted(p for p in root.rglob('*') if p.is_file()):
        relative = path.relative_to(root).as_posix()
        group = identify_group(path, root)
        blob = path.read_bytes()
        info = dict(source_file=relative, group=group, bytes=len(blob),
                    sha256=hashlib.sha256(blob).hexdigest(), encoding='',
                    total_lines=0, separator_lines=0, blank_lines=0, record_lines=0,
                    unrecognized_lines=0, format='key=value telemetry')
        files.append(info)
        if group is None or path.suffix.lower() not in ('.log', '.txt'):
            issue(group, relative, 0, 'unrecognized_file', detail='Inventoried but not parsed.')
            continue
        enc = encoding
        if enc == 'auto':
            enc = ('utf-16' if blob.startswith((b'\xff\xfe', b'\xfe\xff'))
                   else 'utf-8-sig' if blob.startswith(b'\xef\xbb\xbf') else 'utf-8')
        info['encoding'] = 'ASCII (UTF-8 compatible)' if blob.isascii() and enc == 'utf-8' else enc
        try:
            content = blob.decode(enc, errors='strict')
        except (UnicodeError, LookupError) as exc:
            issue(group, relative, 0, 'decode_error', detail=str(exc), severity='error')
            continue
        info['newline'] = 'CRLF' if b'\r\n' in blob else 'LF'
        for lineno, original in enumerate(content.splitlines(), 1):
            info['total_lines'] += 1
            line = original.strip()
            if not line:
                info['blank_lines'] += 1
                continue
            if line in ('---', '...'):
                info['separator_lines'] += 1
                continue
            pairs = KEY_VALUE.findall(line)
            if not FIELD_HINT.search(line):
                info['unrecognized_lines'] += 1
                issue(group, relative, lineno, 'unrecognized_line', value=line)
                continue
            info['record_lines'] += 1
            values, duplicates = {}, set()
            for key, value in pairs:
                if key in values:
                    duplicates.add(key)
                values[key] = value
            row = dict(group=group, source_file=relative, source_line=lineno,
                       raw_line=original, mode=values.get('mode'), analysis_eligible=True)
            for field in FIELDS:
                row[field] = pd.NA
                if field not in values:
                    issue(group, relative, lineno, 'missing_field', field)
                    continue
                token = values[field]
                if field in duplicates:
                    issue(group, relative, lineno, 'duplicate_field', field, token)
                    continue
                try:
                    number = Decimal(token)
                    if not number.is_finite() or number < 0:
                        raise ValueError('Expected finite non-negative number')
                    if field == 'callback_ms':
                        number = float(number)
                        if number == float('inf'):
                            raise ValueError('Floating point overflow')
                    else:
                        if number != number.to_integral_value() or number > 2**63 - 1:
                            raise ValueError('Expected non-negative Int64 count')
                        number = int(number)
                    row[field] = number
                except (InvalidOperation, ValueError, OverflowError) as exc:
                    issue(group, relative, lineno, 'invalid_value', field, token, str(exc))
            if row['mode'] != 'online' or 'mode' in duplicates:
                issue(group, relative, lineno, 'invalid_mode', 'mode', str(row['mode']))
                row['analysis_eligible'] = False
            if pd.isna(row['frame']):
                row['analysis_eligible'] = False
            rows.append(row)
    columns = ['group', 'source_file', 'source_line', 'raw_line', 'mode', 'analysis_eligible', *FIELDS]
    df = pd.DataFrame(rows, columns=columns)
    df['analysis_eligible'] = df['analysis_eligible'].astype(bool)
    for field in FIELDS:
        df[field] = df[field].astype('Float64' if field == 'callback_ms' else 'Int64')
    for group in GROUPS:
        sub = df[df.group == group]
        if sub.empty:
            issue(group, '', 0, 'missing_group', detail='No telemetry records found.', severity='error')
            continue
        duplicate = sub.frame.notna() & sub.frame.duplicated(keep=False)
        for idx in sub.index[duplicate]:
            row = df.loc[idx]
            df.loc[idx, 'analysis_eligible'] = False
            issue(group, row.source_file, int(row.source_line), 'duplicate_frame', 'frame', str(row.frame),
                  'All copies retained but excluded from statistics and plots.')
        if (sub.frame.dropna().diff().dropna() < 0).any():
            df.loc[sub.index, 'analysis_eligible'] = False
            issue(group, '', 0, 'frame_reversal', detail='Possible restart: entire group excluded; split sessions first.', severity='error')
        gaps = sub.frame.dropna().diff().dropna()
        if (gaps != 10).any():
            issue(group, '', 0, 'irregular_frame_interval', detail=f'{int((gaps != 10).sum())} intervals differ from 10; no interpolation performed.')
        for _, row in sub.iterrows():
            if pd.notna(row.raw) and row.raw == 0:
                issue(group, row.source_file, int(row.source_line), 'zero_denominator', 'raw', '0',
                      'Mask Hit Ratio is undefined; retained as NA.')
            if pd.notna(row.raw) and pd.notna(row.candidate_hits) and row.candidate_hits > row.raw:
                issue(group, row.source_file, int(row.source_line), 'hits_exceed_raw', 'candidate_hits',
                      str(row.candidate_hits), 'Ratio retained un-clipped; investigate count semantics.', 'error')
            if pd.notna(row.learning_frames) and pd.notna(row.frame) and row.learning_frames > row.frame:
                issue(group, row.source_file, int(row.source_line), 'learning_exceeds_received', 'learning_frames', str(row.learning_frames))
            if pd.notna(row.orientation_bins) and row.orientation_bins > 60:
                issue(group, row.source_file, int(row.source_line), 'exceeds_current_source_bin_cap', 'orientation_bins', str(row.orientation_bins))
    inventory_columns = ['source_file', 'group', 'bytes', 'sha256', 'encoding', 'total_lines',
                         'separator_lines', 'blank_lines', 'record_lines', 'unrecognized_lines', 'format', 'newline']
    return ParseResult(df, pd.DataFrame(issues, columns=ISSUE_COLUMNS), pd.DataFrame(files, columns=inventory_columns))
