"""Six real-data views, generated before the publication plots."""
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from .log_parser import GROUPS
from .style import COLORS, MARKERS, clean, group_handles, numeric, setup, trace


def explore(df, output: Path):
    setup()
    fig, axes = plt.subplots(3,2,figsize=(11,10))
    for g in GROUPS:
        sub=df[(df.group==g)&df.analysis_eligible].sort_values('frame')
        trace(axes[0,0],sub,'mask_voxels',g)
        trace(axes[0,1],sub,'candidate_voxels',g)
        x=np.sort(numeric(sub.callback_ms.dropna()))
        if len(x):
            axes[1,1].step(np.r_[0,x],np.r_[0,np.arange(1,len(x)+1)/len(x)],where='post',color=COLORS[g])
        axes[2,0].scatter(numeric(sub.frame),numeric(sub.raw),s=7,color=COLORS[g],marker=MARKERS[g])
        axes[2,1].scatter(numeric(sub.orientation_bins),numeric(sub.mask_voxels),s=10,color=COLORS[g],marker=MARKERS[g],alpha=.5,clip_on=False)
    ratio=[numeric(df.loc[(df.group==g)&df.analysis_eligible,'mask_hit_ratio'].dropna())*100 for g in GROUPS]
    axes[1,0].boxplot(ratio,orientation='horizontal',tick_labels=GROUPS,whis=1.5)
    for ax,title,xlabel,ylabel in zip(axes.flat,
        ['A  Mask trajectories','B  Candidate trajectories','C  Ratio: boxes retain zero groups',
         'D  Latency ECDF: full sampled range','E  Raw-point counts','F  Orientation vs mask'],
        ['Frame','Frame','Mask Hit Ratio (%)','Logged callback time (ms)','Frame','Orientation bins'],
        ['Mask voxels','Candidate voxels','','Empirical cumulative probability','Raw points','Mask voxels']):
        ax.set(title=title,xlabel=xlabel,ylabel=ylabel)
        clean(ax,yzero=ax!=axes[1,0])
    axes[1,1].set_ylim(0,1.03)
    axes[2,1].axvline(60,color='#777777',ls=':',lw=.8)
    fig.suptitle('Exploratory audit: all observed telemetry (no smoothing or deletion)',y=.995)
    fig.legend(handles=group_handles(),loc='upper center',bbox_to_anchor=(.5,.968),ncol=4)
    fig.tight_layout(rect=(0,.07,1,.92),h_pad=2)
    fig.text(.02,.02,f'{len(df)} records in the supplied logs; samples are temporally dependent. No ground-truth labels.\n'
             'Latency ECDF describes logged samples only, not all frames. *04_loop_A: reported relative displacement.',fontsize=8)
    output.mkdir(parents=True,exist_ok=True)
    fig.savefig(output/'exploratory_overview.png',dpi=160)
    plt.close(fig)
