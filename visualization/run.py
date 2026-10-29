"""Run from PowerShell: python visualization/run.py [--input ...] [--output ...]."""
from __future__ import annotations
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys

HERE=Path(__file__).resolve().parent


def validate_output(input_dir: Path, output: Path):
    """Task safety boundary: all generated artifacts stay inside this project."""
    if not output.is_relative_to(HERE):
        raise ValueError(f'Output must be inside the visualization project: {HERE}')
    if output==input_dir or output.is_relative_to(input_dir) or input_dir.is_relative_to(output):
        raise ValueError('Input and output trees must not overlap.')
    if any(output==HERE/name or output.is_relative_to(HERE/name) for name in ('src','tests')):
        raise ValueError('Output cannot overwrite the source or tests tree.')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=HERE.parent/'analysis/results/online_controls',help='Read-only log root')
    parser.add_argument('--output',type=Path,default=HERE,help='Output project root (inside visualization/)')
    parser.add_argument('--encoding',default='auto',help='auto: strict UTF-8 or BOM-detected UTF-16; explicit codec also supported')
    parser.add_argument('--audit-only',action='store_true',help='Parse, audit and write CSV/report without figures')
    args=parser.parse_args(argv)
    input_dir,output=args.input.resolve(),args.output.resolve()
    validate_output(input_dir,output)
    os.environ.setdefault('MPLCONFIGDIR',str(HERE/'.mplconfig'))
    from src.log_parser import parse_logs
    from src.data_audit import audit, sha256
    from src.statistics import with_derived,compute_statistics
    from src.reporting import write_report

    print(f'[1/5] Read-only input: {input_dir}',flush=True)
    protected=sorted({p for p in input_dir.rglob('*') if p.is_file()} |
                     {p for p in (HERE.parent/'src').rglob('*') if p.is_file()})
    before={str(p):sha256(p) for p in protected}
    for folder in ('tables','reports','figures'):
        (output/folder).mkdir(parents=True,exist_ok=True)
    result=parse_logs(input_dir,encoding=args.encoding)
    df=with_derived(result.records)
    tables={**audit(result),**compute_statistics(df),'parsed_records':df}
    for name,table in tables.items():
        table.to_csv(output/'tables'/f'{name}.csv',index=False,encoding='utf-8',na_rep='NA',float_format='%.12g')
    print(tables['data_quality'][['group','records','frame_min','frame_max','diagnostics']].to_string(index=False),flush=True)
    diagnostics=result.diagnostics
    print(f'[2/5] {len(df)} records; {len(diagnostics)} diagnostic events.',flush=True)
    if len(diagnostics):
        print(diagnostics.groupby(['severity','code']).size().to_string(),flush=True)
    write_report(df,tables,output/'reports')
    environment={'python':sys.version,'platform':platform.platform(),
                 'packages':{name:importlib.metadata.version(name) for name in ('numpy','pandas','matplotlib','Pillow')},
                 'quantiles':'linear','ratio':'candidate_hits/raw','jitter_seed':20261028}
    (output/'reports/environment.json').write_text(json.dumps(environment,indent=2)+'\n',encoding='utf-8')
    fatal=(diagnostics.severity=='error').any() or not df.analysis_eligible.any()
    if not args.audit_only and not fatal:
        print('[3/5] Exploratory visualization.',flush=True)
        from src.exploration import explore
        explore(df,output/'reports')
        print('[4/5] Five publication figures, three formats each.',flush=True)
        from src.plot_results import make_figures
        make_figures(df,tables,output/'figures')
    else:
        print('[3-4/5] Formal figures skipped: audit-only or blocking data errors.',flush=True)
    after={str(p):sha256(p) if p.is_file() else 'MISSING' for p in protected}
    changed=[str(p) for p in protected if before[str(p)]!=after[str(p)]]
    integrity={'protected_files':len(protected),'changed_files':changed,
               'before':before,'after':after,'status':'PASS' if not changed else 'FAIL'}
    (output/'reports/run_integrity.json').write_text(json.dumps(integrity,indent=2)+'\n',encoding='utf-8')
    if changed:
        raise RuntimeError(f'Protected files changed: {changed}')
    print(f'[5/5] Integrity PASS ({len(protected)} files). Outputs: {output}',flush=True)
    return 2 if fatal else 0


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except (ValueError,FileNotFoundError) as exc:
        print(f'ERROR: {exc}',file=sys.stderr)
        raise SystemExit(2)
