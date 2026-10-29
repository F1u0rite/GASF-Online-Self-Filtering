"""Validate figures, tables and protected-file integrity after running run.py."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
from PIL import Image

HERE=Path(__file__).resolve().parent


def linear_quantile(x,q):
    """Independent scalar implementation used only to verify CSV summaries."""
    ordered=sorted(float(v) for v in x)
    if not ordered:
        return math.nan
    position=(len(ordered)-1)*q
    lo,hi=math.floor(position),math.ceil(position)
    return ordered[lo]+(ordered[hi]-ordered[lo])*(position-lo)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=HERE)
    parser.add_argument('--render-pdfs',action='store_true',help='Optional Poppler QA; requires pdfinfo and pdftoppm on PATH')
    args=parser.parse_args(argv)
    output=args.output.resolve()
    if not output.is_relative_to(HERE):
        raise ValueError('Validation reports must stay inside visualization/.')
    records=pd.read_csv(output/'tables/parsed_records.csv',keep_default_na=False,na_values=['NA'])
    latency=pd.read_csv(output/'tables/callback_latency_summary.csv')
    ratios=pd.read_csv(output/'tables/mask_hit_ratio_summary.csv')
    manifest=json.loads((output/'figures/figure_manifest.json').read_text(encoding='utf-8'))
    checks=[]
    for group in manifest['group_colors']:
        sub=records[(records.group==group)&records.analysis_eligible]
        ratio=sub.loc[sub.raw>0,'candidate_hits']/sub.loc[sub.raw>0,'raw']
        np.testing.assert_allclose(sub.mask_hit_ratio,sub.candidate_hits/sub.raw.replace(0,np.nan),equal_nan=True)
        for metric,values,table in [('latency',sub.callback_ms.dropna(),latency),('ratio',ratio.dropna(),ratios)]:
            saved=table[table.group==group].iloc[0]
            assert saved.n_valid==len(values)
            if not len(values):
                continue
            for name,q in [('p25',.25),('p50',.5),('p75',.75),('p95',.95),('p99',.99)]:
                assert math.isclose(saved[name],linear_quantile(values,q),rel_tol=1e-9,abs_tol=1e-11),(group,metric,name)
            assert math.isclose(saved['mean'],sum(values)/len(values),rel_tol=1e-9,abs_tol=1e-11)
            assert math.isclose(saved.maximum,max(values),rel_tol=1e-9,abs_tol=1e-11)
        checks.append(f'{group}: ratios, sample counts and independent quantile/mean/max checks PASS')
    dimensions=[]
    for stem in manifest['stems']:
        with Image.open(output/'figures'/f'{stem}.png') as im:
            im.load()
            dpi=im.info.get('dpi',(0,0))
            assert all(abs(d-300)<.1 for d in dpi),(stem,dpi)
            assert min(im.size)>1500
            dimensions.append({'figure':stem,'width_px':im.width,'height_px':im.height,'dpi_x':dpi[0],'dpi_y':dpi[1]})
        svg=ET.parse(output/'figures'/f'{stem}.svg').getroot()
        assert svg.tag.endswith('svg')
        assert len(svg.findall('.//{http://www.w3.org/2000/svg}path'))>0
        assert not svg.findall('.//{http://www.w3.org/2000/svg}image'), 'Expected vector paths, not embedded raster'
        pdf=output/'figures'/f'{stem}.pdf'
        content=pdf.read_bytes()
        assert content.startswith(b'%PDF-') and content.rstrip().endswith(b'%%EOF')
        if shutil.which('pdfinfo'):
            info=subprocess.run(['pdfinfo',str(pdf)],capture_output=True,text=True,check=True).stdout
            assert any(line.split(':',1)[-1].strip()=='1' for line in info.splitlines() if line.startswith('Pages:'))
        elif args.render_pdfs:
            raise RuntimeError('Optional --render-pdfs requires Poppler pdfinfo and pdftoppm on PATH.')
        if args.render_pdfs:
            if not shutil.which('pdftoppm'):
                raise RuntimeError('pdftoppm not found')
            render=output/'reports/pdf_render'
            render.mkdir(parents=True,exist_ok=True)
            subprocess.run(['pdftoppm','-f','1','-singlefile','-r','120','-png',str(pdf),str(render/stem)],check=True,capture_output=True)
        checks.append(f'{stem}: 300 DPI PNG, vector SVG, PDF structure'+(' + Poppler page decode/render' if args.render_pdfs else '')+' PASS')
    baseline=HERE/'reports/protected_files_before.json'
    if baseline.exists():
        for name,digest in json.loads(baseline.read_text(encoding='utf-8')).items():
            path=HERE.parent/name
            assert path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==digest,name
        checks.append('Original 17-file baseline: hashes unchanged PASS')
    integrity=json.loads((output/'reports/run_integrity.json').read_text(encoding='utf-8'))
    assert integrity['status']=='PASS' and not integrity['changed_files']
    checks.append('Per-run input/source integrity PASS')
    report={'status':'PASS','checks':checks,'png_metadata':dimensions,
            'pdf_validation':'Poppler rendered all pages' if args.render_pdfs else 'Structure; pdfinfo if available',
            'svg_validation':'XML parsed; vector paths present; no embedded raster images',
            'limitations':'Automatic checks do not replace visual inspection or scientific interpretation.'}
    (output/'reports/validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    for item in checks:
        print(item)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
