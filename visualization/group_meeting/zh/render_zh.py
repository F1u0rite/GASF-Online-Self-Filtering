"""Chinese presentation variants; reuse English drawing functions in memory only."""
from pathlib import Path
import sys, ast, json, hashlib, re
HERE = Path(__file__).resolve().parent
BASE = HERE.parent
ROOT = BASE.parents[1]
sys.path.insert(0, str(BASE))
import plot_meeting as p
from matplotlib.text import Text
from matplotlib import font_manager
import numpy as np
from PIL import Image, ImageDraw

LABELS = set()
REPORT = []
INVENTORY = '--inventory' in sys.argv
EXPERIMENTS_ONLY = '--experiments-only' in sys.argv
TRANSLATIONS = {} if INVENTORY else json.loads((HERE/'translations_zh.json').read_text(encoding='utf-8'))
FONT = next((f for f in ['Microsoft YaHei','Noto Sans CJK SC','SimHei']
             if any(x.name == f for x in font_manager.fontManager.ttflist)), None)
if not FONT: raise RuntimeError('Install/select a local CJK font before rendering.')

def fingerprint(fig):
    h=hashlib.sha256()
    for ax in fig.axes:
        h.update(repr((ax.get_xlim(),ax.get_ylim())).encode())
        for line in ax.lines:
            for a in (line.get_xdata(),line.get_ydata()): h.update(np.asarray(a,dtype=float).tobytes())
        for c in ax.collections: h.update(np.asarray(c.get_offsets(),dtype=float).tobytes())
        for patch in ax.patches: h.update(patch.get_path().vertices.tobytes())
    return h.hexdigest()

def export(fig, stem, output):
    fig.canvas.draw()
    items=[t for t in fig.findobj(Text) if t.get_text().strip()]
    LABELS.update(t.get_text() for t in items)
    if INVENTORY:
        p.plt.close(fig); return
    before=fingerprint(fig)
    for t in items:
        old=t.get_text()
        if old not in TRANSLATIONS and not (re.fullmatch(r'[0-9.]+(?: ms)?|n=\d+|\d{2}_[a-zA-Z_]+\*?(?:   n=\d+)?',old)
            or old in ['/gasf/model_points','CustomMsg  /livox/lidar','Livox Mid-360']):
            raise RuntimeError(f'Missing translation: {old!r}')
        t.set_text(TRANSLATIONS.get(old,old)); t.set_fontfamily(FONT)
    if stem == '02_mask_hit_ratio_comparison':
        # Only the Chinese footer changes; axes, artists and numeric arrays stay put.
        for t in fig.texts:
            if t.get_position()[1] < .10:
                t.set_text('')
        footer_lines = [
            '箱线图说明：箱体表示第 1 至第 3 四分位数（Q1–Q3），中线表示中位数。',
            '须延伸至 1.5×IQR 范围内的最远数据点，超出范围的点单独显示。',
            '散点沿类别轴轻微抖动，仅用于减少重叠，不改变数据值。',
            '指标定义：Mask 命中比例 = candidate_hits / raw，表示被当前 Mask 命中的点占原始点云总点数的比例。',
        ]
        for y, line in zip((.093, .067, .041, .009), footer_lines):
            items.append(fig.text(.045,y,line,fontsize=14,fontfamily=FONT,va='bottom',color='#333333'))
    assert not any('相对位移' in t.get_text() or '安装发生' in t.get_text() for t in items)
    p.plt.rcParams['svg.fonttype']='none'
    p.plt.rcParams['pdf.fonttype']=42
    fig.canvas.draw()
    assert fingerprint(fig)==before
    # Explicit figure boundary check; inactive off-scale tick labels are ignored.
    renderer=fig.canvas.get_renderer()
    for t in items:
        if not t.get_visible(): continue
        b=t.get_window_extent(renderer)
        if b.x0 < -2 or b.y0 < -2 or b.x1 > fig.bbox.x1+2 or b.y1 > fig.bbox.y1+2:
            if t in [x for ax in fig.axes for x in ax.get_xticklabels()+ax.get_yticklabels()]: continue
            raise RuntimeError('Clipped translated text: '+t.get_text())
    out=HERE/'figures'/('latency_focus' if output.name=='latency_focus' else '')
    out.mkdir(parents=True,exist_ok=True)
    for ext in ('png','svg','pdf'):
        fig.savefig(out/f'{stem}_zh.{ext}',dpi=300,facecolor='white')
    with Image.open(out/f'{stem}_zh.png') as im:
        im.load(); assert im.size==(4800,2700)
        assert all(abs(d-300)<.1 for d in im.info['dpi'])
    REPORT.append({'file':str((out/f'{stem}_zh.png').relative_to(HERE)),
                   'geometry_data_unchanged':True,'fingerprint':before,'text_items':len(items)})
    p.plt.close(fig)

def draw_existing_main(path, boundary, stem, output):
    """Execute only existing main's read/draw section; exclude every original write."""
    tree=ast.parse(path.read_text(encoding='utf-8'))
    main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
    stop=next(i for i,n in enumerate(main.body) if isinstance(n,ast.Expr)
              and ast.unparse(n.value).startswith(boundary))
    main.body=main.body[:stop]+[ast.parse(f"export(fig, {stem!r}, Path({str(output)!r}))").body[0]]
    tree.body=[n for n in tree.body if not isinstance(n,ast.If)]
    ast.fix_missing_locations(tree)
    env={'__file__':str(path),'__name__':'localized_drawing','export':export,'Path':Path}
    exec(compile(tree,str(path),'exec'),env)
    env['main']()

def main():
    files=[f for folder in ['src','analysis/results/online_controls','visualization']
           for f in (ROOT/folder).rglob('*') if f.is_file() and not f.is_relative_to(HERE)
           and not any(x in f.parts for x in ['.venv','__pycache__','.mplconfig'])]
    before={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    parsed=p.parse_logs(ROOT/'analysis/results/online_controls'); assert parsed.diagnostics.empty
    df=p.with_derived(parsed.records); tables=p.compute_statistics(df)
    for name,data in {'parsed_records':df,**tables}.items():
        assert data.to_csv(index=False,na_rep='NA',float_format='%.12g').encode()==(p.VIS/'tables'/f'{name}.csv').read_bytes()
    p.export=export; p.presentation_style()
    for draw in (p.mask_state,p.ratio,p.latency,p.learning): draw(df,tables,BASE/'figures')
    p.learning(df,tables,BASE/'figures',progress=True)
    p.orientation(df,tables,BASE/'figures')
    draw_existing_main(BASE/'plot_latency_focus.py','p.export(',p.STEMS[2],BASE/'figures/latency_focus')
    if not EXPERIMENTS_ONLY:
        draw_existing_main(BASE/'figures/00_gasf_algorithm_overview.py','fig.canvas.draw(',
                           '00_gasf_algorithm_overview',BASE/'figures')
    assert all(hashlib.sha256(Path(f).read_bytes()).hexdigest()==h for f,h in before.items())
    if INVENTORY:
        (HERE/'labels_en.json').write_text(json.dumps(sorted(LABELS),ensure_ascii=False,indent=2),encoding='utf-8')
    else:
        (HERE/'validation_zh.json').write_text(json.dumps({'status':'PASS','protected_files':len(before),
          'records':len(df),'statistics_byte_identical':True,'font':FONT,'figures':REPORT},ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'PASS: {len(LABELS)} labels; {len(REPORT)} Chinese pages; {len(before)} original files unchanged.')

if __name__=='__main__': main()
