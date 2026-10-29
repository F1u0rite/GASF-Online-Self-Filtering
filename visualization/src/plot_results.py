"""Publication figures: one figure object exported as PNG, SVG and PDF."""
from pathlib import Path
import json
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator
from .log_parser import GROUPS, META
from .statistics import LEARNING_METRICS
from .style import COLORS, MARKERS, LABELS, clean, group_handles, numeric, setup, trace

STEMS = ('01_online_mask_convergence','02_mask_hit_ratio_comparison',
         '03_runtime_latency_distribution','04_static_vs_dynamic_learning',
         '05_orientation_diversity_vs_mask_activation')
DISTURBED = '*04_loop_A: reported LiDAR/cage relative displacement.'
CAPTIONS = {
    STEMS[0]: 'Online Mask Convergence (observed trajectories). Points are logged observations; connecting lines are visual guides, not interpolated data. Solid lines show the active snapshot count and dashed lines show the candidate-map count. All facets share scales and retain actual Frame numbers. The first positive Mask sample is annotated, not an exact activation instant. Equal counts do not prove convergence or equal voxel membership. Candidate and Mask states are asynchronous. '+DISTURBED,
    STEMS[1]: 'Mask Hit Ratio Comparison. Mask Hit Ratio = candidate_hits / raw, plotted as a percentage of all incoming points at logged frames. Boxes show Q1, median and Q3; whiskers extend to the furthest observations within 1.5 IQR. Every valid logged observation is shown, with deterministic vertical jitter only. Hollow diamonds show the arithmetic mean of per-record ratios. The lower panel retains the original temporal trajectories. Sample counts are not independent trial counts. This metric is not Precision, Recall, Accuracy or F1. '+DISTURBED,
    STEMS[2]: 'Runtime Latency Distribution. Logged callback_ms observations, recorded every 10 frames in the supplied logs. Boxes show Q1/P50/Q3, with 1.5-IQR whiskers and all samples; diamonds indicate means. The empirical CDF uses all valid recorded observations without smoothing. The complete observed range, including the maximum, is retained. P95/P99 in the associated table describe these sampled log points, not all frames, and provide no real-time guarantee. The timer excludes statistics emission and asynchronous worker completion. '+DISTURBED,
    STEMS[3]: 'Static vs Dynamic Learning. Each experiment remains separate; columns distinguish motion labels verified against the repository README. Rows share scales between static and dynamic panels and show actual logged Frame values. No-cage static 01_static is a distinct baseline. A/B denote cage conditions, not replicates. Unequal durations and uncontrolled runtime settings prevent causal or pooled significance claims. Global orientation bins have a source cap of 60. The learner counters and Mask snapshot are asynchronously observed. '+DISTURBED,
    STEMS[4]: 'Orientation Diversity vs Mask Activation. Each point is an actual logged observation, with no positional jitter, fitted trend or interpolation; coincident points overlap. Cage A/B are separate columns; the same no-cage static reference is repeated in both and not counted as an additional experiment. Dashed lines mark the current source cap of 60 global orientation bins, not a universal Mask activation threshold. Spearman associations in the associated table are descriptive, with tied ranks and pair counts; no p-values are reported because observations are temporally dependent and cap-limited. Constant-series correlations are undefined. Global bins differ from per-voxel admission bins, and logged model states are asynchronous. '+DISTURBED,
}


def subset(df, group):
    return df[(df.group==group)&df.analysis_eligible].sort_values('frame')


def footer(fig, text):
    fig.text(.025,.018,text,ha='left',va='bottom',fontsize=7.5,linespacing=1.5)


def export(fig, stem: str, output: Path):
    fig.canvas.draw()
    renderer=fig.canvas.get_renderer()
    # Catch cropped text before exporting. Artist-to-artist overlap is checked visually.
    from matplotlib.text import Text
    clipped=[]
    bounds=fig.bbox
    undrawn_ticks=set()
    for ax in fig.axes:
        for axis,limits in ((ax.xaxis,ax.get_xlim()),(ax.yaxis,ax.get_ylim())):
            lo,hi=sorted(limits)
            for tick in axis.get_major_ticks()+axis.get_minor_ticks():
                if not lo<=tick.get_loc()<=hi:
                    undrawn_ticks.update((id(tick.label1),id(tick.label2)))
    for item in fig.findobj(Text):
        if id(item) not in undrawn_ticks and item.get_visible() and item.get_text().strip():
            box=item.get_window_extent(renderer)
            if box.x0 < bounds.x0-2 or box.y0 < bounds.y0-2 or box.x1 > bounds.x1+2 or box.y1 > bounds.y1+2:
                clipped.append(item.get_text())
    if clipped:
        raise RuntimeError(f'{stem}: text outside figure: {clipped}')
    output.mkdir(parents=True,exist_ok=True)
    for ext in ('png','svg','pdf'):
        metadata = {'Date':None} if ext=='svg' else {'CreationDate':None,'ModDate':None} if ext=='pdf' else {'Software':'GASF visualization'}
        fig.savefig(output/f'{stem}.{ext}',dpi=300,metadata=metadata,facecolor='white')
    print(f'  Figure: {output/stem} (.png, .svg, .pdf)',flush=True)
    plt.close(fig)


def boxes_with_observations(ax, df, column, scale=1, summary=None):
    """Use stable jitter of category position only; never modify metric values."""
    rng=np.random.default_rng(20261028)
    labels=[]
    for i,g in enumerate(GROUPS,1):
        x=numeric(subset(df,g)[column].dropna())*scale
        labels.append(f'{LABELS[g]}  (n={len(x)})')
        if not len(x):
            continue
        box=ax.boxplot([x],positions=[i],orientation='horizontal',widths=.48,
                       patch_artist=True,showfliers=False,whis=1.5,
                       medianprops={'color':'#202020','linewidth':1.1},
                       whiskerprops={'color':COLORS[g],'linewidth':.8},
                       capprops={'color':COLORS[g],'linewidth':.8})
        box['boxes'][0].set(facecolor=COLORS[g],edgecolor=COLORS[g],alpha=.18)
        ax.scatter(x,i+rng.uniform(-.15,.15,len(x)),s=9,marker=MARKERS[g],
                   color=COLORS[g],alpha=.55,linewidths=.2,clip_on=False,zorder=3)
        # Means come from the same statistics table that is saved to CSV.
        mean=(summary.loc[summary.group==g,'mean'].iloc[0]*scale) if summary is not None else x.mean()
        ax.scatter([mean],[i],marker='D',s=30,facecolors='white',edgecolors='#202020',linewidths=.8,zorder=5,clip_on=False)
    ax.set_yticks(range(1,len(GROUPS)+1),labels)
    ax.set_ylim(len(GROUPS)+.6,.4)
    clean(ax,yzero=False)
    ax.grid(False,axis='y')
    ax.grid(True,axis='x',color='#E5E5E5',linewidth=.5)


def convergence(df, tables, output):
    fig,axes=plt.subplots(4,2,figsize=(8.2,8.7),sharex=True,sharey=True)
    max_frame=float(df.frame.max())*1.04
    max_count=float(df[['mask_voxels','candidate_voxels']].max().max())*1.25
    act=tables['mask_activation_summary'].set_index('group')
    for i,(g,ax) in enumerate(zip(GROUPS,axes.flat)):
        sub=subset(df,g)
        trace(ax,sub,'mask_voxels',g,linestyle='-',linewidth=1.25)
        trace(ax,sub,'candidate_voxels',g,linestyle='--',linewidth=.95,alpha=.8,markerfacecolor='white')
        ax.set_title(f'({chr(97+i)}) {LABELS[g]} | {META[g][0].lower()} | n={len(sub)}',loc='left')
        first=act.loc[g,'first_positive_sample_frame']
        note='No positive Mask observed' if np.isnan(first) else f'First positive sample: frame {int(first)}'
        ax.text(.035,.92,note,transform=ax.transAxes,fontsize=7.5,va='top')
        if np.isfinite(first):
            ax.axvline(first,color=COLORS[g],alpha=.4,lw=.7,ls=':')
        ax.set(xlim=(0,max_frame),ylim=(0,max_count),xlabel='Frame',ylabel='Voxel count')
        ax.xaxis.set_major_locator(MaxNLocator(4))
        clean(ax)
        ax.tick_params(labelbottom=True)
    axes.flat[-1].axis('off')
    axes.flat[-1].legend(handles=[Line2D([],[],color='#333333',marker='o',lw=1.2,label='Active Mask snapshot'),
                                 Line2D([],[],color='#333333',marker='o',ls='--',lw=.9,label='Candidate map')],loc='upper left')
    axes.flat[-1].text(.02,.52,'Recorded points; lines are visual guides\nCounts may decrease; common axes\nNo convergence claim',transform=axes.flat[-1].transAxes,fontsize=8,linespacing=1.5,va='top')
    fig.suptitle('Online Mask Convergence',y=.99)
    fig.tight_layout(rect=(0,.075,1,.965),h_pad=1.2,w_pad=1.6)
    footer(fig,'Observed trajectories only; constant counts do not establish convergence or Mask identity.\n'
           'Mask and learner states are asynchronous. '+DISTURBED)
    export(fig,STEMS[0],output)


def hit_ratio(df,tables,output):
    fig,axes=plt.subplots(2,1,figsize=(8.2,7.2),height_ratios=[1.15,1])
    boxes_with_observations(axes[0],df,'mask_hit_ratio',100,tables['mask_hit_ratio_summary'])
    axes[0].set(title='(a) Per-experiment logged distributions',xlabel='Mask Hit Ratio (%)')
    for g in GROUPS:
        sub=subset(df,g).copy()
        sub['percent']=sub.mask_hit_ratio*100
        trace(axes[1],sub,'percent',g,linewidth=1)
    axes[1].set(title='(b) Observed temporal trajectories',xlabel='Frame',ylabel='Mask Hit Ratio (%)')
    axes[1].set_ylim(0,max(.1,float(df.mask_hit_ratio.max())*113))
    clean(axes[1])
    fig.suptitle('Mask Hit Ratio Comparison',y=.99)
    fig.legend(handles=group_handles(),loc='upper center',bbox_to_anchor=(.5,.955),ncol=4)
    fig.tight_layout(rect=(0,.115,1,.885),h_pad=1.8)
    footer(fig,'Mask Hit Ratio = candidate_hits / raw; this is not Precision, Recall or Accuracy.\n'
           'Boxes: Q1/P50/Q3; whiskers: 1.5 IQR; points: all samples; hollow diamonds: sample means.\n'
           'n counts logged samples, not independent trials. '+DISTURBED)
    export(fig,STEMS[1],output)


def latency(df,tables,output):
    fig,axes=plt.subplots(2,1,figsize=(8.2,7.4),height_ratios=[1.15,1])
    boxes_with_observations(axes[0],df,'callback_ms',summary=tables['callback_latency_summary'])
    maximum=df.loc[df.callback_ms.idxmax()]
    xmax=float(maximum.callback_ms)*1.09
    axes[0].set(title='(a) Logged callback samples: full observed range',xlabel='Logged callback time (ms)',xlim=(0,xmax))
    position=GROUPS.index(maximum.group)+1
    axes[0].annotate(f'Maximum: {maximum.callback_ms:.3f} ms\n{maximum.group}, frame {maximum.frame}',
                     xy=(maximum.callback_ms,position),xytext=(xmax*.50,position-.75),
                     fontsize=8,arrowprops={'arrowstyle':'-','color':'#555555','lw':.7})
    for i,g in enumerate(GROUPS):
        x=np.sort(numeric(subset(df,g).callback_ms.dropna()))
        if len(x):
            axes[1].step(np.r_[0,x,xmax],np.r_[0,np.arange(1,len(x)+1)/len(x),1],where='post',
                         color=COLORS[g],lw=1.1,ls=('-', '--', '-.', ':')[i%4])
    axes[1].set(title='(b) Empirical cumulative distribution (no smoothing)',
                xlabel='Logged callback time (ms)',ylabel='Cumulative proportion',xlim=(0,xmax),ylim=(0,1.04))
    clean(axes[1])
    fig.suptitle('Runtime Latency Distribution',y=.99)
    fig.legend(handles=group_handles(),loc='upper center',bbox_to_anchor=(.5,.955),ncol=4)
    fig.tight_layout(rect=(0,.13,1,.885),h_pad=1.8)
    footer(fig,'Logged samples only (every 10 frames here): P95/P99 are not full-frame quantiles or real-time guarantees.\n'
           'Boxes: Q1/P50/Q3; whiskers: 1.5 IQR; all points retained; hollow diamonds: sample means.\n'
           'Timer excludes stats emission and asynchronous learning completion. '+DISTURBED)
    export(fig,STEMS[2],output)


def static_dynamic(df,tables,output):
    fig,axes=plt.subplots(5,2,figsize=(8.2,10.6),sharex=True,sharey='row')
    names=['Processed learner batches','Global orientation bins','Active Mask voxels','Candidate-map voxels','Dropped learner batches']
    for row,(metric,label) in enumerate(zip(LEARNING_METRICS,names)):
        maxval=float(df[metric].max())
        for col,motion in enumerate(('Static','Dynamic')):
            ax=axes[row,col]
            for g in GROUPS:
                if META[g][0]==motion:
                    trace(ax,subset(df,g),metric,g,linewidth=.9)
            ax.set(ylim=(0,maxval*1.12 if maxval else 1),xlim=(0,float(df.frame.max())*1.03))
            if row==0:
                ax.set_title(motion)
            if col==0:
                ax.set_ylabel(label)
            if metric=='orientation_bins':
                ax.axhline(60,color='#666666',lw=.6,ls=':')
            if (df.loc[df.motion==motion,metric].dropna()==0).all():
                ax.text(.04,.68,'All recorded values = 0\n(overlapping series)',transform=ax.transAxes,fontsize=7.5)
            if maxval==0:
                ax.set_yticks([0,1])
            ax.xaxis.set_major_locator(MaxNLocator(4))
            clean(ax)
    for ax in axes[-1]:
        ax.set_xlabel('Frame')
    fig.suptitle('Static vs Dynamic Learning',y=.995)
    fig.legend(handles=group_handles(),loc='upper center',bbox_to_anchor=(.5,.972),ncol=4)
    fig.tight_layout(rect=(0,.078,1,.925),h_pad=1.0,w_pad=1.5)
    footer(fig,'Each run is retained separately; row scales match. Durations differ; A/B are cage conditions, not replicates.\n'
           '01_static: no outer cage. Orientation bins have a source cap of 60. Model counters are asynchronous.\n'
           'No causal or significance claim. '+DISTURBED)
    export(fig,STEMS[3],output)


def orientation(df,tables,output):
    fig,axes=plt.subplots(2,2,figsize=(8.2,6.8),sharex=True,sharey='row')
    for col,cage in enumerate(('A','B')):
        groups=[g for g in GROUPS if META[g][1] in (cage,'None')]
        for row,(metric,label) in enumerate([('mask_voxels','Active Mask voxels'),('candidate_voxels','Candidate-map voxels')]):
            ax=axes[row,col]
            for g in groups:
                sub=subset(df,g).dropna(subset=['orientation_bins',metric])
                ax.scatter(numeric(sub.orientation_bins),numeric(sub[metric]),color=COLORS[g],marker=MARKERS[g],
                           s=15,alpha=.55,linewidths=.25,clip_on=False)
            ax.axvline(60,color='#666666',ls=':',lw=.8)
            ax.set(xlim=(0,max(63,float(df.orientation_bins.max())*1.05)),
                   ylim=(0,float(df[metric].max())*1.12),xlabel='Global orientation bins')
            ax.set_title(f'({chr(97+row*2+col)}) Cage {cage} + no-cage static reference',loc='left')
            if col==0:
                ax.set_ylabel(label)
            clean(ax)
    handles=group_handles()
    for handle,g in zip(handles,GROUPS):
        handle.set_label(f'{LABELS[g]} (n={len(subset(df,g))})')
    fig.suptitle('Orientation Diversity vs Mask Activation',y=.995)
    fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.5,.96),ncol=3)
    fig.tight_layout(rect=(0,.14,1,.825),h_pad=1.8,w_pad=1.5)
    footer(fig,'Points: actual observations; coincident values overlap. The no-cage reference is repeated in both columns.\n'
           'Dotted line: source cap = 60 bins. Global bins are not per-voxel admission counts; model states are asynchronous.\n'
           'Autocorrelated samples; no causal interpretation. '+DISTURBED)
    export(fig,STEMS[4],output)


def make_figures(df,tables,output: Path):
    setup()
    for draw in (convergence,hit_ratio,latency,static_dynamic,orientation):
        draw(df,tables,output)
    (output/'captions.md').write_text('\n\n'.join(f'## {stem}\n\n{CAPTIONS[stem]}' for stem in STEMS)+'\n',encoding='utf-8')
    # Source values are stored independently of plotting for verification/reuse.
    (output/'figure_manifest.json').write_text(json.dumps({'stems':STEMS,'formats':['png','svg','pdf'],
        'png_dpi':300,'source_records':'../tables/parsed_records.csv','quantile_method':'linear',
        'group_colors':COLORS,'group_markers':MARKERS,'n_logged_samples':len(df)},indent=2)+'\n',encoding='utf-8')
