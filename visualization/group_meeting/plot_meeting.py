"""16:9 presentation adaptation of src/plot_results.py; original files stay intact.

Reuses the existing parser, derived values, statistics, colors, trace helper and
three-format export. Only layout, typography and display treatments differ.
Run from the repository root: python visualization/group_meeting/plot_meeting.py
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
VIS=HERE.parent
ROOT=VIS.parent
os.environ.setdefault('MPLCONFIGDIR',str(HERE/'.mplconfig'))
sys.path.insert(0,str(VIS))

import numpy as np
import pandas as pd
from PIL import Image
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator

from src.log_parser import parse_logs,FIELDS,GROUPS,META
from src.statistics import with_derived,compute_statistics
from src.style import COLORS,MARKERS,numeric,trace,setup
from src.plot_results import export,subset

STATIC=[g for g in GROUPS if META[g][0]=='Static']
DYNAMIC=[g for g in GROUPS if META[g][0]=='Dynamic']
ORDER=STATIC+DYNAMIC
LABEL={g:g+('*' if g=='04_loop_A' else '') for g in GROUPS}
SHORT=dict(zip(GROUPS,['01 Static / no cage','02 Static A','03 Arc A','04 Loop A*',
                       '05 Static B','06 Arc B','07 Loop B']))
STEMS=['01_online_mask_state_evolution','02_mask_hit_ratio_comparison',
       '03_runtime_latency_distribution','04_static_vs_dynamic_learning',
       '04b_learning_progress_and_queue','05_orientation_diversity_vs_mask_activation']
PLOT_CHECKS=[]


def presentation_style():
    setup()
    plt.rcParams.update({'font.size':16,'axes.titlesize':18,'axes.labelsize':17,
        'xtick.labelsize':14,'ytick.labelsize':14,'legend.fontsize':14,
        'figure.titlesize':28,'axes.linewidth':1.1,'lines.linewidth':2,
        'svg.hashsalt':'gasf-group-meeting-v1'})


def canvas(title,subtitle):
    fig=plt.figure(figsize=(16,9))
    fig.text(.045,.966,title,fontsize=28,fontweight='bold',va='top')
    fig.text(.045,.912,subtitle,fontsize=17,color='#444444',va='top')
    return fig


def foot(fig,text,second=None):
    fig.text(.045,.035,text,fontsize=14,va='bottom',color='#333333')
    if second:
        fig.text(.045,.067,second,fontsize=14,va='bottom',color='#333333')


def legend(fig,groups=ORDER,y=.869,columns=4):
    handles=[Line2D([],[],color=COLORS[g],marker=MARKERS[g],markersize=7,
                     label=LABEL[g],lw=2) for g in groups]
    fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.52,y),ncol=columns,
               columnspacing=1.5,handlelength=1.7,labelspacing=.5)


def axes_style(ax,xlim=None,ylim=None):
    ax.grid(axis='y',color='#E5E5E5',lw=.7)
    if xlim is not None: ax.set_xlim(*xlim)
    if ylim is not None: ax.set_ylim(*ylim)
    ax.set_axisbelow(True)


def log_check(fig,group,metric,n,kind):
    PLOT_CHECKS.append(dict(figure=fig.get_label(),group=group,metric=metric,n=int(n),representation=kind))


def series(ax,df,g,metric,*,dashed=False,zero_label=False,scale=1):
    sub=subset(df,g).copy()
    col=metric
    if scale!=1:
        col='_display_value'; sub[col]=sub[metric]*scale
    # Reuse the existing trace implementation, including gaps and original Frame IDs.
    line=trace(ax,sub,col,g,linestyle='--' if dashed else '-',alpha=.88 if dashed else 1)[0]
    line.set_linewidth(1.7 if dashed else 2.1)
    line.set_markersize(4.5)
    line.set_markevery(7)  # Only marker density changes; all samples remain vertices.
    if dashed: line.set_markerfacecolor('white')
    allzero=len(sub)>0 and sub[metric].notna().all() and (sub[metric]==0).all()
    if allzero and zero_label: line.set_marker('')
    np.testing.assert_allclose(line.get_xdata(),numeric(sub.frame))
    np.testing.assert_allclose(line.get_ydata(),numeric(sub[metric])*scale)
    log_check(ax.figure,g,metric,len(sub),'all vertices; sparse markers' if not (allzero and zero_label) else 'all zero vertices; no repeated markers')
    return line


def mask_state(df,tables,out):
    fig=canvas('Online Mask-State Evolution','Static runs accumulate candidates; positive Mask samples are observed in all four dynamic runs.')
    fig.set_label(STEMS[0])
    grid=fig.add_gridspec(2,4,left=.065,right=.98,bottom=.15,top=.79,hspace=.70,wspace=.28)
    fig.text(.065,.831,'STATIC  |  Frame 0-750',fontsize=18,fontweight='bold')
    fig.text(.065,.467,'DYNAMIC  |  Frame 0-1800',fontsize=18,fontweight='bold')
    act=tables['mask_activation_summary'].set_index('group')
    for row,groups in enumerate((STATIC,DYNAMIC)):
        for col,g in enumerate(groups):
            ax=fig.add_subplot(grid[row,col])
            series(ax,df,g,'mask_voxels',zero_label=True)
            series(ax,df,g,'candidate_voxels',dashed=True)
            ax.set_title(SHORT[g],loc='left',color=COLORS[g],fontsize=17,pad=9)
            axes_style(ax,(0,750 if row==0 else 1800),(0,420))
            ax.set_xticks([0,250,500,750] if row==0 else [0,600,1200,1800])
            ax.set_yticks([0,200,400]); ax.set_xlabel('Frame',fontsize=15)
            if col==0: ax.set_ylabel('Voxel count')
            first=act.loc[g,'first_positive_sample_frame']
            text='Mask = 0 throughout' if np.isnan(first) else f'First +Mask: {int(first)}'
            ax.text(.035,.95,text,transform=ax.transAxes,va='top',fontsize=14)
            ax.text(.97,.77,f'n={len(subset(df,g))}',transform=ax.transAxes,ha='right',fontsize=14,color='#555555')
            if np.isfinite(first): ax.axvline(first,color=COLORS[g],ls=':',lw=1.4,alpha=.65)
    key=fig.add_subplot(grid[0,3]); key.axis('off')
    key.legend(handles=[Line2D([],[],color='#333333',marker='o',label='Active Mask',lw=2),
                        Line2D([],[],color='#333333',marker='o',markerfacecolor='white',ls='--',label='Candidate map',lw=2)],
               loc='upper left',fontsize=17,borderaxespad=0)
    key.text(0,.49,'Markers: logged samples\nLines: visual guides\nCommon voxel-count scale\nDifferent Frame ranges',transform=key.transAxes,fontsize=15,va='top',linespacing=1.45)
    foot(fig,'First +Mask is a logged sample, not an exact activation time. Count stability is not convergence.',
         '*04_loop_A: reported LiDAR/cage relative displacement. All sample values retained; markers shown sparsely.')
    export(fig,STEMS[0],out)


def distribution(ax,df,metric,scale=1,collapse_zeros=False):
    rng=np.random.default_rng(20261028)
    labels=[]
    for i,g in enumerate(ORDER,1):
        sub=subset(df,g); x=numeric(sub[metric])*scale
        labels.append(f'{LABEL[g]}   n={len(x)}')
        if collapse_zeros and np.all(x==0):
            ax.scatter([0],[i],s=68,color=COLORS[g],marker=MARKERS[g],clip_on=False,zorder=5)
            ax.text(.10,i,f'All {len(x)} samples = 0%',va='center',fontsize=15,color=COLORS[g])
            log_check(ax.figure,g,metric,len(x),'exact all-zero label with n; no repeated points')
            continue
        box=ax.boxplot([x],positions=[i],orientation='horizontal',widths=.5,whis=1.5,showfliers=False,
                       patch_artist=True,medianprops={'color':'#202020','lw':2},
                       whiskerprops={'color':COLORS[g],'lw':1.3},capprops={'color':COLORS[g],'lw':1.3})
        box['boxes'][0].set(facecolor=COLORS[g],edgecolor=COLORS[g],alpha=.16)
        dots=ax.scatter(x,i+rng.uniform(-.14,.14,len(x)),s=23,color=COLORS[g],marker=MARKERS[g],alpha=.58,linewidths=.4,clip_on=False)
        np.testing.assert_array_equal(np.asarray(dots.get_offsets())[:,0],x)
        log_check(ax.figure,g,metric,len(x),'all samples; category-axis jitter only')
    ax.set_yticks(range(1,8),labels)
    ax.set_ylim(7.65,.35)
    ax.axhline(3.5,color='#B0B0B0',lw=.8)
    ax.grid(axis='x',color='#E5E5E5',lw=.7)


def ratio(df,tables,out):
    fig=canvas('Mask Hit Ratio Comparison','Static: 0% in all logged samples. Dynamic means range from 1.64% to 3.49%.')
    fig.set_label(STEMS[1]); legend(fig)
    grid=fig.add_gridspec(1,2,left=.16,right=.975,bottom=.19,top=.73,wspace=.25,width_ratios=[1,1.15])
    left=fig.add_subplot(grid[0,0]); right=fig.add_subplot(grid[0,1])
    distribution(left,df,'mask_hit_ratio',100,True)
    left.set(xlim=(0,4.5),xlabel='Mask Hit Ratio (%)')
    left.set_title('Logged distributions',loc='left',pad=14)
    for g in ORDER: series(right,df,g,'mask_hit_ratio',zero_label=True,scale=100)
    for g in STATIC:
        sub=subset(df,g)
        right.scatter([sub.frame.iloc[-1]],[0],s=60,color=COLORS[g],marker=MARKERS[g],clip_on=False,zorder=7)
    axes_style(right,(0,1800),(0,4.5))
    right.set(xlabel='Frame',ylabel='Mask Hit Ratio (%)')
    right.set_title('Observed trajectories',loc='left',pad=14)
    right.set_xticks([0,600,1200,1800])
    right.text(.40,.07,'Static: all 0%',transform=right.transAxes,fontsize=16)
    foot(fig,'Mask Hit Ratio = candidate_hits / raw. This is not Precision, Recall or Accuracy.',
         'Boxes: median + IQR, 1.5-IQR whiskers. Points: y-jitter only. *04_loop_A: reported relative displacement.')
    export(fig,STEMS[1],out)


def latency(df,tables,out):
    limit=3.2
    n=len(df); inside=int((df.callback_ms<=limit).sum()); maximum=df.loc[df.callback_ms.idxmax()]
    fig=canvas('Runtime Latency Distribution',f'{inside}/{n} logged samples at or below {limit:.1f} ms; observed maximum: {maximum.callback_ms:.3f} ms.')
    fig.set_label(STEMS[2]); legend(fig)
    grid=fig.add_gridspec(1,2,left=.16,right=.975,bottom=.19,top=.73,wspace=.25,width_ratios=[1,1.15])
    left=fig.add_subplot(grid[0,0]); right=fig.add_subplot(grid[0,1])
    distribution(left,df,'callback_ms')
    left.set(xlim=(0,10),xlabel='Logged callback time (ms)')
    left.set_title('Full range | all samples',loc='left',pad=14)
    i=ORDER.index(maximum.group)+1
    left.annotate(f'{maximum.callback_ms:.3f} ms',xy=(maximum.callback_ms,i),xytext=(6.2,i+.55),
                  fontsize=17,fontweight='bold',arrowprops={'arrowstyle':'-','lw':1,'color':'#444444'})
    left.axvline(limit,color='#777777',ls=':',lw=1.3)
    for j,g in enumerate(ORDER):
        x=np.sort(numeric(subset(df,g).callback_ms)); y=np.arange(1,len(x)+1)/len(x)
        line=right.step(np.r_[0,x,10],np.r_[0,y,1],where='post',color=COLORS[g],lw=2,
                       ls=('-', '--', '-.', ':')[j%4])[0]
        assert len(line.get_xdata())==len(x)+2
        np.testing.assert_array_equal(line.get_xdata()[1:-1],x)
        log_check(fig,g,'callback_ms',len(x),'ECDF full-n denominator; display zoom 0-3.2 ms')
    axes_style(right,(0,limit),(0,1.03))
    right.set(xlabel='Logged callback time (ms)',ylabel='Cumulative proportion')
    right.set_title(f'ECDF zoom | 0-{limit:.1f} ms',loc='left',pad=14)
    right.set_xticks([0,.8,1.6,2.4,3.2])
    right.text(.98,.13,f'{n-inside}/{n} above zoom\nRetained in full-range view',transform=right.transAxes,ha='right',fontsize=15,
               bbox={'facecolor':'white','edgecolor':'none','alpha':.85})
    foot(fig,'Logged every 10 frames: sampled latency, not full-frame timing or a real-time guarantee.',
         'ECDF uses all samples without smoothing. Dotted line at left: zoom limit. *04_loop_A: disturbed mounting.')
    export(fig,STEMS[2],out)


def learning(df,tables,out,progress=False):
    stem=STEMS[4] if progress else STEMS[3]
    title='Learning Progress and Queue Status' if progress else 'Static vs Dynamic Learning'
    subtitle=('Processed batches and global orientation bins; no reported learner-queue discards.' if progress else
              'Candidates are present in static runs; active Mask samples are observed in dynamic runs.')
    fig=canvas(title,subtitle); fig.set_label(stem); legend(fig)
    metrics=[('learning_frames','Learning frames',1900),('orientation_bins','Orientation bins',68)] if progress else [
             ('mask_voxels','Active Mask voxels',320),('candidate_voxels','Candidate-map voxels',400)]
    grid=fig.add_gridspec(2,2,left=.09,right=.98,bottom=.24 if progress else .18,top=.71,hspace=.44,wspace=.20)
    for row,(metric,label,ymax) in enumerate(metrics):
        for col,groups in enumerate((STATIC,DYNAMIC)):
            ax=fig.add_subplot(grid[row,col])
            for g in groups: series(ax,df,g,metric,zero_label=True)
            axes_style(ax,(0,750 if col==0 else 1800),(0,ymax))
            ax.set_xticks([0,250,500,750] if col==0 else [0,600,1200,1800])
            if row==0: ax.set_title('Static | Frame 0-750' if col==0 else 'Dynamic | Frame 0-1800',fontsize=20,loc='left',pad=12)
            if row==1: ax.set_xlabel('Frame')
            ax.set_ylabel(label,fontsize=16)
            if metric=='mask_voxels' and col==0:
                ax.text(.04,.66,'Mask = 0 at every logged sample',transform=ax.transAxes,fontsize=18)
            if metric=='orientation_bins':
                ax.axhline(60,color='#777777',ls=':',lw=1.2)
                if col==0: ax.text(.04,.58,'Static: 1-2 bins',transform=ax.transAxes,fontsize=18)
                else: ax.text(.98,.10,'Dotted line: 60-bin cap',transform=ax.transAxes,ha='right',fontsize=15)
            ax.yaxis.set_major_locator(MaxNLocator(3,integer=True))
    if progress:
        assert (df.dropped_learning_batches==0).all()
        fig.text(.09,.112,f'Dropped learning batches = 0 at all {len(df)} logged observations (7 runs)',fontsize=18,fontweight='bold')
        for g in ORDER: log_check(fig,g,'dropped_learning_batches',len(subset(df,g)),'exact constant-zero label; all runs')
    foot(fig,'Static and dynamic Frame ranges differ; vertical scales match within each row. Runs are not pooled.',
         '*04_loop_A: reported relative displacement. '+('Queue discards are not sensor/ROS transport losses.' if progress else 'Each line links recorded values; markers are sparse.'))
    export(fig,stem,out)


def orientation(df,tables,out):
    fig=canvas('Orientation Diversity vs Mask Activation','Cage A and B shown separately; the same no-cage static reference appears in both columns.')
    fig.set_label(STEMS[5]); legend(fig)
    grid=fig.add_gridspec(2,2,left=.09,right=.98,bottom=.17,top=.72,hspace=.46,wspace=.20)
    for col,cage in enumerate(('A','B')):
        for row,(metric,label,ymax) in enumerate([('mask_voxels','Active Mask voxels',330),('candidate_voxels','Candidate-map voxels',410)]):
            ax=fig.add_subplot(grid[row,col])
            for g in ORDER:
                if META[g][1] not in (cage,'None'): continue
                sub=subset(df,g); x=numeric(sub.orientation_bins); y=numeric(sub[metric])
                points=ax.scatter(x,y,s=42,marker=MARKERS[g],color=COLORS[g],alpha=.55,linewidths=.6,clip_on=False)
                np.testing.assert_array_equal(np.asarray(points.get_offsets()),np.column_stack([x,y]))
                log_check(fig,g,metric,len(x),'every point at original x/y; including bin=60; no jitter')
            axes_style(ax,(0,63),(0,ymax))
            ax.axvline(60,ls=':',lw=1.3,color='#666666')
            if row==0: ax.set_title(f'Cage {cage} + no-cage reference',loc='left',fontsize=20,pad=12)
            if row==1: ax.set_xlabel('Global orientation bins')
            ax.set_ylabel(label,fontsize=16)
            ax.set_xticks([0,20,40,60]); ax.yaxis.set_major_locator(MaxNLocator(4,integer=True))
    foot(fig,'Dotted line: 60-bin cap. All points retained, including overlaps. Association does not establish causation.',
         'Global bins are not per-voxel admission counts. *04_loop_A: reported LiDAR/cage relative displacement.')
    export(fig,STEMS[5],out)


def check_originals():
    baseline=json.loads((HERE/'reports/protected_before.json').read_text(encoding='utf-8'))
    changed=[name for name,digest in baseline.items() if not (ROOT/name).is_file() or hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest]
    if changed: raise RuntimeError(f'Protected files changed: {changed}')
    return len(baseline)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=HERE/'figures')
    args=parser.parse_args(); out=args.output.resolve()
    if not out.is_relative_to(HERE): raise ValueError('Output must stay inside visualization/group_meeting/.')
    protected=check_originals()
    parsed=parse_logs(ROOT/'analysis/results/online_controls')
    if len(parsed.diagnostics): raise RuntimeError(parsed.diagnostics.to_string(index=False))
    df=with_derived(parsed.records); tables=compute_statistics(df)
    # Compare to the existing deliverable, not a reimplementation of its parser.
    comparisons={}
    for name,frame in {'parsed_records':df,**tables}.items():
        encoded=frame.to_csv(index=False,na_rep='NA',float_format='%.12g').encode('utf-8')
        original=(VIS/'tables'/f'{name}.csv').read_bytes()
        assert encoded==original,f'Original data/statistics mismatch: {name}'
        comparisons[name]=hashlib.sha256(encoded).hexdigest()
    presentation_style()
    print(f'Input verified: {len(df)} records, nine complete core fields. {protected} original files protected.',flush=True)
    for draw in (mask_state,ratio,latency,learning): draw(df,tables,out)
    learning(df,tables,out,progress=True)
    orientation(df,tables,out)
    for stem in STEMS:
        with Image.open(out/f'{stem}.png') as im:
            im.load(); assert im.size==(4800,2700)
            assert all(abs(d-300)<.1 for d in im.info['dpi'])
    assert len(df)==845 and df[list(FIELDS)].notna().all().all()
    protected=check_originals()
    report={'status':'PASS','records':len(df),'field_values':len(df)*len(FIELDS),
        'group_n':{g:len(subset(df,g)) for g in GROUPS},'original_files_unchanged':protected,
        'original_csv_byte_matches':comparisons,'size_px':[4800,2700],'dpi':300,
        'stems':STEMS,'colors':COLORS,'markers':MARKERS,
        'latency_zoom_ms':[0,3.2],'samples_outside_zoom':int((df.callback_ms>3.2).sum()),
        'visual_data_checks':PLOT_CHECKS}
    (HERE/'reports/validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(f'PASS: {len(STEMS)} widescreen figures x PNG/SVG/PDF; original data, statistics, code and figures unchanged.',flush=True)


if __name__=='__main__': main()
