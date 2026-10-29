"""One visual grammar for exploratory and publication figures."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from .log_parser import GROUPS

# Okabe-Ito categories plus neutral grey; shapes provide redundant encoding.
COLORS = dict(zip(GROUPS, ['#4D4D4D','#0072B2','#009E73','#D55E00','#CC79A7','#56B4E9','#E69F00']))
MARKERS = dict(zip(GROUPS, ['o','s','^','D','v','P','X']))
LABELS = {g:g+('*' if g=='04_loop_A' else '') for g in GROUPS}


def setup():
    plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':9, 'axes.titlesize':10,
                         'axes.labelsize':9, 'xtick.labelsize':8, 'ytick.labelsize':8,
                         'legend.fontsize':8, 'figure.titlesize':13, 'axes.spines.top':False,
                         'axes.spines.right':False, 'axes.linewidth':.7, 'lines.linewidth':1.2,
                         'lines.markersize':3, 'legend.frameon':False, 'savefig.dpi':300,
                         'pdf.fonttype':42, 'ps.fonttype':42, 'svg.fonttype':'none',
                         'svg.hashsalt':'gasf-online-controls-v1', 'axes.axisbelow':True})


def clean(ax, xzero=True, yzero=True):
    ax.grid(axis='y', color='#E5E5E5', linewidth=.5)
    if xzero:
        ax.set_xlim(left=0)
    if yzero:
        ax.set_ylim(bottom=0)


def group_handles(groups=GROUPS):
    return [Line2D([],[],color=COLORS[g],marker=MARKERS[g],label=LABELS[g],lw=1) for g in groups]


def numeric(series):
    return series.to_numpy(dtype=float, na_value=float('nan'))


def trace(ax, sub, metric, group, **kwargs):
    # Do not bridge missing values or gaps in logged frame numbers.
    import numpy as np
    x, y = numeric(sub.frame), numeric(sub[metric])
    if len(x)>1:
        gap_indices = np.where(np.diff(x) != 10)[0]+1
        for i in reversed(gap_indices):
            x, y = np.insert(x,i,np.nan), np.insert(y,i,np.nan)
    return ax.plot(x,y,color=COLORS[group],marker=MARKERS[group],markersize=2,
                   markeredgewidth=.3,label=LABELS[group],clip_on=False,**kwargs)
