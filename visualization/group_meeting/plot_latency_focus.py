"""Targeted Figure 3 revision; preserve the previous six-page set.

Run: python visualization/group_meeting/plot_latency_focus.py
Reuses the existing parser, statistics, distribution artists and slide style.
Only the latency page is exported, to figures/latency_focus/.
"""
import hashlib
import json
import xml.etree.ElementTree as ET

import plot_meeting as p


def main():
    out = p.HERE / 'figures' / 'latency_focus'
    report_dir = p.HERE / 'reports' / 'latency_focus'
    # Protect all earlier deliverables as well as the original source/log baseline.
    protected = {f: hashlib.sha256(f.read_bytes()).hexdigest()
                 for f in p.HERE.rglob('*') if f.is_file()
                 and 'latency_focus' not in f.parts
                 and '__pycache__' not in f.parts and '.mplconfig' not in f.parts}
    p.check_originals()
    parsed = p.parse_logs(p.ROOT / 'analysis/results/online_controls')
    assert parsed.diagnostics.empty
    df = p.with_derived(parsed.records)
    tables = p.compute_statistics(df)
    for name, frame in {'parsed_records': df, **tables}.items():
        assert frame.to_csv(index=False, na_rep='NA', float_format='%.12g').encode('utf-8') == (
            p.VIS / 'tables' / f'{name}.csv').read_bytes(), name
    assert df.analysis_eligible.all() and df.callback_ms.notna().all()
    assert p.np.isfinite(p.numeric(df.callback_ms)).all()
    limit = 3.2
    outside = df.loc[df.callback_ms > limit, ['group', 'frame', 'callback_ms']]
    maximum = df.loc[df.callback_ms.idxmax()]
    n = len(df)
    p.presentation_style()
    p.PLOT_CHECKS.clear()
    fig = p.canvas('Runtime Latency Distribution',
        f'{len(outside)}/{n} samples above {limit:.1f} ms; maximum = {maximum.callback_ms:.3f} ms '
        f'({maximum.group}, frame {int(maximum.frame)}).')
    fig.set_label(p.STEMS[2])
    p.legend(fig)
    grid = fig.add_gridspec(1, 2, left=.16, right=.975, bottom=.19, top=.73,
                           wspace=.25, width_ratios=[1, 1.15])
    left = fig.add_subplot(grid[0, 0])
    right = fig.add_subplot(grid[0, 1])
    # Full arrays are passed to boxplot/scatter; clipping is only a display choice.
    p.distribution(left, df, 'callback_ms')
    for dots in left.collections:
        dots.set_clip_on(True)
        dots.set_clip_path(left.patch)
    assert sum(len(c.get_offsets()) for c in left.collections) == n
    left.set(xlim=(0, limit), xlabel='Logged callback time (ms)')
    left.set_title(f'Distribution zoom | 0-{limit:.1f} ms', loc='left', pad=14)
    ecdf_at_limit = {}
    for j, g in enumerate(p.ORDER):
        x = p.np.sort(p.numeric(p.subset(df, g).callback_ms))
        y = p.np.arange(1, len(x) + 1) / len(x)
        line = right.step(p.np.r_[0, x, max(limit, x[-1])], p.np.r_[0, y, 1],
                          where='post', color=p.COLORS[g], lw=2,
                          ls=('-', '--', '-.', ':')[j % 4])[0]
        p.np.testing.assert_array_equal(line.get_xdata()[1:-1], x)
        p.np.testing.assert_array_equal(line.get_ydata()[1:-1], y)
        ecdf_at_limit[g] = float((x <= limit).sum() / len(x))
        p.log_check(fig, g, 'callback_ms', len(x), 'all samples; full-n ECDF; axes zoom only')
    p.axes_style(right, (0, limit), (0, 1.03))
    right.set(xlabel='Logged callback time (ms)', ylabel='Cumulative proportion')
    right.set_title(f'ECDF zoom | 0-{limit:.1f} ms', loc='left', pad=14)
    for ax in (left, right):
        ax.set_xticks([0, .8, 1.6, 2.4, 3.2])
        assert ax.get_xlim() == (0, limit)
    p.foot(fig,
        'Logged every 10 frames: not full-frame timing or a real-time guarantee. *04_loop_A: disturbed mounting.',
        'All statistics use all logged samples; axes are zoomed to the main range for readability.')
    p.export(fig, p.STEMS[2], out)
    with p.Image.open(out / (p.STEMS[2] + '.png')) as im:
        im.load()
        assert im.size == (4800, 2700)
        assert all(abs(d - 300) < .1 for d in im.info['dpi'])
    ET.parse(out / (p.STEMS[2] + '.svg'))
    assert (out / (p.STEMS[2] + '.pdf')).read_bytes().startswith(b'%PDF-')
    assert all(hashlib.sha256(f.read_bytes()).hexdigest() == h for f, h in protected.items())
    p.check_originals()
    report_dir.mkdir(parents=True, exist_ok=True)
    report = dict(status='PASS', samples=n, limit_ms=limit, outside_count=len(outside),
                  outside_samples=outside.to_dict('records'),
                  maximum=dict(group=maximum.group, frame=int(maximum.frame), ms=float(maximum.callback_ms)),
                  ecdf_at_limit=ecdf_at_limit, statistics_match_original_csv=True,
                  earlier_group_meeting_files_unchanged=len(protected), original_baseline_unchanged=89,
                  visual_data_checks=p.PLOT_CHECKS)
    (report_dir / 'validation.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    # Before/after at identical slide dimensions, for the Skill's Appraisal step.
    from PIL import ImageDraw
    compare = p.Image.new('RGB', (1920, 585), 'white')
    draw = ImageDraw.Draw(compare)
    for i, (label, path) in enumerate([
        ('Previous: full-range distribution', p.HERE / 'figures' / (p.STEMS[2] + '.png')),
        ('Updated: main-range axes + explicit tail report', out / (p.STEMS[2] + '.png'))]):
        draw.text((i * 960 + 20, 10), label, fill='black')
        with p.Image.open(path) as im:
            compare.paste(im.convert('RGB').resize((960, 540), p.Image.Resampling.LANCZOS), (i * 960, 40))
    compare.save(report_dir / 'before_after.png')
    print(json.dumps({k: v for k, v in report.items() if k != 'visual_data_checks'}, indent=2))


if __name__ == '__main__':
    main()
