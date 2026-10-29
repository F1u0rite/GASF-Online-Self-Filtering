"""Local source-audited GASF V1 overview. Only writes 00_gasf_algorithm_overview*.
Run from any directory with the existing visualization requirements installed.
"""
from pathlib import Path
import os
import sys
import hashlib
import json
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STEM = '00_gasf_algorithm_overview'
os.environ.setdefault('MPLCONFIGDIR', str(HERE.parent / '.mplconfig'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.path import Path as MPath
from PIL import Image


def digest_files():
    paths = [ROOT / 'README.md']
    for folder in ('src', 'analysis/results/online_controls', 'visualization'):
        paths.extend(p for p in (ROOT / folder).rglob('*') if p.is_file()
                     and not p.name.startswith(STEM)
                     and not any(s in p.parts for s in ('__pycache__', '.mplconfig', '.venv')))
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def main():
    before = digest_files()
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'svg.fonttype': 'none',
                         'pdf.fonttype': 42, 'svg.hashsalt': 'gasf-v1-overview'})
    fig = plt.figure(figsize=(16, 9), facecolor='white')
    ax = fig.add_axes([0, 0, 1, 1], xlim=(0, 16), ylim=(0, 9))
    ax.axis('off')
    blue, green, amber, ink = '#0072B2', '#008767', '#A66B00', '#263238'
    texts = []

    def text(x, y, s, size=14, color=ink, weight='normal', ha='left', va='center'):
        t = ax.text(x, y, s, fontsize=size, color=color, weight=weight,
                    ha=ha, va=va, linespacing=1.35, zorder=5)
        texts.append(t)
        return t

    def panel(x, y, w, h, fill, edge='#D8E1E5', lw=1):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.015,rounding_size=0.09',
                                   facecolor=fill, edgecolor=edge, linewidth=lw, zorder=1))

    def box(x, y, w, h, title, body, color=blue, fill='white', ts=16, bs=13):
        panel(x, y, w, h, fill, color, 1.4)
        if not body:
            text(x+w/2, y+h/2, title, ts, color, 'bold', 'center')
            return
        text(x+w/2, y+h-(.13 if h<.8 else .23), title, ts, color, 'bold', 'center', 'top')
        if body: text(x+w/2, y+(.08 if h<.8 else .16), body, bs, ha='center', va='bottom')

    def arrow(points, color=ink, dashed=False):
        path = MPath(points, [MPath.MOVETO] + [MPath.LINETO]*(len(points)-1))
        ax.add_patch(FancyArrowPatch(path=path, arrowstyle='-|>', mutation_scale=14,
                                    lw=1.65, color=color, linestyle='--' if dashed else '-', zorder=3))

    text(.45, 8.61, 'GASF V1: Online Self-Filtering Pipeline', 28, weight='bold')
    text(.45, 8.16, 'Online learning of stable near-field structures without a pre-defined cage CAD model', 17, '#555555')
    panel(3.7, 5.05, 11.85, 2.65, '#F3F8FB')
    panel(3.7, 2.65, 11.85, 1.65, '#F1F8F5')
    text(3.9, 7.43, 'A  ONLINE LEARNING', 19, blue, 'bold')
    text(8.1, 7.43, 'Callback preparation → queue → background worker', 14, '#555555')
    text(3.9, 4.04, 'B  REAL-TIME FILTERING', 19, green, 'bold')
    text(9.0, 4.04, 'LiDAR callback • no wait for learner completion', 14, '#555555')
    box(.45, 6.85, 2.9, .95, 'Livox Mid-360', 'CustomMsg  /livox/lidar', ink)
    box(.45, 5.02, 2.9, 1.45, 'IMU → relative attitude',
        'sensor_msgs/Imu  /livox/imu\nGyro integration\nNearest past pose ≤100 ms', ink, ts=14, bs=12.5)
    text(.55, 4.52, 'LiDAR-frame voxel indices\nNo CAD or world transform', 13, '#555555')
    box(3.9, 5.92, 2.65, 1.17, 'Near-field voxels',
        'Finite xyz • 0.12–0.45 m\n0.06 m grid; per-frame dedup.', bs=12)
    box(7.0, 5.92, 2.05, 1.17, 'Bounded queue', 'Capacity: 5 batches\nVoxels + attitude', bs=12.5)
    box(9.5, 5.72, 2.65, 1.37, 'Candidate state',
        'Hits • last seen • bin bits\n6° bin threshold; cap 60\nAge >250: prune every 25', bs=12)
    box(12.6, 5.72, 2.7, 1.37, 'Orientation Diversity\nGating',
        '≥8 hits AND ≥3 voxel bins\nAND age ≤250', ts=15, bs=12.5)
    text(3.95, 5.31, 'Queue full: drop oldest; lock busy: drop incoming. Ages/counts use processed learning batches.', 12)
    arrow([(3.35, 7.32), (3.58, 7.32), (3.58, 6.52), (3.9, 6.52)])
    arrow([(6.55, 6.52), (7, 6.52)], blue)
    arrow([(9.05, 6.52), (9.5, 6.52)], blue)
    arrow([(12.15, 6.52), (12.6, 6.52)], blue)
    arrow([(3.35, 5.62), (8.02, 5.62), (8.02, 5.92)], blue)
    # Snapshot is the only cross-lane model handoff; no training-complete barrier.
    box(12.6, 4.47, 2.7, .75, 'Latest Mask snapshot', 'Immutable • initially empty', amber, '#FFF5DB', ts=14, bs=11.5)
    arrow([(13.95, 5.72), (13.95, 5.22)], amber)
    text(13.70, 5.48, 'Atomic replace / 5', 12, amber, ha='right')
    arrow([(12.6, 4.83), (3.78, 4.83), (3.78, 3.65), (3.9, 3.65)], amber)
    text(7.15, 4.59, 'Atomic load: latest available Mask', 13, amber)
    box(3.9, 2.87, 2.65, .9, 'Read current Mask', 'Atomic snapshot load', green, ts=16, bs=13)
    box(7.1, 2.87, 3.05, .9, 'Mask membership?', 'Valid near-field voxel in Mask?', green, ts=16, bs=12.5)
    # Original input reaches filtering independently of queue/worker execution.
    arrow([(.45, 7.32), (.20, 7.32), (.20, 3.32), (3.9, 3.32)], green)
    text(.55, 3.60, 'Each incoming cloud', 14, green)
    arrow([(6.55, 3.32), (7.1, 3.32)], green)
    box(11.45, 3.30, 3.85, .5, 'Removed Point Cloud', '', '#B34A00', ts=15)
    box(11.45, 2.70, 3.85, .5, 'Retained Point Cloud', '', green, ts=15)
    arrow([(10.15, 3.46), (11.45, 3.55)], '#B34A00')
    arrow([(10.15, 3.18), (11.45, 2.95)], green)
    text(10.75, 3.68, 'Hit', 12, '#B34A00', ha='center')
    text(10.75, 2.88, 'Otherwise', 11.5, green, ha='center')
    text(3.9, 2.38, 'Outside range or invalid xyz → retained. Hit/Miss denotes membership, not a semantic self/environment label.', 12)
    box(3.9, 1.67, 6.25, .52, 'Runtime Statistics  /gasf/stats', '', ink, ts=14)
    arrow([(3.58, 3.32), (3.58, 1.93), (3.9, 1.93)], ink, True)
    box(11.45, 1.67, 3.85, .52, 'Mask Model / Voxel Map', '', amber, ts=14)
    arrow([(15.3, 4.83), (15.80, 4.83), (15.80, 1.93), (15.3, 1.93)], amber)
    text(4.0, 1.46, 'Statistics: every 10 received frames', 11.5, '#555555')
    text(11.55, 1.46, '/gasf/model_points', 11.5, '#555555')
    panel(.45, .18, 14.85, 1.02, '#F5F5F5', '#DDDDDD')
    text(.65, .96, 'Current V1 Limitations', 16, weight='bold')
    text(3.7, .96, '1  Learns stable near-field structures, not semantic cage labels.', 13)
    text(3.7, .66, '2  Full body–world motion consistency checking is not yet implemented.', 13)
    text(3.7, .36, '3  No independent self/environment point labels are currently available for accuracy evaluation.', 13)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for t in texts:
        assert fig.bbox.contains(*t.get_window_extent(renderer).get_points()[0]), t.get_text()
        assert fig.bbox.contains(*t.get_window_extent(renderer).get_points()[1]), t.get_text()
    for ext in ('png', 'svg', 'pdf'):
        meta = {'Date': None} if ext == 'svg' else {'CreationDate': None, 'ModDate': None} if ext == 'pdf' else {}
        fig.savefig(HERE / f'{STEM}.{ext}', dpi=300, metadata=meta)
    plt.close(fig)
    with Image.open(HERE / f'{STEM}.png') as im:
        im.load()
        assert im.size == (4800, 2700)
        assert all(abs(d-300) < .1 for d in im.info['dpi'])
    svg = ET.parse(HERE / f'{STEM}.svg')
    assert len(svg.findall('.//{http://www.w3.org/2000/svg}text')) > 20
    assert before == digest_files(), 'Existing files changed'
    (HERE / f'{STEM}_validation.json').write_text(json.dumps({
        'status': 'PASS', 'png_px': [4800, 2700], 'dpi': 300,
        'svg_editable_text': True, 'existing_files_unchanged': len(before),
        'protected_sha256': before}, indent=2), encoding='utf-8')
    print(f'PASS: PNG/SVG/PDF exported; {len(before)} existing files unchanged.')


if __name__ == '__main__':
    main()
