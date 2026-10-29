"""Validate meeting figures and render optional PDF QA previews; no package installs."""
from pathlib import Path
import argparse
import json
import shutil
import subprocess
import xml.etree.ElementTree as ET
from PIL import Image,ImageDraw,ImageFont,ImageOps
from plot_meeting import HERE,VIS,STEMS,GROUPS,check_originals


def fitted(path,size):
    with Image.open(path) as source:
        return ImageOps.contain(source.convert('RGB'),size,Image.Resampling.LANCZOS)


def contact_sheet(items,path,columns=2,width=960):
    font=ImageFont.truetype('DejaVuSans.ttf',22)
    height=540
    rows=(len(items)+columns-1)//columns
    sheet=Image.new('RGB',(columns*width,rows*(height+45)),'white')
    draw=ImageDraw.Draw(sheet)
    for i,(label,image) in enumerate(items):
        x=(i%columns)*width; y=(i//columns)*(height+45)
        draw.text((x+15,y+9),label,fill='#222222',font=font)
        thumb=fitted(image,(width-20,height))
        sheet.paste(thumb,(x+(width-thumb.width)//2,y+45+(height-thumb.height)//2))
    sheet.save(path)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--render-pdfs',action='store_true')
    args=parser.parse_args()
    validation=json.loads((HERE/'reports/validation.json').read_text(encoding='utf-8'))
    assert validation['status']=='PASS' and validation['records']==845
    checks=validation['visual_data_checks']
    # Every experiment is represented in every page. Figure 5 deliberately repeats
    # the no-cage reference across the two cage columns.
    for stem in STEMS:
        represented={c['group'] for c in checks if c['figure']==stem}
        assert represented==set(GROUPS),(stem,represented)
        for c in [c for c in checks if c['figure']==stem]:
            assert c['n']==validation['group_n'][c['group']]
    structure=[]
    for stem in STEMS:
        png=HERE/'figures'/f'{stem}.png'
        with Image.open(png) as im:
            im.load(); assert im.size==(4800,2700)
            assert all(abs(v-300)<.1 for v in im.info['dpi'])
        svg=ET.parse(HERE/'figures'/f'{stem}.svg').getroot()
        assert not svg.findall('.//{http://www.w3.org/2000/svg}image')
        assert svg.findall('.//{http://www.w3.org/2000/svg}path')
        pdf=HERE/'figures'/f'{stem}.pdf'
        assert pdf.read_bytes().startswith(b'%PDF-')
        if args.render_pdfs:
            if not shutil.which('pdfinfo') or not shutil.which('pdftoppm'):
                raise RuntimeError('Optional PDF render validation requires Poppler on PATH.')
            info=subprocess.run(['pdfinfo',str(pdf)],capture_output=True,text=True,check=True).stdout
            assert 'Pages:           1' in info
            render=HERE/'reports/pdf_render'; render.mkdir(exist_ok=True)
            subprocess.run(['pdftoppm','-singlefile','-r','100','-png',str(pdf),str(render/stem)],check=True,capture_output=True)
        structure.append({'figure':stem,'png_px':[4800,2700],'png_dpi':300,'svg':'vector XML PASS',
                          'pdf':'Poppler decoded and rendered' if args.render_pdfs else 'Header checked'})
    old=['01_online_mask_convergence','02_mask_hit_ratio_comparison','03_runtime_latency_distribution',
         '04_static_vs_dynamic_learning','05_orientation_diversity_vs_mask_activation']
    new=[STEMS[i] for i in [0,1,2,3,5]]
    for i,(a,b) in enumerate(zip(old,new),1):
        contact_sheet([('Before: original layout on a 16:9 slide',VIS/'figures'/f'{a}.png'),
                       ('After: group-meeting layout',HERE/'figures'/f'{b}.png')],HERE/'reports'/f'comparison_{i:02d}.png')
    contact_sheet([(stem,HERE/'figures'/f'{stem}.png') for stem in STEMS],HERE/'reports/overview.png')
    protected=check_originals()
    result={'status':'PASS','pages':structure,'data_artist_checks':len(checks),
            'each_page_represents_all_seven_runs':True,'original_files_unchanged':protected}
    (HERE/'reports/format_validation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(f'PASS: {len(STEMS)} pages, {len(checks)} visual data checks, {protected} protected files unchanged.')
    print(f'Before/after comparisons: {HERE/"reports"}')


if __name__=='__main__': main()
